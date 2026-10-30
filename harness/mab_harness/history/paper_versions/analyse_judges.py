"""Compare model-judge verdicts with the official (rule-based) grader, by outcome class and error mechanism.

Truth classes (from analyse_pilot.classify_failures, validated against the server):
  substantively correct = official pass (non-empty answer) or 'format_only' (right values, rejected form)
  grounded error        = substantive answer error, omission of a required order, or unnecessary order
Key quantities per (agent, judge):
  false-pass rate on grounded errors     P(judge pass | grounded error)
  acceptance of format-only answers      P(judge pass | format_only)
  false-fail rate on correct passes      P(judge fail | official pass)
  controls: judge pass rate on reference replay (should be ~1) and on the do-nothing agent
"""
from __future__ import annotations

import contextlib, io, json, runpy
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "mab_runs"

MECH = {
    ("task4_29", "substantive_answer_error"): "time-window error",
    ("task6_27", "substantive_answer_error"): "computation error",
    ("task2_17", "substantive_answer_error"): "computation error",
    ("task7_16", "substantive_answer_error"): "incomplete retrieval",
    ("task7_19", "substantive_answer_error"): "incomplete retrieval",
    ("task9_4", "substantive_answer_error"): "false absence",
    ("task9_20", "substantive_answer_error"): "false absence",
    ("task9_3", "omission"): "false absence",
    ("task10_10", "omission"): "no action on detected absence",
    ("task10_4", "commission"): "unnecessary order",
}
GROUNDED = {"substantive_answer_error", "omission", "commission"}


def load_judge(run, judge):
    f = RUNS / run / f"judge_{judge}.jsonl"
    out = {}
    if f.exists():
        for l in f.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                if r.get("verdict") in ("pass", "fail"):
                    out[(r["task_id"], r["attempt"])] = r
    return out


def codes_for(run):
    ap = runpy.run_path(str(ROOT / "mab_harness" / "analyse_pilot.py"), run_name="ap")
    with contextlib.redirect_stdout(io.StringIO()):
        _, _, rows = ap["analyse"](run, regrade=True)
    return {(r["task_id"], r["attempt"]): r for r in rows}


def rate(xs):
    return (round(sum(xs) / len(xs), 3), len(xs)) if xs else (None, 0)


def compare(agent_run, judge):
    codes = codes_for(agent_run)
    j = load_judge(agent_run, judge)
    by_class, by_mech = defaultdict(list), defaultdict(list)
    for k, r in codes.items():
        if k not in j:
            continue
        jp = j[k]["verdict"] == "pass"
        c = r["failure_type_refined"]
        by_class[c].append(jp)
        if c in GROUNDED:
            by_class["ALL grounded errors"].append(jp)
            by_mech[MECH.get((r["task_id"], c), "unmapped")].append(jp)
        if c in ("pass", "format_only"):
            by_class["ALL substantively correct"].append(jp)
    return {"agent": agent_run, "judge": judge, "graded": len([k for k in codes if k in j]),
            "judge_pass_rate_by_class": {c: rate(v) for c, v in sorted(by_class.items())},
            "judge_pass_rate_by_mechanism": {m: rate(v) for m, v in sorted(by_mech.items())}}


def controls(judge):
    out = {}
    for run in ("control_replay", "control_null"):
        res = {json.loads(l)["task_id"]: json.loads(l)["passed"]
               for l in (RUNS / run / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
        j = load_judge(run, judge)
        grader_pass = [j[(t, 0)]["verdict"] == "pass" for t, p in res.items() if p and (t, 0) in j]
        grader_fail = [j[(t, 0)]["verdict"] == "pass" for t, p in res.items() if not p and (t, 0) in j]
        out[run] = {"judge_pass_where_grader_passes": rate(grader_pass),
                    "judge_pass_where_grader_fails": rate(grader_fail)}
    return out


if __name__ == "__main__":
    for agent in ("pilot_gpt41", "pilot_gpt41mini"):
        for judge in ("gpt-4.1", "gpt-4.1-mini"):
            print(json.dumps(compare(agent, judge)))
    for judge in ("gpt-4.1", "gpt-4.1-mini"):
        print(judge, json.dumps(controls(judge)))
