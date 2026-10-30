"""Offline case audit. Does not change archived data or invoke models/server."""
import csv
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent
BASE = OUT.parent
RUN = BASE / 'mab_runs/full_deepseekv32'
NOW = datetime.fromisoformat('2023-11-13T10:15:00+00:00')


def bundle(content):
    return json.JSONDecoder().raw_decode(content[content.find('{'):])[0]


def posts(history):
    return [json.loads(m['content'].partition('\n')[2]) for m in history
            if m['role'] == 'agent' and m['content'].startswith('POST')]


source = list(csv.DictReader((BASE / 'derived/provenance_coding.csv').open()))
selected = [r for r in source if r['provenance'] == 'unclassified']
assert len(selected) == 52
rows = []
details = []
for row in selected:
    task, attempt = row['task_id'], int(row['attempt'])
    path = RUN / 'answers' / f'{task}__{attempt:02}.json'
    data = json.loads(path.read_text())
    history = data['history']
    ref = json.loads((RUN / '_reference' / f'{task}.json').read_text())
    actual_posts = posts(history)
    reference_posts = posts(ref['history'])
    responses = [bundle(m['content']) for m in history
                 if m['role'] == 'user' and m['content'].startswith('Here is the response from the GET request')]
    actions = [m['content'] for m in history if m['role'] == 'agent']
    findings = []
    if task.startswith('task6_'):
        entries = [e['resource'] for b in responses for e in b.get('entry', [])
                   if e['resource'].get('resourceType') == 'Observation']
        vals = [(e['effectiveDateTime'], e['valueQuantity']['value']) for e in entries]
        in_window = [(d, v) for d, v in vals if NOW-timedelta(hours=24) <= datetime.fromisoformat(d) <= NOW]
        mean = sum(v for _, v in in_window)/len(in_window)
        answer = float(str(json.loads(data['result'])[0]).split()[0])
        assert abs(mean-answer) < 1e-9
        next_link = any(l.get('relation') == 'next' for b in responses for l in b.get('link', []))
        assert next_link and sum(a.startswith('GET') and '/Observation?' in a for a in actions) == 1
        category = 'mean_of_incomplete_in_window_evidence'
        locus, provenance = 'evidence_gathering', 'grounded'
        findings.append(f'Answer {answer} = mean of retrieved 24h values {[v for _,v in in_window]}; reference {ref["result"]}; next page not requested.')
        findings.append('Provenance parser json.loads fails on feedback suffix; candidate algorithm also omits noncontiguous time-filtered subsets.')
    elif not actual_posts:
        assert task.startswith(('task3_', 'task8_')) and len(reference_posts) == 1
        get_actions = [a for a in actions if a.startswith('GET')]
        assert len(get_actions) == 1 and get_actions[0].count('GET ') == 2
        assert responses[0].get('total') == 0
        category = 'malformed_multi_get_causing_false_absence'
        locus, provenance = 'evidence_gathering', 'grounded'
        findings.append('Two GET lines emitted in one action; runner sends complete text as one URL; authentic zero-hit Patient response; required POST omitted.')
        if '<|constrain|>' in get_actions[0]:
            findings.append('Special token <|constrain|> also contaminates URL.')
        findings.append('Tracer parses only first whitespace-delimited URL, hiding malformed remainder; task3/task8 fallback assigns order_content_error.')
    elif task.startswith('task5_'):
        p, rp = actual_posts[0], reference_posts[0]
        assert p['subject'] == rp['subject']
        dose = p['dosageInstruction'][0]['doseAndRate'][0]
        rdose = rp['dosageInstruction'][0]['doseAndRate'][0]
        assert dose['doseQuantity'] == rdose['doseQuantity']
        assert p['medicationCodeableConcept']['coding'][0]['code'] == rp['medicationCodeableConcept']['coding'][0]['code']
        route = p['dosageInstruction'][0]['route']
        category = 'medication_payload_contract_mismatch'
        locus, provenance = 'action', 'not_applicable_to_order_specification'
        findings.append(f'Dose, drug code and patient match reference. route={route!r}, expected "IV"; rateQuantity={dose["rateQuantity"]!r}, expected {rdose["rateQuantity"]!r}.')
        findings.append('Exact grader rejects representation; route object and hour/h differences alone do not prove clinical error. g/hour differs dimensionally from benchmark duration h.')
    else:
        assert task.startswith(('task8_', 'task10_'))
        p, rp = actual_posts[0], reference_posts[0]
        bad_reference = p['subject'] != rp['subject']
        bad_time = p['authoredOn'] != rp['authoredOn']
        assert bad_reference or bad_time
        category = ('patient_reference_and_timestamp_error' if bad_reference and bad_time else
                    'patient_reference_error' if bad_reference else 'timestamp_error')
        locus, provenance = 'action', 'not_applicable_to_order_specification'
        if bad_reference:
            findings.append(f'subject={p["subject"]!r}; expected {rp["subject"]!r}. Same identifier, missing Patient/ prefix; not evidence of a different patient.')
        if bad_time:
            findings.append(f'authoredOn={p["authoredOn"]}; task/reference time={rp["authoredOn"]}; occurrenceDateTime={p.get("occurrenceDateTime")}.')
        assert p['code']['coding'][0]['code'] == rp['code']['coding'][0]['code']
        findings.append('Requested service code matches reference. Grounded/fabricated patient-fact provenance is not the appropriate axis for this order-specification defect.')
    rows.append(dict(task_id=task, attempt=attempt, original_outcome=row['outcome_class'],
                     original_mechanism=row['mechanism'], original_provenance=row['provenance'],
                     reviewed_category=category, reviewed_locus=locus, reviewed_provenance=provenance,
                     evidence=' '.join(findings), answer_file=str(path.relative_to(BASE))))
    details.append(dict(task_id=task, attempt=attempt, task_context=history[0]['content'].split('Context:')[-1],
                        answer=data['result'], reference_answer=ref['result'], actions=actions,
                        actual_posts=actual_posts, reference_posts=reference_posts, findings=findings))

assert len(rows) == len({(r['task_id'],r['attempt']) for r in rows}) == 52
with (OUT/'case_review.csv').open('w', newline='') as f:
    w=csv.DictWriter(f, fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(OUT/'case_evidence.json').write_text(json.dumps(details, ensure_ascii=False, indent=2)+'\n')
summary = dict(cases=len(rows), categories=dict(Counter(r['reviewed_category'] for r in rows)),
               loci=dict(Counter(r['reviewed_locus'] for r in rows)),
               provenance=dict(Counter(r['reviewed_provenance'] for r in rows)))
(OUT/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary, indent=2))
