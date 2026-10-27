# Project hierarchy

The map of the repository. Every folder below has a `README.md` describing what is in it, and every README links
back here. For *what the project found*, read [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md). For a quick start, read
[`README.md`](README.md).

## Tree

```
AMR Negotiation/
├── README.md                    project intro, quick start, policies, Gazebo usage
├── PROJECT_OVERVIEW.md          detailed review: architecture, metrics, every experiment, results, open issues
├── PROJECT_HIERARCHY.md         this file
├── pyproject.toml               package metadata; installs the amrneg-run / amrneg-sweep / amrneg-world commands
│
├── amr_negotiation/             CORE PACKAGE: geometry, cost model, policies, agent state machine, 2D simulator
├── tests/                       pytest suite (core + LLM adapter)
│
├── configs/                     INPUTS
│   ├── scenarios/               6 corridor layouts and robot sets
│   ├── rulebooks/               2 rule orders for the rule-based policy
│   └── sweeps/                  2 demo Monte Carlo sweeps for amrneg-sweep
│
├── experiments/                 SCRIPTS THAT PRODUCED THE RESULTS
│   ├── classical/               2D studies S1–S10, reservation, convoy, T-junction, maps, explore, learned
│   ├── analysis/                raw CSVs -> markdown tables + figures
│   ├── gazebo/                  Gazebo scenario/run-list generators, Docker runners, Gazebo-vs-2D comparison
│   └── llm/                     LLM/VLM negotiator study + its batch drivers
│
├── data/                        RESULTS
│   ├── raw/                     source of truth, one row per episode
│   │   ├── classical/           14 × *.csv.gz (2D studies)
│   │   ├── gazebo/              2 × *.jsonl.gz (460-run batch, 36-run hold batch)
│   │   └── llm/                 ~55 run folders <tag>/{rows.jsonl, meta.json} + stage logs
│   └── tables/                  generated from raw/ (do not edit by hand)
│       ├── classical/           round-1 tables + figures, convoy/T-junction/maps/explore/learned/reservation/ablation
│       ├── classical_r2/        round-2 tables + figures (noise, comms stress, payments, fairness)
│       ├── gazebo/              per-run Gazebo-vs-2D CSVs + 460-run summary
│       └── llm/                 one llm_<tag>.md table per LLM run
│
├── reports/                     WRITE-UPS
│   ├── classical/               11 study reports, numbered in the order they were run
│   ├── gazebo/                  2 Gazebo validation reports
│   └── llm/                     index of the LLM runs (the write-up is paper 2)
│
├── papers/                      MANUSCRIPTS
│   ├── paper1_ral/              "Who Backs Into the Bay?" (classical policies, IEEE RA-L)
│   └── paper2_tase/             "Deliberation Costs" (LLM/VLM negotiators, IEEE T-ASE)
│
├── docs/                        literature review, LLM experiment plan, local-LLM how-to
├── ros2_ws/                     ROS 2 package: agent, referee and recorder nodes + launch file
├── docker/                      Gazebo/ROS 2 Docker image
└── media/                       videos
    ├── 2d_sim/                  2D-simulator replays (final code)
    ├── gazebo/                  first Gazebo clips (initial code)
    └── gazebo_final/            Gazebo clips on the final code
```

## Folder index

| Folder | What is available | README |
|---|---|---|
| `/` | Project intro, overview, this map, package metadata | [README.md](README.md) |
| `amr_negotiation/` | The 12-module Python package that every simulator and study uses | [README](amr_negotiation/README.md) |
| `tests/` | 46 test functions (47 pass, 3 skip without Gazebo/LLM server): geometry, rulebooks, bidding, Clarke, convoy, T-junction, maps, explore, LLM adapter | [README](tests/README.md) |
| `configs/` | All YAML inputs | [README](configs/README.md) |
| `configs/scenarios/` | Single bay, two bays, urgent/loaded, convoy, T-junction (exit, turn-in) | [README](configs/scenarios/README.md) |
| `configs/rulebooks/` | `default.yaml`, `proximity_first.yaml` | [README](configs/rulebooks/README.md) |
| `configs/sweeps/` | `bay_position.yaml`, `comms_loss.yaml` | [README](configs/sweeps/README.md) |
| `experiments/` | How to rerun anything | [README](experiments/README.md) |
| `experiments/classical/` | 9 study runners (paper 1) | [README](experiments/classical/README.md) |
| `experiments/analysis/` | 4 analysers + shared statistics helpers | [README](experiments/analysis/README.md) |
| `experiments/gazebo/` | Gazebo case generators, run lists, Docker runners, comparison scripts | [README](experiments/gazebo/README.md) |
| `experiments/llm/` | LLM study script + stage scripts (paper 2) | [README](experiments/llm/README.md) |
| `data/` | Layout and conventions for all results | [README](data/README.md) |
| `data/raw/` | Provenance of every raw file: episodes, seeds, commit, command | [README](data/raw/README.md) |
| `data/raw/classical/` | S1–S10, S8c, reservation, explore per-episode CSVs | [README](data/raw/classical/README.md) |
| `data/raw/gazebo/` | All Gazebo result JSONs, packed | [README](data/raw/gazebo/README.md) |
| `data/raw/llm/` | Per-episode LLM answers, reasoning traces, latencies | [README](data/raw/llm/README.md) |
| `data/tables/` | Generated tables and figures | [README](data/tables/README.md) |
| `data/tables/classical/` | Round-1 and extension-study tables | [README](data/tables/classical/README.md) |
| `data/tables/classical_r2/` | Round-2 tables and figures | [README](data/tables/classical_r2/README.md) |
| `data/tables/gazebo/` | Gazebo-vs-2D per-run tables and summary | [README](data/tables/gazebo/README.md) |
| `data/tables/llm/` | One results table per LLM run | [README](data/tables/llm/README.md) |
| `reports/` | Report index and caveats about canonical numbers | [README](reports/README.md) |
| `reports/classical/` | 11 study write-ups | [README](reports/classical/README.md) |
| `reports/gazebo/` | 2 Gazebo write-ups | [README](reports/gazebo/README.md) |
| `reports/llm/` | LLM run index by stage and model | [README](reports/llm/README.md) |
| `papers/` | Both manuscripts, status, Overleaf notes | [README](papers/README.md) |
| `papers/paper1_ral/` | Paper 1 source, figures, build, reviews | [README](papers/paper1_ral/README.md) |
| `papers/paper2_tase/` | Paper 2 source, figures, build, reviews | [README](papers/paper2_tase/README.md) |
| `docs/` | Literature review, LLM plan, local-LLM setup | [README](docs/README.md) |
| `ros2_ws/` | ROS 2 package `amr_negotiation_ros` | [README](ros2_ws/README.md) |
| `docker/` | Dockerfile and entrypoint | [README](docker/README.md) |
| `media/` | Video index | [README](media/README.md) |
| `media/2d_sim/` | 3 side-by-side 2D replays | [README](media/2d_sim/README.md) |
| `media/gazebo/` | 3 early Gazebo clips | [README](media/gazebo/README.md) |
| `media/gazebo_final/` | 10 Gazebo clips on the final code, with result JSONs | [README](media/gazebo_final/README.md) |

**Folders without their own README.** Each of these is covered by its parent's README:
- generated leaf folders: `data/raw/llm/<tag>/`, `experiments/gazebo/scen*/`, `fig/` folders;
- `papers/*/reviews/`, which has its own `SUMMARY.md`;
- the ROS package internals under `ros2_ws/src/`.

## How the pieces connect

```
configs/ ──► amr_negotiation/ (sim2d, agent, policies) ──► experiments/*  ──► data/raw/ ──► experiments/analysis ──► data/tables/
                     │                                        │                                                         │
                     └──► ros2_ws/ + docker/ (Gazebo) ◄───────┘ (experiments/gazebo)                                    ▼
                                                                                              reports/ (write-ups)   papers/ (canonical)
```
