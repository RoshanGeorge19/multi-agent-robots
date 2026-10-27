# Study reports

Each study was written up as it was run. The reports explain the question, the method, the bugs found along the
way and the fixes they motivated. Read them for the reasoning behind a result.

> **Canonical numbers are in the papers** (`papers/paper1_ral/main.tex`, `papers/paper2_tase/main.tex`), which
> report the final code. Several reports are snapshots from earlier code and differ slightly. Examples:
> - reactive success: 93.1% in `01` vs 93.8% in paper 1;
> - S8 success: ≥ 96.7% in `02` vs ≥ 99.3% in paper 1;
> - the S9 section of `02` is superseded by `04`;
> - the "after" numbers in `07` predate the final T-junction table, `data/tables/classical/tjunction_goal.txt`.

## `classical/`: 2D simulator studies (paper 1)

| Report | Was | Question |
|---|---|---|
| [`01_round1_S1-S6.md`](classical/01_round1_S1-S6.md) | `REPORT.md` | Price of no communication, bay position, asymmetric robots, packet loss, two bays, misreporting (plus a first Gazebo spot check) |
| [`02_round2_S7-S10.md`](classical/02_round2_S7-S10.md) | `REPORT_r2.md` | Noisy bids, comms stress and extreme comms, payments (first version), repeated-encounter fairness |
| [`03_bid_cost_fix.md`](classical/03_bid_cost_fix.md) | `REPORT_bid_cost.md` | Fix: weight each robot's delay by its *own* urgency (S2 and convoy re-run) |
| [`04_clarke_payments.md`](classical/04_clarke_payments.md) | `REPORT_payments.md` | Proper Clarke-pivot (VCG) payments vs misreports |
| [`05_reservation_baseline.md`](classical/05_reservation_baseline.md) | `REPORT_reservation.md` | Corridor-reservation baseline and a side-level convoy reference |
| [`06_convoy_group_bid.md`](classical/06_convoy_group_bid.md) | `REPORT_group_bid.md` | Convoys (2 v 1): `group_bid` and the make-room rule |
| [`07_tjunction.md`](classical/07_tjunction.md) | `REPORT_tjunction.md` | T-junction: turning into the side branch, deadlock fix |
| [`08_asymmetric_maps.md`](classical/08_asymmetric_maps.md) | `REPORT_asym.md` | Robots that know different bays; sharing maps in BIDs |
| [`09_blocked_bays.md`](classical/09_blocked_bays.md) | `REPORT_wrong_map.md` | A bay on the map that is physically blocked |
| [`10_explore_mode.md`](classical/10_explore_mode.md) | `REPORT_explore.md` | Mapping as you go, share-on-detect, hold-for-map (2D and Gazebo) |
| [`11_learned_negotiator.md`](classical/11_learned_negotiator.md) | `REPORT_learned.md` | Tabular learned negotiator, in and out of distribution |

## `gazebo/`: ROS 2 + Gazebo validation

| Report | Was | Question |
|---|---|---|
| [`01_s1_sweep.md`](gazebo/01_s1_sweep.md) | `REPORT_gazebo.md` | Does the S1 baseline transfer from 2D to Gazebo? (50 runs, early code) |
| [`02_round2_convoy_tjunction_comms.md`](gazebo/02_round2_convoy_tjunction_comms.md) | `REPORT_gazebo_r2.md` | Convoy, T-junction and lossy comms in Gazebo; sim-to-real fixes |

The final-code Gazebo validation (460 runs over every study) is summarised in
[`data/tables/gazebo/gazebo_all.md`](../data/tables/gazebo/gazebo_all.md) and in paper 1's "Gazebo validation" section.

## `llm/`: LLM/VLM negotiators (paper 2)

[`llm/README.md`](llm/README.md) indexes the ~55 LLM runs by stage and model.
