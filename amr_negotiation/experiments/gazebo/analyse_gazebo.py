"""Compare the Gazebo S1 sweep with 2D-sim reruns of the same scenario, policy and seed.

Usage: python experiments/gazebo/analyse_gazebo.py [GZSWEEP_DIR]  (default ~/studies/gzsweep, laid out as by experiments/gazebo/run_one.sh)
"""

import collections
import glob
import json
import os
import statistics as st
import sys
from pathlib import Path

from amr_negotiation import sim2d
from amr_negotiation.geometry import load_scenario

R = str(Path(__file__).resolve().parents[2])
G = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/studies/gzsweep")
HERE = Path(__file__).resolve().parent
runs = {}
for line in (HERE / "runs.txt").read_text().splitlines():
    k, pol, rb, label = line.split()
    runs[(int(k), label)] = {
        "name": pol,
        **({"rulebook": rb.replace("/amr_negotiation", R)} if rb != "-" else {}),
    }
rows = []
for (k, label), pol in sorted(runs.items()):
    f = (glob.glob(f"{G}/out/{label}/gz_s{k}_*_s{k}.json") or ["missing"])[0]
    if not os.path.exists(f):
        continue
    g = json.loads(Path(f).read_text())
    sc = load_scenario(HERE / f"scen/gz_s{k}.yaml")
    d = sim2d.run_episode(sc, pol, seed=k)
    rows.append(
        {
            "k": k,
            "policy": label,
            "bay": sc.bays[0]["x"] if isinstance(sc.bays[0], dict) else None,
            "gz_ok": g["success"],
            "d_ok": d["success"],
            "gz_coll": g["collision"],
            "gz_y": g["yielder"],
            "d_y": d.get("yielder"),
            "gz_ms": g["makespan"],
            "d_ms": d.get("makespan"),
            "gz_rev": sum(a["reverse_dist"] for a in g["agents"].values()),
            "d_rev": float(sum(a["reverse_dist"] for a in d["agents"].values())),
            "gz_msgs": g["msgs"],
            "gz_minc": g["min_clearance"],
        }
    )
(HERE.parents[1] / "data/tables/gazebo/gazebo_sweep.json").write_text(json.dumps(rows, indent=1))
by = collections.defaultdict(list)
for r in rows:
    by[r["policy"]].append(r)
print(
    "| policy | n | Gazebo success | 2D success | Gazebo collisions | same yielder | makespan Gazebo − 2D, mean (sd) | reverse dist Gazebo / 2D (m) |"
)
print("|---|---|---|---|---|---|---|---|")
for p, v in by.items():
    dm = [r["gz_ms"] - r["d_ms"] for r in v if r["gz_ok"] and r["d_ok"]]
    print(
        f"| {p} | {len(v)} | {sum(r['gz_ok'] for r in v)} | {sum(r['d_ok'] for r in v)} | {sum(r['gz_coll'] for r in v)} | {sum(r['gz_y'] == r['d_y'] for r in v)} | {st.mean(dm):+.1f} ({st.pstdev(dm):.1f}) s | {st.mean(r['gz_rev'] for r in v):.2f} / {st.mean(r['d_rev'] for r in v):.2f} |"
    )
for r in rows:
    if r["gz_y"] != r["d_y"] or r["gz_ok"] != r["d_ok"]:
        print("DIFF", r)
