# Licence and data notes

## No protected health information
All patient data in this package are **synthetic**. The FHIR records, patient names, MRNs, dates and laboratory
values come from the MedAgentBench virtual EHR (a HAPI FHIR server with a pre-loaded H2 database of synthetic
patients, Docker image `jyxsu6/medagentbench@sha256:3fb83d7ed71c5476f9eb6212bd440a909ef7505922bbc757dc488a8fc0701966`).
No real patient, clinician or institution is represented. The agent trajectories, judge rationales and probe
answers in `data/raw/` contain only these synthetic records and model outputs. No human-subject data are included
(the second-coder material of the study is not part of this package).

## Third-party components
| Component | Where | Source and licence |
|---|---|---|
| MedAgentBench tasks (300 task folders: instructions, metadata, reference solver `refsol.py`, grader `medagentbench_logic.py`) | `harness/mab_tasks/` | Jiang et al. (2025), NEJM AI 2(9), AIdbp2500144; code repository github.com/stanfordmlgroup/MedAgentBench (listed as MIT licence). The task package was obtained from the Hugging Face dataset `DCAgent/medagentbench`; check its dataset card for terms before redistribution. |
| Original task loop and prompt | `harness/mab_harness/original_medagentbench_task.py`, `funcs_v1.json`, `prompts/agent_prompt.txt` | verbatim from the MedAgentBench repository (MIT), kept for provenance |
| FHIR server and synthetic database | not included; `fetch_server.py` downloads them from the pinned Docker image | MedAgentBench / HAPI FHIR (Apache 2.0) |
| H2 and Spring Boot jars (extracted class files) | `harness/mab_harness/h2fix/lib/` | from the server's `main.war`; H2 (MPL 2.0 / EPL 1.0), Spring (Apache 2.0); used only to compile the two-class `rwdisk:` file-system provider in `h2fix/src/` |
| Model outputs | `data/raw/**/judge_*.jsonl`, `answers/`, `probes/*.jsonl` | generated with GPT-4.1, GPT-4.1-mini (OpenAI API) and DeepSeek V3.2 (via OpenRouter); subject to the providers' terms of use for outputs |

## This package
Analysis code, pipeline code, configs and documentation written for the study may be reused for research with
attribution to the paper ("No Results Found": Evidential Access and the Automated Assurance of Agentic Health
Information Systems, ECIS 2027). No API keys, credentials or personal paths are included (see REPRO_REPORT.md,
secret scan).
