[↑ Project hierarchy](../../PROJECT_HIERARCHY.md) · [Parent: papers](../README.md)

# `papers/paper1_journal/`: "Who Backs Into the Bay?" (12–14 Page Journal Version)

*Who Backs Into the Bay? Benchmarking Information, Incentives, and Sim-to-3D Robustness in Narrow-Corridor Robot Negotiation.*
Target: 12–14 page `IEEEtran` journal format (e.g., *IEEE Transactions on Automation Science and Engineering*).
Authors: R. George, M. Glavin, E. Jones, and B. Deegan (University of Galway).

Restructures the 8-page letter ([`../paper1_ral/`](../paper1_ral/README.md)) into a full journal architecture organized around two system layers and four research questions (RQ1: Information, Geometry, Cost Noise & Generalization; RQ2: Strategic Incentives & Repeated-Encounter Fairness; RQ3: Channel Impairment, Safeguard Ablation & Map Uncertainty; RQ4: Three-Robot Topologies & Sim-to-3D Gazebo Transfer), with explicit mathematical formulations (Eqs. 1–7), 5 tables, and 7 multi-panel vector figures.

| File | Contents |
|---|---|
| `main.tex` | Self-contained 12–14 page `IEEEtran` journal manuscript |
| `refs.bib`, `IEEEtran.cls`, `IEEEtran.bst` | Verified bibliography and IEEE journal class/style |
| `make_figures.py` | Deterministically regenerates all 7 vector PDFs in `fig/` from `configs/scenarios/`, `data/raw/classical/`, `data/tables/gazebo/`, and `media/gazebo_final/`. Run from repo root: `PYTHONPATH=$PWD python3 papers/paper1_journal/make_figures.py` |
| `fig/scenarios.pdf` | Fig. 1: 4 scenario topologies + Gazebo Harmonic Waffle frame + cross-sectional clearance schematic |
| `fig/protocol.pdf` | Fig. 2: Simulator-agnostic 20 Hz state machine + constant-speed kinematic yield timeline |
| `fig/rq1_information.pdf` | Fig. 3: Single-bay geometry & reservation, asymmetric robots (`S2`), bid noise (`S7`), and bandit layout shift |
| `fig/rq2_incentives.pdf` | Fig. 4: Clarke-pivot VCG misreport curves (`S9`) and repeated-encounter fairness Pareto (`S10`) |
| `fig/rq3_comms_maps.pdf` | Fig. 5: Packet-loss/latency resilience (`S3` & `S8b`) and online bay discovery & map sharing (`explore`) |
| `fig/rq4_topologies.pdf` | Fig. 6: Convoy 2-vs.-1 delays (`convoy_group`) and T-junction `goal_wait` completion/delay (`tjunction_goal`) |
| `fig/rq4_gazebo.pdf` | Fig. 7: 460-run paired Gazebo-vs.-2D delay scatter and Seed-3 lidar-clustering lag trace |
| `main.pdf`, `main.bbl` | Compiled 14-page PDF and bibliography |
| `figures_and_tables_guide.pdf`, `figures_and_tables_guide.tex` | Standalone 10-page visual & tabular companion guide embedding all 7 figures (20 sub-panels) and documenting all 5 tables (*What It Shows* and *What It Means*) |

**Open before submission:**
- Replace `[ANONYMIZED-URL]` with the archival repository URL / DOI and remove draft header note.

Supporting write-ups: [`reports/classical/`](../../reports/classical/README.md), [`reports/gazebo/`](../../reports/gazebo/README.md).
