"""a10 - Evidential provenance of substantive errors (P1, Table 3, Section 5.1).

Level A: summary from the archived per-error coding (data/derived/provenance_coding.csv, 529 errors), plus a
re-coding of the 121 GPT-agent errors from their archived trajectories with the same rules (check).
Level A+ (if data/raw/full_deepseekv32/results.jsonl and answers/ are present): the 408 DeepSeek V3.2 errors are
re-coded from raw as well.
Outputs: outputs/provenance_summary.csv (published), outputs/provenance_recoded.csv, outputs/provenance_recode_check.csv
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
from common import full_mechanisms, pilot_mechanisms, write, MECH
from config import DERIVED, RAW, full_run_raw_available

PV = pd.read_csv(DERIVED / "provenance_coding.csv")
summ = PV.groupby(["agent", "provenance"]).size().unstack(fill_value=0).reindex(columns=["grounded", "fabricated", "unclassified"], fill_value=0)
summ["substantive_errors"] = summ.sum(axis=1)
summ.loc["Total"] = summ.sum()
summ["grounded_share_all"] = (summ.grounded / summ.substantive_errors).round(3)
summ["grounded_share_classifiable"] = (summ.grounded / (summ.grounded + summ.fabricated)).round(3)
summ.columns.name = None
write(summ.reset_index(), "provenance_summary.csv")

from provenance_rules import recode

rows = []
cls = pd.read_csv(DERIVED / "pilot_outcome_classes.csv")
for run, agent in [("pilot_gpt41", "GPT-4.1"), ("pilot_gpt41mini", "GPT-4.1-mini")]:
    d = cls[(cls.agent_run == run) & cls.cls.isin(["substantive_answer_error", "commission", "omission"])]
    pm = pilot_mechanisms(run)
    rows += recode(run, agent, [(t, int(a), c, pm.get((t, int(a)), "") if pm is not None else MECH.get((t, c), ""))
                                for t, a, c in zip(d.task_id, d.attempt, d.cls)])
if full_run_raw_available():
    M = full_mechanisms()
    d = M[M.refined_class.isin(["substantive_answer_error", "commission", "wrong_order", "omission"])]
    rows += recode("full_deepseekv32", "DeepSeek V3.2", [(t, int(a), c, m) for t, a, c, m in zip(d.task_id, d.attempt, d.refined_class, d.mechanism)])
RC = pd.DataFrame(rows)
write(RC, "provenance_recoded.csv")
key = ["agent", "task_id", "attempt"]
cmp_ = PV.merge(RC, on=key, suffixes=("_archived", "_recoded"))
chk = [dict(agent=a, n_recoded=len(g), provenance_agree=int((g.provenance_archived == g.provenance_recoded).sum()),
            basis_agree=int((g.basis_archived == g.basis_recoded).sum())) for a, g in cmp_.groupby("agent")]
write(pd.DataFrame(chk), "provenance_recode_check.csv")
