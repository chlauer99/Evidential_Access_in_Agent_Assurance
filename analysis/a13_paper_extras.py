"""a13 - Numbers quoted in the manuscript text that are not a single cell of a published table
(Sections 1, 4.3, 5.1-5.7, Table 5). One row per number: key, value, description, section.

Inputs : attempt x judge table, record-access table, run folders, derived tables
Outputs: outputs/paper_extras.csv
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import re
import numpy as np
import pandas as pd
from common import access_table, attempts, codes_for, full_mechanisms, read_jsonl, write
from config import RAW

rows = []
def add(key, value, desc, section):
    rows.append(dict(key=key, value=float(value), description=desc, section=section))

A = attempts(judges=["gpt-4.1", "gpt-4.1-mini", "gpt-4.1_spec", "gpt-4.1-mini_spec", "deepseek-v3.2", "deepseek-v3.2_verify"])
P = A[A.agent_run.str.startswith("pilot")]

# ---- scale of the study
n_att = sum(len(codes_for(r)) for r in ["pilot_gpt41", "pilot_gpt41mini", "full_deepseekv32"])
add("attempts_total", n_att, "agent attempts (240 + 240 + 1,200)", "Abstract, 1")
def lines(run, judge):
    f = RAW / run / f"judge_{judge}.jsonl"
    return len(read_jsonl(f)) if f.exists() else 0
runs_all = ["pilot_gpt41", "pilot_gpt41mini", "control_replay", "control_null", "full_deepseekv32"]
traj = sum(lines(r, j) for r in runs_all for j in ["gpt-4.1", "gpt-4.1-mini", "gpt-4.1_spec", "gpt-4.1-mini_spec", "deepseek-v3.2"])
chk = sum(lines(r, "deepseek-v3.2_verify") for r in runs_all)
acc = sum(lines(r, "deepseek-v3.2_access") for r in runs_all)
add("verdicts_trajectory_only", traj, "trajectory-only verdicts (incl. API specification)", "Table 2 note")
add("verdicts_checklist", chk, "checklist verdicts (incl. controls)", "Table 2 note")
add("verdicts_record_access", acc, "record-access verdicts", "Table 2 note")
add("verdicts_total", traj + chk + acc, "model-judge verdicts in total", "1")
add("pilot_nonpassing", sum(1 for r in ["pilot_gpt41", "pilot_gpt41mini"] for v in codes_for(r).values() if v["failure_type_refined"] != "pass"),
    "non-passing pilot attempts validated against the tracer", "4.4")
M = full_mechanisms()
sub = M[M.refined_class.isin(["substantive_answer_error", "commission", "wrong_order", "omission"])]
add("ds_mechanism_coded", int((sub.mechanism.notna() & (sub.mechanism != "unmapped")).sum()), "DeepSeek substantive errors with a tracer mechanism", "4.4, Table 3")

# ---- Table 5: acceptance by outcome class
def acc_rate(run_filter, judge, truth):
    # Table 5 "official pass" = every attempt the rule-based grader passed (incl. passes on do-nothing tasks)
    sel = A.cls.isin(["pass", "pass_without_acting"]) if truth == "correct" else (A.truth == truth)
    d = A[run_filter & (A.judge == judge) & sel]
    return d.judge_pass.mean()
gp = [(r, j) for r in ["pilot_gpt41", "pilot_gpt41mini"] for j in ["gpt-4.1", "gpt-4.1-mini"]]
for truth, key in [("correct", "official_pass"), ("format_only", "format_only"), ("grounded_error", "substantive_error")]:
    v = [acc_rate(A.agent_run == r, j, truth) for r, j in gp]
    add(f"t5_gpt_{key}_min", min(v), f"GPT judges, {key}: minimum over the 4 trajectory-only pairings", "Table 5")
    add(f"t5_gpt_{key}_max", max(v), f"GPT judges, {key}: maximum over the 4 trajectory-only pairings", "Table 5")
    v = [acc_rate(A.agent_run == r, "deepseek-v3.2", truth) for r in ["pilot_gpt41", "pilot_gpt41mini", "full_deepseekv32"]]
    add(f"t5_ds_{key}_min", min(v), f"DeepSeek judge, {key}: minimum over its 3 pairings", "Table 5")
    add(f"t5_ds_{key}_max", max(v), f"DeepSeek judge, {key}: maximum over its 3 pairings", "Table 5")
for truth, run in [("replay", "control_replay"), ("do_nothing", "control_null")]:
    v = [acc_rate(A.agent_run == run, j, truth) for j in ["gpt-4.1", "gpt-4.1-mini"]]
    add(f"t5_gpt_{truth}_min", min(v), f"GPT judges on the {truth} control: minimum", "Table 5")
    add(f"t5_gpt_{truth}_max", max(v), f"GPT judges on the {truth} control: maximum", "Table 5")
    add(f"t5_ds_{truth}", acc_rate(A.agent_run == run, "deepseek-v3.2", truth), f"DeepSeek judge on the {truth} control", "Table 5")
    res = read_jsonl(RAW / run / "results.jsonl")
    add(f"t5_grader_{truth}", np.mean([r["passed"] for r in res]), f"rule-based grader pass rate on the {truth} control (30 pilot tasks)", "Table 5, 5.3, Fig. 2")

for run in ["pilot_gpt41", "pilot_gpt41mini", "full_deepseekv32"]:
    cl = [v["failure_type_refined"] for v in codes_for(run).values()]
    add(f"grader_certification_{run}", cl.count("pass") / (cl.count("pass") + cl.count("format_only")),
        f"rule-based grader: official passes / substantively correct attempts ({run})", "Fig. 2")

# ---- Section 5.4
T = A[A.judge.isin(["gpt-4.1", "gpt-4.1-mini"]) & A.agent_run.str.startswith("pilot") & A.truth.isin(["correct", "format_only", "grounded_error"])]
disc = [1 - T[(T.agent_run == r) & (T.judge == j) & (T.truth == "grounded_error")].judge_pass.mean() for r, j in gp]
cert = [T[(T.agent_run == r) & (T.judge == j) & (T.truth != "grounded_error")].judge_pass.mean() for r, j in gp]
add("gpt_discovery_min", min(disc), "GPT trajectory-only judges: error discovery, minimum", "5.4, Table 7")
add("gpt_discovery_max", max(disc), "GPT trajectory-only judges: error discovery, maximum", "5.4, Table 7")
add("gpt_certification_min", min(cert), "GPT trajectory-only judges: correct certification, minimum", "5.4, Fig. 2, Table 7")
add("gpt_certification_max", max(cert), "GPT trajectory-only judges: correct certification, maximum", "5.4, Fig. 2, Table 7")
sj = A[(A.agent_run == "full_deepseekv32") & (A.judge == "deepseek-v3.2")].copy()
sj["cat"] = sj.task_id.str.split("_").str[0]
g = sj[sj.truth.isin(["correct", "grounded_error"])]
byc = g.groupby(["cat", "truth"]).judge_pass.agg(["mean", "size"]).unstack("truth")
byc.columns = [f"{a}_{b}" for a, b in byc.columns]; byc["J"] = byc.mean_correct - byc.mean_grounded_error
bb = byc.dropna(); w = 1 / (1 / bb.size_correct + 1 / bb.size_grounded_error)
add("ds_self_J_category_stratified", (bb.J * w).sum() / w.sum(), "DeepSeek self-judge J with task category held fixed", "5.4")

# ---- Section 5.5
MECH_EG = ["false absence", "incomplete retrieval"]
eg = P[(P.truth == "grounded_error") & P.mechanism.isin(MECH_EG) & P.judge.isin(["gpt-4.1", "gpt-4.1-mini", "gpt-4.1-mini_spec"])]
add("gpt3_eg_verdicts", len(eg), "verdicts of three GPT judge conditions on evidence-gathering errors", "5.5, Fig. 2")
add("gpt3_eg_accepted", int(eg.judge_pass.sum()), "of which acceptances", "5.5, Fig. 2")
from common import VALID_REASON as _VR
_rej = eg[~eg.judge_pass]
add("gpt3_eg_rationales_questioning_query", int(sum(bool(re.search(_VR[m], r, re.I | re.S)) for m, r in zip(_rej.mechanism, _rej.rationale))),
    "rejections among them whose rationale names the query problem (code, pages)", "5.5")
spec = P[P.judge.str.endswith("_spec")]
add("spec_correct_loinc_rationales", int(spec.rationale.str.contains(r"correct LOINC code", case=False).sum()),
    "API-specification rationales calling the search 'the correct LOINC code'", "5.5, Table 7")
cw = P[(P.truth == "grounded_error") & P.mechanism.isin(["time-window error", "unnecessary order", "no action on detected absence"])]
per = cw[cw.judge.isin(["gpt-4.1", "gpt-4.1-mini", "gpt-4.1-mini_spec"])].groupby("judge")  # the three conditions that saw both agents
add("order_window_errors", cw[cw.judge == "gpt-4.1"].shape[0], "order-rule and time-window errors of the GPT agents", "5.5")
nrej = per.judge_pass.apply(lambda s: int((~s).sum()))
add("order_window_rejected_min", nrej.min(), "GPT judge conditions: rejections of these errors, minimum", "5.5")
add("order_window_rejected_max", nrej.max(), "GPT judge conditions: rejections of these errors, maximum", "5.5")
from common import VALID_REASON
rj = cw[~cw.judge_pass & cw.judge.isin(["gpt-4.1", "gpt-4.1-mini", "gpt-4.1-mini_spec"])]
add("order_window_rejections_reason_valid_share",
    np.mean([bool(re.search(VALID_REASON[m], r, re.I | re.S)) for m, r in zip(rj.mechanism, rj.rationale)]),
    "share of these rejections whose rationale names the actual error", "5.5")
ds = P[P.judge == "deepseek-v3.2"]
kfa = ds[(ds.truth == "grounded_error") & (ds.mechanism == "false absence")]
add("ds_gpt_potassium_fa", len(kfa), "potassium false absences in the GPT attempts", "5.5")
add("ds_gpt_potassium_fa_rejected", int((~kfa.judge_pass).sum()), "rejected by the DeepSeek judge", "5.5")
add("ds_gpt_potassium_fa_named_K", int(kfa[~kfa.judge_pass].rationale.str.contains(r"(?:'K'|\"K\"|\bcode K\b|\bK\b)", regex=True).sum()),
    "rejection rationales naming the local code K", "5.5")
Mx = M.merge(sj[["task_id", "attempt", "judge_pass", "rationale"]].assign(attempt=lambda d: d.attempt.astype(int)), on=["task_id", "attempt"])
nm = Mx[(Mx.mechanism == "false_absence") & (Mx.category == "task1") & Mx.refined_class.isin(["substantive_answer_error", "omission", "commission"])]
add("ds_self_name_fa", len(nm), "DeepSeek's own patient-name false absences (task category 1)", "5.5")
add("ds_self_name_fa_accepted", int(nm.judge_pass.sum()), "accepted by the DeepSeek self-judge", "5.5")
ir = ds[(ds.truth == "grounded_error") & (ds.mechanism == "incomplete retrieval")]
add("ds_gpt_ir", len(ir), "incomplete retrievals in the GPT attempts", "5.5")
add("ds_gpt_ir_accepted", int(ir.judge_pass.sum()), "accepted by the DeepSeek judge", "5.5")
oi = Mx[(Mx.mechanism == "incomplete_retrieval") & Mx.refined_class.isin(["substantive_answer_error", "omission", "commission"])]
add("ds_self_ir", len(oi), "DeepSeek's own incomplete retrievals", "5.5")
add("ds_self_ir_rejected", int((~oi.judge_pass).sum()), "rejected by the DeepSeek self-judge", "5.5")
add("ds_self_ir_rejections_mention_pages", int(oi[~oi.judge_pass].rationale.str.contains(r"\bpages?\b|paginat|\bnext\b|unread|more results", case=False).sum()),
    "of these rejections, rationales mentioning unread pages", "5.5")
g41 = P[(P.agent_run == "pilot_gpt41") & (P.judge == "gpt-4.1") & P.truth.isin(["correct", "format_only"]) & P.task_id.str.match(r"task(3|8)_")]
add("gpt41_bp_referral_correct", len(g41), "correct blood-pressure recordings and referral orders (GPT-4.1 attempts)", "5.5")
add("gpt41_bp_referral_rejected", int((~g41.judge_pass).sum()), "rejected by the GPT-4.1 judge", "5.5")

# ---- Section 5.6: record access
X = access_table(A[A.judge == "deepseek-v3.2"])
add("access_cost_per_verdict", X.cost_usd.mean(), "USD per record-access verdict", "5.6, Table 7")
ne = pd.concat([pd.read_json(RAW / r / "judge_deepseek-v3.2.jsonl", lines=True) for r in ["pilot_gpt41", "pilot_gpt41mini", "full_deepseekv32"]])
add("neutral_ds_cost_per_verdict", ne.filter(like="cost").sum(axis=1).mean(), "USD per trajectory-only DeepSeek verdict", "5.6")
cr = X[(X.cls == "correct") & (~X.access_pass)]
add("access_false_alarms", len(cr), "correct attempts rejected with record access", "5.6")
POST = r"not (?:been )?(?:stored|recorded|saved|created|found in the EHR)|no (?:observation|servicerequest|medicationrequest|order|record)s? (?:was |were )?(?:recorded|found|exist|stored|created)|POST (?:may have |might have )?(?:failed|not)|does not (?:exist|appear)|did not (?:persist|save)|was not (?:stored|recorded|created|saved)|verify (?:creation|the (?:order|record))"
add("access_false_alarms_unstored_orders", int(cr.rationale.astype(str).str.contains(POST, case=False, regex=True).sum()),
    "of these, rationales citing an order or record that was not stored", "5.6")
for run in ["pilot_gpt41", "pilot_gpt41mini", "full_deepseekv32"]:
    d = X[X.run == run]
    add(f"access_reject_correct_{run}", 1 - d[d.cls == "correct"].access_pass.mean(), f"share of correct work rejected with access ({run})", "5.6")
G = X[X.cls == "grounded"].copy()
G["m"] = G.mech.str.replace("_", " ")
for m, pat in [("false absence", r"\bK\b|code|LOINC|2823|name|given|family|birthdate|search|query|exist|found"),
               ("incomplete retrieval", r"page|next|more|additional|all (?:the )?(?:results|values|glucose)|later|recent|missed|only (?:the )?first")]:
    for grp, sel in [("gpt", G.run.str.startswith("pilot")), ("ds", G.run == "full_deepseekv32")]:
        d = G[sel & (G.m == m) & (~G.access_pass)]
        add(f"access_{m.replace(' ', '_')}_named_{grp}", d.rationale.astype(str).str.contains(pat, case=False, regex=True).mean(),
            f"record access, {m}: share of rejections naming the actual error ({grp})", "5.6")

# ---- Section 5.7
E = P[P.truth == "grounded_error"].pivot_table(index=["agent_run", "task_id", "attempt"], columns="judge", values="judge_pass", aggfunc="first")
for a_, b_, k in [("gpt-4.1", "gpt-4.1-mini", "same"), ("gpt-4.1", "deepseek-v3.2", "cross1"), ("gpt-4.1-mini", "deepseek-v3.2", "cross2")]:
    d = E[[a_, b_]].dropna().astype(bool)
    add(f"joint_accept_{k}", (d[a_] & d[b_]).mean(), f"errors accepted by both {a_} and {b_} (n = {len(d)})", "5.7, Table 7")
for r, j in gp:
    add(f"accept_errors_{r}_{j}", P[(P.agent_run == r) & (P.judge == j) & (P.truth == "grounded_error")].judge_pass.mean(),
        f"acceptance of substantive errors, agent {r}, judge {j}", "5.7")
write(pd.DataFrame(rows), "paper_extras.csv")
