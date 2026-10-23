# Response to Reviewers — Round 2

We thank the reviewer. Tables are named by label, because the report's numbering does not match the compiled order (see the last minor comment).

Author's note to orchestrator: the true decompositions for N1, N2, N3, N6 and N8 were recovered from `studies/`; none of the new numbers was guessed. Three things remain open: the artifact URL, the `[XX]`/`[+-XX]` placeholders, and confirming the commit IDs (git log could not be run). Two errors the reviewer didn't flag were also fixed. The paper was not compiled after editing.

## New issues

**N1. Misreport N = 1,080 — Accepted.** The reviewer's reading is correct. `studies/run_studies.py` (study `S6_misreport`) runs five `cost_bid` arms (k in {1, 1.5, 2, 4, 10}) and one reference per bay and draw: (5+1) x 3 x 60 = 1,080. The `tab:design` row now says "reference run once per bay and draw."

**N2. The 122/338 split — Accepted.** The parenthetical named the groups but not the fractions. From `studies/report/gazebo_main_runs.csv` (`main@bf24bf4`), the 122 cases are:
- 40 of the 70 single-bay negotiating runs (F, D, P, C x 10 seeds);
- all 10 reactive runs;
- 18 of the 36 convoy runs (F, D, C with equal urgency);
- all 36 T-junction runs;
- all 18 50%-loss runs.

That sums to 122. The rest of each group (Clarke, learned and reservation single-bay runs, all forced yielders, the group-bid and urgent convoy runs) is among the 338. Sec. IV-H now gives this split.

**N3. 6.8 s vs. 7.0 s — Clarified.** The two numbers are measured against different references:
- 6.8 s is Gazebo share-on-detect minus the paired 2D run (28.9 - 22.1 s).
- 7.0 s is Gazebo share-on-detect minus the Gazebo full-map run (28.9 - 21.9 s).

Sec. IV-F now gives both and names each reference.

**N4. Detection channel — Accepted.** `agent.py` (`oncoming_conflict`) detects conflicts from peer positions in STATE messages, not from the lidar. Sec. III-B now says so, notes that the 6 m default exceeds the 3.5 m lidar range, and lists what the lidar is used for (reactive baseline, bay check, explore mode).

**N5. Claims resting on `[+-XX]` — Accepted.**
- (a) The convoy sentence now says the means "suggest" that the group bid underestimates the cost of a convoy yield, and that its ordering against fixed priority is provisional until the paired intervals exist. The Discussion now says this ordering "awaits paired intervals" instead of stating it.
- (b) The 0.7 s gap is now reported as a difference, and the text says we do not yet claim equivalence.
- The placeholders stay.

**N6. Known-bays study — Accepted; the row is filled.** From `studies/asym_map.py` and `studies/report/asym_map.txt`:
- Design: 7 knowledge conditions x 3 policies (F, D, C) x loss {0, 50}% x map in BID or not x 10 seeds = 840 episodes, with bays at 3 m and 7 m.
- Sec. IV-E reported one fact incorrectly, now fixed:
  - **The +29.6 s belongs to fixed priority and the default rulebook,** not "the rulebooks."
- It also stated two things too broadly:
  - **Sharing maps does not remove the cost in "every case."** When neither robot knows a bay, both share modes cost +30.9 to +31.1 s, so the claim is now limited to conditions in which at least one robot knows a bay.
  - **A poorer map for A does not always cost time.** When A knows only bay 2 there is no cost; the text now says so.
- The 50%-loss values (+9.3 s, +29.3 s) are added.

**N7. Transfer scope — Accepted.** Contribution 4 now limits the transfer claim to corridor studies whose random draws both simulators share. It names noisy bids, heavy packet loss and lidar detection timing as cases that differ. Sec. IV-H now begins the transfer sentence with "Where the two simulators share the random draws." The Discussion makes no transfer claim, so it needed no change.

**N8. N-column semantics — Accepted.** Every row of `tab:design` now gives total episodes:
- Convoy: 3 B types x 4 bay layouts x 3 delays x 2 loss levels x 3 seeds x 5 policies = 1,080.
- T-junction: 12 start-delay combinations x 2 goals x 2 loss levels x 2 seeds x 4 policies = 384.

The prose now says "per policy and B type" and "per policy and loss level" instead of "per cell."

**N9. Ablation pattern — Accepted.** Sec. IV-C now says that cost-bidding success rose slightly as safeguards were removed (98.9% to 99.7%). It also says that commit added 3-4 s of mean delay for both policies. Both policies' success differences are 1-4 deadlocks in 360 episodes, within sampling noise, so commit did not measurably help either policy.

## Minor comments

- **Asymmetric 98% — Accepted.** The "never enough to change the decision" claim is now limited to the single- and two-bay studies. A new clause attributes the other 2% to the bid model ignoring acceleration and turning, and says we have not traced them (TODO added).
- **Artifact URL — Not resolved.** The authors must supply the link.
- **Learned row — Accepted.** It now reads: 800 training encounters, each run under both forced outcomes; then 150 evaluation encounters per layout, with every policy run on every encounter. N is 1,600 training plus 1,500 evaluation episodes.
- **"+10.0 s for both policies" — Accepted.** The values match because, with the hold, both policies sent B into bay 2 in every run (`gazebo_hold_runs.csv`).
- **Table numbering — Clarified.** LaTeX numbers tables by caption order in the source: `tab:design` is Table I, `tab:abl` Table II, `tab:gz` Table III. Every reference uses `\ref`, and there are no hard-coded table numbers. A full-width table can be placed out of order on the page, but its number stays the same. The paper still has not been compiled.

## Questions
1. Yes; see N1.
2. See N2.
3. No, they use different references; see N3.
4. The sentences that depend on placeholders are now hedged, so they can stand if the intervals turn out wide.
5. We think so, but we have not traced these episodes (TODO added).

## Edits to `paper/main.tex`
- **Preamble:** added the `array` package. The `tab:design` grid column is now a fixed-width wrapping column; the long rows would otherwise overflow.
- **Contribution 4:** transfer claim scoped (N7).
- **Sec. III-B:** conflict detection runs on STATE messages, and the lidar's roles are listed (N4).
- **Code versions paragraph:** says the hold-mode runs used a branch, with a TODO to confirm commit IDs.
- **`tab:design`:** misreport row, convoy (1,080), T-junction (384), known bays (filled, 840), learned row.
- **Sec. IV-A:** prediction-error claim scoped; asymmetric 2% clause added.
- **Sec. IV-C:** ablation sentence rewritten (N9).
- **Sec. IV-D:** convoy hedges (N5); "36 distinct start configurations" corrected to 12 combinations x 3 seeds that vary jitter and loss; T-junction count wording.
- **Sec. IV-E:** known-bays paragraph corrected (N6).
- **Sec. IV-F:** 7.0 s vs 6.8 s references (N3); explanation for the equal +10.0 s.
- **Sec. IV-H:** per-study 122/338 split (N2); the transfer sentence scoped; T-junction second yields corrected. The 2D runs also had second yields in 2 of 6 seeds, so the text now says Gazebo added them in 4 of 4 fixed-priority runs and 3 of 4 rulebook runs whose 2D pair had one yielder.
- **Discussion:** convoy conclusion hedged.

## Not resolved
1. **Artifact URL/DOI:** still `[ANONYMIZED-URL]`.
2. **Placeholders that need new analysis:** the prediction-error `[XX]`, and the convoy and T-junction `[+-XX]` intervals.
3. **Commit IDs:** could not read `git log`. The IDs in the TODO (`bf24bf4` as parent of `2ba4c6d`, hold branch `f5249a6`) come from `studies/results_raw/README.md` and `media/gazebo_final/README.md`.
4. **Hold-mode branch:** the repo README says this branch is "not on main yet." The authors should merge it, or confirm it is part of the released code, before the "final agent code" statement holds.
5. **Asymmetric 2% cause:** inferred, not yet traced.
6. **Possible detection-distance inconsistency (left unchanged):** `gazebo_hold_runs.csv` records a Gazebo detection distance of 1.1-1.2 m for the hold runs. Sec. IV-F's hold paragraph says the lidar first sees the peer 2.3-2.6 m away, which is the figure from the runs without the hold. The authors should check what that column measures.
7. **Compile:** the paper was not compiled, so the layout of the widened design table is unchecked.
