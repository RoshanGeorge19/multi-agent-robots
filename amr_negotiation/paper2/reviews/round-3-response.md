# Response to Reviewers (Round 3)

We thank the reviewer for checking the released data so closely. Each point is answered below.

## Major concerns

**1. Fig. 3 marks a completed run "not run". Accepted.** In `make_figures.py`, `LAT_CELLS` now has five cells. Thinking-on Qwen3-30B appears twice, as the concurrent arm and the new serial arm (`qwen3-30b-onm-s`). Thinking-on Qwen3.8 now uses `qwen3.8-27b-onm-s`, labeled "serial*". The caption explains the regimes, says what $n$ counts, and says what the asterisk means (see Major 3). The figure still needs to be regenerated.

**2. Limitations and Table II contradict Sec. V-C. Accepted.**
- (a) The false Limitations sentence is replaced. It now says serial thinking-on latency is measured for two models on 50 encounters each, and that one of those runs was resumed from a stopped run with an unrecorded worker count.
- (b) Table II now has both serial thinking-on rows:
  - Qwen3-30B: 16.5 s latency, $55.3\pm8.7$ s excess, 92% right yielder.
  - Qwen3.8-27B: 49.9 s latency, $157.9\pm23.2$ s excess, 94% right yielder.
  - A new footnote $^b$ gives Qwen3.8's 98% success and its provenance caveat.

**3. Qwen3.8 serial-run metadata. Accepted. The evidence narrows the explanation to two cases but does not decide between them.** Here is what we found:

- **An earlier run used the same output directory.** `stage2c_measured.sh` launched `qwen3.8-27b-onm-s` with `--workers 1` and no `--variants` flag, so it ran every arm. `stage2c.log` shows it began at 11:19 UTC and printed only "10/50 encounters, 35386 s" before it was stopped. The runner prints progress only every 10 encounters, so somewhere between 10 and 19 encounters had finished.
- **The final run reused that run's cached answers.** Its `meta.json` lists only `llm_med_plans` under the same tag, which means the same `cache.jsonl`. In `llm.py`, a cached answer is charged its original latency but costs no wall time. So the final run must have replayed the stopped run's mediator+plans answers.
- **That reuse alone doesn't explain the gap unless the stopped run got quite far.**
  - Summed charged latency is about 2495 s (49.9 × 50), against 1530 s of wall time.
  - From `rows.jsonl`, the ten encounters the log proves complete (single-bay seeds 100000–100009) account for 572 s. That leaves at least 1923 s of uncached latency, which is more than the wall time.
  - Running cumulative latency reaches 906 s after 17 encounters and 981 s after 18. Matching the wall time needs about 965–979 s cached, assuming the ~14 s of simulation overhead seen in `qwen3-30b-onm-s`.
  - So the serial-resume explanation holds only if the stopped run finished at least 18 encounters. The log neither confirms nor rules that out.
- **The other case is more than one worker.** The command for the final run was not logged, `meta.json` doesn't record the worker count, and `cache.jsonl` was not kept. If more than one worker ran, the 49.9 s includes contention and overstates deployed latency.
- **The Qwen3-30B serial arm is clean.** Its wall time is 839 s against 825 s of summed latency.

Sec. V-C now states all of this in one paragraph. It also notes that the conclusion doesn't depend on the Qwen3.8 value, because the clean Qwen3-30B serial latency (16.5 s) alone is about 12 times the break-even latency against the rulebook (1.1–1.4 s). The draft carried a LaTeX comment reading "VERIFIED … workers=1" for this run; it was not verified for Qwen3.8 and has been replaced.

**4. Sec. V-D significance claim. Accepted: the sentence was wrong, not the interval.** The paired point estimates equal the differences of the arm means. Vl-12b's $-5.1\pm4.0$ s gives $[-9.1,-1.1]$, which excludes zero. The text now says the paired intervals exclude zero for qwen3.8 and vl-12b and include it for gemma4 and omni, so the image-only advantage is established for two of the four models. We removed "p≈0.1 for the other three" because it can't be right for vl-12b. The four Wilcoxon p-values are shown as `[X.XXX]` placeholders: I could not recompute them in this session (see below). The Fig. 4 caption is updated to match.

**5. "Fair random tiebreak". Accepted.**
- **"Fair" removed:** it is gone from the abstract, contribution 5, Sec. V-F, the Discussion and the Conclusion, replaced by "random draw".
- **Plain draw disclosed in Sec. V-F:**
  - Both robots use robot A's detection time to compute the cards.
  - The robot IDs are the same in every encounter, so the card pair depends on the detection time alone. The 200 encounters therefore produce only 92 distinct card pairs.
  - Encounters that share a key share their draw, so the draws are not independent.
  - A wins 120 of 200 encounters, which would be 2.8 standard deviations from even if the draws were independent.
- **Commit-reveal draw:** the nonces come from the encounter seed, which both layouts share. That gives 100 distinct pairs, each used twice, and A wins 55 of the 100.
- **The draw is unsteerable only if robots report honestly.** The text now says so.

## Minor comments

- **Abstract range: accepted.** It is now scoped to egocentric images ("63–71% to 48–63%").
- **Commit-run condition: accepted.** Sec. V-F now says the run used agents mode with raw text, no image, and `think=0`, and that Lightning has no vision input. It also gives that run's right-yielder rates (58% visible, 55% hidden, 71% rulebook).
- **Commit prompt in Appendix A: accepted.** The commit-reveal draw rule is added verbatim from `llm.py`. The appendix also notes that the hidden-draw prompts (plain and commit) are identical to the rulebook prompt.
- **Commit arms not in Table III: accepted.** Sec. V-F explains they are excluded because the model and input level differ.
- **Slope from the serial arms: accepted.** Sec. V-C now gives 3.4 s/s for Qwen3-30B, 3.2 s/s for Qwen3.8-27B, 3.4 s/s for thinking-off Qwen3.8, and 3.4 s/s for the concurrent arm.
- **Qwen3.8 timeout: accepted, with a correction to the premise.** The one timed-out episode (single-bay seed 100001) followed a 119.5 s call and named the wrong yielder, so it is not a "slow but correct" case. The text gives only what the data show: the wait used two thirds of the 180 s horizon, leaving less than 60 s, and the answer was also wrong.
- **Which detection time the draw uses: accepted.** The text says robot A's (the lower ID), as the code does.
- **"One sequence at a time" (also Question 3): rebutted against our own draft.** The vLLM log for the concurrent qwen3.8 run (`stage2b.log`) shows "Running: 4 reqs, Waiting: 0 reqs", so the server was processing four sequences at once. The claim came only from `docs/llm_experiments.md` and is false for that run. Sec. III-B now says concurrent runs share one server and their latency includes contention. "Queueing" is replaced throughout.
- **Release tag/DOI:** still a TODO.

## Questions

1. **Qwen3.8 wall time vs. latency:** see Major 3. The cache was resumed, and the stopped run's command line specified one worker. Whether it covered the full gap, or whether the final run also used extra workers, can't be determined from the retained files. We don't know what other load the server had during the stopped run. One clue: the line "10/200 encounters, 8 s" in `stage2c.log`, which has no header, suggests another process was writing to that log at the time.
2. **Distinct-key split:** commit-reveal gives 55 of 100 (exact, since each key appears twice with identical cards). The plain-draw split over 92 keys can't be computed from `rows.jsonl`, which doesn't store detection times or cards. It is shown as `[XX]`.
3. **Serving claim:** contradicted by the server log; see above.
4. **Vl-12b:** the clause was wrong and the interval is right. The paired CIs are stated for all four models; the p-values are placeholders.

---

## Edits made

**`paper2/main.tex`**
- **Abstract:** "fair" removed; right-yielder range scoped to egocentric images.
- **Contribution 5:** "fair" removed.
- **Related Work:** commit-reveal variant mentioned.
- **Sec. III-B:**
  - Caching paragraph: added "a replayed call is charged its original latency but takes no wall time".
  - Serving paragraph: false single-sequence claim replaced with the server-log evidence of contention.
- **Sec. III-E:** "quantify queueing" → "quantify contention".
- **Table II:** two serial thinking-on rows and footnote $^b$ added.
- **Fig. 3 caption:** rewritten for five cells, the regimes, and the asterisk.
- **Sec. V-C:** rewritten into four paragraphs:
  - serial deployed cost, including the timeout sentence;
  - slope, now corroborated by all measured arms;
  - concurrent arm as an upper bound, with the latency contrasts;
  - the Qwen3.8 provenance paragraph, with a corrected LaTeX comment.
- **Sec. V-D:** significance sentence corrected; Wilcoxon placeholders; the LaTeX TODO comment notes the p-value recompute is still pending.
- **Fig. 4 caption:** updated to match Sec. V-D.
- **Sec. V-F:** split into a plain-draw paragraph (keying, 92 pairs, not independent, 120/200 and 2.8 SD, `[XX]` of 92) and a commit-reveal paragraph (100 pairs, 55/100, run condition, right rates, exclusion from Table III). "Fair coin" → "random draw".
- **Discussion, Limitations, Conclusion:** "fair coin" removed; the false Limitations sentence replaced.
- **Appendix A:** commit-reveal prompt added; hidden-draw note covers both draws.

**`paper2/make_figures.py`**
- `LAT_CELLS` now has five cells and includes `qwen3-30b-onm-s` and `qwen3.8-27b-onm-s` ("serial*"), with a comment explaining the asterisk. Figures not yet regenerated.

---

## Could not resolve

1. **Qwen3.8 serial-run provenance.** Two cases fit the evidence: the stopped run finished at least 18 encounters, or the final run used more than one worker. Settling it needs the author's memory of the rerun command, the shell history, or the deleted `cache.jsonl`. If the run did use more than one worker, it should be rerun with `--workers 1` and a fresh tag, or relabeled.
2. **Wilcoxon p-values for the four image-vs-text pairs.** Needed: a paired signed-rank test of `llm_med_img` against `llm_med_plans` on `*-vlm/rows.jsonl`, keyed by (layout, seed), for each model, then fill the four `[X.XXX]` placeholders.
3. **Plain-draw A-win count over the 92 distinct pairs (`[XX]`).** This needs a replay of `_draws` (detection times aren't in `rows.jsonl`).
4. **Commit run's reasoning setting.** `meta.json` doesn't record `--no-think`, and the logged `think` field holds the JSON answer, not a reasoning trace. The text states only `think=0`. Needs author confirmation.
5. **Server flags.** The stage2b log shows four sequences batched, which contradicts the doc's `--max-num-seqs 1`. Whether the stage2c serial runs used a different server configuration can't be checked from these files.
6. **Release tag/DOI:** still a TODO.
