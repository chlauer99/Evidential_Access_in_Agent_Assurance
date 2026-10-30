"""Cross-judge analysis (P5): two judges on the same saved attempts.

Each attempt set is judged by the agent's own model (verdicts from the source run) and by the other
model (verdicts from the cross-judge run). Neutral prompt, trajectory only.

Measures follow analysis/a07_error_dependence.py: Cohen's kappa on the indicator "verdict disagrees
with the reference standard", joint acceptance of the same substantive error, and error acceptance by
agent x judge (self-preference). Truth classes, exclusions and intervals follow analyse_single.py:
wrong_order, do-nothing passes and unfinished attempts are excluded; pairs use attempts with valid
verdicts from both judges; 95% intervals from 1,000 task-cluster bootstrap draws, seed 2027.
"""
from __future__ import annotations
import argparse
from pathlib import Path

from analyse_single import MAIN, read_csv, read_jsonl, write_csv, key, truth, stats, interval


def verdicts(path, eligible):
    return {key(r): r["verdict"] for r in read_jsonl(path) if key(r) in eligible and r.get("verdict") in {"pass", "fail"}}


def kappa(rows):
    """Cohen's kappa on the two judges' error indicators."""
    if not rows:
        return None
    pa = sum(r["err_a"] for r in rows) / len(rows)
    pb = sum(r["err_b"] for r in rows) / len(rows)
    po = sum(r["err_a"] == r["err_b"] for r in rows) / len(rows)
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else (po - pe) / (1 - pe)


def joint_acceptance(rows):
    err = [r for r in rows if r["truth"] == "error"]
    return sum(r["a"] == "pass" and r["b"] == "pass" for r in err) / len(err) if err else None


def analyse(sets, out):
    cells, pairs = [], []
    for s in sets:
        eligible = {key(r): truth(r) for r in read_csv(s["mechanisms"]) if truth(r) != "excluded"}
        judged = {}
        for role in ("self", "cross"):
            j = s[role]
            judged[role] = verdicts(Path(j["verdicts"]), eligible)
            data = [dict(task_id=k[0], truth=eligible[k], verdict=v) for k, v in judged[role].items()]
            d = dict(attempts=s["name"], agent=s["agent"], judge=j["model"], relation=role,
                     eligible=len(eligible), valid_verdicts=len(data),
                     n_errors=sum(r["truth"] == "error" for r in data), n_correct=sum(r["truth"] == "correct" for r in data),
                     **stats(data))
            d["error_acceptance"] = None if d["error_discovery"] is None else 1 - d["error_discovery"]
            for metric in ("error_discovery", "correct_certification", "youden_j"):
                d[metric + "_lo"], d[metric + "_hi"] = interval(data, lambda x, m=metric: stats(x)[m])
            cells.append(d)
        keys = sorted(judged["self"].keys() & judged["cross"].keys())
        rows = []
        for k in keys:
            t, a, b = eligible[k], judged["self"][k], judged["cross"][k]
            ok = t == "correct"
            rows.append(dict(task_id=k[0], truth=t, a=a, b=b, err_a=(a == "pass") != ok, err_b=(b == "pass") != ok))
        both = [r for r in rows if r["err_a"] and r["err_b"]]
        pa = sum(r["err_a"] for r in rows) / len(rows)
        pb = sum(r["err_b"] for r in rows) / len(rows)
        k_lo, k_hi = interval(rows, kappa)
        j_lo, j_hi = interval(rows, joint_acceptance)
        pairs.append(dict(attempts=s["name"], judge_a=s["self"]["model"], judge_b=s["cross"]["model"], n_pairs=len(rows),
                          n_errors=sum(r["truth"] == "error" for r in rows),
                          err_a=pa, err_b=pb, both_wrong=len(both) / len(rows), both_wrong_if_indep=pa * pb,
                          kappa_errors=kappa(rows), kappa_lo=k_lo, kappa_hi=k_hi,
                          joint_acceptance=joint_acceptance(rows), joint_acceptance_lo=j_lo, joint_acceptance_hi=j_hi,
                          p_b_wrong_given_a_wrong=len(both) / sum(r["err_a"] for r in rows) if any(r["err_a"] for r in rows) else None))
    write_csv(out / "agent_judge_cells.csv", cells, list(cells[0]))
    write_csv(out / "judge_error_dependence.csv", pairs, list(pairs[0]))
    report = ["# Cross-judge analysis (P5)", "",
              "Two judges on the same saved attempts; neutral prompt, trajectory only.",
              "Errors: substantive_answer_error, omission, commission. Correct: pass, format_only.",
              "Excluded: wrong_order, pass_without_acting, no_finish; invalid or missing verdicts.",
              "kappa: Cohen's kappa on 'verdict disagrees with the reference standard' (as in a07_error_dependence.py).",
              "Joint acceptance: share of substantive errors accepted by both judges.",
              "95% descriptive intervals: 1,000 task-cluster bootstrap draws, seed 2027; no multiplicity correction.",
              "Self-preference compares acceptance of own vs other model's errors on different attempt sets;",
              "differences in error mix between the agents are not controlled.", "",
              "Outputs: agent_judge_cells.csv, judge_error_dependence.csv."]
    (out / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Cross-judge analysis written to {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs-root", required=True, help="the runs/ folder")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    r = Path(a.runs_root)
    x = r / "cross_judge_exp_1"
    sets = [
        dict(name="gpt_oss_120b_exp_2", agent="openai/gpt-oss-120b",
             mechanisms=r / "gpt_oss_120b_exp_2/derived" / f"{MAIN}_mechanisms.csv",
             self=dict(model="openai/gpt-oss-120b", verdicts=r / "gpt_oss_120b_exp_2/mab_runs" / MAIN / "judge_gpt-oss-120b.jsonl"),
             cross=dict(model="Qwen/Qwen3.8-27B", verdicts=x / "on_gpt_oss_attempts/mab_runs" / MAIN / "judge_qwen3_8_27b.jsonl")),
        dict(name="qwen3_8_27b_exp_3", agent="Qwen/Qwen3.8-27B",
             mechanisms=r / "qwen3_8_27b_exp_3/derived" / f"{MAIN}_mechanisms.csv",
             self=dict(model="Qwen/Qwen3.8-27B", verdicts=r / "qwen3_8_27b_exp_3/mab_runs" / MAIN / "judge_qwen3_8_27b.jsonl"),
             cross=dict(model="openai/gpt-oss-120b", verdicts=x / "on_qwen_attempts/mab_runs" / MAIN / "judge_gpt-oss-120b.jsonl")),
    ]
    analyse(sets, Path(a.out))


if __name__ == "__main__":
    main()
