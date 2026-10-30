"""Shared helpers for every model-calling script (run_agents.py, judge_runs.py, judge_agentic.py, probes.py).

Added for the reproducibility package (model-agnostic Level B). The paper's prompts, parsing and protocol are
unchanged; these helpers only make the endpoint, key, throttle and file locations configurable:

  * api_key(env)        key from an environment variable; an empty name (local servers) sends the dummy key "EMPTY"
  * RateLimiter(rpm)    optional requests-per-minute throttle (free tiers, local servers)
  * strip_reasoning(t)  optional removal of <think>...</think> blocks that some open models emit before the answer
  * call_meta(resp, extra_body, base_url)
                        per-call record of served model, upstream provider and quantisation (requested routing and,
                        where the gateway returns it, the served quantisation)
  * runs_dir(default) / tasks_dir(default)
                        MAB_RUNS_DIR / MAB_TASKS_DIR environment overrides (used by run_pipeline.py)
  * resolve_answer(root, runs, answer_file)
                        OS-independent path of an attempt's answer file (results.jsonl stores Windows-style paths)
Keys are only ever read from the environment; they are never printed or written.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path

DUMMY_KEY = "EMPTY"


def api_key(env_name: str | None) -> str:
    if not env_name:
        return os.environ.get("LOCAL_LLM_API_KEY", DUMMY_KEY)
    v = os.environ.get(env_name)
    if not v:
        raise RuntimeError(f"environment variable {env_name} is not set (the API key is read from it)")
    return v


def load_extra_body(spec: str | None):
    if not spec:
        return None
    if spec.startswith("@"):
        p = Path(spec[1:])
        if not p.exists():
            p = Path(__file__).resolve().parent / Path(spec[1:]).name
        return json.loads(p.read_text(encoding="utf-8"))
    return json.loads(spec)


class RateLimiter:
    """At most `rpm` calls per rolling minute (thread-safe). rpm=None or 0 disables it."""

    def __init__(self, rpm: float | None):
        self.rpm = float(rpm) if rpm else 0.0
        self.lock = threading.Lock()
        self.calls: list[float] = []

    def acquire(self):
        if not self.rpm:
            return
        while True:
            with self.lock:
                now = time.monotonic()
                self.calls = [t for t in self.calls if now - t < 60.0]
                if len(self.calls) < self.rpm:
                    self.calls.append(now)
                    return
                wait = 60.0 - (now - self.calls[0]) + 0.05
            time.sleep(min(max(wait, 0.05), 5.0))


_THINK = re.compile(r"<think>.*?</think>\s*", re.S | re.I)


def strip_reasoning(text: str) -> str:
    """Remove <think>...</think> blocks (and an unterminated leading <think> block)."""
    if not text:
        return text
    t = _THINK.sub("", text)
    if t.lstrip().lower().startswith("<think>"):
        t = t.split("</think>")[-1] if "</think>" in t else ""
    return t.strip()


def call_meta(resp, extra_body=None, base_url=None) -> dict:
    """Provider and quantisation of one call. OpenRouter returns `provider`; the requested quantisation comes from the
    routing body (e.g. {"provider": {"quantizations": ["fp8"]}}); a served quantisation is recorded if returned."""
    extra = (getattr(resp, "model_extra", None) or {}) if resp is not None else {}
    req = (extra_body or {}).get("provider", {}) if isinstance(extra_body, dict) else {}
    host = re.sub(r"^https?://(?:api\.)?([^/:]+).*$", r"\1", base_url) if base_url else "api.openai.com"
    return {"endpoint": host, "served_model": getattr(resp, "model", None),
            "provider": extra.get("provider") or (host.split(".")[0] if base_url else "openai"),
            "requested_quantizations": req.get("quantizations"),
            "served_quantization": extra.get("quantization") or extra.get("quantizations")}


def runs_dir(default: Path) -> Path:
    return Path(os.environ["MAB_RUNS_DIR"]).resolve() if os.environ.get("MAB_RUNS_DIR") else default


def tasks_dir(default: Path) -> Path:
    return Path(os.environ["MAB_TASKS_DIR"]).resolve() if os.environ.get("MAB_TASKS_DIR") else default


def resolve_answer(root: Path, runs: Path, answer_file: str) -> Path:
    """answer_file is stored as e.g. 'mab_runs\\pilot_gpt41\\answers\\task1_4__03.json' (relative to the harness root)."""
    parts = re.split(r"[\\/]+", str(answer_file))
    if "mab_runs" in parts:
        parts = parts[parts.index("mab_runs") + 1:]
        p = Path(runs, *parts)
        if p.exists():
            return p
    p = Path(root, *re.split(r"[\\/]+", str(answer_file)))
    if p.exists():
        return p
    # last resort: <runs>/<run>/answers/<file>
    return Path(runs, *parts[-3:]) if len(parts) >= 3 else p


def answer_ref(root: Path, path: Path) -> str:
    """String stored in results.jsonl for an answer file: relative to the harness root when possible, else
    'mab_runs\\<run>\\answers\\<file>' (the form resolve_answer understands)."""
    try:
        return str(Path(path).relative_to(root))
    except ValueError:
        p = Path(path)
        return "\\".join(["mab_runs", p.parent.parent.name, p.parent.name, p.name])
