[↑ Project hierarchy](../../../PROJECT_HIERARCHY.md) · [Parent: data/raw](../README.md)

# `data/raw/classical/`: 2D-study results, one row per episode

Gzipped CSVs, readable directly with `pandas.read_csv(path)`. The episode counts, seeds, code commit and the exact
command for each file are in [`data/raw/README.md`](../README.md).

| File | Study | Rows |
|---|---|---|
| `S1_baseline.csv.gz` | single bay, bay x 1–7 m, all policies | 2,940 |
| `S2_asymmetry.csv.gz` | urgency / payload / speed asymmetry | 5,040 |
| `S3_comms.csv.gz` | packet loss × latency | 3,600 |
| `S4_two_bays.csv.gz` | two-bay layouts | 2,520 |
| `S6_misreport.csv.gz` | B scales its `cost_bid` bid by k | 1,080 |
| `S7_noisy_bids.csv.gz` | log-normal bid noise σ | 3,150 |
| `S8_comms_stress.csv.gz` | detection range × speed × loss × latency | 4,320 |
| `S8b_comms_extreme.csv.gz` | 90–99% loss, 2–8 s latency | 1,440 |
| `S8c_protocol_ablation.csv.gz` | S8b grid × safeguards on/off | 5,760 |
| `S9_payments.csv.gz` | Clarke pivot under misreports | 10,080 |
| `S10_repeated.csv.gz` / `S10_encounters.csv.gz` | repeated encounters: per sequence and selection rule / per encounter | 350 / 1,000 |
| `reservation.csv.gz` | reservation baseline vs negotiators | 1,260 |
| `explore_map.csv.gz` | explore mode and map sharing, incl. the hold-for-map arm | 1,800 |

## Columns

- **S1–S8c** (`run_studies*.py`):
  - identity: `study`, `label` (policy arm), `seed`;
  - outcome: `success`, `deadlock`, `collision`, `makespan`;
  - delay: `total_delay`, `max_delay`, `wdelay` (urgency-weighted), `jain`, `reverse_dist`;
  - decision: `yielder`, `n_yielders`, `refuge`, `rule`;
  - protocol: `msgs`, `msgs_dropped`, `time_to_decide`, `agreement`, `n_yields`;
  - safety: `min_clearance`, `wall_hits`;
  - per robot: `delay_A`, `reverse_A`, `delay_B`, `reverse_B`;
  - plus one column per grid factor (e.g. `bays.0.x`, `agents.1.start_delay`). Reference rows have `label` = `oracle` / `oracle_w`.
- **S9:**
  - `who`, `k` (misreport scale), `u_B`, `x`, `sd`, `seed`, outcome and delays;
  - predicted costs `t_<outcome>_<robot>`, reports `r_…`, payments `pay_A` / `pay_B`.
- **S10:** `seq`, `rule`, `total`, `cum_A`, `cum_B`, `jain`, `yields_A`, `yields_B`.

Tables built from these files: [`data/tables/classical/`](../../tables/classical/README.md) and
[`classical_r2/`](../../tables/classical_r2/README.md). Producing scripts:
[`experiments/classical/`](../../../experiments/classical/README.md).
