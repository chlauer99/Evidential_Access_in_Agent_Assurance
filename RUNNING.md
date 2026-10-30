# Run new experiments

This repository contains source code, prompts, configurations, all 300 benchmark task instructions and metadata, reference graders, Python requirements, and server setup sources. Selected paper model outputs and run results are included; see `runs/README.md` for the selection and missing original-study raw data.

## Setup

1. Install Python 3.11 and Docker (or Java 17 for the non-Docker server).
2. From the repository root, create the environment:

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

3. Copy a configuration in `harness/configs/` and set the model endpoint, model name and API-key environment-variable name. Keep credentials outside the repository. The checked-in vLLM configurations contain deployment-specific local endpoint addresses.
4. Inspect the execution plan, then start a new run:

```sh
python harness/run_pipeline.py --config harness/configs/gpt_oss_120b_exp_2.yaml --runs-root outputs/new-experiments --steps 0-9 --dry-run
python harness/run_pipeline.py --config harness/configs/gpt_oss_120b_exp_2.yaml --runs-root outputs/new-experiments --steps 0-9 --yes
```

Use a new configuration `name` for a new experiment. Model calls can incur costs. The pipeline downloads/starts the configured benchmark server and generates run-specific references, probe instances and evaluation selections during execution.

## Included and excluded files

- Included: prompts (`harness/prompts/`), model/pipeline configurations, FHIR function catalogue (`funcs_v1.json`), benchmark instructions and task metadata, source code, dependency definitions and usage documentation.
- Archived inputs: the three selected `runs/` directories and original-study inputs in `data/raw/` and `data/derived/`.
- Excluded: other experiments, generated figure files, local environments, server downloads and compiled Java artifacts.
- Original-study reproduction may require additional historical data missing from the local archive. The optional step 10 comparison also requires archived DeepSeek results; use steps 0–9 for new experiments without archived data (see pipeline `--help`).

See [README.md](README.md) for the full usage guide and [LICENSE-NOTES.md](LICENSE-NOTES.md) for third-party component provenance.
