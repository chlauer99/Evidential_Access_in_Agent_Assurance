import sys
from pathlib import Path
import unittest
try:
    import httpx
except ImportError:
    import httpx2 as httpx
from openai import InternalServerError, BadRequestError, APIConnectionError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mab_harness"))
from request_retry import request_with_retry


def error(cls, status):
    return cls("test failure", response=httpx.Response(status, request=httpx.Request("POST", "http://test")), body=None)


class RetryTests(unittest.TestCase):
    def test_recovers_with_identical_payload_and_logs_each_failure(self):
        seen, events, waits, throttles = [], [], [], []
        payload = {"messages": [{"content": "same prompt"}], "response_format": {"type": "json_schema"}}
        def send(**kw):
            seen.append(kw)
            if len(seen) < 3:
                raise error(InternalServerError, 500)
            return "valid response"
        result = request_with_retry(send, payload, {"task_id": "t1", "turn": 2}, events.append,
                                    sleep=waits.append, before=lambda: throttles.append(1))
        self.assertEqual(result, "valid response")
        self.assertEqual(seen, [payload] * 3)
        self.assertEqual(waits, [2, 4])
        self.assertEqual(len(throttles), 3)
        self.assertEqual([e["request_attempt"] for e in events], [1, 2])
        self.assertEqual(len({e["request_sha256"] for e in events}), 1)
        self.assertTrue(all(e["turn"] == 2 for e in events))

    def test_exhaustion_is_bounded_and_audited(self):
        events, waits = [], []
        def send(**kw):
            raise error(InternalServerError, 500)
        with self.assertRaises(InternalServerError):
            request_with_retry(send, {}, {}, events.append, sleep=waits.append)
        self.assertEqual(len(events), 4)
        self.assertFalse(events[-1]["will_retry"])
        self.assertEqual(waits, [2, 4, 8])

    def test_bad_request_is_not_retried(self):
        events = []
        def send(**kw):
            raise error(BadRequestError, 400)
        with self.assertRaises(BadRequestError):
            request_with_retry(send, {}, {}, events.append, sleep=lambda _: self.fail("unexpected wait"))
        self.assertEqual(len(events), 1)
        self.assertFalse(events[0]["will_retry"])

    def test_connection_failure_retried(self):
        events = []
        def send(**kw):
            if not events:
                raise APIConnectionError(request=httpx.Request("POST", "http://test"))
            return "ok"
        self.assertEqual(request_with_retry(send, {}, {}, events.append, sleep=lambda _: None), "ok")


if __name__ == "__main__":
    unittest.main()
