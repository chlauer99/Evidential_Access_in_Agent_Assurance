"""a02 - Outcome classes, analysis denominators (Table 2) and task-level bimodality (Section 5.1).

Inputs : data/derived/pilot_outcome_classes.csv, data/derived/full_deepseekv32_mechanisms.csv,
         data/raw/pilot_*/results.jsonl, data/raw/control_*/results.jsonl, judge verdict files
Outputs: outputs/analysis_denominators.csv   (published; Table 2)
         outputs/outcome_classes.csv          outcome class counts per agent (Table 3 notes, Section 5.3)
         outputs/task_bimodality.csv          tasks on which every attempt passed or every attempt failed
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
from common import attempts, codes_for, full_mechanisms, read_jsonl, write
from config import RAW

A = attempts(judges=["gpt-4.1", "gpt-4.1-mini", "gpt-4.1_spec", "gpt-4.1-mini_spec", "deepseek-v3.2", "deepseek-v3.2_verify"],
             controls=False)
CL = ("correct", "format_only", "grounded_error")


def den(run, judges):
    d = A[(A.agent_run == run) & A.judge.isin(judges)]
    d = d.drop_duplicates(["task_id", "attempt"])
    return len(d), int(d.truth.isin(["correct", "format_only"]).sum()), int((d.truth == "grounded_error").sum()), d


def excl(run, judges):
    codes = codes_for(run)
    n_all = len(codes)
    n, c, e, d = den(run, judges)
    parts = []
    miss = n_all - n
    cls = pd.Series([v["failure_type_refined"] for v in codes.values()])
    judged = set(zip(d.task_id, d.attempt.astype(int)))
    notj = [codes[k]["failure_type_refined"] for k in codes if k not in judged]
    if miss:
        parts.append(f"{miss} attempt{'s' if miss > 1 else ''} without a judge verdict")
    pwa = int((d.cls == "pass_without_acting").sum())
    if pwa:
        parts.append(f"{pwa} pass{'es' if pwa > 1 else ''} on tasks where doing nothing also passes" if pwa > 1
                     else "1 pass on a task where doing nothing also passes")
    wo = int((d.cls == "wrong_order").sum())
    if wo:
        parts.append(f"{wo} wrong-order action errors")
    nf = int((d.cls == "no_finish").sum())
    if nf:
        parts.append(f"{nf} attempts without a final answer")
    return n_all, c, e, parts


rows = []
n, c, e, p = excl("full_deepseekv32", ["deepseek-v3.2"])
# order of the exclusion clauses as published
order = {"without a judge verdict": 0, "doing nothing": 1, "wrong-order": 2, "final answer": 3}
p = sorted(p, key=lambda s: min(v for k, v in order.items() if k in s))
rows.append(("DeepSeek self-judge (trajectory only)", n, c, e, "; ".join(p) or "none"))
for run, lab in [("pilot_gpt41", "GPT-4.1"), ("pilot_gpt41mini", "GPT-4.1-mini")]:
    n, c, e, p = excl(run, ["gpt-4.1"])
    rows.append((f"{lab} attempts, trajectory-only and specification judges", n, c, e, "; ".join(p) or "none"))
for run, lab in [("pilot_gpt41", "GPT-4.1"), ("pilot_gpt41mini", "GPT-4.1-mini")]:
    n, c, e, p = excl(run, ["deepseek-v3.2_verify"])
    p = sorted(p, key=lambda s: 0 if "doing nothing" in s else 1)
    rows.append((f"{lab} attempts, checklist judge", n, c, e, "; ".join(p) or "none"))
# record-access sample: all sampled attempts are classifiable (strata)
import json
from config import RAW as _R
S = pd.DataFrame(json.load(open(_R / "record_access" / "agentic_judge_sample.json", encoding="utf-8")))
rows.append(("Record-access sample (3 agents, stratified)", len(S), int((S.stratum == "subst_correct").sum()),
             int((S.stratum != "subst_correct").sum()), "none (sampled from classifiable attempts)"))
den_df = pd.DataFrame(rows, columns=["analysis", "attempts", "correct_n", "error_n", "exclusions"])
write(den_df, "analysis_denominators.csv")

# outcome classes per agent
oc = []
for run in ["pilot_gpt41", "pilot_gpt41mini", "full_deepseekv32"]:
    cls = pd.Series([v["failure_type_refined"] for v in codes_for(run).values()])
    for k, v in cls.value_counts().items():
        oc.append(dict(agent_run=run, cls=k, n=int(v), share=v / len(cls)))
for run in ["control_replay", "control_null"]:
    res = read_jsonl(RAW / run / "results.jsonl")
    oc.append(dict(agent_run=run, cls="grader_pass", n=sum(r["passed"] for r in res), share=sum(r["passed"] for r in res) / len(res)))
write(pd.DataFrame(oc), "outcome_classes.csv")

# task-level bimodality: all attempts of a task pass, or all fail
bm = []
M = full_mechanisms()
per = {"pilot_gpt41": None, "pilot_gpt41mini": None}
for run in per:
    res = [r for r in read_jsonl(RAW / run / "results.jsonl") if r["status"] != "API_ERROR"]
    latest = {}
    for r in res:
        latest[(r["task_id"], r["attempt"])] = r
    d = pd.DataFrame(latest.values())
    per[run] = d.groupby("task_id").passed.mean()
per["full_deepseekv32"] = M.groupby("task_id").official_pass.mean()
for run, s in per.items():
    bm.append(dict(agent_run=run, tasks=len(s), all_or_nothing=int(((s == 0) | (s == 1)).sum()),
                   all_pass=int((s == 1).sum()), all_fail=int((s == 0).sum()), mean_task_success=s.mean()))
write(pd.DataFrame(bm), "task_bimodality.csv")
