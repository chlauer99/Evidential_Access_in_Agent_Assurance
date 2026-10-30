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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge_schema
from fhir_urls import resolve_fhir_url
from progress import completed
from request_retry import request_with_retry
import llm_config as _llm  # reproducibility package: configurable endpoint/paths (protocol unchanged)
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


class IncompleteVerdict(ValueError):
    """A recorded API or output-validation failure, safe to leave missing."""


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
    ap.add_argument("--temperature", type=float, default=0.0, help="judge temperature (paper 0); negative = omit")
    ap.add_argument("--max-tokens", type=int, default=400, help="output cap per turn (paper 400)")
    ap.add_argument("--rpm", type=float, default=None)
    ap.add_argument("--tpm", type=int, default=None, help="optional tokens-per-minute throttle")
    ap.add_argument("--strip-reasoning", action="store_true")
    ap.add_argument("--structured-output", action="store_true", help="Constrain every turn to a query or verdict JSON schema")
    ap.add_argument("--request-retries", type=int, default=3, help="Additional attempts per transient API failure")
    ap.add_argument("--continue-on-errors", action="store_true", help="Continue with recorded missing verdicts after API/validation failures")
    ap.add_argument("--summary-file", default=None)
    a = ap.parse_args(argv)
    if a.request_retries < 0:
        ap.error("--request-retries must be nonnegative")
    limiter = _llm.RateLimiter(a.rpm)
    bucket = JR["TokenBucket"](a.tpm) if a.tpm else None
    import requests
    from openai import OpenAI, APIError
    ses = requests.Session(); ses.trust_env = False
    client = OpenAI(max_retries=0, timeout=180, base_url=a.base_url, api_key=_llm.api_key(a.api_key_env))
    extra = _llm.load_extra_body(a.extra_body)
    metas = {}
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
                    if r.get("verdict") in ("pass", "fail") and (not a.structured_output or r.get("output_schema") == judge_schema.VERSION):
                        done.add((r["task_id"], int(r["attempt"])))
        for r in JR["valid_attempts"](run):
            k = (r["task_id"], int(r["attempt"]))
            if k in keys and k not in done:
                jobs.append((run, r, out))
    print(f"agentic judge {a.judge}: {len(jobs)} attempts", flush=True)
    lock = threading.Lock(); n_done = [0]

    def call(msgs, context, out, allow_queries=True):
        kw = dict(model=a.judge, messages=msgs, max_tokens=a.max_tokens)
        if a.temperature is not None and a.temperature >= 0:
            kw["temperature"] = a.temperature
        if extra:
            kw["extra_body"] = extra
        if a.structured_output:
            kw["response_format"] = judge_schema.response_format(access=True, allow_queries=allow_queries)
        est = sum(len(m_["content"]) for m_ in msgs) / 4.0 + a.max_tokens
        def before():
            limiter.acquire()
            if bucket:
                bucket.acquire(est)
        def record(event):
            with lock:
                with out.with_name(out.stem + "_request_errors.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(event) + "\n")
            print(f"API failure {context['task_id']} attempt={context['attempt']} "
                  f"turn={context['turn']} request={event['request_attempt']}/{event['max_attempts']} "
                  f"status={event['status_code']} retry={event['will_retry']}", flush=True)
        resp = request_with_retry(client.chat.completions.create, kw, context, record,
                                  retries=a.request_retries, before=before)
        if bucket:
            bucket.reconcile(est, (resp.usage.prompt_tokens or 0) + (resp.usage.completion_tokens or 0))
        metas[threading.get_ident()] = _llm.call_meta(resp, extra, a.base_url)
        u = resp.usage; ux = getattr(u, "model_extra", None) or {}
        raw_content = resp.choices[0].message.content or ""
        text = raw_content
        metas[threading.get_ident()].update(raw_response=raw_content, finish_reason=resp.choices[0].finish_reason)
        if a.strip_reasoning:
            text = _llm.strip_reasoning(text)
        return text, u.prompt_tokens, u.completion_tokens, ux.get("cost") or 0.0, \
               (getattr(resp, "model_extra", None) or {}).get("provider")

    def one(run, r, out):
        instr, ctx = load_task(r["task_id"])
        hist = json.loads(_llm.resolve_answer(ROOT, RUNS, r["answer_file"]).read_text(encoding="utf-8"))["history"]
        prompt = USER.format(instruction=instr, context=ctx, spec="", checks=ACCESS.format(k=a.max_queries, base=FHIR),
                             trajectory=render_trajectory(hist),
                             result=r["result"] if r["result"] is not None else "(no final answer)")
        if a.structured_output:
            prompt = prompt.replace(ACCESS.format(k=a.max_queries, base=FHIR),
                f"You have read-only access to the same EHR under {FHIR}. You may send up to {a.max_queries} GET queries before deciding, using FHIR search syntax as in the trajectory. You will receive the response.\n")
            prompt += ('\nSTRUCTURED TRANSPORT: Wrap every response in {"action": ...}. '
                       'For a GET request use {"action":{"query":"<url>"}}. '
                       'For your final verdict use {"action":{...the five verdict fields specified above...}}. '
                       'No plain GET lines or text outside JSON. After the query budget is used, return the final verdict.')
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
        queries, pt, ct, cost, provider, j, t0 = [], 0, 0, 0.0, None, None, time.time()
        turns, validation_error = [], None
        for turn in range(a.max_queries + 2):
            allow_queries = len(queries) < a.max_queries
            context = dict(run=run, task_id=r["task_id"], attempt=r["attempt"], turn=turn + 1,
                           judge=a.judge, tag=a.tag)
            try:
                content, p_, c_, cost_, provider = call(msgs, context, out, allow_queries=allow_queries)
            except APIError as exc:
                validation_error = f"API request failed: {type(exc).__name__}: {exc}"
                turns.append(dict(turn=turn + 1, api_error=validation_error))
                j = {"verdict": None, "parse_error": validation_error}
                break
            meta = dict(metas.get(threading.get_ident()) or {})
            turns.append(meta)
            pt += p_; ct += c_; cost += cost_
            first = content.strip().splitlines()[0].strip() if content.strip() else ""
            m = re.match(r"^GET\s+(\S+)", first)
            structured = None
            if a.structured_output:
                try:
                    structured = judge_schema.parse(content, meta.get("finish_reason"), access=True, allow_queries=allow_queries)
                except ValueError as exc:
                    validation_error = str(exc)
                    j = {"verdict": None, "parse_error": validation_error}
                    break
                if "query" in structured:
                    m = re.match(r"^GET\s+(\S+)", "GET " + structured["query"])
                else:
                    j = structured
                    break
            if m and len(queries) < a.max_queries:
                url = structured["query"].strip() if structured is not None else m.group(1)
                try:
                    url = resolve_fhir_url(url, FHIR)
                except ValueError:
                    obs = f"Refused: only GET requests under {FHIR} are allowed."
                else:
                    try:
                        # Do not let redirects bypass the validated origin/path.
                        resp = ses.get(url + ("&" if "?" in url else "?") + "_format=json", timeout=120,
                                       allow_redirects=False)
                        turns[-1].update(http_status=resp.status_code, ehr_raw_response=resp.text)
                        obs = compact(resp.text) if 200 <= resp.status_code < 300 else f"HTTP {resp.status_code}: {resp.text[:300]}"
                    except Exception as e:
                        obs = f"Request failed: {e!r}"[:300]
                turns[-1].update(query_url=url, ehr_response=obs)
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
               "prompt_variant": "neutral+ehr_access", "with_spec": False,
               "call_meta": {k: v for k, v in (metas.get(threading.get_ident()) or {}).items() if k != "raw_response"},
               "turns": turns, "validation_error": validation_error,
               "output_schema": judge_schema.VERSION if a.structured_output else None}
        with lock:
            with out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            n_done[0] += 1

        if j.get("verdict") not in ("pass", "fail") and (a.structured_output or validation_error):
            raise IncompleteVerdict(f"Invalid structured verdict for {run}/{r['task_id']}/{r['attempt']}: {validation_error}")

    errors = 0
    fatal_errors = 0
    with ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(one, *jb) for jb in jobs]
        for fut in completed(as_completed(futs), len(futs), "Aktenzugriff-Experiment"):
            try:
                fut.result()
            except IncompleteVerdict as e:
                errors += 1
                print("MISSING VERDICT", repr(e)[:300], flush=True)
            except Exception as e:
                fatal_errors += 1
                print("FATAL ERROR", repr(e)[:300], flush=True)
    print(f"agentic judge done: {n_done[0]}/{len(jobs)}", flush=True)
    summary = dict(status="failed" if fatal_errors or (errors and not a.continue_on_errors)
                   else "completed_with_missing_verdicts" if errors else "completed",
                   attempted=len(jobs), valid_new=len(jobs) - errors - fatal_errors,
                   missing_new=errors, fatal_errors=fatal_errors,
                   continue_on_errors=a.continue_on_errors)
    if a.summary_file:
        target = Path(a.summary_file)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if fatal_errors:
        raise SystemExit(f"{fatal_errors} unexpected failures; inspect log before resuming")
    if errors and not a.continue_on_errors:
        raise SystemExit(f"{errors} record-access calls failed; inspect logs/turns before resuming")
    if errors:
        print(f"WARNING: Continuing with {errors} missing verdicts; these are excluded from judge accuracy.", flush=True)


if __name__ == "__main__":
    main()
