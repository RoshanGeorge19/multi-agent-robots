[↑ Project hierarchy](../PROJECT_HIERARCHY.md) · [Repo README](../README.md)

# Papers

| Folder | Manuscript | Venue | Status |
|---|---|---|---|
| [`paper1_ral/`](paper1_ral/README.md) | *Who Backs Into the Bay? Benchmarking Negotiation Policies for Head-On Robot Encounters in Single-Lane Corridors* | IEEE RA-L (letter, 8 pages) | Draft; 3 adversarial review rounds, final verdict MINOR |
| [`paper2_tase/`](paper2_tase/README.md) | *Deliberation Costs: LLM and VLM Negotiators for Head-On Robot Encounters in Single-Lane Corridors* | IEEE T-ASE | Draft; 3 adversarial review rounds, final verdict MINOR. Companion to paper 1. |

Each folder contains:

| File | Contents |
|---|---|
| `main.tex` | The manuscript. Self-contained: it needs only `refs.bib`, `IEEEtran.cls`/`.bst` and `fig/*.pdf`. |
| `main.pdf`, `main.bbl`, `main.blg` | The last local build |
| `fig/` | Figure PDFs |
| `make_figures.py` | Regenerates the data figures from `data/raw/`. Run from the repo root: `python papers/paper1_ral/make_figures.py`. Paper 1's `scenarios.pdf` is drawn from the scenario configs. |
| `reviews/` | Review cycle record: `round-N-review.md`, `round-N-response.md`, and `SUMMARY.md` with the open pre-submission checklist. These are historical records, so the paths inside them use the old layout (`paper/`, `studies/`). |

**Overleaf.** Zip `main.tex`, `refs.bib`, `IEEEtran.cls`, `IEEEtran.bst` and `fig/` from a paper folder and upload it
(*New Project → Upload Project*). Zips placed in `papers/` are git-ignored.

**Open items before submission** (from `reviews/SUMMARY.md`):
- the artifact URL/DOI (paper 1 still says `[ANONYMIZED-URL]`);
- remove the `% TODO`, `% VERIFIED` and "DRAFT" annotations;
- release the per-episode convoy and T-junction rows;
- fix paper 2's robot radius (it says 0.15 m; the benchmark uses a 0.25 m swept radius).
