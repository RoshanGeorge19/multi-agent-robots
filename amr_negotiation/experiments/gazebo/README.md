[↑ Project hierarchy](../../PROJECT_HIERARCHY.md) · [Parent: experiments](../README.md)

# `experiments/gazebo/`: Gazebo validation batches

These scripts ran the ROS 2 Jazzy + Gazebo Harmonic runs and compared each one with a 2D run on the same seed.
Running them needs Docker and the `amrneg` image, built with `docker build -f docker/Dockerfile -t amrneg .`
(see [`docker/`](../../docker/README.md)).

## Workflow

1. **Generate cases.** `make_scen_r2.py` and `make_scen_all.py` write scenario YAMLs (`scen_r2/`, `scen_all/`), policy JSONs (`scen_all/pol/`) and run lists (`runs_r2.txt`, `runs_all.txt`). `scen/` and `runs.txt` hold the original S1 sweep. Paths inside these files are **container** paths (`/amr_negotiation/...`).
2. **Run.** Copy a `scen*` folder to `$GZSWEEP/scen`, then run each line of a run list:
   - `run_one.sh seed policy rulebook label [scenario]`, for `runs.txt` / `runs_r2.txt`;
   - `run_case.sh idx seed label scenario policy_file`, for `runs_all.txt` / `runs_hold.txt`.

   Each run is one container (about 3–5 min) and writes `$GZSWEEP/out/<label>/<scenario>_*.json`.
3. **Pack.** `pack_raw.py OUT.jsonl.gz DIR:TAG ...` packs the per-run JSONs into [`data/raw/gazebo/`](../../data/raw/gazebo/README.md).
4. **Compare and summarise:**
   - `analyse_gazebo.py [DIR]`: the S1 sweep vs 2D → `data/tables/gazebo/gazebo_sweep.json`.
   - `analyse_gazebo_main.py DIR [label [csv]]`: reruns every case in 2D on the same seed → `data/tables/gazebo/gazebo_*_runs.csv`.
   - `summarise_gazebo.py`: → `data/tables/gazebo/gazebo_all.md`, the 460-run summary.
   - `analyse_hold.py`: the hold-for-map batch table (prints).

| Batch | Cases | Run list | Scenarios |
|---|---|---|---|
| S1 sweep (early code) | 50 | `runs.txt` | `scen/` |
| Round 2: convoy, T-junction, comms | 72 | `runs_r2.txt` | `scen_r2/` |
| All studies, reduced grid (final code) | 362 listed; 460 runs in the final batch with the earlier cases | `runs_all.txt` | `scen_all/` |
| Hold-for-map | 36 | `runs_hold.txt` | `scen_all/` |

Write-ups: [`reports/gazebo/`](../../reports/gazebo/README.md) and the Gazebo sections of
[`reports/classical/10_explore_mode.md`](../../reports/classical/10_explore_mode.md).
