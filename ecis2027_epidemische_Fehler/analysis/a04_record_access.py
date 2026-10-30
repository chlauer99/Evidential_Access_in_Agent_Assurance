"""a04 - Record-access judge (Section 5.6): DeepSeek V3.2 judge with read-only EHR access on a stratified
sample of 418 attempts versus the same judge on trajectories only.

Inputs : data/raw/record_access/agentic_judge_sample.json (the stratified sample, seed 2027),
         data/raw/<run>/judge_deepseek-v3.2_access.jsonl, neutral DeepSeek verdicts, tracer mechanisms
Outputs: outputs/agentic_judge_verdicts.csv, agentic_judge_discrimination.csv, agentic_judge_readonly.csv
Note   : rebuilding the sample itself needs the neutral verdict table, which is available here, so the sample is
         re-drawn and checked against the archived sample (outputs/agentic_judge_sample_check.csv).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import json
import numpy as np
import pandas as pd
from common import access_table, attempts, full_mechanisms, make_boot_J, record_access_rng, write
from config import RAW, SEED_BOOT_J, SEED_SAMPLE

A = attempts(judges=["deepseek-v3.2"], controls=False)
X = access_table(A)
write(X.drop(columns=["queries"]), "agentic_judge_verdicts.csv")

# discrimination per agent run (generator state as in the original session; see common.record_access_rng)
boot_J = make_boot_J(record_access_rng())
rows = []
for run in ["pilot_gpt41", "pilot_gpt41mini", "full_deepseekv32"]:
    d = X[X.run == run]
    for col in ["neutral_pass", "access_pass"]:
        c = d[d.cls == "correct"][col].mean(); e = d[d.cls == "grounded"][col].mean(); lo, hi = boot_J(d, col)
        rows.append(dict(run=run, judge=col.replace("_pass", ""), n_correct=(d.cls == "correct").sum(),
                         n_grounded=(d.cls == "grounded").sum(), pass_correct=c, pass_grounded=e, J=c - e, J_lo=lo, J_hi=hi))
write(pd.DataFrame(rows), "agentic_judge_discrimination.csv")

# task categories answerable by read-only access alone (1, 2, 4, 6, 7); condition-major order as published.
# The same generator continues (as in the original session).
ro = X[X.cat.isin(["task1", "task2", "task4", "task6", "task7"])]
rows = []
for col in ["neutral_pass", "access_pass"]:
    for run in ["pilots (GPT agents)", "full_deepseekv32"]:
        d = ro[ro.run.str.startswith("pilot")] if run.startswith("pilots") else ro[ro.run == run]
        c, e = d[d.cls == "correct"][col].mean(), d[d.cls == "grounded"][col].mean(); lo, hi = boot_J(d, col)
        rows.append(dict(pool=run, judge=col.replace("_pass", ""), n_correct=(d.cls == "correct").sum(),
                         n_grounded=(d.cls == "grounded").sum(), pass_correct=c, pass_grounded=e, J=c - e, J_lo=lo, J_hi=hi))
write(pd.DataFrame(rows), "agentic_judge_readonly.csv")

# re-draw the stratified sample (seed 2027) and compare with the archived sample
M = full_mechanisms()
base = A.copy(); base["attempt"] = base.attempt.astype(int); base["subst_correct"] = base.truth.isin(["correct", "format_only"])
rng2 = np.random.default_rng(SEED_SAMPLE); samp = []
for run in ["pilot_gpt41", "pilot_gpt41mini"]:
    b = base[base.agent_run == run]
    samp += [dict(run=run, task_id=t, attempt=int(a_), stratum="grounded_error") for t, a_ in
             zip(b[b.truth == "grounded_error"].task_id, b[b.truth == "grounded_error"].attempt)]
    c = b[b.subst_correct]; idx = rng2.choice(len(c), size=min(70, len(c)), replace=False)
    samp += [dict(run=run, task_id=t, attempt=int(a_), stratum="subst_correct") for t, a_ in zip(c.iloc[idx].task_id, c.iloc[idx].attempt)]
d = base[base.agent_run == "full_deepseekv32"].merge(M[["task_id", "attempt", "mechanism"]].rename(columns={"mechanism": "tmech"}),
                                                     on=["task_id", "attempt"], how="left")
d["cat"] = d.task_id.str.split("_").str[0]
quota = [("false_absence", "task1", 30), ("false_absence", "task9", 20), ("incomplete_retrieval", "task7", 20),
         ("incomplete_retrieval", None, 10), ("computation_error", None, 10), ("time_window_error", None, 5)]
for mech, cat, n in quota:
    pool = d[(d.truth == "grounded_error") & (d.tmech == mech) & ((d.cat == cat) if cat else (d.cat != "task7"))]
    idx = rng2.choice(len(pool), size=min(n, len(pool)), replace=False)
    samp += [dict(run="full_deepseekv32", task_id=t, attempt=int(a_), stratum=f"grounded_error:{mech}")
             for t, a_ in zip(pool.iloc[idx].task_id, pool.iloc[idx].attempt)]
c = d[d.subst_correct]
for cat_, g_ in c.groupby("cat"):
    n = max(3, round(60 * len(g_) / len(c))); idx = rng2.choice(len(g_), size=min(n, len(g_)), replace=False)
    samp += [dict(run="full_deepseekv32", task_id=t, attempt=int(a_), stratum="subst_correct") for t, a_ in zip(g_.iloc[idx].task_id, g_.iloc[idx].attempt)]
S2 = pd.DataFrame(samp).drop_duplicates(["run", "task_id", "attempt"])
S = pd.DataFrame(json.load(open(RAW / "record_access" / "agentic_judge_sample.json", encoding="utf-8")))
same = S2.reset_index(drop=True).equals(S.reset_index(drop=True)[S2.columns])
write(pd.DataFrame([dict(n_redrawn=len(S2), n_archived=len(S), identical=bool(same))]), "agentic_judge_sample_check.csv")
