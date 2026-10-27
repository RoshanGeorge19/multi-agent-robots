[↑ Project hierarchy](../../PROJECT_HIERARCHY.md) · [Parent: data](../README.md)

# `data/tables/`: generated summary tables and figures

Everything here is produced from [`data/raw/`](../raw/README.md) by the scripts in
[`experiments/`](../../experiments/README.md). Regenerate these files rather than editing them. They are snapshots from
when each study ran; the canonical final-code numbers are in [`papers/`](../../papers/README.md).

| Folder | Contents | Built by |
|---|---|---|
| [`classical/`](classical/README.md) | Round-1 results (S1–S6) + figures; convoy, T-junction, maps, blocked bays, explore, learned, reservation and protocol-ablation tables | `experiments/analysis/`, `experiments/classical/` |
| [`classical_r2/`](classical_r2/README.md) | Round-2 results (S7–S10) + figures; Clarke payments | `experiments/analysis/analyse_r2.py`, `analyse_payments.py` |
| [`gazebo/`](gazebo/README.md) | Per-run Gazebo-vs-2D CSVs; the 460-run summary; the S1 sweep | `experiments/gazebo/` |
| [`llm/`](llm/README.md) | One `llm_<tag>.md` per LLM run | `experiments/llm/llm_negotiation.py` |
