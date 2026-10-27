[↑ Project hierarchy](../../../PROJECT_HIERARCHY.md) · [Parent: data/raw](../README.md)

# `data/raw/llm/`: LLM/VLM negotiator runs (paper 2)

The folder holds one subfolder per run tag (about 55) and the original batch logs (`stage*.log`).
[`reports/llm/README.md`](../../../reports/llm/README.md) explains what each tag means: stage, model and settings.

```
<tag>/
  rows.jsonl    one line per (policy arm, encounter)
  meta.json     run settings: model, server, n, layouts, variants, think mode, max_tokens, JSON constraint, seed0, wall time
  cache.jsonl   prompt/response cache (git-ignored; created when a run executes)
```

## `rows.jsonl` fields

| Field | Meaning |
|---|---|
| `label` | Policy arm: `forced_A`, `forced_B`, `fixed_priority`, `rules_default`, `cost_bid`, or an LLM variant such as `llm_med_plans` |
| `layout`, `seed` | Encounter (`single_bay` / `two_bays`; seeds from 100000, identical across runs) |
| `success`, `collision`, `deadlock`, `makespan` | Episode outcome |
| `wdelay`, `excess` | Urgency-weighted delay, and its excess over the best forced yielder |
| `yielder`, `best_yielder`, `forced_gap` | Chosen yielder, reference yielder, and the gap between the two forced outcomes (< 0.5 s counts as a tie) |
| `rule`, `fallback` | Decision rule; the reason the rulebook decided instead of the LLM (e.g. `disagree`), or empty if the LLM's answer was used |
| `think_time`, `llm_error` | Charged decision time; server or parse error |
| `llm_answers` | The model's raw answers, including the reasoning trace where recorded |

Per-run summary tables: [`data/tables/llm/`](../../tables/llm/README.md). Producing script:
[`experiments/llm/llm_negotiation.py`](../../../experiments/llm/README.md). Figures:
`papers/paper2_tase/make_figures.py` reads these files directly.
