"""Step 3 - official grading plus the format-only regrade: outcome class of every attempt.

Classes (analyse_pilot.classify_failures, failure_type_refined): pass, pass_without_acting, format_only,
substantive_answer_error, omission, commission, wrong_order, no_finish. In the paper's terms: substantively correct =
pass + format_only; substantive error = substantive_answer_error + omission + commission; action errors with a wrong
order (wrong_order) and no_finish are unclassified; pass_without_acting = pass on a task where doing nothing passes.

  --mode online   needs the FHIR server: failed attempts are regraded with the official grader after replacing the
                  answer by the reference answer (orders_ok) and after answer-format normalisation.
  --mode offline  no server: every class that does not need the grader is recomputed from results.jsonl and the
                  stored reference answers (<run>/_reference/); for failed, completed attempts the grader's orders_ok
                  verdict is taken from a stored class table (--stored), and format_only vs substantive_answer_error
                  is then recomputed (content match against the reference answer). Agreement is reported.
Output: <derived>/outcome_classes_<run>.csv and, for pilot_* runs, <derived>/pilot_outcome_classes.csv
"""
from __future__ import annotations

import argparse, contextlib, io, json, os, runpy, sys
from pathlib import Path

import pandas as pd

HM = Path(__file__).resolve().parent.parent / "mab_harness"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True, help="comma-separated run names")
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--derived", required=True)
    ap.add_argument("--mode", choices=["online", "offline"], default="online")
    ap.add_argument("--stored", default=None, help="offline: CSV with agent_run, task_id, attempt, cls (grader-dependent part)")
    ap.add_argument("--null-run", default="control_null")
    a = ap.parse_args()
    os.environ["MAB_RUNS_DIR"] = str(Path(a.runs_dir).resolve())
    der = Path(a.derived); der.mkdir(parents=True, exist_ok=True)
    apy = runpy.run_path(str(HM / "analyse_pilot.py"), run_name="ap")
    stored = pd.read_csv(a.stored) if a.stored else None
    pilot_rows, checks = [], []
    for run in a.runs.split(","):
        if a.mode == "online":
            with contextlib.redirect_stdout(io.StringIO()):
                _, _, rows = apy["analyse"](run, null_run=a.null_run, regrade=True)
            out = [dict(agent_run=run, task_id=r["task_id"], attempt=int(r["attempt"]), cls=r["failure_type_refined"]) for r in rows]
        else:
            rows = apy["load_valid"](run)
            st = {} if stored is None else {(t, int(x)): c for r_, t, x, c in zip(stored.agent_run, stored.task_id, stored.attempt, stored.cls) if r_ == run}
            runs_dir = Path(a.runs_dir)
            out, n_grader, n_agree = [], 0, 0
            for r in rows:
                k = (r["task_id"], int(r["attempt"]))
                if r["passed"]:
                    c = "pass_without_acting" if (r["result"] or "").replace(" ", "") == "[]" and r["agent_posts"] == 0 else "pass"
                elif r["status"] != "COMPLETED":
                    c = "no_finish"
                else:
                    s_ = st.get(k)
                    if s_ is None:
                        raise SystemExit(f"offline mode: no stored grader verdict for {run} {k}; run --mode online")
                    n_grader += 1
                    ref = json.loads((runs_dir / run / "_reference" / f"{r['task_id']}.json").read_text(encoding="utf-8"))
                    ref_res = ref["result"] if isinstance(ref["result"], str) else json.dumps(ref["result"])
                    if s_ in ("format_only", "substantive_answer_error"):        # grader: orders_ok (stored)
                        c = "format_only" if apy["_content_matches"](r["result"], ref_res) else "substantive_answer_error"
                    elif r["ref_posts"] > 0 and r["agent_posts"] == 0:
                        c = "omission"
                    elif r["ref_posts"] == 0 and r["agent_posts"] > 0:
                        c = "commission"
                    else:
                        c = "wrong_order"
                if k in st:
                    n_agree += (st[k] == c)
                out.append(dict(agent_run=run, task_id=r["task_id"], attempt=int(r["attempt"]), cls=c))
            checks.append(dict(run=run, attempts=len(out), grader_dependent=n_grader, stored=len(st),
                               agree_with_stored=n_agree, mismatches=len([1 for o in out if (o["task_id"], o["attempt"]) in st
                                                                          and st[(o["task_id"], o["attempt"])] != o["cls"]])))
        pd.DataFrame(out).to_csv(der / f"outcome_classes_{run}.csv", index=False)
        print(run, pd.Series([o["cls"] for o in out]).value_counts().to_dict())
        if run.startswith("pilot"):
            pilot_rows += out
    if pilot_rows:
        pd.DataFrame(pilot_rows).to_csv(der / "pilot_outcome_classes.csv", index=False)
    if checks:
        pd.DataFrame(checks).to_csv(der / "outcome_classes_offline_check.csv", index=False)
        print(pd.DataFrame(checks).to_string(index=False))
        if any(c["mismatches"] for c in checks):
            sys.exit(1)


if __name__ == "__main__":
    main()
