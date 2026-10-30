# Paper run archives

Only these archived run directories are included:

| Directory | Configuration / experiment |
|---|---|
| `gpt_oss_120b_exp_2/` | `harness/configs/gpt_oss_120b_exp_2.yaml`: GPT-OSS agents and self-judge |
| `qwen3_8_27b_exp_3/` | `harness/configs/qwen3_8_27b_exp_3.yaml`: Qwen agents and self-judge |
| `cross_judge_exp_1/` | `harness/configs/cross_judge_exp_1/`: reciprocal judging of the saved attempts from the two source runs |

Run files include available agent trajectories, judge verdicts, controls, probes, cue attempts, derived analyses, execution logs and recorded request settings. Figures, local caches and server downloads are excluded. No experiments were rerun for this import.

Original GPT-4.1, GPT-4.1-mini and DeepSeek V3.2 inputs, corresponding to `harness/configs/paper.yaml`, retain the analysis-compatible locations `data/raw/` and `data/derived/`.

Excluded: `vllm_gpt_oss_main`, smoke experiments, `gpt_oss_120b_qwen_judge_exp_1`, and comparative analyses that mix in the excluded run.

## Original-study archive limitations

The local original-study archive is incomplete: `data/raw/full_deepseekv32/` contains judge verdicts but no full agent trajectories/results; `data/raw/cue_deepseekv32/` contains configuration and documentation only. Existing derived tables are included instead of reconstructing missing raw files. The full-benchmark control outputs named in `paper.yaml` are also absent from the local archive. See the READMEs within these raw directories for details. Published verification targets under `data/published/` are not included in this run import.
