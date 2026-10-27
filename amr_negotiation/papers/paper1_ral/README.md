[↑ Project hierarchy](../../PROJECT_HIERARCHY.md) · [Parent: papers](../README.md)

# `papers/paper1_ral/`: "Who Backs Into the Bay?"

*Benchmarking Negotiation Policies for Head-On Robot Encounters in Single-Lane Corridors.* Target: IEEE RA-L,
an 8-page letter. Authors: R. George, M. Glavin, E. Jones, B. Deegan (University of Galway).

| File | Contents |
|---|---|
| `main.tex` | The manuscript: benchmark, the eight policies, the study design (Table I, one row per study), results, the safeguard ablation (Table II), Gazebo validation (Table III) |
| `refs.bib`, `IEEEtran.cls`, `IEEEtran.bst` | Bibliography and IEEE template |
| `fig/scenarios.pdf` | The four benchmark layouts (single bay, two bays, convoy, T-junction) |
| `fig/results.pdf` | (a) `cost_bid` excess vs bid noise; (b) urgency-weighted excess with asymmetric robots |
| `make_figures.py` | Regenerates both figures from [`configs/scenarios/`](../../configs/scenarios/README.md) and [`data/raw/classical/`](../../data/raw/classical/README.md). Run from the repo root |
| `main.pdf`, `main.bbl`, `main.blg` | The last local build |
| `reviews/` | Three adversarial review rounds (`round-N-review.md` / `-response.md`). `SUMMARY.md` holds the verdicts and the pre-submission checklist |

**Open before submission:**
- the artifact URL (`[ANONYMIZED-URL]`);
- remove the `% TODO` / `% VERIFIED` / DRAFT annotations;
- release the convoy and T-junction per-episode rows.

Supporting write-ups: [`reports/classical/`](../../reports/classical/README.md), [`reports/gazebo/`](../../reports/gazebo/README.md).
