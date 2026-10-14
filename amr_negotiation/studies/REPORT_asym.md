# Asymmetric map knowledge (robots know different bays)

**Question.** What happens when one robot knows about a bay that the other doesn't?

**Setup.**
- Scenario: `corridor_two_bays.yaml`, a 10 m corridor with `bay0` at x = 3 m (left) and `bay1` at x = 7 m (right).
- Robots: A starts on the west side and B on the east, with B's start delay drawn uniformly from 0–8 s.
- Knowledge: each robot's known bays are set with `AgentConfig.known_refuges`; `None` means it knows every bay. The end rooms are always known.
- Runs: 10 seeds per cell, with packet loss of 0% and 50%. Script `studies/asym_map.py`, raw output in `report/asym_map.txt`.

**Two map modes.**
- **Own maps** (`share_map: false`, the default): each robot decides using only the bays it knows. A robot learns a bay only when the peer's decision names it. With the decision-commit protocol, a mismatch is settled by the lower id, so A's decision wins.
- **Shared maps** (`share_map: true`): every BID lists the bays the sender knows. The receiver adds them to its map before it decides, so both robots decide on the union of their maps.

## Results

Every run in every cell succeeded (10/10), with 0 collisions and 0 deadlocks. "Extra delay" is the mean total delay minus that of the same seed with full knowledge.

| Who knows what | Policy | Extra delay, own maps | Extra delay, shared maps | Decision mismatches, own maps (0% / 50% loss) |
|---|---|---|---|---|
| A knows only bay0 | fixed / rules | +29.6 s | +0.0 s | 20 / 22 |
| A knows only bay0 | cost_bid | +9.1 s | +0.0 s | 20 / 22 |
| A knows only bay1 | all | +0.0 s | +0.0 s | 0 |
| B knows only bay0 | all | +0.0 s | +0.0 s | 20 / 22 (B learns from A) |
| A knows bay0, B knows bay1 | fixed / rules | +29.6 s | +0.0 s | 20 / 22 |
| A knows bay0, B knows bay1 | cost_bid | +9.1 s | +0.0 s | 20 / 22 |
| A knows no bays | all | +31.1 s | +0.0 s | 20 / 22 |

## Findings
- **Knowledge gaps cost time, not safety.** The decision-commit protocol detects the disagreement (`decision_mismatch`) and both robots adopt one decision, so nothing collides. That decision comes from the lower-id robot's map. When that map is missing the useful bay, B backs up to a worse refuge or to the end room: +9 to +31 s per encounter.
- **The cost depends on who holds the better map.** If B's map is the poorer one, there is no cost: A's decision wins and B learns the bay it names (`refuge_learned`).
- **Bidding loses less.** `cost_bid` loses less than the rulebooks (+9 s vs +30 s). A's own bid still prices the bay it knows, so the pair often picks a reasonable yielder.
- **Sharing maps removes the cost entirely.** One list of bay ids in each BID gives +0.0 s in every case, at both 0% and 50% loss, with no mismatches.

## Caveats
- Only 10 seeds per cell, two robots, and one corridor layout.
- In this simulator, "learning" a bay means trusting the peer's bay id. A real robot would also need the bay's pose, and a check that it is free (`bay_seen_occupied` already covers occupancy).
- Not yet tested: 3+ robots, the T-junction, and stale or wrong maps (a bay the peer believes exists but doesn't).
