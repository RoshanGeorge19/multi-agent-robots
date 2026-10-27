[↑ Project hierarchy](../../PROJECT_HIERARCHY.md) · [Parent: data](../README.md)

# Raw per-episode results

Subfolders: [`classical/`](classical/README.md) (2D studies), [`gazebo/`](gazebo/README.md) (Gazebo runs) and [`llm/`](llm/README.md) (LLM runs). This page is the provenance record for the classical and Gazebo files.

One CSV row per simulated episode (S10: per encounter sequence / encounter). All files were produced on branch
`devin/1792011536-unified`, which merges PRs #15–#17 and #19–#21 onto `main`.

**Code version.** S8c, `reservation` and a check rerun of `experiments/classical/asym_map.py` ran at commit `07fd93f`; the other studies ran at
`338bcc2`. The only difference is that `07fd93f` adds protocol-ablation switches (`AgentParams.state_guard`, and gating of the
lidar bay check in `refuge_taken`) that default to on, so the default code path is unchanged. The `experiments/classical/asym_map.py` rerun at `07fd93f` gives byte-identical tables.

**Reproduce.** From the repo root with `PYTHONPATH=$PWD` (otherwise the editable install of another checkout may be
imported), run the command below and gzip the CSV. Reports: `python experiments/analysis/analyse.py OUT` (S1–S6),
`python experiments/analysis/analyse_r2.py OUT` (S7–S10), `python experiments/analysis/analyse_protocol.py` (S8c).

| File | Episodes | Seeds per cell | Command |
|---|---|---|---|
| `S10_encounters.csv.gz` | 1000 | — | `python experiments/classical/run_studies_r2.py OUT` |
| `S10_repeated.csv.gz` | 350 | — | `python experiments/classical/run_studies_r2.py OUT` |
| `S1_baseline.csv.gz` | 2940 | 60 | `python experiments/classical/run_studies.py OUT` |
| `S2_asymmetry.csv.gz` | 5040 | 30 | `python experiments/classical/run_studies.py OUT` |
| `S3_comms.csv.gz` | 3600 | 30 | `python experiments/classical/run_studies.py OUT` |
| `S4_two_bays.csv.gz` | 2520 | 20 | `python experiments/classical/run_studies.py OUT` |
| `S6_misreport.csv.gz` | 1080 | 60 | `python experiments/classical/run_studies.py OUT` |
| `S7_noisy_bids.csv.gz` | 3150 | 30 | `python experiments/classical/run_studies_r2.py OUT` |
| `S8_comms_stress.csv.gz` | 4320 | 20 | `python experiments/classical/run_studies_r2.py OUT` |
| `S8b_comms_extreme.csv.gz` | 1440 | 20 | `python experiments/classical/run_studies_r2.py OUT` |
| `S8c_protocol_ablation.csv.gz` | 5760 | 20 | `python experiments/classical/run_studies_r2.py OUT S8c_protocol_ablation` |
| `S9_payments.csv.gz` | 10080 | 60 | `python experiments/classical/run_studies_r2.py OUT` |
| `reservation.csv.gz` | 1260 | 30 | `python experiments/classical/reservation_baseline.py` |
| `explore_map.csv.gz` | 1440 | 30 | `python experiments/classical/explore_map.py` (explore-mode branch, after the unified version) |
| `gazebo_current.jsonl.gz` | 460 | n/a | Gazebo result JSON per run (`batch` `main@bf24bf4`: 122 original cases on main; `all@2ba4c6d`: 338 reduced-grid cases of every study). Runner `experiments/gazebo/run_case.sh` with cases from `experiments/gazebo/make_scen_all.py`; packed with `python experiments/gazebo/pack_raw.py`. Per-run comparison with 2D on the same seed: `data/tables/gazebo/gazebo_main_runs.csv`, `data/tables/gazebo/gazebo_all_runs.csv` (`experiments/gazebo/analyse_gazebo_main.py`); summary `data/tables/gazebo/gazebo_all.md` (`experiments/gazebo/summarise_gazebo.py`). |

**Conventions.**
- *Success* means every robot reached its goal before the episode timeout without a collision. A *deadlock* is a timeout without a collision. A *collision* is any overlap of the Waffle footprint rectangles.
- Delay means are over successful episodes only. Failed episodes are censored at the timeout and reported through the success, deadlock and collision rates, with Wilson 95% intervals. Zero counts are reported with their Wilson 95% upper bound.
- A seed fixes the random start delays and the comms noise (loss, jitter) of an episode. At 0% loss the negotiating policies are deterministic given the start delays, so the independent samples are the distinct (grid cell, seed) draws, and runs of different policies on the same draw are paired. Excess delay is computed per draw against the best forced yielder on that same draw.
- `oracle`/`oracle_w` rows are the best forced yielder (min over "A yields" and "B yields", total or urgency-weighted delay). They are not a globally optimal plan.
