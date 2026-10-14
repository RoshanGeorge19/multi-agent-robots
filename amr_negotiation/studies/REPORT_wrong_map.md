# Wrong maps: a bay on the map that is physically blocked

Scenario: `scenarios/corridor_two_bays.yaml` (bay0 at x=3 north, bay1 at x=7 south, end rooms). New scenario
field `blocked_bays`: those bays stay on every robot's map but are physically obstructed. The 2D sim puts a
robot-sized obstacle at the bay's parking pose; lidar sees it within `lidar_range` and touching it is a
collision. Grid: 4 blocked sets × 4 policies × {0%, 50%} loss × 10 seeds (B start delay random 0–8 s).
`python studies/wrong_map.py` → `report/wrong_map.md`. 2D only.

## Failure before the fix

Every negotiating policy deadlocked in 10/10 runs whenever the useful bay (bay1) was blocked. In the trace:
B could already see bay1 was occupied and proposed `room_hi`. A's map still showed bay1 free, so the
lower-ID rule adopted A's decision ("B yields into bay1"). On reaching bay1, B's sensor check (from #10) took
the obstacle for a robot that had already yielded and switched B to proceeding. Both robots then proceeded
and stopped nose to nose. No collision: the safety checks held, but nothing made progress.

## Fix

- `robot_in_refuge`: when a yielder finds its bay occupied, it checks the peers' STATE messages. If no known
  robot is in the bay, the bay is **obstructed**, not taken by a peer.
- An obstructed bay is added to the robot's `obstructed` set and dropped from its map. The robot keeps
  yielding into the nearest free refuge behind it (`fallback_refuge`, rule `refuge_blocked`), so the
  proceeding robot's plan stays valid.
- BIDs carry `blocked`, so a peer that negotiates with this robot later also drops the bay.
- If STATE is lost, a peer in the bay can look like an obstruction. The robot then reverses further, which
  is slower but safe.

## Results (10 runs per cell)

| Blocked | Policy | Success 0% / 50% | Collisions | Extra delay vs no blockage |
|---|---|---|---|---|
| bay0 (not used) | all negotiating | 10/10 / 10/10 | 0 | 0 s |
| bay1 (useful) | fixed / rulebook / `cost_bid`, before | 0/10 / 0/10 | 0 | n/a (all deadlock) |
| bay1 (useful) | fixed / rulebook / `cost_bid`, after | 10/10 / 10/10 | 0 | +46 s |
| both | fixed / rulebook / `cost_bid`, after | 10/10 / 10/10 | 0 | +46 s |
| bay1 | reactive | 8/10 / 8/10 | 0 | +24 s (successful runs) |

The +46 s is the cost of finding out late: the yielder reaches the blocked bay and then reverses on to the
end room. Reactive is not affected by the map and does the same as before.

## Limits

- Only detected on arrival (sensor check at the bay). Robots don't see the obstruction earlier or send it
  ahead, so the first robot to find it pays the whole cost.
- Two robots only. Sharing the obstructed set in BIDs is implemented and passes the tests, but this study
  doesn't measure its benefit (it needs a later encounter).
- A "phantom" bay (on the map, absent in reality) behaves like a blocked one to the sensor here. Wrong bay
  *positions*, and peers that report false bays, are not tested.
