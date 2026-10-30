import os,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
out=Path(__file__).resolve().parents[3] / 'paper/ECIS2027_manuscript_v4_LaTeX/Figures'
out.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none'})
fig=plt.figure(figsize=(11.4,4.9));ax=fig.add_axes([.012,.02,.976,.96]);ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
def box(x,y,w,h,fc,ec='#B6C3CC',text=None,size=11,weight='normal'):
    p=FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle='round,pad=0.006,rounding_size=0.012',facecolor=fc,edgecolor=ec,lw=1.1,zorder=2);ax.add_patch(p)
    if text:ax.text(x,y,text,ha='center',va='center',fontsize=size,fontweight=weight,color='#2B4252',linespacing=1.3,zorder=3)
    return p
def line(a,b,arrow=True):ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>' if arrow else '-',mutation_scale=10,color='#778A97',lw=1.2,zorder=1))
# Stage 1: official benchmark verdict and subsequent reference-based assessment.
box(.16,.865,.285,.18,'#EDF1F5',text='Official verdict\nPass / fail',size=12,weight='bold')
line((.31,.865),(.365,.865))
box(.675,.865,.61,.18,'#F4F6F8')
ax.text(.675,.915,'Assessment of substantive correctness',ha='center',fontsize=12,fontweight='bold',color='#2B4252')
ax.text(.675,.868,'Reference-answer regrading · Original-answer check',ha='center',fontsize=10.5,color='#435B6A')
ax.text(.675,.818,'Task · Source record · Reference solution',ha='center',fontsize=10,color='#637581')
# Stage 2: task outcome. The two error categories remain distinct.
centers=[.15,.42,.65,.87]
for x in centers:line((.675,.766),(x,.640))
box(.15,.565,.275,.14,'#EDF5F0','#9CB9A6')
ax.text(.15,.585,'Substantively correct',ha='center',fontsize=11.5,fontweight='bold',color='#355B46')
ax.text(.15,.540,'Official pass · Format-only failure',ha='center',fontsize=9.3,color='#466051')
box(.42,.565,.225,.14,'#FAF1E4','#CDB38D',text='Substantive\nanswer error',size=11.5,weight='bold')
box(.65,.565,.19,.14,'#FAF1E4','#CDB38D',text='Action error',size=11.5,weight='bold')
box(.87,.565,.215,.14,'#F2F3F4','#BFC5CA',text='Unclassified\noutcome',size=11.5,weight='bold')
# Bracket groups answer and action errors without merging them into an error locus.
line((.42,.487),(.42,.448),False);line((.65,.487),(.65,.448),False)
line((.42,.448),(.65,.448),False)
line((.535,.448),(.535,.418),False)
ax.text(.535,.388,'Substantive errors: two separate classification dimensions',ha='center',va='center',fontsize=11.3,fontweight='bold',color='#344C5B')
line((.535,.357),(.255,.307));line((.535,.357),(.755,.307))
# Stage 3: two dimensions, each with three clearly separated categories.
box(.255,.170,.475,.26,'#EFF5F9','#7FA3B8')
box(.755,.170,.475,.26,'#FBF5EB','#C5A874')
ax.text(.255,.258,'ERROR LOCUS',ha='center',fontsize=11.5,fontweight='bold',color='#175F86')
ax.text(.755,.258,'EVIDENTIAL PROVENANCE',ha='center',fontsize=11.5,fontweight='bold',color='#946317')
for x,w,t in [(.102,.145,'Evidence\ngathering'),(.267,.145,'Conclusion'),(.420,.115,'Action')]:
    box(x,.145,w,.105,'#FFFFFF','#B4CAD8',text=t,size=10.5)
for x,w,t in [(.602,.140,'Grounded'),(.755,.140,'Fabricated'),(.914,.140,'Unclassified')]:
    box(x,.145,w,.105,'#FFFFFF','#DBC59F',text=t,size=10.5)
for ext in ['png','svg']:fig.savefig(out/f'reference_standard_classification_overview.{ext}',dpi=400,facecolor='white')
print('Saved complete compact classification overview.')
