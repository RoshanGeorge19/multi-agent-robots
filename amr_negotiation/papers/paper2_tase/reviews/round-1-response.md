# Response to Reviewers — Round 1 (paper2)

We thank the reviewer for a careful report checked against the released data. Most numerical points were correct, and checking them uncovered a larger error in our tiebreak section (Major 5). Two definitions used below:
- **Serial / concurrent:** whether measured-latency runs executed one episode at a time or four at once against the model server.
- **Paired subset:** the first 25 seeds per layout (50 encounters), shared by all 50-encounter arms and the 200-encounter arms.

Author's note to orchestrator: figures were not regenerated and the LaTeX was not compiled (no shell in the writer session); `make_figures.py` needs a rerun. Every number in this response and the manuscript comes from `studies/report/llm_*.md`, the `rows.jsonl` files, the `stage*.sh` launch scripts, or `stage2c.log`.

**Finding beyond the review that changes a main claim:** the tiebreak story is not supported by the data.
- Disagreement does not vanish under the visible draw. The 0% fallback only means the draw, not the rulebook, settled each conflict. Both robots still yield or both proceed on 126, 83, 102 and 104 of 200 encounters.
- Visible and hidden draws give the same outcomes. Right-yielder is 48-59% vs 49-63%.
- The hidden draw "preserving deliberation" is true by construction. Its prompts are byte-identical to the rulebook arm, so within a run it reuses the same cached answers.

Sec. V-F, contribution 5, the abstract, Discussion and Conclusion were rewritten to say what the data show: a fair coin is a worse fallback than the informed rulebook (40-51% vs 66-71% right on the conflicted encounters), whether or not the agents see it.

## Major concerns

**Major 1 (success vs. deadlock contradiction): accepted.**
- "All runs succeed" was wrong. We now define a timeout: either robot has not reached its goal by the 180 s horizon (`t_max`). The released data call this `deadlock`.
- The fallback decision does execute, but only after the charged latency. In `qwen3-30b-onm` raw (88% parse failures, 100.3 s mean latency), it arrives too late to finish within 180 s.
- Sec. III-A now says every zero-cost run succeeds, and that excess is averaged over successful runs only.

**Major 2 (one model, n=50, serial/concurrent confound): accepted.**
- `qwen3-30b-onm` ran with 4 workers (`stage2b_matrix.sh`). Our vLLM deployment serves one sequence at a time (per `docs/llm_experiments.md`), so its 31.1 s latency includes queueing. The same model with thinking off measured 22.0 s concurrently and 0.7 s serially.
- Sec. III-B defines both regimes, and every measured arm in Table II is labeled with its regime, latency and n.
- The +103.1 s is now called an upper bound, with n=50 stated.
- No serial thinking-on data exist. The `qwen3.8-27b-onm-s` rerun was stopped after 10 of 50 encounters (35,386 s, from `stage2c.log`), and `qwen3-30b-onm-s` never ran. This is now stated, with a TODO.
- In place of the single headline number, we report a slope present in the data: about 3.4 s of excess per second of latency.
  - 104.4 s over 31.1 s for thinking-on qwen3-30B.
  - (34.1 - 11.1) s over 6.7 s for serial thinking-off qwen3.8.
  - This matches two robots idling at the mean urgency weight of 5/3.
  - It gives break-even latencies of about 0.4-0.5 s against cost bidding and about 1.4 s against the rulebook. The deployed conclusion now rests on this, not on +103 s.

**Major 3 (Fig. 3 mislabels arms): accepted.** The script did put `qwen3.8-27b-on0` (zero cost) in the "measured" group and used thinking-off runs as the quality baseline. The rewritten block pairs runs with the same thinking setting on the same encounters:

| Pair | Zero-cost run | Measured run |
|---|---|---|
| qwen3-30B, thinking on | `on0` | `onm` |
| qwen3-30B, thinking off | `off0` | `offm-s` |
| qwen3.8, thinking on | `on0` | -- (marked "not run") |
| qwen3.8, thinking off | `off0` | `offm-s` |

Each bar is labeled with n and the measured regime. The caption is updated.

**Major 4 (sample-size asymmetry): accepted.**
- Seeds are `seed0 + i` per layout, so 25-per-layout arms use seeds 100000-100024, a strict subset of the 200-encounter draw. This is stated in Sec. III-A and III-E.
- The baselines on the subset (rulebook 3.7 s, fixed priority 10.3 s) are now Table II rows.
- The plans-arm on/off comparison is fully paired on 200 encounters. The screen run is the thinking-on, zero-cost condition at n=200, and Sec. V-B now uses it rather than the n=50 cells.

**Major 5 (tiebreak numbers): accepted. Verifying them showed a larger error, now corrected.**
- (a) The 99% was cost bidding's figure. On the conflicted encounters themselves, the rulebook is right 66-71% (omni 122/171, qwen3.8 55/82, gemma4 64/92, vl-12b 54/82). The hidden draw is right 40-51% on the same encounters (80/171, 42/82, 47/92, 33/82). The old "45-51%" left out vl-12b's 40%.
- (b) Hidden-draw arm excess is 7.8-14.0 s. The rulebook arm is 3.1-10.6 s.
- (c) Visible-draw right-yielder is 48-59% with egocentric images and 45-56% with text only.
- The larger error is described above.
- Only omni engages with the draw: 183 of 200 encounters cite the card or draw, against 28, 27 and 2 for the other models.
- Sec. V-F and new Table III are rewritten. Contribution 5, the abstract, Discussion and Conclusion are corrected. The "stated default becomes the policy" and "magnet" claims are removed.

**Major 6 (reproducibility): accepted.**
- Sec. III-B now says the cache gives identical answers and exact resumption within a run, not determinism across runs.
- Observed cross-run spread is reported: omni ego disagreements 167-173, and qwen3.8 thinking-off mediator+plans 11.1 vs 14.9 s under the same configuration.
- The hidden-draw identity is described as a cache consequence within one run.

**Major 7 (paired statistics): accepted in part.** Per-arm 95% CIs are now in Table II and Table III. Omni image vs. text is flagged as within CIs. Paired-difference CIs are marked `[XX]` with TODOs: they could not be computed without running code, and were not estimated.

**Major 8 (completeness): accepted.**
- New Appendix A gives the prompt templates verbatim from `llm.py`: system prompt, situation lines, mediator, agent, visible-draw text, and both image legends. It also states that image-only arms drop the text entirely.
- The JSON schema, temperature, seed, token cap, timeout definition, freeze rule and serial/concurrent rule are in Sec. III-B.
- The thinking setting of every arm group is in Sec. III-E (vision, egocentric and tiebreak arms run with `--no-think`).
- New Table II covers 30 arms with n, excess +- CI, right-yielder and fallback composition. New Table III covers the tiebreak arms.

## Minor comments

- **92-94% -> 92-93%:** fixed.
- **Muse-Glimmer:** the table row is removed and the text now says nine models. Its serve log shows "Transformers does not recognize this architecture", and the text says so.
- **1.5B model:** now reported as n=20, llama.cpp 4-bit GGUF, zero-cost mediator arms, 28.0-30.5 s and 25-30% right.
- **Text+image worse "on three of four":** corrected to all four.
- **"far below":** rephrased.
- **Ego images vs. text:** all four models reported, including omni's 97% fallback.
- **Plans arms:** gemma4 21% disagreement and 88% right-yielder, against omni and vl-12b at 199 and 194 of 200.
- **Degenerate raw-on cells:** annotated in the Fig. 2 caption and text.
- **"Below the rulebook":** now "worse than".
- **Survivorship in the 301.5 s raw-arm excess:** stated.
- **Corrupted runs:** `qwen3.8-27b-offm`, `-c2/-c4` and `qwen3-30b-c1-c4` (all with connection resets), plus the hosted endpoint cells, are listed as excluded.
- **"Unspoofable":** removed. The text now says the draw is fair only between non-adversarial robots, and the Blum citation is reframed as the protocol we did not implement. The empirical card-win split is marked `[XX]`.
- **Held-out seeds:** now give the seed range and what they are disjoint from (learned-negotiator training seeds 0-799, evaluation 10000-10149).
- **"30-130 s":** removed. The means are 31.1 and 100.3 s.
- **Per-model agreed-encounter right-yielder (Q8):** now given as 58% (19/33), 69% (77/112), 64% (59/92) and 71% (77/108). The wrong-agreement mean excess is `[XX]`, and the "13.7-38.0 s" and "most expensive failure" claims are dropped.
- **Code release:** repository URL added, with a TODO to pin a tag.
- **Related work:** all six suggested references are now cited.
- **Other limitations:** companion-paper dependence and NVFP4 quantization are now in Limitations.
- **Leftover comment:** removed.
- **Unverified latency claims:** "9.3 -> 4.2 s" and "10-30x" could not be verified and are removed.

## Answers to the questions
1. `onm` ran concurrently. The split between queueing and inference cannot be measured from the released data. No serial thinking-on data exist.
2. The timeout horizon is 180 s, and the fallback executes too late.
3. No: the rulebook picks the yielder by ordered rules and uses the planner only to choose the refuge. Cost bidding sees the same numbers as the LLMs and reaches 0.0 s. The LLMs' sub-reference excess comes from refuge choice: the planner minimizes unweighted delay, while the prompt asks for urgency-weighted delay.
4. The thinking-on cells were run as diagnostics for cost reasons, and their seeds are a strict prefix of the 200-encounter draw.
5. Muse-Glimmer failed to load.
6. The card-win split is `[XX]`.
7. Both robots freeze. In agents mode the charge is the slower of the two calls, and both robots wait that long.
8. The agreed-encounter right-yielder values are given above; the wrong-agreement mean excess is `[XX]`.

## Edits made

**`paper2/main.tex`:**
- **Preamble:** added the `url` package.
- **Abstract:** rewritten for accuracy and kept short (nine models, 92-93%, -1.0 to -1.7 s, "worse than" the rulebook, the latency slope and break-even, corrected tiebreak claim).
- **Introduction:**
  - Model count, parameter range (12-49B) and pairing statement corrected.
  - Contributions 1, 2, 3 and 5 revised; contribution 4 lost the "personality" wording.
- **Related work:** added paragraphs on auction/market coordination and LLM multi-robot work. The game-theory paragraph no longer overclaims.
- **Sec. III-A:**
  - Seed ranges and the subset rule.
  - Timeout definition and 180 s horizon.
  - How the forced-yielder reference picks refuges.
  - Fallback timing under measured latency.
  - "Every zero-cost run succeeds".
- **Sec. III-B:**
  - Request parameters.
  - Information levels, including what the rulebook does and does not see.
  - JSON schema.
  - Cache scope and cross-run spread.
  - Both robots freezing, the slower-call charge in agents mode, and the serial/concurrent regimes.
- **Sec. III-D/E:**
  - Nine models and the Muse-Glimmer failure.
  - Verified empty thinking-off traces.
  - Protocol: screen = thinking-on at n=200, n=50 subset pairing, baselines on the subset, thinking setting per arm group, list of excluded runs, `[XX]` placeholder for paired statistics, repository footnote.
- **Results:**
  - Table I: Muse-Glimmer row removed; 49B note changed to "dense, reasoning" to match the repo roster.
  - New Table II (two side-by-side panels in a `table*`).
  - Sec. V-A, V-B and V-C rewritten.
  - Sec. V-D: all four text+image comparisons, the plans/raw confound, and the omni CI caveat.
  - Sec. V-E: counts per model, ego image vs. text for all four, the plans sentence, and a `[XX]` placeholder.
  - Sec. V-F rewritten, with new Table III.
  - Captions of all six figures updated.
- **Discussion, Limitations, Conclusion:** rewritten to match the corrected results.
- **Appendix A:** prompt templates, verbatim.
- **TODO comments:** paired CIs (x3), serial thinking-on cells, wrong-agreement excess, card-win split, release tag, and screen trace status for gemma4, 49B and vl-12b.

**`paper2/make_figures.py`:** only the `fig_latency` block was replaced (the Major 3 fix): correctly paired arms, n and regime labels on each bar, and "not run" for the missing cell.

## Not resolved

1. **Paired-difference CIs** for the on/off and modality comparisons, the **wrong-agreement mean excess**, and the **card-win split** are `[XX]`. Each needs a short script run over `rows.jsonl`; the TODOs say what to compute.
2. **Serial thinking-on measured latency** needs new runs (`qwen3-30b-onm-s`, `qwen3.8-27b-onm-s`). The paper states the limitation.
3. **Figures need regenerating** by running `make_figures.py`. Two issues left alone because script edits were limited to Major 3:
   - The screen figure still has an empty `MuseGlm` tick, which now contradicts Table I. Removing that entry from the `models` list fixes it.
   - The script's `stat()` CI divides by sqrt(n-1) instead of sqrt(n), so error bars are slightly wider than the reported CIs.
4. **Characterizing models as non-reasoning:** the screen rows do not record traces, so it can't be confirmed whether gemma4, N-Super-49B or N-VL-12B reasoned. The text now avoids calling them non-reasoning (TODO left).
5. **"Max one sequence at a time" server setting:** this comes from `docs/llm_experiments.md`, not from a server log. The 22.0 s vs 0.7 s contrast supports it, but the serve configuration should be confirmed.
6. **Table II width** is estimated at about 500 pt against the 516 pt text width. Check it after compiling.
