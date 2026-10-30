"""a09 - Verification cue (Table 4, Section 5.2): the 83 tasks with DeepSeek V3.2 evidence-gathering errors
rerun with one added sentence; per-task rates, cue minus baseline, task bootstrap (seed 2026, B = 4000).

Inputs : data/derived/full_deepseekv32_mechanisms.csv (baseline, 4 attempts), cue_deepseekv32_mechanisms.csv (2 attempts)
Outputs: outputs/cue_effects.csv (published)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from common import cue_mechanisms, full_mechanisms, write
from config import SEED_CUE, B_CUE

M = full_mechanisms(); CU = cue_mechanisms()
B = M[M.task_id.isin(CU.task_id.unique())]
rng = np.random.default_rng(SEED_CUE)


def task_level(d):
    return d.assign(eg=(d.locus == "evidence_gathering"), succ=d.official_pass.astype(float), act=(d.locus == "action"),
                    conc=(d.locus == "conclusion")).groupby("task_id")[["succ", "eg", "conc", "act"]].mean()


tb, tc = task_level(B), task_level(CU)
tb, tc = tb.loc[tc.index], tc
rows = []
for cat in ["all"] + sorted(CU.category.unique()):
    idx = tc.index if cat == "all" else [t for t in tc.index if t.startswith(cat + "_")]
    d = tc.loc[idx] - tb.loc[idx]
    boots = np.array([d.iloc[rng.integers(0, len(d), len(d))].mean().values for _ in range(B_CUE)])
    for j, m_ in enumerate(d.columns):
        rows.append(dict(category=cat, n_tasks=len(idx), measure=m_, baseline=tb.loc[idx, m_].mean(), cue=tc.loc[idx, m_].mean(),
                         diff=d[m_].mean(), lo=np.percentile(boots[:, j], 2.5), hi=np.percentile(boots[:, j], 97.5)))
write(pd.DataFrame(rows), "cue_effects.csv")
