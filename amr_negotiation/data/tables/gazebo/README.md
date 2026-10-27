[↑ Project hierarchy](../../../PROJECT_HIERARCHY.md) · [Parent: data/tables](../README.md)

# `data/tables/gazebo/`: Gazebo vs 2D

| File | Contents | Built by |
|---|---|---|
| `gazebo_all.md` | **The 460-run final-code summary**: per scenario kind × policy, Gazebo and 2D success, collisions, same first yielder, mean delays and their difference. Basis of paper 1's Gazebo table | `summarise_gazebo.py` |
| `gazebo_main_runs.csv` | Per run: the 122 original cases on the final code | `analyse_gazebo_main.py` |
| `gazebo_all_runs.csv` | Per run: the 338 all-study reduced-grid cases | `analyse_gazebo_main.py` |
| `gazebo_hold_runs.csv` | Per run: the hold-for-map batch (36) | `analyse_gazebo_main.py` |
| `gazebo_r2_runs.csv` | Per run: the round-2 batch on early code (convoy, T-junction, comms) | `analyse_gazebo_main.py` |
| `gazebo_sweep.json` | The first S1 sweep (50 runs, early code) vs 2D | `analyse_gazebo.py` |

The per-run CSV columns pair Gazebo (`gz_*`) and 2D (`d2_*`) values for one scenario, policy and seed:
- outcome: `success`, `deadlock`, `collision`;
- decision: `yielder`, `refuge`, `all_yielders`;
- maps: `map_first`, `detect_dist` (explore mode);
- `wdelay`, `makespan`, `reverse`, `min_clearance`;
- plus `code`, `kind`, `scenario`, `policy` and `seed`.

Scripts: [`experiments/gazebo/`](../../../experiments/gazebo/README.md). Raw runs:
[`data/raw/gazebo/`](../../raw/gazebo/README.md). Write-ups: [`reports/gazebo/`](../../../reports/gazebo/README.md).
