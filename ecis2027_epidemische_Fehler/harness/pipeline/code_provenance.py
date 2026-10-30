"""Step 5 - evidential provenance of every substantive error (grounded / fabricated / unclassified).

Applies the exact rules of the published coding (analysis/provenance_rules.py) to the raw trajectories. Runs offline.
Rows: pilot runs (classes substantive_answer_error, commission, omission; mechanism from <run>_mechanisms.csv or the
hand codes) and the full run (classes substantive_answer_error, commission, wrong_order, omission; tracer mechanism).
If a run's raw trajectories are missing, its rows are imported from --import-from (archived provenance_coding.csv).
Output: <derived>/provenance_coding.csv
"""
from __future__ import annotations

import argparse, os, sys
from pathlib import Path

import pandas as pd

H = Path(__file__).resolve().parent.parent
AGENT = {"pilot_gpt41": "GPT-4.1", "pilot_gpt41mini": "GPT-4.1-mini", "full_deepseekv32": "DeepSeek V3.2"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--derived", required=True)
    ap.add_argument("--import-from", default=None)
    ap.add_argument("--single-run", default=None)
    ap.add_argument("--agent-name", default="Single-model agent")
    a = ap.parse_args()
    os.environ["REPRO_RAW"] = str(Path(a.runs_dir).resolve()); os.environ["REPRO_DERIVED"] = str(Path(a.derived).resolve())
    sys.path.insert(0, str(H.parent / "analysis"))
    from common import MECH, pilot_mechanisms
    from provenance_rules import recode
    raw, der = Path(a.runs_dir), Path(a.derived)
    if a.single_run:
        M = pd.read_csv(der / f"{a.single_run}_mechanisms.csv")
        d = M[M.refined_class.isin(["substantive_answer_error", "omission", "commission", "wrong_order"])]
        rows = recode(a.single_run, a.agent_name,
                      [(t, int(x), c, m) for t, x, c, m in zip(d.task_id, d.attempt, d.refined_class, d.mechanism)], raw=raw)
        columns = ["agent", "task_id", "attempt", "outcome_class", "mechanism", "provenance", "basis", "unsupported_values"]
        pd.DataFrame(rows, columns=columns).to_csv(der / "provenance_coding.csv", index=False)
        print(f"{a.single_run}: {len(rows)} substantive errors coded; no pilot or archived coding loaded")
        return
    rows, imported = [], []
    arch = pd.read_csv(a.import_from) if a.import_from else None
    for run in ["full_deepseekv32", "pilot_gpt41", "pilot_gpt41mini"]:
        agent = AGENT[run]
        have_raw = (raw / run / "results.jsonl").exists() and (raw / run / "answers").is_dir()
        if run.startswith("pilot"):
            f = der / f"outcome_classes_{run}.csv"
            if have_raw and f.exists():
                d = pd.read_csv(f); d = d[d.cls.isin(["substantive_answer_error", "commission", "omission"])]
                pm = pilot_mechanisms(run)
                rows += recode(run, agent, [(t, int(x), c, pm.get((t, int(x)), "") if pm is not None else MECH.get((t, c), ""))
                                            for t, x, c in zip(d.task_id, d.attempt, d.cls)], raw=raw)
                continue
        else:
            f = der / f"{run}_mechanisms.csv"
            if have_raw and f.exists():
                M = pd.read_csv(f); d = M[M.refined_class.isin(["substantive_answer_error", "commission", "wrong_order", "omission"])]
                rows += recode(run, agent, [(t, int(x), c, m) for t, x, c, m in zip(d.task_id, d.attempt, d.refined_class, d.mechanism)], raw=raw)
                continue
        if arch is not None:
            rows += arch[arch.agent == agent].to_dict("records"); imported.append(run)
    PV = pd.DataFrame(rows)[["agent", "task_id", "attempt", "outcome_class", "mechanism", "provenance", "basis", "unsupported_values"]]
    PV.to_csv(der / "provenance_coding.csv", index=False)
    print(PV.groupby(["agent", "provenance"]).size().unstack(fill_value=0).to_string())
    print("imported from archive:", imported or "none")


if __name__ == "__main__":
    main()
