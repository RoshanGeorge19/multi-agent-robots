"""Pluggable LLM backends that return schema-valid JSON.

Both experiments ask the model for a structured decision -- a set of reward
weights, or a per-robot directive -- so every backend exposes one call:

    backend.complete_json(system, user, schema) -> dict

Backends are named by a spec string, so experiment scripts take a single flag:

    ollama:qwen3.6:35b          local Ollama (default; stdlib only, no extra deps)
    claude:claude-opus-5-5      Anthropic API (needs `pip install anthropic` and a key
                                or an `ant auth login` profile)

Schemas must be strict-compatible: every object lists all of its properties in
`required` and sets `additionalProperties: false`, and numeric bounds are left
out (they are enforced by the caller, which clamps and reports back). That keeps
one schema valid for both Ollama's `format` and Claude's structured outputs.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from threading import Lock


class LLMError(RuntimeError):
    """The backend did not produce a usable JSON answer."""


@dataclass
class LLMReply:
    data: dict
    latency_s: float
    model: str
    raw: str


class OllamaBackend:
    """Local model served by Ollama's /api/chat, with JSON-schema constrained output.

    num_batch defaults to 256, not Ollama's 512. On this machine (GB10, Ollama
    0.33.2, qwen3.6:35b) the default intermittently fails prompts of ~1.3-1.8k
    tokens with "CUDA error: an illegal memory access", after which the runner
    keeps failing every request until it is reloaded. Retries replay the same
    prompt and fail identically. At 256 the same prompts, repeated and with shared
    prefixes, all succeed. A different num_batch also forces a fresh runner.
    """

    def __init__(self, model: str, host: str | None = None, think: bool = False,
                 temperature: float = 0.3, num_batch: int = 256, timeout_s: float = 900.0):
        self.model = model
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        if not self.host.startswith("http"):
            self.host = "http://" + self.host
        self.think = think
        self.temperature = temperature
        self.num_batch = num_batch
        self.timeout_s = timeout_s

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    def complete_json(self, system: str, user: str, schema: dict) -> LLMReply:
        body = {
            "model": self.model,
            "stream": False,
            "think": self.think,
            "format": schema,
            "options": {"temperature": self.temperature, "num_batch": self.num_batch},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        start = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            # Ollama puts the actual cause in the body; the status line says nothing
            raise LLMError(f"{self.name} HTTP {exc.code}: {exc.read().decode(errors='replace')[:300]}") from exc
        raw = payload["message"]["content"]
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            thinking = len(payload["message"].get("thinking") or "")
            raise LLMError(
                f"{self.name} returned non-JSON (done_reason={payload.get('done_reason')}, "
                f"{payload.get('eval_count')} tokens generated, {thinking} chars of thinking): "
                f"{raw[:200]!r}"
            ) from exc
        return LLMReply(data, time.monotonic() - start, self.model, raw)


class ClaudeBackend:
    """Anthropic API with structured outputs.

    Server-side refusal fallbacks are on (`fallbacks: "default"`), so a declined
    request is re-run on Anthropic's recommended substitute rather than failing
    the trial; `reply.model` records which model actually answered.
    """

    def __init__(self, model: str = "claude-opus-5-5", effort: str = "high",
                 max_tokens: int = 16000):
        try:
            import anthropic
        except ImportError as exc:
            raise LLMError(
                "The claude backend needs the anthropic SDK in this Python: "
                "`~/IsaacLab/_isaac_sim/python.sh -m pip install anthropic`"
            ) from exc
        self.client = anthropic.Anthropic()
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens

    @property
    def name(self) -> str:
        return f"claude:{self.model}"

    def complete_json(self, system: str, user: str, schema: dict) -> LLMReply:
        start = time.monotonic()
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": schema},
            },
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        if response.stop_reason == "refusal":
            raise LLMError(f"{self.name} refused: {response.stop_details}")
        if response.stop_reason == "max_tokens":
            raise LLMError(f"{self.name} hit max_tokens before finishing the JSON")
        raw = next(block.text for block in response.content if block.type == "text")
        return LLMReply(json.loads(raw), time.monotonic() - start, response.model, raw)


def make_backend(spec: str, **kwargs):
    """Build a backend from 'ollama:<model>' or 'claude:<model>'."""
    kind, _, model = spec.partition(":")
    if kind == "ollama":
        return OllamaBackend(model or "qwen3.6:35b", **kwargs)
    if kind == "claude":
        return ClaudeBackend(model or "claude-opus-5-5", **kwargs)
    raise ValueError(f"unknown backend {spec!r}; expected ollama:<model> or claude:<model>")


class LoggedBackend:
    """Wraps a backend: retries, and appends every exchange to a JSONL transcript.

    The transcript is the experiment's primary record. Results that cannot be
    traced back to the exact prompt and reply that produced them are anecdotes.
    """

    def __init__(self, backend, log_path: str | Path, retries: int = 2):
        self.backend = backend
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.retries = retries
        self._lock = Lock()
        self.calls = 0
        self.failures = 0
        self.total_latency_s = 0.0

    @property
    def name(self) -> str:
        return self.backend.name

    def complete_json(self, system: str, user: str, schema: dict, tag: str = "") -> dict | None:
        """The parsed reply, or None if every attempt failed (the caller falls back)."""
        for attempt in range(self.retries + 1):
            record = {"time": time.time(), "backend": self.name, "tag": tag,
                      "attempt": attempt, "system": system, "user": user}
            try:
                reply = self.backend.complete_json(system, user, schema)
            except Exception as exc:  # noqa: BLE001 - log every failure mode, then retry
                record["error"] = f"{type(exc).__name__}: {exc}"
                self._append(record, ok=False)
                continue
            record.update(reply=reply.data, model=reply.model, latency_s=reply.latency_s)
            self._append(record, ok=True, latency=reply.latency_s)
            return reply.data
        return None

    def _append(self, record: dict, ok: bool, latency: float = 0.0) -> None:
        with self._lock:
            self.calls += 1
            self.failures += not ok
            self.total_latency_s += latency
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")

    def stats(self) -> dict:
        ok = self.calls - self.failures
        return {
            "backend": self.name,
            "calls": self.calls,
            "failures": self.failures,
            "mean_latency_s": self.total_latency_s / ok if ok else None,
        }


def add_backend_args(parser) -> None:
    parser.add_argument("--llm", default="ollama:qwen3.6:35b",
                        help="Backend spec: ollama:<model> or claude:<model>.")
    parser.add_argument("--llm_think", action="store_true",
                        help="Ollama only: let reasoning models think before answering.")
    parser.add_argument("--llm_effort", default="high",
                        help="Claude only: output effort (low/medium/high/xhigh/max).")


def backend_from_args(args, log_path) -> LoggedBackend:
    kwargs = {}
    if args.llm.startswith("ollama"):
        kwargs["think"] = args.llm_think
    elif args.llm.startswith("claude"):
        kwargs["effort"] = args.llm_effort
    return LoggedBackend(make_backend(args.llm, **kwargs), log_path)
