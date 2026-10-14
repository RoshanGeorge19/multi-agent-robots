"""Referee: starts the (paused) Gazebo world once all agents are up, measures the episode and writes JSON."""

from __future__ import annotations

import json
import math
import subprocess
import time
from pathlib import Path

import rclpy
from nav_msgs.msg import Odometry
from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

from amr_negotiation.geometry import footprints_overlap, load_scenario


class Referee(Node):
    def __init__(self):
        super().__init__("referee")
        self.declare_parameter("scenario", "")
        self.declare_parameter("policy", "")
        self.declare_parameter("output", "/tmp/amrneg_gazebo_result.json")
        self.declare_parameter("world", "corridor")
        self.declare_parameter("t_max", 0.0)
        self.declare_parameter("linger", 3.0)
        g = lambda n: self.get_parameter(n).value
        self.sc = load_scenario(g("scenario"))
        self.policy, self.out, self.world = g("policy"), Path(g("output")), g("world")
        self.t_max = g("t_max") or self.sc.t_max
        self.linger = g("linger")
        self.ids = [a.id for a in self.sc.agents]
        self.ready: set[str] = set()
        self.started = False
        self.t0 = None
        self.pose: dict[str, tuple] = {}
        self.min_dist = math.inf
        self.collision_t = None
        self.gone: set[str] = set()
        self.reverse = {i: 0.0 for i in self.ids}
        self.last_t = {}
        self.events, self.summaries = [], {}
        self.msgs = 0
        self.trace = []
        self.finished_at = None
        qos = QoSProfile(depth=100, reliability=ReliabilityPolicy.RELIABLE)
        self.create_subscription(String, "/amr_negotiation/events", self.on_event, qos)
        self.create_subscription(String, "/amr_negotiation/bus", self.on_bus, qos)
        for i in self.ids:
            self.create_subscription(Odometry, f"/{i}/ground_truth", lambda m, i=i: self.on_odom(i, m), 10)
        self.create_timer(1.0, self.on_wall, clock=Clock(clock_type=ClockType.STEADY_TIME))
        self.create_timer(0.1, self.on_tick)

    def sim_t(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def on_event(self, m):
        e = json.loads(m.data)
        if e["event"] == "hello":
            self.ready.add(e["agent"])
        elif e["event"] == "summary":
            self.summaries[e["agent"]] = e
            if self.sc.despawn_done and e["agent"] not in self.gone:  # as in sim2d: finished robots leave the world
                self.gone.add(e["agent"])
                subprocess.Popen(["gz", "service", "-s", f"/world/{self.world}/remove", "--reqtype", "gz.msgs.Entity",
                                  "--reptype", "gz.msgs.Boolean", "--timeout", "2000",
                                  "--req", f'name: "{e["agent"]}" type: MODEL'])
            self.get_logger().info(f"{e['agent']} done at t={e['arrival']:.1f}s")
        else:
            self.events.append(e)
            self.get_logger().info(f"[{e['t']:.2f}] {e['agent']}: {e['event']} "
                                   + " ".join(f"{k}={v}" for k, v in e.items() if k not in ("t", "agent", "event")))

    def on_bus(self, _m):
        self.msgs += 1

    def on_odom(self, i, m):
        p, v = m.pose.pose.position, m.twist.twist.linear.x
        t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        if i in self.last_t and v < 0:
            self.reverse[i] += -v * (t - self.last_t[i])
        self.last_t[i] = t
        q = m.pose.pose.orientation
        th = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        self.pose[i] = (p.x, p.y, th, v)

    def on_wall(self):
        if not self.started and self.ready >= set(self.ids):
            self.get_logger().info(f"all agents ready {sorted(self.ready)}: unpausing world '{self.world}'")
            subprocess.run(["gz", "service", "-s", f"/world/{self.world}/control", "--reqtype",
                            "gz.msgs.WorldControl", "--reptype", "gz.msgs.Boolean", "--timeout", "5000",
                            "--req", "pause: false"], check=False)
            self.started = True
            self.wall0 = time.time()

    def on_tick(self):
        if not self.started or len(self.pose) < len(self.ids):
            return
        t = self.sim_t()
        for a in range(len(self.ids)):
            for b in range(a + 1, len(self.ids)):
                if self.ids[a] in self.gone or self.ids[b] in self.gone:
                    continue
                pa, pb = self.pose[self.ids[a]], self.pose[self.ids[b]]
                d = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
                self.min_dist = min(self.min_dist, d)
                if self.collision_t is None and d < 0.6 and footprints_overlap(pa, pb, self.sc.robot.footprint):
                    self.collision_t = t
                    self.get_logger().warn(f"contact at t={t:.2f}s d={d:.3f}")
        self.trace.append({"t": round(t, 2), **{i: [round(v, 4) for v in self.pose[i]] for i in self.ids}})
        done = set(self.summaries) >= set(self.ids)
        if (done or t > self.t_max) and self.finished_at is None:
            self.finished_at = t
            self.write(done, t)
        if self.finished_at is not None and t - self.finished_at > self.linger:
            raise SystemExit(0)

    def write(self, done, t):
        arrivals = {i: self.summaries[i]["arrival"] for i in self.summaries}
        decisions = [d for s in self.summaries.values() for d in s.get("decisions", [])]
        res = {
            "simulator": "gazebo", "scenario": self.sc.name, "policy": self.policy,
            "success": done and self.collision_t is None, "deadlock": not done,
            "collision": self.collision_t is not None, "t_end": t,
            "makespan": max(arrivals.values()) if done else None,
            "min_clearance": self.min_dist - 2 * self.sc.robot.radius,
            "agents": {i: {"arrival": arrivals.get(i), "reverse_dist": self.reverse[i],
                           "yields": self.summaries.get(i, {}).get("yields")} for i in self.ids},
            "yielder": decisions[0]["yielder"] if decisions else next(
                (e["agent"] for e in self.events if e["event"] == "yield_start"), None),
            "rule": decisions[0]["rule"] if decisions else None,
            "refuge": decisions[0]["refuge"] if decisions else None,
            "msgs": self.msgs, "wall_time": time.time() - self.wall0,
            "events": sorted(self.events, key=lambda e: e["t"]), "decisions": decisions, "trace": self.trace,
        }
        self.out.parent.mkdir(parents=True, exist_ok=True)
        self.out.write_text(json.dumps(res, indent=1, default=float))
        self.get_logger().info(
            f"RESULT success={res['success']} makespan={res['makespan']} yielder={res['yielder']} "
            f"rule={res['rule']} min_clearance={res['min_clearance']:.3f} -> {self.out}")


def main():
    rclpy.init()
    node = Referee()
    try:
        rclpy.spin(node)
    except (SystemExit, KeyboardInterrupt):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
