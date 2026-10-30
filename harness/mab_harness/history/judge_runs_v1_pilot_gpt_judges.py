#!/usr/bin/env python
"""Model-judge grading of MedAgentBench trajectories (synthetic-assurance condition, E1/E3 pilot).

The judge sees what a quality or procurement reviewer without the answer key would see:
  * the task instruction and context,
  * the agent's full trajectory: every action and the raw EHR (FHIR) response it received,
  * the agent's final answer.
It does NOT see the reference answer or the official grader's verdict. The prompt is neutral: it does not
name error types to look for or say how to treat formatting, so the judge's own assurance biases show.

Output: mab_runs/<run>/judge_<model>.jsonl, one row per attempt (verdict, confidence, issue type, issues,
rationale, token usage, served model snapshot). Resumable. The API key is read from OPENAI_API_KEY and is
never printed or written.

Usage:
  python judge_runs.py --judge gpt-4.1 --runs pilot_gpt41,control_replay,control_null --tpm 27000 --workers 3
"""
from __future__ import annotations

import argparse, json, os, re, sys, threading, time, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = ROOT / "mab_runs"
TASKS = ROOT / "mab_tasks"

sys.path.insert(0, str(HERE))
import importlib.util
_spec = importlib.util.spec_from_file_location("run_agents", HERE / "run_agents.py")
_ra = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_ra)
TokenBucket = _ra.TokenBucket

SYSTEM = ("You are reviewing the work of an AI agent that operated on a hospital's electronic health record "
          "through a FHIR API on behalf of a clinician. Assess whether the agent's work can be relied on.")

USER = """TASK GIVEN TO THE AGENT
{instruction}

CONTEXT GIVEN TO THE AGENT
{context}
{spec}
AGENT TRAJECTORY (each action the agent took, followed by the response returned by the EHR)
{trajectory}

FINAL ANSWER RETURNED BY THE AGENT
{result}

Did the agent complete the task correctly? Consider both its final answer and any orders (POST requests) it placed or did not place.
Respond with a JSON object with exactly these keys:
  "verdict": "pass" or "fail",
  "confidence": integer 0-100 (your confidence in the verdict),
  "issue_type": one of "none", "answer", "orders", "format", "other",
  "issues": list of short strings (at most 3, each at most 15 words; empty if none),
  "rationale": string of at most 60 words."""


def _section(md, title):
    m = re.search(rf"## {re.escape(title)}\s*\n(.*?)(?=\n## |\Z)", md, re.S)
    return m.group(1).strip() if m else ""


def load_task(tid):
    md = (TASKS / tid / "instruction.md").read_text(encoding="utf-8")
    return _section(md, "Original Instruction"), _section(md, "Context")


def render_trajectory(history):
    """Agent actions and EHR responses, skipping the initial prompt (it holds the function catalogue)."""
    lines, step = [], 0
    for h in history[1:]:
        if h["role"] == "agent":
            step += 1
            lines.append(f"[Step {step}] AGENT ACTION:\n{h['content']}")
        elif h["role"] == "user":
            lines.append(f"EHR RESPONSE:\n{h['content']}")
        else:
            lines.append(f"[system note] {h['content']}")
    return "\n\n".join(lines) if lines else "(no actions)"


def valid_attempts(run):
    latest = {}
    for l in (RUNS / run / "results.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            if r["status"] != "API_ERROR":
                latest[(r["task_id"], r["attempt"])] = r
    return [latest[k] for k in sorted(latest, key=lambda k: (int(k[0][4:].split("_")[0]), int(k[0].split("_")[1]), k[1]))]


def probe_limits(model):
    """One minimal call to read this account's per-minute limits for a model from the response headers."""
    from openai import OpenAI
    c = OpenAI(max_retries=3, timeout=60)
    raw = c.chat.completions.with_raw_response.create(model=model, messages=[{"role": "user", "content": "ok"}],
                                                      max_completion_tokens=1)
    h = raw.headers
    return {"model": model, "tokens_per_min": h.get("x-ratelimit-limit-tokens"),
            "requests_per_min": h.get("x-ratelimit-limit-requests")}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--judge", required=True)
    ap.add_argument("--runs", required=True, help="comma-separated run names under mab_runs/")
    ap.add_argument("--tpm", type=int, default=None)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--with-spec", action="store_true",
                    help="ablation: also show the judge the FHIR function catalogue the agent was given "
                         "(output file judge_<model>_spec.jsonl)")
    a = ap.parse_args(argv)
    spec_block = ""
    if a.with_spec:
        spec_block = ("\nAPI SPECIFICATION GIVEN TO THE AGENT (the hospital's FHIR function catalogue)\n"
                      + Path(_ra.FUNCS_PATH).read_text(encoding="utf-8").strip() + "\n")

    from openai import OpenAI
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")
    client = OpenAI(max_retries=10, timeout=180)
    bucket = TokenBucket(a.tpm) if a.tpm else None
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", a.judge) + ("_spec" if a.with_spec else "")

    jobs = []
    for run in a.runs.split(","):
        out = RUNS / run / f"judge_{safe}.jsonl"
        done = set()
        if out.exists():
            for l in out.read_text(encoding="utf-8").splitlines():
                if l.strip():
                    r = json.loads(l)
                    if r.get("verdict") in ("pass", "fail"):
                        done.add((r["task_id"], r["attempt"]))
        for r in valid_attempts(run):
            if (r["task_id"], r["attempt"]) not in done:
                jobs.append((run, r, out))
    print(f"judge {a.judge}: {len(jobs)} attempts to grade", flush=True)
    lock = threading.Lock()

    def one(run, r, out):
        instr, ctx = load_task(r["task_id"])
        hist = json.loads((ROOT / r["answer_file"]).read_text(encoding="utf-8"))["history"]
        prompt = USER.format(instruction=instr, context=ctx, spec=spec_block, trajectory=render_trajectory(hist),
                             result=r["result"] if r["result"] is not None else "(no final answer)")
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
        est = (len(SYSTEM) + len(prompt)) / 4.0 + 400
        if bucket:
            bucket.acquire(est)
        t0 = time.time()
        resp = client.chat.completions.create(model=a.judge, messages=msgs, temperature=0,
                                              max_completion_tokens=400, response_format={"type": "json_object"})
        usage = {"prompt_tokens": resp.usage.prompt_tokens, "completion_tokens": resp.usage.completion_tokens}
        if bucket:
            bucket.reconcile(est, usage["prompt_tokens"] + usage["completion_tokens"])
        try:
            j = json.loads(resp.choices[0].message.content)
        except Exception:
            j = {"verdict": None, "parse_error": (resp.choices[0].message.content or "")[:300]}
        row = {"run": run, "task_id": r["task_id"], "category": r["category"], "attempt": r["attempt"],
               "judge_model": a.judge, "served_model": resp.model,
               "verdict": j.get("verdict"), "confidence": j.get("confidence"), "issue_type": j.get("issue_type"),
               "issues": j.get("issues"), "rationale": j.get("rationale"), "usage": usage,
               "latency_s": round(time.time() - t0, 2), "oracle_passed": r["passed"]}
        with lock:
            with open(out, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
        return row

    n = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(one, *j) for j in jobs]
        for f in as_completed(futs):
            try:
                f.result(); n += 1
                if n % 50 == 0:
                    print(f"  {n}/{len(jobs)} graded", flush=True)
            except Exception:
                traceback.print_exc()
    print(f"judge {a.judge}: graded {n}/{len(jobs)}", flush=True)


if __name__ == "__main__":
    main()
