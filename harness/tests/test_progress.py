"""Offline progress tests; no models or Docker required."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

H = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module
monitor = load('progress_monitor',H/'scripts/monitor_progress.py')
pipeline = load('progress_pipeline',H/'run_pipeline.py')

class ProgressTests(unittest.TestCase):
    def test_completion_requires_every_valid_marker(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for i, name in enumerate(monitor.STEPS):
                folder = base / f'{i:02d}_{name}'
                folder.mkdir()
                (folder / 'DONE.json').write_text('{"finished_utc":"2026-10-08T08:00:00Z"}')
            self.assertTrue(monitor.finished(base, range(11)))
            last = base / '10_compare/DONE.json'
            for content in ('{', '{}', '[]'):
                last.write_text(content)
                self.assertFalse(monitor.finished(base, range(11)))
            last.unlink()
            self.assertFalse(monitor.finished(base, range(11)))
            self.assertTrue(monitor.finished(base, [0, 1]))

    def test_monitor_exits_without_sleep_and_preserves_issue_report(self):
        output = io.StringIO()
        with patch.object(sys, 'argv', ['monitor']), \
             patch.object(monitor, 'finished', return_value=True), \
             patch.object(monitor, 'snapshot', return_value='87 ungültig; Abbrüche=1'), \
             patch.object(monitor.time, 'sleep') as sleep, contextlib.redirect_stdout(output):
            monitor.main()
        sleep.assert_not_called()
        self.assertIn('87 ungültig', output.getvalue())
        self.assertIn('Lauf abgeschlossen', output.getvalue())

    def test_monitor_waits_until_complete(self):
        with patch.object(sys, 'argv', ['monitor']), \
             patch.object(monitor, 'finished', side_effect=[False, True]), \
             patch.object(monitor, 'snapshot', return_value='Status'), \
             patch.object(monitor.time, 'sleep') as sleep, contextlib.redirect_stdout(io.StringIO()):
            monitor.main()
        sleep.assert_called_once_with(5)

    def test_partial_records_and_retries(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'run/results.jsonl'; p.parent.mkdir()
            rows = [dict(task_id='t1',attempt=0,status='API_ERROR'),
                    dict(task_id='t1',attempt=0,status='COMPLETED',passed=True),
                    dict(task_id='t2',attempt=0,status='AGENT_INVALID_ACTION',passed=False),
                    dict(task_id='t3',attempt=0,status='API_ERROR')]
            p.write_text(''.join(json.dumps(r)+'\n' for r in rows)+'{"partial":')
            text = monitor.agent_line(p,4)
            self.assertIn('2/4 beendet (50.0%)',text)
            self.assertIn('Abbrüche=1',text)
            self.assertIn('API-Fehler offen=1',text)
            self.assertIn('offiziell bestanden=1',text)

    def test_before_first_run(self):
        cfg = monitor.miniyaml.load(H/'configs/gpt_oss_120b_exp_2.yaml')
        with tempfile.TemporaryDirectory() as td:
            text = monitor.snapshot(cfg,Path(td))
            self.assertIn('0/1200',text)
            self.assertIn('Auswahl noch nicht erstellt',text)

    def test_live_log_and_exit_status(self):
        with tempfile.TemporaryDirectory() as td:
            p = pipeline.Pipeline(H/'configs/gpt_oss_120b_exp_2.yaml',False,True,Path(td))
            log = p.stepdir(1)/'test.log'
            log.write_text('old output\n')
            display = io.StringIO()
            with contextlib.redirect_stdout(display):
                status = p.run(1,[sys.executable,'-c','print("new progress", flush=True)'],log_name='test.log')
            self.assertEqual(status,0)
            self.assertIn('new progress',display.getvalue())
            self.assertNotIn('old output',display.getvalue())
            self.assertIn('old output\nnew progress',log.read_text())
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                p.run(1,[sys.executable,'-c','raise SystemExit(3)'],log_name='failure.log')

if __name__ == '__main__':
    unittest.main()
