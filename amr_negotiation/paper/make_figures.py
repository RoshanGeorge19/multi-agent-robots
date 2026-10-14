"""Figures for the paper. fig_results is computed from studies/results_raw/*.csv.gz."""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from amr_negotiation import load_scenario
from amr_negotiation.viz import draw_map

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "fig"
RAW = ROOT / "studies" / "results_raw"
sys.path.insert(0, str(ROOT / "studies"))
from analyse_helpers import ci, paired

COL = {"A": "tab:blue", "B": "tab:orange", "C": "tab:green", "S": "tab:red"}


def fig_scenarios():
    names = [("corridor_single_bay", "(a) single bay"), ("corridor_two_bays", "(b) two bays"),
             ("corridor_convoy", "(c) convoy, 2 v 1"), ("corridor_tjunction_goal", "(d) T-junction (deep side branch)")]
    fig, axs = plt.subplots(4, 1, figsize=(7.0, 6.4))
    for ax, (n, title) in zip(axs, names):
        sc = load_scenario(ROOT / "scenarios" / f"{n}.yaml")
        draw_map(ax, sc)
        ax.set_xlabel("")
        ax.set_ylabel("y [m]", fontsize=7)
        ax.tick_params(labelsize=7)
        for a in sc.agents:
            ref = next((r for r in sc.refuges() if r.id == getattr(a, "start_refuge", None)), None)
            x, y = (ref.x, ref.park_y) if ref else (a.start_x, 0.0)
            ax.add_patch(plt.Circle((x, y), sc.robot.radius, fc=COL.get(a.id, "0.5"), alpha=0.6, ec="k"))
            ax.text(x, y, a.id, ha="center", va="center", fontsize=7, weight="bold")
            d = 1 if a.goal_x > a.start_x else -1
            if not ref:
                ax.annotate("", (x + 0.7 * d, y), (x + 0.3 * d, y), arrowprops={"arrowstyle": "->", "lw": 1})
        ax.set_title(title, fontsize=8, loc="left")
    axs[-1].set_xlabel("x [m]", fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "scenarios.pdf")


def fig_results():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.0, 2.4))
    p7 = paired(pd.read_csv(RAW / "S7_noisy_bids.csv.gz"))
    cb = p7[p7.label == "cost_bid"].groupby("bid_sigma").regret
    a1.errorbar(cb.mean().index, cb.mean().values, yerr=cb.apply(ci).values, fmt="o-", capsize=2, label="cost_bid, noisy bids")
    prox = p7[p7.label == "rules_proximity"].regret
    a1.axhline(prox.mean(), ls="--", c="tab:green", label="closest-refuge rule")
    p1 = paired(pd.read_csv(RAW / "S1_baseline.csv.gz"))
    a1.axhline(p1[p1.label == "fixed_priority"].regret.mean(), ls=":", c="tab:red", label="fixed priority / default rulebook")
    a1.set_xlabel(r"bid noise $\sigma$ (log-normal)", fontsize=8)
    a1.set_ylabel("excess delay [s]", fontsize=8)
    a1.legend(fontsize=6.5)
    a1.set_title("(a) symmetric robots, single bay", fontsize=8, loc="left")
    p2 = paired(pd.read_csv(RAW / "S2_asymmetry.csv.gz"), ref="oracle_w", metric="wdelay")
    labs = [("fixed_priority", "fixed\npriority", "tab:red"), ("rules_default", "default\nrulebook", "tab:green"),
            ("cost_bid", "cost_bid", "tab:blue"), ("oracle", "unweighted\nbest forced", "0.6")]
    g = [p2[p2.label == lab].regret for lab, _, _ in labs]
    a2.bar([n for _, n, _ in labs], [x.mean() for x in g], yerr=[ci(x) for x in g], capsize=2, color=[c for _, _, c in labs])
    a2.set_ylabel("weighted excess delay [s]", fontsize=8)
    a2.set_title("(b) asymmetric urgency / payload / speed", fontsize=8, loc="left")
    for ax in (a1, a2):
        ax.tick_params(labelsize=7)
        ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(OUT / "results.pdf")
    print("S7 cost_bid", cb.mean().round(2).to_dict(), "prox", round(prox.mean(), 2), "S2", [round(x.mean(), 2) for x in g])


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    fig_scenarios()
    fig_results()
