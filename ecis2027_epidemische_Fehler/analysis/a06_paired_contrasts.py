"""a06 - Paired condition contrasts (Table 6, Section 5.6): same judge model and attempts, trajectory only vs an
added evidence condition (API specification, checklist, record access); task-clustered bootstrap, seed 7.

Outputs: outputs/paired_condition_contrasts.csv, outputs/paired_condition_contrasts_pooled.csv (published)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import access_table, attempts, paired, pilot_wide, write
import pandas as pd

A = attempts(judges=["gpt-4.1", "gpt-4.1-mini", "gpt-4.1_spec", "gpt-4.1-mini_spec", "deepseek-v3.2", "deepseek-v3.2_verify"])
X = access_table(A)
Wv = pilot_wide(A)

rows = []
for run in ["pilot_gpt41", "pilot_gpt41mini", "full_deepseekv32"]:
    d = X[X.run == run][["task_id", "cls", "neutral_pass", "access_pass"]].copy()
    rows.append(dict(comparison="record access vs trajectory only (DeepSeek judge)", agent=run, **paired(d, "neutral_pass", "access_pass")))
for run in ["pilot_gpt41", "pilot_gpt41mini"]:
    d = Wv[Wv.agent_run == run].dropna(subset=["deepseek-v3.2", "deepseek-v3.2_verify"]).copy()
    d[["deepseek-v3.2", "deepseek-v3.2_verify"]] = d[["deepseek-v3.2", "deepseek-v3.2_verify"]].astype(bool)
    rows.append(dict(comparison="checklist vs trajectory only (DeepSeek judge)", agent=run, **paired(d, "deepseek-v3.2", "deepseek-v3.2_verify")))
    d = Wv[Wv.agent_run == run].dropna(subset=["gpt-4.1-mini", "gpt-4.1-mini_spec"]).copy()
    d[["gpt-4.1-mini", "gpt-4.1-mini_spec"]] = d[["gpt-4.1-mini", "gpt-4.1-mini_spec"]].astype(bool)
    rows.append(dict(comparison="specification vs trajectory only (GPT-4.1-mini judge)", agent=run, **paired(d, "gpt-4.1-mini", "gpt-4.1-mini_spec")))
d = Wv[Wv.agent_run == "pilot_gpt41"].dropna(subset=["gpt-4.1", "gpt-4.1_spec"]).copy()
d[["gpt-4.1", "gpt-4.1_spec"]] = d[["gpt-4.1", "gpt-4.1_spec"]].astype(bool)
rows.append(dict(comparison="specification vs trajectory only (GPT-4.1 judge)", agent="pilot_gpt41", **paired(d, "gpt-4.1", "gpt-4.1_spec")))
write(pd.DataFrame(rows), "paired_condition_contrasts.csv")

rows = []
dA = X[["task_id", "cls", "neutral_pass", "access_pass"]].copy()
rows.append(dict(comparison="record access vs trajectory only, pooled (3 agents)", **paired(dA, "neutral_pass", "access_pass")))
dG = X[X.run.str.startswith("pilot")][["task_id", "cls", "neutral_pass", "access_pass"]].copy()
rows.append(dict(comparison="record access vs trajectory only, GPT agents pooled", **paired(dG, "neutral_pass", "access_pass")))
dV = Wv.dropna(subset=["deepseek-v3.2", "deepseek-v3.2_verify"]).copy()
dV[["deepseek-v3.2", "deepseek-v3.2_verify"]] = dV[["deepseek-v3.2", "deepseek-v3.2_verify"]].astype(bool)
rows.append(dict(comparison="checklist vs trajectory only, GPT agents pooled", **paired(dV, "deepseek-v3.2", "deepseek-v3.2_verify")))
dS = Wv.dropna(subset=["gpt-4.1-mini", "gpt-4.1-mini_spec"]).copy()
dS[["gpt-4.1-mini", "gpt-4.1-mini_spec"]] = dS[["gpt-4.1-mini", "gpt-4.1-mini_spec"]].astype(bool)
rows.append(dict(comparison="specification vs trajectory only, GPT-4.1-mini judge, pooled", **paired(dS, "gpt-4.1-mini", "gpt-4.1-mini_spec")))
write(pd.DataFrame(rows), "paired_condition_contrasts_pooled.csv")
