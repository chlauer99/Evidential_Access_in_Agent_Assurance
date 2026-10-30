"""Run judge_report.py with outcome classes taken from a previous, server-graded judge_attempts.csv.

Why: judge_report.py derives the truth classes through analyse_pilot.classify_failures, which calls the official
refsol grader, and the grader queries the FHIR server. When the server is unreachable, this wrapper substitutes the
classes that the same code computed earlier against the same (static) server, read from a saved judge_attempts.csv.
Everything else (judge verdicts, bootstrap, AUROC, reason-validity regexes) runs unchanged from judge_report.py.
Re-run plain judge_report.py once the server is back to confirm identical classes.

Usage: python judge_report_cached.py <cached_judge_attempts.csv>
"""
from __future__ import annotations

import runpy, sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RUNS = HERE.parent / "mab_runs"


def main(cache_csv: str):
    cache = pd.read_csv(cache_csv)
    cache = cache[cache.agent_run.str.startswith("pilot_")]
    # one class per (run, task, attempt); assert the cache is internally consistent across judges
    per = cache.groupby(["agent_run", "task_id", "attempt"]).cls.agg(lambda s: sorted(set(s)))
    bad = per[per.map(len) != 1]
    assert bad.empty, f"inconsistent cached classes: {bad.head()}"
    # Order keys exactly as analyse_pilot.load_valid does (first occurrence in results.jsonl), so the
    # task-clustered bootstrap draws the same resamples as judge_report.py run against the server.
    import json
    codes = {}
    for run in sorted({r for r, _, _ in per.index}):
        order = {}
        for l in (RUNS / run / "results.jsonl").read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                if r["status"] != "API_ERROR":
                    order[(r["task_id"], r["attempt"])] = True
        codes[run] = {(t, a): {"failure_type_refined": per[(run, t, a)][0]} for (t, a) in order}

    jr = runpy.run_path(str(HERE / "judge_report.py"), run_name="jr")
    jr["aj"]["codes_for"] = lambda run: codes[run]           # the only substitution
    A = jr["attempts"](); A.to_csv(RUNS / "judge_attempts.csv", index=False)
    S = jr["summary"](A); S.to_csv(RUNS / "judge_summary.csv", index=False)
    D = jr["discrimination"](A); D.to_csv(RUNS / "judge_discrimination.csv", index=False)
    Rv = jr["reason_validity"](A); Rv.to_csv(RUNS / "judge_reason_validity.csv", index=False)
    print(A.groupby(["agent_run", "judge"]).size().to_string())
    print(D.to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1])
