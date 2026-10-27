[↑ Project hierarchy](../../PROJECT_HIERARCHY.md) · [Parent: experiments](../README.md)

# `experiments/classical/`: 2D-simulator studies (paper 1)

Run from the repo root (`python experiments/classical/<script>`). Everything is pure Python on the 2D simulator,
so no ROS or GPU is needed.

| Script | Studies | Episodes | Writes | Report |
|---|---|---|---|---|
| `run_studies.py OUT [names]` | S1 baseline, S2 asymmetry, S3 comms, S4 two bays, S6 misreport | ~15k | `OUT/<study>.csv` | [01](../../reports/classical/01_round1_S1-S6.md) |
| `run_studies_r2.py OUT [names]` | S7 noisy bids, S8 / S8b comms stress, S8c protocol ablation, S9 Clarke payments, S10 repeated encounters | ~25k | `OUT/<study>.csv` | [02](../../reports/classical/02_round2_S7-S10.md), [04](../../reports/classical/04_clarke_payments.md) |
| `reservation_baseline.py [DATA]` | corridor reservation vs the negotiators | 1,260 | `data/raw/classical/reservation.csv.gz`, `data/tables/classical/reservation.md` | [05](../../reports/classical/05_reservation_baseline.md) |
| `convoy_group.py` | 2 v 1 convoy: `group_bid`, make-room, side-level reference | 1,080 | stdout → `data/tables/classical/convoy_group.txt` | [06](../../reports/classical/06_convoy_group_bid.md) |
| `tjunction_goal.py [out.txt]` | T-junction with the branch as a destination | 384 | `data/tables/classical/tjunction_goal.txt` | [07](../../reports/classical/07_tjunction.md) |
| `asym_map.py` | robots knowing different bays; map sharing | 840 | stdout → `data/tables/classical/asym_map.txt` | [08](../../reports/classical/08_asymmetric_maps.md) |
| `wrong_map.py` | a bay on the map that is physically blocked | 320 | stdout → `data/tables/classical/wrong_map.md` | [09](../../reports/classical/09_blocked_bays.md) |
| `explore_map.py [OUT_CSV]` | explore mode, share-on-detect, hold-for-map | 1,800 | `data/raw/classical/explore_map.csv.gz` | [10](../../reports/classical/10_explore_mode.md) |
| `learned_negotiator.py` | tabular learned negotiator: train on 800, evaluate 2 × 150 | ~3k | `data/tables/classical/learned_negotiator.md`, `learned_table.json` | [11](../../reports/classical/11_learned_negotiator.md) |

- `OUT` is any scratch folder, e.g. `results/` (git-ignored). Gzip a CSV into [`data/raw/classical/`](../../data/raw/classical/README.md) to release it.
- To turn CSVs into tables, see [`experiments/analysis/`](../analysis/README.md).
- `run_studies_r2.py` imports `run_studies.py`, which holds the shared job builder and the S6 bid-scaling wrapper.
- **Workers.** Most scripts use `mp.Pool(8)`. On a 32-core machine, S1 alone takes about 40 s and reproduces the released CSV row for row.
