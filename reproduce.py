"""Reproduce the paper's derived tables.

  python reproduce.py --level A                 # all tables from data/ into outputs/, then verify.py
  python reproduce.py --level A --only a03 a05  # a subset of the analysis scripts
  python reproduce.py --level A --raw runs/x/mab_runs --derived runs/x/derived --out runs/x/09_analysis/outputs \\
                      [--study runs/x/study.json] [--no-verify]     # Level A analyses on a NEW run (Level B step 9)
  python reproduce.py --level B                 # prints how to re-run the experiments (run_pipeline.py)

Level A needs no network, API key or FHIR server (Python >= 3.10 with numpy, pandas, matplotlib).
Runtime on a 16-core laptop: about 4 minutes (a03 and a05 dominate: AUROC inside a 2,000-draw bootstrap).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ["a01_attempts_table.py", "a02_outcome_classes.py", "a03_judge_discrimination.py", "a04_record_access.py",
           "a05_judge_conditions.py", "a06_paired_contrasts.py", "a07_error_dependence.py", "a08_probes.py",
           "a09_cue_effects.py", "a10_provenance.py", "a11_capability_gradient.py", "a12_mechanism_table.py",
           "a13_paper_extras.py"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--level", choices=["A", "B"], required=True)
    ap.add_argument("--only", nargs="*", default=None, help="script prefixes to run, e.g. a03 a05")
    ap.add_argument("--raw", default=None, help="run folders to analyse (default data/raw)")
    ap.add_argument("--derived", default=None, help="per-attempt tables (default data/derived)")
    ap.add_argument("--out", default=None, help="output folder (default outputs/)")
    ap.add_argument("--study", default=None, help="JSON with display names / developers of the role slots")
    ap.add_argument("--no-verify", action="store_true", help="skip verify.py (e.g. for runs with other LLMs)")
    a = ap.parse_args()
    if a.level == "B":
        print("Level B re-runs the experiments (FHIR server + model APIs). Start with a dry run:\n"
              "  python harness/run_pipeline.py --config harness/configs/paper.yaml --dry-run\n"
              "See PACKAGE_README.md, section 'Level B: re-run with other LLMs'.")
        return 0
    env = dict(os.environ)
    for k, v in [("REPRO_RAW", a.raw), ("REPRO_DERIVED", a.derived), ("REPRO_OUT", a.out), ("REPRO_STUDY", a.study)]:
        if v:
            env[k] = str(Path(v).resolve())
    out = Path(env.get("REPRO_OUT", ROOT / "outputs"))
    out.mkdir(parents=True, exist_ok=True)
    todo = [s for s in SCRIPTS if not a.only or any(s.startswith(p) for p in a.only)]
    t_all = time.time(); failed = []
    for s in todo:
        t = time.time()
        print(f"[{s}]", flush=True)
        p = subprocess.run([sys.executable, str(ROOT / "analysis" / s)], cwd=ROOT, env=env)
        print(f"  {'ok' if p.returncode == 0 else 'FAILED'} in {time.time() - t:.1f} s", flush=True)
        if p.returncode:
            failed.append(s)
    print(f"analysis scripts finished in {time.time() - t_all:.0f} s; failed: {failed or 'none'}")
    if failed:
        return 1
    if a.no_verify:
        return 0
    v = [sys.executable, str(ROOT / "verify.py"), "--outputs", str(out)]
    v += ["--skip-figures"]
    return subprocess.run(v, cwd=ROOT, env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
