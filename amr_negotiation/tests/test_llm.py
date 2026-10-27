import json
import os
import urllib.error
from pathlib import Path

import pytest

from amr_negotiation import llm
from amr_negotiation.geometry import load_scenario
from amr_negotiation.sim2d import run_episode

ROOT = Path(__file__).resolve().parents[1]
SC = ROOT / "configs" / "scenarios" / "corridor_single_bay.yaml"


@pytest.fixture(autouse=True)
def clear_cache():
    llm._MEM.clear()
    yield
    llm._MEM.clear()


def fake(answer_fn):
    calls = []

    def post(url, payload, timeout):
        calls.append(payload)
        content = answer_fn(payload["messages"][-1]["content"])
        return {"choices": [{"message": {"content": content}}]}

    post.calls = calls
    return post


def run(policy_llm, **kw):
    return run_episode(load_scenario(SC), {"name": "llm", "llm": {"think_time": 0.0, **policy_llm}}, **kw)


def test_mediator_choice_is_used_and_cached(monkeypatch):
    post = fake(lambda q: json.dumps({"reason": "x", "yielder": "B", "refuge": "any"}))
    monkeypatch.setattr(llm, "post_json", post)
    r = run({"mode": "mediator"})
    assert r["success"] and not r["collision"]
    assert r["yielder"] == "B" and r["rule"] == "llm_mediator"
    assert len(post.calls) == 1  # the second robot's identical prompt is a cache hit
    assert post.calls[0]["temperature"] == 0.0 and "response_format" in post.calls[0]


def test_agents_one_yields(monkeypatch):
    monkeypatch.setattr(llm, "post_json", fake(lambda q: json.dumps(
        {"reason": "x", "action": "yield" if q.startswith("You are robot A") else "proceed", "refuge": "any"})))
    r = run({"mode": "agents"})
    assert r["success"] and r["yielder"] == "A" and r["rule"] == "llm_agents"


@pytest.mark.parametrize("answer,why", [
    (lambda q: json.dumps({"reason": "x", "action": "yield", "refuge": "any"}), "disagree"),
    (lambda q: "I think robot A should probably yield", "parse"),
])
def test_agents_fallback_to_rulebook(monkeypatch, answer, why):
    monkeypatch.setattr(llm, "post_json", fake(answer))
    r = run({"mode": "agents"})
    assert r["success"] and r["rule"].startswith(f"llm_fallback_{why}:")


def test_server_down_falls_back(monkeypatch):
    def down(url, payload, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(llm, "post_json", down)
    r = run({"mode": "mediator"})
    assert r["success"] and r["rule"].startswith("llm_fallback_error:")
    assert "URLError" in r["decisions"][0]["llm_error"]


def test_think_time_is_charged(monkeypatch):
    monkeypatch.setattr(llm, "post_json", fake(lambda q: json.dumps({"reason": "x", "yielder": "A", "refuge": "any"})))
    fast = run({"mode": "mediator", "think_time": 0.0})
    llm._MEM.clear()
    slow = run({"mode": "mediator", "think_time": 5.0})
    assert fast["yielder"] == slow["yielder"] == "A"
    assert slow["total_delay"] > fast["total_delay"] + 4.0


def test_file_cache_replays(monkeypatch, tmp_path):
    cache = str(tmp_path / "cache.jsonl")
    post = fake(lambda q: json.dumps({"reason": "x", "yielder": "A", "refuge": "any"}))
    monkeypatch.setattr(llm, "post_json", post)
    r1 = run({"mode": "mediator", "cache": cache, "think_time": "measured"})
    llm._MEM.clear()
    monkeypatch.setattr(llm, "post_json", fake(lambda q: pytest.fail("cache miss")))
    r2 = run({"mode": "mediator", "cache": cache, "think_time": "measured"})
    assert r1["total_delay"] == r2["total_delay"] and r2["decisions"][0]["llm_cached"]


@pytest.mark.skipif(not os.environ.get("AMRNEG_LLM_URL"), reason="set AMRNEG_LLM_URL to test a live server")
def test_live_server():
    r = run({"mode": "mediator"})
    assert r["success"] and not r["collision"]
    assert r["decisions"][0]["llm_error"] is None
