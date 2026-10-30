import os, sys, math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle
out=Path(__file__).resolve().parents[3] / 'paper/ECIS2027_manuscript_v4_LaTeX/Figures'
out.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none'})
def intersection(r,R,d):
    if d>=r+R:return 0.
    if d<=abs(r-R):return math.pi*min(r,R)**2
    return r*r*math.acos((d*d+r*r-R*R)/(2*d*r))+R*R*math.acos((d*d+R*R-r*r)/(2*d*R))-.5*math.sqrt((-d+r+R)*(d+r-R)*(d-r+R)*(d+r+R))
def geometry(a,b,both):
    r,R=math.sqrt(a/math.pi),math.sqrt(b/math.pi)
    lo,hi=abs(r-R),r+R
    for _ in range(100):
        d=(lo+hi)/2
        if intersection(r,R,d)>both:lo=d
        else:hi=d
    return r,R,(lo+hi)/2
sets=[('GPT-OSS-120B attempts',405,153,.24,.58),('Qwen3.8-27B attempts',352,54,.56,.77)]
fig,axs=plt.subplots(1,2,figsize=(10.6,5.25))
fig.subplots_adjust(left=.025,right=.975,top=.87,bottom=.18,wspace=.08)
for ax,(title,n,miss,a,b) in zip(axs,sets):
    outside=miss/n; union=1-outside; both=a+b-union
    r,R,d=geometry(a,b,both)
    cx0,cx1=-d/2,d/2
    center=((cx0-r)+(cx1+R))/2
    cx0-=center;cx1-=center
    ax.set_xlim(-.79,.79);ax.set_ylim(-.76,.61);ax.set_aspect('equal');ax.axis('off')
    ax.set_title(f'{title}\n$n={n}$ substantive errors',fontsize=13,fontweight='bold',pad=14)
    ax.add_patch(Rectangle((-.77,-.73),1.54,1.30,facecolor='#FAFBFC',edgecolor='#CCD4DA',linewidth=1,zorder=0))
    ax.add_patch(Circle((cx0,.025),r,facecolor='#176B9B',edgecolor='#176B9B',alpha=.30,lw=1.7,zorder=2))
    ax.add_patch(Circle((cx1,.025),R,facecolor='#C17A0A',edgecolor='#C17A0A',alpha=.30,lw=1.7,zorder=3))
    # Midpoints of each exclusive interval and the shared interval on the horizontal diameter.
    xleft=(cx0-r+cx1-R)/2
    xshared=(cx1-R+cx0+r)/2
    xright=(cx0+r+cx1+R)/2
    ax.text(xshared,.025,f'Both\n≈{100*both:.0f}%',ha='center',va='center',fontsize=15,fontweight='bold',color='#26383B',zorder=5)
    for x,tx,v,label,col in [(xleft,-.56,a-both,'GPT-OSS only','#176B9B'),(xright,.55,b-both,'Qwen only','#94600E')]:
        ax.annotate(f'{label}\n≈{100*v:.0f}%',xy=(x,.025),xytext=(tx,.50),ha='center',va='center',fontsize=11,fontweight='bold',color=col,bbox=dict(facecolor='white',edgecolor='none',alpha=.93,pad=2),arrowprops=dict(arrowstyle='-',color=col,linewidth=1,connectionstyle='angle3,angleA=90,angleB=0'),zorder=6)
    ax.text(0,-.56,f'Missed by both: {miss}/{n} ({100*outside:.1f}%)',ha='center',fontsize=11,fontweight='bold',color='#8F4033')
    ax.text(0,-.67,f'Detected by either: {100*union:.1f}%',ha='center',fontsize=10.5,color='#354B55')
    assert abs(intersection(r,R,d)-both)<1e-9
    print(title, 'only GPT',a-both,'both',both,'only Qwen',b-both,'neither',outside)
fig.text(.5,.115,'Circles represent detected errors; overlap represents detection by both judges.',ha='center',fontsize=11)
fig.text(.5,.065,'Circle and overlap areas are proportional to reconstructed shares on a common scale.',ha='center',fontsize=10,color='#55616B')
fig.text(.5,.023,'≈ Approximate shares reconstructed from rounded detection rates; shared-miss counts are exact.',ha='center',fontsize=10,color='#55616B')
for ext in ['png','svg']:fig.savefig(out/f'combined_judges_venn_proportional.{ext}',dpi=400,facecolor='white')
