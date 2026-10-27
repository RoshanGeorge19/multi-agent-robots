[↑ Project hierarchy](../../PROJECT_HIERARCHY.md) · [Parent: configs](../README.md)

# `configs/rulebooks/`: rule orders for the `rule_based` policy

A rulebook is an ordered list. The first rule that tells the two robots apart names the yielder, and the episode
log records which rule fired. Use one with `--rulebook <file>`, or `rulebook:` on a policy in a sweep.

| File | Order |
|---|---|
| `default.yaml` | `no_refuge` → `urgency` (gap ≥ 0.5) → `loaded` → `first_in_corridor` (≥ 1 s apart) → `refuge_behind_within` (2 m) → `lower_id_priority`. Also the fallback for `llm` (unusable answers) and `reservation` (both robots inside). |
| `proximity_first.yaml` | `no_refuge` → `urgency` → `closest_refuge` (tie 0.1 m) → `first_in_corridor` → `lower_id_priority`, i.e. geometry before seniority. In S1 this halves the excess delay (3.1 s vs 6.4 s). |

## Available rules (`amr_negotiation/policies.py: RULES`)

| Rule | The robot that yields |
|---|---|
| `no_refuge` | the one that *has* a feasible refuge, when the other has none |
| `urgency` | the less urgent one, if the urgencies differ by ≥ `threshold` |
| `loaded` | the empty one, when only one is loaded |
| `first_in_corridor` | the one that entered the corridor later (by ≥ `min_gap` s) |
| `refuge_behind_within` | the one with a feasible refuge behind it within `distance` m |
| `closest_refuge` | the one closer to its best refuge (by ≥ `tie` m) |
| `lower_id_priority` | the higher ID (deterministic final tie-break; `fixed_priority` is this rule alone) |
