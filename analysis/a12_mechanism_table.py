"""a12 - Table 3: substantive errors by locus, mechanism and provenance (counts per agent).

Inputs : data/derived/provenance_coding.csv (one row per substantive error, 529 rows)
Outputs: outputs/table3_mechanisms.csv (mechanism x agent counts, with fabricated/unclassified per cell)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
from common import write
from config import DERIVED

NORM = {"false absence": "false_absence", "incomplete retrieval": "incomplete_retrieval", "time-window error": "time_window_error",
        "computation error": "computation_error", "unnecessary order": "unnecessary_order",
        "no action on detected absence": "no_action_on_detected_absence", "unmapped": "no_mechanism_assigned"}
LOCUS = {"false_absence": "evidence_gathering", "incomplete_retrieval": "evidence_gathering", "time_window_error": "conclusion",
         "computation_error": "conclusion", "answer_error_other": "conclusion", "unnecessary_order": "action",
         "no_action_on_detected_absence": "action", "order_content_error": "action", "order_rule_omission": "action",
         "no_mechanism_assigned": "action"}
ORDER = list(LOCUS)
PV = pd.read_csv(DERIVED / "provenance_coding.csv")
PV["mech"] = PV.mechanism.fillna("unmapped").map(lambda m: NORM.get(m, m))
rows = []
for m in ORDER:
    r = {"locus": LOCUS[m], "mechanism": m}
    for ag in ["GPT-4.1", "GPT-4.1-mini", "DeepSeek V3.2"]:
        d = PV[(PV.agent == ag) & (PV.mech == m)]
        r[ag] = len(d); r[f"{ag} F"] = int((d.provenance == "fabricated").sum()); r[f"{ag} U"] = int((d.provenance == "unclassified").sum())
    rows.append(r)
T = pd.DataFrame(rows)
T = T[T[["GPT-4.1", "GPT-4.1-mini", "DeepSeek V3.2"]].sum(axis=1) > 0].reset_index(drop=True)
tot = {"locus": "all", "mechanism": "substantive_errors"}
for c in T.columns[2:]:
    tot[c] = int(T[c].sum())
T = pd.concat([T, pd.DataFrame([tot])], ignore_index=True)
eg = T[T.locus == "evidence_gathering"][["GPT-4.1", "GPT-4.1-mini", "DeepSeek V3.2"]].sum()
share = {"locus": "evidence_gathering", "mechanism": "share_of_substantive_errors"}
for ag in ["GPT-4.1", "GPT-4.1-mini", "DeepSeek V3.2"]:
    share[ag] = eg[ag] / tot[ag]
T = pd.concat([T, pd.DataFrame([share])], ignore_index=True)
write(T, "table3_mechanisms.csv")
