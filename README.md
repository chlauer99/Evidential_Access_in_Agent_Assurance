# Evidential Access in Agent Assurance

Code and selected experiment archives for **“No Results Found”: Evidential Access and the Automated Assurance of Agentic Health Information Systems** (ECIS 2027).

This repository contains the MedAgentBench experiment pipeline, agent runners, reference grading, LLM judges, knowledge probes, analysis code, and the selected paper runs. All benchmark patient records are synthetic. Paper figure scripts and manuscript files are not included.

## 1. Installation

Use **Python 3.11** (the version specified by the original environment files). Run all commands below from the repository root. Examples use a macOS/Linux shell.

```sh
git clone https://github.com/chlauer99/Evidential_Access_in_Agent_Assurance.git
cd Evidential_Access_in_Agent_Assurance
git switch codex/publish-experiment-code
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows PowerShell, create the environment with `py -3.11 -m venv .venv` and activate it with `.venv\Scripts\Activate.ps1`.

`requirements.txt` covers the Python packages used by the experiment and analysis code, including `tqdm` for progress reporting and `httpx` for request/retry tests. It specifies dependency lower bounds, not a locked copy of the historical execution environment.

Alternatively, use Conda:

```sh
conda env create -f environment-harness.yml
conda activate ecis2027-harness
python -m pip install -r requirements.txt
```

**Offline analysis** requires no model endpoint, API key, FHIR server or Docker. **New experiments** additionally require reachable model endpoints and the MedAgentBench FHIR server. The selected open-weight configurations use Docker for that server. The original `paper.yaml` supports automatic server selection; Java 17 is needed for the non-Docker route. Docker, Java and model serving software are separate from the Python requirements.

## 2. Repository layout

| Location | Purpose |
|---|---|
| `harness/configs/` | Selected experiment configurations and cross-judge commands |
| `harness/run_pipeline.py` | Orchestrates experiment steps |
| `harness/mab_harness/` | Agent execution, model judges, knowledge probes and FHIR server setup |
| `harness/pipeline/` | Grading, error coding, sample selection and analysis |
| `harness/prompts/` | Exported experiment prompts |
| `harness/mab_tasks/` | Benchmark instructions, metadata and shared reference-grading code |
| `harness/tests/` | Existing checks for protocol handling, judges and pipeline behaviour |
| `runs/` | The three selected open-weight experiment archives |
| `data/raw/` | Available original GPT-4.1, GPT-4.1-mini and DeepSeek outputs |
| `data/derived/` | Original-study outcome, mechanism and provenance tables |
| `analysis/` | Original-study table analyses and historical comparative analysis |
| `reproduce.py` / `verify.py` | Original-study table runner and verification tools |

The identifiers `full_deepseekv32` and `cue_deepseekv32` are also used inside the Qwen and GPT-OSS runs as internal role names. In those directories they do **not** mean that DeepSeek was the model; the corresponding YAML and `run_config.json` identify the model used.

## 3. Which experiments are included?

| Experiment | Configuration | Archived inputs and results |
|---|---|---|
| GPT-4.1, GPT-4.1-mini and DeepSeek V3.2 | `harness/configs/paper.yaml` | `data/raw/` and `data/derived/` |
| GPT-OSS 120B agents with GPT-OSS self-judge | `harness/configs/gpt_oss_120b_exp_2.yaml` | `runs/gpt_oss_120b_exp_2/` |
| Qwen3.8 27B agents with Qwen self-judge | `harness/configs/qwen3_8_27b_exp_3.yaml` | `runs/qwen3_8_27b_exp_3/` |
| Reciprocal judging of those saved GPT-OSS and Qwen attempts | `harness/configs/cross_judge_exp_1/` | `runs/cross_judge_exp_1/` |

The self-judge experiments include trajectory-only, API-specification, checklist and read-only record-access conditions, plus controls, probes and verification-cue runs. The cross-judge analysis described below compares the trajectory-only condition. A separate script can add specification, checklist and record-access verdicts.

Smoke runs, superseded Qwen configurations and the separate fresh GPT-OSS-agent/Qwen-judge experiment are excluded. See [the configuration mapping](harness/configs/README.md) and [archive details](runs/README.md).

Typical files within an archived run:

- `mab_runs/<role>/results.jsonl`: attempt results; `answers/`: saved trajectories.
- `mab_runs/<role>/run_config.json`: recorded execution settings.
- `judge_<tag>.jsonl`: judge verdicts; `_spec`, `_verify` and `_access` identify additional evidence conditions.
- `derived/`: graded outcomes, error mechanisms and other coded inputs.
- `09_analysis/outputs/`: saved summary tables and reports.
- `pipeline_commands.txt`, stage logs and `DONE.json`: execution records and completion markers.

## 4. Analyse existing results offline

The commands in this section write to `outputs/`, keeping the archived results intact.

### GPT-OSS self-judge

```sh
python harness/pipeline/analyse_single.py \
  --config harness/configs/gpt_oss_120b_exp_2.yaml \
  --runs-dir runs/gpt_oss_120b_exp_2/mab_runs \
  --derived runs/gpt_oss_120b_exp_2/derived \
  --out outputs/gpt_oss_120b_exp_2
```

### Qwen self-judge

```sh
python harness/pipeline/analyse_single.py \
  --config harness/configs/qwen3_8_27b_exp_3.yaml \
  --runs-dir runs/qwen3_8_27b_exp_3/mab_runs \
  --derived runs/qwen3_8_27b_exp_3/derived \
  --out outputs/qwen3_8_27b_exp_3
```

These analyses produce descriptive outcome tables, judge metrics, paired condition comparisons and reports. They use the existing graded outcomes and verdicts; no model calls or regrading against the server are needed.

### Reciprocal cross-judge analysis

```sh
python harness/pipeline/analyse_cross_judge.py \
  --runs-root runs \
  --out outputs/cross_judge_exp_1
```

This joins saved self-judge and cross-judge verdicts on the same attempts and reports joint error acceptance and agreement measures. It currently analyses the **neutral / trajectory-only** condition.

### Original GPT-4.1 / GPT-4.1-mini / DeepSeek analyses

Start with the attempt and outcome tables:

```sh
python reproduce.py --level A --only a01 a02 --out outputs/original-study --no-verify
```

To run the configured original-study table analyses (`a01`–`a13`):

```sh
python reproduce.py --level A --out outputs/original-study --no-verify
```

The full table sequence includes bootstrap calculations and can take several minutes. `--only` selects script prefixes, for example `--only a03 a05`. Figure generation is removed. The open-weight and cross-judge analyses above are separate and are not run by `reproduce.py`.

Use `--no-verify` with the included archive: `verify.py` expects published comparison files under `data/published/`, which are not included. It remains available if those reference files are supplied separately.

## 5. Run new experiments

### Configure the model and output location

Choose one of the three YAML configurations. Set `models.<identifier>.base_url`, `model`, and `api_key_env` for your deployment. The private-network endpoint addresses in the archived configurations must be replaced with reachable endpoints. An empty `api_key_env` is used for the local endpoints in the selected runs.

For `paper.yaml`, supply `OPENAI_API_KEY` and `OPENROUTER_API_KEY` through your environment. Never put keys in YAML files or commit them. Keep the recorded task counts, generation settings and judge settings unchanged when reproducing the paper setup; changes define a different experiment.

Use a separate output root for new runs. The pipeline resumes existing attempts and skips stages with `DONE.json`, so running against the archive would not start a clean experiment.

### Inspect the plan

```sh
python harness/run_pipeline.py \
  --config harness/configs/gpt_oss_120b_exp_2.yaml \
  --runs-root outputs/new-experiments \
  --steps 0-9 --dry-run
```

`--dry-run` prints the commands without executing them. For Qwen or the original study, substitute the corresponding YAML path.

### Execute

After configuring the endpoints and ensuring Docker is running:

```sh
python harness/run_pipeline.py \
  --config harness/configs/gpt_oss_120b_exp_2.yaml \
  --runs-root outputs/new-experiments \
  --steps 0-9 --yes
```

`--yes` enables model-calling stages, which may incur charges. Results are written beneath `outputs/new-experiments/<configuration name>/`. The server stage may download the pinned MedAgentBench image (several GB) and exposes FHIR on port 8080. The model server must use a different port. For an existing FHIR server, configure `fhir.mode: external` and its `base_url`.

| Step | Action |
|---|---|
| 0 | Prepare or connect to the FHIR server |
| 1–2 | Agent attempts and replay / null controls |
| 3–5 | Grade outcomes, trace mechanisms and code provenance |
| 6 | Judge under the configured evidence conditions |
| 7–8 | Knowledge probes and verification-cue attempts |
| 9 | Analyse the new results |
| 10 (optional) | Compare against archived reference results |

The example runs steps 0–9. Step 10 is a comparison stage, not a requirement for generating new experiment results. To resume an interrupted experiment, repeat the same command with the same configuration and output root. See [RUNNING.md](RUNNING.md) for additional setup notes.

## 6. Run cross-judge evaluations

Cross-judging reuses saved agent trajectories rather than starting new agent attempts. For a fresh experiment, prepare copies of the source `results.jsonl` and `answers/` in the two cross-judge target directories. The checked-in archive already contains these copies.

The original neutral-condition commands and request settings are in [harness/configs/cross_judge_exp_1/](harness/configs/cross_judge_exp_1/). After adapting their endpoint addresses, execute them with:

```sh
bash harness/configs/cross_judge_exp_1/neutral_commands.sh
```

These commands call the model endpoints and use the archived cross-judge output paths. Work on a separate copy when preserving the archive. Existing valid results may be reused rather than regenerated.

For additional specification, checklist and record-access conditions, first inspect the plan:

```sh
python harness/scripts/backfill_cross_judge.py
```

Add `--execute` to make model calls. Endpoint and run-location overrides are described in [BACKFILL_CROSS_JUDGE.md](harness/scripts/BACKFILL_CROSS_JUDGE.md). Record access additionally requires the source record-access selections and the benchmark FHIR server. Adding these verdicts does not automatically extend the neutral-only cross-judge analysis.

## 7. Limits of this archive

- Original DeepSeek full-run trajectories and results are not available in the local source archive; judge verdicts and derived tables are included. The original cue directory contains configuration and documentation rather than raw cue trajectories. Original full-benchmark control outputs are also missing. See [runs/README.md](runs/README.md).
- Published verification targets in `data/published/`, the manuscript and paper figures are excluded. The repository therefore does not support an unconditional claim that every original artefact can be verified from a fresh clone.
- `analysis/a15_open_weight_runs.py` is a retained historical comparison script. It still expects the excluded `gpt_oss_120b_qwen_judge_exp_1` run, so it is **not an entry point for the selected three-run release**. Use the self-judge and cross-judge commands above.
- `PACKAGE_README.md`, `REPRO_REPORT.md` and parts of `VLLM_START.md` describe earlier versions of the full research package. This README and the current configuration mapping describe the release contents.
- Historical implementations under `harness/mab_harness/history/` document the original experiments. `original_medagentbench_task.py` is upstream reference code, not the standalone runner used by the pipeline.

## 8. Checks and provenance

Existing automated checks can be run with:

```sh
python -m unittest -v \
  harness.tests.test_fhir_urls \
  harness.tests.test_judge_schema \
  harness.tests.test_progress \
  harness.tests.test_request_retry \
  harness.tests.test_single_model
```

Two additional script-style checks are run directly:

```sh
python harness/tests/test_prompts.py
python harness/tests/test_mock_endpoints.py
```

The prompt check exits after its assertions, so the unit-test command explicitly selects the other test modules rather than importing it through discovery. Local mock-endpoint checks may require permission to bind a local port. These checks do not replace a live model/FHIR reproduction.

See [LICENSE-NOTES.md](LICENSE-NOTES.md) for synthetic-data provenance, third-party components and the stated reuse conditions. No API credentials, downloaded server/database binaries or local Python environments are included.

### Documentation checks for this release

The documented GPT-OSS, Qwen and neutral cross-judge offline analyses completed successfully against the included archives. The original-study `a01` and `a02` quick-start analyses also completed. Dry-run plans were checked for all three YAML configurations. These checks used existing local Python environments; a fresh installation from `requirements.txt`, the full original-study analysis sequence, and live model/FHIR experiments were not executed for this documentation update.
