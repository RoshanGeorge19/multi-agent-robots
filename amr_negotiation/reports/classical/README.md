[↑ Project hierarchy](../../PROJECT_HIERARCHY.md) · [Parent: reports](../README.md)

# `reports/classical/`: 2D-simulator study write-ups (paper 1)

The reports are numbered in the order the studies were run. Each one gives the question, the method, the
results, the bugs found and the fixes they motivated. The final-code numbers are in paper 1; see the caveats in
[`reports/README.md`](../README.md).

| # | Report | Question | Script → data |
|---|---|---|---|
| 01 | [`01_round1_S1-S6.md`](01_round1_S1-S6.md) | Price of no comms, bay position, asymmetric robots, packet loss, two bays, misreporting; first Gazebo spot check | `run_studies.py` → `S1`–`S6` |
| 02 | [`02_round2_S7-S10.md`](02_round2_S7-S10.md) | Noisy bids, comms stress, extreme comms, first payments rule, repeated-encounter fairness | `run_studies_r2.py` → `S7`–`S10` |
| 03 | [`03_bid_cost_fix.md`](03_bid_cost_fix.md) | Fix: each robot's delay weighted by its own urgency (S2 and convoy re-run) | `run_studies.py`, `convoy_group.py` |
| 04 | [`04_clarke_payments.md`](04_clarke_payments.md) | Proper Clarke-pivot (VCG) payments under misreports | `run_studies_r2.py` → `S9` |
| 05 | [`05_reservation_baseline.md`](05_reservation_baseline.md) | Corridor reservation; side-level convoy reference | `reservation_baseline.py` |
| 06 | [`06_convoy_group_bid.md`](06_convoy_group_bid.md) | Convoys: `group_bid` and the make-room rule | `convoy_group.py` |
| 07 | [`07_tjunction.md`](07_tjunction.md) | T-junction turn-in deadlock and its fix | `tjunction_goal.py` |
| 08 | [`08_asymmetric_maps.md`](08_asymmetric_maps.md) | Robots that know different bays; sharing maps | `asym_map.py` |
| 09 | [`09_blocked_bays.md`](09_blocked_bays.md) | A mapped bay that is physically blocked | `wrong_map.py` |
| 10 | [`10_explore_mode.md`](10_explore_mode.md) | Map-as-you-go, share-on-detect, hold-for-map (2D + Gazebo) | `explore_map.py` |
| 11 | [`11_learned_negotiator.md`](11_learned_negotiator.md) | Tabular learned negotiator, in and out of distribution | `learned_negotiator.py` |

Scripts: [`experiments/classical/`](../../experiments/classical/README.md). Tables:
[`data/tables/classical/`](../../data/tables/classical/README.md), [`classical_r2/`](../../data/tables/classical_r2/README.md).
