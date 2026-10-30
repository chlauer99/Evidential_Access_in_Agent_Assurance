# Paper figures

Reproducible Matplotlib scripts for the figures developed during the manuscript revision.
Paths are resolved relative to each script, so scripts can be launched from any working directory.
No model calls or network access are needed to render the figures once dependencies are installed.

## Setup and rendering

Use Python 3.12 or newer. From the repository root:

```sh
python3 -m venv ecis2027_epidemische_Fehler/scripts/paper_figures/.venv
ecis2027_epidemische_Fehler/scripts/paper_figures/.venv/bin/python -m pip install -r ecis2027_epidemische_Fehler/scripts/paper_figures/requirements.txt
ecis2027_epidemische_Fehler/scripts/paper_figures/.venv/bin/python ecis2027_epidemische_Fehler/scripts/paper_figures/render_all.py
```

Render one figure by running its script instead of `render_all.py`.
Each script writes PNG (400 dpi) and SVG files to
`paper/ECIS2027_manuscript_v4_LaTeX/Figures/`, replacing its corresponding existing outputs.
The baseline script also writes the values and sources used as a CSV.

## Current figures

| Script | Output stem |
| --- | --- |
| `plot_assurance_support_effects.py` | `assurance_support_effects` |
| `plot_assurance_support_heatmap.py` | `assurance_support_heatmap` |
| `plot_combined_judges_venn.py` | `combined_judges_venn_proportional` |
| `plot_baseline_judge_performance.py` | `baseline_judge_performance_openweight` |
| `plot_assessment_classification.py` | `assessment_classification_schema_v4` |
| `plot_assurance_detection_overview.py` | `assurance_detection_overview_openweight` |

### Data and interpretation

- The detection overview reads aggregate counts in `runs/comparative_analysis/v4/`, excludes GPT-OSS run 2 and all earlier judges, and shows four trajectory-only pairings and two own-model evaluations per support condition. Shading describes whether all, some, or none of those configurations reject more than half of included errors. It is not a significance test. The benchmark column summarises reference checks and the original control result.

- Support effects and the heatmap read `paired_conditions.csv` in the archived GPT-OSS and Qwen run outputs under `ecis2027_epidemische_Fehler/runs/`.
- The baseline plot reads the archived summary tables. Crossed open-weight estimates and confidence intervals are entered at the rounded precision reported in the original manuscript. These are not reconstructed per-attempt crossed verdicts.
- The Venn plot reconstructs approximate region areas from rounded manuscript detection rates and exact shared-miss counts. The approximation is marked in the figure. Areas use the same percentage scale across the two panels; the enclosing rectangles do not encode the total error counts.
- The assessment diagram represents the classification scheme, not measured frequencies. `Unclassified` in its error branch refers to evidential provenance. The simplified diagram omits unclassifiable task outcomes and analysis exclusions, which must remain described in the Methods.

## Archived drafts

`archive/` retains the earlier layouts and broader baseline comparison. They are not rendered by default.
To regenerate them as well:

```sh
ecis2027_epidemische_Fehler/scripts/paper_figures/.venv/bin/python ecis2027_epidemische_Fehler/scripts/paper_figures/render_all.py --include-archive
```

The original `figure1.png` and `figure2.png` predate these scripts and are not regenerated here.
The rendering scripts no longer depend on temporary directories or machine-specific paths.
