"""Offline integration test of the model-calling code paths against MOCK endpoints (no API key, no real FHIR server).

  python harness/tests/test_mock_endpoints.py [--attempts 3]

Two tiny local servers are started in threads:
  * a mock OpenAI-compatible endpoint (/v1/chat/completions) that replays archived outputs: the agent's next action
    for an agent conversation (matched on the task prompt and the number of turns so far), the archived verdict for a
    judge prompt, the archived answers for a probe prompt;
  * a mock FHIR endpoint on localhost:8080 that replays the EHR responses recorded in the same archived trajectories.
Tests:
  A  step 1  run_agents.OpenAIAgent + run_episode for archived pilot attempts -> identical trajectory, status, answer;
             per-call record includes endpoint, served model and provider/quantisation fields
  B  step 6  judge_runs.py (CLI, empty --api-key-env, custom --base-url) on the same attempts -> archived verdicts
  C  step 7  probes.py run (CLI) on archived probe items -> archived answers and scores
Limits: grading (step 3) needs the official grader against the real FHIR server (the reference solver queries
records that are not in the trajectories), so it is not exercised here; test B uses judge_runs.py's own prompt
builder to index the archived verdicts, i.e. it tests the client/CLI/parsing path, not prompt fidelity (that is
tests/test_prompts.py).
"""
from __future__ import annotations

import argparse, hashlib, json, os, runpy, shutil, socket, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

H = Path(__file__).resolve().parent.parent
ROOT = H.parent
MH = H / "mab_harness"
RAW = ROOT / "data" / "raw"
sha = lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def answer(run, rec):
    return json.loads((RAW / run / "answers" / rec["answer_file"].replace("\\", "/").split("/")[-1]).read_text(encoding="utf-8"))


class State:
    agent = {}      # sha(first prompt) -> list of raw agent texts
    judge = {}      # sha(user prompt) -> verdict JSON text
    probe = {}      # sha(prompt) -> list of answers (by sample)
    probe_i = {}
    fhir = {}       # url without &_format=json -> response body
    lock = threading.Lock()
    calls = 0


class LLM(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        msgs = body["messages"]; State.calls += 1
        first = msgs[0]["content"]
        text = None
        if msgs[0]["role"] == "user" and sha(first) in State.agent:
            k = sum(1 for m in msgs if m["role"] == "assistant")
            seq = State.agent[sha(first)]
            text = seq[k] if k < len(seq) else "FINISH([])"
        elif msgs[0]["role"] == "system" and len(msgs) > 1:
            u = msgs[1]["content"]
            if sha(u) in State.judge:
                text = State.judge[sha(u)]
            elif sha(u) in State.probe:
                with State.lock:
                    i = State.probe_i.get(sha(u), 0); State.probe_i[sha(u)] = i + 1
                lst = State.probe[sha(u)]; text = lst[i % len(lst)]
        if text is None:
            self.send_response(400); self.end_headers(); self.wfile.write(b'{"error": "no archived output for this prompt"}'); return
        out = {"id": f"mock-{State.calls}", "object": "chat.completion", "created": int(time.time()), "model": body["model"],
               "provider": "MockProvider",
               "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": text}}],
               "usage": {"prompt_tokens": len(json.dumps(msgs)) // 4, "completion_tokens": len(text) // 4,
                         "total_tokens": len(json.dumps(msgs)) // 4 + len(text) // 4}}
        b = json.dumps(out).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)


class FHIR(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        url = "http://localhost:8080" + self.path
        key = url.replace("&_format=json", "")
        body = State.fhir.get(key) or State.fhir.get(unquote(key))
        if body is None:
            self.send_response(404); self.end_headers(); return
        b = body.encode("utf-8")
        self.send_response(200); self.send_header("Content-Type", "application/fhir+json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)


def free(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--attempts", type=int, default=3)
    a = ap.parse_args()
    os.environ["NO_PROXY"] = "localhost,127.0.0.1"
    run = "pilot_gpt41"
    res = [r for r in read_jsonl(RAW / run / "results.jsonl") if r["status"] == "COMPLETED"]
    # pick attempts with GET and POST actions, different tasks
    pick, seen = [], set()
    for r in sorted(res, key=lambda r: (-r["n_post"], -r["n_get"], r["task_id"])):
        if r["task_id"] not in seen and r["n_get"] >= 1:
            pick.append(r); seen.add(r["task_id"])
        if len(pick) == a.attempts:
            break
    ra = runpy.run_path(str(MH / "run_agents.py"), run_name="ra")
    tasks = {t["id"]: t for t in ra["load_tasks"]()}
    for r in pick:
        h = answer(run, r)["history"]
        State.agent[sha(h[0]["content"])] = [m.get("raw", m["content"]) for m in h if m["role"] == "agent"]
        for i, m in enumerate(h[:-1]):
            if m["role"] == "agent" and m["content"].startswith("GET") and h[i + 1]["content"].startswith("Here is the response from the GET request:\n"):
                c = h[i + 1]["content"][len("Here is the response from the GET request:\n"):]
                c = c[: c.rfind(". Please call FINISH if you have got answers")]
                State.fhir[m["content"][3:].strip()] = c
    results = []
    port_fhir_ok = free(8080)
    llm = ThreadingHTTPServer(("127.0.0.1", 0), LLM); lport = llm.server_address[1]
    threading.Thread(target=llm.serve_forever, daemon=True).start()
    fh = None
    if port_fhir_ok:
        fh = ThreadingHTTPServer(("127.0.0.1", 8080), FHIR); threading.Thread(target=fh.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{lport}/v1"

    # ---- A: agent episodes
    if port_fhir_ok:
        agent = ra["OpenAIAgent"]("mock-gpt-4.1", 0.8, 4096, None, None, base_url=base, api_key_env="", extra_body={"provider": {"quantizations": ["fp8"]}})
        for r in pick:
            ep = ra["run_episode"](tasks[r["task_id"]], agent, 8, None)
            arch = answer(run, r)["history"]
            same = [(m["role"], m["content"]) for m in ep["history"]] == [(m["role"], m["content"]) for m in arch]
            meta = ep["served_log"][0] if ep["served_log"] else {}
            ok = same and ep["status"] == r["status"] and ep["result"] == r["result"] and meta.get("provider") == "MockProvider" \
                and meta.get("requested_quantizations") == ["fp8"] and "endpoint" in meta
            results.append(("A step 1 agent episode", f"{r['task_id']}#{r['attempt']} ({r['n_get']} GET, {r['n_post']} POST)", ok,
                            f"trajectory identical={same}, status={ep['status']}, answer={ep['result']}, call_meta={ {k: meta.get(k) for k in ('endpoint', 'provider', 'requested_quantizations')} }"))
    else:
        results.append(("A step 1 agent episode", "-", None, "port 8080 is in use (a real FHIR server?); mock FHIR not started, test skipped"))

    # ---- B: judge_runs.py CLI
    tmp = Path(tempfile.mkdtemp(prefix="mockrun_"))
    try:
        (tmp / run / "answers").mkdir(parents=True)
        with open(tmp / run / "results.jsonl", "w", encoding="utf-8") as f:
            for r in pick:
                f.write(json.dumps(r) + "\n")
                src = RAW / run / "answers" / r["answer_file"].replace("\\", "/").split("/")[-1]
                shutil.copy(src, tmp / run / "answers" / src.name)
        os.environ["MAB_RUNS_DIR"] = str(tmp)
        jr = runpy.run_path(str(MH / "judge_runs.py"), run_name="jr")
        arch_v = {(v["task_id"], v["attempt"]): v for v in read_jsonl(RAW / run / "judge_gpt-4.1.jsonl")}
        for r in pick:
            instr, ctx = jr["load_task"](r["task_id"])
            hist = answer(run, r)["history"]
            prompt = jr["USER"].format(instruction=instr, context=ctx, spec="", checks="", trajectory=jr["render_trajectory"](hist),
                                       result=r["result"] if r["result"] is not None else "(no final answer)")
            v = arch_v[(r["task_id"], r["attempt"])]
            State.judge[sha(prompt)] = json.dumps({k: v.get(k) for k in ("verdict", "confidence", "issue_type", "issues", "rationale")})
        env = dict(os.environ, MAB_RUNS_DIR=str(tmp))
        p = subprocess.run([sys.executable, str(MH / "judge_runs.py"), "--judge", "mock-judge", "--tag", "mockjudge", "--runs", run,
                            "--base-url", base, "--api-key-env", "", "--workers", "2", "--no-json-mode"], env=env, capture_output=True, text=True)
        out = {(v["task_id"], v["attempt"]): v for v in read_jsonl(tmp / run / "judge_mockjudge.jsonl")} if (tmp / run / "judge_mockjudge.jsonl").exists() else {}
        for r in pick:
            k = (r["task_id"], r["attempt"]); o, v = out.get(k, {}), arch_v[k]
            ok = bool(o) and all(o.get(f) == v.get(f) for f in ("verdict", "confidence", "rationale")) and (o.get("call_meta") or {}).get("provider") == "MockProvider"
            results.append(("B step 6 judge_runs.py", f"{k[0]}#{k[1]}", ok, f"verdict {o.get('verdict')} (archived {v.get('verdict')}); exit {p.returncode}"
                            + ("" if o else f"; stderr: {p.stderr[-300:]}")))
        # ---- C: probes.py CLI
        P = read_jsonl(RAW / "probes" / "probes_deepseekv32.jsonl")
        inst = json.loads((RAW / "probes" / "probes_instances.json").read_text(encoding="utf-8"))
        chosen = [i for i in inst if i["family"] in ("code_choice", "absence", "window")]
        chosen = [next(i for i in chosen if i["family"] == f) for f in ("code_choice", "absence", "window")]
        for i in chosen:
            ans = [x for x in sorted(P, key=lambda x: x["sample"]) if x["probe_id"] == i["probe_id"]]
            State.probe[sha(i["prompt"])] = [x["answer"] for x in ans]
        (tmp / "inst.json").write_text(json.dumps(chosen), encoding="utf-8")
        p = subprocess.run([sys.executable, str(MH / "probes.py"), "run", "--instances", str(tmp / "inst.json"), "--model", "mock",
                            "--base-url", base, "--api-key-env", "", "--samples", "3", "--workers", "1", "--out", str(tmp / "probe_out.jsonl")],
                           env=env, capture_output=True, text=True)
        got = read_jsonl(tmp / "probe_out.jsonl") if (tmp / "probe_out.jsonl").exists() else []
        for i in chosen:
            g = sorted([x for x in got if x["probe_id"] == i["probe_id"]], key=lambda x: x["sample"])
            e = sorted([x for x in P if x["probe_id"] == i["probe_id"]], key=lambda x: x["sample"])
            ok = len(g) == len(e) == 3 and [x["answer"] for x in g] == [x["answer"] for x in e] and [x["correct"] for x in g] == [x["correct"] for x in e]
            results.append(("C step 7 probes.py", i["probe_id"], ok, f"scores {[x['correct'] for x in g]} (archived {[x['correct'] for x in e]}); exit {p.returncode}"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        llm.shutdown()
        if fh:
            fh.shutdown()
    bad = 0
    for t, item, ok, note in results:
        st = "SKIP" if ok is None else ("PASS" if ok else "FAIL"); bad += (ok is False)
        print(f"{st:5} {t:24} {item:28} {note}")
    print(f"\n{'ALL MOCK TESTS PASSED' if not bad else f'{bad} MOCK TEST(S) FAILED'} ({State.calls} mock LLM calls)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
