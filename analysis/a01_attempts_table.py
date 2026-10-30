"""a01 - Attempt x judge-condition table (inputs of every judge analysis).

Inputs : data/raw/<run>/judge_<condition>.jsonl, data/raw/control_*/results.jsonl,
         data/derived/pilot_outcome_classes.csv (server-regraded classes of the 480 pilot attempts),
         data/derived/full_deepseekv32_mechanisms.csv (classes of the 1,200 DeepSeek V3.2 attempts)
Outputs: outputs/attempts_by_judge.csv  all runs, all 7 judge conditions, controls (not published; inspection)
         outputs/judge_attempts.csv     GPT-judge subset on the pilot attempts = published judge_attempts.csv
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import attempts, write

A = attempts()
write(A, "attempts_by_judge.csv")
G = attempts(judges=["gpt-4.1", "gpt-4.1-mini", "gpt-4.1_spec", "gpt-4.1-mini_spec"],
             runs=("pilot_gpt41", "pilot_gpt41mini"), controls=True)
write(G, "judge_attempts.csv")
