# Review-cycle summary — paper 2 (T-ASE draft)

Manuscript: `paper2/main.tex` — "Deliberation Costs: LLM and VLM
Negotiators for Head-On Robot Encounters in Single-Lane Corridors".
Target venue: IEEE T-ASE. Companion to `paper/main.tex` (cited as
`paper1`).

Adversarial write/review cycle run 2026-10-23 (Devin paper-review-cycle
skill): GPT-family reviewer vs. Claude-family writer, manuscript on disk
as shared state. Two rounds of a permitted three; stopped because the
Round-2 verdict was MINOR with no unresolved major concerns.

## Verdicts

| Round | Verdict | Concerns | Outcome |
|---|---|---|---|
| 1 | MAJOR | 8 major, 18 minor, 8 questions | all resolved; reviewer verified numbers against `rows.jsonl` |
| 2 | MINOR | 1 major (stale figures — already fixed by orchestrator regeneration), 13 minor | all fixed; reviewer re-derived new Sec. V-F numbers from raw data — exact |

Artifacts: `round-1-review.md`, `round-1-response.md`,
`round-2-review.md`, `round-2-response.md`.

## What changed (both rounds)

- **Tiebreak story rewritten against the data** (largest change): the
  original "visible draw eliminates disagreement / hidden draw preserves
  deliberation" claims were wrong — the hidden arm's prompts are
  byte-identical to the rulebook arm, so the cache replays the same
  answers, and the visible draw does not eliminate disagreement. The
  paper now reports that a fair coin is a worse fallback than the
  informed rulebook (40–51% vs 66–71% right on conflicted encounters).
- Deployed-cost claim rebuilt: the +103.1 s figure is now a labeled
  concurrent-regime upper bound (n=50); the claim rests on a ~3.4 s/s
  latency slope matching 2 x mean urgency 5/3, with break-even latencies
  ~0.3–0.5 s vs. cost bidding and ~1.1–1.4 s vs. the rulebook (n=200
  populations).
- Deadlock defined: 180 s horizon; fallback executes after charged
  latency, too late on slow calls — resolves the "all runs succeed"
  contradiction.
- Serial vs. concurrent serving regimes defined; every measured row in
  Table II carries regime, mean charged latency, and n. Queueing
  documented: same model 22.0 s concurrent vs. 0.7 s serial.
- `make_figures.py` latency block rewritten — pairs same-thinking arms
  (on0<->onm, off0<->offm-s), marks the missing qwen3.8 thinking-on
  measured cell "not run", labels n and regime; CI denominator fixed to
  sqrt(n); stale MuseGlm tick removed. All six figures regenerated.
- n=50/n=200 pairing disclosed (50-encounter arms are a strict seed
  prefix; baselines reported per population).
- Cache claim scoped to within-run identity; cross-run spread reported.
- Completeness: verbatim prompt appendix (matches `llm.py`), JSON
  schema, request parameters, timeout/freeze rules, new Tables II–III
  (30 arms + tiebreak arms, n, excess +- CI, right-yielder, fallback).
- Every prose number rechecked against `rows.jsonl`; wrong values
  corrected (92–93%, all-four text+image, all-four ego, per-model
  agreed-encounter rates); corrupted runs excluded and listed; Muse-
  Glimmer row removed (failed to load); nine models, not ten.
- Image-vs-text ordering marked unproven: per-arm CIs overlap for all
  four models; awaiting paired differences.

## Pre-submission checklist (open items)

Each item has an `[XX]`/`% TODO` in `main.tex` unless noted.

- [ ] **Paired-difference CIs** — script over `rows.jsonl` for the
      on/off plans comparison (Sec. V-B) and image-vs-text (Sec. V-D,
      incl. Wilcoxon p). If an interval includes zero, narrow or delete
      the corresponding claim — Sec. V-D is already worded as unproven.
- [ ] **Wrong-yielder agreement excess** — per-model mean excess from
      `*-ego` rows (Sec. V-E `[XX]`).
- [ ] **Card-win split** — empirical A/B split of the SHA-256 draw over
      the 200 encounters (Sec. V-F `[XX]`; compute from `llm._draws`).
- [ ] **Serial thinking-on measured runs** — `qwen3-30b-onm-s` never
      ran; `qwen3.8-27b-onm-s` was stopped at 10/50 (9.8 h). Limitation
      stated; fill `[XX]` latency/excess if runs ever complete.
- [ ] **Screen trace status** — screen rows predate trace logging;
      confirm whether gemma4 / N-Super-49B / N-VL-12B emitted reasoning
      before calling them non-reasoning (TODO in Sec. V-A).
- [ ] **Release tag/DOI** — repo URL is live; pin a tag/commit or DOI
      before submission (footnote in Sec. III-E).
- [ ] **Confirm serving config** — "one sequence at a time" is from
      `docs/llm_experiments.md`, not a server log; verify against the
      actual vLLM deployment flags.

### Deferred by design (need new experiments; claims already narrowed)

- Serial thinking-on latency for local models (see above).
- Commit-reveal draw protocol (Blum cite reframed as what was *not*
  implemented); current draw is fair only between non-adversarial
  robots.
- Agents-mode measured rows exist in released data and are worse
  (172.9 s @ 51.9 s noted in text) but are not in Table II.
