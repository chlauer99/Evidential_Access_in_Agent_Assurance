# Cross-judge evaluation of saved attempts

These are the archived neutral-condition judge commands and request settings from `cross_judge_exp_1`. They reuse saved attempts; they do not rerun agents.

| Target directory | Source attempt set | Judge |
|---|---|---|
| `runs/cross_judge_exp_1/on_gpt_oss_attempts/mab_runs/full_deepseekv32/` | `runs/gpt_oss_120b_exp_2/mab_runs/full_deepseekv32/` | Qwen |
| `runs/cross_judge_exp_1/on_qwen_attempts/mab_runs/full_deepseekv32/` | `runs/qwen3_8_27b_exp_3/mab_runs/full_deepseekv32/` | GPT-OSS |

No historical outputs or target attempt copies are included. First execute the two source experiments or supply their outputs separately, then copy `results.jsonl` and `answers/` from each source to its target directory before running the commands. Configure the model endpoint addresses for your deployment.

From the repository root, `bash harness/configs/cross_judge_exp_1/neutral_commands.sh` executes the original neutral-condition calls and incurs model usage. For specification, checklist and record-access conditions, see [the backfill instructions](../../scripts/BACKFILL_CROSS_JUDGE.md). Those additionally require source record-access selections and a running FHIR server.

Analyse the cross-judge results with:

```sh
python harness/pipeline/analyse_cross_judge.py --runs-root runs --out runs/cross_judge_exp_1/outputs
```
