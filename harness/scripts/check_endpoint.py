"""Check configured OpenAI-compatible endpoints before an experiment (no FHIR needed).

Lists served model IDs, then checks a strict agent action and a judge JSON response.
Only synthetic test prompts are sent; no experiment is started.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request

HARNESS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HARNESS / "pipeline"))
sys.path.insert(0, str(HARNESS / "mab_harness"))
import miniyaml
import llm_config
import judge_schema


def request(base, route, key, timeout, payload=None):
    req = urllib.request.Request(
        base.rstrip("/") + route,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def check_model(model, timeout, structured=False):
    base = model["base_url"]
    key = llm_config.api_key(model.get("api_key_env"))
    available = request(base, "/models", key, timeout)
    ids = [entry["id"] for entry in available.get("data", [])]
    print("Served IDs:", ", ".join(ids))
    if model["model"] not in ids:
        raise ValueError(f"Configured model {model['model']!r} is not in /models. Update the config.")
    minimum = model.get("min_context_tokens")
    if minimum:
        served = next(entry for entry in available["data"] if entry["id"] == model["model"])
        capacity = served.get("max_model_len")
        if not isinstance(capacity, int) or capacity < minimum:
            raise ValueError(f"Expected at least {minimum} context tokens; server reports {capacity!r}. Configure max_model_len on the vLLM server.")
        print(f"PASS context capacity: {capacity} tokens (input plus output)")
    verdict = dict(verdict="pass", confidence=100, issue_type="none", issues=[], rationale="test")
    cases = [("agent", "Reply with exactly FINISH([]) and no other text.", None)]
    if structured:
        cases += [
            ("judge", "Return this verdict: " + json.dumps(verdict), judge_schema.response_format()),
            ("access-query", 'Request /fhir/Patient using {"action":{"query":"/fhir/Patient"}}.',
             judge_schema.response_format(access=True)),
            ("access-final", "Return this verdict wrapped in action: " + json.dumps(verdict),
             judge_schema.response_format(access=True, allow_queries=False)),
        ]
    else:
        cases.append(("judge", "Return this JSON: " + json.dumps(verdict), None))
    for label, prompt, output_format in cases:
        body = dict(model=model["model"], messages=[{"role": "user", "content": prompt}],
                    max_tokens=model.get("max_output_tokens", 8192), temperature=0)
        body.update(model.get("extra_body") or {})
        if output_format:
            body["response_format"] = output_format
        response = request(base, "/chat/completions", key, timeout, body)
        choice = response["choices"][0]
        content = choice["message"].get("content") or ""
        if model.get("strip_reasoning"):
            content = llm_config.strip_reasoning(content)
        if choice.get("finish_reason") == "length" or not content.strip():
            raise ValueError(f"{label}: empty/truncated final answer; check reasoning handling and output/context limits.")
        if label == "agent" and content.strip() != "FINISH([])":
            raise ValueError("Agent action is not in the strict format. Check the server's final-content/reasoning separation.")
        if output_format:
            parsed = judge_schema.parse(content, choice.get("finish_reason"),
                                        access=label.startswith("access"), allow_queries=label != "access-final")
            if label == "access-query" and "query" not in parsed:
                raise ValueError("Access preflight did not return the requested query action")
            if label != "access-query" and parsed.get("verdict") != "pass":
                raise ValueError("Preflight verdict is not pass")
        if label == "judge" and json.loads(content).get("verdict") != "pass":
            raise ValueError("Judge response is not the expected JSON verdict.")
        print(f"PASS {label}: served_model={response.get('model')}, finish_reason={choice.get('finish_reason')}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    config = miniyaml.load(Path(args.config))
    structured_models = {j["model"] for j in config.get("judges", {}).values() if j.get("structured_output")}
    seen = set()
    for alias, model in config["models"].items():
        identity = (model.get("base_url"), model["model"], model.get("api_key_env"),
                    json.dumps(model.get("extra_body"), sort_keys=True), alias in structured_models)
        if identity in seen:
            continue
        seen.add(identity)
        if not model.get("base_url"):
            raise ValueError("This check requires an explicit base_url.")
        print(f"Checking {model['base_url']} / {model['model']}")
        check_model(model, args.timeout, structured=alias in structured_models)
    print("Endpoint checks passed. This checks connectivity and output formats, not long-context task performance.")


if __name__ == "__main__":
    try:
        main()
    except (urllib.error.URLError, ValueError, KeyError, IndexError, RuntimeError, TimeoutError) as exc:
        # Do not print request headers, keys, or arbitrary server response bodies.
        print(f"Endpoint check failed: {exc}", file=sys.stderr)
        sys.exit(1)
