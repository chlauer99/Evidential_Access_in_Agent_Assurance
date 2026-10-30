"""Agentic judge: the neutral model judge plus read-only access to the same FHIR EHR.

Same system prompt, task prompt and trajectory rendering as judge_runs.py (neutral variant, no checklist). The only
change is an access block: the judge may send up to --max-queries GET requests to the EHR before its verdict. It is
not told what to check. EHR responses are returned as a compact listing (bundle total, links incl. `next`, and one
line per entry with the fields a reviewer needs: codes, dates, values, patient identifiers), to bound token cost.

Output rows use the judge_runs.py format (verdict, confidence, issue_type, issues, rationale, ...) plus the queries
sent, so judge_report.py can read mab_runs/<run>/judge_<tag>.jsonl.

Usage:
  python judge_agentic.py --sample sample.json --judge deepseek/deepseek-v3.2 --tag deepseek-v3.2_access \
      --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTE --extra-body @openrouter_route_deepseek-v3.2.json
"""
from __future__ import annotations

import argparse, json, os, re, runpy, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
JR = runpy.run_path(str(HERE / "judge_runs.py"), run_name="judge_runs_mod")
SYSTEM, USER, load_task, render_trajectory = JR["SYSTEM"], JR["USER"], JR["load_task"], JR["render_trajectory"]
ROOT, RUNS = JR["ROOT"], JR["RUNS"]
FHIR = "http://localhost:8080/fhir/"

ACCESS = """You have read-only access to the same EHR. Before giving your verdict you may send up to {k} GET requests to it.
To send one, reply with a single line and nothing else:  GET <url>   (base {base}, FHIR search syntax as in the trajectory).
You will receive the response. When you are ready, reply with the JSON object only.
"""


def _val(res):
    if "valueQuantity" in res:
        q = res["valueQuantity"]; return f"{q.get('value')} {q.get('unit', '')}".strip()
    for k in ("valueString", "valueInteger", "valueBoolean", "valueDateTime"):
        if k in res:
            return str(res[k])
    if "valueCodeableConcept" in res:
        return (res["valueCodeableConcept"].get("text") or "")
    return ""


def compact(text: str, max_entries: int = 200) -> str:
    try:
        d = json.loads(text)
    except Exception:
        return text[:4000]
    if d.get("resourceType") != "Bundle":
        return json.dumps(d)[:4000]
    links = "; ".join(f"{l.get('relation')}={l.get('url')}" for l in d.get("link", []))
    ents = d.get("entry", []) or []
    lines = [f"Bundle total={d.get('total', 'n/a')}; entries in this page={len(ents)}; links: {links or 'none'}"]
    for e in ents[:max_entries]:
        r = e.get("resource", {}); rt = r.get("resourceType")
        if rt == "Patient":
            ident = ",".join(i.get("value", "") for i in r.get("identifier", []))
            nm = "; ".join(" ".join(n.get("given", []) + [n.get("family", "")]).strip() for n in r.get("name", []))
            lines.append(f"Patient id={r.get('id')} identifier={ident} name={nm} birthDate={r.get('birthDate')} gender={r.get('gender')}")
        else:
            code = ",".join(c.get("code", "") for c in (r.get("code") or r.get("medicationCodeableConcept") or {}).get("coding", []))
            when = r.get("effectiveDateTime") or r.get("authoredOn") or r.get("issued") or ""
            lines.append(f"{rt} id={r.get('id')} code={code} time={when} value={_val(r)} status={r.get('status', '')}")
    if len(ents) > max_entries:
        lines.append(f"... {len(ents) - max_entries} more entries in this page not shown")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", required=True, help="JSON list of {run, task_id, attempt}")
    ap.add_argument("--judge", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--api-key-env", default="OPENAI_API_KEY")
    ap.add_argument("--extra-body", default=None)
    ap.add_argument("--max-queries", type=int, default=4)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args(argv)
    import requests
    from openai import OpenAI
    ses = requests.Session(); ses.trust_env = False
    client = OpenAI(max_retries=10, timeout=180, base_url=a.base_url, api_key=os.environ[a.api_key_env])
    extra = (json.loads(Path(a.extra_body[1:]).read_text(encoding="utf-8")) if a.extra_body and a.extra_body.startswith("@")
             else json.loads(a.extra_body) if a.extra_body else None)
    sample = json.loads(Path(a.sample).read_text(encoding="utf-8"))
    rows_by_run = {}
    for s in sample:
        rows_by_run.setdefault(s["run"], set()).add((s["task_id"], int(s["attempt"])))
    jobs = []
    for run, keys in rows_by_run.items():
        out = RUNS / run / f"judge_{a.tag}.jsonl"
        done = set()
        if out.exists():
            for l in out.read_text(encoding="utf-8").splitlines():
                if l.strip():
                    r = json.loads(l)
                    if r.get("verdict") in ("pass", "fail"):
                        done.add((r["task_id"], int(r["attempt"])))
        for r in JR["valid_attempts"](run):
            k = (r["task_id"], int(r["attempt"]))
            if k in keys and k not in done:
                jobs.append((run, r, out))
    print(f"agentic judge {a.judge}: {len(jobs)} attempts", flush=True)
    lock = threading.Lock(); n_done = [0]

    def call(msgs):
        kw = dict(model=a.judge, messages=msgs, temperature=0, max_tokens=400)
        if extra:
            kw["extra_body"] = extra
        resp = client.chat.completions.create(**kw)
        u = resp.usage; ux = getattr(u, "model_extra", None) or {}
        return (resp.choices[0].message.content or ""), u.prompt_tokens, u.completion_tokens, ux.get("cost") or 0.0, \
               (getattr(resp, "model_extra", None) or {}).get("provider")

    def one(run, r, out):
        instr, ctx = load_task(r["task_id"])
        hist = json.loads((ROOT / r["answer_file"]).read_text(encoding="utf-8"))["history"]
        prompt = USER.format(instruction=instr, context=ctx, spec="", checks=ACCESS.format(k=a.max_queries, base=FHIR),
                             trajectory=render_trajectory(hist),
                             result=r["result"] if r["result"] is not None else "(no final answer)")
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
        queries, pt, ct, cost, provider, j, t0 = [], 0, 0, 0.0, None, None, time.time()
        for turn in range(a.max_queries + 2):
            content, p_, c_, cost_, provider = call(msgs)
            pt += p_; ct += c_; cost += cost_
            first = content.strip().splitlines()[0].strip() if content.strip() else ""
            m = re.match(r"^GET\s+(\S+)", first)
            if m and len(queries) < a.max_queries:
                url = m.group(1)
                if not url.startswith("http"):  # relative FHIR path, e.g. "Patient?family=..." -> resolve against the base
                    url = FHIR + url.lstrip("/")
                if not url.startswith(FHIR):
                    obs = f"Refused: only GET requests under {FHIR} are allowed."
                else:
                    try:
                        resp = ses.get(url + ("&" if "?" in url else "?") + "_format=json", timeout=120)
                        obs = compact(resp.text) if resp.ok else f"HTTP {resp.status_code}: {resp.text[:300]}"
                    except Exception as e:
                        obs = f"Request failed: {e!r}"[:300]
                queries.append(url)
                msgs += [{"role": "assistant", "content": content},
                         {"role": "user", "content": f"EHR RESPONSE:\n{obs}\n\n({a.max_queries - len(queries)} queries left.)"}]
                continue
            if m:  # query limit reached
                msgs += [{"role": "assistant", "content": content},
                         {"role": "user", "content": "Query limit reached. Reply with the JSON object only."}]
                continue
            mm = re.search(r"\{.*\}", content, re.S)
            try:
                j = json.loads(mm.group(0)) if mm else None
            except Exception:
                j = None
            if j is None:
                j = {"verdict": None, "parse_error": content[:300]}
            break
        if j is None:
            j = {"verdict": None, "parse_error": "no verdict within turn limit"}
        if isinstance(j.get("verdict"), str):
            j["verdict"] = j["verdict"].strip().lower()
        row = {"run": run, "task_id": r["task_id"], "category": r["category"], "attempt": r["attempt"],
               "judge_model": a.judge, "served_model": a.judge, "verdict": j.get("verdict"),
               "confidence": j.get("confidence"), "issue_type": j.get("issue_type"), "issues": j.get("issues"),
               "rationale": j.get("rationale") or j.get("parse_error"), "queries": queries, "n_queries": len(queries),
               "usage": {"prompt_tokens": pt, "completion_tokens": ct}, "latency_s": round(time.time() - t0, 1),
               "oracle_passed": r.get("passed"), "provider": provider, "cost_usd": cost,
               "prompt_variant": "neutral+ehr_access", "with_spec": False}
        with lock:
            with out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            n_done[0] += 1
            if n_done[0] % 25 == 0:
                print(f"  {n_done[0]}/{len(jobs)} graded", flush=True)

    with ThreadPoolExecutor(a.workers) as ex:
        for fut in [ex.submit(one, *jb) for jb in jobs]:
            try:
                fut.result()
            except Exception as e:
                print("ERROR", repr(e)[:300], flush=True)
    print(f"agentic judge done: {n_done[0]}/{len(jobs)}", flush=True)


if __name__ == "__main__":
    main()
