#!/usr/bin/env python
"""MedAgentBench agent runner for the synthetic-assurance pilot (E3).

Protocol = the original MedAgentBench task loop (Jiang et al., NEJM AI 2025), reproduced verbatim:
  * one user message with the published prompt + the published FHIR function catalogue (funcs_v1.json)
  * the agent answers with exactly one text action per turn: GET ..., POST <url>\\n<json>, or FINISH([...])
  * GET requests get '&_format=json' appended and are sent to the local FHIR server
  * POST requests are validated as JSON and acknowledged but NOT written to the database
    (as in the original code), so repeated attempts never contaminate each other
  * max 8 rounds (paper setting); any other output ends the episode as an invalid action
Grading uses the official refsol grader shipped with the task package (medagentbench_logic.evaluate_submission).

Agents:
  openai  - an OpenAI chat model (needs OPENAI_API_KEY in the environment; never printed or logged)
  replay  - positive control: replays the official reference answer through the same text protocol
  null    - negative control: immediately answers FINISH([])

Examples:
  python run_agents.py --agent replay --tasks pilot --n 1 --run-name control_replay
  python run_agents.py --agent null   --tasks pilot --n 1 --run-name control_null
  python run_agents.py --agent openai --model gpt-4.1 --tasks pilot --n 8 --temperature 0.8 \\
         --workers 6 --max-total-tokens 20000000 --run-name pilot_gpt41
"""
from __future__ import annotations

import argparse, hashlib, json, math, os, random, re, sys, threading, time, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Never route requests to the local FHIR server through an outbound HTTP proxy (the grader uses requests too).
for _k in ("NO_PROXY", "no_proxy"):
    os.environ[_k] = ",".join(x for x in (os.environ.get(_k, ""), "localhost", "127.0.0.1") if x)

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TASKS_DIR = ROOT / "mab_tasks"
RUNS_DIR = ROOT / "mab_runs"
FUNCS_PATH = HERE / "funcs_v1.json"
FHIR_BASE = "http://localhost:8080/fhir/"
IMAGE_DIGEST = "jyxsu6/medagentbench@sha256:3fb83d7ed71c5476f9eb6212bd440a909ef7505922bbc757dc488a8fc0701966"
ACK = ("POST request accepted and executed successfully. Please call FINISH if you have got "
       "answers for all the questions and finished all the requested tasks")

# Verbatim from the original MedAgentBench repository (src/server/tasks/medagentbench/__init__.py).
PROMPT = """You are an expert in using FHIR functions to assist medical professionals. You are given a question and a set of possible functions. Based on the question, you will need to make one or more function/tool calls to achieve the purpose.

1. If you decide to invoke a GET function, you MUST put it in the format of
GET url?param_name1=param_value1&param_name2=param_value2...

2. If you decide to invoke a POST function, you MUST put it in the format of
POST url
[your payload data in JSON format]

3. If you have got answers for all the questions and finished all the requested tasks, you MUST call to finish the conversation in the format of (make sure the list is JSON loadable.)
FINISH([answer1, answer2, ...])

Your response must be in the format of one of the three cases, and you can call only one function each time. You SHOULD NOT include any other text in the response.

Here is a list of functions in JSON format that you can invoke. Note that you should use {api_base} as the api_base.
{functions}

Context: {context}
Question: {question}"""


# ----------------------------------------------------------------------------- tasks & grader
def load_logic():
    tests = TASKS_DIR / "task10_1" / "tests"          # grader files are identical across tasks
    if str(tests) not in sys.path:
        sys.path.insert(0, str(tests))
    import medagentbench_logic  # noqa: E402
    return medagentbench_logic


def _section(md: str, title: str) -> str:
    m = re.search(rf"## {re.escape(title)}\s*\n(.*?)(?=\n## |\Z)", md, re.S)
    return m.group(1).strip() if m else ""


def load_tasks() -> list[dict]:
    tasks = []
    for d in sorted(TASKS_DIR.glob("task*_*"), key=lambda p: (int(p.name[4:].split("_")[0]), int(p.name.split("_")[1]))):
        md_path, meta_path = d / "instruction.md", d / "tests" / "task_metadata.json"
        if not (md_path.exists() and meta_path.exists()):
            continue
        md = md_path.read_text(encoding="utf-8")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["fhir_api_base"] = FHIR_BASE
        tasks.append({"id": d.name, "category": d.name.split("_")[0],
                      "instruction": _section(md, "Original Instruction"),
                      "context": _section(md, "Context"), "metadata": meta})
    return tasks


def select_pilot(tasks: list[dict], per_category: int = 3, seed: int = 2026) -> list[dict]:
    rng = random.Random(seed)
    out = []
    for cat in sorted({t["category"] for t in tasks}, key=lambda c: int(c[4:])):
        pool = [t for t in tasks if t["category"] == cat]
        out += sorted(rng.sample(pool, per_category), key=lambda t: int(t["id"].split("_")[1]))
    return out


# ----------------------------------------------------------------------------- agents
class TokenBucket:
    """Client-side tokens-per-minute throttle shared by all worker threads.

    Keeps request volume under the account's TPM limit so the API never rejects calls with 429s.
    The estimate (chars/4 + output allowance) is reconciled against actual usage after each call.
    """

    def __init__(self, tpm: int):
        self.tpm, self.level, self.t = float(tpm), float(tpm), time.monotonic()
        self.lock = threading.Lock()

    def _refill(self):
        now = time.monotonic()
        self.level = min(self.tpm, self.level + (now - self.t) * self.tpm / 60.0)
        self.t = now

    def acquire(self, n: float):
        n = min(n, self.tpm)                    # a single oversized request waits for a full bucket
        while True:
            with self.lock:
                self._refill()
                if self.level >= n:
                    self.level -= n
                    return
                wait = (n - self.level) * 60.0 / self.tpm
            time.sleep(min(max(wait, 0.05), 5.0))

    def reconcile(self, estimated: float, actual: float):
        with self.lock:
            self.level -= (actual - estimated)


class OpenAIAgent:
    """Any OpenAI-compatible chat endpoint (OpenAI itself, or e.g. OpenRouter via --base-url/--api-key-env).

    v2 additions (protocol unchanged): base_url / api_key_env / extra_body, and a per-response log of the served
    model, the upstream provider and the reported cost (state['served_log'], written to results.jsonl).
    """

    def __init__(self, model: str, temperature: float | None, max_output_tokens: int, reasoning_effort: str | None,
                 tpm: int | None = None, base_url: str | None = None, api_key_env: str = "OPENAI_API_KEY",
                 extra_body: dict | None = None):
        from openai import OpenAI
        if not os.environ.get(api_key_env):
            raise RuntimeError(f"{api_key_env} is not set in the environment")
        self.client = OpenAI(max_retries=10, timeout=180, base_url=base_url, api_key=os.environ[api_key_env])
        self.model, self.temperature = model, temperature
        self.max_output_tokens, self.reasoning_effort = max_output_tokens, reasoning_effort
        self.extra_body = extra_body or None
        self.bucket = TokenBucket(tpm) if tpm else None
        self._drop_temperature = False
        host = re.sub(r"^https?://(?:api\.)?([^/:]+).*$", r"\1", base_url).split(".")[0] if base_url else "openai"
        self.name = f"{host}:{model}"
        self.default_provider = host

    def act(self, messages, task, state):
        est = sum(len(m["content"]) for m in messages) / 4.0 + 300
        if self.bucket:
            self.bucket.acquire(est)
        text, usage, dt, served = self._call(messages)
        if self.bucket:
            self.bucket.reconcile(est, usage["prompt_tokens"] + usage["completion_tokens"])
        state.setdefault("served_log", []).append(self._last_log)
        return text, usage, dt, served

    def _call(self, messages):
        # same 4096-token output cap; OpenRouter documents it as `max_tokens` for most upstream providers
        cap_field = "max_tokens" if self.default_provider != "openai" else "max_completion_tokens"
        kwargs = dict(model=self.model, messages=messages, **{cap_field: self.max_output_tokens})
        if self.temperature is not None and not self._drop_temperature:
            kwargs["temperature"] = self.temperature
        if self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort
        if self.extra_body:
            kwargs["extra_body"] = self.extra_body
        t0 = time.time()
        try:
            resp = self.client.chat.completions.create(**kwargs)
        except Exception as exc:  # some reasoning models reject a non-default temperature
            if "temperature" in str(exc).lower() and "temperature" in kwargs:
                self._drop_temperature = True
                kwargs.pop("temperature")
                resp = self.client.chat.completions.create(**kwargs)
            else:
                raise
        u = resp.usage
        usage = {"prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
                 "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
                 "reasoning_tokens": getattr(getattr(u, "completion_tokens_details", None), "reasoning_tokens", 0) or 0,
                 "cached_tokens": getattr(getattr(u, "prompt_tokens_details", None), "cached_tokens", 0) or 0}
        if not resp.choices:                      # some gateways return 200 with an error body and no choices
            raise RuntimeError(f"no choices in response: {str(getattr(resp, 'model_extra', ''))[:200]}")
        extra = getattr(resp, "model_extra", None) or {}
        u_extra = (getattr(u, "model_extra", None) or {}) if u is not None else {}
        self._last_log = {"id": getattr(resp, "id", None), "model": resp.model,
                          "provider": extra.get("provider") or self.default_provider,
                          "cost_usd": u_extra.get("cost"), "prompt_tokens": usage["prompt_tokens"],
                          "completion_tokens": usage["completion_tokens"], "reasoning_tokens": usage["reasoning_tokens"],
                          "finish_reason": resp.choices[0].finish_reason}
        return (resp.choices[0].message.content or ""), usage, time.time() - t0, resp.model


class ReplayAgent:
    """Positive control: emit the official reference answer (POSTs, then FINISH) through the text protocol."""
    name = "control:replay"

    def __init__(self, logic, run_dir: Path):
        self.logic, self.tmp = logic, run_dir / "_oracle"
        self.tmp.mkdir(parents=True, exist_ok=True)

    def act(self, messages, task, state):
        if "script" not in state:
            ans = self.logic.run_oracle(metadata=task["metadata"], answer_path=self.tmp / f"{task['id']}.json")
            script = []
            hist = ans.get("history", []) if isinstance(ans, dict) else []
            for h in hist:
                if h.get("role") == "agent" and h.get("content", "").startswith("POST"):
                    script.append(h["content"])
            result = ans["result"] if isinstance(ans, dict) else ans
            script.append("FINISH(" + (result if isinstance(result, str) else json.dumps(result)) + ")")
            state["script"] = script
        return state["script"].pop(0), {}, 0.0, "replay"


class NullAgent:
    """Negative control: answer immediately with an empty list and take no actions."""
    name = "control:null"

    def act(self, messages, task, state):
        return "FINISH([])", {}, 0.0, "null"


# ----------------------------------------------------------------------------- episode
def run_episode(task, agent, max_rounds: int, max_get_chars: int | None):
    prompt = PROMPT.format(api_base=FHIR_BASE, functions=json.dumps(json.loads(FUNCS_PATH.read_text(encoding="utf-8"))),
                           context=task["context"], question=task["instruction"])
    messages = [{"role": "user", "content": prompt}]
    history = [{"role": "user", "content": prompt}]
    usage_tot = {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "cached_tokens": 0}
    state, status, result, n_get, n_post, served_model, latency = {}, "TASK_LIMIT_REACHED", None, 0, 0, None, 0.0
    rounds = 0
    for rounds in range(1, max_rounds + 1):
        try:
            text, usage, dt, served_model = agent.act(messages, task, state)
        except Exception as exc:
            msg = str(exc)
            status = "AGENT_CONTEXT_LIMIT" if "context" in msg.lower() and "length" in msg.lower() else "API_ERROR"
            history.append({"role": "system", "content": f"{status}: {msg[:300]}"})
            break
        latency += dt
        for k in usage_tot:
            usage_tot[k] += usage.get(k, 0)
        r = text.strip().replace("```tool_code", "").replace("```", "").strip()
        history.append({"role": "agent", "content": r})
        messages.append({"role": "assistant", "content": text})
        if r.startswith("GET"):
            n_get += 1
            url = r[3:].strip() + "&_format=json"
            if not url.startswith(FHIR_BASE):
                feedback = "Error in sending the GET request: only the provided FHIR api_base may be used"
            else:
                try:
                    g = requests.get(url, timeout=120)
                    g.raise_for_status()
                    data = g.text
                    if max_get_chars and len(data) > max_get_chars:
                        data = data[:max_get_chars] + " ...[truncated]"
                    feedback = (f"Here is the response from the GET request:\n{data}. Please call FINISH if you have "
                                f"got answers for all the questions and finished all the requested tasks")
                except Exception as exc:
                    feedback = f"Error in sending the GET request: {exc}"
        elif r.startswith("POST"):
            try:
                json.loads("\n".join(r.split("\n")[1:]))
            except Exception:
                feedback = "Invalid POST request"
            else:
                n_post += 1
                feedback = ACK
        elif r.startswith("FINISH("):
            status, result = "COMPLETED", r[len("FINISH("):-1]
            break
        else:
            status = "AGENT_INVALID_ACTION"
            break
        history.append({"role": "user", "content": feedback})
        messages.append({"role": "user", "content": feedback})
    return {"status": status, "result": result, "history": history, "rounds": rounds, "n_get": n_get,
            "n_post": n_post, "usage": usage_tot, "latency_s": round(latency, 2), "served_model": served_model,
            "served_log": state.get("served_log", [])}


def count_accepted_posts(history) -> int:
    return sum(1 for i, h in enumerate(history[:-1])
               if h.get("role") == "agent" and h.get("content", "").startswith("POST")
               and "POST request accepted" in history[i + 1].get("content", ""))


def failure_type(passed, status, ref_posts, agent_posts):
    if passed:
        return "none"
    if status != "COMPLETED":
        return "no_finish"
    if ref_posts > 0 and agent_posts == 0:
        return "omission"
    if ref_posts == 0 and agent_posts > 0:
        return "commission"
    if ref_posts > 0 and agent_posts > 0:
        return "wrong_order_or_answer"
    return "wrong_answer"


# ----------------------------------------------------------------------------- summary
def pass_at_k(n: int, c: int, k: int) -> float:
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def summarise(run_dir: Path, price_in: float | None, price_out: float | None) -> dict:
    raw = [json.loads(l) for l in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    # API errors (e.g. rate-limit 429s) are infrastructure failures, not agent outcomes: they are excluded and
    # re-run on resume. Keep the last valid row per (task, attempt).
    latest = {}
    for r in raw:
        if r["status"] != "API_ERROR":
            latest[(r["task_id"], r["attempt"])] = r
    rows = list(latest.values())
    n_api_err = sum(r["status"] == "API_ERROR" for r in raw)
    if not rows:
        return {"attempts": 0, "api_error_rows_excluded": n_api_err}
    by_task: dict[str, list] = {}
    for r in rows:
        by_task.setdefault(r["task_id"], []).append(r)
    per_task = []
    for tid, rs in by_task.items():
        n, c = len(rs), sum(r["passed"] for r in rs)
        per_task.append({"task_id": tid, "category": rs[0]["category"], "n": n, "correct": c,
                         "pass@1": c / n, "pass@8": pass_at_k(n, c, 8) if n >= 8 else None})
    n_all = len(rows)
    tok_in = sum(r["usage"]["prompt_tokens"] for r in rows)
    tok_out = sum(r["usage"]["completion_tokens"] for r in rows)
    cats = sorted({p["category"] for p in per_task}, key=lambda c: int(c[4:]))
    summ = {
        "attempts": n_all, "tasks": len(per_task),
        "mean_pass@1": round(sum(p["pass@1"] for p in per_task) / max(1, len(per_task)), 4),
        "mean_pass@8": (round(sum(p["pass@8"] for p in per_task) / len(per_task), 4)
                        if per_task and all(p["pass@8"] is not None for p in per_task) else None),
        "by_category_pass@1": {c: round(sum(p["pass@1"] for p in per_task if p["category"] == c) /
                                        sum(1 for p in per_task if p["category"] == c), 3) for c in cats},
        "status_counts": {s: sum(r["status"] == s for r in rows) for s in sorted({r["status"] for r in rows})},
        "failure_types": {f: sum(r["failure_type"] == f for r in rows) for f in sorted({r["failure_type"] for r in rows})},
        "mean_rounds": round(sum(r["rounds"] for r in rows) / max(1, n_all), 2),
        "tokens_in": tok_in, "tokens_out": tok_out,
        "mean_tokens_per_attempt": round((tok_in + tok_out) / max(1, n_all)),
        "served_models": sorted({r["served_model"] for r in rows if r.get("served_model")}),
        "providers": sorted({p for r in rows for p in r.get("providers", [])}),
        "cost_usd_reported_by_gateway": (round(sum(r["cost_usd_reported"] for r in rows), 4)
                                         if rows and all(r.get("cost_usd_reported") is not None for r in rows) else None),
        "api_error_rows_excluded": n_api_err,
    }
    if price_in is not None and price_out is not None:
        cost = tok_in / 1e6 * price_in + tok_out / 1e6 * price_out
        summ["cost_usd"] = round(cost, 2)
        summ["cost_per_attempt_usd"] = round(cost / max(1, n_all), 4)
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    import csv
    with open(run_dir / "per_task.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(per_task[0].keys()))
        w.writeheader(); w.writerows(sorted(per_task, key=lambda p: (int(p["category"][4:]), int(p["task_id"].split("_")[1]))))
    return summ


# ----------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent", choices=["openai", "replay", "null"], required=True)
    ap.add_argument("--model", default="gpt-4.1")
    ap.add_argument("--tasks", default="pilot", help="'pilot' (3 per category, seed 2026), 'all', or comma-separated ids")
    ap.add_argument("--n", type=int, default=8, help="attempts per task")
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--reasoning-effort", default=None)
    ap.add_argument("--max-rounds", type=int, default=8)
    ap.add_argument("--max-output-tokens", type=int, default=4096)
    ap.add_argument("--max-get-chars", type=int, default=None, help="optional cap on GET response size (default: none, as in the paper)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-total-tokens", type=int, default=None, help="stop scheduling new attempts beyond this budget")
    ap.add_argument("--tpm", type=int, default=None, help="client-side tokens-per-minute throttle (set just under your account limit)")
    ap.add_argument("--price-in", type=float, default=None, help="USD per 1M input tokens (for the cost estimate)")
    ap.add_argument("--price-out", type=float, default=None, help="USD per 1M output tokens")
    ap.add_argument("--run-name", required=True)
    ap.add_argument("--base-url", default=None, help="OpenAI-compatible endpoint, e.g. https://openrouter.ai/api/v1 (default: OpenAI)")
    ap.add_argument("--api-key-env", default="OPENAI_API_KEY", help="environment variable holding the API key (never printed)")
    ap.add_argument("--extra-body", default=None, help="JSON object (or @path/to/file.json) passed as extra_body, e.g. OpenRouter provider routing")
    a = ap.parse_args(argv)

    logic = load_logic()
    all_tasks = load_tasks()
    if a.tasks == "pilot":
        tasks = select_pilot(all_tasks)
    elif a.tasks == "all":
        tasks = all_tasks
    else:
        ids = set(a.tasks.split(","))
        tasks = [t for t in all_tasks if t["id"] in ids]
    assert tasks, "no tasks selected"

    run_dir = RUNS_DIR / a.run_name
    (run_dir / "answers").mkdir(parents=True, exist_ok=True)
    cfg = {k: v for k, v in vars(a).items()}
    cfg.update({"started_utc": datetime.now(timezone.utc).isoformat(), "task_ids": [t["id"] for t in tasks],
                "fhir_image": IMAGE_DIGEST, "protocol": "MedAgentBench original (verbatim prompt, funcs_v1, POSTs not executed)",
                "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16],
                "funcs_sha256": hashlib.sha256(FUNCS_PATH.read_bytes()).hexdigest()[:16]})
    (run_dir / "run_config.json").write_text(json.dumps(cfg, indent=1), encoding="utf-8")

    agent_factory = {
        "openai": lambda: OpenAIAgent(a.model, a.temperature, a.max_output_tokens, a.reasoning_effort, a.tpm,
                                      base_url=a.base_url, api_key_env=a.api_key_env,
                                      extra_body=(json.loads(Path(a.extra_body[1:]).read_text(encoding="utf-8"))
                                                  if a.extra_body and a.extra_body.startswith("@")
                                                  else json.loads(a.extra_body) if a.extra_body else None)),
        "replay": lambda: ReplayAgent(logic, run_dir),
        "null": lambda: NullAgent(),
    }[a.agent]
    agent = agent_factory()

    # reference POST counts (for omission / commission coding), computed once per task
    ref_dir = run_dir / "_reference"; ref_dir.mkdir(exist_ok=True)
    ref_posts = {}
    for t in tasks:
        ans = logic.run_oracle(metadata=t["metadata"], answer_path=ref_dir / f"{t['id']}.json")
        ref_posts[t["id"]] = count_accepted_posts(ans.get("history", [])) if isinstance(ans, dict) else 0

    results_path = run_dir / "results.jsonl"
    done = set()
    if results_path.exists():
        for l in results_path.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                if r["status"] != "API_ERROR":          # rate-limited / failed API attempts are re-run
                    done.add((r["task_id"], r["attempt"]))
    jobs = [(t, k) for t in tasks for k in range(a.n) if (t["id"], k) not in done]
    lock, tokens_used, stop = threading.Lock(), [0], threading.Event()
    print(f"{len(tasks)} tasks x {a.n} attempts; {len(jobs)} to run ({len(done)} already done) -> {run_dir}", flush=True)

    def one(t, k):
        if stop.is_set():
            return None
        ep = run_episode(t, agent, a.max_rounds, a.max_get_chars)
        ans_path = run_dir / "answers" / f"{t['id']}__{k:02d}.json"
        ans_path.write_text(json.dumps({"result": ep["result"], "history": ep["history"]}), encoding="utf-8")
        if ep["status"] == "COMPLETED":
            passed, detail = logic.evaluate_submission(metadata=t["metadata"], answer_path=ans_path)
        else:
            passed, detail = False, f"{t['id']}: episode ended with {ep['status']}"
        agent_posts = count_accepted_posts(ep["history"])
        row = {"task_id": t["id"], "category": t["category"], "attempt": k, "agent": agent.name,
               "served_model": ep["served_model"], "status": ep["status"], "passed": bool(passed),
               "grader_detail": detail, "failure_type": failure_type(passed, ep["status"], ref_posts[t["id"]], agent_posts),
               "ref_posts": ref_posts[t["id"]], "agent_posts": agent_posts, "rounds": ep["rounds"],
               "n_get": ep["n_get"], "n_post": ep["n_post"], "usage": ep["usage"], "latency_s": ep["latency_s"],
               "result": ep["result"], "answer_file": str(ans_path.relative_to(ROOT)),
               "providers": sorted({str(x.get("provider")) for x in ep["served_log"]}),
               "served_models": sorted({str(x.get("model")) for x in ep["served_log"]}),
               "cost_usd_reported": (round(sum(x["cost_usd"] for x in ep["served_log"]), 6)
                                     if ep["served_log"] and all(x.get("cost_usd") is not None for x in ep["served_log"]) else None),
               "served_log": ep["served_log"]}
        with lock:
            with open(results_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            tokens_used[0] += ep["usage"]["prompt_tokens"] + ep["usage"]["completion_tokens"]
            if a.max_total_tokens and tokens_used[0] >= a.max_total_tokens:
                stop.set()
        return row

    n_done = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(one, t, k) for t, k in jobs]
        for f in as_completed(futs):
            try:
                if f.result() is not None:
                    n_done += 1
                    if n_done % 20 == 0:
                        print(f"  {n_done}/{len(jobs)} attempts, tokens so far {tokens_used[0]:,}", flush=True)
            except Exception:
                traceback.print_exc()
    if stop.is_set():
        print(f"Token budget reached ({tokens_used[0]:,}); stopped early. Re-run the same command to resume.", flush=True)
    print(json.dumps(summarise(run_dir, a.price_in, a.price_out), indent=1), flush=True)


if __name__ == "__main__":
    main()
