# AMR Negotiation: project overview

*A reviewer's guide to the repository. Written 2026-10-27 against upstream commit `876e896`, then updated for the restructured layout (`configs/`, `experiments/`, `data/`, `reports/`, `papers/`) and the per-folder documentation. All changes are listed in §15. Paths are relative to the project root. On the fork, that root is `amr_negotiation/`.*

**Navigation:**
- [`README.md`](README.md): quick start;
- [`PROJECT_HIERARCHY.md`](PROJECT_HIERARCHY.md): map of every folder, with links to its README;
- this file: what the project is and what it found.

---

## 1. TL;DR

- **The question.** Two autonomous mobile robots (TurtleBot3 Waffles) meet head-on in a single-lane corridor that only one can use. One of them must reverse into a pull-in bay or back out to an end room. **Who should yield, into which refuge, and how should the robots agree?**
- **What the repo is.** A research benchmark plus the experiments and papers built on it:
  - one simulator-agnostic agent state machine (`amr_negotiation/agent.py`);
  - a fast 2D Monte Carlo simulator;
  - a ROS 2 Jazzy + Gazebo Harmonic stack running the same agent code;
  - 10 decision policies (reactive, fixed priority, rulebook, reservation, cost bidding, group bidding, Clarke/VCG, learned, LLM/VLM, forced);
  - roughly 20 studies with released per-episode data;
  - two IEEE manuscript drafts.
- **Scale of evidence.**
  - Classical policies: about 50,000 2D episodes.
  - Gazebo: 460 runs paired by seed with 2D, plus a 36-run hold-mode batch.
  - LLM/VLM study: 9 models, about 60 run directories, 200 paired encounters per main arm.
- **Headline results.**
  1. Communication is cheap insurance. Without it, the reactive baseline deadlocks in about 6% of episodes and has at least 3.6× the reference delay. Every negotiating policy succeeds in 100% of episodes.
  2. Cost bidding matches the hindsight "best forced yielder" reference when its cost model is right. It loses that edge at log-normal bid noise σ ≈ 0.5, and it can be gamed unless Clarke (VCG) payments are added.
  3. The protocol never collided on the final code, even at 90–99% packet loss.
  4. 2D yield decisions transfer to Gazebo in 96.8% of negotiating runs. T-junction delays do not transfer.
  5. Reasoning-enabled LLM mediators *beat* the reference at zero decision cost (−1.0 to −1.7 s excess). Real inference latency costs about 3.4 s of excess per second of latency, so cost bidding still dominates in practice. Decentralised LLM agents fail mainly because they disagree.
- **Status.**
  - Both papers have been through 3 rounds of adversarial review, each ending with a MINOR verdict.
  - The test suite passes (47 passed, 3 skipped).
  - The repository has been reorganised by role, and every folder has a README (§2.3, §15).
  - A rerun of S1 from the new layout reproduces the released data row for row.
  - Remaining pre-submission work: the artifact URL/DOI, release of a few datasets, removal of the draft annotations, and the open items in §12.

---

## 2. Repository provenance and layout

### 2.1 Where this code comes from

- **Upstream.** `briandeegan82/multi-agent-robots` on GitHub. That repo is itself a fork of `johannapinard/multi-agent-robots`. `amr_negotiation/` is one subdirectory of a larger monorepo.
- **The local repo** (`/home/roshan/Claude/Projects/AMR Negotiation`) is a `git subtree split` of just that subdirectory, so its paths are flattened: the repo root here is `amr_negotiation/` upstream.
- **Where the current version lives.**

  | Copy | Location | Commit | Layout |
  |---|---|---|---|
  | Local repo | branch `main` (merged from `restructure`) | see `git log` | flattened: the project is the repo root |
  | Your fork, `RoshanGeorge19/multi-agent-robots` | branch `main` | `876e896` → `076c623` (restructure) → `11684c6` (READMEs) → this update | monorepo: the project is in `amr_negotiation/`, next to `IsaacSim/` etc. |
  | Original, `briandeegan82/multi-agent-robots` | branch `main` | `876e896`, unchanged | old layout |

  The fork and the local repo hold **identical project contents** but **different histories**: the local repo is a `git subtree split`. So never `git push` the local `main` to the fork. Changes reach the fork as one commit that replaces `amr_negotiation/` with the local tree (`git read-tree --prefix=amr_negotiation/ -u <branch>` on a branch from the fork's `main`). Pushing happens only on an explicit request.
- **Branch `restructure`** reorganised the flattened repo into the layout in §2.3. Every file was moved with `git mv`, so `git log --follow` still traces history. The old-to-new mapping is:

  | Old location | New location |
  |---|---|
  | `scenarios/`, `rulebooks/`, `sweeps/` | `configs/` |
  | `studies/*.py` | `experiments/{classical,analysis,llm}/` |
  | `studies/gazebo/` | `experiments/gazebo/` |
  | `studies/results_raw/` | `data/raw/{classical,gazebo,llm}/` |
  | `studies/report*/` | `data/tables/` |
  | `studies/REPORT*.md` | `reports/` |
  | `paper/`, `paper2/` | `papers/paper1_ral/`, `papers/paper2_tase/` |

  Pulling future upstream changes in will need those renames resolved, because the original repo still uses the old layout.
- **Authorship.** Commits touching `amr_negotiation/` run from 2026-10-14 to 2026-10-24. Almost all are by Brian Deegan, much of it through Devin agent branches (`devin/*`). The papers list Roshan George, Martin Glavin, Edward Jones and Brian Deegan (CAR group, University of Galway).

### 2.2 Monorepo siblings (not part of the negotiation project)

| Path | What it is |
|---|---|
| `../IsaacSim/` | IsaacLab 3.0 RL training of a rover and an XGO quadruped in mazes. It has its own LLM experiments (LLM reward design, LLM coordinator). `../FIXES.md` documents 19 IsaacLab 3.0 porting fixes. |
| `../multi_agents_ws/` | A ROS 2 workspace with `communication_msgs`. Its `build/`, `install/` and `log/` directories are committed. |
| `../Dockerfile` | A ROS Jazzy image for a "Wave-Rover" base layer. **Not** the negotiation image. Use `docker/Dockerfile` in this repo instead. |

These siblings exist in the monorepo (upstream and your fork). The local repo contains just the negotiation project.

### 2.3 Repository layout

**Every folder has its own README** describing what is in it: files, row counts and columns for data, and inputs/outputs for scripts. Each README opens with a link back to [`PROJECT_HIERARCHY.md`](PROJECT_HIERARCHY.md) and to its parent. The hierarchy is the full map: a tree, an index of all 35 folder READMEs, and a diagram of how the pieces connect.

```
README.md                  intro, quick start, policies, Gazebo usage, limitations
PROJECT_OVERVIEW.md        this file
PROJECT_HIERARCHY.md       folder map with links to every README
pyproject.toml             package metadata; installs amrneg-run / amrneg-sweep / amrneg-world
amr_negotiation/           core Python package (≈2.6k LOC)
  geometry.py              Scenario, RobotSpec, Refuge, AgentConfig; corridor/bay/room geometry; footprint SAT collision test
  planner.py               Snapshot (what a robot broadcasts), refuge feasibility, constant-speed yield-plan timeline & cost
  policies.py              decision functions: rulebook rules, cost_bid, group_bid, learned, clarke, forced, dispatcher
  mechanism.py             Clarke-pivot (VCG) mechanism for the two-outcome yield decision
  agent.py                 the agent state machine (≈850 LOC): CRUISE / NEGOTIATE / YIELD / PROCEED / DONE + safeguards
  llm.py                   LLM/VLM negotiator over any OpenAI-compatible endpoint (mediator & agents modes, images, tiebreaks)
  sim2d.py                 2D unicycle simulator, lossy broadcast bus, free-flow times, run_episode / run_oracle
  sweep.py, cli.py         `amrneg-sweep` (factorial Monte Carlo → CSV + plots) and `amrneg-run` (single episode)
  gzworld.py, viz.py       Gazebo world/bridge generator (`amrneg-world`); plots and GIFs
ros2_ws/src/amr_negotiation_ros/   agent_node, referee_node, recorder_node, corridor.launch.py
docker/                    Dockerfile + entrypoint for the Gazebo stack
configs/                   YAML inputs: scenarios/ (6 layouts), rulebooks/ (2), sweeps/ (2 demo sweeps)
tests/                     test_core.py (core + agent behaviour), test_llm.py (fake LLM server)
experiments/
  classical/               2D study runners (S1–S10, reservation, convoy, T-junction, maps, explore, learned)
  analysis/                raw CSV -> tables + figures (analyse*.py, shared stats helpers)
  gazebo/                  Gazebo scenario/run-list generators, Docker runners, Gazebo-vs-2D analysers
  llm/                     llm_negotiation.py + the stage*.sh batch drivers used on the GB10
data/
  raw/                     per-episode results (classical/*.csv.gz, gazebo/*.jsonl.gz, llm/<tag>/rows.jsonl) + provenance README
  tables/                  generated tables/figures (classical/, classical_r2/, gazebo/, llm/)
reports/                   13 study write-ups (classical/01–11, gazebo/01–02) + LLM run index; README lists caveats
docs/                      literature_review.md (126 refs), llm_experiments.md (LLM plan), llm_local.md (GB10/llama.cpp how-to), references.bib
papers/paper1_ral/         Paper 1 (RA-L letter): main.tex, main.pdf, fig/, make_figures.py, reviews/
papers/paper2_tase/        Paper 2 (T-ASE): main.tex, main.pdf, fig/, make_figures.py, reviews/
media/                     Gazebo and 2D videos (mp4 + webp previews) with provenance READMEs
```

---

## 3. Research purpose

According to the literature review (`docs/literature_review.md` §6), work on corridor conflicts uses three main approaches:

- **Reactive collision avoidance** (ORCA, CBF). This deadlocks in symmetric head-on configurations.
- **Centralised planners and traffic managers** (MAPF, Open-RMF, zone control). These need a global plan.
- **Decentralised negotiation.** This has many proposals (rules, auctions, MARL, LLM dialogue), but every paper builds its own scene and its own metrics.

The project targets three gaps identified there:

1. **No common benchmark.** There is no shared benchmark or metric set for robot-robot head-on negotiation with refuges.
2. **No head-to-head comparison.** Rules, bidding, mechanisms, learning and LLMs have never been compared under the same physics and communication model, including latency and packet loss.
3. **Refuge selection is under-studied.** This covers refuge choice with a reversing cost, asymmetric private costs, incentive compatibility (misreporting), and fairness over repeated encounters.

Paper 2 extends this to the open question of whether **foundation models (LLMs/VLMs)** can act as the negotiator, and what that costs.

---

## 4. System architecture

### 4.1 One agent, two simulators

`Agent.step(t, pose, perception, inbox)` returns `(v, w, outgoing_msgs)`. The same class runs in two hosts:

- **`sim2d`.** A forward-Euler unicycle simulator at dt = 0.05 s (20 Hz) with Waffle limits:
  - speed: 0.26 m/s forward, 0.15 m/s reverse;
  - turn rate: 1.82 rad/s;
  - acceleration: 0.5 m/s² linear, 3 rad/s² angular.

  The lidar is idealised: peers within 3.5 m appear as 0.25 m circles, with no occlusion. Collision is a separating-axis overlap of the 0.281 × 0.306 m body rectangles. Thousands of episodes run per minute.
- **ROS 2 Jazzy + Gazebo Harmonic** (Docker):
  - `gzworld` generates the SDF world: corridor walls, bays and one inlined TurtleBot3 Waffle per robot.
  - `agent_node` runs on each robot. Pose comes from ground truth. The lidar scan is projected into the world frame, points on the known walls are removed, and the remaining points are clustered into peers.
  - Bus messages are JSON on `/amr_negotiation/bus`, with emulated latency and loss.
  - `referee_node` writes a result JSON with the same keys as `sim2d`.
  - A Gazebo run takes about 3–5 min.

### 4.2 Protocol

1. **STATE broadcasts.** Every robot broadcasts STATE at 5 Hz. A STATE message counts as fresh for 1 s after receipt.
2. **Conflict detection.** A conflict exists when an oncoming peer's STATE puts it within the **detection range** (6 m by default). Detection uses radio, not lidar.
3. **BID exchange.** Each robot sends a **BID** carrying a frozen `Snapshot`: x, dir, v, goal, corridor-entry time, urgency, loaded flag and speed limits. Optionally a BID also carries known bays, blocked bays and convoy followers. BIDs are resent every 0.3 s.
4. **Local decision.** Each robot runs `policies.decide(policy, [mine, theirs], scenario)` locally. The function is deterministic, so both robots reach the same decision without a third message.
5. **Safeguards.** Each can be switched off for ablation (`AgentParams`):
   - `commit`: act only once the peer's decision is held; the lower ID wins a mismatch; an unconfirmed decision expires after 3 s.
   - `state_guard`: a peer's STATE showing it yielding into the same refuge, or yielding to us, makes us proceed instead.
   - `bay_check`: a bay the lidar shows occupied counts as taken.
6. **Fallbacks.**
   - No BID within `neg_timeout` = 3 s: act reactively.
   - The yielder has not left the lane within 60 s: proceed timeout.
   - No feasible refuge: back off from that peer for 10 s.
7. **Later extensions.**
   - `make_room`: a follower backs out for its convoy leader.
   - Junction-aware `goal_wait`.
   - Obstructed-bay detection (`refuge_blocked`).
   - Map sharing: `share_map`, `share_on_detect`, `hold_for_map`.
   - `explore` mode: bays are discovered within lidar range.

### 4.3 Cost model (`planner.py`)

- **What a plan is.** A plan is "robot Y pulls into refuge R so that P can pass".
- **The timeline.** Constant-speed and transient-free:
  - Y drives (forward or in reverse) to R, turns, and parks;
  - P holds at `hold_x`, then passes `pass_x`;
  - Y exits and continues.
- **Outputs.** `yielder_delay`, `proceeder_delay`, `total_delay`, `weighted_delay = u_Y·d_Y + u_P·d_P`, makespan and reverse distance.
- **Who uses it.** `best_plan` picks the feasible refuge with the least *unweighted* total delay. Cost bidding, group bidding, the Clarke mechanism, the LLM `plans` prompt and the rulebook's refuge choice all use this same model.

---

## 5. Scenarios (`configs/scenarios/*.yaml`)

| Scenario | Geometry | Robots |
|---|---|---|
| `corridor_single_bay` | 8 m × 0.65 m corridor, one 0.8 × 0.6 m bay (default x = 4), 2.5 m end rooms | A (t=0) vs B (delay 2 s; in studies U[0,8] s) |
| `corridor_two_bays` | 10 m, bays at x=3 (north) and x=7 (south) | A vs B |
| `corridor_urgent_loaded` | as single bay | B urgent (u=2) and loaded |
| `corridor_convoy` | 10 m, two bays, `despawn_done` | A and C eastbound in convoy vs B |
| `corridor_tjunction` | 8 m, the stem is modelled as a 2 m-deep bay at x=5.5 | A, B, and S leaving the stem |
| `corridor_tjunction_goal` | as above | A turns *into* the stem, B passes, S leaves |

- **Overrides.** Any field can be overridden with `--set key.path=value`, e.g. `bays.0.x=2.5` or `comms.loss=0.3`.
- **Comms model.** Fixed latency, plus uniform jitter, plus independent per-receiver loss. The default is 0.05 s latency, 0.02 s jitter and 0% loss.

---

## 6. Policies (`policies.py`, `llm.py`, `sim2d.run_oracle`)

| Policy | Messages | Decision rule |
|---|---|---|
| `reactive` | none | Stop when blocked. After a random patience in U[2,6] s, back up to the nearest refuge behind. Baseline for deadlock and livelock. |
| `fixed_priority` | STATE + BID | The higher ID always yields. |
| `rule_based` | STATE + BID | Ordered rulebook; the first discriminating rule decides. The default order is `no_refuge` → `urgency` (gap ≥ 0.5) → `loaded` → `first_in_corridor` (≥ 1 s) → `refuge_behind_within` (2 m) → `lower_id_priority`. A variant (`proximity_first.yaml`) puts `closest_refuge` before seniority. |
| `reservation` | STATE | First come, first served on the corridor. A robot outside the corridor waits in its end room while an oncoming robot is inside. If both are inside, the rulebook decides. |
| `cost_bid` | STATE + BID | Each side's bid is the predicted urgency-weighted social cost if it yields. The lower bid yields. Optional log-normal noise `bid_sigma`. |
| `group_bid` | STATE + BID | Like `cost_bid`, but each side's cost covers its convoy followers and the proceeding side's followers. |
| `clarke` | STATE + BID | VCG/Clarke pivot. The outcome is the argmin of summed reported costs. Each robot pays its externality to a bank. `report_scale` simulates misreports. |
| `learned` | STATE + BID | Tabular contextual bandit over a coarse observation (binned refuge-behind distance per robot, urgency order, load flags). Trained centrally on 800 encounters by running both forced outcomes. Unseen states fall back to fixed priority. |
| `llm` | STATE + BID | An LLM/VLM picks the yielder. `mediator` mode makes one call that sees both robots. `agents` mode makes one call per robot ("yield"/"proceed"). Inputs are `raw` or `plans` (planner delays added), with optional global or egocentric image. Tiebreak on disagreement: rulebook (default), hidden or visible hash draw, or commit-reveal. Latency can be charged as frozen decision time. |
| `forced` | STATE + BID | A named robot yields. Used to build the reference. |
| `oracle` / `oracle_w` | — | **Best forced yielder**: run "A yields" and "B yields" with the planner's refuge and keep the better result for total (or urgency-weighted) delay. A hindsight reference, *not* a global optimum. A policy can beat it by choosing a better refuge or timing. |

---

## 7. Metrics and statistics

### 7.1 Per-episode metrics (`sim2d.run_episode`, `sweep.COLUMNS`)

| Metric | Definition |
|---|---|
| `success` | Every robot reached its goal within `t_max` = 180 s, with no collision. |
| `deadlock` | Timeout without collision. |
| `collision` | The Waffle body rectangles overlap (SAT test). In the blocked-bay study, being within 0.5 m of the obstacle also counts. |
| `makespan` | Arrival time of the last robot. |
| `total_delay` | Σ_i (T_i − T_i^free), where T_i^free is the robot's travel time with the corridor to itself (cached single-robot run). |
| `max_delay` | max_i (T_i − T_i^free). |
| Urgency-weighted delay | Σ_i u_i (T_i − T_i^free). |
| `min_clearance` | Minimum axle-to-axle distance minus 2 × swept radius. It can go negative without contact. |
| `reverse_dist` | Metres driven in reverse (summed). |
| `n_yields`, `yielder`, `refuge`, `rule` | Who yielded, where, and which rule decided. |
| `msgs`, `msgs_dropped` | Bus traffic. |
| `time_to_decide` | First decision time minus conflict detection time. |
| `agreement` | Both robots reached the same (yielder, refuge). |
| `wall_hits` | Sanity check on wall clearance. |

### 7.2 Derived metrics

- **Excess delay**, Δπ = mean_k [D_π^(k) − min(D_A^(k), D_B^(k))]. It is paired per encounter against the best forced yielder. The reports call this "regret"; the paper avoids that word.
- **Same / reference-yielder rate.** The share of encounters whose first decision names the reference's yielder. Paper 2 excludes ties, where the two forced outcomes are within 0.5 s.
- **Jain's fairness index** on the two robots' (cumulative) delays.
- **Mechanism metrics** (S9): the deviator's gain, defined as utility (−weighted delay − payment) minus truthful utility; bank surplus; joint-collusion gain.
- **LLM metrics:**
  - fallback fraction, by error, parse failure, disagreement or infeasibility;
  - charged think time;
  - disagreement mode (both-yield or both-proceed);
  - latency slope (s of excess per s of latency).
- **Gazebo transfer metrics:** same first yielder as 2D, and the Gazebo − 2D delay difference per paired run.

### 7.3 Statistical conventions (`data/raw/README.md`)

- **Intervals.** Means carry 95% confidence intervals. Rates carry Wilson 95% intervals. A zero count is reported with its 95% upper bound.
- **Delays.** Delays are averaged over **successful episodes only**. Failures are reported through success, deadlock and collision rates. For a failing policy the mean delay is therefore a lower bound.
- **Independent samples.** A seed fixes the start delays and the comms noise. At 0% loss the negotiating policies are deterministic given the draw, so the independent samples are the distinct (cell, seed) draws, and different policies are compared on the same draws.
- **Paper 2 statistics.** Paired-t intervals plus Wilcoxon signed-rank tests on per-encounter differences.

---

## 8. Experiment catalogue

### 8.1 Classical-policy studies (2D)

| ID | Question | Grid (summary) | Episodes | Script → raw data | Report |
|---|---|---|---|---|---|
| S1 | Price of no comms; price of decentralisation; bay position | bay x ∈ {1..7} m × 60 seeds; R, F, D, P, C, O, O_w | 2,940 | `experiments/classical/run_studies.py` → `S1_baseline.csv.gz` | `reports/classical/01_round1_S1-S6.md` |
| S2 | Rulebook vs bidding with asymmetric robots | u_B ∈ {1,3} × loaded × v_B ∈ {0.26, 0.13} × bay {2,4,6} × 30 | 5,040 | `S2_asymmetry.csv.gz` | `reports/classical/01_round1_S1-S6.md`, `reports/classical/03_bid_cost_fix.md` |
| S3 | Packet loss × latency | loss 0–90% × latency 0.05–2 s × 30 | 3,600 | `S3_comms.csv.gz` | `reports/classical/01_round1_S1-S6.md` |
| S4 | Two bays | bay1 {2,3,4} × bay2 {6,7,8} × side × 20 | 2,520 | `S4_two_bays.csv.gz` | `reports/classical/01_round1_S1-S6.md` |
| S5 | Fairness (from S1) | — | — | — | `reports/classical/01_round1_S1-S6.md` |
| S6 | Misreporting under lower-bid-yields | B bid × k ∈ {1,1.5,2,4,10} × bay {2,4,6} × 60 | 1,080 | `S6_misreport.csv.gz` | `reports/classical/01_round1_S1-S6.md` |
| S7 | Noisy bids | σ ∈ {0,0.1,0.25,0.5,1} × bay {1..7} × 30 | 3,150 | `experiments/classical/run_studies_r2.py` → `S7_noisy_bids.csv.gz` | `reports/classical/02_round2_S7-S10.md` |
| S8 | Comms stress | detection {6,3,1.5} m × speed {0.26,0.5} × loss {0,50,90}% × latency {0.05,0.5,2} s × 20 | 4,320 | `S8_comms_stress.csv.gz` | `reports/classical/02_round2_S7-S10.md` |
| S8b | Extreme comms | detection {1.5,6} × loss {90,97,99}% × latency {2,4,8} s, 0.5 m/s | 1,440 | `S8b_comms_extreme.csv.gz` | `reports/classical/02_round2_S7-S10.md` |
| S8c | Safeguard ablation | S8b grid × commit × state guard × bay check | 5,760 | `S8c_protocol_ablation.csv.gz` | `data/tables/classical/protocol_ablation.md` |
| S9 | Clarke-pivot payments vs misreports | deviator A/B/both × 10 k values × u_B {1,3} × bay {2,4,6} × 60 | 10,080 | `S9_payments.csv.gz` | `reports/classical/04_clarke_payments.md` |
| S10 | Repeated-encounter fairness | 50 sequences × 20 encounters; rules applied offline to measured costs | 2,000 | `S10_*.csv.gz` | `reports/classical/02_round2_S7-S10.md` |
| Res. | Corridor-reservation baseline | bay {1..7} × 30 | 1,260 | `experiments/classical/reservation_baseline.py` → `reservation.csv.gz` | `reports/classical/05_reservation_baseline.md` |
| Convoy | 2 v 1 convoy, `group_bid`, make-room | B type × bays × delay × loss {0,50}% × 3 seeds | 1,080 | `experiments/classical/convoy_group.py` (rows not released) | `reports/classical/06_convoy_group_bid.md` |
| T-junc. | Turning into / leaving a side branch | start delays × S goal × loss × 2 seeds | 384 | `experiments/classical/tjunction_goal.py` (rows not released) | `reports/classical/07_tjunction.md` |
| Maps | Asymmetric map knowledge, map sharing | 7 knowledge conditions × share × loss × 10 | 840 | `experiments/classical/asym_map.py` | `reports/classical/08_asymmetric_maps.md` |
| Blocked | Bay on map but physically blocked | blocked set × policy × loss × 10 | 320 | `experiments/classical/wrong_map.py` | `reports/classical/09_blocked_bays.md` |
| Explore | Map-as-you-go, share-on-detect, hold-for-map | 4 map conditions × range {6, 3.5} × loss × 30, plus a hold arm | 1,440 + 360 | `experiments/classical/explore_map.py` → `explore_map.csv.gz` | `reports/classical/10_explore_mode.md` |
| Learned | Tabular negotiator, in and out of distribution | train 800; evaluate 150 per layout | 1,600 + 1,500 | `experiments/classical/learned_negotiator.py` | `reports/classical/11_learned_negotiator.md` |

Policy letters follow paper 1, Table I: R reactive, F fixed priority, D default rulebook, P proximity rulebook, S reservation, C cost_bid, G group_bid, V Clarke, L learned, O/O_w best forced yielder.

### 8.2 Gazebo studies

| Batch | Runs | Content | Report |
|---|---|---|---|
| S1 sweep (early code) | 50 | 5 policies × 10 seeds, single bay | `reports/gazebo/01_s1_sweep.md` |
| Round 2a/2b (early code) | 72 + 36 | convoy, T-junction (exit and turn-in), lossy comms | `reports/gazebo/02_round2_convoy_tjunction_comms.md` |
| **Final code, all studies** | **460** | reduced grid of every study, 6–10 seeds, each run paired with 2D | `data/tables/gazebo/gazebo_all.md`, `data/raw/gazebo/gazebo_current.jsonl.gz` |
| Hold-for-map | 36 | share-on-detect ± hold, 3.5 and 6 m | `reports/classical/10_explore_mode.md`, `data/raw/gazebo/gazebo_hold.jsonl.gz` |

### 8.3 LLM/VLM studies (paper 2)

- **Setup.**
  - Script: `experiments/llm/llm_negotiation.py`.
  - Encounters: seeds 100000–100099, 100 per layout (single bay, two bays), giving 200 paired encounters. Arms run at 25 encounters per layout use seeds 100000–100024.
  - Serving: local vLLM on an NVIDIA GB10 (NVFP4), plus the hosted `nemotron-3-super-120b`.
- **Stage scripts.** `experiments/llm/stage{1,2,2b,2c,4,5,6,7}_*.sh`, one per arm of the plan in `docs/llm_experiments.md`. They record what ran on the GB10 and are not portable tooling.
- **Run index.** [`reports/llm/README.md`](reports/llm/README.md) maps every run tag to its stage, model and settings, and lists the runs paper 2 excludes.
- **Outputs.**
  - `data/raw/llm/<tag>/{rows.jsonl, meta.json}`; `cache.jsonl` is git-ignored.
  - `data/tables/llm/llm_<tag>.md`.
- **Run-tag suffixes:**
  - `-c1..c4`: config matrix (stage 2);
  - `-on0/-off0`: thinking on/off at zero cost;
  - `-onm/-offm`: measured latency; `-s` means serial;
  - `-vlm`: global-image arms;
  - `-ego`: egocentric agents;
  - `-nonce`: visible draw (rule and cards in the prompt);
  - `-silent`: hidden draw (prompt unchanged);
  - `-commit`: commit-reveal draw.

| Stage | Arm | n |
|---|---|---|
| 1. Screen | 9 models, mediator + plans, `think=0`, default reasoning setting | 200 |
| 2. Matrix | top models × mode × info × reasoning × cost mode | 200 (off), 50 (on) |
| 2c. Measured latency | serial vs concurrent, thinking on/off | 50 / 200 |
| 4. Vision | text+plans vs image-only vs image+raw-text (4 VL models) | 200 |
| 5. Egocentric | decentralised agents with egocentric image | 200 |
| 6–7. Tiebreak | rulebook vs hidden draw vs visible draw; commit-reveal | 200 |

Muse-Glimmer-30B failed to load. Several runs are excluded in the paper because of server errors or connection resets: the hosted model outside the screen, `qwen3.8-27b-offm`, `-c2/c4`, and `qwen3-30b-c1..c4`.

---

## 9. Key results: classical policies (2D)

These numbers are the **paper 1 values on the final code**. Some reports in `reports/` are earlier snapshots and differ slightly; see §12.

### 9.1 Two robots, one corridor

| Policy | Success | Excess delay vs best forced yielder | Notes |
|---|---|---|---|
| reactive | 93.8% [91–96] | total delay 97 ± 5 s vs 26.8 s for the reference (≥ 3.6×) | Reverses 5.7 m vs 0.64 m. Both robots back off in 39% of episodes. |
| fixed priority = default rulebook (symmetric robots) | 100% | 6.4 ± 0.6 s (14.6–14.8 s with the bay 2–3 m from A's entrance) | Sends the late robot B back past the bay. |
| proximity-first rulebook | 100% | 3.1 ± 0.5 s | |
| reservation | 100% | 18.8 ± 0.9 s | Never beats the reference (0/210). B must pull off A's exit path. |
| cost_bid | 100% | 0 (picks the reference yielder in every S1/S4 episode) | Predicted-vs-realised error 1.9 s per robot. This validates the implementation rather than showing a robust advantage. |

### 9.2 Asymmetric robots (S2)

Urgency-weighted excess delay:

| Policy | Weighted excess | Same yielder as `oracle_w` |
|---|---|---|
| fixed priority | 27.1 ± 2.6 s | |
| default rulebook | 3.5 ± 0.4 s | |
| cost_bid (after the urgency-weighting bug fix) | **0.04 ± 0.02 s** | 98% |
| unweighted oracle | 7.0 ± 1.5 s | |

The choice of objective matters as much as the protocol.

### 9.3 Noisy bids (S7)

Excess delay of cost_bid as bid noise grows:

| σ | Excess |
|---|---|
| 0.1 | 0.2 s |
| 0.25 | 1.5 s |
| 0.5 | 3.3 s |
| 1.0 | 4.5 s |

At σ = 0.5, bidding is no better than the noise-free closest-refuge rule (3.2 s on the same draws).

### 9.4 Incentives (S6, S9)

- **Lower-bid-yields** is manipulable. If B inflates its bid by 2× or more, B never yields and total delay rises by 4.9 s (+20%).
- **The naive transfer rule** is also gameable: A gains 7.5 s by reporting 0.25× its cost.
- **The Clarke pivot** removes every profitable unilateral misreport under predicted costs. Under realised delays the largest gain is 0.02 s.
- **Clarke's cost:**
  - the bank collects 9.3–10.5 s of credit per encounter (not budget balanced);
  - joint ×0.5 shading pays 4.9 s (collusion);
  - it is not individually rational against fixed priority.

### 9.5 Repeated encounters (S10)

Costs here are measured, and the rules are applied offline.

| Rule | Delay vs cost-optimal | Jain index |
|---|---|---|
| cost-optimal | — | 0.93 |
| fixed priority | +27% | 0.75 |
| strict alternation | +22% | 0.99 |
| **credit-weighted, λ = 0.25** | **+8%** | **0.997** |

### 9.6 Communication (S3, S8, S8b, S8c)

- **Up to 90% loss** with 2 s latency and detection down to 1.5 m: at least 99.3% success and no collisions.
- **Extreme comms (90–99% loss, 2–8 s latency):**
  - a pre-release protocol collided in 6 of 1,440 episodes, each time after both robots yielded on inconsistent decisions;
  - on the final code there are no collisions, with 98.9–99.2% success.
- **Safeguard ablation:** no arm collided, even with every safeguard off (95% upper bound 1.1%). So collision avoidance cannot be credited to any single safeguard.
  - The bay check never triggered.
  - Commit adds 3–4 s of delay with no measurable success gain.
  - Both robots start yielding in 14–24% of episodes.

### 9.7 Convoy (2 v 1)

- **Make room.** The new make-room rule removed every convoy deadlock (72/72 for all policies).
- **Equal urgency:** cost_bid 55.6 s vs group_bid 34.4 s vs fixed priority 33.7 s.
- **Urgent lone robot** (urgency-weighted delay):

  | Policy | Delay |
  |---|---|
  | side-level reference | 85.7 s |
  | fixed priority | 90.3 s |
  | group_bid | 104.7 s |
  | cost_bid | 117.1 s |

  group_bid underestimates the cost of a serial convoy yield.

### 9.8 T-junction

The junction-aware wait-in-bay fix took fixed priority from 29/48 to 48/48 successes. At 0% loss, the delays are:

| Policy | Delay |
|---|---|
| fixed priority | 60.5 s |
| rulebook | 53.1 s |
| cost_bid | 48.9 s |

Reactive succeeds in only 28/48 runs.

### 9.9 Maps

- **Mismatched maps.** These cost time, not safety: commit makes both robots adopt the lower-ID robot's decision.
  - The cost is +9 s for cost_bid and +30 s for the rulebooks when A's map is the poorer one.
  - Listing known bays in each BID removes the cost.
- **Physically blocked bay.** Every negotiating policy deadlocked at first (10/10 runs) because the yielder took the obstacle for a robot. After the fix there are no deadlocks, at a cost of about +46 s because the obstruction is found only on arrival.

### 9.10 Explore mode

- **Share-on-detect is too late at 6 m.** The robots decide before either lidar sees the other, so it equals not sharing (+29.2 s rulebooks, +8.8 s cost_bid).
- **Share every BID** recovers the full-map result.
- **`hold_for_map`** recovers the full map at 6 m in 2D, at about 5 s of extra time to decision.

### 9.11 Learned negotiator

| Layout | Learned | Rulebook | Fixed priority | cost_bid |
|---|---|---|---|---|
| Training layout | +2.6 s | +2.5 s | +9.2 s | 0 |
| Unseen single bay | +13.1 s | — | +12.3 s | — |

It matches the rulebook in its training layout but does not generalise: in the unseen layout it is no better than fixed priority, and 15% of observations are unseen.

---

## 10. Key results: Gazebo transfer

- **Reliability.** 460 final-code runs. Across the 450 non-reactive runs there were **0 failures and 0 collisions** (95% upper bound 0.85%).
- **Same first yielder.** **393 of 406 negotiating runs (96.8%)** chose the same first yielder as 2D. The 13 mismatches:
  - 5 noisy-bid runs (the noise is keyed to decision time);
  - 6 runs at 90% loss (different loss realisations);
  - 1 T-junction run;
  - 1 explore run.
- **Excess delay transfers** where the draws are shared. In the single-bay, urgency and slow-robot cases it is within 1.0 s of 2D (e.g. fixed priority 7.5 vs 7.6 s, reservation 15.2 vs 15.2 s). Elsewhere Gazebo delays run about 0.2–1.2 s lower.
- **T-junction delays do not transfer.** The mean Gazebo − 2D difference is −16.8 s:
  - exit runs: −260.0 s summed, traced to a release-timing race;
  - turn-in runs: −345.4 s summed, **unexplained**.
- **Early Gazebo runs exposed sim-to-real gaps:**
  - a goal placed on the room wall was "reachable" in 2D (fixed);
  - stem walls occlude the lidar (fixed by fusing STATE into `lane_clear`).
- **Share-on-detect at 3.5 m** works in 2D but not in Gazebo, because lidar-cluster detection happens at 2.3–2.6 m. Holding for the map fixes the wrong refuge but costs about +10 s.
- **Reactive baseline.** It is randomised, so it agrees with 2D only statistically: 5/10 runs had the same yielder, and 1 collided.

---

## 11. Key results: LLM/VLM negotiators (paper 2)

### 11.1 Screen (mediator + plans, `think=0`, n = 200)

| Model | Excess | Reference-yielder rate |
|---|---|---|
| cost_bid / rulebook / fixed priority | 0.0 / 2.9 / 10.7 s | 99 / 72 / 56% |
| Qwen3.8-27B, Qwen3-30B, Nemotron-3-Super-120B (hosted) | **−1.7 s** | 92–93% |
| Nemotron-3-Nano | −1.5 s | 92% |
| Nemotron-3-Nano-Omni | −1.0 s | 93% |
| Nemotron-3.5-Lightning | +1.7 s (66% parse fallback) | 80% |
| Gemma4-26B | +6.1 s | 75% |
| Llama-3.3-Nemotron-Super-49B | +15.8 s | 42% |
| Nemotron-Nano-VL-12B | +21.7 s | 38% |

Negative excess comes from refuge choice. The reference fixes each yielder's refuge to the planner's unweighted-delay pick, while the prompt asks for urgency-weighted delay.

### 11.2 Main findings

1. **The reasoning trace carries the capability.** With thinking disabled, the excess rises sharply (Wilcoxon p < 0.001):

   | Model | Thinking on | Thinking off |
   |---|---|---|
   | Qwen3.8-27B | −1.7 s | +11.1 s |
   | Qwen3-30B | −1.7 s | +22.5 s |

   Both thinking-off results are worse than the rulebook (+2.9 s).
2. **Latency kills the advantage.**
   - Charging measured latency as time both robots stand still adds about **3.4 s of excess per second of latency**. This matches the cost model: two robots at mean urgency 5/3 accrue about 3.3 s per second.
   - The serial thinking-on Qwen3-30B mediator charged 16.5 s and reached +55.3 s excess.
   - Break-even latency is about 0.3–0.5 s against cost_bid, and about 1.1–1.4 s against the rulebook. No measured configuration was both fast enough and reasoning-quality.
3. **Vision.** With thinking off, image-only beats text+plans on all four VL models (e.g. Gemma4 3.9 vs 6.6 s). The difference is significant (Wilcoxon) only for Qwen3.8. Adding raw text to the image made every model worse. No image arm reaches reasoning-on text quality.
4. **Decentralised egocentric agents fail by disagreement**, and the failure mode depends on the model:
   - Nemotron-Omni: both robots yield on 84% of encounters.
   - Qwen3.8 and VL-12B: both proceed on 29–31%.
   - Gemma4: agrees on 55%.
5. **The protocol default matters.** On conflicted encounters the rulebook fallback picks the reference yielder 66–71% of the time; a random hash draw picks it 40–51% of the time. Making the draw visible in the prompt changed what one model *wrote*, not the outcomes. Commit-reveal was also implemented.

---

## 12. Review notes, inconsistencies and open items

These are my observations from this review. None of them changes a headline conclusion, but several should be fixed before submission.

### 12.1 Inconsistencies found

1. **Robot radius in paper 2.** `papers/paper2_tase/main.tex:45` says "radius 0.15 m". Paper 1 and `geometry.RobotSpec` use a 0.25 m swept radius on a 0.281 × 0.306 m body. 0.15 m is the reverse speed, so this looks like a copy slip.
2. **The study reports (`reports/classical/`, `reports/gazebo/`; formerly `studies/REPORT_*.md`) are historical snapshots, not the canonical numbers.** They were written as each feature landed. Several differ from the final-code paper values:
   - reactive success 93.1% vs 93.8%;
   - S8 success "≥ 96.7%" vs "≥ 99.3%";
   - S10 cost-optimal Jain 0.92 vs 0.93; fixed priority +28% vs +27%; alternation +23% vs +22%;
   - the S9 section of `reports/classical/02_round2_S7-S10.md` is explicitly superseded by `reports/classical/04_clarke_payments.md`.

   **Treat `papers/paper1_ral/main.tex` as authoritative.** `reports/README.md` now says so and lists these differences.
3. **The old `README.md` was stale.** Fixed on `restructure`.
   - The old policy table omitted `group_bid`, `learned`, `clarke` and `reservation`.
   - The old "Known limitations" said 3+ robots and junctions were only planned.
   - The "Not yet studied" list in `reports/classical/01_round1_S1-S6.md` is still stale. It's a historical report and was left as written.
4. **Media predates the final protocol.** `media/gazebo/` clips were recorded on the initial commit `ba2ca27`, before commit/explore and the other changes; the media README says so. `media/gazebo_final/` holds the current clips.

### 12.2 Open pre-submission items (from `papers/*/reviews/SUMMARY.md` and source TODOs)

- **Paper 1:**
  - the real artifact URL/DOI (currently `[ANONYMIZED-URL]`);
  - remove the `% TODO`, `% VERIFIED` and "DRAFT" annotations;
  - release the convoy (1,080) and T-junction (384) per-episode rows and the bid-capture logs;
  - raw traces for the T-junction turn-in Gazebo gap and the hold-mode detection-distance gap.
- **Paper 2:**
  - the provenance of the Qwen3.8 serial thinking-on run (resumed run, worker count unrecorded);
  - the hosted endpoint failed on 58–100% of calls outside the screen;
  - run-to-run non-determinism of batched vLLM inference (e.g. Omni disagreement count 167–173/200).

### 12.3 Scientific limits the papers themselves acknowledge

- **Simulation only.** There are no physical TurtleBot3 trials. Gazebo uses ground-truth pose; AMCL or SLAM is untested.
- **Cost model.** Cost bidding and Clarke use the simulator's own motion model. Structural model errors, omitted-refuge manipulation and abuse of the commit tie-break are untested.
- **No formal guarantees.** The protocol has no safety or liveness proof; mutual yields are characterised only empirically.
- **Limited scenarios.** Pairwise negotiation is extended ad hoc to convoys. The T-junction is a deep-bay approximation. There are 1–2 corridor layouts.
- **LLM scope.** The LLM arms are 2D only, single-shot prompts, NVFP4-quantised, one run per arm. Multi-turn dialogue, tool use and selfish personas are untested.

### 12.4 Housekeeping

- **Tests.** `pytest`: **47 passed, 3 skipped** (5.8 s). The skips need the TurtleBot3 model (Gazebo) or a live `AMRNEG_LLM_URL`.
- **LLM prompt caches** (`cache.jsonl`) are git-ignored. Replaying an LLM run exactly therefore needs the model server, though `rows.jsonl` holds every per-episode answer and reasoning trace.
- **Worker count.** Most study scripts hard-code `mp.Pool(8)`. Raising it speeds them up on larger machines without changing results.
- **Paper 1 figures depend on the Matplotlib version.** `make_figures.py` reproduces the paper's numbers, but the committed PDFs were built with Matplotlib 3.11.2, so 3.9.2 gives byte-different files. Paper 2's figures regenerate identically.
- **LLM table headers are stale.** The `data/tables/llm/llm_*.md` tables say "Generated by `studies/llm_negotiation.py`", because they were written before the restructure.
- **Committed build output.** The monorepo commits ROS build output (`multi_agents_ws/src/{build,install,log}`). This is unrelated to the negotiation project, but it inflates the repo.

---

## 13. How to reproduce

```bash
# from the repo root
pip install -e .[dev]
PYTHONPATH=$PWD pytest -q tests

# single episodes / sweeps
amrneg-run configs/scenarios/corridor_single_bay.yaml --policy cost_bid --set bays.0.x=2.0 comms.loss=0.5 --plot ep.png
amrneg-sweep configs/sweeps/bay_position.yaml --out results

# study rounds (8 cores: ~8 min and ~10 min)
python experiments/classical/run_studies.py OUT    && python experiments/analysis/analyse.py OUT      # S1–S6
python experiments/classical/run_studies_r2.py OUT && python experiments/analysis/analyse_r2.py OUT   # S7–S10 (+ S8c with arg)
python experiments/classical/reservation_baseline.py
python experiments/classical/convoy_group.py ; python experiments/classical/tjunction_goal.py ; python experiments/classical/asym_map.py
python experiments/classical/wrong_map.py ; python experiments/classical/explore_map.py ; python experiments/classical/learned_negotiator.py

# LLM (needs an OpenAI-compatible server, see docs/llm_local.md)
python experiments/llm/llm_negotiation.py --tag <tag> --model <served-name> --base-url http://localhost:8000/v1 --n 100 --variants llm_med_plans --think 0

# Gazebo (Docker)
docker build -f docker/Dockerfile -t amrneg .
docker run --rm -v $PWD/results:/results amrneg ros2 launch amr_negotiation_ros corridor.launch.py \
  scenario:=/amr_negotiation/configs/scenarios/corridor_single_bay.yaml policy:=rule_based record:=true

# Paper figures (from the repo root), then build with latexmk in each paper folder, or upload to Overleaf
python papers/paper1_ral/make_figures.py
python papers/paper2_tase/make_figures.py
```

Each folder's README has the details: [`experiments/`](experiments/README.md) for studies,
[`papers/`](papers/README.md) for builds and Overleaf, [`docker/`](docker/README.md) for Gazebo.

### 13.1 Local replication status

Checked on a 32-core x86_64 Ubuntu 24.04 machine with 62 GB of RAM and an RTX 4090 (24 GB):

| Part | Status |
|---|---|
| 2D simulator, all classical studies, analysis, paper figures | **Works as-is.** S1 (2,940 episodes) reruns in about 40 s and matches the released CSV row for row |
| Gazebo runs | **Needs Docker** (or a native ROS 2 Jazzy + Gazebo Harmonic install, which supports Ubuntu 24.04). About 3–5 min per run, so plan on a reduced subset |
| LLM study | **Partial.** The paper's NVFP4 weights need Blackwell GPUs. On a 4090, use 4-bit GGUF/AWQ builds of the same families (the ~30B MoE models fit; the 49B dense model does not fit fully in 24 GB). Expect the same pattern of results, not identical numbers. Latency figures will be specific to the hardware |

---

## 14. Glossary

| Term | Meaning |
|---|---|
| Refuge | A bay off the corridor, or a parking spot in an end room, where a yielder waits. |
| Yielder / proceeder | The robot that pulls aside / the robot that passes. |
| Snapshot | The frozen state a robot sends in its BID when a conflict starts. |
| Best forced yielder (oracle) | Hindsight reference: the better of "A yields" and "B yields" with the planner's refuge. |
| Excess delay | Policy delay minus best-forced-yielder delay, paired per encounter. Called "regret" in the reports. |
| Commit / state guard / bay check | The three protocol safeguards against inconsistent decisions under message loss. |
| Mediator / agents | LLM modes: one central call vs one call per robot. |
| `plans` / `raw` | LLM prompt with / without the planner's predicted delays. |
| `think=0` / `measured` | LLM latency not charged / charged as frozen decision time. |
| Share-on-detect / hold-for-map | Send the map only after lidar detects the peer / postpone the decision until that map arrives. |

---

## 15. Change log (2026-10-27)

What changed in the repository since the upstream snapshot `876e896`. None of these changes touch the agent, the
policies or the simulators, apart from the default-rulebook path in `policies.py`.

### 15.1 Restructure (local `5f6423f`; fork `076c623`)

- **Folders reorganised by role**, using the mapping table in §2.1:
  - `configs/` for inputs;
  - `experiments/{classical,analysis,gazebo,llm}/` for scripts;
  - `data/raw/{classical,gazebo,llm}/` and `data/tables/{classical,classical_r2,gazebo,llm}/` for results;
  - `reports/{classical,gazebo,llm}/` for write-ups;
  - `papers/{paper1_ral,paper2_tase}/` for the manuscripts.

  Reports were renamed in run order, e.g. `REPORT.md` became `reports/classical/01_round1_S1-S6.md`; `reports/README.md` lists every old and new name.
- **Every reference updated:** script paths and `parents[...]` depths, cross-folder imports (`sys.path` lines for `analyse_helpers` and `learned_negotiator`), default output folders, `cd` lines in the LLM shell scripts, markdown links, and the container paths inside the Gazebo run lists and policy JSONs (`/amr_negotiation/configs/rulebooks/...`, `/amr_negotiation/data/tables/classical/learned_table.json`).
- **Script interface changes:**
  - `reservation_baseline.py` and `analyse_protocol.py` now default to writing into `data/`.
  - `explore_map.py` defaults to `data/raw/classical/`.
- **`.gitignore`** covers `papers/*/` LaTeX build files, `papers/*.zip` (Overleaf zips) and `.idea/`.
- **Rewritten root `README.md`:** a repository map, all ten policies (four were missing), and current limitations (the old text said convoys and junctions were only planned).
- **Bugs caught while verifying the move, all fixed:**
  - paper 1's figure script and `make_scen_r2.py` built scenario paths in split form (`ROOT / "scenarios" / name`);
  - `llm_negotiation.py` was missing an `import sys`.

### 15.2 Documentation (local `09f8726`; fork `11684c6`)

- **Added `PROJECT_HIERARCHY.md`:** a tree, an index of all 35 folder READMEs, and a data-flow diagram.
- **Added READMEs to the 26 folders that had none.** Each describes what is available: package modules; test coverage; scenario keys; rule semantics; script inputs and outputs; raw-data columns and row counts; table contents; LLM `rows.jsonl` fields and variant names; paper files and open items; ROS nodes and launch arguments; Docker usage.
- **Navigation.** Every README opens with links to the hierarchy and its parent, and parent READMEs link to their children. `media/README.md` became an index of its three subfolders.
- **Corrected the tiebreak labels** in the LLM run index and this overview: `-nonce` is the *visible* draw (rule and cards in the prompt), and `-silent` is the *hidden* draw. This matches `llm.py` and paper 2.

### 15.3 This update

This overview gained the navigation block, the "where the current version lives" table (§2.1), the top-level
files in the layout (§2.3), the run-index pointer and corrected stage-script paths (§8.3), the housekeeping notes
(§12.4), working paper-figure commands, local replication status (§13), and this change log.

### 15.4 Verification

The checks run on the restructured tree:

| Check | Result |
|---|---|
| `pytest` | 47 passed, 3 skipped, before and after, in both the flattened and monorepo layouts |
| S1 rerun from `experiments/classical/` | all 2,940 rows identical to `data/raw/classical/S1_baseline.csv.gz` |
| `amrneg-sweep configs/sweeps/bay_position.yaml` | identical to the pre-move run |
| `analyse_protocol.py`, `summarise_gazebo.py`, `make_scen_r2.py`, `make_scen_all.py` | regenerate their committed outputs byte-identically |
| Both papers' `make_figures.py` | run; paper 2 output is identical, paper 1 differs only by Matplotlib version (§12.4) |
| Markdown links | 0 broken across all 63 markdown files; every README links to the hierarchy, and the hierarchy links to every README |
| Fork commits | the `amr_negotiation/` tree is identical to the local branch, and no file outside it changed |
