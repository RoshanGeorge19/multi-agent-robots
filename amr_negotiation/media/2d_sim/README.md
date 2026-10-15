# 2D-sim videos

Side-by-side replays from the 2D simulator (`run_episode(..., record=True)`, drawn with `amr_negotiation.viz`), at 8x speed, with the panels in sync. Each panel shows its outcome and total delay when its run ends. They were rendered before the bid-cost fix, the Clarke pivot, reservation and explore mode, so their delays may differ from the final-code numbers in `studies/` and the paper.

| File | Scenario | Panels: policy (outcome) | Seed | Code commit |
|---|---|---|---|---|
| `corridor_policies_s3.mp4` (18 s) | `scenarios/corridor_single_bay.yaml` | `reactive` (119 s, 102 s delay); `fixed_priority` (63 s, 28 s); `rule_based`, `rulebooks/default.yaml` (63 s, 28 s); `cost_bid` (61 s, 24 s) | 3 | `fc0bf31` |
| `tjunction_convoy_s0.mp4` (26 s) | T-junction: `scenarios/corridor_tjunction_goal.yaml`, all `start_delay` 0, S `goal_x` -1.5, loss 0. Convoy: `scenarios/corridor_convoy.yaml`, bays at x = 4 and 8, B `start_delay` 0, C `start_delay` 2 | T-junction `fixed_priority` before #13 (deadlock, timeout) and after #13 (77 s, 63 s delay); convoy `cost_bid` (123 s, 132 s delay) and `group_bid` (88 s, 36 s delay). The convoy case was picked to show the gap; 36-run means are 56 s and 34 s | 0 | before #13: `fc0bf31`; after #13: `5ceee16`; convoy: `d473f51` |
| `blocked_bay_s0.mp4` (17 s) | `scenarios/corridor_two_bays.yaml`; blocked panels add `blocked_bays: [bay1]` | `cost_bid`, both bays free (76 s, 22 s delay); `cost_bid`, bay1 blocked (115 s, 68 s, falls back to its end room, no collision); `fixed_priority`, bay1 blocked (115 s, 68 s) | 0 | `e869f85` |
