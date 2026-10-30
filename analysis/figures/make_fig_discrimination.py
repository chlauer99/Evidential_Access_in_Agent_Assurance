import numpy as np, pandas as pd, matplotlib as mpl, matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

apply_figure_style(font="Arial", sizes=(8, 7, 7))
mpl.rcParams["pdf.fonttype"] = 42
mpl.rcParams["savefig.bbox"] = "standard"
mpl.rcParams["mathtext.fontset"] = "custom"; mpl.rcParams["mathtext.it"] = "Arial:italic"; mpl.rcParams["mathtext.rm"] = "Arial"

FR = pd.read_csv(JCS_PATH)   # judge_conditions_summary.csv
COL = {"Trajectory only": "#7F7F7F", "+ API specification": "#56B4E9",
       "+ verification checklist": "#E69F00", "+ read-only EHR access": "#0072B2"}
LAB = {"Trajectory only": "Trajectory only", "+ API specification": "+ API specification",
       "+ verification checklist": "+ checklist", "+ read-only EHR access": "+ record access"}
MK = {"GPT-4.1": "o", "GPT-4.1-mini": "s", "DeepSeek V3.2": "^"}
short = {"GPT-4.1": "GPT-4.1", "GPT-4.1-mini": "GPT-4.1-mini", "DeepSeek V3.2": "DeepSeek"}
pair = {"self": "self", "same-lineage": "same lineage", "cross-developer": "cross"}
order = list(COL)
dodge = {"GPT-4.1": -0.02, "GPT-4.1-mini": 0.02, "DeepSeek V3.2": 0.0}

W, H = 16 / 2.54, 6.8 / 2.54
fig = plt.figure(figsize=(W, H))
ax = fig.add_axes([0.075, 0.1397, 0.265, 0.7026])
bx = fig.add_axes([0.715, 0.1397, 0.275, 0.7426])

# ---- panel a: certification vs acceptance of substantive errors
ax.plot([0, 1], [0, 1], color="#BBBBBB", lw=0.8, ls="--", zorder=0)
ax.text(0.60, 0.50, "chance line", color="#666666", fontsize=7, ha="left", va="top", rotation=0)
for r in FR.itertuples():
    xx = r.pg + (dodge[r.agent] if r.pg < 0.06 else 0)
    ax.scatter(xx, r.pc, marker=MK[r.agent], s=20, color=COL[r.cond], edgecolor="white", linewidth=0.5, zorder=4 if r.agent == "DeepSeek V3.2" else 3)
ax.set_xlim(-0.06, 1.06); ax.set_ylim(-0.04, 1.06)
ax.set_xticks([0, 0.5, 1]); ax.set_yticks([0, 0.5, 1])
ax.set_xlabel("Substantive errors accepted")
ax.set_ylabel("Correct work accepted")
ax.text(0.02, 1.0, "upper left = better", transform=ax.transAxes, fontsize=7, color="#555555", va="top")
hs = [Line2D([], [], marker=m, ls="", color="#555555", markersize=4, label=f"{short[a]} agent") for a, m in MK.items()]
hc = [Patch(facecolor=COL[c], edgecolor="none", label=LAB[c]) for c in order]
leg1 = ax.legend(handles=hs, loc="upper left", bbox_to_anchor=(-0.02, 0.93), frameon=False, fontsize=7,
                 handletextpad=0.2, labelspacing=0.25, borderaxespad=0.2)
ax.add_artist(leg1)
ax.legend(handles=hc, loc="lower right", bbox_to_anchor=(1.03, -0.01), frameon=False, fontsize=7,
          handlelength=0.9, handleheight=0.9, handletextpad=0.35, labelspacing=0.25, borderaxespad=0.2)
fig.text(0.075, 0.9382, "Without a checklist or record access,\njudges sit near the chance line", fontsize=8,
         ha="left", va="center", linespacing=1.05)
fig.text(0.062, 0.9382, "a", fontsize=9, fontweight="bold", ha="right", va="center")

# ---- panel b: Youden's J forest
y = 0; yt, yl, heads = [], [], []
for c in order:
    heads.append((y, c)); y -= 1
    for r in FR[FR.cond == c].sort_values(["judge", "agent"]).itertuples():
        bx.plot([r.lo, r.hi], [y, y], color=COL[c], lw=1.1, solid_capstyle="butt", zorder=2)
        bx.scatter(r.J, y, marker=MK[r.agent], s=18, color=COL[c], edgecolor="white", linewidth=0.5, zorder=3)
        if not np.isnan(r.J_paired):
            bx.scatter(r.J_paired, y, marker="D", s=11, facecolor="white", edgecolor="#7F7F7F", linewidth=0.8, zorder=3)
        yt.append(y); yl.append(f"{short[r.judge]} \u2192 {short[r.agent]} ({pair[r.pairing]})"); y -= 1
bx.axvline(0, color="#BBBBBB", lw=0.8, ls="--", zorder=0)
bx.set_yticks(yt); bx.set_yticklabels(yl, fontsize=7); bx.tick_params(axis="y", length=0, pad=2)
tr = mpl.transforms.blended_transform_factory(bx.transAxes, bx.transData)
for yy, c in heads:
    bx.text(-0.015, yy, LAB[c], transform=tr, fontsize=7, fontweight="bold",
            color=COL[c] if c != "Trajectory only" else "#444444", ha="right", va="center")
bx.set_xlim(-0.45, 0.70); bx.set_ylim(y + 0.5, 0.6)
bx.set_xticks([-0.4, -0.2, 0, 0.2, 0.4, 0.6])
bx.set_xlabel("Youden's $J$ (95% CI)")
yh = [yy for yy, c in heads if c == "+ read-only EHR access"][0]
bx.scatter(-0.40, yh, marker="D", s=11, facecolor="white", edgecolor="#7F7F7F", linewidth=0.8, zorder=3, clip_on=False)
bx.text(-0.36, yh, "trajectory only, same attempts", fontsize=7, color="#555555", ha="left", va="center")
bx.text(1.0, 1.0, "higher = better", transform=bx.transAxes, fontsize=7, color="#555555", ha="right", va="bottom")
fig.text(0.44, 0.9559, "Discrimination ($J$ > 0) appears with a checklist or record access", fontsize=8, ha="left", va="center")
bx.text(-0.015, 1.0, "Judge \u2192 agent (pairing)", transform=bx.transAxes, fontsize=7, color="#555555", ha="right", va="bottom")
fig.text(0.427, 0.9559, "b", fontsize=9, fontweight="bold", ha="right", va="center")

fig.savefig("fig_discrimination.png", dpi=300)
fig.savefig("fig_discrimination.pdf")
