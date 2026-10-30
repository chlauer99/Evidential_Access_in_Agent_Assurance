"""Level B orchestrator: re-run the whole study, with the paper's models or with other LLMs.

  python harness/run_pipeline.py --config harness/configs/paper.yaml --dry-run          # print the plan and costs
  python harness/run_pipeline.py --config harness/configs/paper.yaml --steps 0-2 --yes

Steps (each resumable; outputs under runs/<config name>/):
  0 server      fetch and start the MedAgentBench FHIR server (pinned image; Windows no-Docker path with h2fix,
                or Docker on Linux/macOS, or an already running server)
  1 agents      agent runs (run_agents.py) for the three agent role slots
  2 controls    reference replay and do-nothing agents (30 pilot tasks, judged; 300 tasks, tracer reference)
  3 grade       official grading + format-only regrade -> outcome classes            (pipeline/grade_outcomes.py)
  4 trace       mechanism tracer -> locus and mechanism                              (pipeline/trace_runs.py)
  5 provenance  grounded / fabricated / unclassified coding                          (pipeline/code_provenance.py)
  6 judges      judges under the four evidence conditions and pairings, incl. the record-access sample
  7 probes      knowledge probes with negative controls                              (pipeline/build_probes.py, probes.py)
  8 cue         verification-cue rerun on the tasks with evidence-gathering errors
  9 analysis    the Level A analysis scripts on the new run                          (reproduce.py --level A --raw ...)
  10 compare    new numbers vs published numbers                                     (pipeline/compare_report.py)
Folder layout: runs/<name>/mab_runs/ (raw run folders in the harness format; the analyses read them directly),
runs/<name>/derived/ (per-attempt tables), runs/<name>/<NN_step>/ (logs, plans, step outputs, DONE markers).
Paid steps (1, 6, 7, 8) print a cost and runtime estimate and only run with --yes.
API keys are read from the environment variables named in the config; they are never printed or written.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
ROOT = HARNESS.parent
MH = HARNESS / "mab_harness"
PL = HARNESS / "pipeline"
sys.path.insert(0, str(PL))
import miniyaml  # noqa: E402

STEPS = {0: "server", 1: "agents", 2: "controls", 3: "grade", 4: "trace", 5: "provenance", 6: "judges", 7: "probes",
         8: "cue", 9: "analysis", 10: "compare"}
PAID = {1, 6, 7, 8}
PY = sys.executable

# Per-call usage observed in the paper's runs (used for the estimates; see README "Costs and runtimes").
EST = {"agent_prompt_tokens": 8600, "agent_completion_tokens": 90, "agent_s": 6.0,
       "judge_prompt_tokens": 2000, "judge_spec_prompt_tokens": 4900, "judge_completion_tokens": 100, "judge_s": 3.5,
       "access_prompt_tokens": 9500, "access_completion_tokens": 285, "access_s": 11.0,
       "probe_prompt_tokens": 1150, "probe_completion_tokens": 60, "probe_s": 2.0}
N_TASKS = {"pilot": 30, "all": 300}


def parse_steps(spec: str | None):
    if not spec:
        return list(STEPS)
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-"); out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


class Pipeline:
    def __init__(self, cfg_path: Path, dry: bool, yes: bool, runs_root: Path | None):
        self.cfg = miniyaml.load(cfg_path)
        self.cfg_path = cfg_path
        self.name = self.cfg["name"]
        self.base = (runs_root or ROOT / "runs") / self.name
        self.raw = self.base / "mab_runs"
        self.der = self.base / "derived"
        self.dry, self.yes = dry, yes
        self.archived = bool(self.cfg.get("import_archived"))
        self.offline = bool(self.cfg.get("offline"))
        self.single = self.cfg.get("design") == "single_model"
        if self.single and (set(self.cfg["agents"]) != {"full_deepseekv32"} or len(self.cfg["judges"]) != 1):
            raise ValueError("single_model requires one full_deepseekv32 run and one judge")
        self.models = self.cfg.get("models") or {}
        self.log = []

    # ------------------------------------------------------------------ helpers
    def env(self):
        e = dict(os.environ, MAB_RUNS_DIR=str(self.raw), MAB_TASKS_DIR=str(HARNESS / "mab_tasks"))
        e["NO_PROXY"] = ",".join(x for x in (e.get("NO_PROXY", ""), "localhost", "127.0.0.1") if x)
        e["PYTHONUNBUFFERED"] = "1"
        return e

    @staticmethod
    def show(c):
        """Display form of a command argument: package-relative paths, 'python' for the interpreter."""
        t = str(c)
        if t == PY:
            return "python"
        for pre in (str(ROOT) + os.sep, str(ROOT)):
            t = t.replace(pre, "" if pre.endswith(os.sep) else ".")
        return t.replace("\\", "/")

    def stepdir(self, n):
        d = self.base / f"{n:02d}_{STEPS[n]}"
        if not self.dry:
            d.mkdir(parents=True, exist_ok=True)
        return d

    def run(self, n, cmd, cwd=None, log_name=None, check=True, background=False):
        args = [str(c) for c in cmd]
        def option(key, default=""):
            return args[args.index(key) + 1] if key in args else default
        script = Path(args[1]).name if len(args) > 1 else ""
        labels = {
            "judge_agentic.py": "Aktenzugriff-Experiment",
            "probes.py": "Wissensfragen-Experiment",
            "build_probes.py": "Wissensfragen vorbereiten",
            "make_access_sample.py": "Aktenprüfung vorbereiten",
            "grade_outcomes.py": "Aufgabenergebnisse bewerten",
            "trace_runs.py": "Fehlertypen einordnen",
            "analyse_single.py": "Ergebnisse auswerten",
        }
        label = labels.get(script, STEPS[n])
        if script == "judge_runs.py":
            label = ("Dokumentations-Experiment" if "--with-spec" in args else
                     "Checklisten-Experiment" if option("--prompt") == "verify" else "Basisprüfung")
            label += " · " + option("--runs")
        elif script == "run_agents.py":
            role = option("--run-name")
            label = ("Verifikationshinweis-Experiment" if role.startswith("cue") else
                     "Kontrolllauf" if option("--agent") in ("replay", "null") else "Hauptlauf")
            label += " · " + role
        print(f"\n▶ {label}", flush=True)
        child_env = dict(self.env(), MAB_PROGRESS_LABEL=label)
        shown = " ".join(shlex.quote(self.show(c)) for c in cmd)
        print(f"  $ {shown}")
        self.log.append((n, shown))
        if self.dry:
            return 0
        logf = self.stepdir(n) / (log_name or f"cmd_{len(self.log):03d}.log")
        offset = logf.stat().st_size if logf.exists() else 0
        print(f"  Live log: {logf}", flush=True)
        started = time.monotonic()
        heartbeat = started
        with open(logf, "ab") as fh:
            if background:
                return subprocess.Popen([str(c) for c in cmd], cwd=cwd or ROOT, env=child_env, stdout=fh, stderr=subprocess.STDOUT)
            p = subprocess.Popen([str(c) for c in cmd], cwd=cwd or ROOT, env=child_env, stdout=fh, stderr=subprocess.STDOUT)
            # Tail the log rather than PIPE: keep complete logs and show progress even
            # when the child spends a long time in a model call or server startup.
            with open(logf, "r", encoding="utf-8", errors="replace", newline="") as live:
                live.seek(offset)
                try:
                    while True:
                        chunk = live.read()
                        if chunk:
                            print(chunk, end="", flush=True)
                        if p.poll() is not None:
                            print(live.read(), end="", flush=True)
                            break
                        now = time.monotonic()
                        if now - heartbeat >= 30:
                            print(f"  [running {int(now - started)}s] {logf.name}: process active; see monitor for saved results", flush=True)
                            heartbeat = now
                        time.sleep(0.25)
                except KeyboardInterrupt:
                    p.terminate()
                    try:
                        p.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        p.kill()
                        p.wait()
                    raise
        if check and p.returncode:
            raise SystemExit(f"step {n} command failed (exit {p.returncode}); log: {logf}")
        return p.returncode

    def done(self, n, info=None):
        if not self.dry:
            (self.stepdir(n) / "DONE.json").write_text(json.dumps({"finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                                                    **(info or {})}, indent=1), encoding="utf-8")

    def model(self, key):
        m = self.models.get(key)
        if m is None:
            raise SystemExit(f"model '{key}' is not defined in the config")
        return m

    def model_args(self, m, judge=False, jcfg=None):
        args = ["--base-url", m["base_url"]] if m.get("base_url") else []
        args += ["--api-key-env", m.get("api_key_env") or ""]
        if m.get("extra_body"):
            import hashlib
            f = self.base / "configs" / f"extra_body_{hashlib.sha256(json.dumps(m['extra_body'], sort_keys=True).encode()).hexdigest()[:8]}.json"
            if not self.dry:
                f.parent.mkdir(parents=True, exist_ok=True); f.write_text(json.dumps(m["extra_body"]), encoding="utf-8")
            args += ["--extra-body", f"@{f}"]
        if m.get("tpm"):
            args += ["--tpm", str(m["tpm"])]
        if m.get("rpm"):
            args += ["--rpm", str(m["rpm"])]
        if m.get("strip_reasoning"):
            args += ["--strip-reasoning"]
        return args

    def check_keys(self, keys):
        missing = [k for k in keys if k and not os.environ.get(k)]
        if missing and not self.dry:
            raise SystemExit(f"missing API key environment variable(s): {', '.join(sorted(set(missing)))}")
        if missing:
            print(f"  (note: {', '.join(sorted(set(missing)))} not set in this shell)")

    def confirm(self, n, est):
        print(f"  estimate for step {n}: {est['calls']:,} model calls, about {est['tokens'] / 1e6:.1f} M tokens, "
              f"USD {est['usd']:.2f} at the configured prices, about {est['hours']:.1f} h wall time")
        if self.dry:
            return
        if not self.yes:
            raise SystemExit(f"step {n} calls paid or rate-limited APIs; re-run with --yes to proceed")

    @staticmethod
    def cost(m, calls, pt, ct):
        return calls * (pt * (m.get("price_in") or 0) + ct * (m.get("price_out") or 0)) / 1e6

    def import_dir(self, n, src: Path, dst: Path):
        print(f"  import {self.show(src)} -> {self.show(dst)}")
        self.log.append((n, f"import {self.show(src)} -> {self.show(dst)}"))
        if not self.dry:
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)

    def import_file(self, n, src: Path, dst: Path):
        print(f"  import {self.show(src)} -> {self.show(dst)}")
        self.log.append((n, f"import {self.show(src)} -> {self.show(dst)}"))
        if not self.dry:
            dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy(src, dst)

    # ------------------------------------------------------------------ steps
    def s0_server(self, n):
        f = self.cfg.get("fhir") or {}
        url = f.get("base_url", "http://localhost:8080/fhir/")
        mode = f.get("mode", "auto")
        if self.archived:
            print("  chain test: no FHIR server needed (offline steps only)"); return
        if mode == "auto":
            mode = "windows-nodocker" if os.name == "nt" else ("docker" if shutil.which("docker") else "windows-nodocker")
        print(f"  mode: {mode}")
        if mode == "external":
            print(f"  expecting a running server at {url}")
        elif mode == "docker":
            self.run(n, ["docker", "pull", f["image"]])
            self.run(n, ["docker", "run", "-d", "--rm", "--name", "medagentbench-fhir", "-p", "8080:8080", f["image"]], check=False)
        else:
            sd = HARNESS / f.get("server_dir", "mab_server")
            if not (sd / "app" / "main.war").exists() or self.dry:
                self.run(n, [PY, MH / "fetch_server.py", sd], cwd=HARNESS, log_name="fetch_server.log")
            if f.get("java_env"):
                os.environ["CONDA_PREFIX"] = f["java_env"]
            self.run(n, [PY, MH / "start_server.py"], cwd=HARNESS, log_name="fhir_server.log", background=True)
        if self.dry:
            return
        for _ in range(90):
            try:
                with urllib.request.urlopen(url + "metadata", timeout=5) as r:
                    if r.status == 200:
                        print("  FHIR server ready"); return
            except Exception:
                time.sleep(5)
        raise SystemExit(f"FHIR server not reachable at {url}")

    def s1_agents(self, n):
        ag = self.cfg["agents"]
        if self.archived:
            for role in ag:
                src = ROOT / "data" / "raw" / role
                if (src / "results.jsonl").exists():
                    self.import_dir(n, src, self.raw / role)
                else:
                    print(f"  {role}: raw trajectories not archived; importing its judge files only (see data/raw/{role}/README.md)")
                    if src.exists():
                        self.import_dir(n, src, self.raw / role)
            return
        est = {"calls": 0, "tokens": 0, "usd": 0.0, "hours": 0.0}
        cmds, keys = [], []
        for role, a in ag.items():
            m = self.model(a["model"]); keys.append(m.get("api_key_env"))
            n_att = N_TASKS.get(a["tasks"], len(str(a["tasks"]).split(","))) * int(a["attempts"])
            calls = n_att * 5  # about 5 rounds per attempt
            est["calls"] += calls; est["tokens"] += n_att * (EST["agent_prompt_tokens"] + EST["agent_completion_tokens"])
            est["usd"] += self.cost(m, n_att, EST["agent_prompt_tokens"], EST["agent_completion_tokens"])
            tok = n_att * (EST["agent_prompt_tokens"] + EST["agent_completion_tokens"])
            est["hours"] += max(n_att * EST["agent_s"] / max(1, int(m.get("workers") or 1)),
                                60.0 * tok / m["tpm"] if m.get("tpm") else 0.0,
                                60.0 * calls / m["rpm"] if m.get("rpm") else 0.0) / 3600
            c = [PY, MH / "run_agents.py", "--agent", "openai", "--model", m["model"], "--tasks", str(a["tasks"]),
                 "--n", str(a["attempts"]), "--temperature", str(m.get("temperature") if m.get("temperature") is not None else -1),
                 "--max-output-tokens", str(m.get("max_output_tokens", 4096)), "--workers", str(m.get("workers") or 3),
                 "--run-name", role] + self.model_args(m)
            if a.get("max_total_tokens"):
                c += ["--max-total-tokens", str(a["max_total_tokens"])]
            if m.get("price_in") is not None:
                c += ["--price-in", str(m["price_in"]), "--price-out", str(m.get("price_out") or 0)]
            if m.get("lenient_actions"):
                c += ["--lenient-actions"]
            cmds.append(c)
        self.check_keys(keys); self.confirm(n, est)
        for c in cmds:
            self.run(n, c, log_name=f"{c[c.index('--run-name') + 1]}.log")

    def s2_controls(self, n):
        ctl = self.cfg.get("controls") or {}
        if self.archived:
            for r in ctl.get("judged", []):
                self.import_dir(n, ROOT / "data" / "raw" / r, self.raw / r)
            if ctl.get("full"):
                print("  300-task controls are not archived")
            return
        for r in ctl.get("judged", []):
            self.run(n, [PY, MH / "run_agents.py", "--agent", "replay" if "replay" in r else "null", "--tasks", str(ctl.get("tasks", "pilot")), "--n", "1",
                         "--workers", "6", "--run-name", r], log_name=f"{r}.log")
        for r in ctl.get("full", []):
            self.run(n, [PY, MH / "run_agents.py", "--agent", "replay" if "replay" in r else "null", "--tasks", "all", "--n", "1",
                         "--workers", "6", "--run-name", r], log_name=f"{r}.log")

    def s3_grade(self, n):
        runs = [r for r in self.cfg["agents"] if not self.archived or (ROOT / "data" / "raw" / r / "results.jsonl").exists()]
        c = [PY, PL / "grade_outcomes.py", "--runs", ",".join(runs), "--runs-dir", self.raw, "--derived", self.der,
             "--mode", "offline" if self.offline else "online"]
        if self.offline:
            c += ["--stored", ROOT / "data" / "derived" / "pilot_outcome_classes.csv"]
        self.run(n, c, log_name="grade.log")
        if self.archived and "full_deepseekv32" not in runs:
            print("  full_deepseekv32: outcome classes come with the archived tracer table (step 4)")

    def s4_trace(self, n):
        c = [PY, PL / "trace_runs.py", "--runs", ",".join(self.cfg["agents"]), "--runs-dir", self.raw, "--derived", self.der,
             "--mode", "offline" if self.offline else "online"]
        if self.offline:
            c += ["--import-from", ROOT / "data" / "derived"]
        self.run(n, c, log_name="trace.log")

    def s5_provenance(self, n):
        c = [PY, PL / "code_provenance.py", "--runs-dir", self.raw, "--derived", self.der]
        if self.archived:
            c += ["--import-from", ROOT / "data" / "derived" / "provenance_coding.csv"]
        if self.single:
            model = self.model(self.cfg["agents"]["full_deepseekv32"]["model"])
            c += ["--single-run", "full_deepseekv32", "--agent-name", model["name"]]
        self.run(n, c, log_name="provenance.log")

    def s6_judges(self, n):
        J = self.cfg["judges"]; ra = self.cfg.get("record_access") or {}
        if self.archived:
            print("  judge verdict files were imported with the run folders (steps 1-2)")
            self.run(n, [PY, PL / "make_access_sample.py", "--runs-dir", self.raw, "--derived", self.der,
                         "--seed", str(ra.get("sample_seed", 2027))], log_name="access_sample.log")
            return
        est = {"calls": 0, "tokens": 0, "usd": 0.0, "hours": 0.0}; cmds, keys = [], []
        n_att = {r: N_TASKS.get(a["tasks"], 30) * int(a["attempts"]) for r, a in self.cfg["agents"].items()}
        for r in (self.cfg.get("controls") or {}).get("judged", []):
            n_att[r] = N_TASKS.get((self.cfg.get("controls") or {}).get("tasks", "pilot"), 30)
        for tag, j in J.items():
            m = self.model(j["model"]); keys.append(m.get("api_key_env"))
            common = ["--judge", m["model"], "--tag", tag, "--workers", str(m.get("workers") or 3),
                      "--temperature", str(j.get("temperature", 0)), "--max-tokens", str(j.get("max_tokens", 400))] + self.model_args(m)
            if j.get("structured_output"):
                common += ["--structured-output"]
            for cond, flags, pt in [("neutral", [], EST["judge_prompt_tokens"]), ("spec", ["--with-spec"], EST["judge_spec_prompt_tokens"]),
                                    ("verify", ["--prompt", "verify"], EST["judge_prompt_tokens"])]:
                runs = j.get(cond) or []
                if not runs:
                    continue
                k = sum(n_att.get(r, 0) for r in runs)
                est["calls"] += k; est["tokens"] += k * (pt + EST["judge_completion_tokens"])
                est["usd"] += self.cost(m, k, pt, EST["judge_completion_tokens"])
                est["hours"] += max(k * EST["judge_s"] / max(1, int(m.get("workers") or 1)),
                                    60.0 * k * (pt + 100) / m["tpm"] if m.get("tpm") else 0.0,
                                    60.0 * k / m["rpm"] if m.get("rpm") else 0.0) / 3600
                for run in runs:
                    cmds.append((f"judge_{tag}_{cond}_{run}.log", [PY, MH / "judge_runs.py", *common, *flags, "--runs", run]))
        acc = [t for t, j in J.items() if j.get("access")]
        for tag in acc:
            m = self.model(J[tag]["model"]); k = n_att["full_deepseekv32"] if self.single else 420
            est["calls"] += k * 3; est["tokens"] += k * (EST["access_prompt_tokens"] + EST["access_completion_tokens"])
            est["usd"] += self.cost(m, k, EST["access_prompt_tokens"], EST["access_completion_tokens"])
            est["hours"] += k * EST["access_s"] / max(1, int(ra.get("workers") or 1)) / 3600
        self.check_keys(keys); self.confirm(n, est)
        for log, c in cmds:
            self.run(n, c, log_name=log)
        for tag in acc:
            m = self.model(J[tag]["model"])
            self.run(n, [PY, PL / "make_access_sample.py", "--runs-dir", self.raw, "--derived", self.der, "--judge", tag,
                         "--seed", str(ra.get("sample_seed", 2027))] + (["--all-run", "full_deepseekv32"] if self.single else []), log_name="access_sample.log")
            self.run(n, [PY, MH / "judge_agentic.py", "--sample", self.raw / "record_access" / "agentic_judge_sample.json",
                         "--judge", m["model"], "--tag", f"{tag}_access", "--max-queries", str(ra.get("max_queries", 4)),
                         "--workers", str(ra.get("workers", 6)), "--temperature", str(J[tag].get("temperature", 0)),
                         "--max-tokens", str(J[tag].get("max_tokens", 400))] + self.model_args(m) + (["--structured-output"] if J[tag].get("structured_output") else []) + (["--continue-on-errors"] if ra.get("continue_on_errors") else []) + ["--summary-file", self.stepdir(n) / f"{tag}_access_status.json"], log_name="judge_access.log")

    def s7_probes(self, n):
        pr = self.cfg.get("probes") or {}; out = self.raw / "probes"
        if self.archived:
            for f in ["probes_deepseekv32.jsonl", "probes_deepseekv32_controls.jsonl", "probes_instances.json", "probes_controls.json"]:
                self.import_file(n, ROOT / "data" / "raw" / "probes" / f, out / f)
            print("  (item construction needs the full-run trajectories and, for controls, the FHIR server; not re-run here)")
            return
        m = self.model(pr["model"])
        self.run(n, [PY, PL / "build_probes.py", "--runs-dir", self.raw, "--derived", self.der, "--out", out, "--controls"], log_name="build_probes.log")
        k = 250 * int(pr.get("samples", 3))
        est = {"calls": k, "tokens": k * (EST["probe_prompt_tokens"] + EST["probe_completion_tokens"]),
               "usd": self.cost(m, k, EST["probe_prompt_tokens"], EST["probe_completion_tokens"]), "hours": k * EST["probe_s"] / max(1, int(pr.get("workers", 1))) / 3600}
        self.check_keys([m.get("api_key_env")]); self.confirm(n, est)
        for inst, res in [("probes_instances.json", "probes_deepseekv32.jsonl"), ("probes_controls.json", "probes_deepseekv32_controls.jsonl")]:
            self.run(n, [PY, MH / "probes.py", "run", "--instances", out / inst, "--model", m["model"], "--samples", str(pr.get("samples", 3)),
                         "--temperature", str(pr.get("temperature", 0.8)), "--max-tokens", str(pr.get("max_tokens", 200)),
                         "--workers", str(pr.get("workers", 6)), "--out", out / res] + self.model_args(m), log_name=f"{res}.log")

    def s8_cue(self, n):
        cue = self.cfg.get("cue") or {}
        if self.archived:
            for f in ["cue_deepseekv32_mechanisms.csv", "first_query_codes.csv"]:
                self.import_file(n, ROOT / "data" / "derived" / f, self.der / f)
            self.import_file(n, ROOT / "data" / "raw" / "cue_deepseekv32" / "run_config.json", self.raw / "cue_deepseekv32" / "run_config.json")
            print("  (cue trajectories are not archived; the archived tracer table of the cue run is used)")
            return
        role = cue.get("agent", "full_deepseekv32"); a = self.cfg["agents"][role]; m = self.model(a["model"])
        ids_file = self.stepdir(n) / "cue_tasks.txt"
        self.run(n, [PY, PL / "select_cue_tasks.py", "--mechanisms", self.der / f"{role}_mechanisms.csv", "--out", ids_file], log_name="select.log")
        sentence = (HARNESS / "prompts" / "cue_sentence.txt").read_text(encoding="utf-8")
        k = 83 * int(cue.get("attempts", 2))
        est = {"calls": k * 5, "tokens": k * (EST["agent_prompt_tokens"] + EST["agent_completion_tokens"]),
               "usd": self.cost(m, k, EST["agent_prompt_tokens"], EST["agent_completion_tokens"]), "hours": k * EST["agent_s"] / max(1, int(m.get("workers") or 1)) / 3600}
        self.check_keys([m.get("api_key_env")]); self.confirm(n, est)
        tasks = "@" + str(ids_file)
        if not self.dry:
            tasks = ids_file.read_text(encoding="utf-8").strip()
            if self.single and not tasks:
                (self.stepdir(n) / "SKIPPED.json").write_text(json.dumps({"reason": "No evidence-gathering errors; no cue tasks"}))
                print("  no evidence-gathering errors: cue experiment not applicable")
                return
        c = [PY, MH / "run_agents.py", "--agent", "openai", "--model", m["model"], "--tasks", tasks, "--n", str(cue.get("attempts", 2)),
             "--temperature", str(m.get("temperature") if m.get("temperature") is not None else -1),
             "--max-output-tokens", str(m.get("max_output_tokens", 4096)), "--workers", str(m.get("workers") or 3),
             "--context-suffix", sentence, "--run-name", "cue_deepseekv32"] + self.model_args(m)
        if cue.get("max_total_tokens"):
            c += ["--max-total-tokens", str(cue["max_total_tokens"])]
        self.run(n, c, log_name="cue_run.log")
        mode = "offline" if self.offline else "online"
        self.run(n, [PY, PL / "grade_outcomes.py", "--runs", "cue_deepseekv32", "--runs-dir", self.raw, "--derived", self.der, "--mode", mode], log_name="cue_grade.log")
        self.run(n, [PY, PL / "trace_runs.py", "--runs", "cue_deepseekv32", "--runs-dir", self.raw, "--derived", self.der, "--mode", mode], log_name="cue_trace.log")
        self.run(n, [PY, PL / "first_query_codes.py", "--runs-dir", self.raw, "--derived", self.der], log_name="first_query_codes.log")

    def single_analysis_command(self, n):
        return [PY, PL / "analyse_single.py", "--config", self.cfg_path,
                "--runs-dir", self.raw, "--derived", self.der,
                "--out", self.base / "09_analysis" / "outputs"]

    def s9_analysis(self, n):
        if self.single:
            self.run(n, self.single_analysis_command(n), log_name="analysis.log")
            return
        study = self.base / "study.json"
        if not self.dry:
            names = {r: (self.models.get(a["model"], {}) or {}).get("name") for r, a in self.cfg["agents"].items()}
            jn = {t: (self.models.get(j["model"], {}) or {}).get("name") for t, j in self.cfg["judges"].items()}
            dev = {t: (self.models.get(j["model"], {}) or {}).get("developer") for t, j in self.cfg["judges"].items()}
            s = {"agent_name": {k: v for k, v in names.items() if v}, "judge_name": {k: v for k, v in jn.items() if v},
                 "lineage": {k: v for k, v in dev.items() if v}}
            study.write_text(json.dumps(s, indent=1), encoding="utf-8")
        self.run(n, [PY, ROOT / "reproduce.py", "--level", "A", "--raw", self.raw, "--derived", self.der,
                     "--out", self.stepdir(n) / "outputs", "--study", study, "--no-verify"], log_name="analysis.log")

    def s10_compare(self, n):
        if self.single:
            self.run(n, self.single_analysis_command(n) + ["--compare-out", self.stepdir(n)], log_name="compare.log")
            return
        c = [PY, PL / "compare_report.py", "--outputs", self.base / "09_analysis" / "outputs", "--out", self.stepdir(n)]
        if self.cfg.get("expect_paper"):
            c.append("--expect-paper")
        self.run(n, c, log_name="compare.log")

    def go(self, steps):
        print(f"config {self.cfg_path.name} -> {self.show(self.base)}{'  [DRY RUN: nothing is executed]' if self.dry else ''}")
        if self.archived:
            print("mode: chain test on archived data (no API calls; offline grading/tracing)")
        for n in steps:
            print(f"\n== step {n}: {STEPS[n]}{'  (paid API calls)' if n in PAID and not self.archived else ''}")
            if not self.dry and (self.base / f"{n:02d}_{STEPS[n]}" / "DONE.json").exists() and n not in (9, 10):
                print("  already done (delete the DONE.json marker to redo; the underlying scripts also resume)"); continue
            getattr(self, f"s{n}_{STEPS[n]}")(n)
            info = None
            if n == 6 and not self.dry:
                access = {p.stem: json.loads(p.read_text()) for p in self.stepdir(n).glob("*_access_status.json")}
                if access:
                    info = {"record_access": access,
                            "status": "completed_with_missing_verdicts" if any(
                                v.get("status") == "completed_with_missing_verdicts" for v in access.values()) else "completed"}
            self.done(n, info)
        if not self.dry:
            (self.base / "pipeline_commands.txt").write_text("\n".join(f"[{n}] {c}" for n, c in self.log), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--steps", default=None, help="e.g. 3-10 or 1,2,6 (default: all)")
    ap.add_argument("--dry-run", action="store_true", help="print the planned commands and estimates, run nothing")
    ap.add_argument("--yes", action="store_true", help="allow the paid steps")
    ap.add_argument("--runs-root", default=None, help="parent folder of runs/<name> (default: <package>/runs)")
    a = ap.parse_args()
    Pipeline(Path(a.config).resolve(), a.dry_run, a.yes, Path(a.runs_root).resolve() if a.runs_root else None).go(parse_steps(a.steps))


if __name__ == "__main__":
    main()
