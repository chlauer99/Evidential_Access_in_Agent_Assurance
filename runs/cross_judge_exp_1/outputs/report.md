# Cross-judge analysis (P5)

Two judges on the same saved attempts; neutral prompt, trajectory only.
Errors: substantive_answer_error, omission, commission. Correct: pass, format_only.
Excluded: wrong_order, pass_without_acting, no_finish; invalid or missing verdicts.
kappa: Cohen's kappa on 'verdict disagrees with the reference standard' (as in a07_error_dependence.py).
Joint acceptance: share of substantive errors accepted by both judges.
95% descriptive intervals: 1,000 task-cluster bootstrap draws, seed 2027; no multiplicity correction.
Self-preference compares acceptance of own vs other model's errors on different attempt sets;
differences in error mix between the agents are not controlled.

Outputs: agent_judge_cells.csv, judge_error_dependence.csv.
