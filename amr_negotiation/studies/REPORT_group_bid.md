# Group-level bidding for convoys (`group_bid`) and convoy "make room"

Scenario: `scenarios/corridor_convoy.yaml`. A and C drive east in convoy, B drives west, two bays.
Grid: bay positions {2,4}×{6,8}, B start delay {0,4,8}, 3 seeds, 0% and 50% packet loss: 72 runs per cell
(`python studies/convoy_group.py`, output `report/convoy_group.txt`). 2D simulator only.

## `group_bid`

Pairwise `cost_bid` compares only the two robots in the conflict, so it ignores the follower C. `group_bid`
bids for each side as a group:

- Each robot's negotiation snapshot carries its **followers**: same-direction robots behind it within
  detection range, built from their STATE messages. STATE now also carries `urgency` and `loaded`.
- `group_yield_cost(Y, P)` = Σ over Y and its followers of urgency × delay of the best plan against P (each
  member needs its own bay; rooms can be shared), plus every yielder's wait while P's followers pass.
- The lower-cost side yields; the leader's refuge is chosen as in `cost_bid`.

With no followers it reduces exactly to `cost_bid`: 96/96 two-robot runs (single-bay and two-bay corridors,
0%/50% loss) gave identical outcomes.

## Make room (all policies)

If a yielding leader must reverse into a refuge and its follower sits close behind, the follower blocked it
and the pair deadlocked. The follower stayed cruising behind the leader. This bit every policy whenever the
convoy was the side that yielded. New rule (`Agent.make_room`): a robot that sees a same-direction robot just
ahead in YIELD mode, reversing into a refuge it is blocking, backs into its own free refuge behind it. The
STATE messages say who that refuge is for.

## Results (72 runs per cell, mean delay over successful runs)

| B is | Policy | Success | Total delay (s) | Urgency-weighted delay (s) |
|---|---|---|---|---|
| equal | fixed priority | 72/72 | 33.7 | 33.7 |
| equal | rulebook | 72/72 | 40.0 | 40.0 |
| equal | `cost_bid` | 72/72 | 55.6 | 55.6 |
| equal | **`group_bid`** | 72/72 | **33.7** | **33.7** |
| loaded | fixed priority | 72/72 | 33.7 | 33.7 |
| loaded | rulebook | 72/72 | 100.1 | 100.1 |
| loaded | `cost_bid` | 72/72 | 55.6 | 55.6 |
| loaded | **`group_bid`** | 72/72 | **33.7** | **33.7** |
| urgent (×3) | fixed priority | 72/72 | 33.7 | **90.3** |
| urgent (×3) | rulebook | 72/72 | 100.1 | 133.6 |
| urgent (×3) | `cost_bid` | 72/72 | 97.1 | 132.6 |
| urgent (×3) | `group_bid` | 72/72 | 97.1 | 132.6 |

Zero collisions everywhere. Before make room, on `main`: when B was urgent, `cost_bid` and the rulebook
succeeded in 66/72 runs; when B was loaded, the rulebook succeeded in 66/72. Every failure was a deadlock.

## Findings

- With equal or loaded B, `group_bid` cuts the convoy delay from 55.6 s to 33.7 s, matching the best pairwise
  rule (here fixed priority, because A outranks B).
- With an urgent B, `group_bid` makes the convoy yield, as `cost_bid` does. That costs 132.6 s urgency-weighted
  against 90.3 s for fixed priority, so **the group cost model underestimates what a convoy yield costs**.
  It plans each member's yield independently against B's current position. In reality the follower must
  first back off for the leader (make room) and the yields happen one after another. Modelling that serial
  order (or a centralised 3-robot oracle to measure regret) is the obvious next step.
- Make room is a general convoy fix: it removed the remaining convoy deadlocks for every policy.

## Limits

2D only; a single convoy layout (2 v 1); followers' speeds are assumed equal to the bidder's; no 3-robot oracle.
