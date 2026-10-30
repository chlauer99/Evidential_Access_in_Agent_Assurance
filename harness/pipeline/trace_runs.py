"""Step 4 - mechanism tracer: error locus and mechanism of every non-passing attempt.

  --mode online   harness/mab_harness/trace_mechanisms.py (needs the FHIR server and the 300-task reference replay
                  run full_control_replay): parses each trajectory, queries the patient's full record and assigns one
                  mechanism (false_absence, incomplete_retrieval, time_window_error, computation_error,
                  answer_error_other, unnecessary_order, no_action_on_detected_absence, order_rule_omission,
                  order_content_error) with its locus and an evidence string.
  --mode offline  no server: pilot runs get the hand-traced codes (analyse_judges.MECH, which the tracer reproduced on
                  all 197 non-passing pilot attempts); other runs are imported from --import-from if present.
Output: <derived>/<run>_mechanisms.csv (same columns as data/derived/full_deepseekv32_mechanisms.csv)
"""
from __future__ import annotations

import argparse, os, runpy, shutil, sys
from pathlib import Path

import pandas as pd

H = Path(__file__).resolve().parent.parent
HM = H / "mab_harness"
LOCUS = {"false_absence": "evidence_gathering", "incomplete_retrieval": "evidence_gathering", "time_window_error": "conclusion",
         "computation_error": "conclusion", "answer_error_other": "conclusion", "unnecessary_order": "action",
         "no_action_on_detected_absence": "action", "order_rule_omission": "action", "order_content_error": "action"}
HAND2TRACER = {"false absence": "false_absence", "incomplete retrieval": "incomplete_retrieval", "time-window error": "time_window_error",
               "computation error": "computation_error", "unnecessary order": "unnecessary_order",
               "no action on detected absence": "no_action_on_detected_absence"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--derived", required=True)
    ap.add_argument("--mode", choices=["online", "offline"], default="online")
    ap.add_argument("--reference-run", default="full_control_replay")
    ap.add_argument("--import-from", default=None, help="offline: folder with archived <run>_mechanisms.csv tables")
    a = ap.parse_args()
    os.environ["MAB_RUNS_DIR"] = str(Path(a.runs_dir).resolve())
    der = Path(a.derived); der.mkdir(parents=True, exist_ok=True)
    if a.mode == "online":
        ra = runpy.run_path(str(HM / "run_agents.py"), run_name="ra")
        tm = runpy.run_path(str(HM / "trace_mechanisms.py"), run_name="tm")
        tasks = ra["load_tasks"](); ref = tm["reference"](a.reference_run)
        for run in a.runs.split(","):
            d = pd.DataFrame(tm["trace_run"](run, tasks, ref))
            d = d[d.status != "API_ERROR"]
            d.to_csv(der / f"{run}_mechanisms.csv", index=False)
            print(run, len(d), d.mechanism.value_counts().to_dict())
        return
    # offline
    sys.path.insert(0, str(H.parent / "analysis"))
    from common import MECH  # hand-traced pilot codes
    for run in a.runs.split(","):
        oc = der / f"outcome_classes_{run}.csv"
        if run.startswith("pilot") and oc.exists():
            c = pd.read_csv(oc)
            m = [HAND2TRACER.get(MECH.get((t, k), ""), None) if k not in ("pass", "pass_without_acting") else None
                 for t, k in zip(c.task_id, c.cls)]
            m = ["format_only" if k == "format_only" else x for x, k in zip(m, c.cls)]
            d = c.rename(columns={"agent_run": "run", "cls": "refined_class"}).assign(
                mechanism=m, locus=[LOCUS.get(x) for x in m], evidence="hand-traced code (offline mode)")
            d.to_csv(der / f"{run}_mechanisms.csv", index=False)
            print(run, "hand codes", d.mechanism.value_counts().to_dict())
        elif a.import_from and (Path(a.import_from) / f"{run}_mechanisms.csv").exists():
            shutil.copy(Path(a.import_from) / f"{run}_mechanisms.csv", der / f"{run}_mechanisms.csv")
            print(run, "imported archived tracer table")
        else:
            print(run, "SKIPPED: offline mode needs hand codes or an archived table")


if __name__ == "__main__":
    main()
