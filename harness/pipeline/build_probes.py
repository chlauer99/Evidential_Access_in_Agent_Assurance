"""Step 7 (item construction) - knowledge-probe items from the full-run agent's own failed attempts, and matched
negative controls. Reconstructed from the construction code of probes_instances.json / probes_controls.json.

  instances (offline; needs raw trajectories + tracer table of the full run):
    code_choice   every task of categories 9 (truth K) and 10 (A1C), the first 10 tasks of categories 4 (MG) and 7 (GLU)
    absence       first false-absence attempt per task: its zero-result query and response (truth "no")
    completeness  first incomplete-retrieval attempt per task (6 per category): first page with a next link ("incomplete")
    window        first time-window error per task: retrieved (time, value) pairs; truth = latest value within 24 h, else -1
    age / mean    first computation error per task in categories 2 (age from birth date) and 6 (mean of in-window values)
  controls (needs the FHIR server): valid queries that are genuinely empty (absence, truth "yes") and complete single-page
    responses with 8-20 entries and no next link (completeness, truth "complete"), from the task's own correct query.
Outputs: <out>/probes_instances.json, <out>/probes_controls.json
"""
from __future__ import annotations

import argparse, json, os, re, runpy, sys
from pathlib import Path

import pandas as pd

HM = Path(__file__).resolve().parent.parent / "mab_harness"
FB = "http://localhost:8080/fhir/"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True); ap.add_argument("--derived", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--run", default="full_deepseekv32")
    ap.add_argument("--controls", action="store_true", help="also build the negative controls (needs the FHIR server)")
    a = ap.parse_args()
    os.environ["MAB_RUNS_DIR"] = str(Path(a.runs_dir).resolve())
    ra = runpy.run_path(str(HM / "run_agents.py"), run_name="ra")
    tm = runpy.run_path(str(HM / "trace_mechanisms.py"), run_name="tm")
    T = runpy.run_path(str(HM / "probes.py"), run_name="pr")["TEMPLATES"]
    sys.path.insert(0, str(HM)); import llm_config as _llm
    tasks = ra["load_tasks"](); tk = {t["id"]: t for t in tasks}
    runs = Path(a.runs_dir)
    ansfile = {(r["task_id"], r["attempt"]): r["answer_file"] for r in (json.loads(l) for l in open(runs / a.run / "results.jsonl", encoding="utf-8") if l.strip())
               if r["status"] != "API_ERROR"}
    hist = lambda tid, att: json.loads(_llm.resolve_answer(HM.parent, runs, ansfile[(tid, att)]).read_text(encoding="utf-8"))["history"]
    DS = pd.read_csv(Path(a.derived) / f"{a.run}_mechanisms.csv")

    def get_pairs(h):
        out = []
        for i, m in enumerate(h[1:], start=1):
            if m["role"] == "agent" and m["content"].strip().startswith("GET") and i + 1 < len(h):
                out.append((m["content"].strip(), h[i + 1]["content"]))
        return out

    inst = []
    for c, truth, k in [("task9", "K", 30), ("task10", "A1C", 30), ("task4", "MG", 10), ("task7", "GLU", 10)]:
        for t in sorted([t for t in tasks if t["id"].startswith(c + "_")], key=lambda t: int(t["id"].split("_")[1]))[:k]:
            inst.append({"probe_id": f"code_{t['id']}", "family": "code_choice", "task_id": t["id"], "truth": truth,
                         "prompt": T["code_choice"].format(instruction=t["instruction"], context=t["context"]).replace("{api_base}", FB.rstrip("/"))})

    def first_fail(mech, cats=None):
        d = DS[(DS.mechanism == mech) & (DS.refined_class != "pass")]
        if cats:
            d = d[d.category.isin(cats)]
        return d.sort_values(["task_id", "attempt"]).groupby("task_id").head(1)

    for _, x in first_fail("false_absence").iterrows():
        pairs = [(q, r) for q, r in get_pairs(hist(x.task_id, x.attempt)) if '"total": 0' in r]
        if pairs:
            q, resp = pairs[0]
            inst.append({"probe_id": f"abs_{x.task_id}", "family": "absence", "task_id": x.task_id, "truth": "no", "source_attempt": int(x.attempt),
                         "prompt": T["absence"].format(instruction=tk[x.task_id]["instruction"], context=tk[x.task_id]["context"], query=q, response=resp)})
    for _, x in first_fail("incomplete_retrieval").groupby("category").head(6).iterrows():
        pairs = [(q, r) for q, r in get_pairs(hist(x.task_id, x.attempt)) if '"relation": "next"' in r]
        if pairs:
            q, resp = pairs[0]
            inst.append({"probe_id": f"comp_{x.task_id}", "family": "completeness", "task_id": x.task_id, "truth": "incomplete", "source_attempt": int(x.attempt),
                         "prompt": T["completeness"].format(instruction=tk[x.task_id]["instruction"], context=tk[x.task_id]["context"], query=q, response=resp)})
    for _, x in first_fail("time_window_error").iterrows():
        steps = tm["parse_steps"](hist(x.task_id, x.attempt))
        pts = sorted({(p[0], p[1]) for s in steps if s["kind"] == "GET" for p in tm["obs_points"](s["entries"])})
        inw = [p for p in pts if tm["NOW"] - pd.Timedelta(hours=24) <= p[0] <= tm["NOW"]]
        truth = max(inw)[1] if inw else -1
        analyte = "magnesium (mg/dL)" if x.category in ("task4", "task5") else "capillary blood glucose (mg/dL)"
        inst.append({"probe_id": f"win_{x.task_id}", "family": "window", "task_id": x.task_id, "truth": truth, "source_attempt": int(x.attempt),
                     "prompt": T["window"].format(now="2023-11-13T10:15:00+00:00", analyte=analyte,
                                                  points="\n".join(f"{p[0].isoformat()}  {p[1]}" for p in pts))})
    for _, x in first_fail("computation_error", ["task2"]).iterrows():
        steps = tm["parse_steps"](hist(x.task_id, x.attempt))
        bd = next(r.get("birthDate") for s in steps if s["kind"] == "GET" for r in s["entries"] if r.get("resourceType") == "Patient")
        b = pd.Timestamp(bd); now = pd.Timestamp("2023-11-13")
        truth = now.year - b.year - ((now.month, now.day) < (b.month, b.day))
        inst.append({"probe_id": f"age_{x.task_id}", "family": "age", "task_id": x.task_id, "truth": truth, "source_attempt": int(x.attempt),
                     "prompt": T["age"].format(birthdate=bd, today="2023-11-13")})
    for _, x in first_fail("computation_error", ["task6"]).iterrows():
        steps = tm["parse_steps"](hist(x.task_id, x.attempt))
        pts = {(p[0], p[1], p[2]) for s in steps if s["kind"] == "GET" for p in tm["obs_points"](s["entries"])}
        vals = [p[1] for p in sorted(pts) if tm["NOW"] - pd.Timedelta(hours=24) <= p[0] <= tm["NOW"]]
        if vals:
            inst.append({"probe_id": f"mean_{x.task_id}", "family": "mean", "task_id": x.task_id, "truth": round(sum(vals) / len(vals), 4),
                         "source_attempt": int(x.attempt), "prompt": T["mean"].format(values=", ".join(str(v) for v in vals))})
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    json.dump(inst, open(out / "probes_instances.json", "w", encoding="utf-8"), indent=1)
    print("instances", pd.Series([p["family"] for p in inst]).value_counts().to_dict())
    if not a.controls:
        return
    import requests
    ses = requests.Session(); ses.trust_env = False
    BASE = FB.rstrip("/")

    def get(q):
        r = ses.get(f"{BASE}/{q}" + ("&" if "?" in q else "?") + "_format=json", timeout=120); r.raise_for_status(); return r.text
    rows = []
    for tid, t in tk.items():
        cat = int(t["category"][4:])
        mrn = re.search(r"S\d{7}", t["instruction"]); code = re.search(r'code for [\w\s]+? is "([^"]+)"', t["context"] or "")
        if cat == 1:
            m = re.search(r"name (\w+) (\w+) and DOB of (\d{4}-\d{2}-\d{2})", t["instruction"])
            if m:
                q = f"Patient?family={m[2]}&given={m[1]}&birthdate={m[3]}"
            else:
                continue
        elif mrn and code:
            q = f"Observation?code={code[1]}&patient={mrn[0]}"
        else:
            continue
        txt = get(q); d = json.loads(txt)
        rows.append(dict(task_id=tid, query=q, n=len(d.get("entry", [])), next=any(l["relation"] == "next" for l in d.get("link", [])), text=txt))
    absn = [i for i in inst if i["family"] == "absence"]
    ex_abs = absn[0]["prompt"] if absn else ""; wrap_pre = "Here is the response from the GET request:\n"
    wrap_post = ex_abs[ex_abs.find("}. Please call FINISH") + 1: ex_abs.find("\n\nCan the assistant")]
    ctrl = []
    for r in rows:
        t = tk[r["task_id"]]
        fam = "absence" if r["n"] == 0 else ("completeness" if (8 <= r["n"] <= 20 and not r["next"]) else None)
        if fam:
            ctrl.append(dict(probe_id=f"{'absC' if fam == 'absence' else 'compC'}_{r['task_id']}", family=fam, task_id=r["task_id"],
                             truth="yes" if fam == "absence" else "complete", source_attempt=None, control=True,
                             prompt=T[fam].format(instruction=t["instruction"], context=t["context"] or "(none)",
                                                  query=f"GET {BASE}/{r['query']}", response=wrap_pre + r["text"] + wrap_post)))
    json.dump(ctrl, open(out / "probes_controls.json", "w", encoding="utf-8"), indent=1)
    print("controls", pd.Series([c["family"] for c in ctrl]).value_counts().to_dict())


if __name__ == "__main__":
    main()
