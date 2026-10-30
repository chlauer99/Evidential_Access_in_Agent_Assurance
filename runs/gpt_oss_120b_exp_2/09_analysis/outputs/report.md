# Single-model experiment: GPT-OSS 120B

Main run: 1200 attempts, 300 tasks. Expected: 1200 attempts.
No pilot data or cross-model comparisons are used.

All four evidence conditions target the same completed main-run attempts; record access is not sampled by error type.
Judge accuracy: pass/format_only = correct; substantive answer errors, omissions and commissions = errors.
Wrong-order cases, do-nothing passes and unfinished attempts are excluded from judge accuracy but counted in outcome_classes.csv.
Missing/invalid verdicts are reported per condition. Paired contrasts use only attempts valid in both conditions.
95% descriptive intervals: 1,000 task-cluster bootstrap draws, seed 2027; no multiplicity correction.
Descriptive outcomes, mechanisms, provenance and substantive error rates include wrong-order cases, as in manuscript Table 3. Only judge discrimination excludes them, as in Table 2.

Outputs: outcome_classes.csv, outcomes_by_category.csv, mechanisms.csv, provenance_summary.csv,
judge_attempts.csv, judge_summary.csv, paired_conditions.csv, controls.csv, probes_summary.csv, cue_effects.csv.

Probe scores are descriptive; no between-model independence or capability comparisons are claimed.
Cue results compare task-averaged rates on the selected tasks, not attempt-to-attempt pairs.
The inherited tracer/provenance rules remain benchmark-specific; human validation is still needed.
