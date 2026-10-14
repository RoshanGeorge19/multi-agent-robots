"""Compare every Gazebo run (gazebo/runs.txt + runs_r2.txt) with a 2D-sim rerun of the same scenario, policy and seed.

Usage: python studies/analyse_gazebo_main.py GZSWEEP_DIR [CODE_LABEL]
GZSWEEP_DIR is laid out as by gazebo/run_one.sh (out/<label>/<scenario>_*.json). Writes report/gazebo_main_runs.csv
and prints a markdown summary per scenario kind and policy.
"""

import collections
import csv
import glob
import json
import math
import statistics as st
import sys
from pathlib import Path

from amr_negotiation import sim2d
from amr_negotiation.geometry import load_scenario

HERE = Path(__file__).resolve().parent
R = str(HERE.parent)
G = Path(sys.argv[1])
CODE = sys.argv[2] if len(sys.argv) > 2 else "main"


def kind(scn: str) -> str:
    return "corridor" if scn.startswith("gz_s") else scn.split("_")[1]


def yielders(res: dict) -> str:
    return "".join(sorted(i for i, a in res["agents"].items() if a.get("yields")))


def wilson_upper(k: int, n: int, z: float = 1.96) -> float:
    p = k / n
    return (p + z * z / (2 * n) + z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


runs = []
for fname in ("runs.txt", "runs_r2.txt"):
    for line in (HERE / "gazebo" / fname).read_text().split("\n"):
        if not line.strip():
            continue
        k, pol, rb, label, *scn = line.split()
        scn = scn[0] if scn else f"gz_s{k}"
        sub = "scen" if fname == "runs.txt" else "scen_r2"
        policy = {"name": pol, **({"rulebook": rb.replace("/amr_negotiation", R)} if rb != "-" else {})}
        runs.append((int(k), label, scn, HERE / "gazebo" / sub / f"{scn}.yaml", policy, kind(scn)))

rows = []
if (G / "runs.txt").exists():  # all-study batch (gazebo/run_case.sh): idx seed label scenario policy_file group
    for line in (G / "runs.txt").read_text().split("\n"):
        f = line.split()
        if len(f) == 6:
            _, k, label, scn, pf, grp = f
            policy = json.loads((G / "scen" / "pol" / pf).read_text().replace("/amr_negotiation", R))
            runs.append((int(k), label, scn, G / "scen" / f"{scn}.yaml", policy, grp))
for k, label, scn, path, policy, grp in runs:
    f = sorted(glob.glob(str(G / "out" / label / f"{scn}_*.json")))
    if not f:
        continue
    g = json.loads(Path(f[0]).read_text())
    d = sim2d.run_episode(load_scenario(path), policy, seed=k)
    rows.append({
        "code": CODE, "kind": grp, "scenario": scn, "policy": label, "seed": k,
        "gz_success": g["success"], "gz_deadlock": g["deadlock"], "gz_collision": g["collision"],
        "d2_success": d["success"], "d2_deadlock": d["deadlock"], "d2_collision": d["collision"],
        "gz_yielder": g.get("yielder"), "d2_yielder": d.get("yielder"),
        "gz_refuge": g.get("refuge"), "d2_refuge": d.get("refuge"),
        "gz_all_yielders": yielders(g), "d2_all_yielders": yielders(d),
        "gz_makespan": round(g["makespan"], 3) if g["success"] else None,
        "d2_makespan": round(d["makespan"], 3) if d["success"] else None,
        "gz_reverse": round(sum(a["reverse_dist"] for a in g["agents"].values()), 3),
        "d2_reverse": round(float(sum(a["reverse_dist"] for a in d["agents"].values())), 3),
        "gz_min_clearance": round(g["min_clearance"], 3),
    })

out = HERE / "report" / "gazebo_main_runs.csv"
with out.open("w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

by = collections.defaultdict(list)
for r in rows:
    by[(r["kind"], r["policy"])].append(r)
print(f"{len(rows)} of {len(runs)} runs found; per-run table: {out.relative_to(HERE.parent)}\n")
print("| kind | policy | n | Gazebo success | deadlock | collision | 2D success | same first yielder | same refuge "
      "| same set of yielders | makespan Gazebo − 2D, mean (sd) [s] |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for (kd, p), v in sorted(by.items()):
    dm = [r["gz_makespan"] - r["d2_makespan"] for r in v if r["gz_success"] and r["d2_success"]]
    ms = f"{st.mean(dm):+.1f} ({st.pstdev(dm):.1f})" if dm else "–"
    n = len(v)
    print(f"| {kd} | {p} | {n} | {sum(r['gz_success'] for r in v)} | {sum(r['gz_deadlock'] for r in v)} "
          f"| {sum(r['gz_collision'] for r in v)} | {sum(r['d2_success'] for r in v)} "
          f"| {sum(r['gz_yielder'] == r['d2_yielder'] for r in v)}/{n} "
          f"| {sum(r['gz_refuge'] == r['d2_refuge'] for r in v)}/{n} "
          f"| {sum(r['gz_all_yielders'] == r['d2_all_yielders'] for r in v)}/{n} | {ms} |")
neg = [r for r in rows if r["policy"] != "reactive"]
c = sum(r["gz_collision"] for r in neg)
print(f"\nNegotiating policies: {c} collisions in {len(neg)} Gazebo runs "
      f"(Wilson 95% upper bound {100 * wilson_upper(c, len(neg)):.1f}%).")
for r in rows:
    if (r["gz_success"], r["gz_yielder"], r["gz_all_yielders"]) != (r["d2_success"], r["d2_yielder"], r["d2_all_yielders"]):
        print("DIFF", {k: r[k] for k in ("scenario", "policy", "gz_success", "d2_success", "gz_yielder", "d2_yielder",
                                         "gz_all_yielders", "d2_all_yielders", "gz_makespan", "d2_makespan")})
