# Bid cost fix: weight each robot's delay by its own urgency

Reviewers of the draft paper (PR #18) found two errors in the bid cost functions in `policies.py`:

- `yield_bid` returned `Y.urgency * total_delay`, which weights **both** robots' delays by the yielder's urgency.
  The urgency-weighted social cost of "Y yields" is `u_Y·d_Y + u_P·d_P`.
- `group_yield_cost` summed `u_y·(d_y + d_P)` over every member of the yielding side, so it counted the
  proceeder's delay once per member (weighted by the wrong urgency). P's followers' delays were not counted at all.

Fix:
- `planner.plan_times` now also returns `weighted_delay = u_Y·d_Y + u_P·d_P`, and `yield_bid` uses it.
  The refuge choice itself is unchanged: it still minimises unweighted total delay, so the bid prices the plan that
  is executed.
- `group_yield_cost` = Σ_{y∈Y-side} u_y·d_y + (wait for P's followers)·Σ u_y + max_y d_P(y)·Σ_{p∈P-side} u_p.
  The proceeder's hold is counted once, and it applies to P and each of its followers.

With equal urgencies, `yield_bid` is unchanged. So are all symmetric-robot studies (S1, S3–S10, T-junction, maps).

## Effect: S2, asymmetric robots (5,040 episodes, 30 seeds per cell)

Weighted excess delay against `oracle_w`, mean ± 95% CI, on current `main` code. The other policies differ from
`reports/classical/01_round1_S1-S6.md` only through the decision-commit protocol, which was added after S2 was first run.

| Policy | Weighted delay [s] | Weighted excess delay [s] | Same yielder as `oracle_w` |
|---|---|---|---|
| `cost_bid`, before fix (`reports/classical/01_round1_S1-S6.md`) | 39.2 | 0.8 ± 0.2 | 88% |
| `cost_bid`, after fix | 39.5 | **0.04 ± 0.02** | **98%** |
| `rules_default` | 43.0 | 3.5 ± 0.4 | 64% |
| `fixed_priority` | 66.5 | 27.1 ± 2.6 | 36% |
| `oracle` (unweighted) | 46.5 | 7.0 ± 1.5 | 86% |

## Effect: convoy (A + C vs B, 72 runs per cell, `experiments/classical/convoy_group.py`)

| Case | Policy | Total delay before → after [s] | Urgency-weighted delay before → after [s] |
|---|---|---|---|
| B urgent (×3) | `group_bid` | 97.1 → 65.9 | 132.6 → **104.7** |
| B urgent (×3) | `cost_bid` | 97.1 → 80.6 | 132.6 → 117.1 |
| B urgent (×3) | `fixed_priority` | 33.7 | 90.3 |
| equal / B loaded | `group_bid` | 33.7 → 34.4 | 33.7 → 34.4 |

All runs succeed with no collisions, before and after. In the urgent case, the fix closes about 28 s of the 42 s
gap between `group_bid` and fixed priority. The remaining ~14 s is what the serial-yield approximation still misses.
The equal-urgency convoy is 0.7 s slower, because P's followers' hold is now priced.
