[↑ Project hierarchy](../PROJECT_HIERARCHY.md) · [Repo README](../README.md)

# `docs/`: background and how-tos

| File | Contents |
|---|---|
| `literature_review.md` | *Negotiation and Deadlock Resolution between Autonomous Mobile Robots in Constrained Spaces*. It covers taxonomy, per-theme synthesis (deadlock, AGV traffic rules, MAPF, decentralised avoidance, negotiation protocols, games, learning, LLMs, benchmarks), a comparison of the closest ~20 works, research gaps (§6, which motivates the studies), recommended baselines, metrics, a scenario matrix and venues. Pandoc markdown with `[@key]` citations |
| `references.bib` | Bibliography for the review (126 entries after an integrity check) |
| `llm_experiments.md` | The staged plan for the LLM/VLM study (paper 2): research questions, model roster, stages 0–5, practical notes |
| `llm_local.md` | How to run the `llm` policy against a local llama.cpp `llama-server` (written for a Dell Pro Max GB10): install, start the server, run one episode, run the study |

Related: the LLM scripts are in [`experiments/llm/`](../experiments/llm/README.md), and the run index is in
[`reports/llm/`](../reports/llm/README.md).
