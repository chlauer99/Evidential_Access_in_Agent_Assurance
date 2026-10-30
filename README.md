# Evidential Access in Agent Assurance

Experiment and analysis code for **“No Results Found”: Evidential Access and the Automated Assurance of Agentic Health Information Systems** (ECIS 2027).

## Contents

The repository root contains:

- `harness/`: experiment pipeline, agent runners, judges, prompts, model configurations, benchmark tasks, server setup sources, and existing tests.
- `analysis/`: outcome, provenance, judge, and cross-model analyses.
- `reproduce.py` and `verify.py`: archived-data reproduction and verification entry points.
- Environment definitions, usage documentation, and third-party provenance notes.
- `runs/vllm_gpt_oss_main/audit_unclassified/review.py`: additional audit code, retained at its original relative path.

## Run new experiments

See [RUNNING.md](RUNNING.md) for setup and execution. From the repository root:

```sh
conda env create -f environment-harness.yml
conda activate ecis2027-harness
python harness/run_pipeline.py --config harness/configs/gpt_oss_120b_exp_2.yaml --steps 0-9 --dry-run
```

Configure the endpoint and model before starting a live run. Supply API credentials through environment variables.

## Scope of this initial code release

This branch imports the local experiment source files, including previously untracked scripts. Historical run results, archived datasets, manuscript files, generated figures, local environments, credentials, downloaded server files, and compiled dependencies are excluded. Benchmark task instructions, metadata, reference solvers, and graders are included as experiment inputs.

The package README and reproduction report describe the original full research package. Archived-data reproduction (`reproduce.py --level A`), historical comparisons, and scripts reading archived runs require data that are not included in this initial code release. Existing historical checksum manifests are omitted because they describe that full package.

See [the package documentation](PACKAGE_README.md) and [third-party provenance notes](LICENSE-NOTES.md).

## Import validation

All 113 imported Python source files passed syntax parsing. A scan for common API-token and private-key patterns found no matches. The initial system-Python test run passed 20 of 23 discovered tests; two test modules could not load because `requests` and `httpx` were absent, and one historical comparison test requires the excluded archived dataset. Live model experiments were not rerun as part of this source import.

Paper figure generation scripts are excluded from this repository. The analysis runner generates tables and skips figure verification.

The retained paper configurations and their run mapping are listed in [harness/configs/README.md](harness/configs/README.md).
