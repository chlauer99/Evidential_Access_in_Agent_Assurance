"""Single-model analysis independent of pilot files and paper-specific model comparisons.

Descriptive errors include wrong_order, as in manuscript Table 3.
Judge errors exclude wrong_order, as in manuscript Table 2.
Do-nothing passes and unfinished attempts are separately reported and excluded from judge
accuracy. Missing/invalid verdicts are reported, not silently scored as pass or fail.
Paired contrasts use the intersection of valid verdicts on the exact same attempts.
95% percentile intervals resample whole tasks (1,000 draws, seed 2027), not attempts.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import random
import statistics

import miniyaml

MAIN = "full_deepseekv32"
CUE = "cue_deepseekv32"
ERRORS = {"substantive_answer_error", "omission", "commission"}
DESCRIPTIVE_ERRORS = ERRORS | {"wrong_order"}
CORRECT = {"pass", "format_only"}
CONDITIONS = {"neutral": "", "spec": "_spec", "checklist": "_verify", "record_access": "_access"}


def read_csv(path):
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def key(r):
    return r["task_id"], int(r["attempt"])


def truth(r):
    c = r["refined_class"]
    return "error" if c in ERRORS else "correct" if c in CORRECT else "excluded"


def rate(n, d):
    return n / d if d else None


def truth_bool(value):
    return str(value).lower() in {"true", "1"}


def stats(rows):
    err = [r for r in rows if r["truth"] == "error"]
    cor = [r for r in rows if r["truth"] == "correct"]
    discovery = rate(sum(r["verdict"] == "fail" for r in err), len(err))
    certification = rate(sum(r["verdict"] == "pass" for r in cor), len(cor))
    return dict(error_discovery=discovery, correct_certification=certification,
                false_alarm_rate=None if certification is None else 1 - certification,
                youden_j=None if discovery is None or certification is None else discovery + certification - 1)


def interval(rows, measure):
    """Task-cluster bootstrap; unavailable with fewer than two independent tasks."""
    groups = defaultdict(list)
    for r in rows:
        groups[r["task_id"]].append(r)
    if len(groups) < 2:
        return None, None
    groups = list(groups.values())
    rng = random.Random(2027)
    values = []
    for _ in range(1000):
        sample = [r for g in rng.choices(groups, k=len(groups)) for r in g]
        v = measure(sample)
        if v is not None:
            values.append(v)
    if len(values) < 100:
        return None, None
    values.sort()
    return values[int(.025 * (len(values) - 1))], values[int(.975 * (len(values) - 1))]


def outcomes(rows):
    return dict(n_attempts=len(rows), n_tasks=len({r["task_id"] for r in rows}),
                official_pass_rate=rate(sum(truth_bool(r.get("official_pass")) for r in rows), len(rows)),
                substantive_error_rate=rate(sum(r["refined_class"] in DESCRIPTIVE_ERRORS for r in rows), len(rows)))


def analyse(config, raw, derived, out):
    out.mkdir(parents=True, exist_ok=True)
    model = config["models"][config["agents"][MAIN]["model"]]
    tag = next(iter(config["judges"]))
    rows = read_csv(derived / f"{MAIN}_mechanisms.csv")
    if not rows:
        raise ValueError("No main-run attempts to analyse")
    if len({key(r) for r in rows}) != len(rows):
        raise ValueError("Duplicate main-run attempts")
    counts = Counter(r["refined_class"] for r in rows)
    summary = dict(model=model["model"], **outcomes(rows), outcome_classes=dict(counts))
    results = read_jsonl(raw / MAIN / "results.jsonl")
    summary["api_error_records"] = sum(r.get("status") == "API_ERROR" for r in results)
    expected = config["agents"][MAIN]
    n_tasks = 300 if expected["tasks"] == "all" else len(expected["tasks"].split(","))
    summary["expected_attempts"] = n_tasks * expected["attempts"]
    summary["missing_attempts"] = max(0, summary["expected_attempts"] - len(rows))
    write_csv(out / "outcome_classes.csv", [dict(outcome=k, count=v) for k, v in sorted(counts.items())], ["outcome", "count"])
    mechanisms = Counter((r["locus"], r["mechanism"] or "unmapped") for r in rows if r["refined_class"] in DESCRIPTIVE_ERRORS)
    write_csv(out / "mechanisms.csv", [dict(locus=l, mechanism=m, count=n) for (l, m), n in sorted(mechanisms.items())],
              ["locus", "mechanism", "count"])
    provenance = Counter(r["provenance"] for r in read_csv(derived / "provenance_coding.csv")
                         if r.get("outcome_class") in DESCRIPTIVE_ERRORS)
    write_csv(out / "provenance_summary.csv", [dict(provenance=k, count=n) for k, n in sorted(provenance.items())], ["provenance", "count"])
    cat_rows = []
    for cat in sorted({r["category"] for r in rows}):
        cat_rows.append(dict(category=cat, **outcomes([r for r in rows if r["category"] == cat])))
    write_csv(out / "outcomes_by_category.csv", cat_rows,
              ["category", "n_attempts", "n_tasks", "official_pass_rate", "substantive_error_rate"])
    eligible = {key(r): r for r in rows if truth(r) != "excluded"}
    joined, summaries, maps, paired = [], [], {}, []
    for cond, suffix in CONDITIONS.items():
        source = {key(r): r for r in read_jsonl(raw / MAIN / f"judge_{tag}{suffix}.jsonl")}
        valid = {k: r for k, r in source.items() if k in eligible and r.get("verdict") in {"pass", "fail"}}
        maps[cond] = valid
        data = [dict(task_id=k[0], attempt=k[1], truth=truth(eligible[k]), verdict=r["verdict"]) for k, r in valid.items()]
        joined += [dict(condition=cond, **r) for r in data]
        d = dict(condition=cond, eligible=len(eligible), valid_verdicts=len(data),
                 missing_verdicts=sum(k not in source for k in eligible),
                 invalid_verdicts=sum(k in source and k not in valid for k in eligible),
                 n_errors=sum(r["truth"] == "error" for r in data), n_correct=sum(r["truth"] == "correct" for r in data),
                 **stats(data))
        for metric in ("error_discovery", "correct_certification", "youden_j"):
            d[metric + "_lo"], d[metric + "_hi"] = interval(data, lambda x, m=metric: stats(x)[m])
        summaries.append(d)
    for cond in CONDITIONS:
        if cond == "neutral":
            continue
        keys = sorted(maps["neutral"].keys() & maps[cond].keys())
        data = [dict(task_id=k[0], truth=truth(eligible[k]), baseline=maps["neutral"][k]["verdict"],
                     variant=maps[cond][k]["verdict"]) for k in keys]
        def metrics(ds, field):
            return stats([dict(r, verdict=r[field]) for r in ds])
        for metric in ("error_discovery", "correct_certification", "youden_j"):
            b, v = metrics(data, "baseline")[metric], metrics(data, "variant")[metric]
            def delta(ds, m=metric):
                x, y = metrics(ds, "baseline")[m], metrics(ds, "variant")[m]
                return None if x is None or y is None else y - x
            lo, hi = interval(data, delta)
            paired.append(dict(condition=cond, measure=metric, n_pairs=len(data), n_tasks=len({r['task_id'] for r in data}),
                               baseline=b, variant=v, difference=None if b is None or v is None else v-b, lo=lo, hi=hi))
    write_csv(out / "judge_attempts.csv", joined, ["condition", "task_id", "attempt", "truth", "verdict"])
    write_csv(out / "judge_summary.csv", summaries, list(summaries[0]))
    write_csv(out / "paired_conditions.csv", paired, ["condition", "measure", "n_pairs", "n_tasks", "baseline", "variant", "difference", "lo", "hi"])
    controls = []
    for run in config["controls"].get("judged", []):
        rs = {key(r): r for r in read_jsonl(raw / run / "results.jsonl") if r.get("status") != "API_ERROR"}
        for cond, suffix in CONDITIONS.items():
            if cond == "record_access":
                continue
            js = {key(r): r for r in read_jsonl(raw / run / f"judge_{tag}{suffix}.jsonl") if r.get("verdict") in {"pass", "fail"}}
            controls.append(dict(run=run, condition=cond, n_attempts=len(rs),
                                 official_pass_rate=rate(sum(bool(r.get("passed")) for r in rs.values()), len(rs)),
                                 n_verdicts=len(js), acceptance_rate=rate(sum(r["verdict"] == "pass" for r in js.values()),len(js))))
    write_csv(out / "controls.csv", controls, ["run", "condition", "n_attempts", "official_pass_rate", "n_verdicts", "acceptance_rate"])
    probes = []
    for filename in ("probes_deepseekv32.jsonl", "probes_deepseekv32_controls.jsonl"):
        groups = defaultdict(list)
        for r in read_jsonl(raw / "probes" / filename):
            groups[r["family"]].append(r)
        for family, group in sorted(groups.items()):
            probes.append(dict(source=filename, family=family, n_answers=len(group), accuracy=statistics.mean(bool(r["correct"]) for r in group)))
    write_csv(out / "probes_summary.csv", probes, ["source", "family", "n_answers", "accuracy"])
    cue_rows = []
    cue_path = derived / f"{CUE}_mechanisms.csv"
    if cue_path.exists():
        cue = read_csv(cue_path)
        tasks = {r["task_id"] for r in cue}
        baseline = [r for r in rows if r["task_id"] in tasks]
        for name, pred in [("official_pass", lambda r: truth_bool(r["official_pass"])),
                           ("evidence_gathering", lambda r: truth(r) == "error" and r["locus"] == "evidence_gathering"),
                           ("conclusion", lambda r: truth(r) == "error" and r["locus"] == "conclusion"), ("action", lambda r: truth(r) == "error" and r["locus"] == "action")]:
            paired_tasks = []
            for task in sorted(tasks):
                b = [pred(r) for r in baseline if r["task_id"] == task]
                v = [pred(r) for r in cue if r["task_id"] == task]
                if b and v:
                    paired_tasks.append(dict(task_id=task, baseline=statistics.mean(b), cue=statistics.mean(v), delta=statistics.mean(v)-statistics.mean(b)))
            if paired_tasks:
                lo, hi = interval(paired_tasks, lambda ds: statistics.mean(r["delta"] for r in ds))
                cue_rows.append(dict(measure=name, n_tasks=len(paired_tasks), baseline=statistics.mean(r['baseline'] for r in paired_tasks),
                                     cue=statistics.mean(r['cue'] for r in paired_tasks), difference=statistics.mean(r['delta'] for r in paired_tasks), lo=lo, hi=hi))
    write_csv(out / "cue_effects.csv", cue_rows, ["measure", "n_tasks", "baseline", "cue", "difference", "lo", "hi"])
    summary["cue_status"] = "analysed" if cue_rows else "not available / no eligible cue tasks"
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report = [f"# Single-model experiment: {model['name']}", "",
              f"Main run: {len(rows)} attempts, {summary['n_tasks']} tasks. Expected: {summary['expected_attempts']} attempts.",
              "No pilot data or cross-model comparisons are used.", "",
              "All four evidence conditions target the same completed main-run attempts; record access is not sampled by error type.",
              "Judge accuracy: pass/format_only = correct; substantive answer errors, omissions and commissions = errors.",
              "Wrong-order cases, do-nothing passes and unfinished attempts are excluded from judge accuracy but counted in outcome_classes.csv.",
              "Missing/invalid verdicts are reported per condition. Paired contrasts use only attempts valid in both conditions.",
              "95% descriptive intervals: 1,000 task-cluster bootstrap draws, seed 2027; no multiplicity correction.",
              "Descriptive outcomes, mechanisms, provenance and substantive error rates include wrong-order cases, as in manuscript Table 3. Only judge discrimination excludes them, as in Table 2.", "",
              "Outputs: outcome_classes.csv, outcomes_by_category.csv, mechanisms.csv, provenance_summary.csv,",
              "judge_attempts.csv, judge_summary.csv, paired_conditions.csv, controls.csv, probes_summary.csv, cue_effects.csv.", "",
              "Probe scores are descriptive; no between-model independence or capability comparisons are claimed.",
              "Cue results compare task-averaged rates on the selected tasks, not attempt-to-attempt pairs.",
              "The inherited tracer/provenance rules remain benchmark-specific; human validation is still needed."]
    (out / "report.md").write_text("\n".join(report)+"\n", encoding="utf-8")
    print(f"Single-model analysis written to {out}; {len(rows)} main attempts, no pilots")


def compare(out, target):
    summary = json.loads((out / "summary.json").read_text())
    archive = Path(__file__).resolve().parents[2] / "data/derived/full_deepseekv32_mechanisms.csv"
    reference = outcomes(read_csv(archive))
    target.mkdir(parents=True, exist_ok=True)
    rows = [dict(measure=k, current=summary[k], archived_deepseek=reference[k]) for k in reference]
    write_csv(target / "main_outcomes_comparison.csv", rows, ["measure", "current", "archived_deepseek"])
    (target / "compare_report.md").write_text(
        "# Descriptive main-run comparison\n\nOnly task/attempt counts, official pass rate and substantive error rate are compared with the archived DeepSeek full run.\n"
        "No pilot data, equality checks, paper-specific judge comparisons or cross-developer claims. Different model and reasoning settings prevent a controlled capability comparison.\n",
        encoding="utf-8")
    print(f"Descriptive comparison written to {target}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True)
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--derived", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--compare-out")
    a = ap.parse_args()
    if a.compare_out:
        compare(Path(a.out), Path(a.compare_out))
    else:
        analyse(miniyaml.load(Path(a.config)), Path(a.runs_dir), Path(a.derived), Path(a.out))


if __name__ == "__main__":
    main()
