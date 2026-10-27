[↑ Project hierarchy](../../../PROJECT_HIERARCHY.md) · [Parent: data/raw](../README.md)

# `data/raw/gazebo/`: Gazebo result JSONs

Gzipped JSON Lines: one referee result per Gazebo run, packed by
[`experiments/gazebo/pack_raw.py`](../../../experiments/gazebo/README.md).

| File | Runs | Contents |
|---|---|---|
| `gazebo_current.jsonl.gz` | 460 | The final-code validation over a reduced grid of every study. Batch `main@bf24bf4` has 122 original cases; batch `all@2ba4c6d` has 338 cases. |
| `gazebo_hold.jsonl.gz` | 36 | Hold-for-map batch (`hold@be50818`): share-on-detect ± hold at 3.5 and 6 m, run outside the 460 |

Each line has the same keys as a `sim2d` result:
- `simulator`, `scenario`, `policy`, `policy_label`, `batch`;
- outcome: `success`, `deadlock`, `collision`, `t_end`, `makespan`, `min_clearance`;
- `agents` (per-robot arrival, delay, reverse distance, yields), plus `yielder`, `rule`, `refuge`, `msgs`;
- `wall_time`;
- the full `events` and `decisions` logs, and a pose `trace`.

```python
import gzip, json
runs = [json.loads(l) for l in gzip.open("data/raw/gazebo/gazebo_current.jsonl.gz", "rt")]
```

Per-run comparisons with 2D on the same seed: [`data/tables/gazebo/`](../../tables/gazebo/README.md).
