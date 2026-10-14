"""Simulator-agnostic negotiating agent (one per robot).

The same class drives the robot in the fast 2D simulator and inside the ROS 2 / Gazebo node.
Each control tick the host passes the robot pose, perceived obstacles (world-frame points and
peer position estimates) and received messages; the agent returns (v, w) and outgoing messages.
Messages are plain JSON-serialisable dicts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .geometry import AgentConfig, Refuge, Scenario
from .planner import Snapshot, hold_x, pass_x, refuge_by_id
from .policies import NEGOTIATING_POLICIES, Decision, decide, refuge_of


def wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


@dataclass
class Perception:
    points: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    peers: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class AgentParams:
    detect_range: float = 6.0
    neg_period: float = 0.3
    neg_timeout: float = 3.0
    state_timeout: float = 1.0
    stop_margin: float = 0.10
    lateral_margin: float = 0.03
    patience: tuple[float, float] = (2.0, 6.0)
    park_timeout: tuple[float, float] = (6.0, 12.0)
    proceed_timeout: float = 60.0
    lane_lookahead: float = 0.4
    k_heading: float = 2.5
    k_dist: float = 1.5
    goal_tol: float = 0.05


class Agent:
    def __init__(self, cfg: AgentConfig, sc: Scenario, policy: dict, rng: np.random.Generator | None = None,
                 params: AgentParams | None = None):
        self.cfg, self.sc, self.policy = cfg, sc, dict(policy)
        self.p = params or AgentParams(**policy.get("agent_params", {}))
        self.rng = rng or np.random.default_rng()
        self.id, self.dir, self.goal_x = cfg.id, cfg.direction, cfg.goal_x
        self.goal_ref = refuge_by_id(sc, cfg.goal_refuge) if cfg.goal_refuge else None
        self.v_max = cfg.v_max or sc.robot.v_max
        self.v_rev = cfg.v_rev_max or sc.robot.v_rev_max
        self.r = sc.robot.radius
        self.comms = policy["name"] != "reactive" and policy.get("comms", True)
        self.initial_mode = "CRUISE"
        self.mode = "WAIT_START" if cfg.start_delay > 0 else "CRUISE"
        self.phase = ""
        self.entered_t: float | None = None
        self.peers: dict[str, dict] = {}
        self.neg: dict | None = None
        self.ylds: dict | None = None
        if cfg.start_refuge:  # e.g. waiting in the stem of a T-junction: leave like a parked yielder
            ref = refuge_by_id(sc, cfg.start_refuge)
            self.initial_mode, self.phase = "YIELD", "parked"
            self.ylds = {"refuge": ref, "refuge_id": ref.id, "peer": None, "t0": 0.0, "rule": "start",
                         "park_timeout": 0.0, "t_parked": 0.0, "forward_out": True}
            if cfg.start_delay <= 0:
                self.mode = "YIELD"
        self.prc: dict | None = None
        self.fallback_reactive = policy["name"] == "reactive"
        self.blocked: dict | None = None
        self.no_neg_until: dict[str, float] = {}
        self.last_state_t = -1e9
        self.events: list[dict] = []
        self.decisions: list[dict] = []
        self.msgs_sent = 0
        self.n_yields = 0
        self.done_t: float | None = None

    # ------------------------------------------------------------------ helpers
    def log(self, t, kind, **kw):
        self.events.append({"t": round(t, 3), "agent": self.id, "event": kind, **kw})

    def facing(self) -> float:
        return 0.0 if self.dir > 0 else math.pi

    def snapshot(self, t, pose) -> Snapshot:
        x, _, th, v = pose
        fwd = v * math.cos(th - self.facing())
        return Snapshot(self.id, t, x, self.dir, max(0.0, fwd), self.goal_x, self.entered_t,
                        self.cfg.urgency, self.cfg.loaded, self.v_max, self.v_rev,
                        self.sc.robot.w_max, self.sc.robot.a_max)

    def fresh_peer(self, pid: str, t: float) -> dict | None:
        s = self.peers.get(pid)
        if s is None or t - s["_rx"] > self.p.state_timeout:
            return None
        return s

    def gap(self, pose, points: np.ndarray, sign: int) -> float:
        """Free distance along the robot's x-axis (sign +1 forward, -1 reverse) to the nearest obstacle point."""
        if len(points) == 0:
            return float("inf")
        x, y, th, _ = pose
        dx, dy = points[:, 0] - x, points[:, 1] - y
        px = math.cos(th) * dx + math.sin(th) * dy
        py = -math.sin(th) * dx + math.cos(th) * dy
        m = (np.abs(py) < self.r + self.p.lateral_margin) & (sign * px > 0)
        if not m.any():
            return float("inf")
        return float(np.min(sign * px[m])) - self.r

    def safe_v(self, pose, points, v: float) -> float:
        if abs(v) < 1e-6:
            return 0.0
        g = self.gap(pose, points, 1 if v > 0 else -1) - self.p.stop_margin
        cap = math.sqrt(2 * self.sc.robot.a_max * max(0.0, g))
        return math.copysign(min(abs(v), cap), v)

    # ------------------------------------------------------------------ low-level controllers
    def lane_cmd(self, pose, target_x: float, v_cap: float | None = None):
        """Follow the centreline y=0 to target_x keeping the robot facing its travel direction."""
        x, y, th, _ = pose
        d = target_x - x
        if abs(d) < self.p.goal_tol:
            return 0.0, self.p.k_heading * wrap(self.facing() - th), True
        s = 1 if d > 0 else -1
        forward = s == self.dir
        look = (s * self.p.lane_lookahead, -y)
        motion_heading = math.atan2(look[1], look[0])
        tgt = motion_heading if forward else wrap(motion_heading + math.pi)
        err = wrap(tgt - th)
        vlim = self.v_max if forward else self.v_rev
        if v_cap is not None:
            vlim = min(vlim, v_cap)
        speed = min(vlim, self.p.k_dist * abs(d), math.sqrt(2 * self.sc.robot.a_max * abs(d)))
        speed *= max(0.0, math.cos(err)) if abs(err) < 0.6 else 0.0
        return (speed if forward else -speed), self.p.k_heading * err, False

    def point_cmd(self, pose, tx: float, ty: float, reverse: bool):
        x, y, th, _ = pose
        dx, dy = tx - x, ty - y
        dist = math.hypot(dx, dy)
        if dist < 0.03:
            return 0.0, 0.0, True
        tgt = math.atan2(dy, dx)
        if reverse:
            tgt = wrap(tgt + math.pi)
        err = wrap(tgt - th)
        vlim = self.v_rev if reverse else self.v_max
        speed = min(vlim, self.p.k_dist * dist, math.sqrt(2 * self.sc.robot.a_max * dist))
        speed *= max(0.0, math.cos(err)) if abs(err) < 0.6 else 0.0
        if dist < 0.08:
            err = 0.0
        return (-speed if reverse else speed), self.p.k_heading * err, False

    def rotate_cmd(self, pose, th_target: float):
        err = wrap(th_target - pose[2])
        if abs(err) < 0.03:
            return 0.0, 0.0, True
        w = max(-0.8 * self.sc.robot.w_max, min(0.8 * self.sc.robot.w_max, 3.0 * err))
        return 0.0, w, False

    # ------------------------------------------------------------------ messaging
    def state_msg(self, t, pose) -> dict:
        x, y, th, v = pose
        return {"type": "STATE", "sender": self.id, "t": t, "x": x, "y": y, "theta": th, "v": v,
                "dir": self.dir, "goal_x": self.goal_x, "mode": self.mode, "phase": self.phase,
                "refuge": (self.ylds or {}).get("refuge_id"), "entered_t": self.entered_t,
                "with": (self.ylds or self.prc or {}).get("peer")}

    def bid_msg(self, t) -> dict:
        n = self.neg
        return {"type": "BID", "sender": self.id, "to": n["peer"], "t": t, "conflict": n["cid"],
                "snapshot": n["mine"].to_dict(), "have_peer": n["theirs"] is not None,
                "decision": {"yielder": n["dec"].yielder, "refuge": n["dec"].refuge} if n.get("dec") else None,
                "have_dec": n.get("their_dec") is not None}

    def handle(self, t, pose, msg):
        if msg["type"] == "STATE":
            self.peers[msg["sender"]] = {**msg, "_rx": t}
        elif msg["type"] == "BID" and msg["to"] == self.id:
            pid = msg["sender"]
            if self.neg is None or self.neg["peer"] != pid:
                if self.comms and (self.mode in ("CRUISE", "NEGOTIATE") or self.can_renegotiate(pid)):
                    self.start_neg(t, pose, pid, cid=msg["conflict"])
                else:
                    return
            n = self.neg
            if n["theirs"] is None:
                n["theirs"] = Snapshot.from_dict(msg["snapshot"])
            if msg["have_peer"]:
                n["acked"] = True
            if msg.get("decision"):
                n["their_dec"] = msg["decision"]
            if msg.get("have_dec"):
                n["dec_acked"] = True

    def can_renegotiate(self, pid) -> bool:
        """A proceeding robot that has been released past its yielder may negotiate with a new oncoming robot."""
        c = self.prc
        return self.mode == "PROCEED" and c is not None and c.get("released") and pid != c["peer"]

    def oncoming_conflict(self, t, x, modes, exclude=None):
        for pid, s in list(self.peers.items()):
            s = self.fresh_peer(pid, t)
            if s is None or pid == exclude or t < self.no_neg_until.get(pid, -1):
                continue
            if (s["dir"] == -self.dir and s["mode"] in modes
                    and self.dir * (s["x"] - x) > 0 and abs(s["x"] - x) < self.p.detect_range):
                return pid
        return None

    def start_neg(self, t, pose, pid, cid=None):
        cid = cid or f"{min(self.id, pid)}-{max(self.id, pid)}@{t:.2f}"
        self.neg = {"peer": pid, "cid": cid, "mine": self.snapshot(t, pose), "theirs": None,
                    "t0": t, "last_tx": -1e9, "acked": False, "decided": None}
        self.mode, self.phase = "NEGOTIATE", ""
        self.log(t, "conflict_detected", peer=pid)

    # ------------------------------------------------------------------ main tick
    def step(self, t: float, pose, perception: Perception, inbox: list[dict]):
        out: list[dict] = []
        for m in inbox:
            self.handle(t, pose, m)
        x = pose[0]
        if self.entered_t is None and self.sc.in_corridor(x):
            self.entered_t = t
        v, w = self.tick(t, pose, perception)
        if self.comms:
            if t - self.last_state_t >= 1.0 / self.sc.comms.get("rate", 5.0) - 1e-9:
                out.append(self.state_msg(t, pose))
                self.last_state_t = t
            n = self.neg
            due = n is not None and t - n["last_tx"] >= self.p.neg_period - 1e-9
            if due and (self.mode == "NEGOTIATE" or (n["decided"] is not None and not n.get("dec_acked")
                                                     and t - n["decided"] < self.p.neg_timeout)):
                out.append(self.bid_msg(t))
                n["last_tx"] = t
        self.msgs_sent += len(out)
        return v, w, out

    def tick(self, t, pose, perc: Perception):
        m = self.mode
        if m == "WAIT_START":
            if t >= self.cfg.start_delay:
                self.mode = self.initial_mode
            return 0.0, 0.0
        if m == "DONE":
            return 0.0, 0.0
        if m == "NEGOTIATE":
            return self.tick_negotiate(t, pose, perc)
        if m == "YIELD":
            return self.tick_yield(t, pose, perc)
        if m == "PROCEED":
            return self.tick_proceed(t, pose, perc)
        return self.tick_cruise(t, pose, perc)

    def yielding_peer(self, t, x):
        """A fresh, oncoming peer that has announced it is yielding (so this robot should proceed)."""
        for pid, s in list(self.peers.items()):
            s = self.fresh_peer(pid, t)
            if (s is not None and s["mode"] == "YIELD" and s.get("refuge") and s["dir"] == -self.dir
                    and self.dir * (s["x"] - x) > -0.3):
                return pid, s
        return None

    def tick_cruise(self, t, pose, perc):
        x = pose[0]
        if self.dir * (x - self.goal_x) >= -self.p.goal_tol:
            self.mode, self.done_t = "DONE", t
            self.log(t, "goal_reached")
            return 0.0, 0.0
        yp = self.yielding_peer(t, x) if self.comms else None
        if yp is not None:
            ref = refuge_by_id(self.sc, yp[1]["refuge"])
            if ref is not None and self.dir * (pass_x(ref, self.dir, self.sc) - x) > 0:
                self.log(t, "peer_yielding", peer=yp[0], refuge=ref.id)
                self.begin_proceed(t, ref, yp[0])
                return self.brake()
        if self.comms and not self.fallback_reactive:
            pid = self.oncoming_conflict(t, x, ("CRUISE", "NEGOTIATE", "WAIT_START"))
            if pid is not None:
                self.start_neg(t, pose, pid)
                return self.brake()
        target = self.goal_x
        g = self.goal_ref
        if g is not None:
            if self.refuge_taken(t, g, perc):
                # destination branch still occupied: wait outside the window its occupant needs to leave
                lim = g.span / 2 + 2 * self.r + 2 * self.sc.clearance + 2.0 + 0.3
                target = g.x - self.dir * lim
                if self.dir * (target - x) <= 0:
                    return self.brake()
            elif self.dir * (x - g.x) >= -self.p.goal_tol:
                self.begin_yield(t, g, None, rule="goal")
                self.n_yields -= 1
                self.ylds["goal"] = True
                self.phase = "turn_in"
                return self.brake()
        v, w, _ = self.lane_cmd(pose, target)
        vs = self.safe_v(pose, perc.points, v)
        if self.fallback_reactive and self.reactive_blocked(t, pose, perc, v, vs):
            return self.brake()
        return vs, w

    def brake(self):
        return 0.0, 0.0

    # ------------------------------------------------------------------ reactive (no comms) behaviour
    def reactive_blocked(self, t, pose, perc, v, vs) -> bool:
        """Start a yield manoeuvre if blocked by an oncoming robot for longer than `patience`."""
        if abs(v) < 0.05 or abs(vs) > 0.03 or not perc.peers:
            self.blocked = None
            return False
        g = self.gap(pose, perc.points, 1)
        if self.blocked is None:
            self.blocked = {"t0": t, "gap": g, "patience": float(self.rng.uniform(*self.p.patience))}
            return False
        if g > self.blocked["gap"] + 0.05:
            self.blocked = None
            return False
        if t - self.blocked["t0"] < self.blocked["patience"]:
            return False
        x = pose[0]
        behind = [r for r in self.sc.refuges()
                  if self.dir * (r.x - x) <= 0.05 and self.dir * (self.goal_x - r.x) > 0
                  and not self.refuge_taken(t, r, perc)]
        if not behind:
            return False
        ref = min(behind, key=lambda r: abs(r.x - x))
        self.blocked = None
        self.begin_yield(t, ref, peer=None, rule="reactive")
        return True

    # ------------------------------------------------------------------ negotiation
    def tick_negotiate(self, t, pose, perc):
        n = self.neg
        if n["theirs"] is None:
            yp = self.yielding_peer(t, pose[0])
            if yp is not None and yp[0] == n["peer"]:
                self.neg, self.mode = None, "CRUISE"
                return self.tick_cruise(t, pose, perc)
            if t - n["t0"] > self.p.neg_timeout:
                self.log(t, "negotiation_timeout", peer=n["peer"])
                self.no_neg_until[n["peer"]] = t + 10.0
                self.neg, self.mode = None, "CRUISE"
                self.fallback_reactive = True
            return self.brake()
        if n.get("dec") is None:
            taken = {r.id for r in self.sc.refuges()
                     if r.kind == "bay" and self.refuge_taken(t, r, perc, ignore=n["peer"])}
            sc = _WithoutRefuges(self.sc, taken) if taken else self.sc
            d: Decision = decide(self.policy, [n["mine"], n["theirs"]], sc)
            n["decided"], n["dec"] = t, d
            rec = {"t": t, "agent": self.id, "peer": n["peer"], "yielder": d.yielder, "refuge": d.refuge,
                   "rule": d.rule, "t_detect": n["t0"], **{k: v for k, v in d.detail.items() if k != "plan"}}
            if "plan" in d.detail:
                rec["predicted"] = d.detail["plan"]
            self.decisions.append(rec)
            self.log(t, "decision", yielder=d.yielder, refuge=d.refuge, rule=d.rule)
        d = n["dec"]
        td = n.get("their_dec")
        # commit: act once the peer's decision has arrived (or the commit window expires)
        if td is None and t - n["decided"] < self.p.neg_timeout:
            return self.brake()
        yielder, ref = d.yielder, refuge_of(d, self.sc)
        if td is not None and (td["yielder"], td["refuge"]) != (d.yielder, d.refuge):
            if self.id > n["peer"]:  # disagreement after lost messages: the lower id's decision wins
                yielder = td["yielder"]
                ref = refuge_by_id(self.sc, td["refuge"]) if td["refuge"] else None
            self.log(t, "decision_mismatch", adopted=self.id > n["peer"], yielder=yielder)
        elif td is None:
            self.log(t, "commit_timeout", peer=n["peer"])
        if ref is None:
            self.mode, self.fallback_reactive = "CRUISE", True
            self.no_neg_until[n["peer"]] = t + 10.0
        elif yielder == self.id:
            self.begin_yield(t, ref, peer=n["peer"], rule=d.rule)
        else:
            self.begin_proceed(t, ref, n["peer"])
        return self.brake()

    def begin_yield(self, t, ref: Refuge, peer, rule):
        self.mode, self.phase = "YIELD", "to_refuge"
        self.n_yields += 1
        self.ylds = {"refuge": ref, "refuge_id": ref.id, "peer": peer, "t0": t, "rule": rule,
                     "park_timeout": float(self.rng.uniform(*self.p.park_timeout))}
        self.log(t, "yield_start", refuge=ref.id, rule=rule)

    def begin_proceed(self, t, ref: Refuge, peer):
        self.mode, self.phase = "PROCEED", "hold"
        self.prc = {"refuge": ref, "peer": peer, "t0": t, "hold": hold_x(ref, self.dir, self.sc),
                    "pass": pass_x(ref, self.dir, self.sc)}
        self.log(t, "proceed_start", refuge=ref.id)

    def peer_out_of_lane(self, t, peer, ref: Refuge, perc) -> bool:
        s = self.fresh_peer(peer, t) if peer else None
        if s is not None:
            if s["mode"] == "YIELD" and s["phase"] == "parked":
                return True
            if s["mode"] == "DONE":
                return True
        hw = self.sc.half_width
        near = [(px, py) for px, py in perc.peers if abs(px - ref.x) < ref.span / 2 + 0.3]
        return any(abs(py) > hw + 0.15 for _, py in near) and not any(abs(py) < hw for _, py in near)

    def tick_proceed(self, t, pose, perc):
        c = self.prc
        x = pose[0]
        if c.get("released"):
            pid = self.oncoming_conflict(t, x, ("CRUISE", "NEGOTIATE"), exclude=c["peer"]) if self.comms else None
            if pid is not None:
                self.prc = None
                self.start_neg(t, pose, pid)
                return self.brake()
            if self.dir * (x - c["pass"]) > 0:
                self.mode, self.phase, self.prc, self.neg = "CRUISE", "", None, None
                self.log(t, "passed_refuge")
            v, w, _ = self.lane_cmd(pose, self.goal_x)
            return self.safe_v(pose, perc.points, v), w
        s = self.fresh_peer(c["peer"], t) if self.comms else None
        if s is not None and s["mode"] == "CRUISE" and s["dir"] != self.dir and self.dir * (s["x"] - x) > 0:
            # the robot we are waiting for is driving towards us, not yielding: the agreement is stale
            self.log(t, "proceed_contradicted", peer=c["peer"])
            self.prc = None
            self.start_neg(t, pose, s["sender"])
            return self.brake()
        if self.peer_out_of_lane(t, c["peer"], c["refuge"], perc):
            c["released"] = True
            self.phase = "pass"
            self.log(t, "released")
        elif t - c["t0"] > self.p.proceed_timeout:
            self.log(t, "proceed_timeout")
            self.mode, self.prc, self.neg, self.fallback_reactive = "CRUISE", None, None, True
            return self.brake()
        target = c["hold"] if self.dir * (c["hold"] - x) > 0 else x
        v, w, _ = self.lane_cmd(pose, target)
        return self.safe_v(pose, perc.points, v), w

    def peer_passed(self, t, pose, perc) -> bool:
        c = self.ylds
        ref: Refuge = c["refuge"]
        need = ref.span / 2 + self.r + self.sc.clearance
        pdir = -self.dir
        for pid in list(self.peers):  # e.g. a convoy follower that is also passing this refuge
            s = self.fresh_peer(pid, t)
            if (pid != c["peer"] and s is not None and s["mode"] == "PROCEED" and s.get("with") == self.id
                    and pdir * (s["x"] - ref.x) <= need):
                return False
        if c["peer"]:
            s = self.fresh_peer(c["peer"], t)
            if s is not None:
                return s["mode"] == "DONE" or pdir * (s["x"] - ref.x) > need
        if any(pdir * (px - ref.x) > need and abs(py) < self.sc.half_width + 0.1 for px, py in perc.peers):
            return self.lane_clear(ref, perc)
        if t - c["t_parked"] > c["park_timeout"]:
            return self.lane_clear(ref, perc)
        return False

    def lane_clear(self, ref: Refuge, perc, extra: float = 0.0) -> bool:
        lim = ref.span / 2 + 2 * self.r + 2 * self.sc.clearance + extra
        return not any(abs(px - ref.x) < lim and abs(py) < self.sc.half_width + 0.1 for px, py in perc.peers)

    def refuge_taken(self, t, ref: Refuge, perc, ignore=None) -> bool:
        for pid in list(self.peers):
            if pid == ignore:
                continue
            s = self.fresh_peer(pid, t)
            if s is not None and s["mode"] == "YIELD" and s.get("refuge") == ref.id:
                return True
        return self.bay_seen_occupied(ref, perc)

    def bay_seen_occupied(self, ref: Refuge, perc) -> bool:
        hw = self.sc.half_width
        return any(abs(px - ref.x) < ref.span / 2 + 0.1 and abs(py) > hw - 0.05 and py * ref.side > 0
                   for px, py in perc.peers) if ref.kind == "bay" else False

    def passer_pending(self, t, ref: Refuge) -> bool:
        """A peer is still proceeding past this refuge on the understanding that we wait in it."""
        need = ref.span / 2 + 2 * self.r
        for pid in list(self.peers):
            s = self.fresh_peer(pid, t)
            if s is not None and s["mode"] == "PROCEED" and s.get("with") == self.id \
                    and s["dir"] * (s["x"] - ref.x) <= need:
                return True
        return False

    def tick_yield(self, t, pose, perc):
        c = self.ylds
        ref: Refuge = c["refuge"]
        ph = self.phase
        if ph in ("to_refuge", "turn_in") and not c.get("goal"):
            # two robots heading for the same refuge (e.g. after lost bids): the higher id gives way
            for pid in list(self.peers):
                s = self.fresh_peer(pid, t)
                if (s is not None and s["mode"] == "YIELD" and s.get("refuge") == ref.id
                        and s["phase"] in ("to_refuge", "turn_in", "park_in", "parked")
                        and (s["phase"] != ph or self.id > pid)
                        and self.dir * (pass_x(ref, self.dir, self.sc) - pose[0]) > 0):
                    self.log(t, "yield_conflict", peer=pid, refuge=ref.id)
                    self.n_yields -= 1
                    self.ylds = None
                    self.begin_proceed(t, ref, pid)
                    return self.brake()
        if ph == "to_refuge" and c["peer"] is not None and self.id > c["peer"]:
            # lost messages left both robots yielding to each other in different refuges: the lower id keeps yielding
            s = self.fresh_peer(c["peer"], t)
            if (s is not None and s["mode"] == "YIELD" and s.get("with") == self.id and s.get("refuge")
                    and s["phase"] in ("to_refuge", "turn_in", "park_in", "parked")):
                pref = refuge_by_id(self.sc, s["refuge"])
                self.log(t, "yield_conflict", peer=c["peer"], refuge=pref.id)
                self.n_yields -= 1
                self.ylds = None
                self.begin_proceed(t, pref, c["peer"])
                return self.brake()
        if ph == "to_refuge":
            v, w, done = self.lane_cmd(pose, ref.x)
            if done and self.bay_seen_occupied(ref, perc):
                # sensors show another robot already in the bay (decisions diverged): pass it instead
                self.log(t, "refuge_occupied", refuge=ref.id)
                self.n_yields -= 1
                pid = c["peer"]
                self.ylds = None
                self.begin_proceed(t, ref, pid)
                return self.brake()
            if done:
                self.phase = "turn_in"
            return self.safe_v(pose, perc.points, v), w
        if ph == "turn_in":
            v, w, done = self.rotate_cmd(pose, ref.side * math.pi / 2)
            if done:
                self.phase = "park_in"
            return v, w
        if ph == "park_in":
            v, w, done = self.point_cmd(pose, ref.x, ref.park_y, reverse=False)
            if done and c.get("goal"):
                self.mode, self.done_t, self.phase = "DONE", t, ""
                self.log(t, "goal_reached", refuge=ref.id)
            elif done:
                self.phase, c["t_parked"] = "parked", t
                self.log(t, "parked", refuge=ref.id)
            return v, w
        if ph == "parked":
            if self.peer_passed(t, pose, perc):
                self.phase = "back_out"
                self.log(t, "leaving_refuge", refuge=ref.id)
            return 0.0, 0.0
        if ph == "back_out":
            if not self.lane_clear(ref, perc, extra=2.0 if c.get("forward_out") else 0.0) or (
                    not c.get("forward_out") and self.passer_pending(t, ref)):
                if abs(pose[1]) > self.sc.half_width + self.r:
                    self.phase = "parked"  # still inside the refuge: let the peer pass first
                    return 0.0, 0.0
                if not c.get("forward_out"):
                    self.phase = "park_in"  # partly out and the lane is not clear: drive back in and wait
                    return 0.0, 0.0
                # leaving a T-junction stem and already in the lane: join it and negotiate normally
            v, w, done = self.point_cmd(pose, ref.x, 0.0, reverse=not c.get("forward_out"))
            if done:
                self.phase = "turn_out"
            return v, w
        if ph == "turn_out":
            v, w, done = self.rotate_cmd(pose, self.facing())
            if done:
                self.log(t, "yield_done", refuge=ref.id)
                self.mode, self.phase, self.ylds, self.neg = "CRUISE", "", None, None
            return v, w
        raise RuntimeError(ph)


class _WithoutRefuges:
    """Scenario view that hides refuges already occupied by a third robot."""

    def __init__(self, sc: Scenario, taken: set[str]):
        self._sc, self._taken = sc, taken

    def __getattr__(self, name):
        return getattr(self._sc, name)

    def refuges(self):
        return [r for r in self._sc.refuges() if r.id not in self._taken]


def is_negotiating(policy: dict) -> bool:
    return policy["name"] in NEGOTIATING_POLICIES
