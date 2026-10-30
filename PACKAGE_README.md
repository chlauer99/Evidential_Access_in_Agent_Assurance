> Configuration scope: only the paper configurations listed in [harness/configs/README.md](harness/configs/README.md) are included. Example and archived-chain configurations described in this historical package guide have been removed.

> Code release note: Paper figure scripts have been removed. `reproduce.py` now runs table analyses only and skips figure verification. Figure-related descriptions below document the original full research package.

# Reproducibility package: "No Results Found": Evidential Access and the Automated Assurance of Agentic Health Information Systems (ECIS 2027)

LLM agents (GPT-4.1, GPT-4.1-mini, DeepSeek V3.2) completed MedAgentBench tasks on a local FHIR server; a rule-based
grader and LLM judges under four evidence conditions (trajectory only, API specification, checklist, read-only record
access) assessed them. This package regenerates every table, figure and headline number of the paper (Level A) and
contains everything needed to re-run the experiments, with the paper's models or with other LLMs (Level B).

## Quick start

```bash
conda env create -f environment-analysis.yml && conda activate ecis2027-analysis   # or any Python >= 3.10 with numpy, pandas, matplotlib
python reproduce.py --level A        # about 4 minutes; writes outputs/ and prints the PASS/FAIL table of verify.py
```
Expected end of the output: `ALL CHECKS PASSED (205 checks)` (17 published tables, 2 figures, 186 manuscript numbers).

| Level | What it does | Needs | Tested here |
|---|---|---|---|
| **A** | recomputes all derived tables and both figures from the archived data (`data/raw`, `data/derived`), then `verify.py` compares them with the published copies (`data/published`) and checks `paper_numbers.csv` | Python only; no network, key or server | yes, from a fresh unzip (see REPRO_REPORT.md) |
| **B** | re-runs the experiments: FHIR server, agents, controls, grading, tracer, provenance, judges, probes, cue, then the Level A analyses on the new runs (`harness/run_pipeline.py`) | FHIR server (4.5 GB image), API keys or local model servers | syntax checks, dry runs, the offline chain test on the archived data and a mock-endpoint test; no live model or server run |

## Folder layout

```
reproduce.py  verify.py  paper_numbers.csv      Level A entry point, checker, the 186 manuscript numbers it checks
analysis/     a01..a14 analysis scripts, config.py (paths, seeds, role slots), common.py (loaders, bootstraps),
              provenance_rules.py, figures/ (published figure scripts)
data/raw/     archived raw outputs (trajectories, judge verdicts, probes, record-access sample)   -> data/README.md
data/derived/ per-attempt tables for the analyses whose raw trajectories are not archived
data/published/ derived CSVs and figures as used in the paper (verification targets only)
outputs/      empty; written by reproduce.py
harness/      Level B: mab_harness/ (experiment code), pipeline/ (steps 3-10), run_pipeline.py, configs/, prompts/,
              scripts/run_all_experiments.ps1|.sh, tests/, mab_tasks/ (300 MedAgentBench tasks)
CHECKSUMS.sha256  LICENSE-NOTES.md  environment-analysis.yml  environment-harness.yml
```

## Level A: exhibit -> script -> output

All scripts read `data/` (or a new run, see Level B step 9) and write `outputs/`. Seeds are fixed in `analysis/config.py`;
every published CSV is reproduced **identically** (same bootstrap draws), so the tolerances in `verify.py`
(0 for counts, 0.005 for rounded proportions, 0.01 for bootstrap limits) are not needed for the archived data.

| Paper exhibit / number | Script | Output file(s) (published counterpart in `data/published/`) |
|---|---|---|
| Attempt x judge-condition table (input of all judge analyses) | a01_attempts_table.py | attempts_by_judge.csv, **judge_attempts.csv** |
| Table 2 (denominators, exclusions); 1,680 attempts; 3,660 / 540 / 418 = 4,618 verdicts | a02_outcome_classes.py, a13 | **analysis_denominators.csv**, outcome_classes.csv, paper_extras.csv |
| 5.1 all-or-nothing tasks (28, 29 of 30; 222 of 300); format-only shares (14-16%) | a02 | task_bimodality.csv, outcome_classes.csv |
| Table 3 mechanisms by agent, F/U marks, 70% / 63% / 55% evidence-gathering shares | a12_mechanism_table.py | table3_mechanisms.csv |
| P1: 505 / 6 / 18 of 529; 98.8% of 511 classifiable; 95.5% of all | a10_provenance.py | **provenance_summary.csv**; provenance_recoded.csv + provenance_recode_check.csv (GPT errors re-coded from raw: 121/121 agree) |
| Table 4 capability comparison (0.60 / 0.58 / 0.42; errors per 100 attempts) | a11_capability_gradient.py | **capability_gradient.csv** |
| Table 4 knowledge probes (0.656 vs 0.075; J = -0.09 and 0.17; 0.60 / 0.47 / 0.94) | a08_probes.py | **probe_summary.csv** |
| Table 4 verification cue (0.68 to 0.51, -0.17 [-0.25, -0.10]; 0.08 to 0.19; 0.20 to 0.22) | a09_cue_effects.py | **cue_effects.csv** |
| Table 5 acceptance by outcome class (ranges), 5.3 | a03_judge_discrimination.py, a13 | judge_summary_all.csv, paper_extras.csv (t5_*) |
| 5.4 J -0.14 to +0.10, +0.10 [-0.002, 0.20], AUROC 0.58, category-fixed J -0.02; discovery 0.10-0.20, certification 0.73-0.86 | a03, a05, a13 | judge_discrimination_all.csv, **judge_discrimination.csv**, **judge_summary.csv**, **judge_reason_validity.csv**, paper_extras.csv |
| Figure 1 (all 15 agent-judge-condition rows) | a05_judge_conditions.py, a14_figures.py | **judge_conditions_summary.csv**, fig_discrimination.png/.pdf |
| 5.5 233 of 240; 5 to 17 of 21; 48 rejected, K named in 36; 77 accepted; 32 accepted; 75 of 98, 2 mention pages; 44 of 48 | a13_paper_extras.py | paper_extras.csv |
| Table 6 paired contrasts (spec, checklist, record access), 479 / 477 / 418 | a06_paired_contrasts.py | **paired_condition_contrasts_pooled.csv**, **paired_condition_contrasts.csv** |
| 5.6 record access: 0.65 to 1.00; +0.43 [0.23, 0.64] and +0.27 [-0.07, 0.62]; 63-70% correct rejected; 137 false alarms, 24 unstored orders; USD 0.0005 to 0.0018 | a04_record_access.py, a06, a13 | **agentic_judge_verdicts.csv**, **agentic_judge_discrimination.csv**, **agentic_judge_readonly.csv**, agentic_judge_sample_check.csv (sample re-drawn with seed 2027: identical), paper_extras.csv |
| 5.7 90% vs 88%, 80% vs 80%; both wrong 29%; kappa 0.67 [0.42, 0.86], -0.19 [-0.48, 0.08], 0.03 [-0.28, 0.31]; joint acceptance 75% vs 26-28% | a07_error_dependence.py | **judge_error_sharing.csv**, **judge_error_kappa_ci.csv**, joint_acceptance.csv, error_acceptance_by_agent_judge.csv |
| Figure 2 (observed detection grid; its numbers are checked individually) | a14_figures.py | fig_detection.png/.pdf |
| Table 7 (design principles) | numbers from a06, a07, a12, a13 | as above |
| Table 1 | theoretical; no data | - |

`paper_numbers.csv` lists each checked number with section, exhibit, source file, row filter, column, tolerance and
notes (e.g. where the paper rounded a 3-decimal CSV value a second time). `verify.py` writes `outputs/verify_report.csv`.
Runtime (16-core laptop): a03 about 120 s and a05 about 60 s (AUROC inside a 2,000-draw task bootstrap), all other
scripts under 10 s; total about 4 minutes.

### Where Level A starts from archived per-attempt tables (known gap)
The raw trajectories of the DeepSeek V3.2 full run (`full_deepseekv32`, 1,200 attempts), of the cue run
(`cue_deepseekv32`) and of the 2026-09-26 smoke runs, and the 300-task control runs (`full_control_replay`,
`full_control_null`) are **not archived**. For them Level A reads `data/derived/full_deepseekv32_mechanisms.csv`,
`cue_deepseekv32_mechanisms.csv`, the DeepSeek rows of `provenance_coding.csv` and `first_query_codes.csv`. Everything
downstream (all judge analyses on the full run, record access, cue effects, probes scoring) is recomputed. See
`data/raw/full_deepseekv32/README.md` for dropping the author's folder in and which scripts then run from raw.
Steps that need the live FHIR server (format-only regrade, mechanism tracer, probe controls) are Level B.

### Version choices (two artefacts with the same file name)
* `judge_attempts.csv`, `judge_summary.csv`, `judge_discrimination.csv`, `judge_reason_validity.csv`: the **09:36 versions**
  (artifact versions e7882c52, aa687c13, 36a9dc03, edbed176; produced by the experiments sub-session with the
  server-graded outcome classes) are the final ones and are in `data/published/`. They include the completed
  GPT-4.1 + API-specification condition (240 verdicts), which the paper reports (Table 6, Figure 1); the 08:19
  versions (b26ce21a, 7e366ab1, 0fdcf7f3, 3e359b00) had dropped that condition while it was incomplete and are kept in
  `data/published/superseded/`. The outcome classes of the 480 pilot attempts are identical in all versions.
  The final paper tables (judge_conditions_summary.csv etc.) were computed from the attempt table in memory; a01-a05
  rebuild it and reproduce both the published tables and the 09:36 files exactly.
* `run_agents.py`: the final version (artifact 0c06d7d6, harness hash d066e39c578e8714) is byte-identical to the one
  that produced the cue run (hash recorded in its `run_config.json`); it is `harness/mab_harness/history/paper_versions/run_agents.py`.
  The pilots were produced with v1 (228702d0, `history/run_agents_v1_pilots_228702d0.py`) and the 30-task controls
  with v0 (a9c10028); the v2 README documents that the prompt, catalogue, round limit, output cap and action parsing
  are byte-identical across versions. The harness_v2 copy (4da8ed34) is kept as `history/run_agents_v2_harness_v2_0b97aed2.py`.
* `judge_runs.py` final (61627064) renders the same neutral prompt as the v1 used for the GPT judges (the only change
  is the `{checks}` slot, empty for the neutral and specification conditions).
* Record-access bootstrap: in the original session the record-access J intervals were drawn from the generator of the
  cue bootstrap (seed 2026, after its 24,000 draws); `common.record_access_rng()` replays this, which is why these
  intervals match exactly.

## Level B: re-run with other LLMs

`harness/run_pipeline.py --config <yaml> [--steps ...] [--dry-run] [--yes]` runs every step of the study in order.
Each step is resumable (the underlying scripts skip finished attempts; a `DONE.json` marker skips finished steps) and
writes to `runs/<config name>/`: raw run folders in `mab_runs/`, per-attempt tables in `derived/`, logs and outputs
in `<NN>_<step>/`. Paid steps print a cost and runtime estimate and stop unless `--yes` is given.

| Step | Script | Inputs | Outputs | Paper exhibit |
|---|---|---|---|---|
| 0 server | mab_harness/fetch_server.py, start_server.py (Windows, no Docker: h2fix `rwdisk:` provider, JDK 17) or `docker run` (Linux/macOS) | pinned image `jyxsu6/medagentbench@sha256:3fb83d7e...` | FHIR server on localhost:8080 | 4.2 |
| 1 agents | mab_harness/run_agents.py | config `agents`, `models`; mab_tasks/ | mab_runs/<role>/ results.jsonl, answers/, _reference/ | 4.3 |
| 2 controls | run_agents.py --agent replay / null | tasks | control_replay, control_null (30 tasks), full_control_* (300) | Table 5, 5.3 |
| 3 grade | pipeline/grade_outcomes.py (analyse_pilot.classify_failures) | run folders, server | derived/outcome_classes_<run>.csv, pilot_outcome_classes.csv | 4.4, Table 2 |
| 4 trace | pipeline/trace_runs.py (trace_mechanisms.py) | run folders, server, full_control_replay | derived/<run>_mechanisms.csv | Table 3, Table 4 |
| 5 provenance | pipeline/code_provenance.py (analysis/provenance_rules.py) | trajectories, classes, mechanisms | derived/provenance_coding.csv | 5.1, Table 3 |
| 6 judges | mab_harness/judge_runs.py (neutral, --with-spec, --prompt verify); pipeline/make_access_sample.py + judge_agentic.py (record access, <= 4 GETs, compact listings) | run folders | mab_runs/<run>/judge_<role>[_spec,_verify,_access].jsonl, record_access/agentic_judge_sample.json | 5.3-5.7, Tables 5-6, Fig. 1 |
| 7 probes | pipeline/build_probes.py, mab_harness/probes.py run | full-run trajectories + tracer table; server (controls) | mab_runs/probes/*.json(l) | Table 4 |
| 8 cue | pipeline/select_cue_tasks.py, run_agents.py --context-suffix, grade/trace, first_query_codes.py | full-run tracer table | mab_runs/cue_deepseekv32, derived/cue_deepseekv32_mechanisms.csv, first_query_codes.csv | Table 4, 5.2 |
| 9 analysis | reproduce.py --level A --raw/--derived/--out/--study | steps 1-8 | runs/<name>/09_analysis/outputs/ (all tables, figures) | all |
| 10 compare | pipeline/compare_report.py (verify.py) | step 9 outputs, data/published, paper_numbers.csv | runs/<name>/10_compare/compare_report.md | all |

`harness/scripts/run_all_experiments.ps1` / `.sh` list the paper's exact commands and settings in order (the same
runs without the orchestrator). `configs/paper.yaml` reproduces the paper's setup; `configs/example_api.yaml`
and `configs/example_local.yaml` show hosted and local models; `configs/chain_test_archived.yaml` is the offline test.

### Role slots
The analyses keep the paper's identifiers as role slots, and a config maps them to models: `pilot_gpt41` and
`pilot_gpt41mini` are two agents of one developer on the 30-task pilot (3 per category, seed 2026, 8 attempts),
`full_deepseekv32` is an agent of a second developer on all 300 tasks (4 attempts); the judge slots `gpt-4.1`,
`gpt-4.1-mini` and `deepseek-v3.2` are the three agents' models used as judges, which yields the self /
same-lineage / cross-developer pairings. Display names and developers come from the config (`runs/<name>/study.json`,
read via `REPRO_STUDY`), so tables and figures carry the new model names.

### Model entries
Every model in `models:` has `name, developer, base_url, api_key_env, model, temperature, max_output_tokens,
extra_body, tpm, rpm, workers, lenient_actions, strip_reasoning, price_in, price_out`. All calls go through the
OpenAI Python client (`base_url` + key from `api_key_env`; an empty `api_key_env` sends the dummy key `EMPTY` for local
servers). Each call records endpoint, served model, upstream provider and quantisation (requested routing, and the
served quantisation where a gateway returns it) in `served_log` (agents) or `call_meta` (judges, probes).

| Endpoint | base_url | Notes and known pitfalls |
|---|---|---|
| OpenAI | (null) | pin dated snapshots (`gpt-4.1-2025-04-14`); reasoning models (o-series, gpt-5) reject `temperature` (run_agents drops it after the first error; judges: set `temperature: -1`) and need a larger `max_tokens` for judges; account TPM limits: set `tpm` |
| OpenRouter | https://openrouter.ai/api/v1 | pin the provider and quantisation with `extra_body: {provider: {quantizations: [fp8], allow_fallbacks: true}}` (paper); the response names the upstream `provider`; `:free` models have low daily caps (the 2026-09-26 smoke runs stopped at them) |
| NVIDIA NIM | https://integrate.api.nvidia.com/v1 | free tier about 40 requests/min: set `rpm`; some models cap `max_tokens` below 4096; some return reasoning inline |
| Groq | https://api.groq.com/openai/v1 | strict free-tier token and request limits (set `tpm`, `rpm`, `workers: 1`); reasoning models (gpt-oss) may return reasoning fields or `<think>` text: `strip_reasoning: true` |
| vLLM | http://localhost:8000/v1 | `--max-model-len` >= 16384 (the first prompt is about 8,000 tokens and grows per round) |
| Ollama | http://localhost:11434/v1 | default context is too small: set `num_ctx` >= 16384 in a Modelfile; `api_key_env: ""` |
| llama.cpp server | http://localhost:8081/v1 | start with `-c 16384`; do not use port 8080 (FHIR server) |
| LM Studio | http://localhost:1234/v1 | load the model with a 16k context |

**The strict action parser.** The original protocol accepts exactly one action per turn starting with `GET`, `POST`
or `FINISH(`; anything else ends the episode (`AGENT_INVALID_ACTION`). Models that write a preamble ("Sure, here is
the request: ...") fail this. `lenient_actions: true` accepts an action after a short preamble and logs how often
(`n_preamble`); this is a protocol variant and should be reported. `strip_reasoning: true` removes `<think>...</think>`
blocks before parsing (agents, judges, probes).

### Quick starts
```bash
conda env create -f environment-harness.yml && conda activate ecis2027-harness
python harness/run_pipeline.py --config harness/configs/paper.yaml --dry-run      # plan, commands, cost estimates
python harness/run_pipeline.py --config harness/configs/paper.yaml --steps 0-2 --yes
python harness/run_pipeline.py --config harness/configs/paper.yaml --steps 3-10 --yes
# hosted models of other developers:   export NVIDIA_API_KEY=... GROQ_API_KEY=...
python harness/run_pipeline.py --config harness/configs/example_api.yaml --steps 0-10 --yes
# local models (start vLLM/Ollama/llama.cpp first):
python harness/run_pipeline.py --config harness/configs/example_local.yaml --steps 0-10 --yes
```
Re-judging only (no FHIR server needed except for record access): copy `data/raw/<run>` to a new folder and run
`MAB_RUNS_DIR=<folder> python harness/mab_harness/judge_runs.py --judge <model> --tag <tag> --runs <run> --base-url ... --api-key-env ...`.

### Costs and runtimes (from the paper's runs)
| Unit | Tokens (prompt / completion) | Cost | Wall time |
|---|---|---|---|
| GPT-4.1 agent attempt | about 8,600 / 90 (7,200 cached) | about USD 0.018 at list price (less with caching) | about 20 s at 27k TPM, 3 workers |
| GPT-4.1-mini agent attempt | about 8,300 / 90 | about USD 0.004 | about 2 s |
| DeepSeek V3.2 agent attempt (OpenRouter, fp8) | similar | about USD 0.0016 (gateway-reported) | a few seconds, 6 workers |
| DeepSeek trajectory-only judge verdict | 1,600-2,500 / 100 | about USD 0.0005 (0.0004-0.0007) | 4-6 s |
| DeepSeek record-access verdict (up to 4 GETs) | 8,500-10,400 / 290 | about USD 0.0018-0.0020 | about 11 s |
| GPT judge verdict (neutral / with specification) | 1,600-2,000 / 80 (spec about 4,900) | about USD 0.004-0.010 (GPT-4.1) | 1-3 s |
| Probe call | about 1,150 / 60 | about USD 0.0002 | 1-2 s |
The whole paper setup is about 2,800 agent attempts, 4,600 judge verdicts and 700 probe calls: roughly USD 15-20 at
list prices before prompt-cache discounts (the dry run prints per-step estimates), and 6-10 hours wall time, dominated
by the GPT-4.1 token-per-minute limit and the 300-task DeepSeek run. The FHIR server download is about 4.5 GB
(about 4 minutes) and the server needs 4 GB of heap and about 80 s to start.

### Caveats
* **Non-determinism.** Agents run at T = 0.8 (8 or 4 attempts per task); a re-run gives different trajectories, so
  the paper's numbers are reproduced only in distribution. Judges run at T = 0 but hosted models are not strictly
  deterministic either. Level A is exact because it re-analyses the archived outputs.
* **Model drift.** Aliases (`gpt-4.1`) move; pin snapshots. OpenRouter routes to different providers unless pinned;
  record `provider` and quantisation (logged per call).
* **POSTs are not persisted** (original protocol): orders are validated and acknowledged but not written, so a judge
  with record access cannot find an order the agent placed (24 of 137 record-access false alarms).
* **The 23% floor.** The rule-based grader passes an agent that does nothing on 23% of tasks (7 of 30 pilot tasks,
  70 of 300), because it accepts an empty answer where no order is due; report success against this floor.
* The checklist encodes failure modes found in the pilot; with other agents new failure modes need not be covered.
* A new study needs steps 3-4 online (FHIR server); the offline modes exist only for the archived chain test.

## Tests
* `python harness/tests/test_prompts.py`: the prompt files in `harness/prompts/` equal the prompts in the code.
* `python harness/tests/test_mock_endpoints.py`: agent episodes, judge_runs.py and probes.py against a mock
  OpenAI-compatible endpoint and a mock FHIR endpoint that replay archived outputs (no key, no server).
* `python harness/run_pipeline.py --config harness/configs/chain_test_archived.yaml`: the archived pilot runs,
  controls and verdicts through steps 3-10 (offline grading with stored grader verdicts, hand-traced mechanisms,
  provenance re-coded from raw, record-access sample re-drawn), ending with the comparison against the paper.
See REPRO_REPORT.md for what was executed and what was only syntax-checked.

## Secrets
API keys are read from environment variables only (`api_key_env`); nothing in this package contains a key, a
personal path or a user name (scan in REPRO_REPORT.md).

## GPT-OSS via local vLLM

See [VLLM_START.md](VLLM_START.md) for the configured endpoint, model-ID check, isolated smoke run and full single-model pipeline. Configuration: `harness/configs/vllm_gpt_oss.yaml`. The `single_model` design runs one 300-task main cohort (four attempts each), one judge under four evidence conditions, full-task controls, probes and cue reruns; no pilot cohorts or pilot data are used. Dedicated single-model CSV analyses replace the paper-specific three-model reports.
