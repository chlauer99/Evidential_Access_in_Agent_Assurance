#!/usr/bin/env python3
"""Complete spec/checklist/access in the existing cross-judge experiment.

Defaults to a read-only plan. --execute starts judge calls only; never agents,
controls, grading, probes, cue runs, or the full pipeline.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MAIN = 'full_deepseekv32'
PAIRS = {
    'on_gpt_oss_attempts': ('gpt_oss_120b_exp_2', 'Qwen/Qwen3.8-27B', 'qwen3_8_27b',
                            'http://192.168.92.194:10122/v1', 4096, 3,
                            {'chat_template_kwargs': {'enable_thinking': False}}),
    'on_qwen_attempts': ('qwen3_8_27b_exp_3', 'openai/gpt-oss-120b', 'gpt-oss-120b',
                         'http://192.168.92.194:10121/v1', 8192, 1,
                         {'reasoning_effort': 'low'}),
}


def validate(raw, source, tag):
    """Require the original saved input, not a new or partially copied run."""
    target = raw / MAIN
    original = source / 'mab_runs' / MAIN
    for name in ['results.jsonl']:
        if not (original / name).is_file():
            raise ValueError(f'Source input missing: {original / name}')
        if (target / name).exists() and (target / name).read_bytes() != (original / name).read_bytes():
            raise ValueError(f'Saved inputs differ from source: {target / name}')
    rows = [json.loads(line) for line in (original / 'results.jsonl').read_text().splitlines() if line.strip()]
    for row in rows:
        if row['status'] == 'API_ERROR':
            continue
        name = str(row['answer_file']).replace('\\', '/').split('/')[-1]
        if not (original / 'answers' / name).is_file():
            raise ValueError(f'Source trajectory missing: {name}')
        if (target / 'answers' / name).exists() and (target / 'answers' / name).read_bytes() != (original / 'answers' / name).read_bytes():
            raise ValueError(f'Trajectory differs from source: {name}')
    neutral = target / f'judge_{tag}.jsonl'
    if not neutral.is_file():
        raise ValueError(f'Existing cross-judge baseline missing: {neutral}')
    sample = source / 'mab_runs/record_access/agentic_judge_sample.json'
    entries = json.loads(sample.read_text())
    keys = {(r['task_id'], int(r['attempt'])) for r in rows if r['status'] != 'API_ERROR'}
    if not entries or any(r['run'] != MAIN or (r['task_id'], int(r['attempt'])) not in keys for r in entries):
        raise ValueError(f'Invalid source record-access selection: {sample}')
    return sample, len(entries)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runs-root', type=Path, default=ROOT / 'runs')
    ap.add_argument('--pair', choices=['both', *PAIRS], default='both')
    ap.add_argument('--conditions', nargs='+', choices=['spec', 'checklist', 'access'],
                    default=['spec', 'checklist', 'access'])
    ap.add_argument('--qwen-url', default=PAIRS['on_gpt_oss_attempts'][3])
    ap.add_argument('--gpt-oss-url', default=PAIRS['on_qwen_attempts'][3])
    ap.add_argument('--execute', action='store_true', help='Execute the plan (default: print only)')
    a = ap.parse_args()
    plans = []
    inputs = []
    # Validate BOTH pairs before starting any calls.
    for folder, (source_name, model, tag, _, cap, workers, extra) in PAIRS.items():
        if a.pair != 'both' and a.pair != folder:
            continue
        runs = a.runs_root.resolve()
        raw = runs / 'cross_judge_exp_1' / folder / 'mab_runs'
        sample, count = validate(raw, runs / source_name, tag)
        inputs.append((raw / MAIN, runs / source_name / 'mab_runs' / MAIN))
        url = a.qwen_url if folder == 'on_gpt_oss_attempts' else a.gpt_oss_url
        common = ['--judge', model, '--workers', str(workers), '--temperature', '0',
                  '--max-tokens', str(cap), '--base-url', url, '--api-key-env', '',
                  '--extra-body', json.dumps(extra), '--strip-reasoning', '--structured-output']
        print(f'\n{folder}: existing trajectories; {count} source record-access entries', flush=True)
        for condition in dict.fromkeys(a.conditions):
            if condition == 'access':
                args = ['judge_agentic.py', *common, '--tag', tag + '_access', '--sample', str(sample),
                        '--max-queries', '4', '--summary-file', str(raw.parent / f'{tag}_access_status.json')]
            else:
                flags = ['--with-spec'] if condition == 'spec' else ['--prompt', 'verify']
                args = ['judge_runs.py', *common, '--tag', tag, '--runs', MAIN, *flags]
            cmd = [sys.executable, str(ROOT / 'harness/mab_harness' / args[0]), *args[1:]]
            env = dict(os.environ, MAB_RUNS_DIR=str(raw), MAB_TASKS_DIR=str(ROOT / 'harness/mab_tasks'))
            print('MAB_RUNS_DIR=' + shlex.quote(str(raw)) + ' ' + shlex.join(cmd), flush=True)
            plans.append((cmd, env))
    if a.execute:
        # Restore missing input copies only; never overwrite verdicts or source files.
        for target, original in inputs:
            target.mkdir(parents=True, exist_ok=True)
            if not (target / 'results.jsonl').exists():
                shutil.copy2(original / 'results.jsonl', target / 'results.jsonl')
            (target / 'answers').mkdir(exist_ok=True)
            for answer in (original / 'answers').glob('*.json'):
                if not (target / 'answers' / answer.name).exists():
                    shutil.copy2(answer, target / 'answers' / answer.name)
        for cmd, env in plans:
            subprocess.run(cmd, env=env, cwd=ROOT, check=True)
    else:
        print('\nPlan only. Add --execute to run. Access requires the original FHIR server at localhost:8080.')


if __name__ == '__main__':
    main()
