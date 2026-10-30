"""Seed a full-benchmark run folder with the pilot's first k attempts, so they are reused rather than rerun.

For each pilot task, the latest valid (non-API_ERROR) row of attempts 0..k-1 is copied into
mab_runs/<target>/results.jsonl, and its answer JSON is copied to mab_runs/<target>/answers/ under the same file name.
Copied rows get "reused_from": "<source run>" and their answer_file path is rewritten to the new location.
run_agents.py then treats those (task, attempt) pairs as done when it is resumed with --tasks all --n k.

Usage: python seed_from_pilot.py pilot_gpt41 full_gpt41 [--k 4] [--dry-run]
"""
from __future__ import annotations

import argparse, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "mab_runs"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("source"); ap.add_argument("target")
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    src, dst = RUNS / a.source, RUNS / a.target
    latest = {}
    for l in (src / "results.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            if r["status"] != "API_ERROR" and r["attempt"] < a.k:
                latest[(r["task_id"], r["attempt"])] = r
    existing = set()
    if (dst / "results.jsonl").exists():
        for l in (dst / "results.jsonl").read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                if r["status"] != "API_ERROR":
                    existing.add((r["task_id"], r["attempt"]))
    todo = [r for k, r in latest.items() if k not in existing]
    tasks = sorted({t for t, _ in latest})
    print(f"{a.source} -> {a.target}: {len(latest)} valid pilot rows (attempts < {a.k}, {len(tasks)} tasks); "
          f"{len(existing)} already in target; {len(todo)} to copy")
    if a.dry_run:
        return
    (dst / "answers").mkdir(parents=True, exist_ok=True)
    with open(dst / "results.jsonl", "a", encoding="utf-8") as fh:
        for r in todo:
            old = ROOT / r["answer_file"]
            new = dst / "answers" / old.name
            shutil.copy2(old, new)
            r = dict(r, answer_file=str(new.relative_to(ROOT)), reused_from=a.source)
            fh.write(json.dumps(r) + "\n")
    ref_src, ref_dst = src / "_reference", dst / "_reference"
    if ref_src.exists():
        ref_dst.mkdir(exist_ok=True)
        for f in ref_src.glob("*.json"):
            if not (ref_dst / f.name).exists():
                shutil.copy2(f, ref_dst / f.name)


if __name__ == "__main__":
    main()
