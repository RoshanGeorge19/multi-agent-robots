"""Explore mode: robots start without bays, add each bay once it is within lidar range, and share their map
never / in every BID / only once their own sensor has detected the other robot (corridor_two_bays).

Run from amr_negotiation/: python studies/explore_map.py [OUT_CSV]"""
import collections
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from amr_negotiation import sim2d
from amr_negotiation import sweep as SW

ROOT = Path(__file__).resolve().parents[1]
MAPS = {
    "full": {},
    "explore_no_share": {"explore": True},
    "explore_share_always": {"explore": True, "share_map": True},
    "explore_share_on_detect": {"explore": True, "share_map": True, "share_on_detect": True},
    "explore_share_on_detect_hold": {"explore": True, "share_map": True, "share_on_detect": True, "hold_for_map": True},
}
POLICIES = ["fixed_priority", "rules_default", "cost_bid"]


def run(a):
    mp_, pol, loss, rng_, seed = a
    ov = {"comms.loss": loss, "agents.1.start_delay": float(np.random.default_rng(seed).uniform(0, 8))}
    sc = SW.apply_overrides(SW.load_scenario(ROOT / "scenarios/corridor_two_bays.yaml"), SW._overrides(ov))
    sc.agent_params = {**MAPS[mp_], "detect_range": rng_}
    p = {"name": pol} if pol != "rules_default" else {"name": "rule_based", "rulebook": str(ROOT / "rulebooks/default.yaml")}
    r = sim2d.run_episode(sc, p, seed=seed, record=True)
    ev = r["events"]
    first_dec = min((e["t"] for e in ev if e["event"] == "decision"), default=None)
    first_conf = min((e["t"] for e in ev if e["event"] == "conflict_detected"), default=None)
    shared = [e["t"] for e in ev if e["event"] == "refuge_learned" and e["source"] != "sensed"]
    d = r["decisions"][0] if r["decisions"] else {}
    return {"map": mp_, "policy": pol, "loss": loss, "detect_range": rng_, "seed": seed, "success": r["success"],
            "deadlock": r["deadlock"], "collision": r["collision"], "total_delay": r.get("total_delay"),
            "yielder": d.get("yielder"), "refuge": d.get("refuge"),
            "n_shared": len(shared), "shared_before_decision": bool(shared and first_dec is not None and min(shared) <= first_dec),
            "t_conflict": first_conf, "t_decision": first_dec,
            "time_to_decision": None if first_dec is None or first_conf is None else first_dec - first_conf,
            "n_hold_timeout": sum(e["event"] == "hold_timeout" for e in ev),
            "n_sensed": sum(e["event"] == "refuge_learned" and e["source"] == "sensed" for e in ev)}


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "studies/results_raw/explore_map.csv.gz"
    jobs = [(m, p, lo, dr, s) for m in MAPS for p in POLICIES for lo in (0.0, 0.5) for dr in (6.0, 3.5) for s in range(30)]
    with mp.Pool(8) as pool:
        df = pd.DataFrame(pool.map(run, jobs))
    df.to_csv(out, index=False)
    key = ["policy", "loss", "detect_range", "seed"]
    base = df[df["map"] == "full"].set_index(key)["total_delay"]
    df["extra_vs_full"] = df.total_delay.values - base.reindex(pd.MultiIndex.from_frame(df[key])).values
    print(f"{len(df)} episodes -> {out}\n")
    print("| map | policy | loss | detect range [m] | success | deadlock | collision | mean delay [s] | extra vs full, mean ± 95% CI [s] | map shared before decision | time to decision [s] | hold timeouts |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for (m, p, lo, dr), g in df.groupby(["map", "policy", "loss", "detect_range"], sort=False):
        ok = g[g.success]
        e = ok.extra_vs_full.dropna()
        ci = 1.96 * e.std(ddof=1) / np.sqrt(len(e)) if len(e) > 1 else float("nan")
        sb = f"{g.shared_before_decision.sum()}/{len(g)}" if m.startswith("explore_share") else "–"
        print(f"| {m} | {p} | {lo:.0%} | {dr:.1f} | {g.success.sum()}/{len(g)} | {g.deadlock.sum()} | {g.collision.sum()} | "
              f"{ok.total_delay.mean():.1f} | {e.mean():+.1f} ± {ci:.1f} | {sb} | "
              f"{g.time_to_decision.mean():.1f} | {int((g.n_hold_timeout > 0).sum())} |")
    c = collections.Counter(zip(df["map"], df.collision))
    print("\ncollisions per map:", {m: c[(m, True)] for m in MAPS})
