# MedAgentBench pilot harness (E3, proposal 3)

Runs LLM agents on MedAgentBench against a local copy of the official FHIR server, with no Docker and
nothing installed on the user's machine. Everything runs inside the Claude Science sandbox.

## What's here

| File | Role |
|---|---|
| `fetch_server.py` | Streams the pinned MedAgentBench image (`jyxsu6/medagentbench@sha256:3fb83d7e…`) from Docker Hub and extracts only the FHIR server (`main.war`), its config, and the preloaded synthetic-patient H2 database (4.47 GB). About 4 minutes. |
| `start_server.py` | Starts the HAPI FHIR server with Java 17 on `localhost:8080` (about 80 s to ready). |
| `h2fix/` | Small H2 file-system provider (`rwdisk:`), loaded through the server's extra-classes path. Needed because, inside restricted Windows sandboxes, Java's `Files.isWritable` reports false even though writes succeed, and H2 then opens the database read-only, which breaks every FHIR search. Vendor files are unchanged. |
| `run_agents.py` | Agent runner and grader. |
| `funcs_v1.json`, `original_medagentbench_task.py` | Function catalogue and task loop from the original MedAgentBench repository, kept for provenance. |

## Protocol (what the agent sees and does)

The **original published MedAgentBench protocol**, reproduced verbatim (Jiang et al., NEJM AI 2025):
- one message containing the published prompt, the published function catalogue, the task context and the question;
- one text action per turn: `GET …`, `POST <url>` plus a JSON payload, or `FINISH([...])`; anything else ends the episode;
- GET requests get `&_format=json` appended and go only to the local FHIR server (any other host is refused);
- POST requests (orders) are validated as JSON and acknowledged but **not written to the database**, exactly as in the original code, so repeated attempts can't contaminate each other;
- at most 8 rounds (the paper's setting).

Grading uses the official reference solver and grader shipped with the task package (`evaluate_submission`). Each attempt is also coded against the reference answer as **omission** (a required order not placed), **commission** (an order placed when none was due), wrong order/answer, wrong answer, or no finish.

*Deviation from protocol §4b:* this uses the original published agent setup, not the v2 tool set, because the v2 tools are not available in reproducible form. So the GPT-4.1 check should be compared with published original-protocol results, not with v2's 91%.

## Validation already done (no API key needed)

| Control | Agent | Pilot pass rate (30 tasks) | Reading |
|---|---|---|---|
| Positive | Replays the official reference answer through the text protocol | **30/30 (100%)** | Server, protocol, order recording and grader agree |
| Negative | Answers `FINISH([])` and does nothing | **7/30 (23%)** | Floor set by grader leniency (below) |

**Grader leniency (a finding in itself).** Every do-nothing pass is a check-only conditional task (categories 5, 9, 10: "check X; order Y only if needed") where no order was due. The official grader accepts an empty answer there by design. So an agent that takes no action scores 23% on the pilot set. For E3, report success rates against this floor, and treat "passed without acting" as a separate outcome. It is also a small, concrete example of the permissive assurance errors the paper is about.

Pilot set: 3 tasks per category (seed 2026), 30 tasks in all; 8 of them require placing an order.

## Running agents (after the API key is stored)

The key is read from the `OPENAI_API_KEY` environment variable. It is never printed, logged or written to disk, and it is sent only to the OpenAI API.

```
# 0. smoke test: 3 attempts, measures tokens per attempt
python run_agents.py --agent openai --model gpt-4.1 --tasks task1_1,task3_4,task10_10 --n 1 --run-name smoke_gpt41

# 1. anchor run: GPT-4.1, pilot set, 8 attempts per task (240 attempts), with a hard token budget
python run_agents.py --agent openai --model gpt-4.1 --tasks pilot --n 8 --temperature 0.8 \
       --workers 6 --max-total-tokens 8000000 --run-name pilot_gpt41

# 2. optional second agent (a current mid-tier GPT model), same settings
python run_agents.py --agent openai --model <model-id> --tasks pilot --n 8 --temperature 0.8 \
       --workers 6 --max-total-tokens 8000000 --run-name pilot_<model>
```

Re-running a command resumes where it stopped. `--price-in/--price-out` (USD per million tokens) add a cost estimate to the summary.

**Outputs per run** (`mab_runs/<run-name>/`): `run_config.json` (settings, task list, harness and catalogue hashes, image digest, start time), `results.jsonl` (one row per attempt: pass/fail, grader detail, failure type, rounds, GET/POST counts, tokens, latency, **served model snapshot**), `answers/*.json` (full trajectories; E3's judges grade these), `summary.json` (pass@1, pass@8, by category, failure types, tokens) and `per_task.csv`.

## Rebuilding after the workspace is cleared

```
python fetch_server.py          # ~4 min, re-downloads the pinned image files
python start_server.py          # ~80 s; keep the process alive while agents run
```


## v2 changes (2026-09-24, experiments track)

Protocol unchanged. The verbatim prompt, `funcs_v1.json`, one text action per turn, 8 rounds, temperature 0.8, the
4096-token output cap and the action parsing in `run_episode` are byte-identical to v1 (`run_agents.py` sha256
prefix 228702d0cf368f21, the version that produced the pilot runs). Checked: `PROMPT` strings are equal; the built
first-turn prompts are equal for all 300 tasks; and the only change in `run_episode` is one extra key in its return
dict. The full diff is in `run_agents_v1_to_v2.diff`.

| File | Change |
|---|---|
| `run_agents.py` | `--base-url`, `--api-key-env`, `--extra-body` (JSON or `@file.json`) for any OpenAI-compatible endpoint, e.g. OpenRouter. Each response is logged (`served_log`: response id, served model, upstream provider, gateway-reported cost, tokens, finish reason). Per attempt it adds `providers`, `served_models` and `cost_usd_reported`; per run the summary adds `providers` and `cost_usd_reported_by_gateway`. Non-OpenAI endpoints get the same 4096 cap as `max_tokens`, the field OpenRouter documents for its upstream providers. A 200 response with no `choices` raises, so the attempt becomes `API_ERROR` and is rerun. |
| `seed_from_pilot.py` | Copies the latest valid pilot rows for attempts 0..k-1, plus their answer files, into a new run folder (`reused_from` is set), so `--tasks all --n 4` reruns only the rest. |
| `judge_report_cached.py` | Runs `judge_report.py` with outcome classes read from a saved, server-graded `judge_attempts.csv`, for use when the FHIR server is unreachable. It reproduces the six existing discrimination rows exactly, CIs included. |
| `openrouter_route_*.json` | OpenRouter provider-routing bodies: Claude goes through the Anthropic first-party endpoint (fallbacks allowed); DeepSeek goes only to fp8 endpoints. |

### Full-benchmark run plan (step 3; needs the FHIR server and valid keys)

```
python seed_from_pilot.py pilot_gpt41     full_gpt41     --k 4
python seed_from_pilot.py pilot_gpt41mini full_gpt41mini --k 4
# OpenAI (OPENAI_API_KEY); never two gpt-4.1 jobs at once
python run_agents.py --agent openai --model gpt-4.1      --tasks all --n 4 --temperature 0.8 --workers 3 --tpm 27000  --price-in 2   --price-out 8   --run-name full_gpt41
python run_agents.py --agent openai --model gpt-4.1-mini --tasks all --n 4 --temperature 0.8 --workers 6 --tpm 180000 --price-in 0.4 --price-out 1.6 --run-name full_gpt41mini
# OpenRouter (key in OPENROUTER_API_KEY, copied from the OPENROUTE credential for the call only)
python run_agents.py --agent openai --model anthropic/claude-sonnet-4.6 --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY --extra-body @openrouter_route_claude-sonnet-4.6.json --tasks all --n 4 --temperature 0.8 --workers 4 --price-in 3 --price-out 15 --run-name full_claude-sonnet-4.6
python run_agents.py --agent openai --model deepseek/deepseek-v3.2      --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY --extra-body @openrouter_route_deepseek-v3.2.json      --tasks all --n 4 --temperature 0.8 --workers 6 --price-in 0.269 --price-out 0.40 --run-name full_deepseek-v3.2
# controls (no API)
python run_agents.py --agent replay --tasks all --n 1 --run-name full_control_replay
python run_agents.py --agent null   --tasks all --n 1 --run-name full_control_null
```
Smoke test first (one task per category, one attempt), e.g. `--tasks task1_1,task2_1,...,task10_1 --n 1 --run-name smoke_<slug>`.
