# Review-cycle summary — paper 1 (RA-L letter)

Manuscript: `paper/main.tex` — "Who Backs Into the Bay? Benchmarking
Negotiation Policies for Head-On Robot Encounters in Single-Lane
Corridors". Target venue: IEEE RA-L.

Adversarial write/review cycle run 2026-10-23 (Devin paper-review-cycle
skill): GPT-family reviewer vs. Claude-family writer, manuscript on disk
as shared state. Two rounds of a permitted three; stopped because the
Round-2 verdict was MINOR with no unresolved major concerns.

## Verdicts

| Round | Verdict | Concerns | Outcome |
|---|---|---|---|
| 1 | MAJOR | 5 major, 17 minor, 8 questions | all majors resolved or resolved-by-narrowing |
| 2 | MINOR | 9 new issues (all minor) | all fixed; reviewer re-verified edits against the manuscript and repo |

Artifacts: `round-1-review.md`, `round-1-response.md`,
`round-2-review.md`, `round-2-response.md`.

## What changed (both rounds)

- Cost-bidding match reframed as implementation validation under the
  simulator's own cost model; untested manipulations (refuge-set
  omission, commit tie-break abuse) now stated.
- Reproducibility filled in: 180 s horizon, U[2,6] s reactive patience,
  3 s commit timeout, accel/turn limits, forward-Euler step, lidar
  model, latency/jitter/loss model, collision geometry, seed/draw
  accounting — plus a full-width design table decomposing every study's
  episode count (all factorizations reviewer-verified).
- Transfer claim narrowed to corridor studies whose random draws are
  shared; T-junction delays explicitly do not transfer (cause unknown).
- Deadlock premise attributed to cited literature (no ORCA/RVO/CBF run);
  fixed priority acknowledged as itself a social law not run with
  messages disabled.
- Internal consistency fixes: 122/338 code-version split reconciled per
  study, 6.8 vs 7.0 s shown to use different references, known-bays
  attribution corrected (+29.6 s is F and D, not "the rulebooks"),
  sharing-maps claim scoped to at-least-one-robot-knows conditions.
- Abstract ~350 -> ~205 words; agreement reported as 393/406 on
  negotiating runs; quasi-linear utility and per-encounter credit
  stated; "unseen layout" specified; Jain convention stated; Fig. 1(d)
  variant named.
- Figures/table mechanics: design table set \scriptsize with wrapping
  columns (was 69 pt overfull); compile clean at 8 pages.

## Pre-submission checklist (open items)

Each item has a `[XX]`/`[ANONYMIZED-URL]` placeholder and a `% TODO` in
`main.tex`.

- [ ] **Artifact URL/DOI** — footnote to contribution 1 and the
      conclusion both carry `\url{[ANONYMIZED-URL]}`. Insert the real
      link or drop the release claim (line 26, 204).
- [ ] **Prediction-vs-realized delay error** — compute mean absolute
      error from the released S1/S4 decision logs (line ~104).
- [ ] **Asymmetric 2% mismatches** — confirm from S2 decision logs that
      they are near-tied outcomes flipped by bid-model error (line ~111).
- [ ] **Paired 95% CIs** — convoy equal-urgency gap (0.7 s) and
      urgent-lone-robot column; T-junction mean delays (lines ~150, 153).
      Until filled, the affected sentences are hedged.
- [ ] **Commit IDs** — confirm `bf24bf4` is the parent of `2ba4c6d` and
      that hold branch `f5249a6` is merged/released (line ~66 TODO). The
      repo README says the hold branch is "not on main yet" — merge or
      adjust the "final agent code" claim.
- [ ] **T-junction re-trace** — trace final-code T-junction exit runs
      (2D and Gazebo) to explain ΔD = -16.8 s and the second yields
      (line ~172 TODO). Claims are already narrowed to exclude it.
- [ ] **Detection-distance inconsistency** — `gazebo_hold_runs.csv`
      records 1.1–1.2 m Gazebo detection distance for hold runs vs. the
      paper's 2.3–2.6 m (from non-hold runs). Check what that column
      measures (flagged by writer, left unchanged).
- [ ] **Start-time figures** — the ~35 s / ~12 s values ruling out
      non-conflicting draws were computed from the scenario file; verify
      against 2D logs.

### Deferred by design (need new experiments; claims already narrowed)

- Structural model-mismatch test (wrong speed limits / refuge distances /
  free-flow estimates in bids).
- A non-communicating deterministic social-law arm (fixed priority with
  messages disabled) and an ORCA/RVO/CBF baseline.
- Re-trace of final-code T-junction runs (see above).
- Refuge-set misreporting and commit tie-break exploitation tests.
