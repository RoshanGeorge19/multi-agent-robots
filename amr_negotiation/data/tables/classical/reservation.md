# Corridor-reservation baseline and best-of-strategies reference

1260 episodes; 210 encounters (bay x ∈ {1…7} m × 30 seeds, B start delay U[0, 8] s per seed). Delays include every episode (a failure would count as ∞; there are none if every success rate is 100%).

| Policy | success | collisions | total delay [s] | excess vs best forced yielder [s] | excess vs best of strategies [s] |
|---|---|---|---|---|---|
| `reservation` | 100.0% [98–100] | 0 | 45.6 ± 0.3 | 18.8 ± 0.9 | 18.8 ± 0.9 |
| `fixed_priority` | 100.0% [98–100] | 0 | 33.3 ± 1.3 | 6.5 ± 0.9 | 6.5 ± 0.9 |
| `rules_default` | 100.0% [98–100] | 0 | 33.3 ± 1.3 | 6.5 ± 0.9 | 6.5 ± 0.9 |
| `cost_bid` | 100.0% [98–100] | 0 | 26.8 ± 0.8 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| `best_forced` | — | — | 26.8 ± 0.8 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| `best_of_strategies` | — | — | 26.8 ± 0.8 | 0.0 ± 0.0 | 0.0 ± 0.0 |

`reservation` beats the best forced yielder by > 0.1 s in 0/210 encounters (0%); mean gain there nan s.

Excess of `reservation` over the best forced yielder by bay position [s]: x=1: 7.9 ± 1.5, x=2: 15.6 ± 1.5, x=3: 23.3 ± 1.5, x=4: 23.3 ± 0.0, x=5: 24.0 ± 1.5, x=6: 22.6 ± 0.0, x=7: 14.9 ± 0.0
