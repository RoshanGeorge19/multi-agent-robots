"""Generate all 7 vector figures for Paper 1 (12-14 page journal version).

Reads directly from data/raw/classical/, data/tables/classical/, data/tables/gazebo/,
configs/scenarios/, and media/gazebo_final/. Run from repo root:
    PYTHONPATH=$PWD python3 papers/paper1_journal/make_figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "fig"
RAW = ROOT / "data" / "raw" / "classical"
TAB_G = ROOT / "data" / "tables" / "gazebo"
MEDIA = ROOT / "media" / "gazebo_final"

sys.path[:0] = [str(ROOT), str(ROOT / "experiments" / "analysis")]
from amr_negotiation import load_scenario, sim2d
from amr_negotiation.geometry import deep_update, scenario_from_dict
from amr_negotiation.viz import draw_map
from analyse_helpers import ci, paired
from analyse_payments import utilities

plt.rcParams.update({
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "font.size": 8,
    "axes.titlesize": 8.5,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 6.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

# Colorblind-safe Okabe-Ito / IEEE palette
PAL = {
    "reactive": "#7f7f7f",
    "reservation": "#cc79a7",
    "fixed_priority": "#d55e00",
    "rules_default": "#009e73",
    "rules_proximity": "#56b4e9",
    "learned": "#e69f00",
    "cost_bid": "#0072b2",
    "group_bid": "#004c7a",
    "clarke": "#0072b2",
    "side_oracle": "#333333",
    "oracle": "#555555",
}
AGENT_COL = {"A": "#0072b2", "B": "#d55e00", "C": "#009e73", "S": "#cc79a7"}


def fig1_scenarios():
    """Fig. 1: 4 scenario topologies + Gazebo 3D frame + Waffle clearance cross-section."""
    fig = plt.figure(figsize=(7.16, 4.65))
    gs = GridSpec(4, 2, figure=fig, width_ratios=[1.28, 1.05], hspace=0.58, wspace=0.22)

    names = [
        ("corridor_single_bay", "(a) Single-bay corridor (8 m × 0.65 m)"),
        ("corridor_two_bays", "(b) Two-bay corridor (10 m × 0.65 m)"),
        ("corridor_convoy", "(c) Convoy encounter (2 vs. 1, two bays)"),
        ("corridor_tjunction_goal", "(d) T-junction branch (3 robots, exit / turn-in)"),
    ]
    for idx, (n, title) in enumerate(names):
        ax = fig.add_subplot(gs[idx, 0])
        sc = load_scenario(ROOT / "configs" / "scenarios" / f"{n}.yaml")
        draw_map(ax, sc)
        ax.spines["top"].set_visible(True)
        ax.spines["right"].set_visible(True)
        ax.set_xlabel("x [m]" if idx == 3 else "")
        ax.set_ylabel("y [m]", fontsize=7)
        for a in sc.agents:
            ref = next((r for r in sc.refuges() if r.id == getattr(a, "start_refuge", None)), None)
            x, y = (ref.x, ref.park_y) if ref else (a.start_x, 0.0)
            ax.add_patch(plt.Circle((x, y), sc.robot.radius, fc=AGENT_COL.get(a.id, "0.5"), alpha=0.85, ec="k", lw=0.7))
            ax.text(x, y, a.id, ha="center", va="center", fontsize=6.5, color="white", weight="bold")
            d = 1 if a.goal_x > a.start_x else -1
            if not ref:
                ax.annotate("", (x + 0.75 * d, y), (x + 0.28 * d, y),
                            arrowprops={"arrowstyle": "->", "lw": 1.0, "color": AGENT_COL.get(a.id, "k")})
        ax.set_title(title, fontsize=7.8, loc="left", pad=2)

    # (e) Gazebo Harmonic overhead frame showing Waffle A yielded in bay0 while B passes
    ax_gz = fig.add_subplot(gs[0:2, 1])
    im = Image.open(MEDIA / "corridor_cost_bid.webp")
    im.seek(min(48, getattr(im, "n_frames", 1) - 1))
    frame = np.array(im.convert("RGB"))
    h_f, w_f, _ = frame.shape
    frame = frame[int(0.14 * h_f):int(0.86 * h_f), int(0.03 * w_f):int(0.97 * w_f)]
    ax_gz.imshow(frame)
    ax_gz.set_xticks([])
    ax_gz.set_yticks([])
    for sp in ax_gz.spines.values():
        sp.set_visible(True)
        sp.set_linewidth(0.6)
    ax_gz.set_title("(e) Gazebo Harmonic: Waffle A parked in bay0", fontsize=7.8, loc="left", pad=3)

    # (f) Cross-section / clearance geometry schematic
    ax_g = fig.add_subplot(gs[2:4, 1])
    ax_g.set_xlim(-0.92, 0.92)
    ax_g.set_ylim(-0.54, 1.12)
    ax_g.set_aspect("equal")
    corridor_poly = mpatches.Polygon(
        [(-0.78, -0.325), (0.78, -0.325), (0.78, 0.325), (0.40, 0.325),
         (0.40, 0.925), (-0.40, 0.925), (-0.40, 0.325), (-0.78, 0.325)],
        closed=True, fc="#f2f4f7", ec="#222222", lw=1.15
    )
    ax_g.add_patch(corridor_poly)
    ax_g.axhline(-0.275, ls=":", lw=0.8, c="#d55e00", alpha=0.8)
    ax_g.axhline(0.275, ls=":", lw=0.8, c="#d55e00", alpha=0.8)
    # Proceeder Waffle in lane
    ax_g.add_patch(mpatches.Rectangle((-0.1405, -0.153), 0.281, 0.306, fc="#d55e00", alpha=0.82, ec="k", lw=0.8))
    ax_g.add_patch(plt.Circle((0.0, 0.0), 0.25, fill=False, ls="--", ec="#333333", lw=0.7))
    ax_g.text(0.0, 0.0, "P", ha="center", va="center", fontsize=7.2, color="white", weight="bold")
    ax_g.text(0.29, -0.02, "0.281×0.306 m\n(r_sw = 0.25 m)", ha="left", va="center", fontsize=5.7, color="#222222")
    # Yielder Waffle parked in bay (park_y = +0.625 m)
    ax_g.add_patch(mpatches.Rectangle((-0.1405, 0.625 - 0.153), 0.281, 0.306, fc="#0072b2", alpha=0.82, ec="k", lw=0.8))
    ax_g.text(0.0, 0.625, "Y", ha="center", va="center", fontsize=7.2, color="white", weight="bold")
    ax_g.text(0.18, 0.625, "park\ny=+0.625", ha="left", va="center", fontsize=5.6, color="#004c7a")
    # Dimension annotations
    ax_g.annotate("", (-0.70, -0.325), (-0.70, 0.325), arrowprops={"arrowstyle": "<->", "lw": 0.8, "color": "#222"})
    ax_g.text(-0.74, 0.0, "W=0.65 m", rotation=90, ha="right", va="center", fontsize=6.1)
    ax_g.annotate("", (-0.40, 0.98), (0.40, 0.98), arrowprops={"arrowstyle": "<->", "lw": 0.8, "color": "#222"})
    ax_g.text(0.0, 1.01, "bay 0.80 × 0.60 m", ha="center", va="bottom", fontsize=6.0)
    ax_g.text(0.0, -0.44, "2×0.306 m bodies leave 0.038 m (< 2×0.05 m wall margin)", ha="center", va="center", fontsize=5.8, color="#b00000")
    ax_g.set_xticks([-0.5, 0.0, 0.5])
    ax_g.set_yticks([-0.3, 0.0, 0.3, 0.6, 0.9])
    ax_g.set_xlabel("local x [m]", fontsize=7)
    ax_g.set_ylabel("y [m]", fontsize=7)
    ax_g.set_title("(f) Waffle footprint & single-lane clearance", fontsize=7.8, loc="left", pad=3)

    fig.subplots_adjust(left=0.065, right=0.985, top=0.95, bottom=0.08)
    fig.savefig(OUT / "scenarios.pdf")
    plt.close(fig)


def fig2_protocol():
    """Fig. 2: Simulator-agnostic state machine + message/timeline schematic."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.16, 2.55), gridspec_kw={"width_ratios": [1.14, 1.0]})

    # (a) Agent state machine
    ax1.set_xlim(-0.1, 10.7)
    ax1.set_ylim(-0.15, 5.55)
    ax1.axis("off")
    ax1.set_title("(a) Simulator-agnostic agent state machine (20 Hz)", fontsize=8.2, loc="left")

    def box(x, y, w, h, txt, fc="#e8f1f8", ec="#0072b2", fs=6.3, bold=True):
        p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06,rounding_size=0.16", fc=fc, ec=ec, lw=1.0)
        ax1.add_patch(p)
        ax1.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=fs,
                 weight="bold" if bold else "normal", color="#111111")

    def arr(p1, p2, txt="", rad=0.0, tx_off=(0, 0), fs=5.7, col="#333333", ls="-"):
        a = FancyArrowPatch(p1, p2, arrowstyle="->,head_length=3.8,head_width=2.4",
                            connectionstyle=f"arc3,rad={rad}", lw=0.85, color=col, linestyle=ls)
        ax1.add_patch(a)
        if txt:
            mx, my = (p1[0] + p2[0]) / 2 + tx_off[0], (p1[1] + p2[1]) / 2 + tx_off[1]
            ax1.text(mx, my, txt, ha="center", va="center", fontsize=fs, color=col)

    box(0.02, 2.35, 2.02, 0.84, "CRUISE\n(5 Hz STATE)", fs=5.8)
    box(2.82, 2.35, 2.52, 0.84, "NEGOTIATE\n(0.3 s BID + commit)", fc="#fff4e5", ec="#e69f00", fs=5.8)
    box(6.22, 3.85, 2.22, 0.86, "YIELD\n(rev → park → exit)", fc="#e8f1f8", ec="#0072b2", fs=5.8)
    box(6.22, 1.15, 2.22, 0.86, "PROCEED\n(hold → pass)", fc="#e6f5ef", ec="#009e73", fs=5.8)
    box(9.18, 2.42, 1.25, 0.72, "DONE", fc="#eeeeee", ec="#555555", fs=6.1)
    box(2.60, 0.02, 2.75, 0.74, "Reactive Fallback\n(patience U[2,6] s)", fc="#f9eaea", ec="#cc4444", fs=5.8)

    arr((2.10, 2.76), (2.76, 2.76), "conflict\n≤ R_det", tx_off=(0, 0.50), fs=5.5)
    arr((5.40, 2.96), (6.16, 4.14), "mine == Y", rad=0.08, tx_off=(-0.26, 0.40), col="#0072b2", fs=5.6)
    arr((5.40, 2.58), (6.16, 1.62), "mine == P", rad=-0.08, tx_off=(0.42, 0.30), col="#009e73", fs=5.6)
    arr((8.50, 4.18), (9.72, 3.20), "at goal", rad=-0.12, tx_off=(0.38, 0.20), fs=5.6)
    arr((8.50, 1.52), (9.72, 2.36), "at goal", rad=0.12, tx_off=(0.38, -0.20), fs=5.6)
    arr((7.30, 4.77), (1.02, 3.25), "peer passed", rad=0.25, tx_off=(0, 0.44), fs=5.6)
    arr((6.16, 1.30), (0.95, 2.29), "cleared refuge", rad=-0.22, tx_off=(-1.65, -0.42), fs=5.5)
    arr((3.98, 2.29), (3.98, 0.82), "3 s timeout /\ninfeasible", tx_off=(0.82, 0.02), col="#b03030", ls="--", fs=5.5)
    arr((7.20, 1.09), (5.42, 0.38), "60 s stall", rad=-0.14, tx_off=(0.55, -0.28), col="#b03030", ls="--", fs=5.5)
    arr((7.33, 3.79), (7.33, 2.07), "state_guard /\nbay_check", tx_off=(0.92, 0), col="#555555", ls=":", fs=5.5)

    # (b) Constant-speed yield-plan timeline schematic
    ax2.set_xlim(0, 10.2)
    ax2.set_ylim(0, 5.2)
    ax2.axis("off")
    ax2.set_title("(b) Snapshot exchange & kinematic yield timeline", fontsize=8.2, loc="left")

    ax2.text(1.90, 4.12, "Yielder Y", fontsize=6.8, weight="bold", color="#0072b2", ha="right", va="center")
    ax2.text(1.90, 1.72, "Proceeder P", fontsize=6.8, weight="bold", color="#d55e00", ha="right", va="center")

    y_phases = [
        (2.05, 2.05, "Reverse to r\n(|Δx|/v_rev)", "#cfe5f5"),
        (4.10, 0.88, "Turn+\npark", "#9ecae1"),
        (4.98, 1.75, "Wait in r", "#e6eef4"),
        (6.73, 1.02, "Exit+\nturn", "#9ecae1"),
        (7.75, 2.25, "Cruise to goal\n(v_max)", "#cfe5f5"),
    ]
    for x0, w, lbl, c in y_phases:
        ax2.add_patch(mpatches.Rectangle((x0, 3.65), w, 0.95, fc=c, ec="#0072b2", lw=0.75))
        ax2.text(x0 + w / 2, 4.12, lbl, ha="center", va="center", fontsize=5.6)

    p_phases = [
        (2.05, 1.80, "Approach\nx_hold(r)", "#fddbc7"),
        (3.85, 1.13, "Hold", "#fbeee6"),
        (4.98, 1.75, "Pass bay\nto x_pass(r)", "#f4a582"),
        (6.73, 3.27, "Cruise to goal (v_max)", "#fddbc7"),
    ]
    for x0, w, lbl, c in p_phases:
        ax2.add_patch(mpatches.Rectangle((x0, 1.25), w, 0.95, fc=c, ec="#d55e00", lw=0.75))
        ax2.text(x0 + w / 2, 1.72, lbl, ha="center", va="center", fontsize=5.6)

    for xv, lbl, ha_v, dx in [
        (2.05, "t_0: BID\nsnapshots", "center", 0.0),
        (4.98, "t_go =\nmax(t_park, t_hold)", "center", -0.22),
        (6.73, "t_pass:\nlane clear", "left", 0.08),
    ]:
        ax2.plot([xv, xv], [0.95, 4.8], ls="--", lw=0.75, c="#444444")
        ax2.text(xv + dx, 0.72, lbl, ha=ha_v, va="top", fontsize=5.6, color="#222222")
    ax2.annotate("", (4.98, 3.55), (4.98, 2.25), arrowprops={"arrowstyle": "->", "lw": 0.9, "color": "#009e73"})
    ax2.text(5.85, 2.92, "STATE / lidar\nreleases P & Y", ha="center", va="center", fontsize=5.7, color="#009e73")

    fig.tight_layout(pad=0.5)
    fig.savefig(OUT / "protocol.pdf")
    plt.close(fig)


def fig3_rq1_information():
    """Fig. 3 (2x2): Geometry sweep + reservation, asymmetric robots, noisy bids, learned OOD."""
    fig, axs = plt.subplots(2, 2, figsize=(7.16, 4.4))
    (ax_a, ax_b), (ax_c, ax_d) = axs

    # (a) Excess delay vs bay position (S1 + Reservation)
    s1 = paired(pd.read_csv(RAW / "S1_baseline.csv.gz"))
    res = pd.read_csv(RAW / "reservation.csv.gz")
    fA = res[res.label == "forced_A"].set_index(["x", "seed"]).total_delay
    fB = res[res.label == "forced_B"].set_index(["x", "seed"]).total_delay
    ref_res = np.minimum(fA, fB)
    res_p = res[res.label == "reservation"].set_index(["x", "seed"]).total_delay - ref_res
    res_df = res_p.reset_index(name="regret")

    g_res = res_df.groupby("x").regret.agg(["mean", ci])
    ax_a.errorbar(g_res.index, g_res["mean"], yerr=g_res["ci"], fmt="d--", c=PAL["reservation"],
                  capsize=2, lw=1.2, ms=4, label="reservation (FCFS)")
    for lab, disp, mk in [
        ("fixed_priority", "fixed priority / default rule", "s-"),
        ("rules_proximity", "closest-refuge rulebook", "^-"),
        ("cost_bid", "cost_bid", "o-"),
    ]:
        g = s1[(s1.label == lab) & s1.success].groupby("bays.0.x").regret.agg(["mean", ci])
        ax_a.errorbar(g.index, g["mean"], yerr=g["ci"], fmt=mk, c=PAL[lab], capsize=2, lw=1.2, ms=4, label=disp)
    ax_a.set_xlabel("Bay position x [m] (A enters at 0, B at 8)")
    ax_a.set_ylabel(r"Excess delay $\Delta_\pi$ [s]")
    ax_a.set_xticks(range(1, 8))
    ax_a.grid(alpha=0.25)
    ax_a.legend(loc="upper right", frameon=True, framealpha=0.9)
    ax_a.set_title("(a) Single-bay geometry & zone reservation", loc="left")

    # (b) S2 Asymmetric robots (urgency, load, speed)
    p2 = paired(pd.read_csv(RAW / "S2_asymmetry.csv.gz"), ref="oracle_w", metric="wdelay")
    labs_b = [
        ("fixed_priority", "Fixed\npriority", PAL["fixed_priority"]),
        ("oracle", "Unweighted\nreference", PAL["oracle"]),
        ("rules_default", "Default\nrulebook", PAL["rules_default"]),
        ("cost_bid", "cost_bid\n(weighted)", PAL["cost_bid"]),
    ]
    means_b = [p2[p2.label == k].regret.mean() for k, _, _ in labs_b]
    cis_b = [ci(p2[p2.label == k].regret) for k, _, _ in labs_b]
    bars = ax_b.bar([n for _, n, _ in labs_b], means_b, yerr=cis_b, capsize=3,
                    color=[c for _, _, c in labs_b], width=0.58, edgecolor="k", lw=0.5)
    for bar, m, c_err in zip(bars, means_b, cis_b):
        ax_b.text(bar.get_x() + bar.get_width() / 2, m + c_err + 0.65, f"{m:.2f}" if m < 1 else f"{m:.1f}",
                  ha="center", va="bottom", fontsize=6.8)
    ax_b.set_ylim(0, 34.5)
    ax_b.set_ylabel("Urgency-weighted excess [s]")
    ax_b.grid(alpha=0.25, axis="y")
    ax_b.set_title("(b) Asymmetric urgency, payload & speed (S2)", loc="left")

    # (c) S7 Bid-estimation noise
    p7 = paired(pd.read_csv(RAW / "S7_noisy_bids.csv.gz"))
    cb7 = p7[p7.label == "cost_bid"].groupby("bid_sigma").regret.agg(["mean", ci])
    ax_c.errorbar(cb7.index, cb7["mean"], yerr=cb7["ci"], fmt="o-", c=PAL["cost_bid"],
                  capsize=2.5, lw=1.4, ms=4.5, label="cost_bid (noisy bids)")
    prox_m = p7[p7.label == "rules_proximity"].regret.mean()
    fp_m = s1[s1.label == "fixed_priority"].regret.mean()
    ax_c.axhline(prox_m, ls="--", lw=1.2, c=PAL["rules_proximity"], label=f"closest-refuge rule ({prox_m:.1f} s)")
    ax_c.axhline(fp_m, ls=":", lw=1.2, c=PAL["fixed_priority"], label=f"fixed priority ({fp_m:.1f} s)")
    ax_c.axvline(0.5, ls="-.", lw=0.8, c="#666666", alpha=0.7)
    ax_c.text(0.52, 0.5, "crossover\nσ ≈ 0.5", fontsize=6.5, color="#444444")
    ax_c.set_xlabel(r"Log-normal bid error $\sigma$ ($\tilde{c} = c \cdot e^{\sigma \epsilon}$)")
    ax_c.set_ylabel(r"Excess delay $\Delta_\pi$ [s]")
    ax_c.grid(alpha=0.25)
    ax_c.legend(loc="upper left", frameon=True, framealpha=0.9)
    ax_c.set_title("(c) Sensitivity to cost-model noise (S7)", loc="left")

    # (d) Tabular contextual bandit in-distribution vs OOD (from learned_negotiator.md)
    # Values verified in data/tables/classical/learned_negotiator.md (800 train, 150 eval per layout)
    pols_d = ["fixed_priority", "rules_default", "learned", "cost_bid"]
    names_d = ["Fixed\npriority", "Default\nrulebook", "Learned\n(tabular)", "cost_bid"]
    seen = [9.2, 2.5, 2.6, 0.0]
    unseen = [12.3, 6.3, 13.1, 0.0]
    x_d = np.arange(len(pols_d))
    w = 0.35
    b1 = ax_d.bar(x_d - w / 2, seen, w, label="Two-bay (training layout)", color="#56b4e9", edgecolor="k", lw=0.5)
    b2 = ax_d.bar(x_d + w / 2, unseen, w, label="Single-bay (unseen layout)", color="#e69f00", edgecolor="k", lw=0.5)
    for b in list(b1) + list(b2):
        v = b.get_height()
        ax_d.text(b.get_x() + b.get_width() / 2, v + 0.35, f"{v:.1f}", ha="center", va="bottom", fontsize=6.2)
    ax_d.annotate("15% unseen\nfallback", xy=(2 + w / 2 + 0.16, 12.6), xytext=(3.02, 9.8),
                  arrowprops={"arrowstyle": "->", "lw": 0.7}, fontsize=6.1, ha="center")
    ax_d.set_xticks(x_d, names_d)
    ax_d.set_ylim(0, 19.5)
    ax_d.set_ylabel("Weighted excess delay [s]")
    ax_d.grid(alpha=0.25, axis="y")
    ax_d.legend(loc="upper right", frameon=True, framealpha=0.9)
    ax_d.set_title("(d) Contextual bandit generalization across layouts", loc="left")

    fig.tight_layout(pad=0.6)
    fig.savefig(OUT / "rq1_information.pdf")
    plt.close(fig)


def fig4_rq2_incentives():
    """Fig. 4 (1x2): S9 Clarke VCG misreport curves + S10 repeated-encounter fairness Pareto."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.16, 2.65))

    # (a) S9 payments & misreports
    s9 = utilities(pd.read_csv(RAW / "S9_payments.csv.gz"))
    key = ["u_B", "x", "seed"]
    truth = s9[(s9.who == "A") & (s9.k == 1.0)].set_index(key)

    ks = sorted(s9.k.unique())
    curves = {"A_none": [], "A_naive": [], "A_vcg_real": [], "AB_vcg": []}
    errs = {k: [] for k in curves}
    for kv in ks:
        if kv == 1.0:
            for c in curves:
                curves[c].append(0.0)
                errs[c].append(0.0)
            continue
        ja = s9[(s9.who == "A") & (s9.k == kv)].set_index(key).join(truth, rsuffix="_t")
        jab = s9[(s9.who == "AB") & (s9.k == kv)].set_index(key).join(truth, rsuffix="_t")
        d_none = ja["pred_none_A"] - ja["pred_none_A_t"]
        d_old = ja["pred_old_A"] - ja["pred_old_A_t"]
        d_real = ja["real_vcg_A"] - ja["real_vcg_A_t"]
        d_coll = (jab["real_vcg_A"] - jab["real_vcg_A_t"]) + (jab["real_vcg_B"] - jab["real_vcg_B_t"])
        for name, ser in [("A_none", d_none), ("A_naive", d_old), ("A_vcg_real", d_real), ("AB_vcg", d_coll)]:
            curves[name].append(ser.mean())
            errs[name].append(ci(ser))

    ax1.axhspan(-12, 0.0, color="#e8f5e9", alpha=0.55)
    ax1.axhline(0.0, color="#222222", lw=0.9, ls="-")
    ax1.errorbar(ks, curves["A_none"], yerr=errs["A_none"], fmt="s--", c=PAL["fixed_priority"],
                 capsize=2, lw=1.15, ms=3.8, label="No transfer (A unilateral)")
    ax1.errorbar(ks, np.clip(curves["A_naive"], -11.5, 20), yerr=errs["A_naive"], fmt="^:", c=PAL["reservation"],
                 capsize=2, lw=1.15, ms=3.8, label="Naive transfer (A unilateral)")
    ax1.errorbar(ks, curves["AB_vcg"], yerr=errs["AB_vcg"], fmt="d-.", c=PAL["learned"],
                 capsize=2, lw=1.15, ms=3.8, label="Clarke VCG (A+B collusion)")
    ax1.errorbar(ks, curves["A_vcg_real"], yerr=errs["A_vcg_real"], fmt="o-", c=PAL["cost_bid"],
                 capsize=2, lw=1.5, ms=4.2, label="Clarke VCG, realized (A unil.)")
    ax1.set_xscale("log", base=2)
    ax1.set_xticks([0.25, 0.5, 1.0, 2.0, 4.0], ["0.25×", "0.5×", "1×", "2×", "4×"])
    ax1.set_ylim(-10.8, 9.2)
    ax1.set_xlabel(r"Reported-cost multiplier $k$ ($r_i = k \cdot c_i$)")
    ax1.set_ylabel("Deviator utility gain vs. truthful [s]")
    ax1.text(0.26, -9.8, "Unprofitable deviation zone (≤ 0 s)", fontsize=6.2, color="#1b5e20")
    ax1.grid(alpha=0.25)
    ax1.legend(loc="upper right", fontsize=6.1, frameon=True, framealpha=0.92)
    ax1.set_title("(a) Strategic misreport gain (S9, N=10,080)", loc="left")

    # (b) S10 Repeated-encounter fairness vs delay overhead
    s10 = pd.read_csv(RAW / "S10_repeated.csv.gz")
    cost_seq = s10[s10.rule == "cost"].set_index("seq").total

    def pt(rule):
        g = s10[s10.rule == rule].set_index("seq")
        ex = 100.0 * (g.total / cost_seq - 1.0)
        return ex.mean(), ci(ex), g.jain.mean(), ci(g.jain)

    # Credit trajectory: cost (lambda=0) -> 0.25 -> 0.5 -> 1.0 -> 2.0
    lam_rules = [("cost", "λ=0 (cost-opt.)"), ("credit_l0.25", "λ=0.25"),
                 ("credit_l0.5", "λ=0.5"), ("credit_l1.0", "λ=1.0"), ("credit_l2.0", "λ=2.0")]
    lx, lx_ci, ly, ly_ci = zip(*(pt(r) for r, _ in lam_rules))
    ax2.errorbar(lx, ly, xerr=lx_ci, yerr=ly_ci, fmt="o-", c=PAL["cost_bid"], lw=1.4, ms=4.5, capsize=2,
                 label="Credit-weighted choice (λ sweep)")

    fp_x, fp_xc, fp_y, fp_yc = pt("fixed_priority")
    alt_x, alt_xc, alt_y, alt_yc = pt("alternate")
    ax2.errorbar([fp_x], [fp_y], xerr=[fp_xc], yerr=[fp_yc], fmt="s", c=PAL["fixed_priority"], ms=6, capsize=2.5,
                 label="Fixed priority (+27%, J=0.754)")
    ax2.errorbar([alt_x], [alt_y], xerr=[alt_xc], yerr=[alt_yc], fmt="^", c=PAL["rules_default"], ms=6, capsize=2.5,
                 label="Strict alternation (+22%, J=0.992)")

    ax2.annotate("λ = 0.25 sweet spot\n(+8.1% delay, J = 0.997)", xy=(lx[1], ly[1]), xytext=(9.5, 0.89),
                 arrowprops={"arrowstyle": "->", "lw": 0.8, "color": "#0072b2"}, fontsize=6.5, color="#004c7a", weight="bold")
    ax2.annotate("λ = 0\n(J = 0.927)", xy=(lx[0], ly[0]), xytext=(2.2, 0.915),
                 arrowprops={"arrowstyle": "->", "lw": 0.7}, fontsize=6.2)
    ax2.set_xlim(-1.5, 31)
    ax2.set_ylim(0.72, 1.015)
    ax2.set_xlabel("Sequence delay overhead vs. cost-optimal [%]")
    ax2.set_ylabel(r"Jain's fairness index $J(D_A, D_B)$")
    ax2.grid(alpha=0.25)
    ax2.legend(loc="lower right", fontsize=6.2, frameon=True, framealpha=0.92)
    ax2.set_title("(b) Repeated-encounter fairness Pareto (S10)", loc="left")

    fig.tight_layout(pad=0.6)
    fig.savefig(OUT / "rq2_incentives.pdf")
    plt.close(fig)


def fig5_rq3_comms_maps():
    """Fig. 5 (1x2): Packet loss / extreme comms scaling + Explore/map-sharing excess."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.16, 2.65))

    # (a) S3 (loss 0..90%, lat 0.05 & 2.0 s) + S8b (loss 90..99%, lat 2..8 s, v=0.5 m/s)
    s3 = pd.read_csv(RAW / "S3_comms.csv.gz")
    s8b = pd.read_csv(RAW / "S8b_comms_extreme.csv.gz")

    for pol, disp, col, mk in [("cost_bid", "cost_bid", PAL["cost_bid"], "o"),
                               ("fixed_priority", "fixed priority", PAL["fixed_priority"], "s")]:
        g_low = s3[(s3.label == pol) & (s3["comms.latency"] == 0.05) & s3.success].groupby("comms.loss").total_delay.agg(["mean", ci])
        g_hi = s3[(s3.label == pol) & (s3["comms.latency"] == 2.0) & s3.success].groupby("comms.loss").total_delay.agg(["mean", ci])
        ax1.errorbar(100 * g_low.index, g_low["mean"], yerr=g_low["ci"], fmt=f"{mk}-", c=col, lw=1.2, ms=3.8, capsize=2,
                     label=f"{disp} (τ=0.05 s)")
        ax1.errorbar(100 * g_hi.index, g_hi["mean"], yerr=g_hi["ci"], fmt=f"{mk}--", c=col, lw=1.0, ms=3.4, capsize=2, alpha=0.75,
                     label=f"{disp} (τ=2.0 s)")
        g_ext = s8b[(s8b.label == pol) & s8b.success].groupby("comms.loss").total_delay.agg(["mean", ci])
        ax1.errorbar(100 * g_ext.index, g_ext["mean"], yerr=g_ext["ci"], fmt=f"{mk}:", c=col, lw=1.2, ms=4.2, capsize=2)

    ax1.axvspan(89, 100.5, color="#fff3e0", alpha=0.6)
    ax1.text(87.5, 82.5, "Extreme S8b\n(90–99%,\nτ=2–8 s)", ha="right", va="top", fontsize=5.8, color="#8d4900")
    ax1.text(2, 92, "0 collisions across all 15,120 runs\n(≥99.3% succ. ≤90%; ≥98.9% at 99%)",
             fontsize=6.1, bbox={"boxstyle": "round,pad=0.25", "fc": "#e8f5e9", "ec": "#2e7d32", "lw": 0.6})
    ax1.set_xlim(-3, 101)
    ax1.set_ylim(20, 108)
    ax1.set_xlabel("Packet loss rate [%]")
    ax1.set_ylabel("Mean total delay (successes) [s]")
    ax1.grid(alpha=0.25)
    ax1.legend(loc="center left", fontsize=6.0, frameon=True, framealpha=0.9)
    ax1.set_title("(a) Loss & latency resilience (S3 & S8b)", loc="left")

    # (b) Explore mode & map sharing (0% loss, paired against full map)
    exp = pd.read_csv(RAW / "explore_map.csv.gz")
    e0 = exp[exp["loss"] == 0.0]
    full = e0[e0["map"] == "full"].set_index(["policy", "detect_range", "seed"]).total_delay

    conds = [
        ("explore_no_share", "No\nshare"),
        ("explore_share_on_detect", "Share on\ndetect"),
        ("explore_share_on_detect_hold", "Detect +\nhold"),
        ("explore_share_always", "Share every\nBID"),
    ]
    series = [
        ("fixed_priority", 6.0, "Fixed prio. (R=6 m)", PAL["fixed_priority"], "//"),
        ("fixed_priority", 3.5, "Fixed prio. (R=3.5 m)", "#f4a582", ""),
        ("cost_bid", 6.0, "cost_bid (R=6 m)", PAL["cost_bid"], "//"),
        ("cost_bid", 3.5, "cost_bid (R=3.5 m)", "#92c5de", ""),
    ]
    x_pos = np.arange(len(conds))
    bw = 0.19
    for idx, (pol, rng, lbl, col, hat) in enumerate(series):
        means, cis = [], []
        for m_key, _ in conds:
            sub = e0[(e0["map"] == m_key) & (e0["policy"] == pol) & (e0["detect_range"] == rng)]
            diff = sub.set_index(["policy", "detect_range", "seed"]).total_delay - full
            diff = diff.dropna()
            means.append(diff.mean())
            cis.append(ci(diff))
        ax2.bar(x_pos + (idx - 1.5) * bw, means, bw, yerr=cis, capsize=1.8, label=lbl,
                color=col, edgecolor="k", lw=0.45, hatch=hat)

    ax2.axhline(0.0, color="#222222", lw=0.8)
    ax2.annotate("Decision at 6 m precedes\n3.5 m lidar (0/30 timely)", xy=(1 - 1.5 * bw, 29.5), xytext=(0.45, 33.0),
                 arrowprops={"arrowstyle": "->", "lw": 0.7}, fontsize=5.9, ha="center")
    ax2.annotate("Hold waits\n~5.0 s", xy=(2, 0.2), xytext=(2.05, 8.5),
                 arrowprops={"arrowstyle": "->", "lw": 0.7}, fontsize=6.0, ha="center")
    ax2.set_xticks(x_pos, [lbl for _, lbl in conds])
    ax2.set_ylim(-2.5, 37.5)
    ax2.set_ylabel("Excess delay vs. full map [s]")
    ax2.grid(alpha=0.25, axis="y")
    ax2.legend(loc="upper right", fontsize=5.9, frameon=True, framealpha=0.92)
    ax2.set_title("(b) Online bay discovery & map sharing (2D)", loc="left")

    fig.tight_layout(pad=0.6)
    fig.savefig(OUT / "rq3_comms_maps.pdf")
    plt.close(fig)


def fig6_rq4_topologies():
    """Fig. 6 (1x2): Convoy 2v1 weighted delay + T-junction before/after upstream goal_wait."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.16, 2.65))

    # (a) Convoy 2v1 from convoy_group.csv.gz
    dfc = pd.read_csv(RAW / "convoy_group.csv.gz")
    cases = [("none", "Equal\nrobots"), ("B_loaded", "Lone B\nloaded"), ("B_urgent", "Lone B\nurgent (u=3)")]
    pols = [
        ("side_oracle", "Side ref.", PAL["side_oracle"]),
        ("fixed_priority", "Fixed prio.", PAL["fixed_priority"]),
        ("rules_default", "Rulebook", PAL["rules_default"]),
        ("group_bid", "group_bid", PAL["group_bid"]),
        ("cost_bid", "cost_bid", PAL["cost_bid"]),
    ]
    xc = np.arange(len(cases))
    bw = 0.155
    for idx, (p_key, p_lbl, col) in enumerate(pols):
        ms, cs = [], []
        for c_key, _ in cases:
            vals = dfc[(dfc.case == c_key) & (dfc.label == p_key) & dfc.success].wdelay
            ms.append(vals.mean())
            cs.append(ci(vals))
        ax1.bar(xc + (idx - 2.0) * bw, ms, bw, yerr=cs, capsize=1.8, label=p_lbl,
                color=col, edgecolor="k", lw=0.45)
    ax1.annotate("Serial yield\nunderestimated", xy=(2 + 1.0 * bw, 108), xytext=(1.58, 127),
                 arrowprops={"arrowstyle": "->", "lw": 0.7}, fontsize=6.0, ha="center")
    ax1.set_xticks(xc, [lbl for _, lbl in cases])
    ax1.set_ylim(0, 148)
    ax1.set_ylabel("Urgency-weighted delay [s]")
    ax1.grid(alpha=0.25, axis="y")
    ax1.legend(loc="upper left", ncol=2, fontsize=5.9, frameon=True, framealpha=0.92)
    ax1.set_title("(a) Convoy 2 vs. 1 with make_room (N=1,080)", loc="left")

    # (b) T-junction turn-in before vs after goal_wait (0% loss, n=48 per policy)
    dft = pd.read_csv(RAW / "tjunction_goal.csv.gz")
    t0 = dft[dft.loss == 0.0]
    pols_t = ["reactive", "fixed_priority", "rules_default", "cost_bid"]
    names_t = ["Reactive", "Fixed\npriority", "Default\nrulebook", "cost_bid"]
    # Before values from data/tables/classical/tjunction_goal_before.txt (0% loss, n=48)
    succ_before = [100 * 27 / 48, 100 * 29 / 48, 100 * 42 / 48, 100 * 44 / 48]
    succ_after = [100 * t0[t0.label == p].success.mean() for p in pols_t]
    del_before = [189.1, 152.2, 70.6, 51.3]
    del_after = [t0[(t0.label == p) & t0.success].total_delay.mean() for p in pols_t]

    xt = np.arange(len(pols_t))
    w = 0.34
    ax2.bar(xt - w / 2, succ_before, w, color="#cccccc", edgecolor="k", lw=0.5, label="Success % (lane wait)")
    ax2.bar(xt + w / 2, succ_after, w, color="#009e73", alpha=0.82, edgecolor="k", lw=0.5, label="Success % (goal_wait)")
    ax2.set_ylim(0, 126)
    ax2.set_ylabel("Completion rate [%]", color="#006d4e")
    ax2.set_xticks(xt, names_t)
    ax2.grid(alpha=0.25, axis="y")

    ax2_r = ax2.twinx()
    ax2_r.spines["top"].set_visible(False)
    ax2_r.plot(xt - w / 2, del_before, "o--", c="#b03030", lw=1.1, ms=4.2, label="Delay [s] (before)")
    ax2_r.plot(xt + w / 2, del_after, "s-", c="#004c7a", lw=1.3, ms=4.5, label="Delay [s] (after)")
    ax2_r.set_ylim(0, 235)
    ax2_r.set_ylabel("Mean delay, successes [s]", color="#004c7a")

    h1, l1 = ax2.get_legend_handles_labels()
    h2, l2 = ax2_r.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=5.7, ncol=2, frameon=True, framealpha=0.92)
    ax2.set_title("(b) T-junction turn-in: upstream goal_wait fix", loc="left")

    fig.tight_layout(pad=0.6)
    fig.savefig(OUT / "rq4_topologies.pdf")
    plt.close(fig)


def fig7_rq4_gazebo():
    """Fig. 7 (1x2): 460-run Gazebo vs 2D scatter + Seed-3 paired 2D/Gazebo spacetime trace."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.16, 2.75))

    # (a) 460-run paired Gazebo vs 2D delay scatter
    gz = pd.concat([
        pd.read_csv(TAB_G / "gazebo_main_runs.csv"),
        pd.read_csv(TAB_G / "gazebo_all_runs.csv"),
    ], ignore_index=True)
    ok = gz[gz.gz_success.astype(bool) & gz.d2_success.astype(bool)].copy()

    def bucket(row):
        k = row["kind"]
        if row["policy"] == "reactive":
            return "Reactive (random patience)"
        if k in ("tj", "tjgoal"):
            return "T-junction (timing race)"
        if k == "explore_det_3.5":
            return "Explore share_on_detect (3.5 m)"
        if k in ("S7", "S8b", "S8c_all_off"):
            return "Stochastic draws (noise / 90% loss)"
        return "Shared-draw corridors (n=350)"

    ok["grp"] = ok.apply(bucket, axis=1)
    n_corr = int((ok.grp == "Shared-draw corridors (n=350)").sum())
    styles = [
        ("Shared-draw corridors (n=350)", f"Shared-draw corridors (n={n_corr})", "#0072b2", "o", 18, 0.72),
        ("Stochastic draws (noise / 90% loss)", "Stochastic draws (noise / 90% loss)", "#e69f00", "^", 24, 0.85),
        ("Explore share_on_detect (3.5 m)", "Explore share_on_detect (3.5 m)", "#009e73", "D", 28, 0.95),
        ("T-junction (timing race)", "T-junction (timing race)", "#d55e00", "s", 24, 0.88),
        ("Reactive (random patience)", "Reactive (random patience)", "#7f7f7f", "x", 26, 0.85),
    ]
    ax1.plot([15, 165], [15, 165], ls="--", lw=1.0, c="#222222", zorder=1, label="y = x (exact transfer)")
    for grp, lbl, col, mk, sz, al in styles:
        sub = ok[ok.grp == grp]
        if sub.empty:
            continue
        kw = {"c": col, "marker": mk, "s": sz, "alpha": al, "label": lbl, "zorder": 3}
        if mk != "x":
            kw.update({"edgecolors": "k", "linewidths": 0.3})
        else:
            kw.update({"linewidths": 0.9})
        ax1.scatter(sub.d2_wdelay, sub.gz_wdelay, **kw)

    ax1.annotate("Seed 3\n(panel b)", xy=(26.2, 67.3), xytext=(36, 78),
                 arrowprops={"arrowstyle": "->", "lw": 0.7, "color": "#006d4e"}, fontsize=5.8, color="#006d4e")
    ax1.annotate("T-junction\n(ΔD = -16.8 s mean)", xy=(91.5, 57.4), xytext=(95, 25),
                 arrowprops={"arrowstyle": "->", "lw": 0.7, "color": "#d55e00"}, fontsize=6.0, color="#b03a00")
    ax1.set_xlim(15, 165)
    ax1.set_ylim(15, 165)
    ax1.set_xlabel("2D simulator weighted delay [s]")
    ax1.set_ylabel("Gazebo Harmonic weighted delay [s]")
    ax1.grid(alpha=0.25)
    ax1.legend(loc="upper left", fontsize=5.8, frameon=True, framealpha=0.92)
    ax1.set_title("(a) 460-run seed-paired Gazebo vs. 2D delay", loc="left")

    # (b) Empirical spacetime trajectory x(t) on Seed 3 (explore_det_3.5 vs explore_all_3.5)
    gz_det = json.load(open(MEDIA / "explore_det35_fixed_priority.json"))
    gz_all = json.load(open(MEDIA / "explore_all35_fixed_priority.json"))

    # Paired 2D trace for exact same scenario & seed=3
    raw_sc = json.loads((ROOT / "configs/scenarios/corridor_two_bays.yaml").read_text()) if False else None
    import yaml
    d_sc = yaml.safe_load((ROOT / "configs/scenarios/corridor_two_bays.yaml").read_text())
    d_sc["agents"][1]["start_delay"] = round(float(np.random.default_rng(3).uniform(0, 8)), 3)
    deep_update(d_sc, {"agent_params": {"explore": True, "detect_range": 3.5, "share_map": True, "share_on_detect": True}})
    d2_ep = sim2d.run_episode(scenario_from_dict(d_sc), {"name": "fixed_priority"}, seed=3, record=True)

    # Background corridor & refuge bands
    ax2.axhspan(0.0, 10.0, color="#f4f6f8", zorder=0)
    ax2.axhline(3.0, ls=":", lw=0.8, c="#666666")
    ax2.axhline(7.0, ls=":", lw=0.8, c="#666666")
    ax2.text(108, 3.2, "bay0 (x=3)", fontsize=5.8, ha="right", color="#555555")
    ax2.text(108, 7.2, "bay1 (x=7)", fontsize=5.8, ha="right", color="#555555")
    ax2.text(108, 10.9, "room_hi", fontsize=5.8, ha="right", color="#555555")

    t_det = [p["t"] for p in gz_det["trace"]]
    ax2.plot(t_det, [p["A"][0] for p in gz_det["trace"]], "-", c=PAL["cost_bid"], lw=1.2, label="A (Gazebo / 2D)")
    ax2.plot(t_det, [p["B"][0] for p in gz_det["trace"]], "-", c=PAL["fixed_priority"], lw=1.5,
             label="B: Gazebo share_on_detect (→room_hi)")

    t_all = [p["t"] for p in gz_all["trace"]]
    ax2.plot(t_all, [p["B"][0] for p in gz_all["trace"]], "--", c=PAL["rules_default"], lw=1.4,
             label="B: Gazebo share_every_bid (→bay1)")

    t_2d = [p["t"] for p in d2_ep["trace"]]
    ax2.plot(t_2d, [p["B"][0] for p in d2_ep["trace"]], ":", c="#111111", lw=1.3,
             label="B: 2D share_on_detect (→bay1)")

    ax2.axvline(17.1, ls="-.", lw=0.75, c="#555555")
    ax2.text(18.2, -1.2, "t=17.1 s:\ndecision", fontsize=5.8, color="#333333")
    ax2.annotate("Gazebo lidar detects\npeer at t=37.9 s (late!)", xy=(37.9, 9.7), xytext=(50, 8.3),
                 arrowprops={"arrowstyle": "->", "lw": 0.75, "color": "#d55e00"}, fontsize=5.9, color="#b03a00")

    ax2.set_xlim(0, 115)
    ax2.set_ylim(-2.0, 12.0)
    ax2.set_xlabel("Simulation time t [s]")
    ax2.set_ylabel("Corridor position x [m]")
    ax2.grid(alpha=0.22)
    ax2.legend(loc="lower right", fontsize=5.6, frameon=True, framealpha=0.92)
    ax2.set_title("(b) Sim-to-3D lidar lag trace (Seed 3, R=3.5 m)", loc="left")

    fig.tight_layout(pad=0.6)
    fig.savefig(OUT / "rq4_gazebo.pdf")
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fig1_scenarios()
    fig2_protocol()
    fig3_rq1_information()
    fig4_rq2_incentives()
    fig5_rq3_comms_maps()
    fig6_rq4_topologies()
    fig7_rq4_gazebo()
    print("Generated all 7 figures in", OUT)
