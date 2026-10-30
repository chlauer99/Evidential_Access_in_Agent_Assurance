"""Judge experiment report: assurance profiles, discrimination and reason validity.

Inputs  : mab_runs/<agent_run>/judge_<judge>.jsonl (from judge_runs.py) and the regraded outcome classes
          from analyse_pilot.classify_failures (via analyse_judges.codes_for).
Outputs : mab_runs/judge_attempts.csv        one row per (agent run, attempt, judge condition)
          mab_runs/judge_summary.csv         pass rates by outcome class with task-clustered bootstrap CIs
          mab_runs/judge_discrimination.csv  Youden J and confidence AUROC (correct vs grounded error)
          mab_runs/judge_reason_validity.csv judge fails on grounded errors: does the rationale name the mechanism?

Truth classes: 'correct' = official pass; 'format_only' = right values in a form the grader rejects;
'grounded_error' = substantive answer error, omission or commission (validated against the FHIR server).
Controls: 'replay' = reference answers with no visible retrieval; 'do_nothing' = agent that finishes at once.
"""
from __future__ import annotations

import json, re, runpy
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm_config as _llm  # reproducibility package: configurable endpoint/paths (protocol unchanged)
RUNS = _llm.runs_dir(ROOT / "mab_runs")
aj = runpy.run_path(str(HERE / "analyse_judges.py"), run_name="aj")

AGENTS = {"pilot_gpt41": "gpt-4.1", "pilot_gpt41mini": "gpt-4.1-mini", "full_deepseekv32": "deepseek-v3.2"}
JUDGES = ["gpt-4.1", "gpt-4.1-mini", "gpt-4.1_spec", "gpt-4.1-mini_spec", "deepseek-v3.2", "deepseek-v3.2_verify", "deepseek-v3.2_access"]
LINEAGE = {"gpt-4.1": "openai", "gpt-4.1-mini": "openai", "deepseek-v3.2": "deepseek"}
GROUNDED = {"substantive_answer_error", "omission", "commission"}

# A judge fail on a grounded error counts as reason-valid only if its rationale names the actual mechanism.
VALID_REASON = {
    "false absence": r"LOINC|2823|\bcode\b|search term|query (?:term|code|parameter)|wrong (?:code|query|search)",
    "incomplete retrieval": r"\bpage|paginat|\bnext\b|first \d+|only \d+ (?:results|entries|observations)|not all (?:results|observations)|additional (?:results|pages)|more results|truncat",
    "time-window error": r"(?:24|window|outside).*(?:-1|no (?:recent|value|result))|(?:-1|no (?:recent|value|result)).*(?:24|window|outside)",
    "computation error": r"\b245(?:\.0)?\b|miscalculat|arithmetic|incorrect(?:ly)? (?:calculated|computed)|birthday|has not (?:yet )?had",
    "no action on detected absence": r"(?:order|ordered|place).*(?:A1C|HbA1c|hemoglobin a1c|lab)|(?:A1C|HbA1c).*(?:order|should)",
    "unnecessary order": r"unnecessar|not (?:needed|required|indicated)|no new (?:test|lab|order)[^.]*needed|less than (?:1|one) year|already|recent (?:A1C|HbA1c|result|value)|within (?:the )?(?:last )?(?:year|12 months)|should not have|contrary to",
}


def load(run, judge):
    return aj["load_judge"](run, judge)


def attempts():
    rows = []
    for run, agent in AGENTS.items():
        codes = aj["codes_for"](run)
        for judge in JUDGES:
            j = load(run, judge)
            for (t, a), r in codes.items():
                v = j.get((t, a))
                if v is None:
                    continue
                c = r["failure_type_refined"]
                truth = ("correct" if c == "pass" else "format_only" if c == "format_only"
                         else "grounded_error" if c in GROUNDED else c)
                rows.append({"agent_run": run, "agent": agent, "judge": judge, "task_id": t, "attempt": str(a),
                             "cls": c, "truth": truth, "mechanism": aj["MECH"].get((t, c), ""),
                             "verdict": v["verdict"], "judge_pass": v["verdict"] == "pass",
                             "confidence": float(v.get("confidence") or 0), "issue_type": v.get("issue_type"),
                             "rationale": v.get("rationale") or ""})
    for run, truth in (("control_replay", "replay"), ("control_null", "do_nothing")):
        res = {json.loads(l)["task_id"]: json.loads(l)["passed"]
               for l in (RUNS / run / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
        for judge in JUDGES:
            j = load(run, judge)
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


def cluster_boot(df, col="judge_pass", B=2000, seed=2026):
    """Mean of `col` with a 95% CI from resampling tasks (attempts within a task are not independent)."""
    if df.empty:
        return np.nan, np.nan, np.nan
    g = df.groupby("task_id")[col].agg(["sum", "count"])
    s, n = g["sum"].to_numpy(float), g["count"].to_numpy(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), size=(B, len(g)))
    boots = s[idx].sum(1) / n[idx].sum(1)
    return s.sum() / n.sum(), *np.percentile(boots, [2.5, 97.5])


def auroc(pos, neg):
    """P(score_correct > score_error) + 0.5 ties."""
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


def discrimination(A, B=2000, seed=2026):
    out = []
    for (run, judge), d in A[A.agent_run.isin(AGENTS)].groupby(["agent_run", "judge"]):
        d = d[d.truth.isin(["correct", "format_only", "grounded_error"])].copy()
        d["ok"] = d.truth != "grounded_error"                       # substantively correct
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
        out.append({"agent_run": run, "judge": judge,
                    "pairing": ("self" if judge.split("_")[0] == AGENTS[run] else
                                "same-lineage" if LINEAGE[judge.split("_")[0]] == LINEAGE[AGENTS[run]] else "cross-developer"),
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


if __name__ == "__main__":
    A = attempts(); A.to_csv(RUNS / "judge_attempts.csv", index=False)
    S = summary(A); S.to_csv(RUNS / "judge_summary.csv", index=False)
    D = discrimination(A); D.to_csv(RUNS / "judge_discrimination.csv", index=False)
    R = reason_validity(A); R.to_csv(RUNS / "judge_reason_validity.csv", index=False)
    print(A.groupby(["agent_run", "judge"]).size().to_string())
    print(D.to_string(index=False))
