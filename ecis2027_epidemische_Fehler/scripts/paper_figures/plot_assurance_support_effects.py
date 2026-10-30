import os, sys, csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

root=Path(__file__).resolve().parents[3]
out=root/'paper/ECIS2027_manuscript_v4_LaTeX/Figures'
out.mkdir(parents=True, exist_ok=True)
models=[('GPT-OSS-120B','gpt_oss_120b_exp_2','#176B9B','o',0.13), ('Qwen3.8-27B','qwen3_8_27b_exp_3','#B56B00','s',-0.13)]
data={}
for name, run, *_ in models:
    path=root/'ecis2027_epidemische_Fehler/runs'/run/'09_analysis/outputs/paired_conditions.csv'
    with path.open() as f:
        data[name]={(r['condition'],r['measure']):r for r in csv.DictReader(f)}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.titlesize':14,'axes.labelsize':12,'xtick.labelsize':11,'ytick.labelsize':12,'svg.fonttype':'none'})
fig, axs=plt.subplots(1,2,figsize=(10.5,4.8),sharex=True,sharey=True)
fig.subplots_adjust(left=.235,right=.98,top=.78,bottom=.30,wspace=.13)
conditions=['spec','checklist','record_access']
labels=['API documentation','Verification checklist','Independent record access']
for ax, measure, title in zip(axs,['error_discovery','correct_certification'],['(a) Error discovery','(b) Correct acceptance']):
    ax.axvspan(-16,0,color='#FAF2F0',zorder=0)
    ax.axvspan(0,32,color='#F1F7F3',zorder=0)
    ax.set_xlim(-16,32); ax.set_ylim(-.52,2.52)
    ax.set_xticks([-10,0,10,20,30])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v,p: '0' if v==0 else f'{v:+.0f}'))
    ax.grid(axis='x',color='#D6DDE0',linewidth=.65,zorder=1)
    ax.axvline(0,color='#46545D',linewidth=1.3,zorder=2)
    for y in [.5,1.5]: ax.axhline(y,color='white',linewidth=3,zorder=1)
    for name,run,color,marker,offset in models:
        for y,cond in zip([2,1,0],conditions):
            r=data[name][cond,measure]
            d,lo,hi=[float(r[k])*100 for k in ['difference','lo','hi']]
            assert lo<=d<=hi
            ax.errorbar(d,y+offset,xerr=[[d-lo],[hi-d]],fmt=marker,color=color,ecolor=color,markersize=8,markeredgecolor='white',markeredgewidth=.75,elinewidth=2.1,capsize=4,capthick=1.5,zorder=4)
    ax.set_title(title,loc='left',pad=28,fontweight='bold')
    ax.text(-8,.99,'Worse',transform=ax.get_xaxis_transform(),ha='center',va='bottom',fontsize=10,color='#7B5148')
    ax.text(16,.99,'Better',transform=ax.get_xaxis_transform(),ha='center',va='bottom',fontsize=10,color='#42674C')
    ax.set_yticks([2,1,0],labels)
    ax.tick_params(axis='y',length=0,pad=11)
    ax.tick_params(axis='x',length=0,pad=7)
    for spine in ax.spines.values(): spine.set_visible(False)
axs[1].tick_params(axis='y',labelleft=False)
fig.text(.61,.18,'Change from trajectory-only evaluation (percentage points)',ha='center',fontsize=12)
handles=[Line2D([0],[0],color=color,marker=marker,linestyle='none',markersize=8,label=name) for name,run,color,marker,offset in models]
fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.59,.055),ncol=2,frameon=False,handletextpad=.25,columnspacing=2.4)
fig.text(.59,.02,'Points: paired changes   |   Lines: 95% task-clustered bootstrap confidence intervals',ha='center',fontsize=9.5,color='#4C565E')
for fmt in ['png','svg']:
    fig.savefig(out/f'assurance_support_effects.{fmt}',dpi=400,facecolor='white')
print(out/'assurance_support_effects.png')
print(out/'assurance_support_effects.svg')
