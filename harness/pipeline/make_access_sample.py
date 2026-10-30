"""Step 6 (record-access condition) - stratified sample of attempts for the record-access judge (seed 2027).

Rule used in the paper (418 attempts): for each pilot agent, all substantive errors plus 70 randomly drawn
substantively correct attempts; for the full-run agent, substantive errors by tracer mechanism and task category
(false absence: 30 from task 1 and 20 from task 9; incomplete retrieval: 20 from task 7 and 10 from other categories;
computation errors 10; time-window errors 5) plus substantively correct attempts allocated to categories in proportion
(60 in total, at least 3 per category). Classes come from the trajectory-only verdict table of the full-run judge.
Output: <runs-dir>/record_access/agentic_judge_sample.json (list of {run, task_id, attempt, stratum})
"""
from __future__ import annotations

import argparse, json, os, sys
from pathlib import Path


H = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True); ap.add_argument("--derived", required=True)
    ap.add_argument("--seed", type=int, default=2027)
    ap.add_argument("--judge", default="deepseek-v3.2", help="judge role whose trajectory-only verdicts define the frame")
    ap.add_argument("--all-run", default=None, help="Assess every completed attempt in this run; no pilot-dependent sampling")
    a = ap.parse_args()
    if a.all_run:
        results = Path(a.runs_dir) / a.all_run / "results.jsonl"
        latest = {}
        for line in results.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("status") != "API_ERROR":
                    latest[(r["task_id"], int(r["attempt"]))] = r
        sample = [dict(run=a.all_run, task_id=t, attempt=x, stratum="all_completed")
                  for (t, x), r in sorted(latest.items()) if r.get("status") == "COMPLETED"]
        out = Path(a.runs_dir) / "record_access"
        out.mkdir(parents=True, exist_ok=True)
        (out / "agentic_judge_sample.json").write_text(json.dumps(sample, indent=1), encoding="utf-8")
        print(f"{len(sample)} completed attempts; no sampling by mechanism or judge verdict")
        return
    import numpy as np
    import pandas as pd
    os.environ["REPRO_RAW"] = str(Path(a.runs_dir).resolve()); os.environ["REPRO_DERIVED"] = str(Path(a.derived).resolve())
    sys.path.insert(0, str(H.parent / "analysis"))
    from common import attempts, full_mechanisms
    A = attempts(judges=[a.judge], controls=False)
    M = full_mechanisms()
    base = A.copy(); base["attempt"] = base.attempt.astype(int); base["subst_correct"] = base.truth.isin(["correct", "format_only"])
    rng2 = np.random.default_rng(a.seed); samp = []
    for run in ["pilot_gpt41", "pilot_gpt41mini"]:
        b = base[base.agent_run == run]
        samp += [dict(run=run, task_id=t, attempt=int(x), stratum="grounded_error") for t, x in
                 zip(b[b.truth == "grounded_error"].task_id, b[b.truth == "grounded_error"].attempt)]
        c = b[b.subst_correct]; idx = rng2.choice(len(c), size=min(70, len(c)), replace=False)
        samp += [dict(run=run, task_id=t, attempt=int(x), stratum="subst_correct") for t, x in zip(c.iloc[idx].task_id, c.iloc[idx].attempt)]
    d = base[base.agent_run == "full_deepseekv32"].merge(M[["task_id", "attempt", "mechanism"]].rename(columns={"mechanism": "tmech"}),
                                                         on=["task_id", "attempt"], how="left")
    d["cat"] = d.task_id.str.split("_").str[0]
    quota = [("false_absence", "task1", 30), ("false_absence", "task9", 20), ("incomplete_retrieval", "task7", 20),
             ("incomplete_retrieval", None, 10), ("computation_error", None, 10), ("time_window_error", None, 5)]
    for mech, cat, n in quota:
        pool = d[(d.truth == "grounded_error") & (d.tmech == mech) & ((d.cat == cat) if cat else (d.cat != "task7"))]
        idx = rng2.choice(len(pool), size=min(n, len(pool)), replace=False)
        samp += [dict(run="full_deepseekv32", task_id=t, attempt=int(x), stratum=f"grounded_error:{mech}")
                 for t, x in zip(pool.iloc[idx].task_id, pool.iloc[idx].attempt)]
    c = d[d.subst_correct]
    for cat_, g_ in c.groupby("cat"):
        n = max(3, round(60 * len(g_) / len(c))); idx = rng2.choice(len(g_), size=min(n, len(g_)), replace=False)
        samp += [dict(run="full_deepseekv32", task_id=t, attempt=int(x), stratum="subst_correct") for t, x in zip(g_.iloc[idx].task_id, g_.iloc[idx].attempt)]
    S = pd.DataFrame(samp).drop_duplicates(["run", "task_id", "attempt"])
    out = Path(a.runs_dir) / "record_access"; out.mkdir(parents=True, exist_ok=True)
    json.dump(S.to_dict("records"), open(out / "agentic_judge_sample.json", "w"), indent=0)
    print(len(S), S.groupby("run").stratum.value_counts().to_dict())


if __name__ == "__main__":
    main()
