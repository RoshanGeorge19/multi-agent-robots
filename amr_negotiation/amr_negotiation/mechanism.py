"""Clarke-pivot (VCG) mechanism for the two-outcome yield decision.

An outcome is named by its yielder. Robot i's type is its own predicted urgency-weighted delay in each
outcome, c_i(o) = u_i * d_i(o). Each robot reports r_i(o); the mechanism picks
    o* = argmin_o sum_i r_i(o)
and charges robot i the externality it imposes on the others,
    p_i = sum_{j != i} r_j(o*) - min_o sum_{j != i} r_j(o)  >= 0.
Truthful reporting is then a dominant strategy with respect to the predicted costs. With two robots
and two outcomes this is a second-price auction on the cost difference; payments go to a bank, so the
mechanism runs a surplus and is not budget balanced (Green-Laffont).
"""

from __future__ import annotations

import math

from .geometry import Scenario
from .planner import Snapshot, best_plan


def types(a: Snapshot, b: Snapshot, sc: Scenario) -> dict[str, dict[str, float]]:
    """costs[yielder][robot]: each robot's predicted urgency-weighted delay if `yielder` yields."""
    out = {}
    for Y, P in ((a, b), (b, a)):
        plan = best_plan(Y, P, sc)
        out[Y.id] = ({Y.id: math.inf, P.id: math.inf} if plan is None else
                     {Y.id: Y.urgency * plan["yielder_delay"], P.id: P.urgency * plan["proceeder_delay"]})
    return out


def clarke(reports: dict[str, dict[str, float]]) -> tuple[str | None, dict[str, float]]:
    """Return (chosen outcome, Clarke-pivot payment per robot). Ties go to the last outcome (higher id yields)."""
    outcomes = sorted(reports)
    robots = sorted({i for o in outcomes for i in reports[o]})
    total = {o: sum(reports[o].values()) for o in outcomes}
    ok = [o for o in outcomes if math.isfinite(total[o])]
    if not ok:
        return None, dict.fromkeys(robots, 0.0)
    best = min(ok, key=lambda o: (total[o], o != outcomes[-1]))
    pay = {}
    for i in robots:
        others = {o: sum(v for j, v in reports[o].items() if j != i) for o in outcomes}
        pay[i] = others[best] - min(others.values())
    return best, pay
