# S9 revisited: Clarke-pivot payments

Reviewers of the draft paper (#18) pointed out that the S9 payment rule was not Clarke pivot. That rule had the
proceeder pay the yielder's reported bid. Under it, truthful reporting is not optimal: a robot gains by
under-reporting. This study replaces it with the real mechanism and tests it on a much wider set of misreports.

## Mechanism (`amr_negotiation/mechanism.py`, policy `clarke`)

- **Outcomes:** o ∈ {A yields, B yields}.
- **Type:** robot i's private type is its own predicted urgency-weighted delay in each outcome, c_i(o) = u_i·d_i(o),
  from the planner's motion model. Each robot reports r_i(o). In the simulation, both robots compute the mechanism
  locally from the exchanged reports. A misreport is modelled as r_i = k·c_i.
- **Allocation:** o* = argmin_o Σ_i r_i(o). Ties go to "B yields", as in `cost_bid`.
- **Payment:** p_i = Σ_{j≠i} r_j(o*) − min_o Σ_{j≠i} r_j(o) ≥ 0, paid to a bank. With two robots and two outcomes
  this is a second-price auction on the cost difference.
- **Equivalence:** with truthful reports, the allocation equals the corrected `cost_bid` (#19).

**Guarantees and limits:**
- **What is truthful:** truthful reporting is a dominant strategy *with respect to the predicted costs*. Realized
  delays differ from the prediction, so the ex-post utility can still move slightly under a misreport.
- **Budget:** the mechanism never runs a deficit, but it is not budget balanced. By Green–Laffont, no efficient,
  dominant-strategy-truthful mechanism can be budget balanced in general.
- **Collusion:** a joint misreport by both robots leaves the allocation unchanged and scales both payments down, so
  colluding pays.

## Study (`experiments/classical/run_studies_r2.py S9_payments`, `experiments/analysis/analyse_payments.py`)

- **Grid:** single-bay corridor; bay x ∈ {2, 4, 6} m; B starts U[0, 8] s late; B's urgency is 1 or 3; 60 seeds.
- **Misreports:** A, B, or both report k × their true costs, for k ∈ {0.25, 0.5, 0.75, 0.9, 1.1, 1.25, 1.5, 2, 4}.
- **Outcome:** 10,080 episodes, all successful, 0 collisions.
- **Raw data:** `data/raw/classical/S9_payments.csv.gz`. Full tables: `data/tables/classical_r2/payments.md`.

Gain = the misreporting robot's utility minus its utility in the same encounter when it reports truthfully. Units
are seconds of urgency-weighted delay, mean ± 95% CI.

| Misreport | No transfers | Previous S9 rule | Clarke, predicted | Clarke, realized |
|---|---|---|---|---|
| A ×0.25 | −2.35 ± 0.54 | **+7.54 ± 1.76** | −1.47 ± 0.34 | −2.06 ± 0.48 |
| A ×2 | **+3.98 ± 0.96** | −3.36 ± 0.74 | −2.04 ± 0.52 | −1.59 ± 0.44 |
| A ×4 | **+4.74 ± 0.99** | −9.68 ± 1.96 | −3.99 ± 1.10 | −3.33 ± 1.04 |
| B ×0.75 | −0.72 ± 0.45 | **+0.68 ± 0.24** | −0.14 ± 0.10 | −0.25 ± 0.14 |
| B ×4 | **+0.88 ± 0.20** | −42.98 ± 8.58 | −1.47 ± 0.34 | −0.85 ± 0.20 |
| A and B ×0.5 (joint) | 0 | **+14.35 ± 0.76** | **+4.94 ± 0.55** | **+4.94 ± 0.55** |

**Findings:**
- **Without transfers:** inflating your own cost pays. A gains up to +4.7 s and B +0.9 s.
- **Previous S9 rule:** under-reporting pays (A +7.5 s at ×0.25, B +0.7 s at ×0.75). This confirms the reviewer's
  finding: the earlier claim that truthful reporting was best was wrong.
- **Clarke pivot, predicted costs:** no unilateral misreport is profitable in any tested encounter (share with gain
  > 0.01 s: 0% in every cell).
- **Clarke pivot, realized delays:** the gain is at most +0.02 ± 0.02 s (A ×1.1), i.e. noise from model error.
- **Efficiency:** every misreport that changes the yielder raises the true total cost, by up to 4 s per encounter.
- **Budget:** with truthful reports the bank collects 9.3 ± 1.6 s per encounter when u_B = 1 (44% of total delay)
  and 10.5 ± 1.5 s when u_B = 3 (29%).
- **Participation:** relative to fixed priority without transfers, where B always yields, A is worse off under Clarke
  pivot in every encounter. Fixed priority always favours A, so a mechanism that charges A or makes it yield cannot
  be individually rational against that baseline.
- **Collusion:** a joint ×0.5 shading by both robots saves them 4.9 s of payments with the same allocation.
  Payments to an outside bank therefore need a trusted fleet manager, not peer-to-peer settlement.
