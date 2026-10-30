# cue_deepseekv32: raw trajectories not archived

Only `run_config.json` of the verification-cue run is archived (83 tasks with evidence-gathering errors in the full
run, 2 attempts each, cue sentence in `context_suffix`; resumed once after the 3,000,000-token budget, see `resumed`).
Level A uses the archived tracer table `data/derived/cue_deepseekv32_mechanisms.csv` (166 attempts) and the cue-run
rows of `data/derived/first_query_codes.csv`. Drop the author's `mab_runs/cue_deepseekv32/` here to re-trace it
(see `data/raw/full_deepseekv32/README.md`).
