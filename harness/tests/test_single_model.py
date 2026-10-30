"""Offline tests for the pilot-free pipeline and its statistical denominators.
Run: python -m unittest discover -s harness/tests -p test_single_model.py
"""
import contextlib
import csv
import importlib.util
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

H = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(H / "pipeline"))
import analyse_single as analysis
import miniyaml
spec = importlib.util.spec_from_file_location("single_pipeline", H / "run_pipeline.py")
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


class SingleModelTests(unittest.TestCase):
    def test_missing_verdict_status_allows_next_step(self):
        with tempfile.TemporaryDirectory() as td, contextlib.redirect_stdout(io.StringIO()):
            p = pipeline.Pipeline(H / "configs/vllm_gpt_oss.yaml", False, True, Path(td))
            def judge_step(n):
                (p.stepdir(n) / "test_access_status.json").write_text(json.dumps(
                    {"status": "completed_with_missing_verdicts", "missing_new": 2}))
            with patch.object(p, "s6_judges", side_effect=judge_step), patch.object(p, "s7_probes") as following:
                p.go([6, 7])
                following.assert_called_once_with(7)
            marker = json.loads((p.stepdir(6) / "DONE.json").read_text())
            self.assertEqual(marker["status"], "completed_with_missing_verdicts")
            self.assertEqual(marker["record_access"]["test_access_status"]["missing_new"], 2)

    def test_plan_has_no_pilot_calls(self):
        with contextlib.redirect_stdout(io.StringIO()):
            p = pipeline.Pipeline(H / "configs/vllm_gpt_oss.yaml", True, False, None)
            p.go(list(pipeline.STEPS))
        commands = '\n'.join(cmd for _, cmd in p.log)
        self.assertNotIn('pilot', commands)
        self.assertNotIn('api.openai.com', commands)
        self.assertNotIn('openrouter', commands)
        agents = [cmd for step, cmd in p.log if step == 1]
        self.assertEqual(len(agents), 1)
        self.assertIn('--tasks all --n 4', agents[0])
        controls = [cmd for step, cmd in p.log if step == 2]
        self.assertEqual(len(controls), 2)
        self.assertTrue(all('--tasks all' in cmd for cmd in controls))
        judges = [cmd for step, cmd in p.log if step == 6 and '/judge_runs.py' in cmd]
        self.assertEqual(len(judges), 9)
        self.assertEqual(sum('--runs full_deepseekv32' in cmd for cmd in judges), 3)
        self.assertEqual(sum('--runs full_control_replay' in cmd for cmd in judges), 3)
        self.assertEqual(sum('--runs control_null' in cmd for cmd in judges), 3)
        self.assertIn('--all-run full_deepseekv32', commands)
        self.assertIn('--continue-on-errors', commands)
        self.assertIn('--summary-file', commands)
        self.assertIn('analyse_single.py', commands)
        self.assertIn('--single-run full_deepseekv32', commands)

    def test_original_plan_unchanged(self):
        with contextlib.redirect_stdout(io.StringIO()):
            p = pipeline.Pipeline(H / "configs/paper.yaml", True, False, None)
            p.go(list(pipeline.STEPS))
        self.assertFalse(p.single)
        self.assertEqual(sum(step == 1 for step, _ in p.log), 3)
        self.assertTrue(any('reproduce.py' in cmd for step, cmd in p.log if step == 9))

    def test_accuracy_denominators_and_pairs(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); raw = base / 'raw'; der = base / 'derived'; out = base / 'out'
            der.mkdir(); (raw / analysis.MAIN).mkdir(parents=True)
            rows = []
            for i, cls in enumerate(['pass', 'format_only', 'wrong_order', 'substantive_answer_error', 'no_finish', 'pass_without_acting']):
                rows.append(dict(task_id=f'task1_{i+1}', attempt=0, category='task1', official_pass=cls=='pass',
                                 refined_class=cls, mechanism='order_content_error' if cls=='wrong_order' else '', locus='action'))
            analysis.write_csv(der / f'{analysis.MAIN}_mechanisms.csv', rows, list(rows[0]))
            analysis.write_csv(der / 'provenance_coding.csv', [], ['provenance'])
            # Neutral misses the eligible error; checklist detects it but rejects one correct answer.
            # Spec: a valid but excluded wrong_order verdict, one invalid error verdict, missing correct verdicts.
            verdicts = {'': ['pass','pass','pass','pass'], '_verify':['fail','pass','fail','fail'],
                        '_spec':[None,None,'fail','invalid'], '_access':['pass','pass','fail','fail']}
            for suffix, vs in verdicts.items():
                data = [dict(task_id=f'task1_{i+1}', attempt=0, verdict=v) for i,v in enumerate(vs) if v is not None]
                (raw / analysis.MAIN / f'judge_gpt-oss-120b{suffix}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in data))
            config = miniyaml.load(H / 'configs/vllm_gpt_oss.yaml')
            with contextlib.redirect_stdout(io.StringIO()):
                analysis.analyse(config, raw, der, out)
                analysis.compare(out, base / 'compare')
            report = {r['condition']: r for r in analysis.read_csv(out / 'judge_summary.csv')}
            self.assertEqual(report['neutral']['eligible'], '3')
            self.assertEqual(report['neutral']['n_errors'], '1')  # wrong_order is unclassified
            self.assertEqual(float(report['neutral']['error_discovery']), 0)
            self.assertEqual(float(report['record_access']['youden_j']), 1)
            self.assertEqual(report['spec']['missing_verdicts'], '2')
            self.assertEqual(report['spec']['invalid_verdicts'], '1')
            self.assertEqual(report['spec']['correct_certification'], '')
            paired = analysis.read_csv(out / 'paired_conditions.csv')
            checklist_j = next(r for r in paired if r['condition']=='checklist' and r['measure']=='youden_j')
            self.assertEqual(float(checklist_j['difference']), .5)
            self.assertTrue(all(r['n_pairs']=='0' for r in paired if r['condition']=='spec'))
            counts = {r['outcome']: int(r['count']) for r in analysis.read_csv(out / 'outcome_classes.csv')}
            self.assertEqual(counts['wrong_order'], 1)
            self.assertNotIn('unclassified', counts)
            self.assertIn('order_content_error', (out / 'mechanisms.csv').read_text())
            summary = json.loads((out / 'summary.json').read_text())
            self.assertEqual(summary['substantive_error_rate'], 2 / 6)
            self.assertEqual(analysis.read_csv(out / 'cue_effects.csv'), [])
            self.assertFalse((der / 'pilot_outcome_classes.csv').exists())

    def test_no_error_or_no_correct_subset_is_not_zero(self):
        self.assertIsNone(analysis.stats([])['youden_j'])
        result = analysis.stats([dict(truth='correct', verdict='pass')])
        self.assertIsNone(result['error_discovery'])
        self.assertEqual(result['correct_certification'], 1)
        self.assertEqual(analysis.interval([], lambda r: 0), (None, None))

    def test_record_access_frame_needs_no_pilot_or_judge_files(self):
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td) / 'raw'
            run = raw / analysis.MAIN
            run.mkdir(parents=True)
            records = [dict(task_id='task1_1', attempt=0, status='API_ERROR'),
                       dict(task_id='task1_1', attempt=0, status='COMPLETED'),
                       dict(task_id='task1_2', attempt=0, status='COMPLETED'),
                       dict(task_id='task1_3', attempt=0, status='AGENT_INVALID_ACTION')]
            (run / 'results.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
            subprocess.run([sys.executable, str(H / 'pipeline/make_access_sample.py'),
                            '--runs-dir', str(raw), '--derived', str(Path(td) / 'derived'),
                            '--all-run', analysis.MAIN], check=True, capture_output=True)
            sample = json.loads((raw / 'record_access/agentic_judge_sample.json').read_text())
            self.assertEqual({r['task_id'] for r in sample}, {'task1_1', 'task1_2'})
            self.assertEqual(len(sample), 2)

    def test_empty_cue_selection_does_not_run_agents(self):
        with tempfile.TemporaryDirectory() as td:
            p = pipeline.Pipeline(H / 'configs/vllm_gpt_oss.yaml', False, True, Path(td))
            def fake_run(n, cmd, **kwargs):
                Path(cmd[cmd.index('--out') + 1]).write_text('')
            with patch.object(p, 'run', side_effect=fake_run) as run, contextlib.redirect_stdout(io.StringIO()):
                p.s8_cue(8)
            self.assertEqual(run.call_count, 1)
            self.assertTrue((p.stepdir(8) / 'SKIPPED.json').exists())


if __name__ == '__main__':
    unittest.main()
