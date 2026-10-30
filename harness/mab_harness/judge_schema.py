"""Versioned judge output schemas and strict local validation (standard library only)."""
import json
from copy import deepcopy

VERSION = 'judge-json-v1'
VERDICT = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'verdict': {'type': 'string', 'enum': ['pass', 'fail']},
        'confidence': {'type': 'integer', 'minimum': 0, 'maximum': 100},
        'issue_type': {'type': 'string', 'enum': ['none', 'answer', 'orders', 'format', 'other']},
        'issues': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 3},
        'rationale': {'type': 'string'},
    },
    'required': ['verdict', 'confidence', 'issue_type', 'issues', 'rationale'],
}
QUERY = {'type': 'object', 'properties': {'query': {'type': 'string', 'minLength': 1}},
         'required': ['query'], 'additionalProperties': False}


def response_format(access=False, allow_queries=True):
    schema = deepcopy(VERDICT)
    if access:
        schema = {'type': 'object', 'properties': {'action': {'anyOf': [deepcopy(QUERY), schema]} if allow_queries else schema},
                  'required': ['action'], 'additionalProperties': False}
    return {'type': 'json_schema', 'json_schema': {'name': 'ehr_action' if access else 'judge_verdict',
                                                'strict': True, 'schema': schema}}


def parse(text, finish_reason, access=False, allow_queries=True):
    if finish_reason != 'stop':
        raise ValueError(f'Incomplete structured output: finish_reason={finish_reason}')
    obj = json.loads(text)
    if access:
        if not isinstance(obj, dict) or set(obj) != {'action'}:
            raise ValueError('Expected an action object')
        obj = obj['action']
        if isinstance(obj, dict) and set(obj) == {'query'}:
            if not allow_queries or not isinstance(obj['query'], str) or not obj['query'].strip():
                raise ValueError('Query not allowed or empty')
            return obj
    if not isinstance(obj, dict) or set(obj) != set(VERDICT['required']):
        raise ValueError('Missing or unexpected verdict fields')
    if obj['verdict'] not in ('pass', 'fail'):
        raise ValueError('Invalid verdict')
    if type(obj['confidence']) is not int or not 0 <= obj['confidence'] <= 100:
        raise ValueError('Confidence must be an integer between 0 and 100')
    if obj['issue_type'] not in VERDICT['properties']['issue_type']['enum']:
        raise ValueError('Invalid issue_type')
    if (not isinstance(obj['issues'], list) or len(obj['issues']) > 3
            or not all(isinstance(i, str) for i in obj['issues']) or not isinstance(obj['rationale'], str)):
        raise ValueError('Invalid issues or rationale')
    return obj
