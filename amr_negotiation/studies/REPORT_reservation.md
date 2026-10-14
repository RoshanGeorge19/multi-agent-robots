# Corridor-reservation baseline and stronger references

Reviewers of the draft paper (#18) asked for two additions:
- **A zone-control / mutual-exclusion baseline.** Real fleet managers use these, so the paper should compare
  against one.
- **A stronger comparator than the two forced-yielder runs.** The earlier reports called that comparator the
  "oracle", but it only chooses who yields.

## Policy `reservation`

- **First come, first served:** a robot that is still outside the corridor while an oncoming robot is inside parks
  in its own end room (refuge `room_lo` / `room_hi`). It leaves once that robot has passed. This reuses the
  existing yield logic: the robot inside sees the yield announcement and proceeds.
- **Both inside:** if both robots get into the corridor (similar arrival times, or latency), they fall back to the
  default rulebook. Negotiation is otherwise suppressed while only one robot is inside.
- **Code:** `Agent.corridor_holder`, the reservation branch in `Agent.tick_cruise`, and the `oncoming_conflict`
  filter.

## Study (`studies/reservation_baseline.py`)

- **Grid:** single-bay corridor, bay x ∈ {1, …, 7} m, 30 seeds per bay, B's start delay U[0, 8] s per seed.
  That is 210 paired encounters and 1,260 episodes.
- **Raw data:** `results_raw/reservation.csv.gz`. Table: `report/reservation.md`.
- **References, per encounter:**
  - **best forced yielder** = min(forced A, forced B). This is the "oracle" of the earlier reports.
  - **best of strategies** = min(forced A, forced B, reservation).

| Policy | success | total delay [s] | excess over best forced yielder [s] |
|---|---|---|---|
| `reservation` | 100% | 45.6 ± 0.3 | 18.8 ± 0.9 |
| `fixed_priority` / `rules_default` | 100% | 33.3 ± 1.3 | 6.5 ± 0.9 |
| `cost_bid` | 100% | 26.8 ± 0.8 | 0.0 ± 0.0 |

**Findings:**
- **Reservation never helps here.** It beats the best forced yielder in 0/210 encounters, so in this scenario
  "best of strategies" equals the best forced yielder.
- **Why it's slow:** B starts in its room *on A's exit path* (start x = 9 m, A's goal x = 10 m). So B cannot just
  stop at the corridor entrance; it has to pull off the lane into the room. Turning in, parking and leaving cost
  about 17 s, and B waits for A's whole traversal rather than only until A passes a bay.
- **Reviewer's estimate:** the reviewer's scratch estimate (≈ 30.6 s, beating the oracle in 43/210) let B wait at
  the entrance without leaving A's path, so it did not pay this overhead. Reservation would win only where the
  waiting robot can hold off the other robot's path at no cost.
- **Excess by bay position:** 7.9 s at x = 1, 23–24 s at x = 3–6, 14.9 s at x = 7. Reservation's cost doesn't
  depend on the bay, whereas the best forced yielder's falls when the bay is central.

## Side-level convoy reference (`studies/convoy_group.py`, policy `side_oracle`)

- **What it compares:** for the convoy (A, C eastbound vs B), the reference keeps the better of "the A+C side
  yields" (forced A) and "B yields to both" (forced B).
- **Objective:** it minimises urgency-weighted delay, i.e. it is the best forced *side*, not a joint motion plan.
- **Results:** see `report/convoy_group.txt`.

Urgent B (×3), 72 runs per cell, all successful, no collisions:
- **`side_oracle`:** 85.7 s urgency-weighted delay (41.9 s unweighted).
- **`fixed_priority`:** 90.3 s, about 4.6 s worse than the side-level reference.
- **`group_bid`:** 132.6 s on this branch's code. With the cost fix from #19 it is 104.7 s, still 19 s worse.

With equal urgencies, or a loaded B, the side-level reference equals fixed priority and `group_bid` (33.7 s).
