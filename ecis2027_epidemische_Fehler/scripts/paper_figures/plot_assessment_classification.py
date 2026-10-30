import os,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
out=Path(__file__).resolve().parents[3] / 'paper/ECIS2027_manuscript_v4_LaTeX/Figures'
out.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'none'})
fig=plt.figure(figsize=(10.8,4.7));ax=fig.add_axes([.015,.025,.97,.95]);ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
def box(x,y,w,h,text,fc,ec,fs=12,bold=False):
    ax.add_patch(FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle='round,pad=0.005,rounding_size=0.014',facecolor=fc,edgecolor=ec,lw=1.2,zorder=3))
    ax.text(x,y,text,ha='center',va='center',fontsize=fs,fontweight='bold' if bold else 'normal',color='#2E4757',linespacing=1.25,zorder=4)
def path(points):
    ax.plot([p[0] for p in points],[p[1] for p in points],color='#71828E',lw=1.3,solid_capstyle='butt',solid_joinstyle='miter',zorder=1)
def arrow(a,b):
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=12,lw=1.3,color='#71828E',shrinkA=0,shrinkB=0,zorder=2))
# Root and outcome branches.
box(.5,.92,.52,.11,'Assessment of substantive errors','#EDF1F5','#B2C0CA',13.5,True)
arrow((.455,.860),(.17,.780));arrow((.545,.860),(.665,.780))
box(.17,.72,.29,.11,'Substantively correct','#ECF5EF','#96B6A1',12.5,True)
box(.665,.72,.30,.11,'Substantive error','#F1ECF7','#AF9AC4',12.5,True)
# Correct attempts comprise official passes and format-only failures.
path([(.17,.660),(.17,.610),(.035,.610),(.035,.430)])
for y,t in [(.550,'Official pass verdict'),(.430,'Format-only failure')]:
    box(.185,y,.26,.080,t,'#F4F9F5','#B0CBB8',11.2)
    arrow((.035,y),(.050,y))
# Shared classification region.
ax.add_patch(FancyBboxPatch((.345,.045),.635,.555,boxstyle='round,pad=0.006,rounding_size=0.016',facecolor='#FAFBFC',edgecolor='#D2D9DE',linewidth=1,zorder=0))
# Continuous paths; every segment meets exactly, with no automatic endpoint shrink.
arrow((.665,.660),(.665,.606))
ax.text(.665,.565,'Two separate classification dimensions',ha='center',va='center',fontsize=10.8,color='#566C7B',zorder=5)
path([(.665,.535),(.665,.515)])
path([(.505,.515),(.825,.515)])
arrow((.505,.515),(.505,.495));arrow((.825,.515),(.825,.495))
box(.505,.435,.285,.11,'Error locus','#EAF3F9','#7DA2B9',12.3,True)
box(.825,.435,.285,.11,'Evidential provenance','#FBF2E3','#C5A46B',11.7,True)
for y,t in [(.290,'Evidence gathering'),(.195,'Conclusion'),(.100,'Action')]:
    box(.525,y,.225,.065,t,'#F5F9FC','#B3CBD9',10.8)
for y,t in [(.290,'Grounded'),(.195,'Fabricated'),(.100,'Unclassified')]:
    box(.845,y,.225,.065,t,'#FEFAF3','#DCC7A3',10.8)
# Connected sibling branches to the three alternatives in each dimension.
for parent,spine,edge in [(.505,.375,.4075),(.825,.695,.7275)]:
    path([(parent,.375),(spine,.345),(spine,.100)])
    for y in [.290,.195,.100]:arrow((spine,y),(edge,y))
for ext in ['png','svg']:fig.savefig(out/f'assessment_classification_schema_v4.{ext}',dpi=400,facecolor='white')
print('Saved revised schema with continuous connectors.')
