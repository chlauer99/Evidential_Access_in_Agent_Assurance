# Licence and data provenance

These notes describe the source code and selected experiment archives included in this repository. They retain the study package's stated reuse conditions and distinguish the included material from separately downloaded dependencies.

## Synthetic benchmark records

The benchmark FHIR records originate from the MedAgentBench virtual electronic health record, a HAPI FHIR server with a preloaded H2 database of synthetic patients. Patient names, record identifiers, dates and laboratory values in benchmark trajectories are synthetic; they are not records collected from real patients.

The server image pinned by the experiment code is:

```
jyxsu6/medagentbench@sha256:3fb83d7ed71c5476f9eb6212bd440a909ef7505922bbc757dc488a8fc0701966
```

Synthetic record excerpts may appear in saved agent trajectories, judge rationales and knowledge-probe material under `data/raw/` and `runs/`. Human-subject material and the study's second-coder material are not included.

## Included third-party material

| Component | Location | Provenance and licence information |
|---|---|---|
| Benchmark task instructions, metadata and shared reference solver/grader code | `harness/mab_tasks/` | MedAgentBench, Stanford Machine Learning Group. The existing package provenance records the task-package source as the Hugging Face dataset [DCAgent/medagentbench](https://huggingface.co/datasets/DCAgent/medagentbench). The [upstream MedAgentBench code licence](https://github.com/stanfordmlgroup/MedAgentBench/blob/main/LICENSE) is MIT, copyright 2025 Stanford Machine Learning Group. Dataset provenance and any accompanying terms remain distinct from the upstream code licence. |
| Original task loop, function catalogue and agent prompt | `harness/mab_harness/original_medagentbench_task.py`, `harness/mab_harness/funcs_v1.json`, `harness/prompts/agent_prompt.txt` | Derived from the [MedAgentBench repository](https://github.com/stanfordmlgroup/MedAgentBench); the upstream MIT copyright and permission notices apply to that material. |
| Historical copies of experiment code | `harness/mab_harness/history/` | Retained to document the implementations used during the original experiments. Any embedded upstream material retains its original provenance and notices. |

MedAgentBench is described by Jiang et al. (2025), *NEJM AI* 2(9), AIdbp2500144. This repository's notes do not replace upstream copyright notices or grant additional rights to third-party material.

## Server and compiled dependencies: not included

The FHIR server binary, synthetic H2 database, downloaded JARs and compiled Java classes are not checked in. `harness/mab_harness/fetch_server.py` downloads the server files from the pinned image. The non-Docker startup code extracts compilation dependencies into `harness/mab_harness/h2fix/lib/` and builds the local file-system provider from `harness/mab_harness/h2fix/src/`.

The original dependency provenance identifies HAPI FHIR and Spring components as Apache-2.0 components and H2 as MPL-2.0 / EPL-1.0 material. Their own distributed notices govern those components; downloading them does not make them part of this repository's study-code reuse statement. Python dependencies are listed in `requirements.txt` and retain their individual licences.

## Included model outputs

| Archive | Models / experiment |
|---|---|
| `data/raw/` and `data/derived/` | Available original GPT-4.1, GPT-4.1-mini and DeepSeek V3.2 outputs and derived study tables; OpenAI API and OpenRouter were used for the original hosted-model experiments. |
| `runs/gpt_oss_120b_exp_2/` | GPT-OSS 120B agent attempts and self-judge experiment, served through the recorded OpenAI-compatible local endpoint. |
| `runs/qwen3_8_27b_exp_3/` | Qwen3.8 27B agent attempts and self-judge experiment, served through the recorded OpenAI-compatible local endpoint. |
| `runs/cross_judge_exp_1/` | Reciprocal GPT-OSS/Qwen judging of saved attempts from the two source runs. |

These archives contain generated outputs, synthetic benchmark excerpts, execution metadata, evaluation verdicts and derived analyses. Provider terms and model-specific terms remain relevant to their originating components; these notes do not apply one common third-party licence to all outputs. Recorded model identifiers and serving settings are preserved in the YAML configurations and archived run files.

The original DeepSeek archive is incomplete. See [runs/README.md](runs/README.md) for the missing raw trajectories and controls; derived tables are included where available. Excluded smoke runs and the separate fresh GPT-OSS-agent/Qwen-judge run are not part of this release.

## Study-authored code and documentation

The existing study-package reuse statement is retained: analysis code, pipeline code, configurations and documentation written for the study may be reused for research with attribution to **“No Results Found”: Evidential Access and the Automated Assurance of Agentic Health Information Systems** (ECIS 2027).

This update does not introduce a new blanket software licence or relicense third-party components. The study reuse statement does not override the upstream licences and notices described above.

## Credentials and execution metadata

Credentials are supplied through environment variables; local environment files, private keys and downloaded server binaries are excluded. Import checks found no matches for the common API-token and private-key patterns scanned. This is a description of those checks, not a claim that every possible secret format was verified.

Archived execution records can retain original local paths, endpoint addresses and run identifiers as provenance. These records are historical metadata, not portable configuration defaults. Adapt endpoint settings before running new experiments and keep credentials outside the repository.
