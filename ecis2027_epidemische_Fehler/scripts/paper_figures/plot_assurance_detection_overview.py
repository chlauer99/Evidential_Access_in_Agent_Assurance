"""Selected assurance conditions: GPT-OSS and Qwen main runs only.

Reads archived aggregate counts, excluding GPT-OSS run 2 and earlier judges.
Detection shading reports whether all, some, or none of the configurations
reject more than half of the included errors. It is not a significance test.
"""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

root = Path(__file__).resolve().parents[3]
data_dir = root / 'ecis2027_epidemische_Fehler/runs/comparative_analysis/v4'
out = root / 'paper/ECIS2027_manuscript_v4_LaTeX/Figures'
out.mkdir(parents=True, exist_ok=True)

def read(name):
    with (data_dir / name).open() as stream:
        return [r for r in csv.DictReader(stream) if r['attempts'] in ('GPT-OSS', 'Qwen')]

infer = read('ow_inferability.csv')
loci = read('ow_locus.csv')
cells = read('ow_judge_cells.csv')

def select(rows, condition, **keys):
    return [r for r in rows if r['condition'] == condition
            and all(r[k] == v for k, v in keys.items())]

def rate_range(rows, key='discovery'):
    vals = [float(r[key]) for r in rows]
    assert vals
    return f'{100 * min(vals):.0f}–{100 * max(vals):.0f}%', vals

def rates_by_judge(rows, key='discovery'):
    assert len(rows) == 2
    by = {r['judge']: r for r in rows}
    vals = [float(by[j][key]) for j in ('Qwen', 'GPT-OSS')]
    return '\n'.join(f'{j}: {100 * v:.0f}%' for j, v in zip(('Qwen', 'GPT-OSS'), vals)), vals

palette = {
    'all': ('#176B9B', 'white'),
    'mixed': ('#C5DEEC', '#17384D'),
    'none': ('#F8E3D6', '#71402A'),
    'reference': ('#EEF1F4', '#354B5B'),
    'acceptance': ('#FFFFFF', '#273F50'),
}

def shade(vals):
    return 'all' if all(v > .5 for v in vals) else 'none' if all(v <= .5 for v in vals) else 'mixed'

# Cell contents: qualitative reference column followed by the three judge conditions.
reference = ['Wrong outcome\ndetected; no\nlocalisation',
             'Wrong outcome\ndetected; no\nlocalisation',
             'Wrong-value\nchecks',
             'Wrong-order checks\nDo-nothing pass:\n70/300 tasks',
             '78–79%\nFormat-only\nfailures rejected']
contents = {(i, 0): (text, 'reference') for i, text in enumerate(reference)}
for column, condition in enumerate(('neutral', 'checklist', 'record_access'), 1):
    names = select(infer, condition, group='not_inferable')
    n = sum(int(r['n']) for r in names)
    rejected = sum(int(r['rejected']) for r in names)
    if condition == 'record_access':
        by = {r['judge']: r for r in names}
        text = '\n'.join(f"{j}: {by[j]['rejected']}/{by[j]['n']}" for j in ('Qwen', 'GPT-OSS'))
    else:
        text = f'{rejected}/{n} rejected' + ('*\n4 evaluations' if condition == 'neutral' else '')
    contents[0, column] = text, shade([float(r['discovery']) for r in names])
    code = select(infer, condition, group='inferable')
    if condition == 'neutral':
        q, qv = rate_range([r for r in code if r['judge'] == 'Qwen'])
        g, gv = rate_range([r for r in code if r['judge'] == 'GPT-OSS'])
        text, vals = f'Qwen: {100*qv[0]:.0f}%\nGPT-OSS: {g}', qv + gv
    else:
        text, vals = rates_by_judge(code)
    contents[1, column] = text, shade(vals)
    for row, locus in [(2, 'conclusion'), (3, 'action')]:
        text, vals = rate_range(select(loci, condition, locus=locus))
        contents[row, column] = text, shade(vals)
    accepted = select(cells, condition)
    if condition == 'neutral':
        text, _ = rate_range(accepted, key='correct_accepted')
    else:
        text, _ = rates_by_judge(accepted, key='correct_accepted')
    contents[4, column] = text, 'acceptance'
assert contents[0, 1][0].startswith('1/272')
assert contents[0, 2][0] == '2/136 rejected'
assert len(select(cells, 'neutral')) == 4

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'svg.fonttype': 'none'})
fig = plt.figure(figsize=(12.4, 5.8))
ax = fig.add_axes([.015, .015, .97, .97])
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
left, width, gap = .235, .185, .007
header_y, top, height = .89, .805, .127
headers = [
    ('Reference-based\nbenchmark grader', 'Outcome checks'),
    ('Trajectory\nonly', '4 judge–agent pairings'),
    ('Trajectory +\nchecklist', '2 own-model evaluations'),
    ('Trajectory +\nrecord access', '2 own-model evaluations'),
]
ax.text(.004, .925, 'Observed assurance\nperformance', ha='left', va='center', fontsize=12.5, weight='bold', color='#273F50')
labels = ['Patient-name\nfalse absence', 'Code / pagination\nerrors', 'Conclusion\nerrors', 'Action\nerrors', 'Correct\nacceptance']
for col, (title, subtitle) in enumerate(headers):
    x = left + col * width + width / 2
    ax.text(x, header_y+.035, title, ha='center', va='center', fontsize=12, weight='bold', linespacing=1.1)
    ax.text(x, header_y-.045, subtitle, ha='center', va='center', fontsize=9, color='#5C6D78')
for row, label in enumerate(labels):
    y = top - (row+1)*height
    ax.text(.004, y+height/2, label, ha='left', va='center', fontsize=11.5, weight='bold', color='#273F50', linespacing=1.2)
    for col in range(4):
        text, level = contents[row,col]
        fc, tc = palette[level]
        ax.add_patch(Rectangle((left+col*width+gap/2, y+gap/2),width-gap,height-gap,
                               facecolor=fc,edgecolor='#BBC7CF' if row==4 else 'none',linewidth=.8))
        ax.text(left+col*width+width/2, y+height/2, text, ha='center',va='center',fontsize=11.2,color=tc,linespacing=1.15)
legend_y = .115
for x, key, text in [(.235,'all','All >50%'),(.405,'mixed','Some >50%'),(.585,'none','None >50%')]:
    ax.add_patch(Rectangle((x,legend_y-.014),.025,.027,facecolor=palette[key][0],edgecolor='none'))
    ax.text(x+.033,legend_y,text,va='center',fontsize=9.5,color='#435A68')
ax.text(.004,legend_y,'Error discovery:',va='center',fontsize=9.5,color='#435A68')
ax.text(.004,.069,'Shading indicates which judge configurations reject more than half of included errors. Ranges span configurations.',fontsize=9,color='#526774')
ax.text(.004,.035,'* The sole rejection concerned answer format. Wrong-order exclusions apply. API documentation is not shown.',fontsize=9,color='#526774')
for extension in ('png', 'svg'):
    fig.savefig(out / f'assurance_detection_overview_openweight.{extension}',dpi=400,facecolor='white')
with (out/'assurance_detection_overview_openweight_data.csv').open('w',newline='') as stream:
    writer=csv.writer(stream);writer.writerow(['row','column','text','shading'])
    for (i,j),(text,level) in sorted(contents.items()):writer.writerow([labels[i],headers[j][0],text,level])
print('Created assurance_detection_overview_openweight PNG, SVG, and displayed values.')
