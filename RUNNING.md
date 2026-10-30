# Run new experiments

This repository contains source code, prompts, configurations, all 300 benchmark task instructions and metadata, reference graders, environment definitions, and server setup sources. Historical model outputs and run results are intentionally excluded.

## Setup

1. Install Conda and Docker (or Java 17 for the non-Docker server).
2. From the repository root, create the environment:

```sh
conda env create -f environment-harness.yml
conda activate ecis2027-harness
```

3. Copy a configuration in `harness/configs/` and set the model endpoint, model name and API-key environment-variable name. Keep credentials outside the repository. The checked-in vLLM configurations contain deployment-specific local endpoint addresses.
4. Inspect the execution plan, then start a new run:

```sh
python harness/run_pipeline.py --config harness/configs/vllm_gpt_oss.yaml --steps 0-9 --dry-run
python harness/run_pipeline.py --config harness/configs/vllm_gpt_oss.yaml --steps 0-9 --yes
```

Use a new configuration `name` for a new experiment. Model calls can incur costs. The pipeline downloads/starts the configured benchmark server and generates run-specific references, probe instances and evaluation selections during execution.

## Included and excluded files

- Included: prompts (`harness/prompts/`), model/pipeline configurations, FHIR function catalogue (`funcs_v1.json`), benchmark instructions and task metadata, source code, dependency definitions and usage documentation.
- Excluded: `runs/`, `mab_runs/`, archived `data/`, generated `outputs/`, logs, local environments, server downloads and compiled Java artifacts.
- Archived paper reproduction and archived chain-test configurations require historical data that are intentionally absent here. The optional step 10 comparison also requires archived DeepSeek results; use steps 0–9 for new experiments without archived data (see pipeline `--help`).

See `LICENSE-NOTES.md` for third-party component provenance and `VLLM_START.md` for deployment details.
