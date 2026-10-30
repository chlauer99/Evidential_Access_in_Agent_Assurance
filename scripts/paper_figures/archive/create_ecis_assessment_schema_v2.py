import os,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
out=Path(__file__).resolve().parents[3] / 'paper/ECIS2027_manuscript_v4_LaTeX/Figures'
out.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'none'})
fig=plt.figure(figsize=(10.8,4.5));ax=fig.add_axes([.015,.025,.97,.95]);ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
def box(x,y,w,h,text,fc,ec,fs=12,bold=False):
    ax.add_patch(FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle='round,pad=0.005,rounding_size=0.014',facecolor=fc,edgecolor=ec,lw=1.2,zorder=2))
    ax.text(x,y,text,ha='center',va='center',fontsize=fs,fontweight='bold' if bold else 'normal',color='#2E4757',linespacing=1.25,zorder=3)
def line(a,b,arrow=False):ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>' if arrow else '-',mutation_scale=12,lw=1.3,color='#71828E',zorder=1))
box(.5,.92,.24,.11,'Assessment','#EDF1F5','#B2C0CA',14,True)
line((.455,.86),(.17,.78),True);line((.545,.86),(.665,.78),True)
box(.17,.72,.29,.11,'Substantively correct','#ECF5EF','#96B6A1',12.5,True)
box(.665,.72,.30,.11,'Substantive error','#F1ECF7','#AF9AC4',12.5,True)
# A bounded group places both classification dimensions unambiguously below the error branch.
ax.add_patch(FancyBboxPatch((.345,.055),.635,.545,boxstyle='round,pad=0.006,rounding_size=0.016',facecolor='#FAFBFC',edgecolor='#D2D9DE',linewidth=1,zorder=0))
line((.665,.66),(.665,.56))
line((.505,.56),(.825,.56))
line((.505,.56),(.505,.505),True);line((.825,.56),(.825,.505),True)
box(.505,.445,.285,.11,'Error locus','#EAF3F9','#7DA2B9',12.3,True)
box(.825,.445,.285,.11,'Evidential provenance','#FBF2E3','#C5A46B',11.7,True)
# Within each dimension, stack the three alternatives for a compact, readable layout.
for y,t in [(.300,'Evidence gathering'),(.205,'Conclusion'),(.110,'Action')]:
    box(.525,y,.225,.065,t,'#F5F9FC','#B3CBD9',10.8)
for y,t in [(.300,'Grounded'),(.205,'Fabricated'),(.110,'Unclassified')]:
    box(.845,y,.225,.065,t,'#FEFAF3','#DCC7A3',10.8)
# Single connectors identify each list as the alternatives of its parent dimension.

for parent,spine,edge in [(.505,.375,.406),(.825,.695,.726)]:
    line((parent,.385),(spine,.355))
    line((spine,.355),(spine,.110))
    for y in [.300,.205,.110]: line((spine,y),(edge,y),True)
# No arrows join the category alternatives: the enclosing colour column groups them.
for ext in ['png','svg']:fig.savefig(out/f'assessment_classification_schema_v2.{ext}',dpi=400,facecolor='white')
print('Saved revised assessment schema.')
