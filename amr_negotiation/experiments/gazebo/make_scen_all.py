"""Gazebo cases for every 2D study (reduced grid), on top of runs.txt / runs_r2.txt.

Writes scen_all/<case>.yaml, scen_all/pol/<label>.json and runs_all.txt with lines
`seed label scenario policy_file|-`. Run from the repo root: python experiments/gazebo/make_scen_all.py
(after make_scen_r2.py, which writes the convoy scenarios used here)."""
import copy
import json
from pathlib import Path

import numpy as np
import yaml

from amr_negotiation.geometry import deep_update

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "scen_all"
RB = "/amr_negotiation/configs/rulebooks/default.yaml"
P = {  # label -> policy (rulebook/table paths are inside the Docker image)
    "fixed_priority": {"name": "fixed_priority"}, "rules_default": {"name": "rule_based", "rulebook": RB},
    "cost_bid": {"name": "cost_bid"}, "forced_A": {"name": "forced", "yielder": "A"},
    "forced_B": {"name": "forced", "yielder": "B"}, "reservation": {"name": "reservation", "rulebook": RB},
    "clarke": {"name": "clarke"}, "group_bid": {"name": "group_bid"},
    "learned": {"name": "learned", "table": "/amr_negotiation/data/tables/classical/learned_table.json"},
    "cost_bid_sigma0.5": {"name": "cost_bid", "bid_sigma": 0.5}, "cost_bid_sigma1.0": {"name": "cost_bid", "bid_sigma": 1.0},
    "clarke_Ax0.5": {"name": "clarke", "report_scale": {"A": 0.5}},
    "clarke_Bx0.5": {"name": "clarke", "report_scale": {"B": 0.5}},
    "clarke_ABx0.5": {"name": "clarke", "report_scale": {"A": 0.5, "B": 0.5}},
}
STD = ["fixed_priority", "rules_default", "cost_bid"]
TWO = ["fixed_priority", "cost_bid"]


def load(path):
    return yaml.safe_load(Path(path).read_text())


def two_bays(seed, **upd):
    d = load(ROOT / "configs/scenarios/corridor_two_bays.yaml")
    d["agents"][1]["start_delay"] = round(float(np.random.default_rng(seed).uniform(0, 8)), 3)
    return deep_update(d, upd)


def main():
    (OUT / "pol").mkdir(parents=True, exist_ok=True)
    for lab, pol in P.items():
        (OUT / "pol" / f"{lab}.json").write_text(json.dumps(pol))
    runs = []

    def case(name, data, labels, seed, group):
        data = copy.deepcopy(data)
        data["name"] = name
        (OUT / f"{name}.yaml").write_text(yaml.safe_dump(data, sort_keys=True))
        runs.extend(f"{seed} {lab} {name} {lab}.json {group}" for lab in labels)

    for k in range(10):  # S1 corridor: the policies and forced yielders the first sweep did not cover
        case(f"gz_s{k}", load(HERE / "scen" / f"gz_s{k}.yaml"),
             ["forced_A", "forced_B", "reservation", "clarke", "learned"], k, "S1")
    for k in range(6):
        base = load(HERE / "scen" / f"gz_s{k}.yaml")
        urg, slow = copy.deepcopy(base), copy.deepcopy(base)
        urg["agents"][1]["urgency"] = 3.0
        slow["agents"][1]["v_max"] = 0.13
        case(f"gz_urg_s{k}", urg, STD + ["forced_A", "forced_B"], k, "S2_urgent")
        case(f"gz_slow_s{k}", slow, STD + ["forced_A", "forced_B"], k, "S2_slow")
        case(f"gz_noise_s{k}", base, ["cost_bid_sigma0.5", "cost_bid_sigma1.0"], k, "S7")
        case(f"gz_pay_s{k}", base, ["clarke_Ax0.5", "clarke_Bx0.5", "clarke_ABx0.5"], k, "S9")
        ext = deep_update(base, {"comms": {"loss": 0.9, "latency": 2.0}, "agent_params": {"detect_range": 1.5}})
        case(f"gz_ext_s{k}", ext, TWO, k, "S8b")
        case(f"gz_extoff_s{k}", deep_update(ext, {"agent_params": {"commit": False, "state_guard": False,
                                                                    "bay_check": False}}), TWO, k, "S8c_all_off")
        conv = load(HERE / "scen_r2" / f"gz_convoy_s{k}.yaml")
        case(f"gz_convoy_s{k}", conv, ["group_bid"], k, "convoy")
        conv["agents"][2]["urgency"] = 3.0
        case(f"gz_convoyurg_s{k}", conv, ["fixed_priority", "group_bid"], k, "convoy_B_urgent")
        case(f"gz_2bay_s{k}", two_bays(k), STD, k, "S4")
        case(f"gz_blk_s{k}", two_bays(k, blocked_bays=["bay1"]), STD, k, "wrong_map")
        asym = two_bays(k)
        asym["agents"][0]["known_refuges"], asym["agents"][1]["known_refuges"] = ["bay0"], ["bay1"]
        case(f"gz_asym_s{k}", asym, TWO, k, "asym_own")
        case(f"gz_asymshare_s{k}", deep_update(asym, {"agent_params": {"share_map": True}}), TWO, k, "asym_share")
        case(f"gz_2bay35_s{k}", two_bays(k, agent_params={"detect_range": 3.5}), TWO, k, "explore_full_3.5")
        for tag, ap in (("none", {}), ("all", {"share_map": True}), ("det", {"share_map": True, "share_on_detect": True}),
                        ("hold", {"share_map": True, "share_on_detect": True, "hold_for_map": True})):
            for rng in (6.0, 3.5):
                case(f"gz_exp{tag}{int(rng * 10)}_s{k}", two_bays(k, agent_params={"explore": True, "detect_range": rng, **ap}),
                     TWO, k, f"explore_{tag}_{rng}")
    for k in range(4):
        case(f"gz_2bayalt_s{k}", two_bays(k, bays=None) | {"bays": [{"x": 3.0, "side": 1, "width": 0.8, "depth": 0.6},
                                                                    {"x": 7.0, "side": 1, "width": 0.8, "depth": 0.6}]},
             STD, k, "S4_same_side")
    (HERE / "runs_all.txt").write_text("\n".join(runs) + "\n")
    print(f"{len(runs)} runs, {len(list(OUT.glob('*.yaml')))} scenarios")


if __name__ == "__main__":
    main()
