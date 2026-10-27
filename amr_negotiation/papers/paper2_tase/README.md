[↑ Project hierarchy](../../PROJECT_HIERARCHY.md) · [Parent: papers](../README.md)

# `papers/paper2_tase/`: "Deliberation Costs"

*LLM and VLM Negotiators for Head-On Robot Encounters in Single-Lane Corridors.* Target: IEEE T-ASE. It is a
companion to [paper 1](../paper1_ral/README.md), whose benchmark it uses unchanged.

| File | Contents |
|---|---|
| `main.tex` | The manuscript: LLM adapter, model screen, reasoning on/off, latency cost, vision arms, egocentric agents, tiebreak defaults; an appendix with the prompts verbatim |
| `refs.bib`, `IEEEtran.cls`, `IEEEtran.bst` | Bibliography and IEEE template |
| `fig/screen.pdf` | Model screen (9 models, mediator + plans) |
| `fig/think.pdf` | Reasoning trace on vs off |
| `fig/latency.pdf` | Zero-cost vs measured-latency excess |
| `fig/vlm.pdf` | Text vs image vs image + text |
| `fig/disagree.pdf` | Both-yield / both-proceed disagreement modes |
| `fig/tiebreak.pdf` | Rulebook vs hidden vs visible random tiebreak |
| `make_figures.py` | Regenerates all six figures from [`data/raw/llm/`](../../data/raw/llm/README.md). Run from the repo root |
| `main.pdf`, `main.bbl`, `main.blg` | The last local build |
| `reviews/` | Three adversarial review rounds plus `SUMMARY.md` (verdicts, checklist) |

**Open before submission:**
- Fix the robot radius at `main.tex` line 45: it says 0.15 m, but the benchmark uses a 0.25 m swept radius.
- Remove the draft annotations.

The run index for every figure and table is in [`reports/llm/`](../../reports/llm/README.md).
