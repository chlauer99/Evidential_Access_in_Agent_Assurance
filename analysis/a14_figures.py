"""a14 - Figures 1 and 2 (fig_discrimination.png/.pdf, fig_detection.png/.pdf).

Figure 1 plots outputs/judge_conditions_summary.csv directly. Figure 2 is a summary grid whose cell texts carry
numbers from the text (each is checked in paper_numbers.csv). The drawing code is the final published script
(make_fig_discrimination.py / make_fig_detection.py, 27 Sep 2026) with the data path and style made local.
Fonts: Arial if installed, otherwise Liberation Sans / DejaVu Sans (glyph metrics then differ slightly).
Outputs: outputs/fig_discrimination.png/.pdf, outputs/fig_detection.png/.pdf
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import matplotlib
matplotlib.use("Agg")
import matplotlib as mpl
from matplotlib import font_manager
from config import OUT

HERE = Path(__file__).resolve().parent


def apply_figure_style(font="Arial", sizes=(8, 7, 7)):
    """Minimal stand-in for the figure-style helper used for the published figures."""
    have = {f.name for f in font_manager.fontManager.ttflist}
    fam = next((f for f in [font, "Liberation Sans", "Helvetica", "DejaVu Sans"] if f in have), "DejaVu Sans")
    mpl.rcParams.update({"font.family": "sans-serif", "font.sans-serif": [fam, "DejaVu Sans"], "font.size": sizes[0],
                         "axes.titlesize": sizes[0], "axes.labelsize": sizes[0], "xtick.labelsize": sizes[1],
                         "ytick.labelsize": sizes[1], "legend.fontsize": sizes[2], "axes.spines.top": False,
                         "axes.spines.right": False, "axes.linewidth": 0.6, "xtick.major.width": 0.6,
                         "ytick.major.width": 0.6, "figure.dpi": 100, "savefig.dpi": 300})
    if fam != "Arial":
        mpl.rcParams["mathtext.fontset"] = "dejavusans"
    return fam


def run(script, **ns):
    src = (HERE / "figures" / script).read_text(encoding="utf-8")
    if "Arial" not in {f.name for f in font_manager.fontManager.ttflist}:
        src = src.replace('mpl.rcParams["mathtext.fontset"] = "custom"; mpl.rcParams["mathtext.it"] = "Arial:italic"; mpl.rcParams["mathtext.rm"] = "Arial"',
                          'mpl.rcParams["mathtext.fontset"] = "dejavusans"')
    import os
    cwd = os.getcwd(); os.chdir(OUT)
    try:
        exec(compile(src, script, "exec"), {"apply_figure_style": apply_figure_style, "__name__": "__fig__", **ns})
    finally:
        os.chdir(cwd)
    print(f"  wrote outputs/{script.replace('make_', '').replace('.py', '')}.png/.pdf")


run("make_fig_discrimination.py", JCS_PATH=str(OUT / "judge_conditions_summary.csv"))
run("make_fig_detection.py")
