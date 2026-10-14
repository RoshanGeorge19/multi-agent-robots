"""Figures for the draft paper. Values in fig_results are copied from studies/REPORT*.md."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from amr_negotiation import load_scenario
from amr_negotiation.viz import draw_map

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "fig"
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
    sig = [0, 0.1, 0.25, 0.5, 1.0]
    a1.plot(sig, [0, 0.2, 1.5, 3.3, 4.5], "o-", label="cost_bid, noisy bids")
    a1.axhline(3.1, ls="--", c="tab:green", label="closest-refuge rule")
    a1.axhline(6.4, ls=":", c="tab:red", label="fixed priority / default rulebook")
    a1.set_xlabel(r"bid noise $\sigma$ (log-normal)", fontsize=8)
    a1.set_ylabel("excess delay vs. oracle [s]", fontsize=8)
    a1.legend(fontsize=6.5)
    a1.set_title("(a) symmetric robots, single bay", fontsize=8, loc="left")
    pols = ["fixed\npriority", "default\nrulebook", "cost_bid", "unweighted\noracle"]
    a2.bar(pols, [27.0, 3.6, 0.8, 7.1], color=["tab:red", "tab:green", "tab:blue", "0.6"])
    a2.set_ylabel("weighted excess delay [s]", fontsize=8)
    a2.set_title("(b) asymmetric urgency / payload / speed", fontsize=8, loc="left")
    for ax in (a1, a2):
        ax.tick_params(labelsize=7)
        ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(OUT / "results.pdf")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    fig_scenarios()
    fig_results()
