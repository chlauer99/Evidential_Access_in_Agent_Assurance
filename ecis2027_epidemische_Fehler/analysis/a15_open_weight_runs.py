"""a15 - Open-weight extension for manuscript v4 (GPT-OSS-120B and Qwen3.8-27B runs, cross-judging).

Inputs : runs/gpt_oss_120b_exp_2, runs/qwen3_8_27b_exp_3, runs/gpt_oss_120b_qwen_judge_exp_1 (derived/ tables,
         mab_runs/full_deepseekv32/judge_*.jsonl, 09_analysis/outputs/) and runs/cross_judge_exp_1 (cross verdicts).
Truth classes and exclusions follow harness/pipeline/analyse_single.py (= paper Table 2): errors are
substantive_answer_error, omission and commission; correct work is pass and format_only; wrong_order,
pass_without_acting and no_finish are excluded from judge measures. Descriptive error counts include wrong_order.
Task-cluster intervals for J are read from the run outputs (1,000 draws, seed 2027), not recomputed.
Stratified J weights task categories as in a13 (w = 1 / (1/n_correct + 1/n_errors)).

Outputs: runs/comparative_analysis/v4/
  ow_numbers.csv          every v4 number: key, value, description, manuscript section
  ow_judge_cells.csv      attempt set x judge x condition: n, acceptance by truth, J and CI, stratified J
  ow_locus.csv            error discovery by error locus per cell
  ow_detection.csv        rejections by task category and tracer mechanism per cell
  ow_rationales.csv       keyword matches in rationales for selected error and correct-work groups
  ow_cross_judge.csv      cross-judged sets: joint acceptance by mechanism, shared false rejections by category
  ow_fig1_rows.csv        Figure 1 rows in judge_conditions_summary.csv format
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
OUT = RUNS / "comparative_analysis" / "v4"
OUT.mkdir(parents=True, exist_ok=True)
MAIN = "full_deepseekv32"
ERR = {"substantive_answer_error", "omission", "commission"}
COR = {"pass", "format_only"}
DESCR = ERR | {"wrong_order"}

SETS = {"gptoss": "gpt_oss_120b_exp_2", "qwen": "qwen3_8_27b_exp_3", "gptoss2": "gpt_oss_120b_qwen_judge_exp_1"}
AGENT = {"gptoss": "GPT-OSS", "qwen": "Qwen", "gptoss2": "GPT-OSS (run 2)"}
JFILE = {"GPT-OSS": "judge_gpt-oss-120b", "Qwen": "judge_qwen3_8_27b"}
SUFFIX = {"neutral": "", "spec": "_spec", "checklist": "_verify", "record_access": "_access"}
CROSS = RUNS / "cross_judge_exp_1"

# (attempt set, judge, pairing, condition, verdict file)
CELLS = [("gptoss", "GPT-OSS", "self", c, RUNS / SETS["gptoss"] / "mab_runs" / MAIN / f"{JFILE['GPT-OSS']}{s}.jsonl") for c, s in SUFFIX.items()]
CELLS += [("gptoss", "Qwen", "cross-developer", "neutral", CROSS / "on_gpt_oss_attempts/mab_runs" / MAIN / f"{JFILE['Qwen']}.jsonl")]
CELLS += [("qwen", "Qwen", "self", c, RUNS / SETS["qwen"] / "mab_runs" / MAIN / f"{JFILE['Qwen']}{s}.jsonl") for c, s in SUFFIX.items()]
CELLS += [("qwen", "GPT-OSS", "cross-developer", "neutral", CROSS / "on_qwen_attempts/mab_runs" / MAIN / f"{JFILE['GPT-OSS']}.jsonl")]
CELLS += [("gptoss2", "Qwen", "cross-developer", c, RUNS / SETS["gptoss2"] / "mab_runs" / MAIN / f"{JFILE['Qwen']}{s}.jsonl") for c, s in SUFFIX.items()]
PATH = {(s, judge, cond): path for s, judge, _, cond, path in CELLS}

NUM = []


def add(key, value, description, section):
    NUM.append(dict(key=key, value=value, description=description, section=section))


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def truth(c):
    return "error" if c in ERR else "correct" if c in COR else "excluded"


M = {}
for s, run in SETS.items():
    d = pd.read_csv(RUNS / run / "derived" / f"{MAIN}_mechanisms.csv")
    d["truth"] = d.refined_class.map(truth)
    M[s] = d.set_index(["task_id", "attempt"])


def verdicts(path):
    rows = [r for r in read_jsonl(path)]
    v = pd.DataFrame([dict(task_id=r["task_id"], attempt=int(r["attempt"]), verdict=r.get("verdict"),
                           text=" ".join([str(r.get("rationale") or "")] + [str(i) for i in (r.get("issues") or [])]))
                      for r in rows])
    return v.drop_duplicates(["task_id", "attempt"], keep="last").set_index(["task_id", "attempt"])


V = {}
for cell in CELLS:
    s, judge, pairing, cond, path = cell
    v = verdicts(path).join(M[s][["category", "refined_class", "truth", "mechanism", "locus", "official_pass"]], how="inner")
    v = v[(v.truth != "excluded") & v.verdict.isin(["pass", "fail"])]
    V[(s, judge, cond)] = v


def j_of(v):
    e, c = v[v.truth == "error"], v[v.truth == "correct"]
    return (e.verdict == "fail").mean() + (c.verdict == "pass").mean() - 1


def stratified_j(v):
    num = den = 0.0
    for _, g in v.groupby("category"):
        e, c = g[g.truth == "error"], g[g.truth == "correct"]
        if len(e) and len(c):
            w = 1 / (1 / len(e) + 1 / len(c))
            num += w * ((e.verdict == "fail").mean() + (c.verdict == "pass").mean() - 1); den += w
    return num / den


# ---- intervals as published in the run outputs
CI = {}
for s, run in SETS.items():
    js = pd.read_csv(RUNS / run / "09_analysis/outputs/judge_summary.csv").set_index("condition")
    judge = "Qwen" if s != "gptoss" else "GPT-OSS"
    for cond in SUFFIX:
        CI[(s, judge, cond)] = tuple(js.loc[cond, ["youden_j", "youden_j_lo", "youden_j_hi"]])
xc = pd.read_csv(CROSS / "outputs/agent_judge_cells.csv")
for r in xc[xc.relation == "cross"].itertuples():
    s = "gptoss" if r.attempts == SETS["gptoss"] else "qwen"
    CI[(s, "Qwen" if r.judge.startswith("Qwen") else "GPT-OSS", "neutral")] = (r.youden_j, r.youden_j_lo, r.youden_j_hi)

cells = []
for (s, judge, cond), v in V.items():
    e, c = v[v.truth == "error"], v[v.truth == "correct"]
    J, lo, hi = CI[(s, judge, cond)]
    assert abs(J - j_of(v)) < 1e-9, (s, judge, cond, J, j_of(v))
    pairing = "self" if (judge == "GPT-OSS") == (s != "qwen") else "cross-developer"
    cells.append(dict(attempts=AGENT[s], judge=judge, pairing=pairing, condition=cond, n_correct=len(c), n_errors=len(e),
                      correct_accepted=(c.verdict == "pass").mean(), errors_accepted=(e.verdict == "pass").mean(),
                      official_pass_accepted=(v[v.refined_class == "pass"].verdict == "pass").mean(),
                      format_only_accepted=(v[v.refined_class == "format_only"].verdict == "pass").mean(),
                      J=J, J_lo=lo, J_hi=hi, J_stratified=stratified_j(v)))
C = pd.DataFrame(cells)
C.to_csv(OUT / "ow_judge_cells.csv", index=False)
for r in C.itertuples():
    k = f"{r.judge}_on_{r.attempts}_{r.condition}".replace(" ", "").replace("(run2)", "_run2")
    add(f"{k}_J_stratified", round(r.J_stratified, 3), f"{r.judge} judge on {r.attempts} attempts, {r.condition}: J with task category held fixed", "5.4")

# ---- error discovery by locus
loc = []
for (s, judge, cond), v in V.items():
    for l, g in v[v.truth == "error"].groupby("locus"):
        loc.append(dict(attempts=AGENT[s], judge=judge, condition=cond, locus=l, n=len(g), rejected=int((g.verdict == "fail").sum())))
L = pd.DataFrame(loc); L["discovery"] = L.rejected / L.n
L.to_csv(OUT / "ow_locus.csv", index=False)

# ---- detection by task category and mechanism
det = []
for (s, judge, cond), v in V.items():
    for (cat, mech), g in v[v.truth == "error"].groupby(["category", "mechanism"]):
        det.append(dict(attempts=AGENT[s], judge=judge, condition=cond, category=cat, mechanism=mech, n=len(g),
                        rejected=int((g.verdict == "fail").sum())))
    for cat, g in v[v.truth == "correct"].groupby("category"):
        det.append(dict(attempts=AGENT[s], judge=judge, condition=cond, category=cat, mechanism="(correct work)", n=len(g),
                        rejected=int((g.verdict == "fail").sum())))
D = pd.DataFrame(det)
D.to_csv(OUT / "ow_detection.csv", index=False)


def det_of(s, judge, cond, cat, mech):
    r = D[(D.attempts == AGENT[s]) & (D.judge == judge) & (D.condition == cond) & (D.category == cat) & (D.mechanism == mech)]
    return (int(r.rejected.iloc[0]), int(r.n.iloc[0])) if len(r) else (0, 0)


# inferability of evidence-gathering errors (Figure 2): a patient-name false absence ("Patient not found" for a full
# name sent as one parameter) is not inferable from the trajectory; a potassium false absence (local code K stated
# in the context) and an incomplete retrieval (unfollowed `next` link in the response) are.
inf = []
for (s, judge, cond), v in V.items():
    e = v[(v.truth == "error") & (v.locus == "evidence_gathering")]
    name = (e.category == "task1") & (e.mechanism == "false_absence")
    inferable = ((e.category == "task9") & (e.mechanism == "false_absence")) | (e.mechanism == "incomplete_retrieval")
    for grp, g in [("not_inferable", e[name]), ("inferable", e[inferable])]:
        inf.append(dict(attempts=AGENT[s], judge=judge, condition=cond, group=grp, n=len(g), rejected=int((g.verdict == "fail").sum())))
I = pd.DataFrame(inf); I["discovery"] = I.rejected / I.n
I.to_csv(OUT / "ow_inferability.csv", index=False)
for r in I.itertuples():
    add(f"eg_{r.group}_{r.judge}_on_{r.attempts}_{r.condition}".replace(" ", ""), f"{r.rejected}/{r.n}",
        f"{r.group.replace('_', ' ')} evidence-gathering errors rejected, {r.judge} judge on {r.attempts} attempts, {r.condition}", "Fig. 2")

TRAJ = [("gptoss", "GPT-OSS"), ("gptoss", "Qwen"), ("qwen", "Qwen"), ("qwen", "GPT-OSS"), ("gptoss2", "Qwen")]
groups = {"name_fa": ("task1", "false_absence", "patient-name false absences (task category 1)"),
          "k_fa": ("task9", "false_absence", "potassium false absences (task category 9)"),
          "t7_ir": ("task7", "incomplete_retrieval", "latest-glucose incomplete retrievals (task category 7)"),
          "t6_ir": ("task6", "incomplete_retrieval", "mean-glucose incomplete retrievals (task category 6)"),
          "t6_other": ("task6", "answer_error_other", "mean-glucose other answer errors (task category 6)"),
          "bp_correct": ("task3", "(correct work)", "correct blood-pressure recordings (task category 3)"),
          "ref_correct": ("task8", "(correct work)", "correct referrals (task category 8)")}
for g, (cat, mech, lab) in groups.items():
    for cond in SUFFIX:
        for s, judge in TRAJ:
            if (s, judge, cond) not in V:
                continue
            rej, n = det_of(s, judge, cond, cat, mech)
            if n:
                add(f"{g}_{judge}_on_{s}_{cond}", f"{rej}/{n}", f"{lab}: rejected/total, {judge} judge on {AGENT[s]} attempts, {cond}", "5.5-5.6")
for s, judge in TRAJ:
    r = D[(D.attempts == AGENT[s]) & (D.judge == judge) & (D.condition == "neutral") & (D.mechanism == "incomplete_retrieval")]
    add(f"ir_all_{judge}_on_{s}_neutral", f"{int(r.rejected.sum())}/{int(r.n.sum())}",
        f"incomplete retrievals, all task categories: rejected/total, {judge} judge on {AGENT[s]} attempts, neutral", "5.5")
tot = [det_of(s, j, "neutral", "task1", "false_absence") for s, j in TRAJ]
add("name_fa_traj_only_new_total", f"{sum(r for r, _ in tot)}/{sum(n for _, n in tot)}",
    "patient-name false absences rejected/total over the five open-weight trajectory-only cells", "5.5")

# ---- rationale keywords (automated keyword match, not hand coding)
KW = {"local_code": r"(?<![A-Za-z0-9])['\"`]?K['\"`]?(?![A-Za-z0-9+])|local code",
      "pages": r"page|pagina|\bnext\b|truncat",
      "fhir_convention": r"component|valueString|LOINC|best practice|standard FHIR|FHIR standard"}
rat = []
for (s, judge, cond), v in V.items():
    for g, (cat, mech, kw, verdict) in {"k_fa": ("task9", "false_absence", "local_code", "fail"),
                                        "ir": (None, "incomplete_retrieval", "pages", "fail"),
                                        "bp_correct": ("task3", None, "fhir_convention", "fail")}.items():
        sub = v[v.verdict == verdict]
        sub = sub[sub.truth == ("correct" if mech is None else "error")]
        if cat:
            sub = sub[sub.category == cat]
        if mech:
            sub = sub[sub.mechanism == mech]
        if len(sub):
            hit = sub.text.str.contains(KW[kw], regex=True, flags=re.I if kw != "local_code" else 0)
            rat.append(dict(attempts=AGENT[s], judge=judge, condition=cond, group=g, keyword=kw, rejections=len(sub), matches=int(hit.sum())))
RT = pd.DataFrame(rat)
RT.to_csv(OUT / "ow_rationales.csv", index=False)

# reasons behind rejections of patient-name false absences: answer format vs. the search / the existing patient
FMT, FOUND = r"array|plain string|format|JSON", r"given|family|full name|name parameter|split|separate|\bexists?\b|found the patient|MRN|S\d{5,}"
for (s, judge, cond), v in V.items():
    rej = v[(v.category == "task1") & (v.mechanism == "false_absence") & (v.truth == "error") & (v.verdict == "fail")]
    if len(rej):
        fmt_only = rej.text.str.contains(FMT, case=False) & ~rej.text.str.contains(FOUND, case=False)
        add(f"name_fa_reason_{judge}_on_{s}_{cond}", f"format only {int(fmt_only.sum())}; search or existing patient "
            f"{int(rej.text.str.contains(FOUND, case=False).sum())}; of {len(rej)}",
            f"rejections of patient-name false absences by reason (keyword match), {judge} judge on {AGENT[s]} attempts, {cond}", "5.6")
# the API specification's effect on the GPT-OSS judge without task category 1
for cond in ["neutral", "spec"]:
    v = V[("gptoss", "GPT-OSS", cond)]
    e = v[(v.truth == "error") & (v.category != "task1")]
    add(f"gptoss_selfjudge_{cond}_discovery_without_task1", f"{int((e.verdict == 'fail').sum())}/{len(e)}",
        f"GPT-OSS judge on own attempts, {cond}: errors rejected outside task category 1", "5.6")
for r in RT[RT.condition == "neutral"].itertuples():
    add(f"rationale_{r.group}_{r.judge}_on_{r.attempts}".replace(" ", ""), f"{r.matches}/{r.rejections}",
        f"neutral {r.judge} judge on {r.attempts} attempts: rejections of {r.group} whose rationale matches '{r.keyword}'", "5.5")

# ---- cross-judged sets (identical attempts, neutral prompt)
xrows = []
for s, a, b in [("gptoss", "GPT-OSS", "Qwen"), ("qwen", "Qwen", "GPT-OSS")]:
    va, vb = V[(s, a, "neutral")], V[(s, b, "neutral")]
    k = va.index.intersection(vb.index)
    P = va.loc[k, ["category", "mechanism", "truth"]].copy()
    P["a"], P["b"] = va.loc[k, "verdict"], vb.loc[k, "verdict"]
    P["err_a"] = (P.a == "pass") != (P.truth == "correct"); P["err_b"] = (P.b == "pass") != (P.truth == "correct")
    E, Cc = P[P.truth == "error"], P[P.truth == "correct"]
    for (cat, mech), g in E.groupby(["category", "mechanism"]):
        xrows.append(dict(attempts=AGENT[s], judge_self=a, judge_cross=b, group="error", category=cat, mechanism=mech, n=len(g),
                          self_wrong=int((g.a == "pass").sum()), cross_wrong=int((g.b == "pass").sum()),
                          both_wrong=int(((g.a == "pass") & (g.b == "pass")).sum())))
    for cat, g in Cc.groupby("category"):
        xrows.append(dict(attempts=AGENT[s], judge_self=a, judge_cross=b, group="correct", category=cat, mechanism="", n=len(g),
                          self_wrong=int((g.a == "fail").sum()), cross_wrong=int((g.b == "fail").sum()),
                          both_wrong=int(((g.a == "fail") & (g.b == "fail")).sum())))

    def kap(d):
        pa, pb = d.err_a.mean(), d.err_b.mean(); po = (d.err_a == d.err_b).mean(); pe = pa * pb + (1 - pa) * (1 - pb)
        return (po - pe) / (1 - pe)
    both_acc = (E.a == "pass") & (E.b == "pass")
    sa = f"{AGENT[s]}"
    add(f"x_{s}_n_pairs", len(P), f"cross-judged {sa} attempts with valid verdicts from both judges", "5.7")
    add(f"x_{s}_joint_acceptance", round(both_acc.mean(), 3), f"{sa} attempts: share of errors accepted by both judges", "5.7")
    add(f"x_{s}_joint_accepted_n", f"{int(both_acc.sum())}/{len(E)}", f"{sa} attempts: errors accepted by both judges", "5.7")
    t1 = (E.category == "task1") & (E.mechanism == "false_absence")
    add(f"x_{s}_joint_accepted_name_fa", f"{int((both_acc & t1).sum())}/{int(both_acc.sum())}",
        f"{sa} attempts: patient-name false absences among errors accepted by both judges", "5.7")
    nt1 = P[P.category != "task1"]; Ent1 = nt1[nt1.truth == "error"]
    add(f"x_{s}_joint_acceptance_without_task1", round(((Ent1.a == "pass") & (Ent1.b == "pass")).mean(), 3),
        f"{sa} attempts: joint acceptance of errors outside task category 1", "5.7")
    add(f"x_{s}_kappa_without_task1", round(kap(nt1), 3), f"{sa} attempts: kappa on judge errors outside task category 1", "5.7")
    add(f"x_{s}_union_discovery", round(1 - both_acc.mean(), 3), f"{sa} attempts: errors rejected by at least one judge", "5.7")
    add(f"x_{s}_best_single_discovery", round(max((E.a == "fail").mean(), (E.b == "fail").mean()), 3),
        f"{sa} attempts: error discovery of the better single judge", "5.7")
    both_rej = (Cc.a == "fail") & (Cc.b == "fail")
    add(f"x_{s}_shared_false_rejections_bp", f"{int((both_rej & (Cc.category == 'task3')).sum())}/{int(both_rej.sum())}",
        f"{sa} attempts: correct blood-pressure recordings among correct attempts rejected by both judges", "5.7")
    add(f"x_{s}_name_fa_share_of_errors", f"{int(t1.sum())}/{len(E)}", f"{sa} attempts: patient-name false absences among judged errors", "5.7")
    for j, col in [(a, "a"), (b, "b")]:
        add(f"x_{s}_{j}_error_acceptance", f"{int((E[col] == 'pass').sum())}/{len(E)}", f"{j} judge: errors accepted on {sa} attempts", "5.7")
X = pd.DataFrame(xrows)
X.to_csv(OUT / "ow_cross_judge.csv", index=False)

# ---- agents: outcomes, loci, provenance, bimodality, first queries, probes, cue
for s, run in SETS.items():
    m = M[s].reset_index()
    sj = json.loads((RUNS / run / "09_analysis/outputs/summary.json").read_text(encoding="utf-8"))
    add(f"{s}_official_success", round(sj["official_pass_rate"], 3), f"{AGENT[s]}: official success rate", "5.2")
    e = m[m.refined_class.isin(DESCR)]
    add(f"{s}_substantive_errors", len(e), f"{AGENT[s]}: substantive errors incl. wrong order", "5.1")
    for l, g in e.groupby("locus"):
        add(f"{s}_{l}_per100", round(100 * len(g) / len(m), 1), f"{AGENT[s]}: {l} errors per 100 attempts", "5.2")
        add(f"{s}_{l}_share", round(len(g) / len(e), 3), f"{AGENT[s]}: share of substantive errors at locus {l}", "5.1")
    for (l, mech), g in e.groupby(["locus", "mechanism"], dropna=False):
        add(f"{s}_mech_{l}_{mech}", len(g), f"{AGENT[s]}: substantive errors, {l} / {mech}", "Table 3")
    for cat, g in e.groupby("category"):
        add(f"{s}_errors_{cat}", len(g), f"{AGENT[s]}: substantive errors in task category {cat}", "5.1")
    pv = pd.read_csv(RUNS / run / "derived/provenance_coding.csv")
    pv = pv[pv.outcome_class.isin(DESCR)]
    for p, g in pv.groupby("provenance"):
        add(f"{s}_prov_{p}", len(g), f"{AGENT[s]}: provenance {p}", "Table 3")
    na = pv.basis.str.startswith("order specification")
    add(f"{s}_prov_not_applicable", int((pv.provenance.eq("unclassified") & na).sum()),
        f"{AGENT[s]}: unclassified because provenance is not applicable (order specification)", "Table 3, 5.1")
    tk = m.groupby("task_id").official_pass.mean()
    add(f"{s}_all_or_nothing_tasks", int(((tk == 0) | (tk == 1)).sum()), f"{AGENT[s]}: tasks on which all four attempts passed or all failed", "5.1")
    fq = pd.read_csv(RUNS / run / "derived/first_query_codes.csv")
    k = fq[(fq.run == MAIN) & (fq.category == "task9")]
    add(f"{s}_first_query_K", f"{int(k.used_given.sum())}/{len(k)}", f"{AGENT[s]}: first in-task potassium query used local code K", "5.2")
    pr = pd.read_csv(RUNS / run / "09_analysis/outputs/probes_summary.csv")
    acc = {(r.source.endswith("controls.jsonl"), r.family): r.accuracy for r in pr.itertuples()}
    add(f"{s}_probe_absence_J", round(acc[(False, "absence")] + acc[(True, "absence")] - 1, 3),
        f"{AGENT[s]} agent: absence probes, J against valid empty queries", "5.2")
    add(f"{s}_probe_completeness_J", round(acc[(False, "completeness")] + acc[(True, "completeness")] - 1, 3),
        f"{AGENT[s]} agent: completeness probes, J against complete single pages", "5.2")
    ce = pd.read_csv(RUNS / run / "09_analysis/outputs/cue_effects.csv").set_index("measure")
    for meas in ["official_pass", "evidence_gathering", "conclusion", "action"]:
        r = ce.loc[meas]
        add(f"{s}_cue_{meas}", f"{r.baseline:.2f} to {r.cue:.2f}; {r.difference:+.2f} [{r.lo:.2f}, {r.hi:.2f}]",
            f"{AGENT[s]}: verification cue on {int(r.n_tasks)} tasks, {meas} per attempt", "5.2")
    cue = pd.read_csv(RUNS / run / "derived/cue_deepseekv32_mechanisms.csv")
    base = m[m.task_id.isin(set(cue.task_id))]
    for cls in ["format_only", "no_finish"]:
        add(f"{s}_cue_share_{cls}", f"{(base.refined_class == cls).mean():.3f} to {(cue.refined_class == cls).mean():.3f}",
            f"{AGENT[s]}: share of {cls} attempts on cue tasks, baseline to cue", "5.2")
    ctl = pd.read_csv(RUNS / run / "09_analysis/outputs/controls.csv")
    for r in ctl[ctl.condition == "neutral"].itertuples():
        add(f"{s}_control_{r.run}_accepted", round(r.acceptance_rate, 3), f"{AGENT[s]} run judge, neutral: acceptance of {r.run}", "Table 5")
        add(f"{s}_control_{r.run}_grader", round(r.official_pass_rate, 3), f"rule-based grader: pass rate of {r.run}", "Table 5")

# ---- record access: did the judge use its access? (n_queries per verdict, last row per attempt)
for (s, judge, cond), v in V.items():
    if cond != "record_access":
        continue
    q = pd.DataFrame([dict(task_id=r["task_id"], attempt=int(r["attempt"]), nq=r.get("n_queries") or 0) for r in read_jsonl(PATH[(s, judge, cond)])])
    q = q.drop_duplicates(["task_id", "attempt"], keep="last").set_index(["task_id", "attempt"]).join(v[["category", "mechanism", "truth"]], how="inner")
    add(f"access_{judge}_on_{s}_mean_queries", round(q.nq.mean(), 2), f"record access, {judge} judge on {AGENT[s]} attempts: GET queries per verdict", "5.6")
    add(f"access_{judge}_on_{s}_no_query", round((q.nq == 0).mean(), 3), f"record access, {judge} judge on {AGENT[s]} attempts: share of verdicts without any query", "5.6")
    t6 = q[(q.category == "task6") & (q.mechanism == "incomplete_retrieval") & (q.truth == "error")]
    add(f"access_{judge}_on_{s}_t6_ir_no_query", f"{int((t6.nq == 0).sum())}/{len(t6)}",
        f"record access, {judge} judge on {AGENT[s]} attempts: mean-glucose incomplete retrievals judged without any query", "5.6")

# ---- verdict counts (all judge files of the open-weight runs and the cross-judge run)
def n_judged(f):
    """Judged attempts in one verdict file; retries append rows, so count each attempt once."""
    return len({(r["task_id"], r["attempt"]) for r in read_jsonl(f)})


nv = sum(n_judged(f) for run in SETS.values() for f in (RUNS / run / "mab_runs").rglob("judge_*.jsonl")
         if "request_errors" not in f.name)
nx = sum(n_judged(f) for f in CROSS.rglob("judge_*.jsonl"))
add("verdicts_open_weight_runs", nv, "model-judge verdicts in the three open-weight runs (all conditions, incl. controls)", "1, 4.3")
add("verdicts_cross_judge", nx, "model-judge verdicts in the cross-judge run", "4.3")
for s, run in SETS.items():
    add(f"verdicts_{s}", sum(n_judged(f) for f in (RUNS / run / "mab_runs").rglob("judge_*.jsonl")
                             if "request_errors" not in f.name),
        f"model-judge verdicts in the {AGENT[s]} run (all conditions, incl. controls)", "1, 4.3 (v5)")

# ---- Figure 1 rows (judge_conditions_summary.csv format)
COND = {"neutral": "Trajectory only", "spec": "+ API specification", "checklist": "+ verification checklist",
        "record_access": "+ read-only EHR access"}
AGN = {"GPT-OSS": "GPT-OSS-120B", "GPT-OSS (run 2)": "GPT-OSS-120B (run 2)", "Qwen": "Qwen3.8-27B"}
JN = {"GPT-OSS": "GPT-OSS-120B", "Qwen": "Qwen3.8-27B"}
fr = []
for r in C.itertuples():
    jp = np.nan
    if r.condition == "record_access":
        s = {v: k for k, v in AGENT.items()}[r.attempts]
        base, acc_ = V[(s, r.judge, "neutral")], V[(s, r.judge, "record_access")]
        jp = j_of(base.loc[base.index.intersection(acc_.index)])
    fr.append(dict(cond=COND[r.condition], judge=JN[r.judge], agent=AGN[r.attempts], pairing=r.pairing, n_c=r.n_correct,
                   n_g=r.n_errors, pc=round(r.correct_accepted, 3), pg=round(r.errors_accepted, 3), J=r.J, lo=r.J_lo, hi=r.J_hi, J_paired=jp))
pd.DataFrame(fr).to_csv(OUT / "ow_fig1_rows.csv", index=False)

pd.DataFrame(NUM).to_csv(OUT / "ow_numbers.csv", index=False)
print(f"a15: {len(NUM)} numbers, {len(C)} judge cells -> {OUT}")
