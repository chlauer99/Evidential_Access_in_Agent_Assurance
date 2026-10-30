import os,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
out=Path(__file__).resolve().parents[3] / 'paper/ECIS2027_manuscript_v4_LaTeX/Figures'
out.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none'})
fig=plt.figure(figsize=(10.5,2.9));ax=fig.add_axes([.012,.04,.976,.93]);ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
def box(x,y,w,h,text,fc,ec='#B8C4CD',size=11,bold=False):
    ax.add_patch(FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle='round,pad=0.006,rounding_size=0.018',facecolor=fc,edgecolor=ec,lw=1))
    ax.text(x,y,text,ha='center',va='center',fontsize=size,fontweight='bold' if bold else 'normal',color='#2B4252',linespacing=1.45)
def arrow(a,b):
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=11,color='#7F8F9B',lw=1.2,zorder=0))
box(.14,.51,.25,.39,'Official verdict\nPass / fail','#EFF2F5',bold=True)
arrow((.272,.51),(.325,.51))
box(.49,.51,.31,.61,'Substantive correctness\n\nCorrect (incl. format-only)\nSubstantive error\nUnclassified','#F4F6F8',size=11)
# Arrow originates at the substantive-error row, not at all outcome classes.
arrow((.650,.425),(.714,.75));arrow((.650,.425),(.714,.25))
box(.85,.75,.265,.30,'Error locus\nEvidence gathering · Conclusion · Action','#EFF5F9','#7FA3B8',size=9.6)
box(.85,.25,.265,.30,'Evidential provenance\nGrounded · Fabricated · Unclassified','#FBF5EB','#C5A874',size=9.6)
# Category lists are split to keep them readable at paper width.
ax.text(.49,.90,'Reference-based assessment',ha='center',va='center',fontsize=10,color='#667783')
ax.text(.85,.97,'Separate dimensions',ha='center',va='center',fontsize=10,color='#667783')
for ext in ['png','svg']:fig.savefig(out/f'reference_standard_classification_compact.{ext}',dpi=400,facecolor='white')
print('Saved compact classification diagram.')
