import os,sys,csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap,TwoSlopeNorm
import numpy as np
root=Path(__file__).resolve().parents[3]
out=root/'paper/ECIS2027_manuscript_v4_LaTeX/Figures'
out.mkdir(parents=True, exist_ok=True)
models=[('GPT-OSS-120B','gpt_oss_120b_exp_2'),('Qwen3.8-27B','qwen3_8_27b_exp_3')]
conditions=['spec','checklist','record_access']; measures=['error_discovery','correct_certification']
values=[]; crossing=[]
for name,run in models:
    with (root/'ecis2027_epidemische_Fehler/runs'/run/'09_analysis/outputs/paired_conditions.csv').open() as f:
        rows={(r['condition'],r['measure']):r for r in csv.DictReader(f)}
    values.append([[100*float(rows[c,m]['difference']) for m in measures] for c in conditions])
    crossing.append([[float(rows[c,m]['lo'])<=0<=float(rows[c,m]['hi']) for m in measures] for c in conditions])
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'svg.fonttype':'none'})
cmap=LinearSegmentedColormap.from_list('effect',['#BC542E','#F7F7F5','#176B9B'])
norm=TwoSlopeNorm(vmin=-25,vcenter=0,vmax=25)
fig,axs=plt.subplots(1,2,figsize=(10.5,4.9),sharey=True)
fig.subplots_adjust(left=.245,right=.97,top=.73,bottom=.29,wspace=.10)
for k,(ax,(name,run)) in enumerate(zip(axs,models)):
    im=ax.imshow(values[k],cmap=cmap,norm=norm,aspect='auto')
    ax.set_title(name,fontsize=15,fontweight='bold',pad=24)
    ax.set_xticks([0,1],['Error\ndiscovery','Correct\nacceptance'])
    ax.xaxis.tick_top(); ax.tick_params(axis='x',length=0,pad=10,labelsize=12)
    ax.set_yticks([0,1,2],['API documentation','Verification checklist','Independent record access'])
    ax.tick_params(axis='y',length=0,pad=12,labelleft=k==0)
    for y in [.5,1.5]: ax.axhline(y,color='white',linewidth=4)
    ax.axvline(.5,color='white',linewidth=4)
    for i in range(3):
        for j in range(2):
            v=values[k][i][j]
            s=f'{v:+.1f}'+(' *' if crossing[k][i][j] else '')
            ax.text(j,i,s,ha='center',va='center',fontsize=19,fontweight='bold',color='white' if abs(v)>14 else '#172B39')
    for s in ax.spines.values(): s.set_visible(False)
cax=fig.add_axes([.37,.15,.47,.035])
cb=fig.colorbar(im,cax=cax,orientation='horizontal',ticks=[-25,-10,0,10,25])
cb.ax.set_xticklabels(['−25','−10','0','+10','+25']);cb.outline.set_visible(False)
cb.ax.tick_params(length=0,labelsize=10)
fig.text(.605,.225,'Worse  ←    Change from baseline (percentage points)    →  Better',ha='center',fontsize=10.5)
fig.text(.605,.035,'* 95% confidence interval includes zero; direction of change is uncertain.',ha='center',fontsize=10.5,color='#4C565E')
for ext in ['png','svg']: fig.savefig(out/f'assurance_support_heatmap.{ext}',dpi=400,facecolor='white')
print('Saved heatmap PNG and SVG.')
