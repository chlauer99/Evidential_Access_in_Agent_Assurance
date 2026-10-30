import matplotlib as mpl, matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

apply_figure_style(font="Arial", sizes=(8, 7, 7))
mpl.rcParams["pdf.fonttype"] = 42
mpl.rcParams["savefig.bbox"] = "standard"

# Manuscript v5, Figure 2 (v4 without the second GPT-OSS-120B run). Observed pattern; values for the original study trace to make_fig_detection.py,
# values for the open-weight judges to runs/comparative_analysis/v4 (ow_inferability.csv, ow_locus.csv,
# ow_judge_cells.csv, ow_numbers.csv) from a15_open_weight_runs.py.
LV = {"disc": ("#08519C", "white", "none"),      # most errors rejected
      "part": ("#9ECAE1", "#111111", "none"),    # partial
      "acc":  ("#FBE0CF", "#111111", "#D55E00"), # most errors accepted
      "cert": ("#FFFFFF", "#111111", "#AAAAAA")}
cols = [("Reference +\nfinal state", "rule-based grader"),
        ("Trajectory\nonly", "model judges, 11 pairings"),
        ("Trajectory +\nchecklist", "3 judge configurations"),
        ("Trajectory +\nrecord access", "3 judge configurations")]
rows = [("Evidence gathering,", "not inferable (name search)"),
        ("Evidence gathering,", "inferable (code, next link)"),
        ("Conclusion", "arithmetic, time, rules"),
        ("Action", "orders placed or withheld"),
        ("Correct work accepted", "correct certification")]
C = {(0, 0): ("disc", "Detects the wrong\noutcome; does not\nlocalise it"),
     (0, 1): ("acc", "1 of 349 errors\nrejected in five\nanalyses"),
     (0, 2): ("acc", "2 of 136 errors\nrejected"),
     (0, 3): ("disc", "Qwen 28 of 29;\nGPT-OSS 68 of 107"),
     (1, 0): ("disc", "Detects the wrong\noutcome; does not\nlocalise it"),
     (1, 1): ("part", "Qwen 0.75;\nGPT-OSS 0.26–0.47;\nGPT judges 7 of 240"),
     (1, 2): ("disc", "Qwen 0.96;\nGPT-OSS 0.50;\nDeepSeek: most"),
     (1, 3): ("part", "DeepSeek all; Qwen\n0.89; GPT-OSS\n0.18 (rarely queried)"),
     (2, 0): ("disc", "Detects wrong values"),
     (2, 1): ("part", "Open-weight 0.45–0.91;\njudges made own date\nand arithmetic errors"),
     (2, 2): ("part", "DeepSeek all rejected;\nopen-weight\n0.48–0.86"),
     (2, 3): ("part", "DeepSeek all rejected;\nopen-weight\n0.58–0.91"),
     (3, 0): ("part", "Detects wrong orders;\npassed doing nothing\non 23% of tasks"),
     (3, 1): ("part", "Detects rule breaches;\ninherits evidence errors\nit accepted upstream"),
     (3, 2): ("part", "DeepSeek 13 of 13;\nopen-weight\n0.59–0.88"),
     (3, 3): ("part", "DeepSeek all rejected;\nopen-weight\n0.52–0.94"),
     (4, 0): ("cert", "0.78–0.79 (rejects\nnon-conforming form)"),
     (4, 1): ("cert", "GPT 0.73–0.86;\nDeepSeek 0.35–0.39;\nopen-weight 0.66–0.73"),
     (4, 2): ("cert", "DeepSeek 0.35–0.40;\nopen-weight 0.73–0.90"),
     (4, 3): ("cert", "DeepSeek 0.30–0.37;\nopen-weight 0.70–0.80")}

W, H = 16 / 2.54, 7.4 / 2.54
fig = plt.figure(figsize=(W, H))
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
x0, cw = 1.42, (W - 1.42 - 0.02) / 4
top = H - 0.44
rh = [0.45, 0.45, 0.45, 0.45, 0.45]
yt = [top]
for h in rh: yt.append(yt[-1] - h)
g = 0.022
# column headers
for j, (h1, h2) in enumerate(cols):
    cx = x0 + j * cw + cw / 2
    ax.text(cx, top + 0.28, h1, ha="center", va="center", fontsize=8, fontweight="bold", linespacing=1.05)
    ax.text(cx, top + 0.08, h2, ha="center", va="center", fontsize=7, color="#555555")
ax.text(0.04, top + 0.28, "Observed in\nthis study", ha="left", va="center", fontsize=8, fontweight="bold", color="#333333")
ax.text(0.04, top + 0.08, "error locus", ha="left", va="center", fontsize=7, color="#555555")
# rows
for i, (h, sub) in enumerate(rows):
    cy = (yt[i] + yt[i + 1]) / 2
    ax.text(0.04, cy + 0.07, h, ha="left", va="center", fontsize=8, fontweight="bold")
    ax.text(0.04, cy - 0.09, sub, ha="left", va="center", fontsize=7, color="#555555")
    for j in range(4):
        lvl, txt = C[(i, j)]; fc, tc, ec = LV[lvl]
        x, y = x0 + j * cw + g, yt[i + 1] + g
        w, hh = cw - 2 * g, rh[i] - 2 * g
        ax.add_patch(Rectangle((x, y), w, hh, facecolor=fc, edgecolor=ec,
                               linewidth=1.3 if lvl == "acc" else 0.6))
        ax.text(x + w / 2, y + hh / 2, txt, ha="center", va="center", fontsize=7, color=tc, linespacing=1.1)
ax.plot([0.04, x0 + 4 * cw], [yt[4], yt[4]], color="#444444", lw=0.6)
# legend
ly = yt[5] - 0.13
items = [("disc", "most errors rejected"), ("part", "partial or judge-dependent"), ("acc", "most errors accepted")]
lx = x0 + g
for k, (lvl, lab) in enumerate(items):
    fc, _, ec = LV[lvl]; xx = lx + k * 1.75
    ax.add_patch(Rectangle((xx, ly - 0.055), 0.2, 0.11, facecolor=fc, edgecolor=ec,
                           linewidth=1.1 if lvl == "acc" else 0.6))
    ax.text(xx + 0.26, ly, lab, ha="left", va="center", fontsize=7)
ax.text(0.04, ly, "Detection rows:", ha="left", va="center", fontsize=7, color="#555555")
fig.savefig("fig_detection_v5.png", dpi=300)
fig.savefig("fig_detection_v5.pdf")
