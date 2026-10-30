import os,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch
from matplotlib.lines import Line2D
out=Path(__file__).resolve().parents[3] / 'paper/ECIS2027_manuscript_v4_LaTeX/Figures'
out.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none'})
fig,axs=plt.subplots(1,2,figsize=(10.8,5.5))
fig.subplots_adjust(left=.02,right=.98,top=.86,bottom=.11,wspace=.10)
for ax,title,n,miss in zip(axs,['GPT-OSS-120B attempts','Qwen3.8-27B attempts'],[405,352],[153,54]):
    ax.set_aspect('equal');ax.set_xlim(-2.2,2.2);ax.set_ylim(-1.9,1.6);ax.axis('off')
    ax.set_title(f'{title}\n{n} substantive errors',fontsize=14,fontweight='bold',pad=16)
    ax.add_patch(FancyBboxPatch((-2.15,-1.73),4.3,3.15,boxstyle='round,pad=0.015,rounding_size=0.06',facecolor='#FAFBFC',edgecolor='#C7D0D7',linewidth=1))
    ax.add_patch(Circle((-.57,.24),1.07,facecolor='#176B9B',edgecolor='#176B9B',alpha=.22,lw=2))
    ax.add_patch(Circle((.57,.24),1.07,facecolor='#B56B00',edgecolor='#B56B00',alpha=.22,lw=2))
    ax.text(-1.03,.25,'GPT-OSS\nonly',ha='center',va='center',fontsize=12,color='#164D70')
    ax.text(0,.25,'Both\njudges',ha='center',va='center',fontsize=12,fontweight='bold',color='#26363D')
    ax.text(1.03,.25,'Qwen\nonly',ha='center',va='center',fontsize=12,color='#84500B')
    ax.text(0,1.1,'Errors detected',ha='center',fontsize=11,color='#26363D')
    ax.text(0,-1.1,f'Missed by both: {miss} ({100*miss/n:.1f}%)',ha='center',fontsize=12,fontweight='bold',color='#8C3E2D')
    ax.text(0,-1.52,f'Detected by either: {n-miss}/{n} ({100*(n-miss)/n:.1f}%)',ha='center',fontsize=11,color='#26363D')

fig.text(.5,.045,'Schematic sets, not proportional to counts. Exact counts within the three detection regions are not shown.',ha='center',fontsize=10,color='#57616B')
for ext in ['png','svg']: fig.savefig(out/f'combined_judges_venn_schematic.{ext}',dpi=400,facecolor='white')
print('Saved schematic Venn diagrams as PNG and SVG.')
