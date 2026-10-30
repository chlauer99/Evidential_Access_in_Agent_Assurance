import os,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
out=Path(__file__).resolve().parents[4] / 'paper/ECIS2027_manuscript_v4_LaTeX/Figures'
out.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'none'})
fig=plt.figure(figsize=(10.5,4.0));ax=fig.add_axes([.015,.025,.97,.95]);ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
def box(x,y,w,h,text,fc,ec,fs=12,bold=False):
    ax.add_patch(FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle='round,pad=0.005,rounding_size=0.016',facecolor=fc,edgecolor=ec,lw=1.2,zorder=2))
    ax.text(x,y,text,ha='center',va='center',fontsize=fs,fontweight='bold' if bold else 'normal',color='#2E4757',linespacing=1.3,zorder=3)
def arr(a,b):ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=12,lw=1.3,color='#798C98',zorder=1))
box(.5,.91,.25,.12,'Assessment','#EDF1F5','#B2C0CA',14,True)
arr((.45,.845),(.23,.755));arr((.55,.845),(.73,.755))
box(.23,.69,.36,.12,'Substantively correct','#EDF5F0','#9EBBA9',12.5,True)
box(.73,.69,.43,.12,'Substantive answer error','#FAF1E4','#CCB18A',12.5,True)
arr((.68,.625),(.26,.495));arr((.76,.625),(.76,.495))
box(.26,.43,.45,.12,'Error locus','#EFF5F9','#80A4BA',12.5,True)
box(.76,.43,.45,.12,'Evidential provenance','#FBF5EB','#C6A975',12.5,True)
for x,t in [(.105,'Evidence\ngathering'),(.26,'Conclusion'),(.415,'Action')]:
    arr((.26,.365),(x,.25))
    box(x,.175,.14,.14,t,'#F6F9FB','#B3C9D7',10.5)
for x,t in [(.605,'Grounded'),(.76,'Fabricated'),(.915,'Unclassified')]:
    arr((.76,.365),(x,.25))
    box(x,.175,.14,.14,t,'#FDF9F2','#D8C39D',10.5)
for ext in ['png','svg']:fig.savefig(out/f'assessment_classification_schema.{ext}',dpi=400,facecolor='white')
print('Saved assessment schema.')
