"""Analyse a MedAgentBench pilot run against the pre-registered agent-selection rule (protocol §4b).

Outputs, per run: pilot_<run>_per_task.csv, pilot_<run>_summary.json
  * pass@1 and pass@8 per task (unbiased estimator), mean over tasks, by category
  * selection headroom = pass@8 - pass@1 (room for best-of-n to choose wrongly)
  * failure types, with 'format_only' split out: attempts the official grader rejected that pass after
    normalising the answer format (flattening a nested list, numeric strings -> numbers); re-graded with the
    official grader against the live FHIR server
  * grader leniency floor: per-task boolean column 'do_nothing_passes' (the do-nothing control passes the task) and
    the summary statistic 'share_passes_on_do_nothing_tasks' (share of the agent's passes that fall on such tasks)
Selection rule (pre-registered): pass@1 in [0.3, 0.8] and the largest pass@8 - pass@1 gap.
"""
from __future__ import annotations

import csv, json, math, os, sys, tempfile
from pathlib import Path

for _k in ("NO_PROXY", "no_proxy"):
    os.environ[_k] = ",".join(x for x in (os.environ.get(_k, ""), "localhost", "127.0.0.1") if x)

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "mab_runs"


def pass_at_k(n, c, k):
    if n < k:
        return None
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def load_valid(run):
    latest = {}
    for l in (RUNS / run / "results.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            if r["status"] != "API_ERROR":
                latest[(r["task_id"], r["attempt"])] = r
    return list(latest.values())


def _normalise(result: str):
    try:
        v = json.loads(result)
    except Exception:
        return None
    changed = False
    if isinstance(v, list) and len(v) == 1 and isinstance(v[0], list):
        v, changed = v[0], True
    out = []
    for x in v if isinstance(v, list) else []:
        if isinstance(x, str):
            try:
                x, changed = float(x) if "." in x else int(x), True
            except ValueError:
                pass
        out.append(x)
    return json.dumps(out) if changed else None


def regrade_format(rows, tasks_meta):
    """Return set of (task, attempt) whose failure disappears after answer-format normalisation."""
    sys.path.insert(0, str(ROOT / "mab_tasks" / "task10_1" / "tests"))
    import medagentbench_logic as logic
    fixed = set()
    with tempfile.TemporaryDirectory() as td:
        for r in rows:
            if r["passed"] or r["status"] != "COMPLETED" or r["result"] is None:
                continue
            norm = _normalise(r["result"])
            if norm is None:
                continue
            ans = json.loads((ROOT / r["answer_file"]).read_text(encoding="utf-8"))
            ans["result"] = norm
            p = Path(td) / f"{r['task_id']}_{r['attempt']}.json"
            p.write_text(json.dumps(ans), encoding="utf-8")
            ok, _ = logic.evaluate_submission(metadata=tasks_meta[r["task_id"]], answer_path=p)
            if ok:
                fixed.add((r["task_id"], r["attempt"]))
    return fixed


import re
_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _content_matches(agent_result, ref_result) -> bool:
    """True if every value in the reference answer appears in the agent's stated answer (any format)."""
    try:
        ref = json.loads(ref_result) if isinstance(ref_result, str) else ref_result
    except Exception:
        return False
    text = agent_result or ""
    # dates/timestamps are removed before extracting numbers, so "2023-11-01" is not read as -11 or -1
    no_dates = re.sub(r"\d{4}-\d{2}-\d{2}(?:[T ][\d:.]+(?:Z|[+-]\d{2}:?\d{2})?)?", " ", text)
    nums = [float(x) for x in _NUM.findall(no_dates)]
    for v in ref if isinstance(ref, list) else [ref]:
        if isinstance(v, (int, float)):
            if not any(abs(n - float(v)) < 1e-6 for n in nums):
                return False
        elif str(v) not in text:
            # a timestamp counts as stated if its calendar date is given (e.g. "2023-11-02" for 2023-11-02T06:53:00+00:00)
            m = re.match(r"(\d{4}-\d{2}-\d{2})T", str(v))
            if not (m and m.group(1) in text):
                return False
    return True


def classify_failures(rows, tasks_meta, run):
    """Refine failure types for COMPLETED, failed attempts using the official grader.

    orders_ok: re-grade the attempt with its answer replaced by the reference answer. If it now passes,
               the actions (orders / no orders) were correct and only the stated answer failed.
    Then:  orders_ok & answer contains the reference values -> 'format_only' (right content, rejected form)
           orders_ok & values absent                         -> 'substantive_answer_error'
           not orders_ok -> 'omission' / 'commission' / 'wrong_order' (from reference vs agent order counts)
    """
    sys.path.insert(0, str(ROOT / "mab_tasks" / "task10_1" / "tests"))
    import medagentbench_logic as logic
    out = {}
    with tempfile.TemporaryDirectory() as td:
        for r in rows:
            key = (r["task_id"], r["attempt"])
            if r["passed"]:
                out[key] = "pass_without_acting" if (r["result"] or "").replace(" ", "") == "[]" and r["agent_posts"] == 0 else "pass"
                continue
            if r["status"] != "COMPLETED":
                out[key] = "no_finish"
                continue
            ref = json.loads((RUNS / run / "_reference" / f"{r['task_id']}.json").read_text(encoding="utf-8"))
            ref_res = ref["result"] if isinstance(ref["result"], str) else json.dumps(ref["result"])
            ans = json.loads((ROOT / r["answer_file"]).read_text(encoding="utf-8"))
            ans["result"] = ref_res
            p = Path(td) / f"{r['task_id']}_{r['attempt']}.json"
            p.write_text(json.dumps(ans), encoding="utf-8")
            orders_ok, _ = logic.evaluate_submission(metadata=tasks_meta[r["task_id"]], answer_path=p)
            if orders_ok:
                out[key] = "format_only" if _content_matches(r["result"], ref_res) else "substantive_answer_error"
            elif r["ref_posts"] > 0 and r["agent_posts"] == 0:
                out[key] = "omission"
            elif r["ref_posts"] == 0 and r["agent_posts"] > 0:
                out[key] = "commission"
            else:
                out[key] = "wrong_order"
    return out


def analyse(run, null_run="control_null", regrade=True):
    rows = load_valid(run)
    null = {json.loads(l)["task_id"]: json.loads(l)["passed"]
            for l in (RUNS / null_run / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    meta = {}
    for r in rows:
        m = json.loads((ROOT / "mab_tasks" / r["task_id"] / "tests" / "task_metadata.json").read_text(encoding="utf-8"))
        m["fhir_api_base"] = "http://localhost:8080/fhir/"
        meta[r["task_id"]] = m
    refined = classify_failures(rows, meta, run) if regrade else {}
    fmt = {k for k, v in refined.items() if v == "format_only"}
    for r in rows:
        r["failure_type_refined"] = refined.get((r["task_id"], r["attempt"]), r["failure_type"])
    per = {}
    for r in rows:
        per.setdefault(r["task_id"], []).append(r)
    table = []
    for tid, rs in per.items():
        n, c = len(rs), sum(x["passed"] for x in rs)
        p1, p8 = c / n, pass_at_k(n, c, 8)
        table.append({"task_id": tid, "category": rs[0]["category"], "n": n, "correct": c,
                      "pass@1": round(p1, 3), "pass@8": None if p8 is None else round(p8, 3),
                      "headroom": None if p8 is None else round(p8 - p1, 3),
                      "requires_order": rs[0]["ref_posts"] > 0, "do_nothing_passes": bool(null.get(tid)),
                      "format_only_failures": sum((tid, x["attempt"]) in fmt for x in rs),
                      "mean_tokens": round(sum(x["usage"]["prompt_tokens"] + x["usage"]["completion_tokens"] for x in rs) / n)})
    table.sort(key=lambda t: (int(t["category"][4:]), int(t["task_id"].split("_")[1])))
    complete = [t for t in table if t["n"] >= 8]
    ftypes = {}
    for r in rows:
        ftypes[r["failure_type_refined"]] = ftypes.get(r["failure_type_refined"], 0) + 1
    tok_in = sum(r["usage"]["prompt_tokens"] for r in rows)
    tok_out = sum(r["usage"]["completion_tokens"] for r in rows)
    mean = lambda xs: round(sum(xs) / len(xs), 3) if xs else None
    passes = [r for r in rows if r["passed"]]
    summ = {
        "run": run, "valid_attempts": len(rows), "tasks": len(table), "tasks_with_8_attempts": len(complete),
        "served_models": sorted({r["served_model"] for r in rows if r.get("served_model")}),
        "mean_pass@1": mean([t["pass@1"] for t in table]),
        "mean_pass@8": mean([t["pass@8"] for t in complete]),
        "mean_headroom": mean([t["headroom"] for t in complete]),
        "mean_pass@1_excluding_do_nothing_tasks": mean([t["pass@1"] for t in table if not t["do_nothing_passes"]]),
        "mean_pass@1_order_tasks": mean([t["pass@1"] for t in table if t["requires_order"]]),
        "mean_pass@1_if_format_accepted": mean([(t["correct"] + t["format_only_failures"]) / t["n"] for t in table]),
        "share_passes_on_do_nothing_tasks": round(sum(null.get(r["task_id"], False) for r in passes) / max(1, len(passes)), 3),
        "tasks_in_selection_band_0.3_0.8": sum(0.3 <= t["pass@1"] <= 0.8 for t in table),
        "tasks_at_ceiling_pass@1_eq_1": sum(t["pass@1"] == 1.0 for t in table),
        "tasks_at_floor_pass@1_eq_0": sum(t["pass@1"] == 0.0 for t in table),
        "failure_types": dict(sorted(ftypes.items(), key=lambda kv: -kv[1])),
        "by_category_pass@1": {c: mean([t["pass@1"] for t in table if t["category"] == c])
                               for c in sorted({t["category"] for t in table}, key=lambda c: int(c[4:]))},
        "tokens_in": tok_in, "tokens_out": tok_out,
        "meets_selection_rule_pass@1_in_0.3_0.8": None,
    }
    p = summ["mean_pass@1"]
    summ["meets_selection_rule_pass@1_in_0.3_0.8"] = bool(p is not None and 0.3 <= p <= 0.8)
    with open(ROOT / f"pilot_{run}_per_task.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0]))
        w.writeheader(); w.writerows(table)
    (ROOT / f"pilot_{run}_summary.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    return summ, table, rows


if __name__ == "__main__":
    s, _, _ = analyse(sys.argv[1] if len(sys.argv) > 1 else "pilot_gpt41")
    print(json.dumps(s, indent=1))
