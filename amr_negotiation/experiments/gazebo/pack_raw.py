"""Pack the per-run Gazebo result JSONs of the current-code batches into one gzipped JSONL for data/raw/gazebo/.

Usage: python experiments/gazebo/pack_raw.py OUT.jsonl.gz BATCH_DIR:TAG [BATCH_DIR:TAG ...]
Each line is one run's result JSON plus `batch` (TAG) and `policy_label` (the out/ subdirectory)."""
import gzip
import json
import sys
from pathlib import Path

out, n = sys.argv[1], 0
with gzip.open(out, "wt") as f:
    for arg in sys.argv[2:]:
        d, tag = arg.rsplit(":", 1)
        for p in sorted(Path(d, "out").glob("*/*.json")):
            rec = json.loads(p.read_text())
            rec.update(batch=tag, policy_label=p.parent.name)
            f.write(json.dumps(rec) + "\n")
            n += 1
print(n, "runs ->", out)
