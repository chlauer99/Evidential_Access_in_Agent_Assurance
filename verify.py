"""Compare regenerated outputs with the published copies and check the key numbers of the manuscript.

  python verify.py [--outputs outputs] [--published data/published] [--numbers paper_numbers.csv]

File checks (outputs/<f> vs data/published/<f>): same columns and row count; rows aligned by their non-float
columns; integer-valued columns must match exactly; bootstrap interval columns (lo/hi) within 0.01; other
floats (rounded proportions) within 0.005; strings exactly. Figures: the PNG must exist with the published pixel
size, and the PDF must exist.
Number checks: each row of paper_numbers.csv names an output file, a row filter, a column and an optional
transform; the value must equal the number printed in the paper within the stated tolerance.
Prints a PASS/FAIL table, writes outputs/verify_report.csv and exits with status 1 if anything fails.
"""
from __future__ import annotations

import argparse
import math
import re
import struct
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent

# (output file, published file). Every published CSV that Level A regenerates.
FILE_CHECKS = [
    "analysis_denominators.csv", "judge_attempts.csv", "judge_summary.csv", "judge_discrimination.csv",
    "judge_reason_validity.csv", "judge_conditions_summary.csv", "agentic_judge_verdicts.csv",
    "agentic_judge_discrimination.csv", "agentic_judge_readonly.csv", "paired_condition_contrasts.csv",
    "paired_condition_contrasts_pooled.csv", "judge_error_sharing.csv", "judge_error_kappa_ci.csv",
    "probe_summary.csv", "cue_effects.csv", "provenance_summary.csv", "capability_gradient.csv",
]
FIGURES = ["fig_discrimination", "fig_detection"]
CI_COL = re.compile(r"(^|_)(lo|hi)$|^ci_(lo|hi)$|_lo$|_hi$")


def _png_size(p):
    with open(p, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def _is_intlike(s):
    s = pd.to_numeric(s, errors="coerce")
    s = s.dropna()
    return len(s) > 0 and np.all(np.isclose(s, np.round(s)))


def compare_csv(out, pub):
    a = pd.read_csv(out, keep_default_na=True)
    b = pd.read_csv(pub, keep_default_na=True)
    if list(a.columns) != list(b.columns):
        return "FAIL", f"columns differ: {sorted(set(a.columns) ^ set(b.columns)) or 'order'}"
    if len(a) != len(b):
        return "FAIL", f"row count {len(a)} vs published {len(b)}"
    keys = [c for c in b.columns if not pd.api.types.is_float_dtype(b[c]) or _is_intlike(b[c])]
    keys = [c for c in keys if not (pd.api.types.is_float_dtype(b[c]) and b[c].isna().all())]
    def key_frame(d):
        k = d[keys].copy()
        for c in keys:
            k[c] = k[c].astype(str)
        return k
    a = a.iloc[key_frame(a).sort_values(keys, kind="mergesort").index].reset_index(drop=True) if keys else a
    b = b.iloc[key_frame(b).sort_values(keys, kind="mergesort").index].reset_index(drop=True) if keys else b
    worst, exact, notes = 0.0, True, []
    for c in b.columns:
        x, y = a[c], b[c]
        num = pd.api.types.is_numeric_dtype(y) or pd.api.types.is_bool_dtype(y)
        if num and not pd.api.types.is_bool_dtype(y):
            xv = pd.to_numeric(x, errors="coerce").to_numpy(float); yv = y.to_numpy(float)
            nan_ok = np.array_equal(np.isnan(xv), np.isnan(yv))
            if not nan_ok:
                return "FAIL", f"{c}: missing values differ"
            m = ~np.isnan(yv)
            d = np.abs(xv[m] - yv[m]).max() if m.any() else 0.0
            if _is_intlike(y) and _is_intlike(x) and d > 0:
                return "FAIL", f"{c}: counts differ (max diff {d:g})"
            tol = 0.01 if CI_COL.search(c) else 0.005
            if d > tol + 1e-12:
                return "FAIL", f"{c}: max diff {d:.4g} > {tol}"
            if d > 1e-9:
                exact = False; worst = max(worst, d); notes.append(f"{c} {d:.2g}")
        else:
            xs = x.astype(str).where(x.notna(), "<NA>"); ys = y.astype(str).where(y.notna(), "<NA>")
            if not (xs.values == ys.values).all():
                bad = int((xs.values != ys.values).sum())
                return "FAIL", f"{c}: {bad} text value(s) differ"
    return "PASS", ("identical" if exact else f"within tolerance (max {worst:.3g}: {', '.join(notes[:4])})")


def check_figures(outdir, pubdir):
    res = []
    for f in FIGURES:
        o, p = outdir / f"{f}.png", pubdir / "figures" / f"{f}.png"
        if not o.exists() or not (outdir / f"{f}.pdf").exists():
            res.append((f"{f}.png/.pdf", "FAIL", "missing")); continue
        so, sp = _png_size(o), _png_size(p)
        res.append((f"{f}.png/.pdf", "PASS" if so == sp else "FAIL",
                    f"{so[0]}x{so[1]} px (published {sp[0]}x{sp[1]}); visual comparison: see README"))
    return res


def eval_number(row, outdir):
    f = outdir / row.source_file
    if not f.exists():
        return np.nan, "FAIL", f"missing {row.source_file}"
    d = pd.read_csv(f)
    if isinstance(row.row_filter, str) and row.row_filter.strip():
        d = d.query(row.row_filter, engine="python")
    if len(d) != 1:
        return np.nan, "FAIL", f"filter matched {len(d)} rows"
    x = d.iloc[0][row.column]
    try:
        x = float(x)
    except (TypeError, ValueError):
        return np.nan, "FAIL", f"non-numeric value {x!r}"
    v = eval(row.transform, {"math": math, "round": round, "abs": abs}, {"x": x}) if isinstance(row.transform, str) and row.transform.strip() else x
    ok = abs(v - float(row.paper_value)) <= float(row.tolerance) + 1e-12
    return v, "PASS" if ok else "FAIL", ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs", default=str(ROOT / "outputs"))
    ap.add_argument("--published", default=str(ROOT / "data" / "published"))
    ap.add_argument("--numbers", default=str(ROOT / "paper_numbers.csv"))
    ap.add_argument("--files", nargs="*", default=None, help="restrict the file checks to these names")
    ap.add_argument("--skip-figures", action="store_true")
    a = ap.parse_args()
    outdir, pubdir = Path(a.outputs), Path(a.published)
    rows = []
    for f in (a.files if a.files is not None else FILE_CHECKS):
        o, p = outdir / f, pubdir / f
        if not o.exists():
            rows.append(("file", f, "FAIL", "not regenerated")); continue
        st, note = compare_csv(o, p)
        rows.append(("file", f, st, note))
    if not a.skip_figures:
        for name, st, note in check_figures(outdir, pubdir):
            rows.append(("figure", name, st, note))
    nums = pd.read_csv(a.numbers) if Path(a.numbers).exists() else pd.DataFrame()
    for r in nums.itertuples():
        v, st, note = eval_number(r, outdir)
        rows.append(("number", f"{r.id} [{r.exhibit}] {r.description}", st,
                     f"paper {r.paper_value} | reproduced {v:.4g} | tol {r.tolerance} | {r.source_file}" + (f" | {note}" if note else "")))
    R = pd.DataFrame(rows, columns=["kind", "item", "result", "detail"])
    R.to_csv(outdir / "verify_report.csv", index=False)
    w = max(len(s) for s in R["item"]) if len(R) else 10
    w = min(w, 78)
    print(f"{'KIND':7} {'ITEM':{w}} RESULT  DETAIL")
    for r in R.itertuples():
        print(f"{r.kind:7} {r.item[:w]:{w}} {r.result:6}  {r.detail}")
    n_fail = int((R.result == "FAIL").sum())
    by = R.groupby("kind").result.value_counts().unstack(fill_value=0)
    print("\nSummary:\n" + by.to_string())
    print(f"\n{'ALL CHECKS PASSED' if n_fail == 0 else f'{n_fail} CHECK(S) FAILED'} ({len(R)} checks)")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
