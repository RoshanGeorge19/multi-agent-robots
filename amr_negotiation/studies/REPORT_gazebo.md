# Gazebo sweep: S1 baseline, 10 seeds per policy

Repeats the S1 baseline (single-bay corridor, head-on encounter) in Gazebo Harmonic + ROS 2 Jazzy with two TurtleBot3 Waffles, and compares every run with a 2D-sim rerun of the same scenario, policy and seed.

## Setup
- Scenarios: `gazebo/scen/gz_s0.yaml` … `gz_s9.yaml`. 8 m × 0.65 m corridor, one bay 0.8 m wide × 0.6 m deep on the +y side. Bay position cycles x = 1…7 m (seeds 7–9 repeat 1, 2, 3 m). B's start delay is drawn U(0, 8) s with the S1 seed rule (`10_000 + seed`). No packet loss; latency 0.05 s.
- Policies: `reactive`, `fixed_priority`, `rule_based` with `rulebooks/default.yaml` and with `rulebooks/proximity_first.yaml`, and `cost_bid`. That is 5 × 10 = 50 runs, listed in `gazebo/runs.txt`.
- Runner: `gazebo/run_one.sh`. Each run is one `amrneg` Docker container launching `corridor.launch.py`. Runs used separate `ROS_DOMAIN_ID`/`GZ_PARTITION` values so they could execute in parallel. Total Gazebo wall time was 2.3 h (mean 168 s per run).
- Comparison: `python studies/analyse_gazebo.py [GZSWEEP_DIR]` reruns each case in `sim2d` and writes `report/gazebo_sweep.json`. The Gazebo image was built from the S1–S6 code. The 2D reruns used main plus #5/#7, whose two-robot behaviour in this scenario matches.

## Results

| policy | n | Gazebo success | 2D success | Gazebo collisions | same yielder as 2D | makespan, Gazebo − 2D: mean (sd) | reverse distance, Gazebo / 2D (m) |
|---|---|---|---|---|---|---|---|
| cost_bid | 10 | 10 | 10 | 0 | 10 | −0.3 (0.1) s | 0.79 / 0.72 |
| fixed_priority | 10 | 10 | 10 | 0 | 10 | −0.4 (0.1) s | 1.15 / 1.09 |
| rules_default | 10 | 10 | 10 | 0 | 10 | −0.4 (0.1) s | 1.15 / 1.09 |
| rules_proximity | 10 | 10 | 10 | 0 | 10 | −0.4 (0.1) s | 0.81 / 0.74 |
| reactive | 10 | 8 | 9 | 1 | 5 | +8.5 (20.6) s | 7.09 / 7.05 |

- **Negotiating policies transfer.** All 40 negotiating runs succeeded in both simulators with the same yielder. Makespan agreed within 0.4 s, and reverse distance within about 0.07 m on average. In this scenario the 2D-sim conclusions of S1 (regret, reverse distance, policy ranking) carry over to Gazebo.
- **Reactive does not transfer run by run.** It agreed with 2D on the yielder in only 5/10 runs. Its back-off is randomised and sensitive to small timing differences, so only its statistics are comparable, not individual runs.
  - Gazebo had 2 failures out of 10: one deadlock and one collision (seed 4). 2D had 1 failure, a deadlock (seed 9).
  - Every reactive Gazebo run had negative minimum clearance, i.e. the 0.25 m-radius robot circles overlapped (mean −0.25 m). The negotiating runs stayed at about +0.1 m or more.
- **Caveats.**
  - The sample is 10 seeds, with one Gazebo run per seed and no comms impairment.
  - Gazebo runs are not bit-reproducible, because of physics and ROS scheduling.
  - Multi-robot (convoy, T-junction) and comms-loss cases have not been run in Gazebo yet.
