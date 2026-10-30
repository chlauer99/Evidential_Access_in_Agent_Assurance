"""Automated, evidence-backed error-mechanism tracer for MedAgentBench attempts (original protocol).

For every non-passing attempt (outcome classes from analyse_pilot.classify_failures), the tracer parses the agent's
trajectory (GET queries, EHR responses, POST orders, final answer), queries the FHIR server for the patient's full
record, and assigns ONE mechanism with an evidence string. Labels (and error locus):

  evidence gathering : false_absence           searched with a code other than the local code (or wrong search
                                                parameters) -> empty result, although data exist
                       incomplete_retrieval    a `next` link was not followed and the true target lies on an unread page
  conclusion         : time_window_error       reported value lies outside the requested window (or -1/absent claimed
                                                when an in-window value was retrieved)
                       computation_error       correct values retrieved, derived number wrong (mean, age, dose)
                       answer_error_other      wrong answer not explained by the rules above
  action             : unnecessary_order       an order the task rule did not require
                       no_action_on_detected_absence   data correctly found missing/outdated, required order not placed
                       order_rule_omission     value correctly retrieved, rule required an order, none placed
                       order_content_error     order placed with wrong content (dose, code, time, payload)
  other              : protocol_failure        no valid FINISH (invalid action or round limit)
                       format_only / pass_without_acting   carried over from the outcome classifier
Omissions/commissions that follow from an evidence-gathering error are labelled with that upstream mechanism
(upstream_of_action = True), as in the hand-traced pilot.
"""
from __future__ import annotations

import contextlib, io, json, math, re, runpy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = ROOT / "mab_runs"
FHIR = "http://localhost:8080/fhir/"
NOW = datetime(2023, 11, 13, 10, 15, tzinfo=timezone.utc)
LOCAL = {"task4": "MG", "task5": "MG", "task6": "GLU", "task7": "GLU", "task9": "K", "task10": "A1C"}
_S = requests.Session(); _S.trust_env = False
_CACHE: dict = {}

LOCUS = {"false_absence": "evidence_gathering", "incomplete_retrieval": "evidence_gathering",
         "time_window_error": "conclusion", "computation_error": "conclusion", "answer_error_other": "conclusion",
         "unnecessary_order": "action", "no_action_on_detected_absence": "action", "order_rule_omission": "action",
         "order_content_error": "action", "protocol_failure": "other", "format_only": "format",
         "pass_without_acting": "grader", "unmapped": "other"}


# ----------------------------------------------------------------------------- parsing
def _dt(s):
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _bundle(text):
    i = text.find("{")
    if i < 0:
        return None
    try:
        b, _ = json.JSONDecoder().raw_decode(text[i:])
        return b if isinstance(b, dict) else None
    except Exception:
        return None


def parse_steps(history):
    """Agent actions paired with the EHR response that followed each."""
    out, h = [], history[1:]
    for i, m in enumerate(h):
        if m["role"] != "agent":
            continue
        c = m["content"].strip()
        resp = h[i + 1]["content"] if i + 1 < len(h) and h[i + 1]["role"] == "user" else ""
        if c.startswith("GET"):
            url = c[3:].strip().split()[0] if c[3:].strip() else ""
            q = parse_qs(urlparse(url).query)
            b = _bundle(resp)
            ents = [e.get("resource", {}) for e in (b or {}).get("entry", [])]
            links = {l.get("relation"): l.get("url") for l in (b or {}).get("link", [])}
            out.append({"kind": "GET", "url": url, "path": urlparse(url).path.rstrip("/").split("/")[-1],
                        "q": {k: v[0] for k, v in q.items()}, "total": (b or {}).get("total"),
                        "entries": ents, "next": links.get("next")})
        elif c.startswith("POST"):
            first, _, body = c.partition("\n")
            try:
                payload = json.loads(body) if body.strip() else None
            except Exception:
                payload = None
            out.append({"kind": "POST", "url": first[4:].strip(), "payload": payload})
        elif c.startswith("FINISH("):
            out.append({"kind": "FINISH", "answer": c[len("FINISH("):-1]})
    return out


def obs_points(entries):
    pts = []
    for r in entries:
        if r.get("resourceType") != "Observation":
            continue
        v = (r.get("valueQuantity") or {}).get("value")
        pts.append((_dt(r.get("effectiveDateTime")), v, r.get("id")))
    return [p for p in pts if p[0] is not None]


def server_obs(patient, code):
    key = (patient, code)
    if key not in _CACHE:
        r = _S.get(FHIR + "Observation", params={"patient": patient, "code": code, "_count": 5000, "_format": "json"},
                   timeout=60)
        r.raise_for_status()
        _CACHE[key] = obs_points([e.get("resource", {}) for e in r.json().get("entry", [])])
    return _CACHE[key]


def numbers(ans):
    """Numbers in the final answer, with dates/timestamps removed first."""
    s = re.sub(r"\d{4}-\d{2}-\d{2}(?:[T ][\d:.]+(?:Z|[+-]\d{2}:?\d{2})?)?", " ", str(ans))
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", s)]


def mrn_of(task):
    m = re.search(r"\bS\d{6,8}\b", task["instruction"])
    return m.group(0) if m else None


def close(a, b, tol=0.051):
    return a is not None and b is not None and abs(a - b) <= tol


# ----------------------------------------------------------------------------- orders
def med_doses(posts):
    out = []
    for p in posts:
        pl = p.get("payload") or {}
        if pl.get("resourceType") == "MedicationRequest" or "MedicationRequest" in p["url"]:
            try:
                out.append(float(pl["dosageInstruction"][0]["doseAndRate"][0]["doseQuantity"]["value"]))
            except Exception:
                out.append(None)
    return out


def service_reqs(posts):
    return [p for p in posts if "ServiceRequest" in p["url"] or (p.get("payload") or {}).get("resourceType") == "ServiceRequest"]


# ----------------------------------------------------------------------------- detectors
def evidence_gathering(cat, patient, steps):
    """Return (mechanism, evidence) for false absence / incomplete retrieval, or (None, None)."""
    local = LOCAL.get(cat)
    gets = [s for s in steps if s["kind"] == "GET" and s["path"] == "Observation"]
    if not local:
        return None, None
    truth = server_obs(patient, local)
    codes = [s["q"].get("code", "") for s in gets]
    used_local = any(c.split("|")[-1].upper() == local for c in codes)
    if truth and not used_local and gets and all((s["total"] or 0) == 0 for s in gets):
        return "false_absence", f"queried code(s) {sorted(set(codes))} -> 0 results; local code {local} has {len(truth)} results"
    if truth and not gets:
        return "false_absence", f"no Observation query issued; local code {local} has {len(truth)} results"
    unread = [s for s in gets if s["next"] and s["q"].get("code", "").upper().split("|")[-1] == local]
    if unread:
        followed = any("_getpages" in s["url"] or "_offset" in s["url"] or "page" in s["url"].lower() for s in gets)
        seen = {p[2] for s in gets for p in obs_points(s["entries"])}
        latest = max(truth, key=lambda p: p[0])
        if not followed and latest[2] not in seen:
            return "incomplete_retrieval", (f"`next` link not followed; {len(seen)} of {len(truth)} results read; "
                                            f"true latest {latest[0].isoformat()} ({latest[1]}) on an unread page")
    return None, None


def trace_attempt(row, task, ref):
    cat = row["category"]
    cls = row["failure_type_refined"]
    if cls == "pass":
        return "", "", ""
    if cls in ("format_only", "pass_without_acting"):
        return cls, LOCUS[cls], ""
    hist = json.loads((ROOT / row["answer_file"]).read_text(encoding="utf-8"))["history"]
    steps = parse_steps(hist)
    if not any(s["kind"] == "FINISH" for s in steps):
        return "protocol_failure", "other", f"status {row['status']}"
    patient = mrn_of(task)
    ans = next(s["answer"] for s in steps if s["kind"] == "FINISH")
    posts = [s for s in steps if s["kind"] == "POST"]
    ref_posts = ref["posts"]

    mech, ev = evidence_gathering(cat, patient, steps)
    if mech:
        return mech, LOCUS[mech], ev + ("" if cls == "substantive_answer_error" else f"; upstream of {cls}")

    nums = numbers(ans)
    gets = [s for s in steps if s["kind"] == "GET"]
    retrieved = [p for s in gets for p in obs_points(s["entries"])]

    if cat == "task1":
        if "not found" in str(ans).lower():
            return "false_absence", LOCUS["false_absence"], f"answered 'Patient not found'; search params {[s['q'] for s in gets]}"
        return "answer_error_other", LOCUS["answer_error_other"], f"answer {ans} vs reference {ref['answer']}"

    if cat == "task2":
        pats = [r for s in gets for r in s["entries"] if r.get("resourceType") == "Patient"]
        bd = _dt((pats[0].get("birthDate") + "T00:00:00+00:00")) if pats and pats[0].get("birthDate") else None
        if bd:
            true_age = NOW.year - bd.year - ((NOW.month, NOW.day) < (bd.month, bd.day))
            if nums and int(nums[0]) != true_age:
                return "computation_error", LOCUS["computation_error"], f"birthDate {bd.date()} retrieved; true age {true_age}; answered {nums[0]:g}"
        return "answer_error_other", LOCUS["answer_error_other"], f"answer {ans} vs reference {ref['answer']}"

    if cat in ("task3", "task8"):
        return "order_content_error", LOCUS["order_content_error"], f"{len(posts)} POST(s) vs {len(ref_posts)} reference"

    if cat in ("task4", "task5", "task6"):
        truth = server_obs(patient, LOCAL[cat])
        inwin = [p for p in truth if NOW - timedelta(hours=24) <= p[0] <= NOW]
        rin = [p for p in retrieved if NOW - timedelta(hours=24) <= p[0] <= NOW]
        rout = [p for p in retrieved if p not in rin]
        if cat == "task6":
            if nums and nums[0] == -1 and rin:
                return "time_window_error", LOCUS["time_window_error"], f"{len(rin)} in-window value(s) retrieved but -1 (none in window) answered"
            if inwin and {p[2] for p in inwin} <= {p[2] for p in retrieved} and nums:
                true_mean = sum(p[1] for p in inwin) / len(inwin)
                all_mean = sum(p[1] for p in retrieved) / len(retrieved) if retrieved else None
                if rout and close(nums[0], all_mean, 0.6):
                    return "time_window_error", LOCUS["time_window_error"], f"mean of all {len(retrieved)} retrieved values incl. {len(rout)} outside window; true mean {true_mean:.2f}"
                if not close(nums[0], true_mean, 0.6):
                    return "computation_error", LOCUS["computation_error"], f"all {len(inwin)} in-window values retrieved; true mean {true_mean:.2f}; answered {nums[0]:g}"
        else:
            latest_in = max(inwin, key=lambda p: p[0]) if inwin else None
            if cls == "substantive_answer_error" or (cat == "task4"):
                if nums and not latest_in and nums[0] != -1:
                    hit = sorted([p for p in retrieved if close(p[1], nums[0])], key=lambda p: p[0], reverse=True)
                    return "time_window_error", LOCUS["time_window_error"], (f"no value within 24 h; reported {nums[0]:g}"
                                                                          + (f" measured {hit[0][0].isoformat()}" if hit else ""))
                if nums and latest_in and nums[0] == -1 and latest_in in retrieved:
                    return "time_window_error", LOCUS["time_window_error"], f"in-window value {latest_in[1]} at {latest_in[0].isoformat()} retrieved but -1 answered"
            if cat == "task5":
                v = latest_in[1] if latest_in else None
                need = v is not None and v < 1.9 + 1e-9
                doses = med_doses(posts)
                if need and not doses:
                    return "order_rule_omission", LOCUS["order_rule_omission"], f"latest in-window Mg {v} requires replacement; no order"
                if not need and doses:
                    return ("unnecessary_order", LOCUS["unnecessary_order"],
                            f"Mg {'not available within 24 h' if v is None else v}; ordered dose {doses}")
                if need and doses:
                    return "order_content_error", LOCUS["order_content_error"], f"Mg {v}; ordered {doses} vs reference {med_doses(ref_posts)}"

    if cat == "task7":
        return "answer_error_other", LOCUS["answer_error_other"], f"answer {ans} vs reference {ref['answer']}"

    if cat == "task9":
        truth = server_obs(patient, "K")
        latest = max(truth, key=lambda p: p[0]) if truth else None
        doses, srs, rdoses = med_doses(posts), service_reqs(posts), med_doses(ref_posts)
        if latest and latest[1] < 3.5:
            if not doses and not srs:
                return "order_rule_omission", LOCUS["order_rule_omission"], f"latest K {latest[1]} < 3.5 retrieved; no orders"
            if doses and rdoses and not all(d is not None and close(d, rdoses[0], 0.6) for d in doses):
                return "computation_error", LOCUS["computation_error"], f"K {latest[1]}: dose {doses} vs correct {rdoses}"
            return "order_content_error", LOCUS["order_content_error"], f"K {latest[1]}: {len(doses)} med + {len(srs)} lab orders vs reference {len(ref_posts)}"
        if latest and (doses or srs):
            return "unnecessary_order", LOCUS["unnecessary_order"], f"latest K {latest[1]} >= 3.5; orders placed"

    if cat == "task10":
        truth = server_obs(patient, "A1C")
        latest = max(truth, key=lambda p: p[0]) if truth else None
        old = latest is None or (NOW - latest[0]) > timedelta(days=365)
        srs = service_reqs(posts)
        if old and not srs:
            if latest is None:
                return "no_action_on_detected_absence", LOCUS["no_action_on_detected_absence"], "no HbA1c on file (correctly found); required order not placed"
            return "order_rule_omission", LOCUS["order_rule_omission"], f"latest HbA1c {latest[0].date()} older than 1 year; no order"
        if not old and srs:
            return "unnecessary_order", LOCUS["unnecessary_order"], f"latest HbA1c {latest[0].date()} ({(NOW - latest[0]).days} days old); order placed"
        if old and srs and cls in ("wrong_order", "commission"):
            return "order_content_error", LOCUS["order_content_error"], f"{len(srs)} order(s) vs reference {len(ref_posts)}"

    return "answer_error_other" if cls == "substantive_answer_error" else "unmapped", \
        LOCUS["answer_error_other" if cls == "substantive_answer_error" else "unmapped"], f"class {cls}; answer {str(ans)[:80]}"


# ----------------------------------------------------------------------------- runs
def reference(replay_run="full_control_replay"):
    ref = {}
    for l in (RUNS / replay_run / "results.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            h = json.loads((ROOT / r["answer_file"]).read_text(encoding="utf-8"))["history"]
            ref[r["task_id"]] = {"answer": r["result"], "posts": [s for s in parse_steps(h) if s["kind"] == "POST"]}
    return ref


def trace_run(run, tasks, ref):
    ap = runpy.run_path(str(HERE / "analyse_pilot.py"), run_name="ap")
    with contextlib.redirect_stdout(io.StringIO()):
        _, _, rows = ap["analyse"](run, regrade=True)
    tk = {t["id"]: t for t in tasks}
    out = []
    for r in rows:
        mech, locus, ev = trace_attempt(r, tk[r["task_id"]], ref[r["task_id"]])
        out.append({"run": run, "served_model": r.get("served_model"), "task_id": r["task_id"], "category": r["category"],
                    "attempt": r["attempt"], "status": r["status"], "official_pass": r["passed"],
                    "refined_class": r["failure_type_refined"], "mechanism": mech, "locus": locus, "evidence": ev})
    return out
