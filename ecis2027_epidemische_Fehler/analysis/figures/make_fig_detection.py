import matplotlib as mpl, matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

apply_figure_style(font="Arial", sizes=(8, 7, 7))
mpl.rcParams["pdf.fonttype"] = 42
mpl.rcParams["savefig.bbox"] = "standard"

# Observed pattern; every value traces to manuscript v6 (Sections 5.3-5.6, Figure 2) or
# judge_conditions_summary.csv (certification ranges) -- see exhibits_changelog.md
LV = {"disc": ("#08519C", "white", "none"),      # most errors rejected
      "part": ("#9ECAE1", "#111111", "none"),    # partial
      "acc":  ("#FBE0CF", "#111111", "#D55E00"), # most errors accepted
      "cert": ("#FFFFFF", "#111111", "#AAAAAA")}
cols = [("Reference +\nfinal state", "rule-based grader, all attempts"),
        ("Trajectory\nonly", "model judges, 7 pairings"),
        ("Trajectory +\nchecklist", "DeepSeek judge, n = 477"),
        ("Trajectory +\nrecord access", "DeepSeek judge, n = 418")]
rows = [("Evidence gathering", "codes, pages, time window"),
        ("Conclusion", "arithmetic, time, rules"),
        ("Action", "orders placed or withheld"),
        ("Correct work accepted", "correct certification")]
C = {(0, 0): ("disc", "Detects the wrong\noutcome; does not\nlocalise it"),
     (0, 1): ("acc", "Accepted unless visible\nin the trajectory; GPT\njudges: 233 of 240"),
     (0, 2): ("disc", "Listed failure modes\ndetected; unread pages\naccepted in 19% and 0%"),
     (0, 3): ("disc", "0 of 216 errors\naccepted; judge queries\nfound the missing data"),
     (1, 0): ("disc", "Detects wrong values"),
     (1, 1): ("part", "Partial; judges made\ntheir own date and\narithmetic errors"),
     (1, 2): ("disc", "All computation and\ntime-window errors\nrejected"),
     (1, 3): ("disc", "All computation and\ntime-window errors\nrejected"),
     (2, 0): ("part", "Detects wrong orders;\npassed doing nothing\non 23% of tasks"),
     (2, 1): ("part", "Detects rule breaches;\ninherits evidence errors\nit accepted upstream"),
     (2, 2): ("disc", "All 13 action errors\nrejected"),
     (2, 3): ("disc", "All action errors\nrejected"),
     (3, 0): ("cert", "0.78\u20130.79 (rejects\nnon-conforming form)"),
     (3, 1): ("cert", "GPT judges 0.73\u20130.86\nDeepSeek 0.35\u20130.39"),
     (3, 2): ("cert", "0.35\u20130.40"),
     (3, 3): ("cert", "0.30\u20130.37 (unchanged)")}

W, H = 16 / 2.54, 6.0 / 2.54
fig = plt.figure(figsize=(W, H))
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
x0, cw = 1.30, (W - 1.30 - 0.02) / 4
top = H - 0.44
rh = [0.45, 0.43, 0.45, 0.35]
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
ax.plot([0.04, x0 + 4 * cw], [yt[3], yt[3]], color="#444444", lw=0.6)
# legend
ly = yt[4] - 0.13
items = [("disc", "most errors rejected"), ("part", "partial"), ("acc", "most errors accepted")]
lx = x0 + g
for k, (lvl, lab) in enumerate(items):
    fc, _, ec = LV[lvl]; xx = lx + k * 1.45
    ax.add_patch(Rectangle((xx, ly - 0.055), 0.2, 0.11, facecolor=fc, edgecolor=ec,
                           linewidth=1.1 if lvl == "acc" else 0.6))
    ax.text(xx + 0.26, ly, lab, ha="left", va="center", fontsize=7)
ax.text(0.04, ly, "Detection rows:", ha="left", va="center", fontsize=7, color="#555555")
fig.savefig("fig_detection.png", dpi=300)
fig.savefig("fig_detection.pdf")
