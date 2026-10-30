#!/usr/bin/env bash
# Every experiment of the paper, in order, with the exact settings. Run from anywhere; it changes to harness/.
# Same with a config:  python run_pipeline.py --config configs/paper.yaml --dry-run   (then --steps ... --yes)
# Keys come from environment variables only:  export OPENAI_API_KEY=... OPENROUTER_API_KEY=...
# Estimated cost of a full replication: about USD 15-20 at list prices before prompt-cache discounts (README, "Costs").
set -euo pipefail
cd "$(dirname "$0")/.."
export NO_PROXY=localhost,127.0.0.1

# ---- 0. FHIR server (pinned image jyxsu6/medagentbench@sha256:3fb83d7e...; about 4.5 GB). Windows without Docker:
python mab_harness/fetch_server.py mab_server
# start in a SEPARATE window and keep it open (about 80 s to ready):  python mab_harness/start_server.py
# Linux/macOS with Docker instead:  docker run -d --rm --name medagentbench-fhir -p 8080:8080 jyxsu6/medagentbench@sha256:3fb83d7ed71c5476f9eb6212bd440a909ef7505922bbc757dc488a8fc0701966
# ---- 2. controls (no API). The 30-task controls were produced with run_agents v0 (a9c10028); protocol identical
python mab_harness/run_agents.py --agent replay --tasks pilot --n 1 --run-name control_replay
python mab_harness/run_agents.py --agent null --tasks pilot --n 1 --run-name control_null
python mab_harness/run_agents.py --agent replay --tasks all --n 1 --workers 6 --run-name full_control_replay
python mab_harness/run_agents.py --agent null --tasks all --n 1 --workers 6 --run-name full_control_null
# ---- 1. agents. Paper: model aliases gpt-4.1 / gpt-4.1-mini (served as the 2025-04-14 snapshots), T = 0.8, 8 rounds
python mab_harness/run_agents.py --agent openai --model gpt-4.1 --tasks task1_1,task3_4,task10_10 --n 1 --run-name smoke_gpt41
python mab_harness/run_agents.py --agent openai --model gpt-4.1 --tasks pilot --n 8 --temperature 0.8 --workers 3 --tpm 27000 --max-total-tokens 4000000 --price-in 2.0 --price-out 8.0 --run-name pilot_gpt41
python mab_harness/run_agents.py --agent openai --model gpt-4.1-mini --tasks pilot --n 8 --temperature 0.8 --workers 6 --tpm 180000 --max-total-tokens 6000000 --price-in 0.4 --price-out 1.6 --run-name pilot_gpt41mini
python mab_harness/run_agents.py --agent openai --model deepseek/deepseek-v3.2 --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY --extra-body @mab_harness/openrouter_route_deepseek-v3.2.json --tasks all --n 4 --workers 6 --max-total-tokens 14000000 --price-in 0.27 --price-out 0.4 --run-name full_deepseekv32
# ---- 3-5. outcome classes, mechanism tracer (both need the FHIR server), provenance
python pipeline/grade_outcomes.py --runs pilot_gpt41,pilot_gpt41mini,full_deepseekv32 --runs-dir mab_runs --derived derived
python pipeline/trace_runs.py --runs pilot_gpt41,pilot_gpt41mini,full_deepseekv32 --runs-dir mab_runs --derived derived
python pipeline/code_provenance.py --runs-dir mab_runs --derived derived
# ---- 6. judges: trajectory only (neutral prompt), + API specification, + checklist, + record access; T = 0, 400-token cap
python mab_harness/judge_runs.py --judge gpt-4.1-mini --runs pilot_gpt41,pilot_gpt41mini,control_replay,control_null --tpm 180000 --workers 6
python mab_harness/judge_runs.py --judge gpt-4.1 --runs pilot_gpt41,control_replay,control_null --tpm 27000 --workers 3
python mab_harness/judge_runs.py --judge gpt-4.1 --runs pilot_gpt41mini --tpm 27000 --workers 3
python mab_harness/judge_runs.py --judge gpt-4.1-mini --with-spec --runs pilot_gpt41,pilot_gpt41mini,control_replay,control_null --tpm 150000 --workers 6
python mab_harness/judge_runs.py --judge gpt-4.1 --with-spec --runs pilot_gpt41,control_replay,control_null --tpm 27000 --workers 3
python mab_harness/judge_runs.py --judge deepseek/deepseek-v3.2 --tag deepseek-v3.2 --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY --extra-body @mab_harness/openrouter_route_deepseek-v3.2.json --runs pilot_gpt41,pilot_gpt41mini,control_replay,control_null --workers 6
python mab_harness/judge_runs.py --judge deepseek/deepseek-v3.2 --tag deepseek-v3.2 --prompt verify --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY --extra-body @mab_harness/openrouter_route_deepseek-v3.2.json --runs pilot_gpt41,pilot_gpt41mini,control_replay,control_null --workers 4
python mab_harness/judge_runs.py --judge deepseek/deepseek-v3.2 --tag deepseek-v3.2 --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY --extra-body @mab_harness/openrouter_route_deepseek-v3.2.json --runs full_deepseekv32 --workers 6
# record-access sample: the paper's is mab_harness/agentic_judge_sample.json; re-draw (seed 2027): python pipeline/make_access_sample.py --runs-dir mab_runs --derived derived
python mab_harness/judge_agentic.py --sample mab_harness/agentic_judge_sample.json --judge deepseek/deepseek-v3.2 --tag deepseek-v3.2_access --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY --extra-body @mab_harness/openrouter_route_deepseek-v3.2.json --max-queries 4 --workers 6
# ---- 7. knowledge probes (3 samples per item, T = 0.8). pipeline/build_probes.py rebuilds the items from the full run
python mab_harness/probes.py run --instances mab_harness/probes_instances.json --model deepseek/deepseek-v3.2 --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY --extra-body @mab_harness/openrouter_route_deepseek-v3.2.json --samples 3 --workers 6 --out mab_runs/probes/probes_deepseekv32.jsonl
python mab_harness/probes.py run --instances mab_harness/probes_controls.json --model deepseek/deepseek-v3.2 --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY --extra-body @mab_harness/openrouter_route_deepseek-v3.2.json --samples 3 --out mab_runs/probes/probes_deepseekv32_controls.jsonl
# ---- 8. verification cue on the 83 tasks with evidence-gathering errors, 2 attempts (the paper resumed it once: run_config.json 'resumed')
python mab_harness/run_agents.py --agent openai --model deepseek/deepseek-v3.2 --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY --extra-body @mab_harness/openrouter_route_deepseek-v3.2.json --tasks task1_1,task1_10,task1_11,task1_12,task1_13,task1_14,task1_15,task1_16,task1_17,task1_18,task1_19,task1_2,task1_20,task1_21,task1_22,task1_23,task1_24,task1_25,task1_26,task1_27,task1_3,task1_4,task1_5,task1_6,task1_7,task1_8,task1_9,task4_17,task4_28,task4_3,task4_5,task6_12,task6_13,task6_2,task6_20,task6_21,task6_23,task6_24,task6_29,task6_30,task6_4,task6_5,task6_8,task7_1,task7_10,task7_12,task7_13,task7_14,task7_15,task7_16,task7_18,task7_19,task7_23,task7_24,task7_27,task7_30,task9_1,task9_10,task9_11,task9_14,task9_15,task9_16,task9_17,task9_18,task9_19,task9_2,task9_20,task9_21,task9_22,task9_23,task9_24,task9_25,task9_26,task9_27,task9_28,task9_29,task9_3,task9_30,task9_5,task9_6,task9_7,task9_8,task9_9 --n 2 --workers 6 --max-total-tokens 3000000 --context-suffix "Before concluding that a record or result does not exist, or that a value is the most recent one, check that your search used the codes and parameters given here and that you have read every page of the results." --price-in 0.27 --price-out 0.4 --run-name cue_deepseekv32
python pipeline/grade_outcomes.py --runs cue_deepseekv32 --runs-dir mab_runs --derived derived
python pipeline/trace_runs.py --runs cue_deepseekv32 --runs-dir mab_runs --derived derived
python pipeline/first_query_codes.py --runs-dir mab_runs --derived derived
# ---- 9. all tables and figures from these runs (10: python pipeline/compare_report.py --outputs ../runs/manual/outputs --out ../runs/manual)
python ../reproduce.py --level A --raw mab_runs --derived derived --out ../runs/manual/outputs --no-verify
