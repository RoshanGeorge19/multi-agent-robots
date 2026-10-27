# Response to Reviewer — Round 3 (paper1)

We thank the reviewer for checking the released data. Section numbers below follow the manuscript (IV-D convoy and T-junction, IV-F explore, IV-H Gazebo).

Author's note to orchestrator: a `% VERIFIED` comment in the middle of the hold-mode paragraph (Sec. IV-F) was commenting out the rest of that line — several sentences never appeared in the PDF (+10.0 s excess, share-on-detect comparison, bays-sensed, closing sentence). They now render. That fix plus new text adds ~20-25 lines; compile check needed for the 8-page limit. Two departures from the reviewer: the turn-in makespan range is 0.4-6.4 s, not 0.5-6.4 s (smallest values 0.448 s); and Q2 is rebutted — the code counts STATE freshness from receipt, not from sending.

## Major concerns

**M1 (timing parameters not specified). Accepted.** We read every parameter from `AgentParams` and the code paths in `agent.py`. Sec. III-B now has a short paragraph on the timers, which are the same in every study:
- **BID resend (`neg_period` = 0.3 s):** a negotiating robot resends its BID every 0.3 s until the peer acknowledges its decision.
- **STATE freshness (`state_timeout` = 1.0 s):** a STATE counts as fresh for 1 s after it is received. The state guard, the renegotiation check and the release of a waiting robot use only fresh STATE.
- **Parked yielder (`park_timeout` ~ U[6,12] s):** it leaves once the peer's fresh STATE shows the peer past the refuge. Without a fresh STATE, it leaves when the lidar shows the peer past, or after a delay drawn per yield from U[6,12] s. Either way the lidar must show the lane clear.
- **Fallback after 3 s or 60 s (`neg_timeout`, `proceed_timeout`):** if no peer BID arrives within 3 s, or a waiting robot's yielder has not left the lane within 60 s, the robot falls back to reactive behavior. It negotiates again only when a peer's BID reaches it.
- **10 s backoff (line 592):** if no feasible refuge remains, the robot acts reactively and does not renegotiate with that peer for 10 s.

Reading the code also showed an error in our T-junction text. After the 60 s proceed timeout the robots fall back to reactive behavior; they do not "renegotiate". Sec. IV-H now says this correctly.

**M2 (T-junction Delta_D by variant). Accepted.** Sec. IV-H now splits the summed difference: -605.3 s in total, -260.0 s from the 18 exit runs (`cost_bid` -264.7, fixed priority +18.6, rulebook -14.0) and -345.4 s from the 18 turn-in runs. The text says the release-timing account covers only the exit runs.

For turn-in, the CSV shows two groups:

| Turn-in runs | Gazebo delay lower by (per run) | Gazebo makespan shorter by |
|---|---|---|
| A yielded (all `cost_bid` runs, seed 0 of the other two policies) | 9.5-11.7 s | 0.4-1.0 s |
| B yielded | 21.2-28.9 s | 4.0-6.4 s |

The old "1-5 s shorter" sentence mixed up makespan with weighted delay; it is deleted. We could not check whether the same ~20 s release offset explains the turn-in gap. The CSV has no event times, and we did not re-trace the raw turn-in logs. So the manuscript says plainly that this share is unexplained. "We do not claim that T-junction delays transfer" stays.

## Minor comments

- **Discussion, stale hedge. Accepted.** It now states that the group bid trails fixed priority by 14.4 +- 8.0 s when the lone robot is urgent.
- **Limitations, T-junction. Accepted.** It now says the gap is traced to a release-timing race only for the exit variant, and the larger turn-in share is unexplained.
- **"4.7-4.9 s longer". Accepted.** Now "on average 4.7-4.9 s (3.4-6.1 s per run)". The per-condition means are 4.73-4.88 s; per-run differences are 3.35-6.05 s.
- **196.8 s outlier. Accepted.** Added "summed over the three robots; the episode ended at 152 s".
- **"Parent of the last commit". Accepted.** Now "the commit before the last two". We also fixed the next sentence, which wrongly said explore mode was in the last commit; it is in the second-to-last.
- **N3, release completeness. Accepted (scoped).** The Statistics paragraph now names what is not released per episode: the convoy and T-junction studies and the bid-capture reruns. Their scripts regenerate them from fixed seeds. The abstract, contribution list, footnote and conclusion now say "results" instead of "per-episode results". A TODO comment marks the rows to release.
- **Detection distance. Clarified, partly unresolved.** In `analyse_gazebo_main.py`, `gz_detect_dist` is the distance between the robots at the first `peer_detected` event. That event needs a fresh STATE within lidar range and a lidar cluster within 0.5 m of that STATE's position. It is the same test in both arms, so "the lidar first sees the peer" was the wrong label, and the text now names the test. In the same CSV, the share-on-detect reruns detect at 1.23-3.36 m and the hold runs at 1.10-1.18 m. We could not find why holding brings detection closer, and the text now says so.
- **`gz_min_clearance`. Clarified.** The referee computes it as the distance between wheel axles minus twice the 0.25 m swept radius (`referee_node.py` line 136). It is not body clearance or wall clearance. The body extends only 0.0765 m ahead of the axle (`geometry.py`), so two robots stopped face to face can be 0.26 m apart axle to axle without touching, which reads as -0.24. Collisions are checked separately, with body rectangles at 10 Hz. One clause in Sec. III-D now defines the column. We did not check the heading of every negative-clearance run, so the text says only that negative values *can* occur without contact.
- **"each robot ... 5 of 6". Accepted.** Now "A in all 6 seeds and B in 5 of 6".
- **Hold run provenance. Noted.** The text says the hold runs came from a branch merged before release. Adding the be50818 -> f5249a6 line to the artifact README is outside this manuscript edit.
- **24 hold runs outside the 460. Accepted.** Sec. IV-F now says they and the 12 share-on-detect reruns are a separate batch outside the 460.
- **Working annotations. Acknowledged.** The `% VERIFIED`/TODO comments, `[ANONYMIZED-URL]` and the DRAFT thanks line will be removed before submission.

## Questions

1. **Release of per-episode rows and logs:** yes, before submission; tracked in the TODO above. Until then the text scopes the claim.
2. **`state_timeout` at 2-8 s latency. Rebutted in part.** Freshness is counted from when a message is *received* (`_rx = t` in `handle()`), not when it was sent. So latency alone never makes a STATE stale; it makes a fresh STATE describe the peer 2-8 s in the past. Packet loss is what thins out fresh STATE. With STATE sent 5 times per second and independent loss, the chance that none arrived in the last second is loss^5: 59% at 90% loss and 95% at 99% loss. Sec. IV-C now says this. It supports the reading that protection comes from the yield-and-pass logic, the lidar and the timers, and fits the state guard's null effect in Table II.
3. **A's role in the exit variant:** yes. Under `cost_bid`, A is the first yielder and waits parked off the lane. Under fixed priority and the rulebook, B yields and A waits in the lane. The text now says this explicitly.
4. **Same offset in the turn-in runs:** not verified (see M2).
5. **`gz_min_clearance`:** now defined (see the minor point). The collision check uses body rectangles, so these negative values are not missed contacts. The artifact docs should also note that this check runs at 10 Hz.
6. **Stale repo reports:** yes, they will be regenerated. `REPORT_explore.md` line 126 also gives 2.3-2.6 m for the hold runs, which contradicts `gazebo_hold_runs.csv` (1.10-1.18 m); the manuscript follows the CSV.

## Edits made (`paper/main.tex` only)

1. **Abstract:** "Code, study scripts, and results are released."
2. **Contributions:** footnote now ends "and results"; dropped "and per-episode results" from item 2.
3. **Sec. III-B:** added `\label{sec:proto}` and the timer paragraph (M1).
4. **Sec. III-D Metrics:** one clause defining the minimum-clearance column.
5. **Sec. III-D Statistics:** scoped the release claim, with a TODO comment on its own line so it does not hide the next sentence.
6. **Sec. IV-C:** sentence on STATE freshness under loss (Q2).
7. **Sec. IV-F hold paragraph:**
   - moved the `% VERIFIED` comment to the end of its line, so the hidden sentences now render;
   - redefined detection and said its cause is untraced;
   - "on average 4.7-4.9 s (3.4-6.1 s per run)";
   - noted the batch is outside the 460;
   - "+10.0-10.1 s, nearly coincide";
   - "A in all 6 seeds and B in 5 of 6".
8. **Sec. IV-H commit text:** "the commit before the last two"; corrected which commit added explore mode.
9. **Sec. IV-H T-junction paragraph:**
   - variant split (-605.3 = -260.0 + -345.4) and per-policy exit sums;
   - A's role under `cost_bid` versus the other two policies;
   - proceed timeout now leads to reactive fallback;
   - 196.8 s explained as summed over robots, episode ended at 152 s;
   - turn-in breakdown, stated as unexplained;
   - removed "1-5 s shorter";
   - the VERIFIED comment now records the CSV sums.
10. **Discussion:** asserts the 14.4 +- 8.0 s result.
11. **Limitations:** T-junction sentence updated.
12. **Conclusion:** "results are released".

## Not resolved

- **Turn-in mechanism (M2, Q4):** needs a trace of the raw turn-in logs; the CSV has no event times.
- **Why holding brings detection closer:** needs the Gazebo hold traces. The text says it is untraced.
- **Negative clearance, run by run:** the column is explained from the code but each run's robot headings were not checked from its trace.
- **Artifact work outside this file:** releasing the convoy and T-junction rows and the bid-capture logs, the artifact URL, the README line for the hold-run tag, and regenerating `REPORT_tjunction.md` and `REPORT_explore.md`.
