# Round 2: noisy bids, comms stress, payments, repeated encounters

This round follows up on [`REPORT.md`](REPORT.md). It uses the same 2D simulator, the same single-bay corridor and the same statistics (95 % CIs, regret paired by seed against the hindsight oracle). Full tables are in [`report_r2/results_r2.md`](report_r2/results_r2.md).

Reproduce with:

```bash
python studies/run_studies_r2.py studies/results
python studies/analyse_r2.py studies/results
```

That is about 14 000 episodes, taking ~10 min on 8 cores.

| Study | Question | Episodes |
|---|---|---|
| S7 | Does `cost_bid` still match the oracle when each robot's cost estimate is noisy? | 3 150 |
| S8 | Do a shorter conflict-detection range and faster robots (0.5 m/s) break the protocols under loss and latency? | 4 320 |
| S8b | The same, under extreme comms: loss 90–99 %, latency 2–8 s | 1 440 |
| S9 | Do VCG (Clarke-pivot) payments remove the incentive to inflate bids? | 1 440 |
| S10 | Fairness over 20 repeated encounters: alternation and credit-weighted bidding | 2 000 |

## Findings

1. **Noisy bids: the advantage of `cost_bid` holds up to about ±50 % estimation error.**
   - Each robot's bid was multiplied by a log-normal factor exp(σ·N(0,1)).

     | σ | regret vs. oracle | same yielder as oracle |
     |---|---|---|
     | 0 | 0 s | 100 % |
     | 0.1 | 0.2 s | 97 % |
     | 0.25 | 1.5 s | 86 % |
     | 0.5 | 3.3 s | 72 % |
     | 1.0 | 4.5 s | 62 % |
   - At σ ≈ 0.5, `cost_bid` is no better than the noise-free rule "closest refuge yields" (3.1 s regret).
   - So bidding needs cost estimates good to within roughly a factor of 1.6 to beat a simple rulebook.
2. **Comms stress: the protocols are hard to break, but extreme impairment does produce rare collisions.**
   - **S8.** Every policy reached ≥ 96.7 % success with **no collisions**. This covered all loss levels up to 90 %, latency up to 2 s, detection range down to 1.5 m and robot speed up to 0.5 m/s. A shorter detection range did not hurt.
   - **S8b.** Under extreme impairment (loss 90–99 %, latency 4–8 s), **6 of 1 440 episodes (0.4 %) collided**.
     - All 6 used the 6 m detection range.
     - They came from just two seed/configuration pairs: loss 0.9 with latency 8 s, and loss 0.99 with latency 4 s.
     - In all 6, **both robots ended up yielding**. This is the lost-message asymmetry seen before: one robot acts on a stale decision while the other has timed out and fallen back to reactive behaviour.
   - Both robots yielded in about 15 % of S8b episodes, and about 2.5 % deadlocked.
   - At 97–99 % loss, the robots fall back to reactive behaviour in 73–91 % of episodes. That fallback is slow but safe.
   - Hardening the protocol against lost messages (an acknowledged commit before moving, or a lease/expiry on decisions) is the next protocol fix.
3. **Payments make honest bidding pay.**
   - **Without transfers**, B gains 1.0 ± 0.2 s by reporting 2× its cost, and total delay rises by 4.9 s.
   - **With VCG payments**, where the robot that proceeds pays the yielder's reported bid, the same inflation *costs* B 9.7 ± 2.0 s. Truthful reporting is best for B.
   - **Price:** the payments are not budget-balanced. About 21–25 s of "delay credit" per encounter goes to the bank. In a fleet this would be a virtual currency rather than real cost.
   - An inflation of 1.5× changed no decisions.
4. **Repeated encounters: a small fairness credit buys near-perfect fairness cheaply.**

   | Rule | Total delay vs. cost-optimal | Jain index (cumulative delays) |
   |---|---|---|
   | `fixed_priority` | +28 % | 0.75 |
   | cost-optimal | — | 0.92; gap between the robots 128 s per sequence |
   | strict alternation | +23 % | 0.99 |
   | **credit-weighted bidding, λ = 0.25** | **+8 %** | **0.997** (gap 25 s) |
   | credit-weighted bidding, λ = 2 | +21 % | 0.999 |

   Credit-weighted bidding yields the robot that minimises total delay + λ·(own cumulative delay − other's). Larger λ adds cost for no extra fairness.

## Caveats

- **S10 decisions use measured costs.** Its per-encounter costs come from forced-yielder runs. Each selection rule is therefore applied with realised costs, not the robots' predictions.
- **S9 utilities use the robots' predicted bids** together with measured delays.
- **Gazebo sweep still running.** The Gazebo sweep of S1 (10 seeds × 5 policies) is in progress and will be reported separately.
- **3+ robots and T-junctions need new code.** A quick three-robot test, a two-robot convoy against one oncoming robot in the two-bay corridor, deadlocks under every policy: reactive, fixed priority and cost bid. Negotiation is pairwise and cannot resolve convoys yet.
