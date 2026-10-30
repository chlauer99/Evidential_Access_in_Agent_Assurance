import os,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
out=Path(__file__).resolve().parents[4] / 'paper/ECIS2027_manuscript_v4_LaTeX/Figures'
out.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none'})
fig=plt.figure(figsize=(10.8,7.0)); ax=fig.add_axes([.025,.025,.95,.95]);ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
def box(x,y,w,h,fc,ec='#B6C3CC',lw=1.1):
    p=FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle='round,pad=0.007,rounding_size=0.012',facecolor=fc,edgecolor=ec,lw=lw,zorder=2);ax.add_patch(p);return p
def arrow(a,b,color='#748591',style='-|>',lw=1.2):
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle=style,mutation_scale=12,color=color,lw=lw,connectionstyle='arc3',zorder=1))
# Separate measurement supplied by benchmark from reconstructed outcome.
box(.5,.94,.56,.075,'#EDF1F5')
ax.text(.5,.94,'Official benchmark verdict: pass / fail',ha='center',va='center',fontsize=13,fontweight='bold',color='#263B4A')
arrow((.5,.895),(.5,.855))
box(.5,.775,.91,.145,'#F5F7F9')
ax.text(.5,.817,'Assess substantive task correctness',ha='center',va='center',fontsize=13,fontweight='bold',color='#263B4A')
ax.text(.5,.758,'For failed attempts: regrade with the reference answer to check actions.\nCompare the original answer with reference values, irrespective of format.',ha='center',va='center',fontsize=11.5,linespacing=1.35,color='#3E4E59')
# Outcome classes; these arrows denote assignment, not deterministic branching rules.
for x in [.165,.5,.835]:
    arrow((.5,.695),(x,.625))
box(.165,.568,.285,.10,'#EDF5F0','#9CB9A6')
ax.text(.165,.585,'Substantively correct',ha='center',va='center',fontsize=11.5,fontweight='bold',color='#355B46')
ax.text(.165,.550,'Including format-only failures',ha='center',va='center',fontsize=10,color='#465B4D')
box(.5,.568,.285,.10,'#F8F0E4','#CDB38D')
ax.text(.5,.585,'Substantive error',ha='center',va='center',fontsize=12,fontweight='bold',color='#75541F')
ax.text(.5,.550,'Incorrect answer or action',ha='center',va='center',fontsize=10.5,color='#67573E')
box(.835,.568,.285,.10,'#F2F3F4','#BFC5CA')
ax.text(.835,.585,'Unclassified outcome',ha='center',va='center',fontsize=11.5,fontweight='bold',color='#48545D')
ax.text(.835,.550,'Correctness not established',ha='center',va='center',fontsize=10.2,color='#5A646B')
ax.text(.5,.475,'For substantive errors: classify two separate dimensions',ha='center',va='center',fontsize=11.5,fontweight='bold',color='#364B59')
arrow((.5,.511),(.5,.493),style='-')
arrow((.5,.451),(.25,.413));arrow((.5,.451),(.75,.413))
# Independent axes, not a nested taxonomy.
box(.25,.258,.455,.29,'#EFF5F9','#7FA3B8')
box(.75,.258,.455,.29,'#FBF5EB','#C5A874')
ax.text(.25,.375,'ERROR LOCUS',ha='center',fontsize=12,fontweight='bold',color='#175F86')
ax.text(.25,.344,'Where did the error occur?',ha='center',fontsize=10.5,color='#526571')
ax.text(.75,.375,'EVIDENTIAL PROVENANCE',ha='center',fontsize=12,fontweight='bold',color='#946317')
ax.text(.75,.344,'What supports the erroneous claim?',ha='center',fontsize=10.5,color='#73634D')
for y,head,desc in [(.294,'Evidence gathering','Selection or completeness of retrieval'),(.225,'Conclusion','Interpretation or calculation'),(.156,'Action','Required action omitted or incorrect order')]:
    ax.text(.050,y,head,ha='left',fontsize=11,fontweight='bold',color='#264B63')
    ax.text(.050,y-.027,desc,ha='left',fontsize=9.5,color='#4E6270')
for y,head,desc in [(.294,'Grounded','Authentic information or an empty response'),(.225,'Fabricated','Material patient fact unsupported by retrieval or source'),(.156,'Unclassified','Provenance unresolved or not applicable')]:
    ax.text(.550,y,head,ha='left',fontsize=11,fontweight='bold',color='#7C581C')
    ax.text(.550,y-.027,desc,ha='left',fontsize=9.1,color='#74634B')
ax.text(.5,.071,'Example: an incorrect mean calculated from authentic values is a conclusion error with grounded provenance.',ha='center',va='center',fontsize=10.3,color='#374D5B')
ax.text(.5,.027,'Reference: benchmark tasks, source records, and reference solutions; no independent clinical validation.',ha='center',va='center',fontsize=9.5,color='#63717B')
for ext in ['png','svg']:fig.savefig(out/f'reference_standard_classification.{ext}',dpi=400,facecolor='white')
print('Saved classification diagram as PNG and SVG.')
