# Learned negotiator baseline (tabular, trained in the 2D sim)

`python studies/learned_negotiator.py` → `report/learned_negotiator.md`, `report/learned_table.json`.

## Method

- **Policy `learned`.** Both robots compute the same coarse observation from the two negotiation snapshots
  (`learned_features`). Per robot: the distance to its nearest feasible refuge behind it, binned
  <1 / 1–2.5 / 2.5–5 / >5 m / none. Plus which robot is more urgent and both payload flags. The action is
  who yields; the refuge is then chosen as in the other policies.
  Each robot looks the observation up in a shared table and yields the side with the lower mean learned cost.
  An observation not in the table falls back to fixed priority.
- **Training.** Encounters are drawn at random in `corridor_two_bays`: bays at x ∈ U(1.5, 4.5) and
  U(5.5, 8.5), start delays U(0, 4) and U(0, 8), urgency 1 or 3, loaded with p = 0.3. For each encounter we
  record the observation at decision time and run **both** forced outcomes. Each action's cost is the
  urgency-weighted delay Σ uᵢ·delayᵢ, or 300 s if the episode fails.
  This makes it a full-information contextual bandit, trained centrally and run decentrally. The policy uses
  no planner costs, so it learns from outcomes rather than copying `cost_bid`.
- **Evaluation.** 150 held-out encounters (seeds 10000+) in the training layout. Another 150 in an
  **unseen** layout, `corridor_single_bay` with the bay at U(1.5, 8.5). 0% packet loss.
  `oracle_w` is the best of the two forced outcomes in hindsight. ± is a 95% CI on the mean.

## Results

| Training | Eval layout | Policy | Weighted delay (s) | Regret (s) | Fallback |
|---|---|---|---|---|---|
| 800 | two bays (seen) | fixed priority | 42.5 ± 4.0 | +9.2 | |
| 800 | two bays | rulebook | 35.7 ± 3.3 | +2.5 | |
| 800 | two bays | `cost_bid` | 33.6 ± 2.9 | +0.4 | |
| 800 | two bays | **learned** | 35.8 ± 3.3 | +2.6 | 1% |
| 50 / 200 | two bays | learned | 37.1 / 36.0 | +3.9 / +2.8 | 35% / 8% |
| 800 | single bay (unseen) | fixed priority | 52.6 ± 5.3 | +12.3 | |
| 800 | single bay | rulebook | 46.6 ± 4.8 | +6.3 | |
| 800 | single bay | `cost_bid` | 41.1 ± 3.9 | +0.7 | |
| 800 | single bay | **learned** | 53.5 ± 6.0 | +13.1 | 15% |

No failures or collisions in any evaluation run. The table has 93 observation states.

## Findings

- In the layout it was trained on, the learned policy reaches **rulebook-level** performance (regret +2.6 s
  against +2.5 s), well ahead of fixed priority (+9.2 s). It does this from 200 or more encounters,
  without a hand-written rulebook or a cost model.
- It **does not transfer**. In the unseen single-bay layout it is no better than fixed priority (+13.1 s
  against +12.3 s). Part of that is the 15% fallback; the rest is that its features don't capture
  where the bay lies relative to the other robot.
- `cost_bid` stays best everywhere. But its cost model is the simulator's own kinematics (best case), while
  the learner only sees outcomes.

## Limits

This is a lightweight baseline, not deep MARL. It makes one decision per encounter and uses a tabular
value per observation, with two robots and lossless communications. Training is centralised, with both
forced outcomes simulated for each encounter. Not tested: per-robot (independent) learners, partial
observation, learning the motion itself, and 3+ robots. Natural next steps are independent learners with
only their own reward, which would expose strategic behaviour, and a richer observation with features of the
peer's refuge.
