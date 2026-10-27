# Data

```
data/
  raw/                     source of truth: one row per episode (or per run / encounter)
    README.md              file-by-file provenance: episodes, seeds, code commit, command, conventions
    classical/             2D studies: S1–S10, S8c, reservation, explore (*.csv.gz)
    gazebo/                Gazebo result JSONs: gazebo_current (460 runs), gazebo_hold (36 runs) (*.jsonl.gz)
    llm/<tag>/             LLM study: rows.jsonl (per episode, incl. answers and reasoning) + meta.json; stage*.log run logs
  tables/                  generated from raw/ by experiments/ (do not edit by hand)
    classical/             round 1 tables + figures (results.md, fig/), and the convoy, T-junction, maps, explore, learned, reservation and protocol-ablation tables
    classical_r2/          round 2 tables + figures (results_r2.md, payments.md, fig/)
    gazebo/                per-run Gazebo-vs-2D CSVs, gazebo_all.md summary, S1 sweep JSON
    llm/                   llm_<tag>.md, one table per LLM run
```

**Conventions** (details in `raw/README.md`):
- *Success*: every robot reaches its goal within 180 s with no collision.
- *Deadlock*: a timeout without a collision.
- *Collision*: the body rectangles overlap.
- Delays are averaged over successful episodes only.
- Excess delay is paired per encounter against the best forced yielder.
- Rates carry Wilson 95% intervals.

**Which numbers are canonical?** The papers in `papers/` report the final-code values. `tables/` and `reports/` are
snapshots from when each study ran, and a few differ slightly; see `reports/README.md`.

The LLM run tags are explained in [`../reports/llm/README.md`](../reports/llm/README.md).
