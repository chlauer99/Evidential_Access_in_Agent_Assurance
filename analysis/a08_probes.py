"""a08 - Knowledge probes (Table 4): DeepSeek V3.2 answering isolated questions outside the agent loop, with
matched negative controls. Scoring as in harness/mab_harness/probes.py (first word must equal the truth label).

Inputs : data/raw/probes/probes_deepseekv32.jsonl, probes_deepseekv32_controls.jsonl, data/derived/first_query_codes.csv
Outputs: outputs/probe_summary.csv (published)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import re
import pandas as pd
from common import write
from config import DERIVED, RAW


def score(family, text, truth):
    """Verbatim from harness/mab_harness/probes.py (control-aware version used for the paper)."""
    t = (text or "").strip()
    low = t.lower()
    if family == "code_choice":
        tok = re.sub(r"[`'\"\s.]", "", t.split("\n")[0])
        return tok.upper() == str(truth).upper()
    if family == "absence":  # truth 'no' (invalid query) or 'yes' (valid query, genuinely empty) -- controls added
        return re.sub(r"[^a-z]", " ", low).split()[:1] == [str(truth).lower()]
    if family == "completeness":  # truth 'incomplete' (paged) or 'complete' (single page, no next link)
        return re.sub(r"[^a-z]", " ", low).split()[:1] == [str(truth).lower()]
    nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", t)]
    if not nums:
        return False
    if family in ("window", "age"):
        return abs(nums[0] - float(truth)) < 1e-6
    if family == "mean":
        return abs(nums[0] - float(truth)) <= 0.06
    return False


P = pd.read_json(RAW / "probes" / "probes_deepseekv32.jsonl", lines=True)
PC = pd.read_json(RAW / "probes" / "probes_deepseekv32_controls.jsonl", lines=True)
for d in (P, PC):
    d["correct"] = [score(f, a, t) for f, a, t in zip(d.family, d.answer, d.truth)]
    d["cat"] = d.task_id.str.extract(r"task(\d+)_")[0].astype(int)
allP = pd.concat([P.assign(control=False), PC.assign(control=True)], ignore_index=True).rename(columns={"cat": "catn"})


def cond(r):
    if r.family == "code_choice":
        return "potassium: local code K (LOINC 2823-3 also given)" if r.catn == 9 else "control analytes (A1C, MG, GLU)"
    if r.family == "absence":
        return "valid query, genuinely empty (control)" if r.control else "invalid query (wrong code or name parameter)"
    if r.family == "completeness":
        return "single page, no next link (control)" if r.control else "first page of paged result (next link)"
    return {"window": "latest value within 24 h", "age": "age from birth date", "mean": "mean of listed values"}[r.family]


allP["condition"] = allP.apply(cond, axis=1)
PS = allP.groupby(["family", "condition"]).agg(n_probes=("correct", "size"), n_instances=("probe_id", "nunique"),
                                               accuracy=("correct", "mean")).reset_index()
# in-task behaviour from the first Observation query of each attempt of the full run
FC = pd.read_csv(DERIVED / "first_query_codes.csv")
F = FC[FC.run == "full_deepseekv32"]
k = F[F.category == "task9"]; o = F[F.category != "task9"]
intask = {"potassium: local code K (LOINC 2823-3 also given)":
              f"first in-task Observation query used K: {int(k.used_given.sum())}/{len(k)} ({100 * k.used_given.mean():.1f}%)",
          "control analytes (A1C, MG, GLU)":
              f"first in-task query used the given code: {int(o.used_given.sum())}/{len(o)} ({100 * o.used_given.mean():.0f}%)"}
PS["in_task_behaviour"] = PS.condition.map(intask).fillna("")
write(PS, "probe_summary.csv")
