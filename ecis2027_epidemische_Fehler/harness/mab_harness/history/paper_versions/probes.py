"""'Knows but doesn't do' probes: isolated knowledge questions built from an agent's own failed attempts.

Each probe asks, outside the agent loop, for the one piece of knowledge the failed attempt needed:
  F1 code_choice   which code to put in the Observation search, given the task context (trap: a second, standard
                   code is supplied for ordering). Built for every task of the category (not only failures).
  F2 absence       given the agent's query and the zero-result response, may one conclude the data do not exist?
  F3 completeness  given the first-page response the agent read, is the result set complete?
  F4 window        given the retrieved (time, value) pairs and the current time, which value lies in the last 24 h?
  F5 arithmetic    age from a birth date, or mean of listed values.
Usage:
  python probes.py run --instances probes_instances.json --model deepseek/deepseek-v3.2 --base-url https://openrouter.ai/api/v1
                       --api-key-env OPENROUTE --extra-body @openrouter_route_deepseek-v3.2.json --samples 3 --out probes_results.jsonl
"""
from __future__ import annotations

import argparse, json, os, re, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SYSTEM = "You are an expert in electronic health records and the HL7 FHIR API. Answer precisely and briefly."

TEMPLATES = {
    "code_choice": ("TASK: {instruction}\nCONTEXT: {context}\n\nYou will now search the EHR with "
                    "GET {{api_base}}/Observation?code=<CODE>&patient=<MRN>. Which value should <CODE> take to find "
                    "this patient's existing results? Reply with the code only."),
    "absence": ("TASK: {instruction}\nCONTEXT: {context}\n\nAn assistant sent this request:\n{query}\n\nThe EHR returned:\n"
                "{response}\n\nCan the assistant validly conclude from this response that the patient has no such record or "
                "result? Answer 'yes' or 'no' first, then give one sentence of reasoning."),
    "completeness": ("TASK: {instruction}\nCONTEXT: {context}\n\nAn assistant sent this request:\n{query}\n\nThe EHR returned:\n"
                     "{response}\n\nDoes this response contain ALL of the patient's matching observations? Answer 'complete' "
                     "or 'incomplete' first, then say in one sentence what the assistant should do next."),
    "window": ("It is now {now}. These are a patient's {analyte} measurements (time, value):\n{points}\n\nWhat is the most "
               "recent value measured within the last 24 hours? Reply with the number only, or -1 if there is none."),
    "age": ("A patient was born on {birthdate}. Today is {today}. What is the patient's age in whole years, rounded down? "
            "Reply with the number only."),
    "mean": ("Compute the arithmetic mean of these values: {values}. Reply with the number only, rounded to two decimals."),
}


def score(family, text, truth):
    t = (text or "").strip()
    low = t.lower()
    if family == "code_choice":
        tok = re.sub(r"[`'\"\s.]", "", t.split("\n")[0])
        return tok.upper() == str(truth).upper()
    if family == "absence":  # truth 'no' (invalid query) or 'yes' (valid query, genuinely empty) -- controls added
        return re.sub(r"[^a-z]", " ", low).split()[:1] == [str(truth).lower()]
    if family == "completeness":  # truth 'incomplete' (paged) or 'complete' (single page, no next link)
        return re.sub(r"[^a-z]", " ", low).split()[:1] == [str(truth).lower()]
    nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", t)]
    if not nums:
        return False
    if family in ("window", "age"):
        return abs(nums[0] - float(truth)) < 1e-6
    if family == "mean":
        return abs(nums[0] - float(truth)) <= 0.06
    return False


def run(a):
    from openai import OpenAI
    client = OpenAI(max_retries=8, timeout=180, base_url=a.base_url, api_key=os.environ[a.api_key_env])
    extra = (json.loads(Path(a.extra_body[1:]).read_text(encoding="utf-8")) if a.extra_body and a.extra_body.startswith("@")
             else json.loads(a.extra_body) if a.extra_body else None)
    inst = json.loads(Path(a.instances).read_text(encoding="utf-8"))
    out = Path(a.out)
    done = set()
    if out.exists():
        for l in out.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l); done.add((r["probe_id"], r["sample"]))
    jobs = [(p, s) for p in inst for s in range(a.samples) if (p["probe_id"], s) not in done]
    print(f"{len(jobs)} probe calls", flush=True)
    lock = threading.Lock()

    def one(job):
        p, s = job
        kw = dict(model=a.model, messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": p["prompt"]}],
                  temperature=a.temperature, max_tokens=200)
        if extra:
            kw["extra_body"] = extra
        resp = client.chat.completions.create(**kw)
        text = resp.choices[0].message.content if resp.choices else ""
        u = resp.usage
        row = {"probe_id": p["probe_id"], "family": p["family"], "task_id": p["task_id"], "sample": s,
               "truth": p["truth"], "answer": (text or "")[:400], "correct": score(p["family"], text, p["truth"]),
               "source_attempt": p.get("source_attempt"), "served_model": resp.model,
               "provider": (getattr(resp, "model_extra", None) or {}).get("provider"),
               "cost_usd": (getattr(u, "model_extra", None) or {}).get("cost") if u else None,
               "prompt_tokens": getattr(u, "prompt_tokens", None)}
        with lock:
            with open(out, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(one, jobs))
    print("done", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--instances", required=True); r.add_argument("--model", required=True)
    r.add_argument("--base-url", default=None); r.add_argument("--api-key-env", default="OPENAI_API_KEY")
    r.add_argument("--extra-body", default=None); r.add_argument("--samples", type=int, default=3)
    r.add_argument("--temperature", type=float, default=0.8); r.add_argument("--workers", type=int, default=6)
    r.add_argument("--out", required=True)
    a = ap.parse_args()
    run(a)
