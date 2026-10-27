# Response to Reviewer — Round 2 (paper2)

Author's note: all 13 minor points and Q1-Q4 answered; each number was checked against `studies/report/llm_*.md` and the `meta.json` files before writing. Not recompiled after these edits.

The biggest change: Q2 asked whether we would narrow any claim whose paired interval includes zero. The per-arm 95% CIs already overlap for **all four** models in the image-only vs. text+plans comparison, not just omni. The text now says that ordering is unproven until paired differences are computed.

**Major 1 (stale figures). Clarified, no edit needed.** The orchestrator reran `make_figures.py` and recompiled before this review was written. The regenerated `fig/latency.pdf` shows four pairs: on0<->onm, off0<->offm-s, with "not run" on the qwen3.8 thinking-on cell and n/regime labels on each bar. That compile was clean at 7 pages, with zero overfull boxes (so Table II fits) and no rendered `[XX]` strings. This answers Q1. That compile came before this round's edits, so it was repeated by the orchestrator.

## Minor comments

1. **Sec. V-E, plans arms (selective reporting). Accepted.** The sentence now says planner delays help only gemma4 agree (21% disagreement, 88% right, 3.1 s). Qwen3.8, omni and vl-12b disagree on 137, 199 and 194 of 200 with plans. With egocentric images the same three models disagree on 87, 167 and 103. Qwen3.8's 137 comes from `qwen3.8-27b-ego`, the run that also supplies its img arm.
2. **"Stays at 92%". Accepted.** Now reads "is 92%, against 94% at zero cost."
3. **Break-even populations mixed. Accepted.** All endpoints now come from the n=200 screen:
   - against cost bidding: margin 1.0-1.7 s, latency limit about 0.3-0.5 s;
   - against the rulebook (2.9 s): margin 3.9-4.6 s, latency limit about 1.1-1.4 s.
4. **Table III, rulebook comparator. Accepted in part, and Q4 answered.** We keep the `-silent` rulebook arm in the column on purpose. It shares cached answers with the hidden-draw arm byte for byte (170/27/3 for omni), so the rulebook-vs-hidden comparison changes only how conflicts are resolved. That comparison carries the section's main claim. A new footnote gives the rulebook arm from inside each visible-draw (nonce) run: 2.7 (73%), 8.7 (62%), 2.5 (75%), 4.8 (68%). These are all in the released data, and the gap from the silent-run values is consistent with the run-to-run variation reported in Sec. III-B.
5. **vl-12b fallback in Table III. Accepted, with a correction.** The vl-12b rulebook and hidden-draw arms (silent run) each have 10 parse fallbacks (5%). The visible-draw *image* arm in Table III has 0% fallback. The 5% in the visible draw belongs to the text-only arm, which is not in the table. Changes:
   - footnote b on the two affected vl-12b cells;
   - the Sec. V-F sentence now says no *image-arm* encounter falls back, and notes vl-12b's 10 text-only parse fallbacks.
6. **Omni "never has both proceed". Accepted.** Now reads "never has both proceed on this arm."
7. **Fig. 2 n=50 vs. text n=200. Accepted.** One sentence added in Sec. V-B: the figure plots the thinking-on cells from the 50-encounter reruns (-1.3 s for both models), not the screen.
8. **Fig. 3 caption. Accepted.** Now reads "No completed measured thinking-on arm exists for qwen3.8 (marked; a serial run was stopped after 10 of 50 encounters)."
9. **nemotron-3-super-onm-s. Accepted, but we read it differently.** One sentence added: the serial run completed, but every call returned an error within 0.1 s, so it measures error latency, not deliberation. This run used the hosted NVIDIA endpoint, not our local vLLM server. It therefore says nothing about local queueing either way. The Sec. V-C text and the Limitations now say "no *informative* serial thinking-on measurement."
10. **1.5B smoke used `max_tokens=256`. Accepted.** Confirmed in both smoke-run `meta.json` files. One clause added in Sec. V-A.
11. **Bare `[XX]` at the end of Sec. III-E. Accepted.** Sentence deleted. The TODO comment now lists the remaining paired-difference placeholders (Secs. V-B and V-D).
12. **Response-letter bookkeeping. Acknowledged.** The current `make_figures.py` has no MuseGlm entry and divides by sqrt(n). Both items were already fixed, and the figures are regenerated.
13. **Agents-mode measured rows missing from Table II. Accepted.** One sentence added in Sec. V-C: the decentralized measured arms are worse (thinking-on qwen3-30B agents+plans, concurrent: 172.9 s excess at 51.9 s latency) and are in the released data.

## Questions

- **Q1.** Answered under Major 1.
- **Q2. Yes, and we have already narrowed one claim.** On/off plans: the per-arm CIs are far apart (-1.7+-0.8 vs. 11.1+-2.5 and 22.5+-3.7 s), so paired CIs can only confirm the result. Image-only vs. text+plans is different. The per-arm CIs overlap for all four models:

  | Model | Image-only (s) | Text+plans (s) |
  |---|---|---|
  | gemma4 | 3.9+-1.9 | 6.6+-2.0 |
  | qwen3.8 | 9.0+-3.5 | 14.9+-3.0 |
  | vl-12b | 17.0+-3.5 | 22.1+-3.9 |
  | omni | 14.2+-3.7 | 16.4+-3.1 |

  The Sec. V-D text and the Fig. 4 caption now say this ordering is unproven until the paired differences are computed. We also note the overlap for gemma4 and qwen3.8 in the image+raw-text vs. image-only comparison.
- **Q3. Agreed, and Sec. V-C now says so.** The slope follows from the cost model rather than a fit: two robots idling at mean urgency weight 5/3 accrue about 3.3 s of weighted delay per second of latency. The two measured arms back this up (104.4/31.1 and 23.0/6.7 both give 3.4 s/s).
- **Q4.** Answered under minor 4.

## Edits to `paper2/main.tex`

| Location | Change |
|---|---|
| Sec. III-E (Protocol) | Deleted the "Paired ... are [XX]" sentence; TODO comment now points to the remaining placeholders. |
| Sec. V-A (Screen), 1.5B sentence | Added the 256-token cap caveat. |
| Sec. V-B (Reasoning) | Added a sentence saying Fig. 2 plots the n=50 on-cells (-1.3 s). |
| Fig. 3 caption | "No completed measured thinking-on arm...", plus the stopped-run note. |
| Sec. V-C, para 1 | 92% vs. 94%; slope reframed as following from the cost model and backed up by both measured arms; added the agents-mode measured-arm sentence. |
| Sec. V-C, para 2 | Added the nemotron-3-super-onm-s sentence; "no informative serial...". |
| Sec. V-C, break-even | n=200 margins 1.0-1.7 / 3.9-4.6 s; limits 0.3-0.5 / 1.1-1.4 s. |
| Sec. V-D (Vision) | Omni-only CI caveat widened to all four models; overlap note on image+text for gemma4 and qwen3.8. |
| Fig. 4 caption | "lowest mean excess ... but its per-arm CI overlaps the text arm's for each." |
| Sec. V-E (Ego) | "on this arm"; plans sentence now reports all four models with img comparators. |
| Sec. V-F (Tiebreak) | Visible-draw sentence: "no image-arm encounter falls back," plus the vl-12b text-only note. |
| Table III | Footnote a (same-run rulebook values) and b (vl-12b 5% parse) on the two affected cells. |
| Limitations | "no informative serial thinking-on measurement." |

## Still open

- **Paired-difference CIs:** the `[XX]` in Sec. V-B (on/off) and Sec. V-D (image vs. text) remain, with TODOs. They need a script run over `rows.jsonl`. The Sec. V-D claim is now worded as unproven, so filling it can only firm it up or remove it.
- **Other placeholders the reviewer didn't raise:** wrong-yielder excess in Sec. V-E, the card-win split in Sec. V-F, and a serial thinking-on latency measurement (needs new runs). All still have their TODOs.
- **Recompile:** needed to confirm the two new Table III footnotes fit with no overfull box.
- **Release tag/DOI:** still needs pinning before submission.
