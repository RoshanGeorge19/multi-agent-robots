[↑ Project hierarchy](../PROJECT_HIERARCHY.md) · [Repo README](../README.md)

# `tests/`: pytest suite

```bash
pytest -q          # from the repo root: 47 passed, 3 skipped, about 6 s
```

| File | Covers |
|---|---|
| `test_core.py` (39 test functions) | Geometry and the single-lane check; refuge feasibility; rulebook rules and the ID tie-break; decision symmetry; overrides; episodes resolving without collision; negotiation beating reactive, and `cost_bid` matching the oracle; urgent/loaded right of way; two bays; packet loss and extreme comms; determinism; footprint overlap; convoy and make-room; T-junction exit and turn-in; asymmetric maps and map sharing; blocked-bay fallback; the learned-policy table; reachable goals; lidar occlusion handled via STATE; `group_bid`; urgency-weighted bids; Clarke truthfulness and its equivalence to `cost_bid`; reservation; explore mode; hold-for-map (default off, map exchange, lost MAP, timeout); Gazebo world generation |
| `test_llm.py` (7 test functions) | The LLM adapter against a fake in-process server: mediator choice and cache, agents mode, rulebook fallback on disagreement and on a dead server, latency charged as think time, file-cache replay, plus one live-server test |

The 3 skips are expected on a machine without Gazebo or an LLM server:
- two Gazebo-world tests need the TurtleBot3 Waffle model from `ros-jazzy-turtlebot3-gazebo`;
- the live LLM test runs only when `AMRNEG_LLM_URL` is set.
