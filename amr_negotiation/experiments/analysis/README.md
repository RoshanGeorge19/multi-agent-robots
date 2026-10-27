[↑ Project hierarchy](../../PROJECT_HIERARCHY.md) · [Parent: experiments](../README.md)

# `experiments/analysis/`: raw results → tables and figures

| Script | Input | Output |
|---|---|---|
| `analyse.py OUT` | `OUT/S1_baseline.csv` … `S6_misreport.csv` (from `run_studies.py`) | `OUT/results.md`, `OUT/fig/S1_delay_vs_bay.png`, `S3_success_heatmap.png` |
| `analyse_r2.py OUT` | `OUT/S7_*.csv` … `S10_*.csv` (from `run_studies_r2.py`) | `OUT/results_r2.md`, `OUT/fig/S7_regret_vs_noise.png`, `S8_cost_bid_success.png` |
| `analyse_payments.py OUT` | `OUT/S9_payments.csv` | `OUT/payments.md` (also embedded in `results_r2.md`) |
| `analyse_protocol.py [DATA]` | `data/raw/classical/S8c_protocol_ablation.csv.gz` | `data/tables/classical/protocol_ablation.md` |
| `analyse_helpers.py` | — | Shared statistics: 95% CI of a mean, Wilson interval, formatting, pairing each policy against the best forced yielder on the same draw |

The released copies of these outputs are in [`data/tables/classical/`](../../data/tables/classical/README.md) and
[`data/tables/classical_r2/`](../../data/tables/classical_r2/README.md).

`analyse.py` and `analyse_r2.py` read **uncompressed** CSVs. To re-analyse the released data:

```bash
mkdir -p results && for f in data/raw/classical/S*.csv.gz; do gunzip -c "$f" > results/$(basename "$f" .gz); done
python experiments/analysis/analyse.py results
```

`experiments/classical/reservation_baseline.py` and `papers/paper1_ral/make_figures.py` also import
`analyse_helpers.py`.
