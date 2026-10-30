"""Shared configuration for the Level A analyses.

All paths are relative to the package root (the folder that contains reproduce.py), so the
package can be unpacked anywhere. No network access, API keys or FHIR server are needed.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
# Input locations. Defaults = the archived study data; run_pipeline.py (step 9) points them at a new run instead:
#   REPRO_RAW      run folders in the harness format (<run>/results.jsonl, answers/, judge_<condition>.jsonl),
#                  plus probes/ and record_access/
#   REPRO_DERIVED  per-attempt tables (outcome classes, tracer mechanisms, provenance coding, first-query codes)
#   REPRO_OUT      where the regenerated tables and figures go
#   REPRO_STUDY    optional JSON file mapping the role slots below to display names and developers (other LLMs)
RAW = Path(os.environ.get("REPRO_RAW", DATA / "raw")).resolve()
DERIVED = Path(os.environ.get("REPRO_DERIVED", DATA / "derived")).resolve()
PUBLISHED = DATA / "published"  # derived CSVs exactly as used in the paper (for verify.py only)
OUT = Path(os.environ.get("REPRO_OUT", ROOT / "outputs")).resolve()
OUT.mkdir(parents=True, exist_ok=True)

# Fixed random seeds (identical to the seeds used for the published analyses)
SEED_JUDGE_REPORT = 2026   # judge_report.cluster_boot / discrimination (B = 2000)
SEED_BOOT_J = 2026         # record-access J bootstrap (B = 4000), shared generator per script
SEED_PAIRED = 7            # paired condition contrasts (B = 4000), fresh generator per contrast
SEED_KAPPA = 3             # kappa bootstrap (B = 3000), fresh generator per judge pair
SEED_CUE = 2026            # cue effects (B = 4000)
SEED_SAMPLE = 2027         # record-access stratified sample (only used when rebuilding the sample from raw)

B_JUDGE = 2000
B_BOOT_J = 4000
B_PAIRED = 4000
B_KAPPA = 3000
B_CUE = 4000

AGENT_RUNS = {"pilot_gpt41": "gpt-4.1", "pilot_gpt41mini": "gpt-4.1-mini", "full_deepseekv32": "deepseek-v3.2"}
AGENT_NAME = {"pilot_gpt41": "GPT-4.1", "pilot_gpt41mini": "GPT-4.1-mini", "full_deepseekv32": "DeepSeek V3.2"}
JUDGE_NAME = {"gpt-4.1": "GPT-4.1", "gpt-4.1-mini": "GPT-4.1-mini", "deepseek-v3.2": "DeepSeek V3.2"}
# Judge conditions (file suffix under data/raw/<run>/judge_<condition>.jsonl)
JUDGES = ["gpt-4.1", "gpt-4.1-mini", "gpt-4.1_spec", "gpt-4.1-mini_spec", "deepseek-v3.2", "deepseek-v3.2_verify",
          "deepseek-v3.2_access"]
LINEAGE = {"gpt-4.1": "openai", "gpt-4.1-mini": "openai", "deepseek-v3.2": "deepseek"}
GROUNDED = {"substantive_answer_error", "omission", "commission"}   # "substantive error" in the paper

# Role slots. The identifiers are the paper's run and judge names; a study with other LLMs keeps the identifiers
# (they define the design: two agents of one developer on the pilot tasks, one agent of a second developer on all
# tasks, each agent's model also used as a judge) and maps them to its own models via REPRO_STUDY, e.g.
# {"agent_name": {"pilot_gpt41": "Llama-3.3-70B", ...}, "judge_name": {"gpt-4.1": "Llama-3.3-70B", ...},
#  "lineage": {"gpt-4.1": "meta", "gpt-4.1-mini": "meta", "deepseek-v3.2": "qwen"}}
if os.environ.get("REPRO_STUDY"):
    import json as _json
    _S = _json.loads(Path(os.environ["REPRO_STUDY"]).read_text(encoding="utf-8"))
    AGENT_NAME.update(_S.get("agent_name", {}))
    JUDGE_NAME.update(_S.get("judge_name", {}))
    LINEAGE.update(_S.get("lineage", {}))


def raw_run(run: str) -> Path:
    """Folder of an archived run. The DeepSeek full run and the cue run hold only judge files / config
    unless the author's raw folders are dropped in (see data/raw/full_deepseekv32/README.md)."""
    return RAW / run


def full_run_raw_available() -> bool:
    return (RAW / "full_deepseekv32" / "results.jsonl").exists() and (RAW / "full_deepseekv32" / "answers").is_dir()
