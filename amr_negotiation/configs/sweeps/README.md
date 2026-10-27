[↑ Project hierarchy](../../PROJECT_HIERARCHY.md) · [Parent: configs](../README.md)

# `configs/sweeps/`: Monte Carlo sweep definitions

Inputs to `amrneg-sweep` (`amr_negotiation/sweep.py`):

```bash
amrneg-sweep configs/sweeps/bay_position.yaml --out results
# -> results/bay_position_episodes.csv, bay_position_summary.csv, bay_position_summary.png
```

| File | Policies | Grid | Seeds |
|---|---|---|---|
| `bay_position.yaml` | reactive, fixed priority, both rulebooks, `cost_bid`, oracle | bay x ∈ {1, 2.5, 4, 5.5, 7} m; B delay U[0, 6] s | 10 |
| `comms_loss.yaml` | default rulebook, `cost_bid` | loss ∈ {0, 20, 50, 80, 95}%; B delay U[0, 6] s | 10 |

## Format

```yaml
scenario: scenarios/corridor_single_bay.yaml   # paths are relative to configs/
seeds: 10
policies:  [{name: cost_bid}, {name: rule_based, rulebook: rulebooks/proximity_first.yaml, label: rules_proximity}]
grid:      {bays.0.x: [1.0, 4.0, 7.0]}          # full factorial over dotted override keys
random:    {agents.1.start_delay: [0.0, 6.0]}   # per-seed uniform draw
```

These are small demonstrations. The published studies define their own grids in
[`experiments/classical/`](../../experiments/classical/README.md).
