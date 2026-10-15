## All current-code Gazebo runs (460)

| kind             | policy            |   n |   Gazebo success |   collisions |   2D success |   same first yielder |   delay Gazebo [s] |   delay 2D [s] |   Gazebo − 2D [s] |
|:-----------------|:------------------|----:|-----------------:|-------------:|-------------:|---------------------:|-------------------:|---------------:|------------------:|
| S1               | clarke            |  10 |               10 |            0 |           10 |                   10 |               29.0 |           29.3 |              -0.3 |
| S1               | forced_A          |  10 |               10 |            0 |           10 |                   10 |               32.4 |           32.8 |              -0.4 |
| S1               | forced_B          |  10 |               10 |            0 |           10 |                   10 |               36.5 |           36.9 |              -0.4 |
| S1               | learned           |  10 |               10 |            0 |           10 |                   10 |               34.2 |           34.6 |              -0.4 |
| S1               | reservation       |  10 |               10 |            0 |           10 |                   10 |               44.2 |           44.6 |              -0.4 |
| S2_slow          | cost_bid          |   6 |                6 |            0 |            6 |                    6 |               37.6 |           37.7 |              -0.0 |
| S2_slow          | fixed_priority    |   6 |                6 |            0 |            6 |                    6 |               39.7 |           40.4 |              -0.7 |
| S2_slow          | forced_A          |   6 |                6 |            0 |            6 |                    6 |               49.3 |           48.9 |               0.4 |
| S2_slow          | forced_B          |   6 |                6 |            0 |            6 |                    6 |               39.9 |           40.4 |              -0.6 |
| S2_slow          | rules_default     |   6 |                6 |            0 |            6 |                    6 |               39.9 |           40.4 |              -0.6 |
| S2_urgent        | cost_bid          |   6 |                6 |            0 |            6 |                    6 |               39.6 |           40.0 |              -0.5 |
| S2_urgent        | fixed_priority    |   6 |                6 |            0 |            6 |                    6 |               89.5 |           90.9 |              -1.4 |
| S2_urgent        | forced_A          |   6 |                6 |            0 |            6 |                    6 |               41.1 |           41.5 |              -0.4 |
| S2_urgent        | forced_B          |   6 |                6 |            0 |            6 |                    6 |               89.4 |           90.9 |              -1.5 |
| S2_urgent        | rules_default     |   6 |                6 |            0 |            6 |                    6 |               41.1 |           41.5 |              -0.4 |
| S4               | cost_bid          |   6 |                6 |            0 |            6 |                    6 |               21.9 |           22.1 |              -0.2 |
| S4               | fixed_priority    |   6 |                6 |            0 |            6 |                    6 |               22.0 |           22.1 |              -0.2 |
| S4               | rules_default     |   6 |                6 |            0 |            6 |                    6 |               22.0 |           22.1 |              -0.2 |
| S4_same_side     | cost_bid          |   4 |                4 |            0 |            4 |                    4 |               23.3 |           23.5 |              -0.2 |
| S4_same_side     | fixed_priority    |   4 |                4 |            0 |            4 |                    4 |               23.3 |           23.5 |              -0.1 |
| S4_same_side     | rules_default     |   4 |                4 |            0 |            4 |                    4 |               23.2 |           23.5 |              -0.3 |
| S7               | cost_bid_sigma0.5 |   6 |                6 |            0 |            6 |                    4 |               31.5 |           30.2 |               1.3 |
| S7               | cost_bid_sigma1.0 |   6 |                6 |            0 |            6 |                    3 |               33.4 |           30.2 |               3.2 |
| S8b              | cost_bid          |   6 |                6 |            0 |            6 |                    4 |               77.2 |           80.1 |              -2.9 |
| S8b              | fixed_priority    |   6 |                6 |            0 |            6 |                    5 |               93.3 |           84.4 |               8.9 |
| S8c_all_off      | cost_bid          |   6 |                6 |            0 |            6 |                    5 |               73.7 |           62.4 |              11.3 |
| S8c_all_off      | fixed_priority    |   6 |                6 |            0 |            6 |                    4 |               84.9 |           82.8 |               2.2 |
| S9               | clarke_ABx0.5     |   6 |                6 |            0 |            6 |                    6 |               27.1 |           27.5 |              -0.4 |
| S9               | clarke_Ax0.5      |   6 |                6 |            0 |            6 |                    6 |               27.4 |           27.8 |              -0.4 |
| S9               | clarke_Bx0.5      |   6 |                6 |            0 |            6 |                    6 |               30.4 |           30.7 |              -0.3 |
| asym_own         | cost_bid          |   6 |                6 |            0 |            6 |                    6 |               30.5 |           30.9 |              -0.4 |
| asym_own         | fixed_priority    |   6 |                6 |            0 |            6 |                    6 |               50.3 |           50.7 |              -0.5 |
| asym_share       | cost_bid          |   6 |                6 |            0 |            6 |                    6 |               21.9 |           22.1 |              -0.2 |
| asym_share       | fixed_priority    |   6 |                6 |            0 |            6 |                    6 |               21.9 |           22.1 |              -0.2 |
| comms            | cost_bid          |   6 |                6 |            0 |            6 |                    6 |               26.1 |           26.8 |              -0.7 |
| comms            | fixed_priority    |   6 |                6 |            0 |            6 |                    6 |               30.9 |           31.7 |              -0.8 |
| comms            | rules_default     |   6 |                6 |            0 |            6 |                    6 |               30.8 |           31.7 |              -0.9 |
| convoy           | cost_bid          |   6 |                6 |            0 |            6 |                    6 |               29.3 |           29.6 |              -0.3 |
| convoy           | fixed_priority    |   6 |                6 |            0 |            6 |                    6 |               29.4 |           29.6 |              -0.3 |
| convoy           | group_bid         |   6 |                6 |            0 |            6 |                    6 |               29.3 |           29.6 |              -0.3 |
| convoy           | rules_default     |   6 |                6 |            0 |            6 |                    6 |               29.4 |           29.6 |              -0.2 |
| convoy_B_urgent  | fixed_priority    |   6 |                6 |            0 |            6 |                    6 |               86.7 |           87.9 |              -1.2 |
| convoy_B_urgent  | group_bid         |   6 |                6 |            0 |            6 |                    6 |               86.7 |           87.9 |              -1.1 |
| corridor         | cost_bid          |  10 |               10 |            0 |           10 |                   10 |               28.9 |           29.3 |              -0.4 |
| corridor         | fixed_priority    |  10 |               10 |            0 |           10 |                   10 |               36.5 |           36.9 |              -0.4 |
| corridor         | reactive          |  10 |                9 |            1 |           10 |                    5 |              109.6 |          110.0 |              -1.5 |
| corridor         | rules_default     |  10 |               10 |            0 |           10 |                   10 |               36.5 |           36.9 |              -0.4 |
| corridor         | rules_proximity   |  10 |               10 |            0 |           10 |                   10 |               33.2 |           33.6 |              -0.4 |
| explore_all_3.5  | cost_bid          |   6 |                6 |            0 |            6 |                    6 |               21.9 |           22.1 |              -0.2 |
| explore_all_3.5  | fixed_priority    |   6 |                6 |            0 |            6 |                    6 |               21.9 |           22.1 |              -0.2 |
| explore_all_6.0  | cost_bid          |   6 |                6 |            0 |            6 |                    6 |               21.9 |           22.1 |              -0.2 |
| explore_all_6.0  | fixed_priority    |   6 |                6 |            0 |            6 |                    6 |               22.0 |           22.1 |              -0.1 |
| explore_det_3.5  | cost_bid          |   6 |                6 |            0 |            6 |                    5 |               22.2 |           22.1 |               0.1 |
| explore_det_3.5  | fixed_priority    |   6 |                6 |            0 |            6 |                    6 |               28.9 |           22.1 |               6.8 |
| explore_det_6.0  | cost_bid          |   6 |                6 |            0 |            6 |                    6 |               30.6 |           30.9 |              -0.3 |
| explore_det_6.0  | fixed_priority    |   6 |                6 |            0 |            6 |                    6 |               50.3 |           50.7 |              -0.4 |
| explore_full_3.5 | cost_bid          |   6 |                6 |            0 |            6 |                    6 |               21.9 |           22.1 |              -0.2 |
| explore_full_3.5 | fixed_priority    |   6 |                6 |            0 |            6 |                    6 |               21.9 |           22.1 |              -0.2 |
| explore_none_3.5 | cost_bid          |   6 |                6 |            0 |            6 |                    6 |               22.1 |           22.4 |              -0.2 |
| explore_none_3.5 | fixed_priority    |   6 |                6 |            0 |            6 |                    6 |               28.7 |           29.4 |              -0.7 |
| explore_none_6.0 | cost_bid          |   6 |                6 |            0 |            6 |                    6 |               30.6 |           30.9 |              -0.4 |
| explore_none_6.0 | fixed_priority    |   6 |                6 |            0 |            6 |                    6 |               50.3 |           50.7 |              -0.4 |
| tj               | cost_bid          |   6 |                6 |            0 |            6 |                    6 |               47.4 |           91.5 |             -44.1 |
| tj               | fixed_priority    |   6 |                6 |            0 |            6 |                    6 |               93.0 |           89.9 |               3.1 |
| tj               | rules_default     |   6 |                6 |            0 |            6 |                    6 |               84.6 |           87.0 |              -2.3 |
| tjgoal           | cost_bid          |   6 |                6 |            0 |            6 |                    6 |               41.7 |           52.7 |             -11.0 |
| tjgoal           | fixed_priority    |   6 |                6 |            0 |            6 |                    5 |               54.0 |           77.1 |             -23.1 |
| tjgoal           | rules_default     |   6 |                6 |            0 |            6 |                    6 |               53.7 |           77.1 |             -23.5 |
| wrong_map        | cost_bid          |   6 |                6 |            0 |            6 |                    6 |               66.8 |           67.9 |              -1.1 |
| wrong_map        | fixed_priority    |   6 |                6 |            0 |            6 |                    6 |               66.7 |           67.9 |              -1.2 |
| wrong_map        | rules_default     |   6 |                6 |            0 |            6 |                    6 |               66.6 |           67.9 |              -1.3 |

All policies except reactive (negotiating and forced yielders): 0 collisions and 0 failures in 450 Gazebo runs.

## Excess delay over the best forced yielder of the same simulator

| set      | policy          |   n |   Gazebo [s] |   2D [s] |
|:---------|:----------------|----:|-------------:|---------:|
| corridor | clarke          |  10 |         -0.0 |      0.0 |
| corridor | cost_bid        |  10 |         -0.1 |      0.0 |
| corridor | fixed_priority  |  10 |          7.5 |      7.6 |
| corridor | learned         |  10 |          5.1 |      5.3 |
| corridor | reactive        |  10 |         80.1 |     80.7 |
| corridor | reservation     |  10 |         15.2 |     15.2 |
| corridor | rules_default   |  10 |          7.5 |      7.6 |
| corridor | rules_proximity |  10 |          4.2 |      4.3 |
| slow     | cost_bid        |   6 |         -0.0 |      0.0 |
| slow     | fixed_priority  |   6 |          2.1 |      2.8 |
| slow     | rules_default   |   6 |          2.2 |      2.8 |
| urg      | cost_bid        |   6 |          0.0 |      0.0 |
| urg      | fixed_priority  |   6 |         49.9 |     50.9 |
| urg      | rules_default   |   6 |          1.5 |      1.4 |

## Explore mode: map from the peer received before the first decision

| kind             | policy         |   n |   Gazebo |   2D |   detect dist. Gazebo [m] |   detect dist. 2D [m] |   delay Gazebo [s] |   delay 2D [s] |
|:-----------------|:---------------|----:|---------:|-----:|--------------------------:|----------------------:|-------------------:|---------------:|
| explore_all_3.5  | cost_bid       |   6 |        6 |    6 |                       2.6 |                   3.4 |               21.9 |           22.1 |
| explore_all_3.5  | fixed_priority |   6 |        6 |    6 |                       2.6 |                   3.4 |               21.9 |           22.1 |
| explore_all_6.0  | cost_bid       |   6 |        6 |    6 |                       2.6 |                   3.4 |               21.9 |           22.1 |
| explore_all_6.0  | fixed_priority |   6 |        6 |    6 |                       2.6 |                   3.4 |               22.0 |           22.1 |
| explore_det_3.5  | cost_bid       |   6 |        0 |    6 |                       2.6 |                   3.4 |               22.2 |           22.1 |
| explore_det_3.5  | fixed_priority |   6 |        0 |    6 |                       2.3 |                   3.4 |               28.9 |           22.1 |
| explore_det_6.0  | cost_bid       |   6 |        0 |    0 |                       1.5 |                   3.5 |               30.6 |           30.9 |
| explore_det_6.0  | fixed_priority |   6 |        0 |    0 |                       1.7 |                   3.5 |               50.3 |           50.7 |
| explore_full_3.5 | cost_bid       |   6 |        0 |    0 |                       2.6 |                   3.4 |               21.9 |           22.1 |
| explore_full_3.5 | fixed_priority |   6 |        0 |    0 |                       2.6 |                   3.4 |               21.9 |           22.1 |
| explore_none_3.5 | cost_bid       |   6 |        0 |    0 |                       2.6 |                   3.4 |               22.1 |           22.4 |
| explore_none_3.5 | fixed_priority |   6 |        0 |    0 |                       2.3 |                   3.4 |               28.7 |           29.4 |
| explore_none_6.0 | cost_bid       |   6 |        0 |    0 |                       1.5 |                   3.5 |               30.6 |           30.9 |
| explore_none_6.0 | fixed_priority |   6 |        0 |    0 |                       1.7 |                   3.5 |               50.3 |           50.7 |
