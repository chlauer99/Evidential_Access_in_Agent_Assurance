import os,sys,csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
root=Path(__file__).resolve().parents[3]
out=root/'paper/ECIS2027_manuscript_v4_LaTeX/Figures'
out.mkdir(parents=True, exist_ok=True)
with (root/'data/published/judge_conditions_summary.csv').open() as f:
    original=[r for r in csv.DictReader(f) if r['cond']=='Trajectory only']
lookup={(r['judge'],r['agent']):r for r in original}
order=[('GPT-4.1','GPT-4.1'),('GPT-4.1-mini','GPT-4.1'),('GPT-4.1','GPT-4.1-mini'),('GPT-4.1-mini','GPT-4.1-mini'),('DeepSeek V3.2','GPT-4.1'),('DeepSeek V3.2','GPT-4.1-mini'),('DeepSeek V3.2','DeepSeek V3.2')]
rows=[]
short={'GPT-4.1':'GPT-4.1','GPT-4.1-mini':'GPT-mini','DeepSeek V3.2':'DeepSeek','GPT-OSS-120B':'GPT-OSS','Qwen3.8-27B':'Qwen'}
colors={'GPT-4.1':'#536B7A','GPT-4.1-mini':'#887B9D','DeepSeek V3.2':'#53816D','GPT-OSS-120B':'#176B9B','Qwen3.8-27B':'#B56B00'}
for judge,agent in order:
    r=lookup[judge,agent]
    rows.append(dict(judge=judge,agent=agent,ed=1-float(r['pg']),ca=float(r['pc']),J=float(r['J']),lo=float(r['lo']),hi=float(r['hi']),source='judge_conditions_summary.csv'))
for judge,agent,run in [('GPT-OSS-120B','GPT-OSS-120B','gpt_oss_120b_exp_2'),('Qwen3.8-27B','Qwen3.8-27B','qwen3_8_27b_exp_3')]:
    with (root/'runs'/run/'09_analysis/outputs/judge_summary.csv').open() as f:
        r=next(r for r in csv.DictReader(f) if r['condition']=='neutral')
    rows.append(dict(judge=judge,agent=agent,ed=float(r['error_discovery']),ca=float(r['correct_certification']),J=float(r['youden_j']),lo=float(r['youden_j_lo']),hi=float(r['youden_j_hi']),source=f'{run}/judge_summary.csv'))
# Crossed estimates and intervals are reported to two decimals in the original manuscript.
rows.extend([dict(judge='GPT-OSS-120B',agent='Qwen3.8-27B',ed=.56,ca=.66,J=.22,lo=.12,hi=.32,source='original PDF, Sections 5.4 and 5.7 (rounded)'),dict(judge='Qwen3.8-27B',agent='GPT-OSS-120B',ed=.58,ca=.73,J=.31,lo=.21,hi=.41,source='original PDF, Sections 5.4 and 5.7 (rounded)')])
# Keep own and crossed evaluations next to each other.
rows=rows[:7]+[rows[7],rows[9],rows[8],rows[10]]
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'svg.fonttype':'none'})
fig=plt.figure(figsize=(11.8,6.25))
left=fig.add_axes([.075,.25,.31,.585]); right=fig.add_axes([.735,.25,.245,.585])
x=np.linspace(0,100,301)
left.fill_between(x,100-x,100,color='#F0F6F2',zorder=0)
left.fill_between(x,0,100-x,color='#FCF4F1',zorder=0)
left.plot(x,100-x,'--',lw=1,color='#718087')
left.text(48,13,'J = 0',rotation=-45,fontsize=10,color='#627078')
left.text(62,93,'Higher discrimination',ha='center',fontsize=9.5,color='#517158')
# Offset numerical IDs so close estimates remain distinguishable.
offsets=[(7,-11),(-18,-7),(7,-10),(7,5),(-19,-13),(10,8),(-20,8),(7,-11),(7,-11),(7,5),(7,5)]
for i,(r,off) in enumerate(zip(rows,offsets),1):
    c=colors[r['judge']]
    left.scatter(r['ed']*100,r['ca']*100,s=60,color=c,edgecolors='white',linewidth=.7,zorder=4)
    left.annotate(str(i),(r['ed']*100,r['ca']*100),xytext=off,textcoords='offset points',fontsize=10,fontweight='bold',color=c,zorder=5)
left.set(xlim=(0,100),ylim=(0,100),xlabel='Error discovery (%)',ylabel='Correct acceptance (%)')
left.set_xticks([0,25,50,75,100]);left.set_yticks([0,25,50,75,100]);left.grid(color='#DDE2E4',lw=.5)
left.set_title('(a) Detection and correct acceptance',fontsize=13,fontweight='bold',loc='left',pad=24)
left.set_aspect('equal',adjustable='box')
ys=np.arange(len(rows))[::-1]
right.axvspan(0,.64,color='#F0F6F2',zorder=0)
right.axvline(0,color='#53616A',lw=1.2)
for i,(y,r) in enumerate(zip(ys,rows),1):
    c=colors[r['judge']]
    right.errorbar(r['J'],y,xerr=[[r['J']-r['lo']],[r['hi']-r['J']]],fmt='o',color=c,elinewidth=1.8,markersize=6,capsize=3,zorder=3)
right.axhline(3.5,color='#CCD4D8',lw=1)
right.set_yticks(ys,[f"{i}  {short[r['judge']]} → {short[r['agent']]}" for i,r in enumerate(rows,1)])
right.tick_params(axis='y',length=0,pad=10,labelsize=10.5)
right.set_xlim(-.40,.64);right.set_ylim(-.7,10.7)
right.set_xticks([-.4,-.2,0,.2,.4,.6],['−0.4','−0.2','0','+0.2','+0.4','+0.6'])
right.tick_params(axis='x',labelsize=10)
right.grid(axis='x',color='#DDE2E4',lw=.5)
right.set_xlabel("Youden’s J")
right.set_title('(b) Discrimination and uncertainty',fontsize=13,fontweight='bold',loc='right',pad=24)
fig.text(.73,.87,'Judge → evaluated agent',fontsize=10.5,color='#53616A',ha='center')
for ax in [left,right]:
    ax.spines['top'].set_visible(False);ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#AAB5BC');ax.spines['bottom'].set_color('#AAB5BC')
fig.text(.5,.11,'Numbered points identify the same judge–agent pairings in both panels.',ha='center',fontsize=11)
fig.text(.5,.065,'Lines: 95% task-clustered bootstrap confidence intervals. All evaluations use trajectories only.',ha='center',fontsize=10,color='#53616A')
fig.text(.5,.025,'Crossed open-weight estimates are plotted at the precision reported in the original manuscript.',ha='center',fontsize=9.5,color='#53616A')
for ext in ['png','svg']:fig.savefig(out/f'baseline_judge_performance.{ext}',dpi=400,facecolor='white')
with (out/'baseline_judge_performance_data.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('Saved baseline judge performance figure and source values.')
