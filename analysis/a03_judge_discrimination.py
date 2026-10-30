"""a03 - Judge assurance profiles, discrimination and reason validity (Sections 5.3-5.5, Table 5).

Reconstructs harness/mab_harness/judge_report.py (summary, discrimination, reason_validity).
Inputs : attempt x judge table (common.attempts)
Outputs: outputs/judge_summary.csv, judge_discrimination.csv, judge_reason_validity.csv
             GPT judges on the pilot attempts (= the published, final versions of these files)
         outputs/judge_discrimination_all.csv   all agent runs and judge conditions (Section 5.4)
         outputs/judge_summary_all.csv          pass rates by outcome class incl. controls (Table 5)
Runtime: about 2-4 minutes (AUROC inside a 2,000-draw bootstrap for 15 agent-judge cells).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import attempts, discrimination, reason_validity, summary, write

GPTJ = ["gpt-4.1", "gpt-4.1-mini", "gpt-4.1_spec", "gpt-4.1-mini_spec"]
G = attempts(judges=GPTJ, runs=("pilot_gpt41", "pilot_gpt41mini"), controls=True)
write(summary(G), "judge_summary.csv")
write(discrimination(G), "judge_discrimination.csv")
write(reason_validity(G), "judge_reason_validity.csv")

A = attempts(judges=GPTJ + ["deepseek-v3.2", "deepseek-v3.2_verify"])
write(summary(A), "judge_summary_all.csv")
write(discrimination(A), "judge_discrimination_all.csv")
write(reason_validity(A), "judge_reason_validity_all.csv")
