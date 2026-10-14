"""Yield-plan feasibility and cost model shared by all negotiating policies.

A plan is "robot Y pulls into refuge R so that robot P can pass". The timeline model is a
simple constant-speed estimate (no acceleration transients); it is what the robots *believe*
when they bid, not what the simulator measures.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from .geometry import Refuge, Scenario


@dataclass
class Snapshot:
    """What a robot tells its peer about itself when a conflict is detected (frozen per conflict)."""

    id: str
    t: float
    x: float
    dir: int
    v: float
    goal_x: float
    entered_t: float | None
    urgency: float
    loaded: bool
    v_max: float
    v_rev_max: float
    w_max: float
    a_max: float

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> Snapshot:
        return Snapshot(**d)


def stop_x(s: Snapshot) -> float:
    v = max(0.0, s.v)
    return s.x + s.dir * v * v / (2.0 * s.a_max)


def hold_x(refuge: Refuge, proceeder_dir: int, sc: Scenario) -> float:
    """Lane position where the proceeding robot waits until the yielder is out of the lane."""
    return refuge.x - proceeder_dir * (refuge.span / 2 + sc.robot.radius + sc.clearance)


def pass_x(refuge: Refuge, proceeder_dir: int, sc: Scenario) -> float:
    """Lane position beyond which the proceeding robot has cleared the refuge."""
    return refuge.x + proceeder_dir * (refuge.span / 2 + sc.robot.radius + sc.clearance)


def feasible(refuge: Refuge, Y: Snapshot, P: Snapshot, sc: Scenario) -> bool:
    h = hold_x(refuge, P.dir, sc)
    if P.dir * (h - stop_x(P)) < 0:
        return False
    if P.dir * (P.goal_x - pass_x(refuge, P.dir, sc)) < 0:
        return False
    return Y.dir * (Y.goal_x - refuge.x) >= 0


def plan_times(refuge: Refuge, Y: Snapshot, P: Snapshot, sc: Scenario) -> dict:
    t_turn = (math.pi / 2) / (0.8 * Y.w_max)
    dY = refuge.x - Y.x
    reverse = Y.dir * dY < 0
    vY = Y.v_rev_max if reverse else Y.v_max
    depth = abs(refuge.park_y)
    t_park = abs(dY) / vY + t_turn + depth / Y.v_max
    h = hold_x(refuge, P.dir, sc)
    px = pass_x(refuge, P.dir, sc)
    t_hold = abs(h - P.x) / P.v_max
    t_go = max(t_park, t_hold)
    t_pass = t_go + abs(px - h) / P.v_max
    t_exit = t_pass + depth / Y.v_rev_max + t_turn
    y_arr = t_exit + abs(Y.goal_x - refuge.x) / Y.v_max
    p_arr = t_pass + abs(P.goal_x - px) / P.v_max
    y_free = abs(Y.goal_x - Y.x) / Y.v_max
    p_free = abs(P.goal_x - P.x) / P.v_max
    return {
        "refuge": refuge.id,
        "yielder_delay": y_arr - y_free,
        "proceeder_delay": p_arr - p_free,
        "total_delay": (y_arr - y_free) + (p_arr - p_free),
        "makespan": max(y_arr, p_arr),
        "reverse_dist": abs(dY) if reverse else 0.0,
        "refuge_dist": abs(dY),
        "refuge_behind": reverse,
    }


def best_plan(Y: Snapshot, P: Snapshot, sc: Scenario, objective: str = "total_delay") -> dict | None:
    plans = [plan_times(r, Y, P, sc) for r in sc.refuges() if feasible(r, Y, P, sc)]
    if not plans:
        return None
    return min(plans, key=lambda p: (p[objective], p["refuge_dist"]))


def refuge_by_id(sc: Scenario, rid: str) -> Refuge:
    for r in sc.refuges():
        if r.id == rid:
            return r
    raise KeyError(rid)
