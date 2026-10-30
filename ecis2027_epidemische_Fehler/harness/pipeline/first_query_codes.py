"""Code used in the first Observation search of each attempt (in-task behaviour of the knowledge probes, Table 4).
Runs offline on raw trajectories. Output: <derived>/first_query_codes.csv"""
import argparse, json, re, sys
from pathlib import Path
from urllib.parse import unquote
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--runs-dir", required=True); ap.add_argument("--derived", required=True)
ap.add_argument("--runs", default="full_deepseekv32,cue_deepseekv32")
a = ap.parse_args()
raw, der = Path(a.runs_dir), Path(a.derived)


def first_obs_code(path):
    d = json.load(open(path, encoding="utf-8"))
    for m in d["history"]:
        c = m.get("content")
        if m.get("role") in ("agent", "assistant") and isinstance(c, str) and c.strip().startswith("GET") and "Observation" in c:
            q = re.search(r"[?&]code=([^&\s]+)", c)
            return unquote(q[1]) if q else "(no code)"
    return None


fc = []
for run in a.runs.split(","):
    M = pd.read_csv(der / f"{run}_mechanisms.csv")
    for t, x, cat in zip(M.task_id, M.attempt, M.category):
        if cat in ("task4", "task5", "task7", "task9", "task10"):
            fc.append(dict(run=run, task_id=t, category=cat, attempt=x, first_code=first_obs_code(raw / run / "answers" / f"{t}__{int(x):02d}.json")))
FC = pd.DataFrame(fc)
given = {"task4": "MG", "task5": "MG", "task7": "GLU", "task9": "K", "task10": "A1C"}
FC["used_given"] = [c == given[k] for c, k in zip(FC.first_code, FC.category)]
FC.to_csv(der / "first_query_codes.csv", index=False)
print(FC.groupby(["run", "category"]).used_given.mean().round(3).to_dict())
