[↑ Project hierarchy](../../../PROJECT_HIERARCHY.md) · [Parent: data/tables](../README.md)

# `data/tables/classical/`: round-1 and extension-study tables

| File | Contents | Built by | Report |
|---|---|---|---|
| `results.md`, `fig/S1_delay_vs_bay.png`, `fig/S3_success_heatmap.png` | S1–S6: success, delay, excess over the oracle, fairness, misreporting | `experiments/analysis/analyse.py` | [01](../../../reports/classical/01_round1_S1-S6.md) |
| `protocol_ablation.md` | S8c: safeguards on/off under extreme comms | `analyse_protocol.py` | paper 1, Table II |
| `reservation.md` | reservation baseline vs negotiators, by bay position | `reservation_baseline.py` | [05](../../../reports/classical/05_reservation_baseline.md) |
| `convoy_group.txt` | convoy (2 v 1) by B type and policy, incl. `side_oracle` | `convoy_group.py` | [06](../../../reports/classical/06_convoy_group_bid.md) |
| `tjunction_goal.txt`, `tjunction_goal_before.txt` | T-junction turn-in, after / before the junction fix | `tjunction_goal.py` | [07](../../../reports/classical/07_tjunction.md) |
| `asym_map.txt` | different known bays × map sharing | `asym_map.py` | [08](../../../reports/classical/08_asymmetric_maps.md) |
| `wrong_map.md` | blocked bays | `wrong_map.py` | [09](../../../reports/classical/09_blocked_bays.md) |
| `explore_map.md` | explore mode, share-on-detect, hold | `explore_map.py` | [10](../../../reports/classical/10_explore_mode.md) |
| `learned_negotiator.md`, `learned_table.json` | learned-negotiator evaluation; the trained table used by the `learned` policy (also in Gazebo) | `learned_negotiator.py` | [11](../../../reports/classical/11_learned_negotiator.md) |

Raw inputs: [`data/raw/classical/`](../../raw/classical/README.md). Scripts:
[`experiments/classical/`](../../../experiments/classical/README.md),
[`experiments/analysis/`](../../../experiments/analysis/README.md).
