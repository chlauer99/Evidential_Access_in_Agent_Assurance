"""Bounded retries for transient model API errors, with one audit event per failure."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import time

from openai import APIConnectionError, APIStatusError


def request_with_retry(send, payload, context, record, retries=3, sleep=time.sleep, before=None):
    if retries < 0:
        raise ValueError("retries must be nonnegative")
    # Snapshot once; retries use exactly the same messages and schema.
    snapshot = deepcopy(payload)
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    for attempt in range(retries + 1):
        if before:
            before()
        try:
            return send(**deepcopy(snapshot))
        except (APIConnectionError, APIStatusError) as exc:
            status = getattr(exc, "status_code", None)
            transient = isinstance(exc, APIConnectionError) or status in (408, 409, 429) or (status is not None and status >= 500)
            again = transient and attempt < retries
            delay = min(2 ** (attempt + 1), 30) if again else 0
            record(dict(context, timestamp=datetime.now(timezone.utc).isoformat(),
                        request_sha256=digest, request_attempt=attempt + 1,
                        max_attempts=retries + 1, status_code=status,
                        error_type=type(exc).__name__, error=str(exc),
                        request_id=getattr(exc, "request_id", None),
                        will_retry=again, delay_seconds=delay))
            if not again:
                raise
            sleep(delay)
