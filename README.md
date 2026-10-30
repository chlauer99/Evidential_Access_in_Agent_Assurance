# Evidential Access in Agent Assurance

Experiment and analysis source code for **“No Results Found”: Evidential Access and the Automated Assurance of Agentic Health Information Systems** (ECIS 2027).

This repository contains the MedAgentBench experiment pipeline, agent runners, reference grading, LLM judges, knowledge probes, analysis code, and configurations for the selected paper experiments. Experiment trajectories, verdicts, run logs, derived tables and manuscript-number results are not included. All benchmark patient records are synthetic. Paper figure scripts and manuscript files are not included.

## Contents

1. [Installation](#1-installation)
2. [Repository layout](#2-repository-layout)
3. [Experiment configurations, protocol and metrics](#3-which-experiments-are-included)
4. [Analysis of your own or separately supplied data](#4-analyse-existing-results-offline)
5. [New experiments and configuration](#5-run-new-experiments)
6. [Cross-judge evaluation](#6-run-cross-judge-evaluations)
7. [Code-only scope](#7-code-only-scope)
8. [Checks and provenance](#8-checks-and-provenance)
9. [Troubleshooting](#9-troubleshooting)

## 1. Installation

Use **Python 3.11**, the recommended version for the experiment pipeline. Run all commands below from the repository root. Examples use a macOS/Linux shell.

```sh
git clone https://github.com/chlauer99/Evidential_Access_in_Agent_Assurance.git
cd Evidential_Access_in_Agent_Assurance
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Until this release is merged into `main`, run `git switch codex/publish-experiment-code` after cloning to use the publication branch.

On Windows PowerShell, create the environment with `py -3.11 -m venv .venv` and activate it with `.venv\Scripts\Activate.ps1`.

`requirements.txt` covers the Python packages used by the experiment and analysis code, including `tqdm` for progress reporting and `httpx` for request/retry tests. It specifies dependency lower bounds, not a locked copy of the historical execution environment.

Alternatively, create a Python environment with Conda and install the same requirements:

```sh
conda create -n agent-assurance python=3.11
conda activate agent-assurance
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
| `runs/` (generated, ignored) | Default experiment output directories |
| `data/raw/` (external, ignored) | Optional original-study raw inputs supplied separately |
| `data/derived/` (external, ignored) | Optional original-study coded tables supplied separately |
| `analysis/` | Original-study table analyses and shared analysis utilities |
| `reproduce.py` / `verify.py` | Original-study table runner and verification tools |

The identifiers `full_deepseekv32` and `cue_deepseekv32` are also used inside the Qwen and GPT-OSS runs as internal role names. In those directories they do **not** mean that DeepSeek was the model; the corresponding YAML and `run_config.json` identify the model used.

## 3. Which experiments are included?

Only the configurations and implementation are included. The run-directory names below identify expected output locations, not checked-in results.

| Experiment | Configuration | Expected output/input location (not included) |
|---|---|---|
| GPT-4.1, GPT-4.1-mini and DeepSeek V3.2 | `harness/configs/paper.yaml` | `data/raw/` and `data/derived/` |
| GPT-OSS 120B agents with GPT-OSS self-judge | `harness/configs/gpt_oss_120b_exp_2.yaml` | `runs/gpt_oss_120b_exp_2/` |
| Qwen3.8 27B agents with Qwen self-judge | `harness/configs/qwen3_8_27b_exp_3.yaml` | `runs/qwen3_8_27b_exp_3/` |
| Reciprocal judging of those saved GPT-OSS and Qwen attempts | `harness/configs/cross_judge_exp_1/` | `runs/cross_judge_exp_1/` |

The self-judge configurations cover trajectory-only, API-specification, checklist and read-only record-access conditions, plus controls, probes and verification-cue runs. The cross-judge analysis described below compares the trajectory-only condition. A separate script can add specification, checklist and record-access verdicts.

Smoke runs, superseded Qwen configurations and the separate fresh GPT-OSS-agent/Qwen-judge experiment are excluded. See [the configuration mapping](harness/configs/README.md).

Typical files created by an experiment (not checked in):

- `mab_runs/<role>/results.jsonl`: attempt results; `answers/`: saved trajectories.
- `mab_runs/<role>/run_config.json`: recorded execution settings.
- `judge_<tag>.jsonl`: judge verdicts; `_spec`, `_verify` and `_access` identify additional evidence conditions.
- `derived/`: graded outcomes, error mechanisms and other coded inputs.
- `09_analysis/outputs/`: saved summary tables and reports.
- `pipeline_commands.txt`, stage logs and `DONE.json`: execution records and completion markers.

### Task protocol and evidence conditions

The runner uses the original MedAgentBench text-action protocol and function catalogue (`harness/mab_harness/funcs_v1.json`). Each turn contains one `GET`, `POST` or `FINISH(...)` action, with at most eight rounds under the paper configurations. The agent receives the task context, question, instructions and function catalogue. The strict parser rejects actions that do not start in the expected form.

`GET` actions query the benchmark FHIR server. `POST` actions are validated and acknowledged but **are not persisted to the database**, following the original protocol. Consequently, a record-access judge cannot establish that an order was placed simply by looking for a newly stored order. Replay and null controls provide reference-answer and do-nothing baselines.

| Judge condition | Evidence supplied | Verdict suffix |
|---|---|---|
| Trajectory only | Task and saved agent trajectory | no condition suffix |
| API specification | Trajectory plus the API specification | `_spec` |
| Checklist | Trajectory plus the verification checklist | `_verify` |
| Record access | Read-only FHIR queries in addition to the supplied task/trajectory evidence | `_access` |

The conditions actually applied to each model/run are specified by its YAML; the original three-model study does not evaluate every possible combination. Record-access samples use seed 2027 and a maximum of four queries in the retained configurations.

### How outcome and judge measures are defined

The reference grader evaluates the task result; the analysis further distinguishes outcome classes and error mechanisms. In the selected self-judge analyses, `pass` and `format_only` count as correct work for judge discrimination; `substantive_answer_error`, `omission` and `commission` count as errors. `wrong_order`, `pass_without_acting` and `no_finish` are excluded from those judge measures. Descriptive error rates also include `wrong_order`, so their denominator and meaning differ from judge discrimination.

- **Error discovery:** the fraction of eligible erroneous attempts rejected by the judge.
- **Correct certification:** the fraction of eligible correct attempts accepted by the judge.
- **Youden's J:** error discovery + correct certification − 1.
- **Paired condition contrasts:** differences on attempts with valid verdicts under both conditions.
- **Cross-judge dependence:** joint acceptance of errors and agreement of judge-error indicators on the same attempts.

Missing and invalid verdicts are reported separately. Open-weight self-judge and cross-judge uncertainty estimates resample tasks, using 1,000 bootstrap draws and seed 2027. Original-study scripts have their own fixed seeds and bootstrap settings in `analysis/config.py`; they should not be assumed to use the same procedure for every measure.

## 4. Analyse existing results offline

**Prerequisite:** first execute the experiments or supply compatible data separately at the paths shown below. These commands do not work against a fresh clone without those inputs. They write analyses to ignored `outputs/` directories and do not make model calls.

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

These analyses produce descriptive outcome tables, judge metrics, paired condition comparisons and reports. They require the corresponding `mab_runs/` trajectories/verdicts and `derived/` graded tables. Once those inputs exist, no model calls or regrading against the server are needed.

### Reciprocal cross-judge analysis

```sh
python harness/pipeline/analyse_cross_judge.py \
  --runs-root runs \
  --out outputs/cross_judge_exp_1
```

This joins saved self-judge and cross-judge verdicts on the same attempts and reports joint error acceptance and agreement measures. It currently analyses the **neutral / trajectory-only** condition.

### Original GPT-4.1 / GPT-4.1-mini / DeepSeek analyses

Supply the original-study inputs under `data/raw/` and `data/derived/`, or point `--raw` and `--derived` at a completed original-design run. Then start with the attempt and outcome tables:

```sh
python reproduce.py --level A --only a01 a02 --out outputs/original-study --no-verify
```

To run the configured original-study table analyses (`a01`–`a13`):

```sh
python reproduce.py --level A --out outputs/original-study --no-verify
```

The full table sequence includes bootstrap calculations and can take several minutes. `--only` selects script prefixes, for example `--only a03 a05`. Figure generation is removed. The open-weight and cross-judge analyses above are separate and are not run by `reproduce.py`.

Use `--no-verify` unless you have also supplied the original published comparison files. `verify.py` expects reference CSVs under `data/published/` and, for manuscript-number checks, a separately supplied `paper_numbers.csv`. Neither is included.

### Original-study analysis map

These scripts belong to the original GPT-4.1 / GPT-4.1-mini / DeepSeek analysis path, not the separate open-weight summaries. Run them through `reproduce.py` so input/output overrides are passed consistently.

| Script | Purpose | Main output files |
|---|---|---|
| `a01_attempts_table.py` | Join attempts, judge conditions and outcome labels | `attempts_by_judge.csv`, `judge_attempts.csv` |
| `a02_outcome_classes.py` | Denominators, outcome classes and task bimodality | `analysis_denominators.csv`, `outcome_classes.csv`, `task_bimodality.csv` |
| `a03_judge_discrimination.py` | Judge acceptance, discrimination and rationale coding | `judge_summary.csv`, `judge_discrimination.csv`, `judge_reason_validity.csv` |
| `a04_record_access.py` | Record-access verdicts, discrimination and sample checks | `agentic_judge_verdicts.csv`, `agentic_judge_discrimination.csv`, `agentic_judge_readonly.csv` |
| `a05_judge_conditions.py` | Compare evidence conditions | `judge_conditions_summary.csv` |
| `a06_paired_contrasts.py` | Paired evidence-condition effects | `paired_condition_contrasts.csv`, `paired_condition_contrasts_pooled.csv` |
| `a07_error_dependence.py` | Shared errors and joint acceptance | `judge_error_sharing.csv`, `judge_error_kappa_ci.csv`, `joint_acceptance.csv` |
| `a08_probes.py` | Knowledge-probe performance | `probe_summary.csv` |
| `a09_cue_effects.py` | Verification-cue effects | `cue_effects.csv` |
| `a10_provenance.py` | Grounded/fabricated/unclassified provenance | `provenance_summary.csv`, `provenance_recoded.csv` |
| `a11_capability_gradient.py` | Descriptive capability/error comparison | `capability_gradient.csv` |
| `a12_mechanism_table.py` | Error-mechanism table | `table3_mechanisms.csv` |
| `a13_paper_extras.py` | Additional manuscript quantities | `paper_extras.csv` |

Input/output overrides are `--raw`, `--derived`, `--out` and optional `--study` (display-name mapping). For example, a completed new original-design run can be analysed using its `mab_runs/` and `derived/` directories. For Qwen/GPT-OSS use `analyse_single.py`, as shown above, because those runs have one agent cohort rather than the original pilot/full-run combination.

The optional `paper_numbers.csv` input records original manuscript quantities, source tables, row filters and tolerances. After supplying that file and the published CSV targets separately, verification without figures can be requested with:

```sh
python verify.py --outputs outputs/original-study --published data/published --skip-figures
```

This is an optional verification path requiring those additional files, not a command supported by this code-only repository alone. No fixed number of successful reproduction checks is claimed for a fresh clone.

## 5. Run new experiments

### Configure the model and output location

Choose one of the three YAML configurations. Set `models.<identifier>.base_url`, `model`, and `api_key_env` for your deployment. The private-network endpoint addresses in the archived configurations must be replaced with reachable endpoints. An empty `api_key_env` is used for the local endpoints in the selected runs.

For `paper.yaml`, supply `OPENAI_API_KEY` and `OPENROUTER_API_KEY` through your environment. Never put keys in YAML files or commit them. Keep the recorded task counts, generation settings and judge settings unchanged when reproducing the paper setup; changes define a different experiment.

Use a separate output root for independent experiments. The pipeline resumes existing attempts and skips stages with `DONE.json`, so reusing an output directory resumes work instead of starting a clean experiment.

### Configuration fields

| YAML field | Meaning |
|---|---|
| `name` | Run directory name under the selected output root |
| `design: single_model` | One full agent cohort and one judge; used for GPT-OSS and Qwen |
| `fhir.mode`, `fhir.base_url` | Docker, automatic/non-Docker or external benchmark server configuration |
| `models.<id>.model`, `base_url`, `api_key_env` | Model identifier, OpenAI-compatible endpoint and environment variable containing its key |
| `temperature`, `max_output_tokens`, `extra_body` | Agent generation budget and provider/model-specific request settings |
| `workers`, `tpm`, `rpm` | Concurrency and optional token/request throttles |
| `lenient_actions`, `strip_reasoning` | Optional parsing behaviour; changing these can alter the protocol |
| `agents` | Model, task subset and number of attempts for each role |
| `controls` | Replay/null control cohorts |
| `judges` | Judge model, evidence conditions, verdict token budget and structured-output settings |
| `record_access` | Judge, query limit, sample seed and concurrency |
| `probes`, `cue` | Knowledge-probe sampling and verification-cue reruns |
| `expect_paper` | Optional reference-comparison behaviour; not a guarantee that new stochastic runs match archived numbers |

`paper.yaml` uses 30 pilot tasks (three per category, seed 2026) with eight attempts each for GPT-4.1 and GPT-4.1-mini, and all 300 tasks with four attempts each for DeepSeek. GPT-OSS and Qwen each use all 300 tasks with four attempts and no pilot cohort.

GPT-OSS retains `reasoning_effort: low`; Qwen retains `chat_template_kwargs: {enable_thinking: false}` and its configured context-capacity requirement. The judge and agent token budgets are distinct. Follow the retained YAML rather than substituting a generic model recipe.

The local model endpoints use an empty `api_key_env`; the client supplies a dummy key for an endpoint that does not require authentication. If your deployment requires a key, configure a named environment variable instead. Endpoints must support the structured-output settings requested by the judge code. API aliases, provider routing and model-serving versions can change outputs; inspect recorded served-model/provider metadata when comparing runs.

The `price_in` / `price_out` values and pipeline estimates are historical configuration values. Zero prices in local-model configurations do not measure hardware or hosting cost. Runtime depends on serving capacity, rate limits and retries; no historical dollar estimate is a current price guarantee.

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

Cross-judging reuses saved agent trajectories rather than starting new agent attempts. For a fresh experiment, prepare copies of the source `results.jsonl` and `answers/` in the two cross-judge target directories. No saved attempts or copied trajectories are included. Both source experiments must have been completed, or their outputs supplied separately, before cross-judging.

The neutral-condition commands and request settings are in [harness/configs/cross_judge_exp_1/](harness/configs/cross_judge_exp_1/). After adapting their endpoint addresses, execute them with:

```sh
bash harness/configs/cross_judge_exp_1/neutral_commands.sh
```

These commands call the model endpoints and write to the expected cross-judge output paths under `runs/cross_judge_exp_1/`. Existing valid results may be reused rather than regenerated. The commands themselves are retained as experiment instructions; they contain no saved verdicts.

For additional specification, checklist and record-access conditions, first inspect the plan:

```sh
python harness/scripts/backfill_cross_judge.py
```

Add `--execute` to make model calls. Endpoint and run-location overrides are described in [BACKFILL_CROSS_JUDGE.md](harness/scripts/BACKFILL_CROSS_JUDGE.md). Record access additionally requires the source record-access selections and the benchmark FHIR server. Adding these verdicts does not automatically extend the neutral-only cross-judge analysis.

## 7. Code-only scope

Included: source code, experiment YAML files, request-setting JSON files, prompts, the FHIR function catalogue, benchmark task instructions/metadata/reference graders, historical code snapshots, dependency requirements and documentation.

Excluded: all saved experiment runs, agent trajectories, judge verdicts, probe answers, controls, result summaries, derived tables, logs, execution markers, manuscript-number tables, paper figures, server binaries and local Python environments. `runs/`, `data/`, `mab_runs/` and `outputs/` are ignored by Git.

Benchmark tasks and reference solutions are experiment inputs, not results generated by this study. They remain in `harness/mab_tasks/`. Historical source code remains in `harness/mab_harness/history/` as requested; the historical cross-model comparison script that required an excluded experiment has been removed.

Original archived data would need to be obtained separately for exact reanalysis of the paper's outputs. Running the configurations produces new model outputs, which need not match the original trajectories or paper numbers.

## 8. Checks and provenance

Existing automated checks can be run with:

```sh
python -m unittest -v \
  harness.tests.test_fhir_urls \
  harness.tests.test_judge_schema \
  harness.tests.test_progress \
  harness.tests.test_request_retry
```

The single-model test module additionally contains a historical comparison test that requires `data/derived/full_deepseekv32_mechanisms.csv`; supply that input separately before running the full module.

The prompt check can be run directly:

```sh
python harness/tests/test_prompts.py
```

The prompt check exits after its assertions, so the unit-test command selects modules explicitly. `harness/tests/test_mock_endpoints.py` replays historical pilot trajectories and probe outputs; it requires the corresponding separately supplied data under `data/raw/` and permission to bind local ports. It is not a self-contained test of a fresh code-only clone. These checks do not replace a live model/FHIR reproduction.

The original agent implementations and other paper-era snapshots are retained under `harness/mab_harness/history/`; version identifiers are preserved in the snapshot filenames. The current configurable runners and these historical snapshots serve different purposes. `harness/scripts/run_all_experiments.sh` and `.ps1` document the original manual execution sequence; the YAML-driven pipeline is the recommended entry point for new runs.

See [LICENSE-NOTES.md](LICENSE-NOTES.md) for synthetic-data provenance, third-party components and the stated reuse conditions. The benchmark material derives from MedAgentBench; downloaded HAPI FHIR/H2 components have separate terms. Consult the provenance notes before redistributing third-party material. No API credentials, downloaded server/database binaries or local Python environments are included.

### Validation scope

Configuration dry-runs can be checked without experiment data or live model calls. Offline analysis examples require user-generated or separately supplied outputs. Earlier analysis checks used data that are no longer included in this code-only release; they are not proof that a fresh clone contains everything needed for exact paper reproduction. A fresh dependency installation and live model/FHIR experiments have not been performed for this documentation update.

## 9. Troubleshooting

| Symptom | Check / action |
|---|---|
| `ModuleNotFoundError` | Activate the intended environment and run `python -m pip install -r requirements.txt` using that interpreter. `tqdm` is needed for progress output. |
| Model endpoint cannot be reached | Replace the archived private-network URLs with your endpoint. Check its model identifier and use `python harness/scripts/check_endpoint.py --config <yaml>` for a live preflight; this may make model calls. |
| Structured-output/schema error | Verify endpoint support for the configured judge schemas. A successful ordinary chat request does not establish schema support. |
| FHIR server cannot be reached | Check Docker/Java, port 8080, `fhir.base_url`, and the selected server mode. Record-access and online grading need the populated benchmark server. |
| Missing trajectories, verdicts or derived tables | No experiment outputs are shipped. Run the appropriate experiment first or supply compatible data separately; check the analysis input paths. |
| `verify.py` cannot find reference files | Use `--no-verify` for analysis only. Full verification requires separately supplied `data/published/` targets and manuscript-number inputs. |
| A new run skips work | Check its output root, configuration `name`, `DONE.json` markers and existing attempt files. Use a fresh output root to start independently of previous work. |
| Rate limits, retries or incomplete verdict counts | Inspect stage logs, request settings and status files. Resume the same run for unfinished work, and report missing/invalid verdicts rather than treating them as passes. |

Reanalysing fixed archived outputs and generating new model outputs are different reproducibility goals. Agent sampling, model-serving behaviour and upstream providers can yield different trajectories on a fresh run, even with the same configuration. Keep separately supplied original data unchanged and report any model, endpoint, reasoning, parsing or sampling changes alongside new results.
