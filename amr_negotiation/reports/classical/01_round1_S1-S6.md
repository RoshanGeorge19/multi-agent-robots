# Corridor / pull-in-bay negotiation: first studies

These studies address the open questions from [`docs/literature_review.md`](../../docs/literature_review.md) §6. Unless stated otherwise:

- Simulator: the 2D unicycle simulator (`sim2d`), with TurtleBot3 Waffle dimensions and limits.
- Scenario: 8 m × 0.65 m corridor with a 0.8 × 0.6 m bay. The end rooms also act as refuges.
- Arrivals: A enters at t = 0; B's start delay is drawn from U[0, 8] s for each seed.
- Statistics: ± values are 95% confidence intervals. Rates show 95% Wilson intervals in brackets.
- Regret: total delay minus that of the hindsight **oracle**, which simulates both possible yielders and keeps the better one, paired by seed.
- Full tables are in [`data/tables/classical/results.md`](../../data/tables/classical/results.md).
- Reproduce with `python experiments/classical/run_studies.py results` followed by `python experiments/analysis/analyse.py results` (about 19 000 episodes, ~8 min on 8 cores).

| Study | Question | Episodes |
|---|---|---|
| S1 | Q1 price of no communication; Q2 price of decentralisation; Q4 bay position | 2 940 |
| S2 | Q3 rulebook vs. bidding when robots differ (urgency 1/3, loaded, half speed) | 5 040 |
| S3 | Q5 packet loss 0–90 % × latency 0.05–2 s | 3 600 |
| S4 | Q4 two bays (positions and sides) | 2 520 |
| S5 | Q6 fairness (derived from S1) | — |
| S6 | Q7 strategic misreporting in cost bidding | 1 080 |

## Headline findings

1. **The price of no communication is large.** The reactive baseline:
   - succeeds in **93.1 %** of episodes; the other 6.9 % are deadlocks still unresolved at `t_max`;
   - incurs **98 ± 5 s** total delay, against 26 ± 0.6 s for the oracle (×3.8);
   - reverses **5.7 m**, against 0.64 m;
   - has **both** robots back off in 39 % of episodes, the reciprocal "dance" described in the literature.

   Every negotiating policy reached 100 % success with no collisions.
2. **In this simulator, cost bidding matches the oracle.** `cost_bid` picked the oracle's yielder in 100 % of S1 and S4 episodes (zero regret). Under asymmetry (S2) it picked it in 88 % of episodes, with a weighted-delay regret of 0.8 s.
   - Caveat: the bids use the same kinematic model as the simulator, so this is an upper bound. Noisy or biased cost estimates, and Gazebo runs, are the next test.
3. **Rulebooks lose most when the bay is behind the first robot.**
   - `fixed_priority` and the default rulebook give identical decisions when the robots are symmetric. Their regret is 6.4 s on average, and up to 14.7 s when the bay is 2–3 m from A's entrance: they send the late robot B back past it.
   - `rules_proximity` ("closest refuge yields") halves the regret to 3.1 s.
   - When the bay is on B's side (x ≥ 5 m), all negotiating policies are optimal.
4. **Asymmetry punishes fixed priority.** With urgency, load and speed differences, `fixed_priority` has 27 s of weighted-delay regret. The default rulebook, with its urgency and loaded rules, cuts that to 3.6 s, and `cost_bid` to 0.8 s.
   - An oracle that minimises *unweighted* delay has 7.1 s regret on the weighted metric. The choice of objective matters as much as the choice of protocol.
5. **In this set-up the negotiation was very robust to communication impairment.** Across 3 600 episodes:
   - no collisions occurred;
   - success stayed ≥ 93 % even at 90 % loss with 2 s latency;
   - failures appeared only at 90 % loss;
   - agreement was 96–97 %, and both robots yielded in about 1 % of episodes.

   Latency up to 2 s had no measurable effect. Conflicts are detected 6 m out and `neg_timeout` is 3 s, which leaves slack. Shorter detection ranges and higher speeds are needed to find the breaking point.
6. **Efficiency and per-episode fairness trade off.**
   - `fixed_priority` makes B yield in 100 % of episodes, with a Jain index of 0.67 on the two delays.
   - `cost_bid` is the most efficient but has the lowest per-episode Jain index (0.56), because it puts most of the delay on one robot.
   - Across episodes, the yielding share is balanced: A 57 %, B 43 %.
7. **Cost bidding can be manipulated.** If B multiplies its bid by ≥ 2, B never yields:
   - B's own delay falls slightly (8.8 → 7.8 s);
   - A's delay rises from 15.6 to 21.5 s;
   - total delay rises by 4.9 s (+20 %);
   - an inflation of 1.5× changed nothing.

   "Lower bid yields" without transfers is not incentive-compatible. VCG-style payments or verifiable costs are needed (lit. review gap 3).

## Not yet studied

The following need code that does not exist yet:

- **Q8, 3+ robots, T-junctions and doorways.** Negotiation is currently pairwise (`policies._pair`).
- **Q9, LLM and MARL negotiators.**
- **Repeated-encounter fairness**, i.e. a token or credit carried across encounters.
- **Model mismatch in bids.**

## Gazebo spot-check

This section checks that the 2D results carry over to ROS 2 Jazzy + Gazebo Harmonic. It uses one headless episode per configuration on the default geometry (bay at 4 m, B delayed by 2 s; seed 0, `docker run … corridor.launch.py`).

| Scenario | Policy | Yielder(s), 2D → Gazebo | Makespan [s], 2D → Gazebo | Collision (Gazebo) |
|---|---|---|---|---|
| single bay | `reactive` | A and B → B | 116.8 → 110.8 | no |
| single bay | `fixed_priority` | B → B | 62.4 → 62.0 | no |
| single bay | `rule_based` (default) | B → B (`first_in_corridor`) | 62.4 → 62.0 | no |
| single bay | `cost_bid` | A → A | 60.3 → 59.9 | no |
| urgent + loaded B | `rule_based` (default) | A → A (`urgency`) | 60.3 → 60.1 | no |
| urgent + loaded B | `cost_bid` | A → A | 60.3 → 59.9 | no |

- **Negotiating policies.** All five negotiating runs made the same decision in Gazebo as in 2D, with makespans within 0.4 s.
- **Reactive baseline.** It differs in Gazebo: only B backed off, whereas in 2D both robots did. The reactive baseline is random by design (each robot's patience timeout is random), so its outcomes need many seeds in Gazebo before they can be compared.
- **Scope.** This is a single-seed sanity check, not a statistical Gazebo study. A Gazebo sweep runs at about 4–5 min per episode, i.e. roughly 40 episodes per hour with 3 containers.

