"""Regression checks for invalid verdicts observed in the archived run."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HARNESS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS / "mab_harness"))
import judge_schema as schema
spec = importlib.util.spec_from_file_location("check_endpoint", HARNESS / "scripts/check_endpoint.py")
endpoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(endpoint)


class StructuredJudges(unittest.TestCase):
    def setUp(self):
        self.verdict = dict(verdict="pass", confidence=90, issue_type="none", issues=[], rationale="Checked")

    def test_valid_verdict_and_access(self):
        self.assertEqual(schema.parse(json.dumps(self.verdict), "stop"), self.verdict)
        self.assertEqual(schema.parse(json.dumps({"action": self.verdict}), "stop", access=True), self.verdict)

    def test_invalid_verdicts(self):
        for change in ({"confidence": "ninety"}, {"confidence": True}, {"confidence": 101},
                       {"verdict": "unknown"}, {"issues": ["x"] * 4}, {"extra": "field"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                schema.parse(json.dumps(dict(self.verdict, **change)), "stop")
        for text, reason in ((json.dumps(self.verdict), "length"), ('{"verdict":', "stop"),
                             ('{}', 'stop'), ('', 'stop')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                schema.parse(text, reason)

    def test_query_limit(self):
        text = json.dumps({"action": {"query": "/fhir?_getpages=abc"}})
        self.assertIn("query", schema.parse(text, "stop", access=True))
        with self.assertRaises(ValueError):
            schema.parse(text, "stop", access=True, allow_queries=False)
        action = schema.response_format(access=True, allow_queries=False)["json_schema"]["schema"]["properties"]["action"]
        self.assertEqual(action, schema.VERDICT)

    def test_preflight_sends_all_schemas(self):
        calls = []
        def request(base, route, key, timeout, payload=None):
            if route == "/models":
                return {"data": [{"id": "local"}]}
            calls.append(payload)
            idx = len(calls)
            obj = self.verdict if idx == 2 else {"action": {"query": "/fhir/Patient"}} if idx == 3 else {"action": self.verdict}
            content = "FINISH([])" if idx == 1 else json.dumps(obj)
            return {"model": "local", "choices": [{"message": {"content": content}, "finish_reason": "stop"}]}
        with patch.object(endpoint, "request", side_effect=request):
            endpoint.check_model({"model": "local", "base_url": "http://unused", "api_key_env": ""}, 1, structured=True)
        self.assertNotIn("response_format", calls[0])
        self.assertEqual([c["response_format"]["type"] for c in calls[1:]], ["json_schema"] * 3)
        self.assertNotIn("anyOf", calls[-1]["response_format"]["json_schema"]["schema"]["properties"]["action"])

    def test_unsupported_schema_is_not_silently_ignored(self):
        with patch.object(endpoint, "request", side_effect=[
            {"data": [{"id": "local"}]},
            {"choices": [{"message": {"content": "FINISH([])"}, "finish_reason": "stop"}]},
            ValueError("unsupported response_format"),
        ]), self.assertRaisesRegex(ValueError, "unsupported"):
            endpoint.check_model({"model": "local", "base_url": "http://unused", "api_key_env": ""}, 1, structured=True)


if __name__ == "__main__":
    unittest.main()
