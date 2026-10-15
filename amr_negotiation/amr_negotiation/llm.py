"""LLM negotiator: ask a local or remote OpenAI-compatible chat endpoint (e.g. llama.cpp `llama-server`) who yields.

Modes
  mediator  one call sees both robots' snapshots and names the yielder (and optionally the refuge).
  agents    one call per robot, each prompt written from that robot's point of view (its own state and the
            peer's broadcast snapshot); the robot answers "yield" or "proceed". If exactly one says yield it
            yields, otherwise the rulebook decides.
Both robots evaluate the same prompts from the same frozen snapshots, so with temperature 0 (and the response
cache) they reach the same decision without an extra message round. Any failure (server down, bad JSON,
infeasible choice) falls back to the rulebook and is recorded in the decision detail.

Policy config (all optional), e.g. {"name": "llm", "llm": {"mode": "agents", "model": "qwen"}}:
  base_url     default $AMRNEG_LLM_URL or http://localhost:8080/v1
  model        default $AMRNEG_LLM_MODEL or "local"
  mode         mediator | agents (default mediator)
  info         raw | plans: plans adds each robot's predicted yield cost (s) to the prompt (default raw)
  temperature  0.0;  seed 0;  max_tokens 256;  timeout 120 s;  constrain true (JSON-schema constrained output)
  think_time   "measured" (charge the real LLM latency as sim decision time; default), or a number of seconds
  cache        path of a JSON-lines prompt/response cache (default: in-memory only)
  rulebook     fallback rulebook (default rulebooks/default.yaml order)
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request

from .geometry import Scenario
from .planner import Snapshot, feasible, plan_times

SYSTEM = ("You coordinate autonomous mobile robots (TurtleBot3 Waffle) in a warehouse. The corridor is a single lane: "
          "two robots cannot pass each other inside it. One robot must pull into a refuge (a side bay or an end room) "
          "and wait while the other passes. Reversing is slower than driving forward. Answer only with JSON.")

_MEM: dict[str, dict] = {}


def _cfg(policy: dict) -> dict:
    c = dict(policy.get("llm") or {})
    c.setdefault("base_url", os.environ.get("AMRNEG_LLM_URL", "http://localhost:8080/v1"))
    c.setdefault("model", os.environ.get("AMRNEG_LLM_MODEL", "local"))
    for k, v in (("mode", "mediator"), ("info", "raw"), ("temperature", 0.0), ("seed", 0), ("max_tokens", 256),
                 ("timeout", 120.0), ("constrain", True), ("think_time", "measured"), ("cache", None)):
        c.setdefault(k, v)
    return c


def post_json(url: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    key = os.environ.get("AMRNEG_LLM_API_KEY")
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _load_cache(path):
    if not path or path in _MEM.setdefault("__loaded__", {}):
        return
    _MEM["__loaded__"][path] = True
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                try:
                    e = json.loads(line)
                    _MEM[e["key"]] = e
                except (json.JSONDecodeError, KeyError):
                    continue


def chat(cfg: dict, messages: list[dict], schema: dict) -> dict:
    """Return {"text", "latency", "cached", "error"}; cached entries keep the latency of the original call."""
    body = {"model": cfg["model"], "messages": messages, "temperature": cfg["temperature"], "seed": cfg["seed"],
            "max_tokens": cfg["max_tokens"]}
    if cfg["constrain"]:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "answer", "schema": schema}}
    key = hashlib.sha256(json.dumps([cfg["base_url"], body], sort_keys=True).encode()).hexdigest()
    _load_cache(cfg["cache"])
    if key in _MEM:
        e = _MEM[key]
        return {"text": e["text"], "latency": e["latency"], "cached": True, "error": None}
    t0 = time.perf_counter()
    try:
        r = post_json(cfg["base_url"].rstrip("/") + "/chat/completions", body, cfg["timeout"])
        text = r["choices"][0]["message"]["content"] or ""
    except (urllib.error.URLError, OSError, KeyError, IndexError, ValueError) as ex:
        return {"text": "", "latency": time.perf_counter() - t0, "cached": False, "error": f"{type(ex).__name__}: {ex}"}
    e = {"key": key, "text": text, "latency": time.perf_counter() - t0, "model": cfg["model"]}
    _MEM[key] = e
    if cfg["cache"]:
        with open(cfg["cache"], "a") as f:
            f.write(json.dumps({**e, "messages": messages}) + "\n")
    return {**{k: e[k] for k in ("text", "latency")}, "cached": False, "error": None}


def parse(text: str) -> dict | None:
    s, e = text.find("{"), text.rfind("}")
    if s < 0 or e <= s:
        return None
    try:
        out = json.loads(text[s:e + 1])
    except json.JSONDecodeError:
        return None
    return out if isinstance(out, dict) else None


# ---------------------------------------------------------------- prompts

def _heading(s: Snapshot) -> str:
    return "+x (east)" if s.dir > 0 else "-x (west)"


def describe_robot(s: Snapshot, sc: Scenario) -> str:
    where = ("inside the corridor" if 0.0 <= s.x <= sc.length else "outside the corridor (in an end room)")
    entered = f"entered the corridor at t={s.entered_t:.1f} s" if s.entered_t is not None else "not yet in the corridor"
    return (f"robot {s.id}: x={s.x:.2f} m, {where}, heading {_heading(s)}, goal x={s.goal_x:.1f} m, "
            f"speed now {s.v:.2f} m/s (max forward {s.v_max:.2f}, max reverse {s.v_rev_max:.2f} m/s), "
            f"urgency {s.urgency:g} (1 = normal; higher = its delay costs more), "
            f"{'loaded (carrying a payload)' if s.loaded else 'unloaded'}, {entered}")


def describe_refuges(me: Snapshot, other: Snapshot, sc: Scenario, info: str) -> list[str]:
    rows = []
    for r in sc.refuges():
        if not feasible(r, me, other, sc):
            continue
        d = r.x - me.x
        rel = "behind it (it must reverse)" if me.dir * d < 0 else "ahead of it"
        line = f"  {r.id}: {r.kind} at x={r.x:.2f} m, {abs(d):.2f} m {rel}"
        if info == "plans":
            p = plan_times(r, me, other, sc)
            line += (f"; predicted delay if {me.id} yields here: {me.id} {p['yielder_delay']:.1f} s, "
                     f"{other.id} {p['proceeder_delay']:.1f} s")
        rows.append(line)
    return rows


def situation(a: Snapshot, b: Snapshot, sc: Scenario, info: str) -> str:
    lines = [f"Corridor: single lane from x=0 to x={sc.length:.1f} m, {sc.width:.2f} m wide. Time t={max(a.t, b.t):.1f} s.",
             describe_robot(a, sc), describe_robot(b, sc)]
    for me, other in ((a, b), (b, a)):
        rs = describe_refuges(me, other, sc, info)
        lines.append(f"Refuges robot {me.id} could pull into to let {other.id} pass:" if rs else
                     f"Robot {me.id} has no refuge it can pull into.")
        lines += rs
    return "\n".join(lines)


def _ids_schema(ids, refs, key, values):
    return {"type": "object", "properties": {"reason": {"type": "string", "maxLength": 300},
                                            key: {"type": "string", "enum": list(values)},
                                            "refuge": {"type": "string", "enum": list(refs) + ["any"]}},
            "required": ["reason", key, "refuge"]}


def mediator_messages(a: Snapshot, b: Snapshot, sc: Scenario, info: str):
    q = (situation(a, b, sc, info) + "\n\nDecide which robot yields so that the urgency-weighted total delay of both "
         "robots is as small as possible. Reply as JSON: "
         '{"reason": "<one sentence>", "yielder": "<robot id>", "refuge": "<refuge id, or any>"}')
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": q}]


def agent_messages(me: Snapshot, other: Snapshot, sc: Scenario, info: str):
    a, b = sorted((me, other), key=lambda s: s.id)
    q = (f"You are robot {me.id}. Robot {other.id} has broadcast its state to you.\n" + situation(a, b, sc, info) +
         f"\n\nShould you ({me.id}) yield, or proceed and let {other.id} yield? Aim to keep the urgency-weighted "
         "total delay of both robots small; if you both proceed or both yield, a fixed rulebook decides instead. "
         'Reply as JSON: {"reason": "<one sentence>", "action": "yield" or "proceed", "refuge": "<refuge id, or any>"}')
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": q}]


# ---------------------------------------------------------------- decision

def _refuge_choice(name, Y, P, sc):
    """The named refuge if feasible for Y, else the planner's best (None if Y has no refuge)."""
    from .planner import best_plan

    for r in sc.refuges():
        if r.id == name and feasible(r, Y, P, sc):
            return plan_times(r, Y, P, sc)
    return best_plan(Y, P, sc)


def decide_llm(snaps: list[Snapshot], sc: Scenario, policy: dict):
    from .policies import Decision, decide_rulebook, load_rulebook

    cfg = _cfg(policy)
    a, b = sorted(snaps, key=lambda s: s.id)
    refs = [r.id for r in sc.refuges()]
    calls, choice = [], {}
    if cfg["mode"] == "mediator":
        r = chat(cfg, mediator_messages(a, b, sc, cfg["info"]), _ids_schema([a.id, b.id], refs, "yielder", (a.id, b.id)))
        calls.append({"role": "mediator", **r})
        ans = parse(r["text"]) or {}
        calls[-1]["answer"] = ans
        y = ans.get("yielder")
        if y in (a.id, b.id):
            choice = {"yielder": y, "refuge": ans.get("refuge")}
    elif cfg["mode"] == "agents":
        acts = {}
        for me, other in ((a, b), (b, a)):
            r = chat(cfg, agent_messages(me, other, sc, cfg["info"]),
                     _ids_schema([me.id], refs, "action", ("yield", "proceed")))
            ans = parse(r["text"]) or {}
            calls.append({"role": me.id, **r, "answer": ans})
            acts[me.id] = ans.get("action")
        ylds = [i for i in (a.id, b.id) if acts[i] == "yield"]
        prc = [i for i in (a.id, b.id) if acts[i] == "proceed"]
        if len(ylds) == 1 and len(prc) == 1:
            ans = calls[0]["answer"] if ylds[0] == a.id else calls[1]["answer"]
            choice = {"yielder": ylds[0], "refuge": ans.get("refuge")}
    else:
        raise ValueError(f"llm.mode must be mediator or agents, not {cfg['mode']!r}")

    think = sum(c["latency"] for c in calls) if cfg["think_time"] == "measured" else float(cfg["think_time"] or 0.0)
    detail = {"llm_mode": cfg["mode"], "llm_model": cfg["model"], "think_time": think,
              "llm_latency": sum(c["latency"] for c in calls), "llm_cached": all(c["cached"] for c in calls),
              "llm_error": next((c["error"] for c in calls if c["error"]), None),
              "llm_answers": [{"role": c["role"], **c["answer"]} for c in calls]}
    if choice:
        Y = a if choice["yielder"] == a.id else b
        P = b if Y is a else a
        plan = _refuge_choice(choice["refuge"], Y, P, sc)
        if plan is not None:
            return Decision(Y.id, P.id, plan["refuge"], f"llm_{cfg['mode']}", {**detail, "plan": plan})
        why = "infeasible"
    elif detail["llm_error"]:
        why = "error"
    elif cfg["mode"] == "agents" and all(c["answer"].get("action") in ("yield", "proceed") for c in calls):
        why = "disagree"
    else:
        why = "parse"
    d = decide_rulebook(snaps, sc, load_rulebook(policy.get("rulebook")))
    return Decision(d.yielder, d.proceeder, d.refuge, f"llm_fallback_{why}:{d.rule}", {**d.detail, **detail})
