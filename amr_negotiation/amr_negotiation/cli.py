"""`amrneg-run`: run one episode, print metrics, optionally save JSON / plot / GIF."""

from __future__ import annotations

import argparse
import json

from .geometry import deep_update, load_scenario, scenario_from_dict
from .policies import ALL_POLICIES
from .sim2d import run_episode, run_oracle, scenario_to_dict

SUMMARY_KEYS = ["policy", "success", "deadlock", "collision", "makespan", "total_delay",
                "max_delay", "min_clearance", "yielder", "refuge", "rule", "n_yields", "msgs"]


def parse_set(items):
    """Turn ['comms.loss=0.2', 'bays.0.x=3'] into a nested override dict."""
    out: dict = {}
    for it in items or []:
        key, val = it.split("=", 1)
        cur = out
        parts = key.split(".")
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = json.loads(val) if val[:1] in "[{0123456789-tfn" else val
    return out


def make_policy(name, rulebook=None, yielder=None):
    p = {"name": name}
    if rulebook:
        p["rulebook"] = rulebook
    if yielder:
        p["yielder"] = yielder
    return p


def apply_overrides(sc, overrides):
    if not overrides:
        return sc
    d = scenario_to_dict(sc)
    for k, v in overrides.items():
        if k == "bays" and isinstance(v, dict):
            for idx, bv in v.items():
                d["bays"][int(idx)].update(bv)
        elif k == "agents" and isinstance(v, dict):
            for idx, av in v.items():
                d["agents"][int(idx)].update(av)
        elif isinstance(v, dict) and isinstance(d.get(k), dict):
            d[k] = deep_update(d[k], v)
        else:
            d[k] = v
    return scenario_from_dict(d)


def run(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("scenario")
    ap.add_argument("--policy", default="rule_based", choices=ALL_POLICIES + ("oracle",))
    ap.add_argument("--rulebook", help="rulebook YAML for policy=rule_based")
    ap.add_argument("--yielder", help="agent id for policy=forced")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--set", nargs="*", help="scenario overrides, e.g. comms.loss=0.3 bays.0.x=2.5")
    ap.add_argument("--pset", nargs="*", help="policy parameters, e.g. llm.mode=agents llm.model=qwen2.5-7b")
    ap.add_argument("--json", help="write full result JSON here")
    ap.add_argument("--plot", help="write trajectory + x-t plot (PNG)")
    ap.add_argument("--gif", help="write animation (GIF)")
    ap.add_argument("--events", action="store_true", help="print the event log")
    a = ap.parse_args(argv)
    sc = apply_overrides(load_scenario(a.scenario), parse_set(a.set))
    record = bool(a.plot or a.gif or a.json)
    if a.policy == "oracle":
        res = run_oracle(sc, seed=a.seed, record=record)
    else:
        pol = deep_update(make_policy(a.policy, a.rulebook, a.yielder), parse_set(a.pset))
        res = run_episode(sc, pol, seed=a.seed, record=record)
    for k in SUMMARY_KEYS:
        v = res.get(k)
        print(f"{k:>14}: {round(v, 3) if isinstance(v, float) else v}")
    if a.events:
        for e in res["events"]:
            print("  ", e)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(res, f, indent=1, default=str)
    if a.plot or a.gif:
        from . import viz

        if a.plot:
            viz.plot_episode(sc, res, a.plot)
        if a.gif:
            viz.animate_episode(sc, res, a.gif)
    return res


def run_main(argv=None) -> int:
    res = run(argv)
    return 0 if res["success"] else 1


if __name__ == "__main__":
    raise SystemExit(run_main())
