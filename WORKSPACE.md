# WORKSPACE.md - Research Workspace Layout

This workspace is organized as a technical lab notebook plus a coding workspace.

## Recommended Structure

- `projects/`
  - Active coding projects, notebooks, scripts, packages, and experiment-specific repos
- `data/`
  - Local data staging area
  - Suggested subfolders: `raw/`, `interim/`, `processed/`, `external/`
- `data_dictionaries/`
  - Definitions for plant tags, lab variables, inclusion descriptors, units, and business rules
- `workflows/`
  - Step-by-step technical workflows and SOP-like notes
  - Examples: Thermo-Calc studies, inclusion analysis routines, plant-data ETL checklists
- `notes/`
  - Short-form technical notes, hypotheses, meeting notes, and interpretation drafts
- `templates/`
  - Reusable templates for notebooks, reports, scripts, figure styles, and project skeletons
- `references/`
  - Local summaries of papers, copied excerpts you are allowed to store, standards notes, and bibliographic scratch notes
- `memory/`
  - Daily operating memory and technical memory files

## How to Use It

### `projects/`
Use one subfolder per substantial project. Good candidates:
- `steelmaking-data-pipeline/`
- `inclusion-classification/`
- `thermo-calc-postprocess/`
- `thesis-analysis/`

### `data/`
Treat as a staging zone, not as long-term canonical storage unless intended.
- `raw/`: untouched exports
- `interim/`: cleaned but not final
- `processed/`: analysis-ready outputs
- `external/`: reference datasets from outside sources

### `data_dictionaries/`
Put machine-usable definitions here.
Examples:
- tag name → meaning
- unit conventions
- heat/sample key structure
- missing-value semantics
- quality flags

### `workflows/`
Document repeatable procedures.
Examples:
- `thermo-calc-equilibrium-study.md`
- `inclusion-analysis-checklist.md`
- `plant-data-cleaning.md`

### `notes/`
Use for active thinking:
- hypotheses
- interpretation fragments
- experiment ideas
- thesis section drafts

### `templates/`
Keep reusable assets here.
Examples:
- starter notebook
- report skeleton
- matplotlib/seaborn style helper
- project README template

## Suggested Operating Rules

1. Raw data should remain untouched.
2. Every reusable analysis should graduate from notebook-only to script/module form.
3. If a plant variable is ambiguous, define it in `data_dictionaries/`.
4. If a workflow repeats twice, document it in `workflows/`.
5. If a criterion matters repeatedly, store it in memory and/or a data dictionary.
