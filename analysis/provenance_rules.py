"""Provenance coding rules (grounded / fabricated / unclassified) for substantive errors, P1.

Verbatim reconstruction of the coding script that produced data/derived/provenance_coding.csv (lineage of that
artifact): every patient value stated in the answer is looked up in the numbers of the retrieved EHR responses;
computation errors are grounded by construction (tracer-verified derivation from retrieved values); order-content
errors are unclassified (no patient fact at issue); task-6 means are grounded if they equal the mean of a subset of
retrieved values, else unclassified; any other unsupported stated value is fabricated, unless it is a task threshold
(from the task text) or a deficit derived from a retrieved value (three DeepSeek attempts, hand-checked).
"""
import json
import re as _re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import read_jsonl  # noqa: E402
from config import RAW  # noqa: E402

DT = _re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ][0-9:.]+(?:[+-]\d{2}:\d{2}|Z)?)?")
NUM = _re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w])")
LAB = _re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(mmol/l|meq/l|mg/dl|g/dl|mmhg|%|years?\b|bpm)", _re.I)
DEFICIT = _re.compile(r"(deficit|below|under)", _re.I)


def answer_path(run, rec, raw=None):
    return Path(raw or RAW) / run / "answers" / _re.split(r"[\\/]", rec["answer_file"])[-1]


def get_responses(hist):
    return [x["content"] for x in hist if x.get("role") == "user" and str(x.get("content", "")).startswith("Here is the response from the GET request")]


def retrieved_set(resps):
    s = set()
    for r in resps:
        for m in NUM.finditer(r):
            try:
                s.add(round(float(m.group(0)), 2))
            except ValueError:
                pass
    return s


def patient_values(text):
    return [(float(m.group(1)), bool(DEFICIT.search(text[m.end():m.end() + 20]) or DEFICIT.search(text[max(0, m.start() - 20):m.start()])))
            for m in LAB.finditer(text)]


def task_thresholds(hist):
    first = next((str(x.get("content")) for x in hist if x.get("role") == "user"), "")
    return {round(float(m.group(0)), 2) for m in NUM.finditer(first)}


def mean_candidates(resps):
    vals = []
    for r in resps:
        try:
            b = json.loads(r[r.find("{"):])
        except Exception:
            continue
        for e in b.get("entry", []) or []:
            res_ = e.get("resource", {})
            v = res_.get("valueQuantity", {}).get("value", res_.get("valueString"))
            try:
                vals.append((res_.get("effectiveDateTime", ""), float(v)))
            except Exception:
                pass
    return vals


def prov2(hist, rec, task_id, mechanism):
    resps = get_responses(hist); rs = retrieved_set(resps); th = task_thresholds(hist)
    ans = str(rec["result"])
    try:
        payload = json.loads(ans)
    except Exception:
        payload = ans
    text = " ".join(str(x) for x in payload) if isinstance(payload, list) else str(payload)
    pv = patient_values(text)
    if isinstance(payload, list) and payload and all(isinstance(x, (int, float)) for x in payload):
        pv += [(float(x), False) for x in payload if x != -1]
    unsupported = []
    for v, is_def in pv:
        if round(v, 2) in rs:
            continue
        if is_def and any(abs(round(t - r, 2) - v) < 0.011 for t in th for r in rs):
            continue
        unsupported.append(v)
    if mechanism in ("computation error", "computation_error"):
        return "grounded", "derived value from retrieved evidence (tracer-verified)", unsupported
    if mechanism == "order_content_error":
        return "unclassified", "order specification; no patient fact at issue", unsupported
    if not unsupported:
        if not pv and not resps:
            return "unclassified", "no retrieval and no stated value", []
        return "grounded", ("stated values retrieved" if pv else "no stated patient value; basis is an authentic retrieval result"), []
    if task_id.startswith("task6"):
        allv = [v for _, v in mean_candidates(resps)]
        cands = {round(sum(allv) / len(allv), 3)} if allv else set()
        for k in range(1, len(allv) + 1):
            cands.add(round(sum(allv[:k]) / k, 3)); cands.add(round(sum(allv[-k:]) / k, 3))
        if all(any(abs(u - c) < 0.01 for c in cands) for u in unsupported):
            return "grounded", "mean of a subset of retrieved values", []
        return "unclassified", "derived value not reproducible from retrieved values", unsupported
    return "fabricated", "stated patient value absent from retrieved evidence", unsupported


def recode(run, agent, errs, raw=None):
    res = {}
    raw = Path(raw) if raw else RAW
    for r in read_jsonl(raw / run / "results.jsonl"):
        if r.get("status") != "API_ERROR":
            res[(r["task_id"], int(r["attempt"]))] = r
    out = []
    for t, a, cls, mech in errs:
        rec = res[(t, a)]
        hist = json.load(open(answer_path(run, rec, raw), encoding="utf-8")).get("history", [])
        p, basis, miss = prov2(hist, rec, t, mech)
        if p == "fabricated":
            th = task_thresholds(hist); left = [v for v in miss if round(v, 2) not in th]
            if not left:
                p, basis, miss = "grounded", "stated values retrieved; other numbers are task thresholds", []
            else:
                miss = left
        if agent == "DeepSeek V3.2" and (t, a) in {("task9_13", 0), ("task9_13", 3), ("task9_22", 3)}:
            p, basis, miss = "grounded", "deficit derived from a retrieved value", []
        out.append(dict(agent=agent, task_id=t, attempt=a, outcome_class=cls, mechanism=mech, provenance=p, basis=basis,
                        unsupported_values=";".join(str(x) for x in miss)))
    return out


