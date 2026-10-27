[↑ Project hierarchy](../../PROJECT_HIERARCHY.md) · [Parent: reports](../README.md)

# `reports/gazebo/`: Gazebo validation write-ups

| # | Report | What it covers |
|---|---|---|
| 01 | [`01_s1_sweep.md`](01_s1_sweep.md) | The S1 baseline in Gazebo (50 runs, early code). Negotiating policies transfer run for run; the reactive baseline only statistically |
| 02 | [`02_round2_convoy_tjunction_comms.md`](02_round2_convoy_tjunction_comms.md) | Convoy, T-junction and 50%-loss comms in Gazebo (72 + 36 runs). Two sim-to-real gaps found and fixed: a goal on the room wall, and lidar occlusion in the side branch |

**The final-code validation is not written up here.** It covers 460 runs over a reduced grid of every study, and
lives in [`data/tables/gazebo/gazebo_all.md`](../../data/tables/gazebo/gazebo_all.md) and in paper 1's Gazebo
section. The hold-for-map Gazebo batch is in
[`reports/classical/10_explore_mode.md`](../classical/10_explore_mode.md).

Scripts: [`experiments/gazebo/`](../../experiments/gazebo/README.md). Data:
[`data/raw/gazebo/`](../../data/raw/gazebo/README.md).
