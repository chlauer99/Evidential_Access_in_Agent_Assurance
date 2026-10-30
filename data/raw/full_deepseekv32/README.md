# full_deepseekv32: raw trajectories not archived

This folder holds only the judge verdicts on the DeepSeek V3.2 full run (300 tasks x 4 attempts):
`judge_deepseek-v3.2.jsonl` (trajectory-only self-judge, 1,200 lines) and `judge_deepseek-v3.2_access.jsonl`
(record-access judge, 157 lines). The run itself (`results.jsonl`, `run_config.json`, `summary.json`,
`per_task.csv`, `_reference/` and `answers/<task>__<attempt>.json` with the full trajectories) was produced on the
author's machine in `mab_runs/full_deepseekv32` and is not part of the archived artefacts. Level A therefore starts
from the archived per-attempt tables in `data/derived/` for everything that depends on these trajectories.

## Dropping the folder in

Copy the author's `mab_runs/full_deepseekv32/` into this folder so that `data/raw/full_deepseekv32/results.jsonl`
and `data/raw/full_deepseekv32/answers/` exist (keep the two judge files). Then:

| Becomes re-runnable from raw | How | Output (compare with) |
|---|---|---|
| Provenance coding of the 408 DeepSeek errors (P1, Table 3) | `python reproduce.py --level A --only a10` (a10 re-codes all runs when the raw folder is present) | `outputs/provenance_recoded.csv`, `outputs/provenance_recode_check.csv` (vs `data/derived/provenance_coding.csv`) |
| First-query codes (Table 4, 9/120 and 480/480) | `python harness/pipeline/first_query_codes.py --runs-dir data/raw --derived <tmp> --runs full_deepseekv32` | vs `data/derived/first_query_codes.csv` (full-run rows) |
| Knowledge-probe items (Table 4) | `python harness/pipeline/build_probes.py --runs-dir data/raw --derived data/derived --out <tmp>` | vs `data/raw/probes/probes_instances.json` |
| Mechanism tracer (Table 3, Table 4, cue baseline) | needs the FHIR server and `full_control_replay`: `python harness/pipeline/trace_runs.py --runs full_deepseekv32 --runs-dir data/raw --derived <tmp> --mode online` | vs `data/derived/full_deepseekv32_mechanisms.csv` |
| Outcome classes incl. format-only regrade | needs the FHIR server: `python harness/pipeline/grade_outcomes.py --runs full_deepseekv32 --runs-dir data/raw --derived <tmp>` | `refined_class` column of the tracer table |
| Record-access sample (418 attempts) | already re-drawn from the verdict table by `a04` (seed 2027) | `outputs/agentic_judge_sample_check.csv` |
| Re-judging (any judge model, no FHIR server needed) | `harness/mab_harness/judge_runs.py` with `MAB_RUNS_DIR` pointing at a copy of `data/raw` | new `judge_<tag>.jsonl` |

The same applies to `cue_deepseekv32` (cue run, 83 tasks x 2 attempts; only `run_config.json` is archived) and to the
2026-09-26 smoke runs of other OpenRouter models (`smoke_model_comparison.csv` in `data/published/`), whose raw folders
were also not archived.
