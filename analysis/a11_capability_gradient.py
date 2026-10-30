"""a11 - Capability comparison (Table 4): success and error rates by locus on the same 30 pilot tasks.

GPT agents: server-regraded outcome classes + the hand-traced mechanisms (the tracer reproduced these on all 197
non-passing pilot attempts; the original script traced the pilot runs live, which needs the FHIR server).
DeepSeek V3.2: tracer output of the full run (data/derived/full_deepseekv32_mechanisms.csv).
Outputs: outputs/capability_gradient.csv (published)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
from common import MECH, codes_for, full_mechanisms, pilot_mechanisms, read_jsonl, write
from config import RAW

HAND2TRACER = {"false absence": "false_absence", "incomplete retrieval": "incomplete_retrieval", "time-window error": "time_window_error",
               "computation error": "computation_error", "unnecessary order": "unnecessary_order",
               "no action on detected absence": "no_action_on_detected_absence"}
MECHS = ["false_absence", "incomplete_retrieval", "time_window_error", "computation_error", "unnecessary_order",
         "no_action_on_detected_absence", "order_rule_omission", "order_content_error", "answer_error_other", "format_only"]
EG = ["false_absence", "incomplete_retrieval"]; CONC = ["time_window_error", "computation_error", "answer_error_other"]
ACT = ["unnecessary_order", "no_action_on_detected_absence", "order_rule_omission", "order_content_error"]


def pilot_frame(run):
    res = {}
    for r in read_jsonl(RAW / run / "results.jsonl"):
        if r["status"] != "API_ERROR":
            res[(r["task_id"], r["attempt"])] = r
    rows = []
    pm = pilot_mechanisms(run)
    for (t, a), c in codes_for(run).items():
        c = c["failure_type_refined"]
        hand = (pm.get((t, a), "") if pm is not None else MECH.get((t, c), ""))
        mech = "format_only" if c == "format_only" else HAND2TRACER.get(hand, hand or None)
        rows.append(dict(task_id=t, attempt=a, official_pass=bool(res[(t, a)]["passed"]), mechanism=mech))
    return pd.DataFrame(rows)


def row(name, d):
    n = len(d)
    r = {"agent": name, "attempts": n, "tasks": d.task_id.nunique(), "success": round(d.groupby("task_id").official_pass.mean().mean(), 3)}
    for m in MECHS:
        r[m] = round(100 * (d.mechanism == m).sum() / n, 1)
    r["evidence_gathering_per100"] = round(100 * d.mechanism.isin(EG).sum() / n, 1)
    r["conclusion_per100"] = round(100 * d.mechanism.isin(CONC).sum() / n, 1)
    r["action_per100"] = round(100 * d.mechanism.isin(ACT).sum() / n, 1)
    return r


V41, Vmini = pilot_frame("pilot_gpt41"), pilot_frame("pilot_gpt41mini")
DS = full_mechanisms()
pilot_ids = set(V41.task_id)
rows = [row("GPT-4.1", V41), row("GPT-4.1-mini", Vmini), row("DeepSeek V3.2", DS[DS.task_id.isin(pilot_ids)]),
        row("DeepSeek V3.2 (all 300 tasks)", DS)]
write(pd.DataFrame(rows), "capability_gradient.csv")
