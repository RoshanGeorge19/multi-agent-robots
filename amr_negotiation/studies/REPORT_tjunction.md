# T-junction: robot turning into the side branch (stem-exit vs turn-in deadlock fix)

Scenario: `scenarios/corridor_tjunction_goal.yaml`. A drives east with the side branch (stem, modelled as a
deep bay `bay1` at x = 5.5) as its destination; B drives west through the corridor; S starts parked in the
stem and leaves it, heading west (goal −2.5) or east (goal 10). Grid: A/B/S start delays {0,4}×{0,4,8}×{0,6},
both S goals, 2 seeds, at 0% and 50% packet loss: 48 runs per policy × loss cell
(`python studies/tjunction_goal.py`). The stem is still a deep-bay approximation, not a full 2-D junction.

## Failure modes on `main` (PR #11)

1. **S leaves westward, straight at A.** A waits in the lane just short of the occupied stem. Neither robot has a
   free refuge behind it, so the pairwise decision is `infeasible`; S falls back to reactive, backs into the
   stem again, and the pair livelocks.
2. **S leaves eastward, B oncoming.** A waits in the lane for the stem while B arrives; again no feasible
   pairwise yield, and B ends up reversing a long way.
3. **Yielder's refuge beyond A's destination.** When B yields into `room_hi` (east of the stem), A treated it as
   an ordinary yielding peer and tried to "proceed past" a refuge it never reaches, looping
   `proceed_start → released → passed_refuge`.

## Fix (junction-aware waiting, `agent.py`)

- `goal_occupant()`: while A's destination is occupied, A looks for a peer it must let by: the stem occupant
  if it will leave towards A, or an oncoming robot in the corridor within detection range.
- `goal_wait_refuge()`: A then waits in the closest free bay before its destination (one ahead is preferred,
  so no reversing) instead of in the lane, using the normal yield machinery (`rule="goal_wait"`), and resumes
  once that peer has passed.
- A robot with a destination refuge ignores a yielding peer whose refuge lies at or beyond that destination
  (it turns off before reaching it).

All three only apply to robots with a `goal_refuge`; with no comms (reactive) nothing changes.

## Results

| Policy | Loss | Success before → after | Mean total delay before → after (s) |
|---|---|---|---|
| fixed priority | 0% | 29/48 → **48/48** | 152.2 → 60.4 |
| fixed priority | 50% | 33/48 → **48/48** | 152.7 → 65.5 |
| rulebook | 0% | 42/48 → **48/48** | 70.6 → 53.1 |
| rulebook | 50% | 46/48 → **48/48** | 66.9 → 55.4 |
| `cost_bid` | 0% | 44/48 → **48/48** | 51.3 → 48.8 |
| `cost_bid` | 50% | 48/48 → 48/48 | 52.4 → 49.7 |
| reactive | both | 27/48 → 27/48 | 189.1 → 189.1 |

Zero collisions before and after. Every earlier failure was a deadlock. Delays are means over successful runs,
so the "before" numbers exclude the deadlocked runs. Full tables: `report/tjunction_goal_before.txt`, `report/tjunction_goal.txt`.

**No regressions:** the stem-start T-junction (18 runs/policy), the convoy (36 runs/policy at 0% and 50% loss),
S4 two-bay and S8b extreme-comms sweeps give identical results to `main`.

## Limits

- 2 seeds per start-delay combination; the 2D simulator only.
- The reactive baseline still deadlocks in 21/48 runs; it has no messages, so `goal_occupant()` cannot apply.
- A needs a free bay before the junction to wait in. With none, it falls back to the old behaviour.
