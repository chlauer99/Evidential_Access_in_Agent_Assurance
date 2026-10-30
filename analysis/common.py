"""Shared loaders and statistics for the Level A analyses.

Reconstructed from the code that produced the published tables (harness/mab_harness/judge_report.py,
analyse_judges.py and the analysis cells recorded in the study's lineage), rewritten to read the
archived files under data/ instead of a live FHIR server and a working directory.

Row order matters for the task-clustered bootstraps (the resampled task order follows first appearance),
so the loaders keep the original order: pilot attempts in results.jsonl order, DeepSeek V3.2 attempts in
tracer output order (full_deepseekv32_mechanisms.csv), judge conditions in JUDGES order.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (AGENT_RUNS, DERIVED, GROUNDED, JUDGES, LINEAGE, OUT, RAW, SEED_JUDGE_REPORT, B_JUDGE,  # noqa: E402
                    SEED_PAIRED, B_PAIRED)

# Hand-traced mechanisms of the 30 pilot tasks (analyse_judges.MECH). The tracer reproduced these codes on all
# 197 non-passing pilot attempts.
MECH = {
    ("task4_29", "substantive_answer_error"): "time-window error",
    ("task6_27", "substantive_answer_error"): "computation error",
    ("task2_17", "substantive_answer_error"): "computation error",
    ("task7_16", "substantive_answer_error"): "incomplete retrieval",
    ("task7_19", "substantive_answer_error"): "incomplete retrieval",
    ("task9_4", "substantive_answer_error"): "false absence",
    ("task9_20", "substantive_answer_error"): "false absence",
    ("task9_3", "omission"): "false absence",
    ("task10_10", "omission"): "no action on detected absence",
    ("task10_4", "commission"): "unnecessary order",
}

# A judge fail on a substantive error counts as reason-valid only if its rationale names the actual mechanism.
VALID_REASON = {
    "false absence": r"LOINC|2823|\bcode\b|search term|query (?:term|code|parameter)|wrong (?:code|query|search)",
    "incomplete retrieval": r"\bpage|paginat|\bnext\b|first \d+|only \d+ (?:results|entries|observations)|not all (?:results|observations)|additional (?:results|pages)|more results|truncat",
    "time-window error": r"(?:24|window|outside).*(?:-1|no (?:recent|value|result))|(?:-1|no (?:recent|value|result)).*(?:24|window|outside)",
    "computation error": r"\b245(?:\.0)?\b|miscalculat|arithmetic|incorrect(?:ly)? (?:calculated|computed)|birthday|has not (?:yet )?had",
    "no action on detected absence": r"(?:order|ordered|place).*(?:A1C|HbA1c|hemoglobin a1c|lab)|(?:A1C|HbA1c).*(?:order|should)",
    "unnecessary order": r"unnecessar|not (?:needed|required|indicated)|no new (?:test|lab|order)[^.]*needed|less than (?:1|one) year|already|recent (?:A1C|HbA1c|result|value)|within (?:the )?(?:last )?(?:year|12 months)|should not have|contrary to",
}


# ----------------------------------------------------------------------------------------------- loaders
def read_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def load_judge(run, judge):
    """Valid verdicts (pass/fail) of one judge condition on one run, keyed by (task_id, attempt)."""
    f = RAW / run / f"judge_{judge}.jsonl"
    out = {}
    if f.exists():
        for r in read_jsonl(f):
            if r.get("verdict") in ("pass", "fail"):
                out[(r["task_id"], r["attempt"])] = r
    return out


def full_mechanisms():
    """Per-attempt tracer output for the DeepSeek V3.2 full run (1,200 attempts; API errors already removed)."""
    return pd.read_csv(DERIVED / "full_deepseekv32_mechanisms.csv")


def cue_mechanisms():
    return pd.read_csv(DERIVED / "cue_deepseekv32_mechanisms.csv")


def codes_for(run):
    """Server-regraded outcome class (analyse_pilot.classify_failures -> failure_type_refined) per attempt."""
    if run in ("pilot_gpt41", "pilot_gpt41mini"):
        d = pd.read_csv(DERIVED / "pilot_outcome_classes.csv")
        d = d[d.agent_run == run]
        return {(t, int(a)): {"failure_type_refined": c} for t, a, c in zip(d.task_id, d.attempt, d.cls)}
    if run == "full_deepseekv32":
        M = full_mechanisms()
        return {(t, int(a)): {"failure_type_refined": c} for t, a, c in zip(M.task_id, M.attempt, M.refined_class)}
    raise KeyError(run)


TRACER2HAND = {"false_absence": "false absence", "incomplete_retrieval": "incomplete retrieval",
               "time_window_error": "time-window error", "computation_error": "computation error",
               "unnecessary_order": "unnecessary order", "no_action_on_detected_absence": "no action on detected absence"}


def pilot_mechanisms(run):
    """Mechanism per pilot attempt. The paper used the hand-traced codes (MECH, keyed by task and class). A new run
    (Level B) has its own tracer table derived/<run>_mechanisms.csv, which then takes precedence."""
    f = DERIVED / f"{run}_mechanisms.csv"
    if run.startswith("pilot") and f.exists():
        d = pd.read_csv(f)
        return {(t, int(a)): TRACER2HAND.get(m, m if isinstance(m, str) else "") for t, a, m in zip(d.task_id, d.attempt, d.mechanism)}
    return None


def truth_of(c):
    return ("correct" if c == "pass" else "format_only" if c == "format_only"
            else "grounded_error" if c in GROUNDED else c)


def attempts(judges=JUDGES, runs=tuple(AGENT_RUNS), controls=True):
    """One row per (agent run, attempt, judge condition) -- judge_report.attempts()."""
    rows = []
    for run in runs:
        agent = AGENT_RUNS[run]
        codes = codes_for(run)
        pm = pilot_mechanisms(run)
        for judge in judges:
            j = load_judge(run, judge)
            for (t, a), r in codes.items():
                v = j.get((t, a))
                if v is None:
                    continue
                c = r["failure_type_refined"]
                rows.append({"agent_run": run, "agent": agent, "judge": judge, "task_id": t, "attempt": str(a),
                             "cls": c, "truth": truth_of(c),
                             "mechanism": (pm.get((t, a), "") if c in GROUNDED else "") if pm is not None else MECH.get((t, c), ""),
                             "verdict": v["verdict"], "judge_pass": v["verdict"] == "pass",
                             "confidence": float(v.get("confidence") or 0), "issue_type": v.get("issue_type"),
                             "rationale": v.get("rationale") or ""})
    if controls:
        for run, truth in (("control_replay", "replay"), ("control_null", "do_nothing")):
            res = {r["task_id"]: r["passed"] for r in read_jsonl(RAW / run / "results.jsonl")}
            for judge in judges:
                j = load_judge(run, judge)
                for t, p in res.items():
                    v = j.get((t, 0)) or j.get((t, "0"))
                    if v is None:
                        continue
                    rows.append({"agent_run": run, "agent": run, "judge": judge, "task_id": t, "attempt": "0",
                                 "cls": "grader_pass" if p else "grader_fail", "truth": truth, "mechanism": "",
                                 "verdict": v["verdict"], "judge_pass": v["verdict"] == "pass",
                                 "confidence": float(v.get("confidence") or 0), "issue_type": v.get("issue_type"),
                                 "rationale": v.get("rationale") or ""})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------------------------- statistics
def cluster_boot(df, col="judge_pass", B=B_JUDGE, seed=SEED_JUDGE_REPORT):
    """Mean of `col` with a 95% CI from resampling tasks."""
    if df.empty:
        return np.nan, np.nan, np.nan
    g = df.groupby("task_id")[col].agg(["sum", "count"])
    s, n = g["sum"].to_numpy(float), g["count"].to_numpy(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), size=(B, len(g)))
    boots = s[idx].sum(1) / n[idx].sum(1)
    return s.sum() / n.sum(), *np.percentile(boots, [2.5, 97.5])


def auroc(pos, neg):
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    return ((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def summary(A):
    out = []
    for (run, judge), d in A.groupby(["agent_run", "judge"]):
        for truth, dd in d.groupby("truth"):
            m, lo, hi = cluster_boot(dd)
            out.append({"agent_run": run, "judge": judge, "truth": truth, "n_attempts": len(dd),
                        "n_tasks": dd.task_id.nunique(), "judge_pass_rate": round(m, 3),
                        "ci_lo": round(lo, 3), "ci_hi": round(hi, 3)})
        for mech, dd in d[d.truth == "grounded_error"].groupby("mechanism"):
            m, lo, hi = cluster_boot(dd)
            out.append({"agent_run": run, "judge": judge, "truth": f"grounded_error: {mech}", "n_attempts": len(dd),
                        "n_tasks": dd.task_id.nunique(), "judge_pass_rate": round(m, 3),
                        "ci_lo": round(lo, 3), "ci_hi": round(hi, 3)})
    return pd.DataFrame(out)


def discrimination(A, B=B_JUDGE, seed=SEED_JUDGE_REPORT):
    """Youden J and confidence AUROC (substantively correct vs substantive error), task-clustered CIs."""
    out = []
    for (run, judge), d in A[A.agent_run.isin(AGENT_RUNS)].groupby(["agent_run", "judge"]):
        d = d[d.truth.isin(["correct", "format_only", "grounded_error"])].copy()
        d["ok"] = d.truth != "grounded_error"
        d["score"] = np.where(d.judge_pass, d.confidence, 100 - d.confidence)
        J = d[d.ok].judge_pass.mean() - d[~d.ok].judge_pass.mean()
        auc = auroc(d[d.ok].score, d[~d.ok].score)
        tasks = d.task_id.unique(); rng = np.random.default_rng(seed); Js, aucs = [], []
        groups = {t: g for t, g in d.groupby("task_id")}
        for _ in range(B):
            s = pd.concat([groups[t] for t in rng.choice(tasks, len(tasks))])
            if s.ok.all() or (~s.ok).all():
                continue
            Js.append(s[s.ok].judge_pass.mean() - s[~s.ok].judge_pass.mean())
            aucs.append(auroc(s[s.ok].score, s[~s.ok].score))
        base = judge.split("_")[0]
        out.append({"agent_run": run, "judge": judge,
                    "pairing": ("self" if base == AGENT_RUNS[run] else
                                "same-lineage" if LINEAGE[base] == LINEAGE[AGENT_RUNS[run]] else "cross-developer"),
                    "spec_shown": judge.endswith("_spec"), "n_correct": int(d.ok.sum()), "n_grounded_error": int((~d.ok).sum()),
                    "pass_if_correct": round(d[d.ok].judge_pass.mean(), 3),
                    "pass_if_grounded_error": round(d[~d.ok].judge_pass.mean(), 3),
                    "youden_J": round(J, 3),
                    "J_lo": round(np.percentile(Js, 2.5), 3) if Js else np.nan,
                    "J_hi": round(np.percentile(Js, 97.5), 3) if Js else np.nan,
                    "conf_auroc": round(auc, 3),
                    "auroc_lo": round(np.nanpercentile(aucs, 2.5), 3) if aucs else np.nan,
                    "auroc_hi": round(np.nanpercentile(aucs, 97.5), 3) if aucs else np.nan})
    return pd.DataFrame(out)


def reason_validity(A):
    d = A[(A.truth == "grounded_error") & (~A.judge_pass)].copy()
    d["reason_valid"] = [bool(re.search(VALID_REASON.get(m, r"$^"), r, re.I | re.S)) for m, r in zip(d.mechanism, d.rationale)]
    return d[["agent_run", "judge", "task_id", "attempt", "mechanism", "issue_type", "reason_valid", "rationale"]]


def _task_sums(d, cols):
    """Per-task counts and sums of boolean columns for the correct and error classes (first-appearance task order)."""
    tasks = d.task_id.unique()
    pos = {t: i for i, t in enumerate(tasks)}
    ti = d.task_id.map(pos).to_numpy()
    isc = (d.cls == "correct").to_numpy()
    nc = np.bincount(ti[isc], minlength=len(tasks)).astype(float)
    ne = np.bincount(ti[~isc], minlength=len(tasks)).astype(float)
    sc = {c: np.bincount(ti[isc], weights=d[c].to_numpy(float)[isc], minlength=len(tasks)) for c in cols}
    se = {c: np.bincount(ti[~isc], weights=d[c].to_numpy(float)[~isc], minlength=len(tasks)) for c in cols}
    return tasks, nc, ne, sc, se


def record_access_rng():
    """Random generator of the published record-access bootstraps.

    In the original analysis session, the record-access J intervals (agentic_judge_discrimination.csv, then
    agentic_judge_readonly.csv, and the access rows of judge_conditions_summary.csv) were drawn from the generator
    created as default_rng(2026) for the verification-cue bootstrap, i.e. after 6 x 4,000 draws of
    rng.integers(0, n, n) with n = number of cue tasks per category (all, task1, task4, task6, task7, task9).
    Replaying those draws reproduces the published intervals exactly."""
    from config import SEED_CUE, B_CUE
    rng = np.random.default_rng(SEED_CUE)
    CU = cue_mechanisms()
    tids = sorted(CU.task_id.unique())
    for cat in ["all"] + sorted(CU.category.unique()):
        n = len(tids) if cat == "all" else sum(t.startswith(cat + "_") for t in tids)
        for _ in range(B_CUE):
            rng.integers(0, n, n)
    return rng


def make_boot_J(rng):
    """Task-clustered bootstrap of J = pass(correct) - pass(error) with a shared generator (record-access tables).

    Equivalent to the published implementation (resample tasks with rng.choice(tasks, n), concatenate, take means)
    but computed from per-task sums: the generator draws the same indices, and the means are the same ratios of
    integer counts, so the percentiles are identical."""
    def boot_J(d, col, B=4000):
        tasks, nc, ne, sc, se = _task_sums(d, [col])
        out = []
        for _ in range(B):
            idx = rng.choice(len(tasks), len(tasks))
            n1, n2 = nc[idx].sum(), ne[idx].sum()
            if n1 and n2:
                out.append(sc[col][idx].sum() / n1 - se[col][idx].sum() / n2)
        return np.percentile(out, [2.5, 97.5])
    return boot_J


def paired(df, a, b, B=B_PAIRED, seed=SEED_PAIRED):
    """Paired contrast of two conditions on the same attempts: certification, discovery and J, with task-clustered CIs.
    Same draws as the published implementation (fresh generator, seed 7), computed from per-task sums."""
    rng_ = np.random.default_rng(seed)
    tasks, nc, ne, sc, se = _task_sums(df, [a, b])

    def st(idx):
        n1, n2 = nc[idx].sum(), ne[idx].sum()
        out = {}
        for col in (a, b):
            spec = sc[col][idx].sum() / n1; disc = 1 - se[col][idx].sum() / n2
            out[col] = (spec, disc, spec - (1 - disc))
        return out
    base_ = st(np.arange(len(tasks))); boots = []
    for _ in range(B):
        idx = rng_.choice(len(tasks), len(tasks))
        if nc[idx].sum() > 0 and ne[idx].sum() > 0:
            s_ = st(idx); boots.append([s_[b][k] - s_[a][k] for k in range(3)])
    boots = np.array(boots); lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)
    return dict(n_correct=int((df.cls == "correct").sum()), n_grounded=int((df.cls == "grounded").sum()),
                cert_a=base_[a][0], cert_b=base_[b][0], disc_a=base_[a][1], disc_b=base_[b][1], J_a=base_[a][2], J_b=base_[b][2],
                d_cert=base_[b][0] - base_[a][0], d_cert_lo=lo[0], d_cert_hi=hi[0], d_disc=base_[b][1] - base_[a][1],
                d_disc_lo=lo[1], d_disc_hi=hi[1], dJ=base_[b][2] - base_[a][2], dJ_lo=lo[2], dJ_hi=hi[2])


def kappa_err(d, a_, b_):
    pa, pb = d[a_].mean(), d[b_].mean(); po = (d[a_] == d[b_]).mean(); pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe)


# ----------------------------------------------------------------------------------------------- record access
def access_table(A):
    """Record-access sample (418 attempts) merged with the access verdicts, the neutral DeepSeek verdicts on the
    same attempts and the tracer mechanism (reconstruction of the published agentic_judge_verdicts.csv)."""
    M = full_mechanisms()
    base = A[A.judge == "deepseek-v3.2"].copy()
    base["attempt"] = base.attempt.astype(int)
    S = pd.DataFrame(json.load(open(RAW / "record_access" / "agentic_judge_sample.json", encoding="utf-8")))
    AC = pd.concat([pd.read_json(RAW / r / "judge_deepseek-v3.2_access.jsonl", lines=True).assign(run=r)
                    for r in S.run.unique()])
    AC["attempt"] = AC.attempt.astype(int)
    NE = base[["agent_run", "task_id", "attempt", "judge_pass", "truth", "mechanism"]].rename(
        columns={"agent_run": "run", "judge_pass": "neutral_pass"})
    X = (S.merge(AC[["run", "task_id", "attempt", "verdict", "n_queries", "queries", "rationale", "cost_usd"]],
                 on=["run", "task_id", "attempt"])
         .merge(NE, on=["run", "task_id", "attempt"], how="left"))
    X["access_pass"] = X.verdict.eq("pass"); X["neutral_pass"] = X.neutral_pass.astype(bool)
    X = X.merge(M[["task_id", "attempt", "mechanism"]].rename(columns={"mechanism": "tmech"}), on=["task_id", "attempt"], how="left")
    X["cls"] = np.where(X.stratum == "subst_correct", "correct", "grounded")
    X["mech"] = np.where(X.run == "full_deepseekv32", X.tmech, X.mechanism).astype(str)
    X["cat"] = X.task_id.str.split("_").str[0]
    return X


def pilot_wide(A):
    """Pilot attempts x judge conditions (bool accept), classifiable attempts only."""
    Wp = A[A.agent_run.isin(["pilot_gpt41", "pilot_gpt41mini"]) & A.truth.isin(["correct", "format_only", "grounded_error"])].copy()
    Wp["cls"] = np.where(Wp.truth == "grounded_error", "grounded", "correct"); Wp["judge_pass"] = Wp.judge_pass.astype(bool)
    return Wp.pivot_table(index=["agent_run", "task_id", "attempt", "cls"], columns="judge", values="judge_pass",
                          aggfunc="first").reset_index()


def write(df, name, **kw):
    p = OUT / name
    df.to_csv(p, **({"index": False} | kw))
    print(f"  wrote outputs/{name} ({len(df)} rows)")
    return p
