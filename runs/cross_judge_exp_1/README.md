# Cross-judging on saved attempts (P5)

Judge-only experiment. No agent runs, no FHIR server calls. Neutral prompt, trajectory only.
Each attempt set is a copy of results.jsonl + answers/ from the confirmed runs; judge settings
are identical to those used in the source runs (same model IDs, temperature, max tokens, extra body).

| Folder | Attempts from | New judge | Existing judge (source run) |
|---|---|---|---|
| on_gpt_oss_attempts | gpt_oss_120b_exp_2 (O/O) | Qwen/Qwen3.8-27B | GPT-OSS-120B |
| on_qwen_attempts | qwen3_8_27b_exp_3 (Q/Q) | openai/gpt-oss-120b | Qwen3.8-27B |

Commands: see pipeline_commands.txt. Run from ecis2027_epidemische_Fehler/.

Analysis (kappa, joint acceptance, agent x judge cells; truth labels from the source runs):

    python harness/pipeline/analyse_cross_judge.py --runs-root runs --out runs/cross_judge_exp_1/outputs

Environment note: environment-harness.yml does not list tqdm, which harness/mab_harness/progress.py
imports; it was installed into ecis2027-harness with pip before these runs.
