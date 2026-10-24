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
| 3 | MINOR | 10 issues (2 blocking: protocol timers undocumented; T-junction discrepancy not split by variant) | all resolved or explicitly bounded; cycle stops at MINOR |

Artifacts: `round-1-review.md`, `round-1-response.md`,
`round-2-review.md`, `round-2-response.md`,
`round-3-review.md`, `round-3-response.md`.

## Update 2026-10-24 (round 3 — post-experiment revision review)

After the authors filled the checklist numbers and re-ran experiments, a
third review verified the filled values and found consistency-level issues.
All addressed in `round-3-response.md` and `main.tex`:

- Protocol timing parameters added (BID resend 0.3 s, STATE freshness
  1.0 s, park timeout U[6,12] s, neg/proceed timeouts 3/60 s, 10 s
  backoff) — reviewer M1.
- T-junction discrepancy split by variant: exit −260.0 s / turn-in
  −345.4 s; exit mechanism traced to a release-timing race; turn-in
  share explicitly stated as unexplained — reviewer M2/M3.
- STATE freshness under loss clarified; fixed-priority/rulebook vs.
  cost-bid yielder roles in exit runs explained; `gz_min_clearance`
  defined against rectangle collision checks; bay-sensing count
  corrected (A 6/6, B 5/6); hold/share-on-detect batch marked as
  outside the 460 Gazebo runs.
- Writer caught a source-comment bug: a `% VERIFIED` comment had
  commented out the rest of a line, hiding four sentences of the
  hold-mode paragraph from the rendered PDF. Now visible.
- Page limit restored: the new content pushed the letter to 9 pages;
  restored to 8 pages via float-spacing/caption tightening,
  microtype, `\scriptsize` bibliography, `\arraystretch` 0.9, ~6 lines
  of prose compression, and `\enlargethispage` on the refs page.
  Compile clean: 8 pages, 0 overfull, 0 undefined refs.

Open pre-submission items (unchanged): real artifact URL/DOI; `% TODO` /
`% VERIFIED` / DRAFT annotation cleanup; release of convoy/T-junction
per-episode rows and bid-capture logs; raw traces for the turn-in
mechanism and the hold-mode detection-distance discrepancy.

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

## Update 2026-10-23 (second pass)

All computable checklist items resolved; manuscript `% TODO` markers flipped to `% VERIFIED` with method notes.

- Prediction-vs-realized delay error: per-robot MAE 1.9 s (S1+S4, 780 eps rerun with bid capture; 780/780 rows match released CSVs). Filled.
- Asymmetric 2% mismatches: confirmed near-ties — 16/720 flips, median bid gap 0.6 s vs 12.4 s for matches. Text updated.
- Convoy paired CIs: equal-urgency gap +0.7±1.4 s; urgent column per-mean CIs ±3.1/±4.2/±6.7/±6.3 and paired gb−fp +14.4±8.0, gb−oracle +19.0±6.9, cb−gb +12.4±5.8. Filled; provisional-ordering hedge resolved.
- T-junction mean-delay CIs ±4.7/±5.0/±4.0; cb−rulebook paired −4.3±2.8. Filled.
- Commit IDs: parent of 2ba4c6d is e400e99 (explore-mode commit), not bf24bf4; f5249a6 merged on main. Sentence corrected.
- T-junction re-trace: done — both diffs trace to one timing race (whether the stem robot exits before/after A clears the bay); s3's 196.8 s is a dual-proceed wait released by the 60 s proceed timeout. Paragraph rewritten.
- Detection distance: gz_detect_dist = first lidar-cluster contact. Hold runs are 1.10–1.18 m, not 2.3–2.6 m (that's the share-on-detect runs). Sentence corrected.
- Start-time figures (35 s/12 s): verified — A clears x=8 in 34.9 s, B enters by 12.1 s; all 6000 released negotiating episodes recorded a yielder.

Still open: real artifact URL/DOI (lines 26, 205). Deferred-by-design items unchanged.
