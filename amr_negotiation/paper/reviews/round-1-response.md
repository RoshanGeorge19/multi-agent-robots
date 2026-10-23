# Response to Reviewers — Round 1

We thank the reviewer for a careful report and for checking the arithmetic. Section numbers refer to the revised manuscript.

Author's note to orchestrator: the paper has `[XX]` placeholders, each with a `% TODO` comment. There is no repository URL. The T-junction gap between simulators is still unexplained. The paper was not compiled after editing; the new full-width design table (Table III) costs about a quarter page. New configuration numbers (time limit, patience range, timeouts, acceleration limits, latency model, study grids) come from the repository code and study scripts, not from new runs.

## Major concerns

**M1. The cost-bidding result is near-tautological. Accepted.**
- **The match is now framed as implementation validation (Sec. IV-A).** The text says the result validates the implementation more than it shows an advantage that would survive model error. It also says why the match is close to guaranteed: the bids use the simulator's speed limits, positions and refuge geometry, and the reference runs the same deterministic simulator.
- **The bid model is now described exactly (Sec. III-C).** It is a constant-speed model that ignores acceleration and turning. Predicted and realized delays therefore differ, but never by enough to change the decision.
- **(a) Prediction error.** The paper alone does not give this number. We added a placeholder ("mean absolute error [XX] s") with a TODO naming the decision logs it must come from.
- **(b) Structural model mismatch.** We did not run new experiments. Instead we narrowed the claims:
  - The abstract and conclusion now say "when bids use the simulator's own cost model."
  - The Discussion's sigma~0.25 statement now refers to a scalar log-normal error.
  - Sec. IV-A and the Limitations state that wrong speed limits, refuge distances and free-flow times are untested.
- **Clarke result.** It is now framed as following from the VCG theorem, so the 10,080 episodes confirm the implementation.
- **Untested manipulations.** The text now states that two manipulations are untested and that we assume robots follow the protocol apart from their cost reports:
  - omitting known bays from the BID, which changes the outcomes over which r_i(o) is defined;
  - abusing the lower-ID tie-break in the commit step.

**M2. Reproducibility is under-specified. Mostly accepted; one item unresolved.**
- **(a) Artifact.** We added a footnote to contribution 1 and a link in the conclusion, both reading `\url{[ANONYMIZED-URL]}` with a TODO. We have no URL or DOI to give, so this remains open.
- **(b) Time limit.** It is now stated as 180 s, used in every study (Sec. III-D).
- **(c) Missing parameters.** All are now in Sec. III:
  - reactive patience drawn from U[2,6] s;
  - commit timeout of 3 s;
  - acceleration limits of 0.5 m/s^2 linear and 3 rad/s^2 angular, and a turn rate of 1.82 rad/s;
  - forward-Euler integration at 0.05 s;
  - a 3.5 m lidar that sees peers as 0.25 m circles, without occlusion;
  - latency modeled as fixed delay plus uniform U[0,j] jitter, with independent loss per receiver (defaults 0.05 s and 0.02 s);
  - collision defined as overlap of the 0.281x0.306 m body rectangles, with the 0.25 m swept radius used only for planning clearances and the lidar, plus the blocked-bay obstacle rule.
- **Presentation.** We put the parameters in the text rather than a separate table to save space. Table III collects the study-level configuration.

**M3. The experimental matrix cannot be reconstructed. Accepted.**
- **New Table III** lists, for every study: grid factors, seeds per cell, policies and N.
- **2,940 single-bay episodes** = 7 rows x 420. The rows are reactive, fixed priority, both rulebooks, cost bidding, and two best-forced-yielder rows (total and urgency-weighted delay). Group bidding, reservation and Clarke are not part of this study.
- **5,040 asymmetric episodes** = 24 cells x 30 seeds x 7 rows.
- **10,080 Clarke episodes** = 6 configurations x 28 report profiles x 60 draws. The reviewer's reconstruction was correct, and this is now stated in Sec. IV-B.
- **The comms studies:**
  - 1,440 = 4 policies x 18 cells x 20 seeds.
  - 5,760 = 2 policies x 8 safeguard arms x 18 cells x 20 seeds.
  - 3,600 = 4 policies x 30 cells x 30 seeds.
  - 4,320 = 4 policies x 54 cells x 20 seeds.
- **Wrong description fixed.** The text had described the 4,320-episode grid as "1.5 m detection at 0.5 m/s." It actually covers 6, 3 and 1.5 m detection at 0.26 and 0.5 m/s, and Sec. IV-C now says so.
- **Censoring of reactive delays.** Sec. IV-A now states that the 97 s mean excludes the 26 deadlocked episodes and is therefore a lower bound. We derived an upper bound from numbers in the paper: each robot's delay is below 180 s, so counting deadlocks at the limit gives at most 113 s (4.2x the reference). The abstract now says "at least 3.6x."

**M4. The T-junction gap is unexplained. Accepted by narrowing the claim; not resolved.**
- **No re-trace was possible.** We could not re-trace the final-code runs without new experiments, and the response says so plainly.
- **Narrowed claims:**
  - Contribution 4 and the abstract now say that decisions and excess delays transfer for the corridor studies and that T-junction delays do not.
  - Sec. IV-H says the cause is unknown, attributes the stall explanation to a trace on pre-release code, and says we make no transfer claim for the T-junction.
  - The Limitations list the unexplained gap.
- **A TODO in the source** records the re-trace that is needed.

**M5. The baseline is weak and the deadlock premise is not shown. Partly accepted, partly clarified.**
- **Baseline.** Fixed priority is already the kind of deterministic social law the reviewer proposes: if robot IDs were observable it would need no messages to decide. What we did not do is run it with messages disabled. Sec. IV-A and the Discussion now say that the 93.8%->100% gap measures a shared rule together with the messages that implement it, and the two are not separated.
- **Deadlock premise.** No ORCA, RVO or CBF controller exists in the codebase. The Introduction and Limitations now state that the deadlock premise is taken from the cited literature and is not reproduced in our benchmark.

## Minor comments

- **Abstract.**
  - Cut from about 350 to about 205 words.
  - "Every negotiating policy succeeds" is now scoped to the single-bay study.
  - The sample size is now stated as 420 episodes per policy.
- **Line 87, phantom antecedent. Accepted.** The naive transfer (the proceeder pays the yielder's reported bid) is now defined in Sec. III-C and referred to from Sec. IV-B.
- **Development-history language. Accepted.**
  - A new "Code versions" paragraph explains that all numbers come from the final agent code. The last commit added only Gazebo support and explore mode, so 2D studies other than explore mode ran on its parent.
  - Failures seen before a fix are reported only as the reason for that fix.
  - "Merged main branch," "older code" and similar phrases are gone.
- **Agreement figure. Accepted.** It is now reported as 393 of 406 negotiating runs (96.8%). Table II notes that forced-yielder runs agree by construction.
- **Quasi-linear utility and credit. Accepted.**
  - The quasi-linearity assumption is now stated.
  - Credit is settled per encounter and is not carried forward.
  - The repeated-encounter study uses measured costs with no payments.
  - The text notes that carrying credit across encounters would break the single-encounter truthfulness analysis.
- **Confidence intervals. Accepted with placeholders.** The convoy and T-junction intervals cannot be computed from the paper, so they are `[+-XX]` with TODOs. That includes the paired interval for the 0.7 s gap between 34.4 s and 33.7 s.
- **98.9-99.2% range. Clarified.** The range is for the default protocol (all safeguards on) across the four policies. Table I now marks the default rows.
- **Passing is infeasible. Clarified.** Side by side, two 0.306 m-wide bodies leave 0.04 m of the 0.65 m corridor. That is less than the 0.05 m wall clearance each robot keeps, and the controller follows the centerline with no passing maneuver.
- **Head-on encounter for every draw. Clarified.** A needs about 35 s to clear the corridor, and B enters it within about 12 s.
- **Reservation draw set. Accepted.** The text now says the reservation study uses its own set of draws, separate from the main 60-draw grid.
- **Reservation rule. Accepted.** The robot that entered the corridor first holds it. When neither robot is inside, both may enter.
- **"Unseen layout." Clarified.** Training used the two-bay corridor; evaluation used the single-bay corridor with a randomly placed bay.
- **Jain's index on delays. Clarified.** It is applied to cumulative delays clamped at zero, so it measures how evenly the cost is shared.
- **Mutual yields. Clarified.** The text now states that the protocol does not guarantee mutual yields terminate and that we have no bound. Deadlocks in Table I are episodes that did not resolve within 180 s. The Limitations now say there is no formal safety or liveness guarantee.
- **Fig. 1(d). Accepted.** The caption now identifies the turn-in variant and describes the exit variant.
- **Scope claim and citations. Accepted.**
  - Added "to our knowledge."
  - `fanti2002event` and `geozone2023` are now cited under zone control in Related Work.
  - Unused .bib entries are not printed by BibTeX, and I was limited to editing `main.tex`, so `refs.bib` is unchanged.

## Questions

1. **Time limit:** 180 s in every study. The reactive mean is between 97 s and at most 113 s (3.6-4.2x the reference).
2. **Episode counts:** see M3 and Table III.
3. **Footprint and clearance:** see the "passing is infeasible" item above.
4. **Refuge-set misreporting and tie-break abuse:** both are possible and both are untested; this is now stated in the text.
5. **Reciprocal avoidance:** no ORCA, RVO or CBF controller was run. The premise now cites the literature explicitly.
6. **Hosting:** placeholder only, still unresolved.
7. **Agreement:** 437/450 included the forced-yielder runs. On negotiating policies alone it is 393/406.
8. **0.26 m/s:** the milder comms grid already includes 0.26 m/s; the extreme grid was 2D at 0.5 m/s only. The Gazebo extreme-comms runs at 0.26 m/s had 24/24 successes. Sec. IV-C now states this.

## Edits to `paper/main.tex`

1. **Abstract:** rewritten at about 205 words, with the scope and model caveats, 393/406, and the T-junction statement.
2. **Introduction:**
   - added "to our knowledge";
   - added that the deadlock premise is taken from the literature and not reproduced;
   - contribution 1 has an artifact footnote with a URL placeholder and TODO;
   - contribution 2 points to Table III;
   - contribution 4 is scoped to exclude T-junction delays.
3. **Related Work:** zone-control sentence citing `fanti2002event` and `geozone2023`.
4. **Sec. III-A:**
   - body dimensions and the reason passing is infeasible;
   - start positions and why every draw produces an encounter;
   - latency, jitter and loss model with defaults;
   - Fig. 1 caption now names the variant.
5. **Sec. III-B:** lidar range, integration scheme, acceleration limits, 2D lidar model, and the 3 s commit timeout.
6. **Sec. III-C (labeled `sec:pol`):**
   - reactive patience distribution;
   - reservation rule details;
   - the cost-bidding model described as constant-speed;
   - quasi-linear utility and per-encounter credit;
   - the naive transfer defined.
7. **Sec. III-D:**
   - 180 s limit;
   - collision definition and the role of the swept radius;
   - how Jain's index is applied;
   - new "Code versions" paragraph;
   - censoring stated as a lower bound;
   - new Table III (`tab:design`), full width.
8. **Sec. IV-A (`sec:two`):**
   - episode-count breakdown;
   - censoring bound (at most 113 s, 4.2x);
   - the point that fixed priority is a social law;
   - cost-bidding match framed as near-guaranteed, with the `[XX]` prediction-error placeholder and the untested structural errors;
   - reservation uses separate draws.
9. **Sec. IV-B (`sec:inc`):**
   - naive transfer replaces the phantom "earlier rule";
   - Clarke breakdown (6x28x60), the VCG framing, and the untested manipulations;
   - fairness study uses measured costs with no payments;
   - credit-banking caveat.
10. **Sec. IV-C:**
    - corrected 4,320-grid description;
    - "pre-release version" wording;
    - default protocol made explicit;
    - 0.26 m/s scope;
    - no termination bound;
    - Table I caption marks the default rows.
11. **Sec. IV-D to IV-G:**
    - labels `sec:three`, `sec:maps`, `sec:learned`;
    - convoy pooling stated, with `[+-XX]` intervals and a TODO;
    - T-junction `[+-XX]` and a TODO;
    - learned layouts defined.
12. **Sec. IV-H (`sec:gz`):**
    - code-version wording;
    - 393/406 agreement;
    - T-junction marked as not transferring, cause unknown, re-trace TODO;
    - Table II footnote on forced yielders.
13. **Discussion and Limitations:** the first and second conclusions are scoped, and the limitations now cover:
    - the unexplained T-junction gap;
    - structural model errors, refuge-set and tie-break manipulation;
    - the reactive policy being the only non-communicating baseline;
    - no reciprocal-avoidance controller;
    - no liveness guarantee.
14. **Conclusion:** claims qualified by "under the simulator's own cost model," reservation and fixed priority stated as 6-19 s of excess delay "in our layout," and the URL placeholder.

## Not resolved

- **Prediction-vs-realized delay error (M1a):** needs analysis of the per-episode decision logs (`[XX]` in Sec. IV-A).
- **Structural model-mismatch experiment (M1b):** needs new runs; for now the claims are narrowed.
- **Artifact URL or DOI (M2a):** needs the real link.
- **Re-trace of the final-code T-junction runs (M4):** needs new tracing; for now the transfer claim is narrowed.
- **ORCA/RVO/CBF condition and a fixed-priority run with messages disabled (M5):** need new runs; for now the text states these limits.
- **Confidence intervals:** the convoy and T-junction intervals need computing from the released results.
- **"Different known bays" row of Table III:** factors, policies and N are `[XX]`. The configuration could not be found in the repository.
- **Code-version claim:** the "Code versions" paragraph relies on the paper's own statement that the last commit "adds only Gazebo support and explore mode." The authors should confirm it.
- **Start-time parameters:** the ~35 s and ~12 s figures that rule out non-conflicting draws are calculated from the scenario file (start positions, 0.26 m/s). They should be checked against the 2D logs.
