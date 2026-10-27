[↑ Project hierarchy](../PROJECT_HIERARCHY.md) · [Repo README](../README.md)

# Experiments

Every script that produced the released results. Run all commands **from the repo root** after
`pip install -e .[dev]`. If another checkout's editable install might shadow this one, prefix them with
`PYTHONPATH=$PWD`.

```
experiments/
  classical/   2D-simulator studies (paper 1)        -> data/raw/classical/, data/tables/classical/
  analysis/    raw CSVs -> markdown tables + figures -> data/tables/classical*/
  gazebo/      Gazebo batch generation, runners, Gazebo-vs-2D comparison -> data/raw/gazebo/, data/tables/gazebo/
  llm/         LLM/VLM negotiator study (paper 2)    -> data/raw/llm/, data/tables/llm/
```

## [`classical/`](classical/README.md): 2D studies

| Script | Studies | Writes | Report |
|---|---|---|---|
| `run_studies.py OUT [names]` | S1 baseline, S2 asymmetry, S3 comms, S4 two bays, S6 misreport | `OUT/<study>.csv` (gzip into `data/raw/classical/` to release) | `reports/classical/01_round1_S1-S6.md` |
| `run_studies_r2.py OUT [names]` | S7 noisy bids, S8/S8b comms stress, S8c protocol ablation, S9 Clarke payments, S10 repeated encounters | `OUT/<study>.csv` | `reports/classical/02_…`, `04_clarke_payments.md` |
| `reservation_baseline.py [DATA]` | corridor-reservation baseline | `data/raw/classical/reservation.csv.gz`, `data/tables/classical/reservation.md` | `05_reservation_baseline.md` |
| `convoy_group.py` | convoy (2 v 1), `group_bid`, side-level reference | stdout (saved as `data/tables/classical/convoy_group.txt`) | `06_convoy_group_bid.md` |
| `tjunction_goal.py [out.txt]` | T-junction turn-in | stdout or `out.txt` (`tjunction_goal.txt`) | `07_tjunction.md` |
| `asym_map.py` | robots knowing different bays | stdout (`asym_map.txt`) | `08_asymmetric_maps.md` |
| `wrong_map.py` | bay on the map but physically blocked | stdout (`wrong_map.md`) | `09_blocked_bays.md` |
| `explore_map.py [OUT_CSV]` | explore mode, map sharing, hold-for-map | `data/raw/classical/explore_map.csv.gz` | `10_explore_mode.md` |
| `learned_negotiator.py` | tabular learned negotiator (train and evaluate) | `data/tables/classical/learned_negotiator.md`, `learned_table.json` | `11_learned_negotiator.md` |

`OUT` is any scratch folder, e.g. `results` (git-ignored). Most scripts hard-code `mp.Pool(8)`; raising this
speeds them up on bigger machines without changing results. For example, S1 (2,940 episodes) reruns in about 40 s and matches
`data/raw/classical/S1_baseline.csv.gz` row for row.

## [`analysis/`](analysis/README.md): tables and figures

| Script | Input | Output |
|---|---|---|
| `analyse.py OUT` | S1–S6 CSVs from `run_studies.py` | `OUT/results.md`, `OUT/fig/` (released copy: `data/tables/classical/`) |
| `analyse_r2.py OUT` | S7–S10 CSVs | `OUT/results_r2.md`, `OUT/fig/` (released: `data/tables/classical_r2/`) |
| `analyse_payments.py OUT` | `S9_payments.csv` | `OUT/payments.md` |
| `analyse_protocol.py [DATA]` | `data/raw/classical/S8c_protocol_ablation.csv.gz` | `data/tables/classical/protocol_ablation.md` |
| `analyse_helpers.py` | — | Shared statistics: CIs, Wilson intervals, pairing against the best forced yielder |

`analyse.py` and `analyse_r2.py` read uncompressed CSVs. To re-analyse the released data, gunzip
`data/raw/classical/*.csv.gz` into a scratch folder first.

## [`gazebo/`](gazebo/README.md): Gazebo validation (needs Docker and the `amrneg` image)

| File | Role |
|---|---|
| `scen/`, `scen_r2/`, `scen_all/` (+ `scen_all/pol/`) | Generated scenario YAMLs and per-run policy JSONs. Paths inside them point into the container (`/amr_negotiation/...`). |
| `runs.txt`, `runs_r2.txt`, `runs_all.txt`, `runs_hold.txt` | Run lists for each batch |
| `make_scen_r2.py`, `make_scen_all.py` | Regenerate the scenarios and run lists |
| `run_one.sh`, `run_case.sh` | Run one case in a container (`$GZSWEEP` holds `scen/` and `out/`) |
| `pack_raw.py` | Pack per-run result JSONs into `data/raw/gazebo/*.jsonl.gz` |
| `analyse_gazebo.py` | S1 sweep vs 2D → `data/tables/gazebo/gazebo_sweep.json` |
| `analyse_gazebo_main.py GZSWEEP_DIR [label [csv]]` | Each Gazebo run vs a 2D rerun on the same seed → `data/tables/gazebo/gazebo_*_runs.csv` |
| `summarise_gazebo.py` | → `data/tables/gazebo/gazebo_all.md` (the 460-run summary) |
| `analyse_hold.py` | Hold-for-map batch table |

Reports: `reports/gazebo/` and the Gazebo sections of `reports/classical/10_explore_mode.md`.

## [`llm/`](llm/README.md): LLM/VLM negotiators (needs an OpenAI-compatible server)

`llm_negotiation.py --tag TAG --model NAME --base-url URL --n 100 --variants ... --think 0|measured` runs paired
encounters (seeds 100000+). For each encounter it runs the baselines, the best forced yielder and the chosen LLM variants. It writes
`data/raw/llm/TAG/{rows.jsonl,meta.json}` and `data/tables/llm/llm_TAG.md`. The prompt cache (`cache.jsonl`) is
git-ignored. Server setup is in `docs/llm_local.md`.

The `stage*.sh` scripts, plus `orchestrate.sh`, `run_rest.sh` and `tail_offm.sh`, are the exact batch drivers used on the GB10 machine:
- they assume `./.venv`;
- they assume `~/.nemoclaw/local-models/serve.sh` for model switching;
- they assume `$NVIDIA_INFERENCE_API_KEY` for the hosted model.

Treat them as a record of what ran (stage plan: `docs/llm_experiments.md`), not as portable tooling. The run
index is in `reports/llm/README.md`.
