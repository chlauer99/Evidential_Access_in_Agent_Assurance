"""Step 8 (selection) - tasks on which the full-run agent made at least one evidence-gathering error (paper: 83).
Output: <out> (comma-separated task ids, the --tasks argument of the cue run)"""
import argparse
from pathlib import Path
import pandas as pd

ap = argparse.ArgumentParser(); ap.add_argument("--mechanisms", required=True); ap.add_argument("--out", required=True)
a = ap.parse_args()
M = pd.read_csv(a.mechanisms)
ids = sorted(M[M.locus == "evidence_gathering"].task_id.unique(), key=lambda t: (int(t[4:].split("_")[0]), int(t.split("_")[1])))
Path(a.out).write_text(",".join(ids), encoding="utf-8")
print(len(ids), "tasks")
