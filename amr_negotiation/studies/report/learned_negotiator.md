| train encounters | eval layout | policy | mean weighted delay (s) | regret vs oracle_w (s) | failures | fallback rate |
|---|---|---|---|---|---|---|
| 50 | two_bays | learned | 37.1 ± 3.4 | +3.9 | 0 | 35% |
| 50 | single_bay | learned | 53.9 ± 5.5 | +13.6 | 0 | 89% |
| 200 | two_bays | learned | 36.0 ± 3.4 | +2.8 | 0 | 8% |
| 200 | single_bay | learned | 55.0 ± 5.6 | +14.7 | 0 | 83% |
| 800 | two_bays | fixed_priority | 42.5 ± 4.0 | +9.2 | 0 |  |
| 800 | two_bays | rules_default | 35.7 ± 3.3 | +2.5 | 0 |  |
| 800 | two_bays | cost_bid | 33.6 ± 2.9 | +0.4 | 0 |  |
| 800 | two_bays | learned | 35.8 ± 3.3 | +2.6 | 0 | 1% |
| 800 | two_bays | oracle_w | 33.3 ± 2.8 | +0.0 | 0 |  |
| 800 | single_bay | fixed_priority | 52.6 ± 5.3 | +12.3 | 0 |  |
| 800 | single_bay | rules_default | 46.6 ± 4.8 | +6.3 | 0 |  |
| 800 | single_bay | cost_bid | 41.1 ± 3.9 | +0.7 | 0 |  |
| 800 | single_bay | learned | 53.5 ± 6.0 | +13.1 | 0 | 15% |
| 800 | single_bay | oracle_w | 40.3 ± 3.8 | +0.0 | 0 |  |

Table states: 93; training samples with a decision: 800/800
