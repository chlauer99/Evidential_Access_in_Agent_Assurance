"""Step 10 - compare the numbers of a (new) run with the published paper numbers.

Runs verify.py on the step-9 outputs. For the paper configuration (or the archived chain test) every check should pass.
For other LLMs the file comparisons are expected to differ; the report then lists, per paper number, the published
value next to the new value (no pass/fail semantics). Output: <out>/compare_report.md and verify_report.csv
"""
import argparse, subprocess, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
ap = argparse.ArgumentParser(); ap.add_argument("--outputs", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--expect-paper", action="store_true", help="fail (exit 1) unless every check passes")
a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
p = subprocess.run([sys.executable, str(ROOT / "verify.py"), "--outputs", a.outputs], capture_output=True, text=True)
(out / "verify_stdout.txt").write_text(p.stdout + p.stderr, encoding="utf-8")
R = pd.read_csv(Path(a.outputs) / "verify_report.csv")
R.to_csv(out / "verify_report.csv", index=False)
n_pass, n_fail = int((R.result == "PASS").sum()), int((R.result == "FAIL").sum())
lines = ["# Comparison with the published numbers", "", f"Outputs: `{a.outputs}`", "",
         f"{n_pass} checks passed, {n_fail} differ from the paper.", "", "| kind | item | result | detail |", "|---|---|---|---|"]
lines += [f"| {r.kind} | {r.item} | {r.result} | {str(r.detail).replace('|', '/')} |" for r in R.itertuples()]
(out / "compare_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"compare_report.md: {n_pass} pass, {n_fail} differ")
sys.exit(1 if (a.expect_paper and n_fail) else 0)
