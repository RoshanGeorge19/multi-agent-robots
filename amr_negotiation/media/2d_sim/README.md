# 2D-sim videos

Side-by-side replays from the 2D simulator (`run_episode(..., record=True)`, drawn with `amr_negotiation.viz`), at 8x speed, with the panels in sync. Each panel shows its outcome and total delay when its run ends. All three were re-rendered on `main` at `c99270c` (the final code of the paper: bid-cost fix, Clarke pivot, reservation, explore mode). Their outcomes are identical to the earlier renders on older code, because none of these cases uses unequal urgencies, payments or exploration.

| File | Scenario | Panels: policy (outcome) | Seed | Code commit |
|---|---|---|---|---|
| `corridor_policies_s3.mp4` (18 s) | `configs/scenarios/corridor_single_bay.yaml` | `reactive` (119 s, 102 s delay); `fixed_priority` (63 s, 28 s); `rule_based`, `configs/rulebooks/default.yaml` (63 s, 28 s); `cost_bid` (61 s, 24 s) | 3 | `c99270c` |
| `tjunction_convoy_s0.mp4` (18 s) | T-junction: `configs/scenarios/corridor_tjunction_goal.yaml`, all `start_delay` 0, S `goal_x` -1.5, loss 0. Convoy: `configs/scenarios/corridor_convoy.yaml`, bays at x = 4 and 8, B `start_delay` 0, C `start_delay` 2 | T-junction `fixed_priority` (77 s, 63 s delay) and `cost_bid` (77 s, 63 s); convoy `cost_bid` (123 s, 132 s delay) and `group_bid` (88 s, 36 s). The convoy case was picked to show the gap; 36-run means are in `studies/`. The earlier render's "before #13 deadlock" panel is gone, since that code is no longer on `main` | 0 | `c99270c` |
| `blocked_bay_s0.mp4` (17 s) | `configs/scenarios/corridor_two_bays.yaml`; blocked panels add `blocked_bays: [bay1]` | `cost_bid`, both bays free (76 s, 22 s delay); `cost_bid`, bay1 blocked (115 s, 68 s, falls back to its end room, no collision); `fixed_priority`, bay1 blocked (115 s, 68 s) | 0 | `c99270c` |
