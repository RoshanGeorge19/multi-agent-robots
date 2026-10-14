"""Plotting helpers: scenario map, trajectories, x-t diagram, animation."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

COLORS = ["tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple"]


def draw_map(ax, sc):
    for r in sc.free_rects():
        ax.add_patch(Rectangle((r.x0, r.y0), r.x1 - r.x0, r.y1 - r.y0, fc="0.93", ec="none"))
    for (x0, y0), (x1, y1) in sc.wall_segments():
        ax.plot([x0, x1], [y0, y1], "k-", lw=1.5)
    for r in sc.refuges():
        ax.plot(r.x, r.park_y, "x", color="0.4")
        ax.annotate(r.id, (r.x, r.park_y), fontsize=7, color="0.4", xytext=(3, 3),
                    textcoords="offset points")
    ax.set_aspect("equal")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")


def _ids(trace):
    return [k for k in trace[0] if k != "t"]


def plot_episode(sc, res, path):
    tr = res["trace"]
    ids = _ids(tr)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), gridspec_kw={"height_ratios": [1.2, 1]})
    draw_map(ax1, sc)
    for k, i in enumerate(ids):
        xs = [s[i][0] for s in tr]
        ys = [s[i][1] for s in tr]
        ax1.plot(xs, ys, color=COLORS[k % 5], lw=1.2, label=i)
        ax2.plot([s["t"] for s in tr], xs, color=COLORS[k % 5], label=i)
        rev = [s for s in tr if s[i][3] < -0.01]
        ax2.plot([s["t"] for s in rev], [s[i][0] for s in rev], ".", ms=2, color="k")
    ax1.legend(loc="upper right", fontsize=8)
    title = f"{sc.name} | policy={res['policy']} | yielder={res.get('yielder')} ({res.get('rule')})"
    if res.get("total_delay") is not None:
        title += f" | total delay={res['total_delay']:.1f}s"
    ax1.set_title(title, fontsize=9)
    ax2.set_xlabel("t [s]")
    ax2.set_ylabel("x [m]  (black = reversing)")
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def animate_episode(sc, res, path, fps=10, speedup=4.0):
    from matplotlib.animation import FuncAnimation, PillowWriter

    tr = res["trace"]
    ids = _ids(tr)
    dt = tr[1]["t"] - tr[0]["t"] if len(tr) > 1 else 0.1
    stride = max(1, round(speedup / (fps * dt)))
    frames = tr[::stride]
    fig, ax = plt.subplots(figsize=(10, 3.2))
    draw_map(ax, sc)
    circles, heads = [], []
    for k, _ in enumerate(ids):
        c = Circle((0, 0), sc.robot.radius, fc=COLORS[k % 5], alpha=0.5, ec="k")
        ax.add_patch(c)
        circles.append(c)
        heads.append(ax.plot([], [], "k-", lw=1.5)[0])
    txt = ax.text(0.01, 0.95, "", transform=ax.transAxes, fontsize=8, va="top")
    import math

    def upd(s):
        for k, i in enumerate(ids):
            x, y, th = s[i][0], s[i][1], s[i][2]
            circles[k].center = (x, y)
            heads[k].set_data([x, x + 0.3 * math.cos(th)], [y, y + 0.3 * math.sin(th)])
        txt.set_text(f"t={s['t']:.1f}s  " + "  ".join(f"{i}:{s[i][4]}/{s[i][5]}" for i in ids))
        return circles + heads + [txt]

    anim = FuncAnimation(fig, upd, frames=frames, blit=False)
    anim.save(path, writer=PillowWriter(fps=fps))
    plt.close(fig)
