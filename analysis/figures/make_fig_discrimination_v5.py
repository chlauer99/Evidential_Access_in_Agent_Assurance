import numpy as np, pandas as pd, matplotlib as mpl, matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

apply_figure_style(font="Arial", sizes=(8, 7, 7))
mpl.rcParams["pdf.fonttype"] = 42
mpl.rcParams["savefig.bbox"] = "standard"
mpl.rcParams["mathtext.fontset"] = "custom"; mpl.rcParams["mathtext.it"] = "Arial:italic"; mpl.rcParams["mathtext.rm"] = "Arial"

# Manuscript v5, Figure 1. Layout of v3 (make_fig_discrimination.py): (a) certification vs acceptance of errors,
# now with the open-weight judges; (b) forest of the original study (judge_conditions_summary.csv);
# (c) forest of the open-weight judges incl. cross-judged attempts (ow_fig1_rows.csv from a15_open_weight_runs.py).
# v5: the second GPT-OSS-120B run (judged by Qwen only) is not shown.
FO, FW = pd.read_csv(JCS_PATH), pd.read_csv(OW_PATH)
FW = FW[FW.agent != "GPT-OSS-120B (run 2)"]
COL = {"Trajectory only": "#7F7F7F", "+ API specification": "#56B4E9",
       "+ verification checklist": "#E69F00", "+ read-only EHR access": "#0072B2"}
LAB = {"Trajectory only": "Trajectory only", "+ API specification": "+ API specification",
       "+ verification checklist": "+ checklist", "+ read-only EHR access": "+ record access"}
MK = {"GPT-4.1": "o", "GPT-4.1-mini": "s", "DeepSeek V3.2": "^", "GPT-OSS-120B": "p", "GPT-OSS-120B (run 2)": "p",
      "Qwen3.8-27B": "v"}
short = {"GPT-4.1": "GPT-4.1", "GPT-4.1-mini": "GPT-4.1-mini", "DeepSeek V3.2": "DeepSeek", "GPT-OSS-120B": "GPT-OSS",
         "GPT-OSS-120B (run 2)": "GPT-OSS run 2", "Qwen3.8-27B": "Qwen"}
pair = {"self": "self", "same-lineage": "same lineage", "cross-developer": "cross"}
order = list(COL)
dodge = {"GPT-4.1": -0.02, "GPT-4.1-mini": 0.02, "DeepSeek V3.2": 0.0}

W, H = 16 / 2.54, 10.2 / 2.54
fig = plt.figure(figsize=(W, H))
# forest rows: one per cell plus one header per condition; (b) and (c) share the row height
nb, nc = len(FO) + 4, len(FW) + 4
bot, top, gap = 0.10, 0.935, 0.075
unit = (top - bot - gap) / (nb + nc)
bx = fig.add_axes([0.715, top - nb * unit, 0.275, nb * unit])
cx = fig.add_axes([0.715, bot, 0.275, nc * unit])
ax = fig.add_axes([0.075, 0.49, 0.285, 0.445])

# ---- panel a: certification vs acceptance of substantive errors
ax.plot([0, 1], [0, 1], color="#BBBBBB", lw=0.8, ls="--", zorder=0)
ax.text(0.60, 0.50, "chance line", color="#666666", fontsize=7, ha="left", va="top")
for FR, ow in ((FO, False), (FW, True)):
    for r in FR.itertuples():
        xx = r.pg + (dodge.get(r.agent, 0) if r.pg < 0.06 else 0)
        ax.scatter(xx, r.pc, marker=MK[r.agent], s=20, color=COL[r.cond], edgecolor="white", linewidth=0.5,
                   zorder=4 if r.agent == "DeepSeek V3.2" else 3)
ax.set_xlim(-0.06, 1.06); ax.set_ylim(-0.04, 1.06)
ax.set_xticks([0, 0.5, 1]); ax.set_yticks([0, 0.5, 1])
ax.set_xlabel("Substantive errors accepted")
ax.set_ylabel("Correct work accepted")
ax.text(0.02, 1.0, "upper left = better", transform=ax.transAxes, fontsize=7, color="#555555", va="top")
ax.annotate("Qwen judge", xy=(0.10, 0.70), xytext=(0.03, 0.47), fontsize=7, color="#333333",
            arrowprops=dict(arrowstyle="-", color="#888888", lw=0.6))
fig.text(0.075, 0.965, "Height above the chance line\nshows discrimination", fontsize=8,
         ha="left", va="center", linespacing=1.05)
fig.text(0.062, 0.965, "a", fontsize=9, fontweight="bold", ha="right", va="center")

# legend under panel a: agent markers, evidence conditions, diamonds
hs = [Line2D([], [], marker=m, ls="", color="#555555", markersize=4, label=f"{short[a]} agent")
      for a, m in MK.items() if a != "GPT-OSS-120B (run 2)"]
hc = [Patch(facecolor=COL[c], edgecolor="none", label=LAB[c]) for c in order]
hd = [Line2D([], [], marker="D", ls="", markerfacecolor="white", markeredgecolor="#7F7F7F", markersize=3.5,
             label="trajectory only,\nsame attempts")]
leg1 = fig.legend(handles=hs, loc="upper left", bbox_to_anchor=(0.03, 0.37), frameon=False, fontsize=7,
                  handletextpad=0.2, labelspacing=0.3)
fig.legend(handles=hc + hd, loc="upper left", bbox_to_anchor=(0.215, 0.37), frameon=False, fontsize=7,
           handlelength=0.9, handleheight=0.9, handletextpad=0.35, labelspacing=0.3)


# ---- panels b and c: Youden's J forests
def forest(bx, FR, letter, title, xlabel):
    y = 0; yt, yl, heads = [], [], []
    for c in order:
        heads.append((y, c)); y -= 1
        for r in FR[FR.cond == c].sort_values(["judge", "agent"]).itertuples():
            bx.plot([r.lo, r.hi], [y, y], color=COL[c], lw=1.1, solid_capstyle="butt", zorder=2)
            bx.scatter(r.J, y, marker=MK[r.agent], s=18, color=COL[c], edgecolor="white", linewidth=0.5, zorder=3)
            if not np.isnan(r.J_paired):
                bx.scatter(r.J_paired, y, marker="D", s=11, facecolor="white", edgecolor="#7F7F7F", linewidth=0.8,
                           zorder=3)
            yt.append(y); yl.append(f"{short[r.judge]} → {short[r.agent]} ({pair[r.pairing]})"); y -= 1
    bx.axvline(0, color="#BBBBBB", lw=0.8, ls="--", zorder=0)
    bx.set_yticks(yt); bx.set_yticklabels(yl, fontsize=7); bx.tick_params(axis="y", length=0, pad=2)
    tr = mpl.transforms.blended_transform_factory(bx.transAxes, bx.transData)
    for yy, c in heads:
        bx.text(-0.015, yy, LAB[c], transform=tr, fontsize=7, fontweight="bold",
                color=COL[c] if c != "Trajectory only" else "#444444", ha="right", va="center")
    bx.set_xlim(-0.45, 0.75); bx.set_ylim(y + 0.5, 0.6)
    bx.set_xticks([-0.4, -0.2, 0, 0.2, 0.4, 0.6])
    if xlabel:
        bx.set_xlabel("Youden's $J$ (95% CI)")
    else:
        bx.set_xticklabels([])
    bx.text(1.0, 1.0, "higher = better", transform=bx.transAxes, fontsize=7, color="#555555", ha="right",
            va="bottom")
    p = bx.get_position()
    fig.text(0.44, p.y1 + 0.022, title, fontsize=8, ha="left", va="center")
    fig.text(0.427, p.y1 + 0.022, letter, fontsize=9, fontweight="bold", ha="right", va="center")


forest(bx, FO, "b", "Original study: GPT and DeepSeek judges", False)
forest(cx, FW, "c", "Open-weight judges, incl. cross-judged attempts", True)

fig.savefig("fig_discrimination_v5.png", dpi=300)
fig.savefig("fig_discrimination_v5.pdf")
