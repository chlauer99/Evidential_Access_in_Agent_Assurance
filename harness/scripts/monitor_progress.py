"""Read-only terminal progress monitor; works alongside an already running pipeline.
No model/server calls, no third-party dependencies. Ctrl+C stops only this monitor.
Automatically exits after all selected steps have valid completion markers.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import sys
import time

H = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(H / 'pipeline'))
import miniyaml
STEPS = ['server', 'agents', 'controls', 'grade', 'trace', 'provenance', 'judges', 'probes', 'cue', 'analysis', 'compare']


def finished(base, steps):
    """Partially written or invalid markers must not trigger premature exit."""
    for i in steps:
        try:
            marker = json.loads((base / f'{i:02d}_{STEPS[i]}' / 'DONE.json').read_text())
            if not isinstance(marker, dict) or not marker.get('finished_utc'):
                return False
        except (OSError, json.JSONDecodeError):
            return False
    return True


def selected_steps(value):
    try:
        result = set()
        for part in value.split(','):
            bounds = [int(x) for x in part.split('-')]
            if len(bounds) == 1:
                result.add(bounds[0])
            elif len(bounds) == 2 and bounds[0] <= bounds[1]:
                result.update(range(bounds[0], bounds[1] + 1))
            else:
                raise ValueError
        if not result or not result <= set(range(len(STEPS))):
            raise ValueError
        return sorted(result)
    except ValueError:
        raise argparse.ArgumentTypeError('Schritte als 0-10 oder 0,1 angeben (zulässig: 0 bis 10).')


def records(path):
    """Ignore an incomplete last JSONL line while a worker is writing it."""
    if not path.exists():
        return []
    result = []
    with path.open(encoding='utf-8', errors='replace') as f:
        for line in f:
            try:
                r = json.loads(line)
                if isinstance(r, dict):
                    result.append(r)
            except json.JSONDecodeError:
                continue
    return result


def latest(rows):
    return {(r.get('task_id'), r.get('attempt')): r for r in rows}


def total(tasks, attempts=1):
    n = {'all': 300, 'pilot': 30}.get(str(tasks))
    return (n if n is not None else len(str(tasks).split(','))) * int(attempts)


def agent_line(path, expected):
    rows = records(path)
    # Match resume semantics: a later API failure must not erase a finished attempt.
    done = latest([r for r in rows if r.get('status') != 'API_ERROR'])
    last = latest(rows)
    api_pending = sum(r.get('status') == 'API_ERROR' and k not in done for k, r in last.items())
    statuses = Counter(r.get('status') for r in done.values())
    complete = statuses.get('COMPLETED', 0)
    passed = sum(bool(r.get('passed')) for r in done.values())
    pct = f'{100*len(done)/expected:.1f}%' if expected else '?'
    return (f'{path.parent.name}: {len(done)}/{expected} beendet ({pct}); '
            f'regulär={complete}, Abbrüche={len(done)-complete}, API-Fehler offen={api_pending}, '
            f'offiziell bestanden={passed}')


def snapshot(config, base):
    raw = base / 'mab_runs'
    lines = [f'Fortschritt · {datetime.now().astimezone():%Y-%m-%d %H:%M:%S %Z}', str(base), '']
    done = [f'{i}:{name}' for i, name in enumerate(STEPS) if (base / f'{i:02d}_{name}' / 'DONE.json').exists()]
    lines += ['Schrittmarker: ' + (', '.join(done) or 'noch keine'), '', 'Agenten / Kontrollen:']
    for run, a in config['agents'].items():
        lines.append('  ' + agent_line(raw / run / 'results.jsonl', total(a['tasks'], a['attempts'])))
    ctl = config.get('controls') or {}
    for run in ctl.get('judged', []) + ctl.get('full', []):
        n = total('all' if run in ctl.get('full', []) else ctl.get('tasks', 'pilot'))
        lines.append('  ' + agent_line(raw / run / 'results.jsonl', n))
    lines += ['', 'KI-Prüfungen (Nenner = bisher abgeschlossene Agenten-/Kontrollversuche):']
    for tag, judge in config['judges'].items():
        for condition, suffix in [('neutral',''),('spec','_spec'),('verify','_verify'),('access','_access')]:
            runs = list(config['agents']) if condition == 'access' and judge.get('access') else judge.get(condition, [])
            for run in runs:
                eligible = {k for k,r in latest(records(raw/run/'results.jsonl')).items() if r.get('status') == 'COMPLETED'}
                if condition == 'access':
                    sp = raw/'record_access/agentic_judge_sample.json'
                    try:
                        eligible = {(r['task_id'],r['attempt']) for r in json.loads(sp.read_text()) if r['run']==run}
                    except (FileNotFoundError,json.JSONDecodeError):
                        lines.append(f'  {tag}/{condition}/{run}: Auswahl noch nicht erstellt')
                        continue
                js = latest(records(raw/run/f'judge_{tag}{suffix}.jsonl'))
                valid = sum(r.get('verdict') in {'pass','fail'} for k,r in js.items() if k in eligible)
                invalid = sum(r.get('verdict') not in {'pass','fail'} for k,r in js.items() if k in eligible)
                missing = len(eligible - js.keys())
                lines.append(f'  {tag}/{condition}/{run}: {valid}/{len(eligible)} gültig; {invalid} ungültig; {missing} fehlen')
    lines += ['', 'Zusatzversuche:']
    for inst, result in [('probes_instances.json','probes_deepseekv32.jsonl'),('probes_controls.json','probes_deepseekv32_controls.jsonl')]:
        try:
            count = len(json.loads((raw/'probes'/inst).read_text())) * config.get('probes',{}).get('samples',3)
        except (FileNotFoundError,json.JSONDecodeError):
            count = '?'
        rs = records(raw/'probes'/result)
        ids = {(r.get('probe_id'),r.get('sample')) for r in rs}
        lines.append(f'  {result}: {len(ids)}/{count} Antworten gespeichert')
    cue_ids = base/'08_cue/cue_tasks.txt'
    if cue_ids.exists():
        text = cue_ids.read_text().strip()
        n = len(text.split(',')) * config.get('cue',{}).get('attempts',2) if text else 0
        lines.append('  ' + agent_line(raw/'cue_deepseekv32/results.jsonl',n) if n else '  Hinweisexperiment: keine geeigneten Aufgaben')
    else:
        lines.append('  Hinweisexperiment: Auswahl noch nicht erstellt')
    logs = list(base.glob('[0-9][0-9]_*/*.log'))
    if logs:
        log = max(logs, key=lambda p: p.stat().st_mtime)
        age = max(0, int(time.time()-log.stat().st_mtime))
        lines += ['', f'Zuletzt beschriebenes Log: {log.relative_to(base)} (vor {age}s)']
        with log.open('rb') as f:
            f.seek(max(0, log.stat().st_size-3000))
            tail = f.read().decode('utf-8',errors='replace').splitlines()[-5:]
        lines += ['  '+line[:240] for line in tail]
    lines += ['', 'Beendet ≠ erfolgreich gelöst. Inhaltliche Fehler sind Messdaten.',
              'Marker/Logalter beweisen nicht, dass ein Prozess noch läuft. Lange Pausen können Modellaufrufe sein.',
              'Strg+C beendet nur diese Anzeige.']
    return '\n'.join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', default=str(H/'configs/gpt_oss_120b_exp_2.yaml'))
    p.add_argument('--runs-root', type=Path, default=H.parent/'runs')
    p.add_argument('--interval', type=float, default=5)
    p.add_argument('--once', action='store_true')
    p.add_argument('--steps', type=selected_steps, default=list(range(len(STEPS))),
                   help='Erwartete Schritte für automatisches Ende; Standard 0-10, Funktionstest: 0-1')
    a = p.parse_args()
    if a.interval <= 0:
        p.error('--interval must be positive')
    config = miniyaml.load(Path(a.config))
    base = a.runs_root.resolve()/config['name']
    try:
        while True:
            # Check before the snapshot so the final display reflects completed files.
            complete = finished(base, a.steps)
            view = snapshot(config,base)
            if sys.stdout.isatty() and not a.once:
                print('\033[2J\033[H',end='')
            print(view,flush=True)
            if complete:
                print('\nLauf abgeschlossen: Alle ausgewählten Schritte sind beendet.\n'
                      'Abbrüche, offene API-Fehler sowie ungültige/fehlende Urteile stehen oben.\n'
                      'Sie werden nicht automatisch wiederholt. Die Fortschrittsanzeige wird beendet.', flush=True)
                return
            if a.once:
                return
            time.sleep(a.interval)
    except KeyboardInterrupt:
        print('\nFortschrittsanzeige beendet; Experiment läuft unabhängig davon weiter.')


if __name__ == '__main__':
    main()
