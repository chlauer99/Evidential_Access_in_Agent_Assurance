"""a05 - Judge conditions summary: the data of Figure 1 (all 15 agent-judge-condition rows).

Inputs : attempt x judge table; record-access table
Outputs: outputs/judge_conditions_summary.csv (published)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from common import access_table, attempts, discrimination, make_boot_J, record_access_rng, write
from config import AGENT_NAME, JUDGE_NAME, SEED_BOOT_J

A = attempts(judges=["gpt-4.1", "gpt-4.1-mini", "gpt-4.1_spec", "gpt-4.1-mini_spec", "deepseek-v3.2", "deepseek-v3.2_verify"])
D = discrimination(A)
X = access_table(A)
boot_J = make_boot_J(record_access_rng())  # same draws as agentic_judge_discrimination.csv
AJ = []
for run in ["pilot_gpt41", "pilot_gpt41mini", "full_deepseekv32"]:
    d = X[X.run == run]
    for col in ["neutral_pass", "access_pass"]:
        c, e = d[d.cls == "correct"][col].mean(), d[d.cls == "grounded"][col].mean(); lo, hi = boot_J(d, col)
        AJ.append(dict(run=run, judge=col.replace("_pass", ""), n_correct=(d.cls == "correct").sum(), n_grounded=(d.cls == "grounded").sum(),
                       pass_correct=c, pass_grounded=e, J=c - e, J_lo=lo, J_hi=hi))
AJ = pd.DataFrame(AJ)
cond_of = lambda j: "+ API specification" if j.endswith("_spec") else "+ verification checklist" if j.endswith("_verify") else "Trajectory only"
R = []
for r in D.itertuples():
    R.append(dict(cond=cond_of(r.judge), judge=JUDGE_NAME[r.judge.split("_")[0]], agent=AGENT_NAME[r.agent_run], pairing=r.pairing,
                  n_c=r.n_correct, n_g=r.n_grounded_error, pc=r.pass_if_correct, pg=r.pass_if_grounded_error, J=r.youden_J,
                  lo=r.J_lo, hi=r.J_hi, J_paired=np.nan))
for r in AJ[AJ.judge == "access"].itertuples():
    nr = AJ[(AJ.run == r.run) & (AJ.judge == "neutral")].iloc[0]
    R.append(dict(cond="+ read-only EHR access", judge="DeepSeek V3.2", agent=AGENT_NAME[r.run],
                  pairing="self" if r.run == "full_deepseekv32" else "cross-developer",
                  n_c=r.n_correct, n_g=r.n_grounded, pc=r.pass_correct, pg=r.pass_grounded, J=r.J, lo=r.J_lo, hi=r.J_hi, J_paired=nr.J))
write(pd.DataFrame(R), "judge_conditions_summary.csv")
