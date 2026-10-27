"""Gazebo round 2: convoy, T-junction (stem start / stem goal) and impaired-comms scenarios.

Writes experiments/gazebo/scen_r2/gz_<kind>_s<k>.yaml and experiments/gazebo/runs_r2.txt. Start delays of the non-leading robots are
jittered per seed. Run from the repo root: python experiments/gazebo/make_scen_r2.py
"""
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KINDS = {
    "convoy": ("corridor_convoy.yaml", {}),
    "tj": ("corridor_tjunction.yaml", {}),
    "tjgoal": ("corridor_tjunction_goal.yaml", {}),
    "comms": ("corridor_single_bay.yaml", {"comms": {"latency": 0.5, "jitter": 0.2, "loss": 0.5, "rate": 5.0}}),
}
POLICIES = [("fixed_priority", "-", "fixed_priority"),
            ("rule_based", "/amr_negotiation/configs/rulebooks/default.yaml", "rules_default"),
            ("cost_bid", "-", "cost_bid")]
SEEDS = range(6)


def main():
    out = HERE / "scen_r2"
    out.mkdir(exist_ok=True)
    runs = []
    for kind, (fname, extra) in KINDS.items():
        base = yaml.safe_load((ROOT / "configs" / "scenarios" / fname).read_text())
        for k in SEEDS:
            rng = np.random.default_rng(1000 + k)
            sc = {**base, **extra, "name": f"gz_{kind}_s{k}"}
            sc["agents"] = [dict(a) for a in base["agents"]]
            for a in sc["agents"][1:]:
                d = a.get("start_delay", 0.0)
                a["start_delay"] = round(float(rng.uniform(0.5 * d, 1.5 * d + 2.0)), 3)
            (out / f"gz_{kind}_s{k}.yaml").write_text(yaml.safe_dump(sc, sort_keys=False))
            runs += [f"{k} {p} {rb} {lab} gz_{kind}_s{k}" for p, rb, lab in POLICIES]
    (HERE / "runs_r2.txt").write_text("\n".join(runs) + "\n")
    print(len(runs), "runs")


if __name__ == "__main__":
    main()
