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
                 ("timeout", 120.0), ("constrain", True), ("think_time", "measured"), ("cache", None),
                 ("vision", "none"), ("extra_body", None), ("tiebreak", "")):
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
    if cfg["extra_body"]:
        body.update(cfg["extra_body"])
    key = hashlib.sha256(json.dumps([cfg["base_url"], body], sort_keys=True).encode()).hexdigest()
    _load_cache(cfg["cache"])
    if key in _MEM:
        e = _MEM[key]
        return {"text": e["text"], "latency": e["latency"], "reasoning": e.get("reasoning", ""),
                "cached": True, "error": None}
    t0 = time.perf_counter()
    try:
        r = post_json(cfg["base_url"].rstrip("/") + "/chat/completions", body, cfg["timeout"])
        msg = r["choices"][0]["message"]
        text = msg.get("content") or ""
        reasoning = msg.get("reasoning") or msg.get("reasoning_content") or ""
    except (urllib.error.URLError, OSError, KeyError, IndexError, ValueError) as ex:
        return {"text": "", "reasoning": "", "latency": time.perf_counter() - t0, "cached": False,
                "error": f"{type(ex).__name__}: {ex}"}
    e = {"key": key, "text": text, "reasoning": reasoning, "latency": time.perf_counter() - t0,
         "model": cfg["model"]}
    _MEM[key] = e
    if cfg["cache"]:
        with open(cfg["cache"], "a") as f:
            f.write(json.dumps({**e, "messages": messages}) + "\n")
    return {**{k: e[k] for k in ("text", "latency", "reasoning")}, "cached": False, "error": None}


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


def render_scene(a: Snapshot, b: Snapshot, sc: Scenario) -> str:
    """Top-down PNG of the encounter as a data URL (used by llm.vision != 'none')."""
    import base64
    import io

    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    from .viz import COLORS, draw_map

    fig, ax = plt.subplots(figsize=(10, 3.4))
    draw_map(ax, sc)
    for k, s in enumerate((a, b)):
        y = -0.09 if k == 0 else 0.09  # small offset so both discs stay visible
        ax.add_patch(Circle((s.x, y), sc.robot.radius, fc=COLORS[k % 5], alpha=0.65, ec="k"))
        ax.arrow(s.x, y, 0.45 * s.dir, 0.0, head_width=0.07, head_length=0.12,
                 fc="k", length_includes_head=True)
        ax.annotate(f"{s.id} (u={s.urgency:g}{', loaded' if s.loaded else ''})",
                    (s.x, y + (0.5 if k else -0.5)), ha="center", fontsize=8)
        ax.plot(s.goal_x, y, marker="*", ms=13, color=COLORS[k % 5], mec="k")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


_IMG_LEGEND = (" The image is a top-down map of the same encounter: the corridor and its refuges "
               "(x marks are parking poses), each robot is a coloured disc (the first robot listed is "
               "blue, the second is orange) with a black arrow showing its heading, and the matching "
               "star is its goal. Numbers in the text are authoritative if they disagree.")

_EGO_LEGEND = (" The image is your own forward view from your onboard camera: the corridor and its "
               "refuges (x marks are parking poses), you are the blue disc with a black heading arrow, "
               "the star is your goal, and the orange disc is the other robot if it is in view.")


def render_ego(me: Snapshot, other: Snapshot, sc: Scenario) -> str:
    """Egocentric corridor view for one robot (vision='ego'): centred on me, ~7 m field ahead."""
    import base64
    import io

    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    from .viz import COLORS, draw_map

    fig, ax = plt.subplots(figsize=(10, 3.4))
    draw_map(ax, sc)
    for s, k in ((me, 0), (other, 1)):
        ax.add_patch(Circle((s.x, 0.0), sc.robot.radius, fc=COLORS[k % 5], alpha=0.65, ec="k"))
        ax.arrow(s.x, 0.0, 0.45 * s.dir, 0.0, head_width=0.07, head_length=0.12,
                 fc="k", length_includes_head=True)
        ax.annotate(s.id, (s.x, 0.5), ha="center", fontsize=8)
    ax.plot(me.goal_x, 0.0, marker="*", ms=13, color=COLORS[0], mec="k")
    lo, hi = sorted((me.x - 1.5, me.x + me.dir * 6.5))  # mostly forward view
    ax.set_xlim(lo, hi)
    ax.set_title(f"{me.id} onboard view", fontsize=9)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _content(q: str, sc: Scenario, vision: str, img: str | None):
    if vision == "none" or img is None:
        return q
    legend = _EGO_LEGEND if vision == "ego" else _IMG_LEGEND
    return [{"type": "text", "text": q + legend},
            {"type": "image_url", "image_url": {"url": img}}]


def _ids_schema(ids, refs, key, values):
    return {"type": "object", "properties": {"reason": {"type": "string", "maxLength": 300},
                                            key: {"type": "string", "enum": list(values)},
                                            "refuge": {"type": "string", "enum": list(refs) + ["any"]}},
            "required": ["reason", key, "refuge"]}


def mediator_messages(a: Snapshot, b: Snapshot, sc: Scenario, info: str, vision: str = "none"):
    desc = "" if vision == "only" else situation(a, b, sc, info) + "\n\n"
    q = (desc + "Decide which robot yields so that the urgency-weighted total delay of both "
         "robots is as small as possible. Reply as JSON: "
         '{"reason": "<one sentence>", "yielder": "<robot id>", "refuge": "<refuge id, or any>"}')
    img = render_scene(a, b, sc) if vision != "none" else None
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": _content(q, sc, vision, img)}]


def _draws(a: Snapshot, b: Snapshot) -> dict:
    """Each robot's card: a hash bound to its id and this encounter's detection time.
    Computed identically by both sides from broadcast data — fair draw, no spoofing."""
    enc = f"{a.id}|{b.id}|{a.t:.3f}"
    return {s.id: int(hashlib.sha256(f"{s.id}|{enc}".encode()).hexdigest()[:16], 16)
            for s in (a, b)}


def _commit_draws(a: Snapshot, b: Snapshot, seed: int = 0) -> dict:
    """Commit-reveal draw (Blum coin flip): each robot holds a nonce it commits to before the peer's
    reveal, so the card material — both nonces — cannot be steered by anything a robot chooses to
    broadcast. In deployment the nonces are runtime-random secrets; in simulation they are derived
    deterministically from the per-encounter draw seed (`llm.draw_seed`, set by the study to the
    episode seed) and the robot's own id, so both sides recompute identical values. Deliberately
    NOT bound to the detection time: a robot that shifts the time it broadcasts changes nothing."""
    nonces = {s.id: int(hashlib.sha256(f"{seed}|nonce|{s.id}".encode()).hexdigest()[:16], 16)
              for s in (a, b)}
    commits = {s.id: hashlib.sha256(f"{s.id}|{nonces[s.id]}".encode()).hexdigest()[:16]
               for s in (a, b)}
    material = f"{nonces[a.id]}|{nonces[b.id]}"
    cards = {s.id: int(hashlib.sha256(f"{s.id}|{material}".encode()).hexdigest()[:16], 16)
             for s in (a, b)}
    return {"nonces": nonces, "commits": commits, "cards": cards}


def agent_messages(me: Snapshot, other: Snapshot, sc: Scenario, info: str, vision: str = "none",
                   tiebreak: str = "", draws: dict | None = None):
    a, b = sorted((me, other), key=lambda s: s.id)
    desc = "" if vision == "only" else situation(a, b, sc, info)
    q = (f"You are robot {me.id}. Robot {other.id} has broadcast its state to you.\n" + desc +
         f"\n\nShould you ({me.id}) yield, or proceed and let {other.id} yield? Aim to keep the urgency-weighted "
         "total delay of both robots small; if you both proceed or both yield, a fixed rulebook decides instead. ")
    if tiebreak in ("nonce", "commit") and draws:
        q = q.replace("a fixed rulebook decides instead. ",
                      "the draw decides instead. ")
        if tiebreak == "commit":
            q += ("Draw rule: each robot commits to a nonce, then reveals it; each card is a hash of "
                  "the robot's id and BOTH nonces, committed before either was seen, so neither can "
                  f"choose its value: yours is {draws[me.id]}, {other.id}'s is {draws[other.id]}. "
                  "If actions conflict (both yield or both proceed), the robot with the LARGER card proceeds. ")
        else:
            q += ("Draw rule: each robot holds a card — a random value bound to its id and this encounter "
                  f"that neither can choose: yours is {draws[me.id]}, {other.id}'s is {draws[other.id]}. "
                  "If actions conflict (both yield or both proceed), the robot with the LARGER card proceeds. ")
    q += (
         'Reply as JSON: {"reason": "<one sentence>", "action": "yield" or "proceed", "refuge": "<refuge id, or any>"}')
    if vision == "ego":
        img = render_ego(me, other, sc)
    elif vision != "none":
        img = render_scene(a, b, sc)
    else:
        img = None
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": _content(q, sc, vision, img)}]


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
    calls, choice, tiebroken, cr = [], {}, False, None
    if cfg["mode"] == "mediator":
        r = chat(cfg, mediator_messages(a, b, sc, cfg["info"], cfg["vision"]),
                 _ids_schema([a.id, b.id], refs, "yielder", (a.id, b.id)))
        calls.append({"role": "mediator", **r})
        ans = parse(r["text"]) or parse(r.get("reasoning") or "") or {}
        calls[-1]["answer"] = ans
        y = ans.get("yielder")
        if y in (a.id, b.id):
            choice = {"yielder": y, "refuge": ans.get("refuge")}
    elif cfg["mode"] == "agents":
        tb = cfg["tiebreak"]
        cr = _commit_draws(a, b, cfg.get("draw_seed", 0)) if tb in ("commit", "csilent") else None
        draws = cr["cards"] if cr else (_draws(a, b) if tb in ("nonce", "silent") else None)
        acts = {}
        for me, other in ((a, b), (b, a)):
            r = chat(cfg, agent_messages(me, other, sc, cfg["info"], cfg["vision"],
                                         cfg["tiebreak"], draws),
                     _ids_schema([me.id], refs, "action", ("yield", "proceed")))
            ans = parse(r["text"]) or parse(r.get("reasoning") or "") or {}
            calls.append({"role": me.id, **r, "answer": ans})
            acts[me.id] = ans.get("action")
        ylds = [i for i in (a.id, b.id) if acts[i] == "yield"]
        prc = [i for i in (a.id, b.id) if acts[i] == "proceed"]
        if len(ylds) == 1 and len(prc) == 1:
            ans = calls[0]["answer"] if ylds[0] == a.id else calls[1]["answer"]
            choice = {"yielder": ylds[0], "refuge": ans.get("refuge")}
        elif draws and len(ylds) + len(prc) == 2:
            win = max(draws, key=draws.get)  # larger card proceeds
            choice = {"yielder": a.id if win == b.id else b.id, "refuge": "any"}
            tiebroken = True
    else:
        raise ValueError(f"llm.mode must be mediator or agents, not {cfg['mode']!r}")

    think = max((c["latency"] for c in calls), default=0.0) if cfg["think_time"] == "measured" else float(cfg["think_time"] or 0.0)
    # agents-mode prompts would run on each robot in parallel, so charge the slower call, not the sum
    detail = {"llm_mode": cfg["mode"], "llm_model": cfg["model"], "think_time": think,
              "llm_latency": sum(c["latency"] for c in calls), "llm_cached": all(c["cached"] for c in calls),
              "llm_error": next((c["error"] for c in calls if c["error"]), None),
              "llm_answers": [{"role": c["role"], "think": c.get("reasoning", ""), **c["answer"]} for c in calls],
              "llm_tiebreak": tiebroken}
    if cr:
        detail["llm_draw"] = {"nonces": cr["nonces"], "commits": cr["commits"], "cards": cr["cards"]}
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
