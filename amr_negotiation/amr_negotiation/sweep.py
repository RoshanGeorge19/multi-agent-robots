"""`amrneg-sweep`: Monte Carlo sweep of policies x scenario variations -> CSV + summary plots.

Sweep file format (YAML):
    scenario: scenarios/corridor_single_bay.yaml
    seeds: 20
    policies:
      - {name: reactive}
      - {name: rule_based, rulebook: rulebooks/default.yaml, label: rules_default}
      - {name: cost_bid}
      - {name: oracle}
    grid:                       # full factorial over these overrides (dotted keys)
      bays.0.x: [1.5, 4.0, 6.5]
      comms.loss: [0.0, 0.3]
    random:                     # per-seed uniform jitter applied on top
      agents.1.start_delay: [0.0, 6.0]
"""

from __future__ import annotations

import argparse
import csv
import itertools
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import yaml

from .cli import apply_overrides, parse_set
from .geometry import load_scenario
from .sim2d import run_episode, run_oracle

COLUMNS = ["label", "policy", "seed", "success", "deadlock", "collision", "makespan", "total_delay",
           "max_delay", "min_clearance", "yielder", "refuge", "rule", "n_yields", "msgs",
           "msgs_dropped", "time_to_decide", "agreement", "reverse_dist"]


def _overrides(assign: dict) -> dict:
    return parse_set([f"{k}={v}" for k, v in assign.items()])


def _job(args):
    scen_path, base_dir, pol, assign, seed = args
    sc = apply_overrides(load_scenario(scen_path), _overrides(assign))
    pol = dict(pol)
    label = pol.pop("label", pol["name"])
    if pol.get("rulebook") and not os.path.isabs(pol["rulebook"]):
        pol["rulebook"] = str(Path(base_dir) / pol["rulebook"])
    res = run_oracle(sc, seed=seed) if pol["name"] == "oracle" else run_episode(sc, pol, seed=seed)
    row = {k: res.get(k) for k in COLUMNS}
    row.update(label=label, policy=pol["name"], seed=seed,
               reverse_dist=sum(a["reverse_dist"] for a in res["agents"].values()))
    row.update({k: v for k, v in assign.items()})
    return row


def build_jobs(spec, base_dir):
    scen = str(Path(base_dir) / spec["scenario"])
    grid = spec.get("grid") or {}
    keys = list(grid)
    rnd = spec.get("random") or {}
    jobs = []
    for combo in itertools.product(*[grid[k] for k in keys]) if keys else [()]:
        for seed in range(spec.get("seeds", 10)):
            rng = np.random.default_rng(10_000 + seed)
            assign = dict(zip(keys, combo))
            assign.update({k: round(float(rng.uniform(*v)), 3) for k, v in rnd.items()})
            for pol in spec["policies"]:
                jobs.append((scen, base_dir, pol, assign, seed))
    return jobs, keys


def summarise(rows, keys):
    groups: dict = {}
    for r in rows:
        groups.setdefault(tuple([r["label"]] + [r.get(k) for k in keys]), []).append(r)
    out = []
    for g, rs in groups.items():
        ok = [r for r in rs if r["success"]]
        d = dict(zip(["label"] + keys, g))
        d.update(n=len(rs), success_rate=len(ok) / len(rs),
                 deadlock_rate=sum(bool(r["deadlock"]) for r in rs) / len(rs),
                 collision_rate=sum(bool(r["collision"]) for r in rs) / len(rs),
                 mean_total_delay=float(np.mean([r["total_delay"] for r in ok])) if ok else None,
                 mean_makespan=float(np.mean([r["makespan"] for r in ok])) if ok else None,
                 mean_reverse=float(np.mean([r["reverse_dist"] for r in ok])) if ok else None,
                 mean_msgs=float(np.mean([r["msgs"] for r in rs])))
        out.append(d)
    return out


def plot_summary(summary, keys, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = list(dict.fromkeys(s["label"] for s in summary))
    xkey = keys[0] if keys else None
    fig, axs = plt.subplots(1, 3, figsize=(14, 4))
    for lab in labels:
        ss = [s for s in summary if s["label"] == lab]
        if xkey:
            for other in sorted({tuple(s[k] for k in keys[1:]) for s in ss}):
                sub = sorted([s for s in ss if tuple(s[k] for k in keys[1:]) == other], key=lambda s: s[xkey])
                name = lab + ("" if not other else " " + ",".join(f"{k}={v}" for k, v in zip(keys[1:], other)))
                xs = [s[xkey] for s in sub]
                axs[0].plot(xs, [s["mean_total_delay"] or np.nan for s in sub], "o-", label=name)
                axs[1].plot(xs, [s["success_rate"] for s in sub], "o-", label=name)
                axs[2].plot(xs, [s["mean_reverse"] or np.nan for s in sub], "o-", label=name)
        else:
            axs[0].bar(lab, ss[0]["mean_total_delay"] or 0)
            axs[1].bar(lab, ss[0]["success_rate"])
            axs[2].bar(lab, ss[0]["mean_reverse"] or 0)
    for ax, t in zip(axs, ["mean total delay [s] (successful runs)", "success rate", "mean distance reversed [m]"]):
        ax.set_title(t, fontsize=9)
        ax.grid(alpha=0.3)
        if xkey:
            ax.set_xlabel(xkey)
    if xkey:
        axs[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def run_sweep(argv=None) -> list[dict]:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sweep")
    ap.add_argument("--out", default="results")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--seeds", type=int, help="override number of seeds")
    a = ap.parse_args(argv)
    with open(a.sweep) as f:
        spec = yaml.safe_load(f)
    if a.seeds:
        spec["seeds"] = a.seeds
    base_dir = str(Path(a.sweep).resolve().parent.parent)
    jobs, keys = build_jobs(spec, base_dir)
    print(f"{len(jobs)} episodes on {a.workers} workers")
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(_job, jobs, chunksize=4))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    name = Path(a.sweep).stem
    cols = COLUMNS + [k for k in rows[0] if k not in COLUMNS]
    with open(out / f"{name}_episodes.csv", "w", newline="") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)
    summary = summarise(rows, keys)
    with open(out / f"{name}_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, list(summary[0]))
        w.writeheader()
        w.writerows(summary)
    plot_summary(summary, keys, out / f"{name}_summary.png")
    for s in summary:
        print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in s.items()})
    return summary


def main(argv=None) -> int:
    run_sweep(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
