# S8c protocol ablation

Extreme comms grid of S8b (loss 0.9/0.97/0.99, latency 2/4/8 s, detect range 1.5/6 m, v_max 0.5 m/s, B start delay U[0, 8] s, 20 seeds per cell). commit = wait for the peer's decision; state guard = STATE-message rules that detect both robots yielding (same refuge / to each other); bay check = lidar-occupied bays count as taken. Delays are means over successful episodes (± 95% CI half-width).

| Policy | commit | state guard | bay check | n | success [95% CI] | deadlocks | collisions (95% upper) | delay, successes (s) | both started yielding |
|---|---|---|---|---|---|---|---|---|---|
| `fixed_priority` | 1 | 1 | 1 | 360 | 99.2% [97.6–99.7] | 3 | 0 (1.06%) | 89.8 ± 3.9 | 21.9% |
| `fixed_priority` | 1 | 1 | 0 | 360 | 99.2% [97.6–99.7] | 3 | 0 (1.06%) | 89.8 ± 3.9 | 21.9% |
| `fixed_priority` | 1 | 0 | 1 | 360 | 99.2% [97.6–99.7] | 3 | 0 (1.06%) | 90.0 ± 4.0 | 23.6% |
| `fixed_priority` | 1 | 0 | 0 | 360 | 99.2% [97.6–99.7] | 3 | 0 (1.06%) | 90.0 ± 4.0 | 23.6% |
| `fixed_priority` | 0 | 1 | 1 | 360 | 98.1% [96.0–99.1] | 7 | 0 (1.06%) | 86.0 ± 3.6 | 15.3% |
| `fixed_priority` | 0 | 1 | 0 | 360 | 98.1% [96.0–99.1] | 7 | 0 (1.06%) | 86.0 ± 3.6 | 15.3% |
| `fixed_priority` | 0 | 0 | 1 | 360 | 98.6% [96.8–99.4] | 5 | 0 (1.06%) | 86.8 ± 3.7 | 16.4% |
| `fixed_priority` | 0 | 0 | 0 | 360 | 98.6% [96.8–99.4] | 5 | 0 (1.06%) | 86.8 ± 3.7 | 16.4% |
| `cost_bid` | 1 | 1 | 1 | 360 | 98.9% [97.2–99.6] | 4 | 0 (1.06%) | 79.6 ± 3.9 | 17.8% |
| `cost_bid` | 1 | 1 | 0 | 360 | 98.9% [97.2–99.6] | 4 | 0 (1.06%) | 79.6 ± 3.9 | 17.8% |
| `cost_bid` | 1 | 0 | 1 | 360 | 99.2% [97.6–99.7] | 3 | 0 (1.06%) | 79.9 ± 3.9 | 18.6% |
| `cost_bid` | 1 | 0 | 0 | 360 | 99.2% [97.6–99.7] | 3 | 0 (1.06%) | 79.9 ± 3.9 | 18.6% |
| `cost_bid` | 0 | 1 | 1 | 360 | 99.4% [98.0–99.8] | 2 | 0 (1.06%) | 76.4 ± 3.7 | 14.2% |
| `cost_bid` | 0 | 1 | 0 | 360 | 99.4% [98.0–99.8] | 2 | 0 (1.06%) | 76.4 ± 3.7 | 14.2% |
| `cost_bid` | 0 | 0 | 1 | 360 | 99.7% [98.4–100.0] | 1 | 0 (1.06%) | 76.8 ± 3.7 | 14.7% |
| `cost_bid` | 0 | 0 | 0 | 360 | 99.7% [98.4–100.0] | 1 | 0 (1.06%) | 76.8 ± 3.7 | 14.7% |

Bay-check arms are episode-for-episode identical to the arms without it: True.
