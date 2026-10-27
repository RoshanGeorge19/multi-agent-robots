[↑ Project hierarchy](../PROJECT_HIERARCHY.md) · [Repo README](../README.md)

# `media/`: videos

| Folder | What is available | Code version |
|---|---|---|
| [`2d_sim/`](2d_sim/README.md) | 3 side-by-side 2D-simulator replays (8× speed): the four policies in the single-bay corridor; T-junction and convoy (`cost_bid` vs `group_bid`); a blocked bay | final code (`c99270c`) |
| [`gazebo/`](gazebo/README.md) | 3 early Gazebo clips of the single-bay corridor: `cost_bid`, `rule_based`, `reactive` | initial code (`ba2ca27`) |
| [`gazebo_final/`](gazebo_final/README.md) | 10 Gazebo clips covering corridor, blocked bay, convoy, T-junction (exit, turn-in), noisy bids, Clarke misreport and explore modes. Each has its result JSON and a `.webp` preview | final code (`c99270c`) |

Each folder's README gives the scenario, seed, policy and outcome of every clip. The `.webp` files are animated
previews that play in a browser or on GitHub.
