"""The reward weights an LLM may change, and the bounds it must stay within.

Shared by the search orchestrator (which builds the schema and prompt from it)
and train_rl.py (which applies the overrides to the env config). Keeping both on
one table means the LLM cannot propose a field the trainer silently ignores.

Pure Python -- imported outside Isaac by the orchestrator.
"""

from __future__ import annotations

# name -> (lower, upper, what it does). Signs are fixed by the bounds: penalties
# stay <= 0 and bonuses >= 0, so a proposal cannot invert a term's meaning.
REWARD_SPACE: dict[str, tuple[float, float, str]] = {
    "rew_gets_closer_to_goal": (0.0, 100.0, "per metre of goal distance closed this step (dense progress)"),
    "rew_reach_goal": (0.0, 500.0, "one-off bonus on reaching a goal; the goal then respawns"),
    "rew_step": (-0.5, 0.0, "constant per-step cost"),
    "rew_wall_proximity_penalty": (-2.0, 0.0, "x proximity ramp (0 at trigger distance, 1 at contact) to nearest wall"),
    "wall_proximity_distance": (0.05, 0.6, "metres at which the wall-proximity ramp starts"),
    "rew_robot_proximity_penalty": (-5.0, 0.0, "x proximity ramp to the other robot, applied to both agents"),
    "robot_proximity_distance": (0.1, 1.0, "metres at which the robot-proximity ramp starts"),
    "rew_wall_collision": (-200.0, 0.0, "on contact; contact also ends the episode for both robots"),
    "rew_xgo_alive": (0.0, 1.0, "XGO only: per step while upright (also scales an uprightness bonus)"),
    "rew_xgo_fell": (-200.0, 0.0, "XGO only: on falling; falling ends the episode for both robots"),
    "rew_xgo_action_rate": (-0.5, 0.0, "XGO only: x norm of change in its velocity command"),
}


def clamp_overrides(proposal: dict) -> tuple[dict[str, float], list[str]]:
    """Keep known fields, clamp to bounds. Returns (overrides, notes on anything changed)."""
    overrides, notes = {}, []
    for name, value in proposal.items():
        if name not in REWARD_SPACE:
            notes.append(f"ignored unknown field {name!r}")
            continue
        lo, hi, _ = REWARD_SPACE[name]
        clamped = min(max(float(value), lo), hi)
        if clamped != value:
            notes.append(f"{name}={value} clamped to {clamped}")
        overrides[name] = clamped
    return overrides, notes


def apply_overrides(cfg, overrides: dict[str, float]) -> None:
    """Set the overrides on an env config, refusing anything outside the space."""
    clean, notes = clamp_overrides(overrides)
    if notes:
        raise ValueError("reward overrides out of space: " + "; ".join(notes))
    for name, value in clean.items():
        if not hasattr(cfg, name):
            raise AttributeError(f"env config has no field {name!r}")
        setattr(cfg, name, value)


def proposal_schema() -> dict:
    """Strict JSON schema for one proposal: reasoning plus every weight."""
    return {
        "type": "object",
        "properties": {
            "diagnosis": {"type": "string"},
            "hypothesis": {"type": "string"},
            "weights": {
                "type": "object",
                "properties": {name: {"type": "number"} for name in REWARD_SPACE},
                "required": list(REWARD_SPACE),
                "additionalProperties": False,
            },
        },
        "required": ["diagnosis", "hypothesis", "weights"],
        "additionalProperties": False,
    }


def fitness(summary: dict) -> float:
    """The fixed objective the reward search is judged on. The LLM cannot change it.

    Mean over both robots of goals per env-minute, minus failures (collisions and
    falls) per env-minute. Equal weights: a reward that buys the rover goals by
    starving the XGO should not score well. `summary` is MazeMetrics.summary().
    """
    agents = summary["agents"].values()
    return sum(a["goals_per_env_min"] - a["failures_per_env_min"] for a in agents) / len(agents)
