# Paper experiment configurations

Only configurations for the paper experiment families are retained.

| Configuration | Models / experiment | Generated run directory (not included) |
|---|---|---|
| `paper.yaml` | GPT-4.1, GPT-4.1-mini, DeepSeek V3.2; original agent/judge conditions, controls, probes and cue | `runs/paper/` (rerun; role identifiers match the original study) |
| `gpt_oss_120b_exp_2.yaml` | Complete GPT-OSS 120B run with self-judge | `runs/gpt_oss_120b_exp_2/` |
| `qwen3_8_27b_exp_3.yaml` | Complete Qwen3.8 27B run with self-judge | `runs/qwen3_8_27b_exp_3/` |
| `cross_judge_exp_1/` | Reciprocal cross-judging of saved GPT-OSS and Qwen attempts | `runs/cross_judge_exp_1/` |

Example models, technical smoke tests, the offline archived-chain test and superseded Qwen runs are excluded. The YAML files retain their original experiment settings; endpoint addresses must be adapted to the deployment. See the cross-judge README and `harness/scripts/BACKFILL_CROSS_JUDGE.md` for judge-only commands.

The retained open-weight experiment configurations correspond to `gpt_oss_120b_exp_2`, `qwen3_8_27b_exp_3` and `cross_judge_exp_1` (original archived identifiers). The separate fresh GPT-OSS agent / Qwen judge run is excluded. `paper.yaml` retains the original GPT-4.1, GPT-4.1-mini and DeepSeek experiment setup.

No saved runs, trajectories, verdicts or derived results are included. Generate the source runs before cross-judging or supply compatible outputs separately.
