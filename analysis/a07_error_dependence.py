"""a07 - Assurance error dependence (Section 5.7): shared judge errors, Cohen's kappa on error indicators
(task-clustered CI, seed 3) and joint acceptance of substantive errors.

Outputs: outputs/judge_error_sharing.csv, outputs/judge_error_kappa_ci.csv (published),
         outputs/joint_acceptance.csv (share of the 121 GPT-agent substantive errors accepted by both judges)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from common import attempts, kappa_err, write
from config import SEED_KAPPA, B_KAPPA

A = attempts(judges=["gpt-4.1", "gpt-4.1-mini", "deepseek-v3.2", "deepseek-v3.2_verify"], runs=("pilot_gpt41", "pilot_gpt41mini"),
             controls=False)
P_ = A[A.truth.isin(["correct", "format_only", "grounded_error"])].copy()
P_["subst_ok"] = P_.truth.isin(["correct", "format_only"])
P_["judge_err"] = P_.judge_pass.astype(bool) != P_.subst_ok
W = P_.pivot_table(index=["agent_run", "task_id", "attempt"], columns="judge", values="judge_err", aggfunc="first")
js = ["gpt-4.1", "gpt-4.1-mini", "deepseek-v3.2", "deepseek-v3.2_verify"]
lin = lambda j: "openai" if j.startswith("gpt") else "deepseek"
rows = []
for i, a_ in enumerate(js):
    for b_ in js[i + 1:]:
        d = W[[a_, b_]].dropna().astype(bool)
        pa, pb, both = d[a_].mean(), d[b_].mean(), (d[a_] & d[b_]).mean()
        po = (d[a_] == d[b_]).mean(); pe = pa * pb + (1 - pa) * (1 - pb); kap = (po - pe) / (1 - pe)
        rows.append(dict(judge_a=a_, judge_b=b_, relation="same lineage" if lin(a_) == lin(b_) else "cross-developer", n=len(d),
                         err_a=pa, err_b=pb, both_wrong=both, both_wrong_if_indep=pa * pb, lift=both / (pa * pb), kappa_errors=kap,
                         p_b_wrong_given_a_wrong=(d[b_] & d[a_]).sum() / d[a_].sum()))
write(pd.DataFrame(rows), "judge_error_sharing.csv")

Wk = W.reset_index()
kk = []
for a_, b_ in [("gpt-4.1", "gpt-4.1-mini"), ("gpt-4.1", "deepseek-v3.2"), ("gpt-4.1-mini", "deepseek-v3.2")]:
    d = Wk[["task_id", a_, b_]].dropna().copy(); d[[a_, b_]] = d[[a_, b_]].astype(bool)
    tasks = d.task_id.unique(); g = {t: d[d.task_id == t] for t in tasks}; rr = np.random.default_rng(SEED_KAPPA)
    bs = [kappa_err(pd.concat([g[t] for t in rr.choice(tasks, len(tasks))]), a_, b_) for _ in range(B_KAPPA)]
    kk.append(dict(judge_a=a_, judge_b=b_, n=len(d), kappa=round(kappa_err(d, a_, b_), 3),
                   lo=round(np.nanpercentile(bs, 2.5), 3), hi=round(np.nanpercentile(bs, 97.5), 3)))
write(pd.DataFrame(kk), "judge_error_kappa_ci.csv")

# joint acceptance of the same substantive error
E = A[A.truth == "grounded_error"].pivot_table(index=["agent_run", "task_id", "attempt"], columns="judge", values="judge_pass", aggfunc="first")
ja = []
for a_, b_ in [("gpt-4.1", "gpt-4.1-mini"), ("gpt-4.1", "deepseek-v3.2"), ("gpt-4.1-mini", "deepseek-v3.2")]:
    d = E[[a_, b_]].dropna().astype(bool)
    ja.append(dict(judge_a=a_, judge_b=b_, n_errors=len(d), both_accept=int((d[a_] & d[b_]).sum()), joint_acceptance=(d[a_] & d[b_]).mean()))
# self-preference: acceptance of substantive errors by agent x judge
sp = A[A.truth == "grounded_error"].groupby(["agent_run", "judge"]).judge_pass.mean().reset_index(name="accept_errors")
write(pd.DataFrame(ja), "joint_acceptance.csv")
write(sp, "error_acceptance_by_agent_judge.csv")
