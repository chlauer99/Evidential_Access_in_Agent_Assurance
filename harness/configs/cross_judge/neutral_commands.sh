#!/usr/bin/env bash
set -euo pipefail
# Run from the repository root after preparing copies of the saved source attempts.
MAB_RUNS_DIR=runs/cross_judge_exp_1/on_gpt_oss_attempts/mab_runs python harness/mab_harness/judge_runs.py --judge Qwen/Qwen3.8-27B --tag qwen3_8_27b --workers 3 --temperature 0 --max-tokens 4096 --base-url http://192.168.92.194:10122/v1 --api-key-env '' --extra-body @harness/configs/cross_judge/extra_body_ddfbc286.json --strip-reasoning --structured-output --runs full_deepseekv32
MAB_RUNS_DIR=runs/cross_judge_exp_1/on_qwen_attempts/mab_runs python harness/mab_harness/judge_runs.py --judge openai/gpt-oss-120b --tag gpt-oss-120b --workers 1 --temperature 0 --max-tokens 8192 --base-url http://192.168.92.194:10121/v1 --api-key-env '' --extra-body @harness/configs/cross_judge/extra_body_a8da54bc.json --strip-reasoning --structured-output --runs full_deepseekv32
