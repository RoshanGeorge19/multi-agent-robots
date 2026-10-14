"""Summarise round-2 study CSVs (S7-S10) -> results_r2.md + figures."""
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from analyse_helpers import ci, fmt, paired, rate
from analyse_payments import s9_markdown

matplotlib.use('Agg')
import matplotlib.pyplot as plt

D = Path(sys.argv[1]); F = D / 'fig'; F.mkdir(exist_ok=True)
md = []
H = lambda t: md.append('\n## ' + t + '\n')
ok = lambda g: g[g.success.astype(bool)]

# S7 noisy bids
s7 = pd.read_csv(D / 'S7_noisy_bids.csv'); p7 = paired(s7)
H('S7 — Noisy cost estimates in `cost_bid` (bid × exp(σ·N(0,1)); bay x ∈ 1…7 m; 30 seeds)')
rows = ['| σ | cost_bid regret [s] | cost_bid same yielder as oracle | rules_proximity regret [s] | cost_bid success |', '|---|---|---|---|---|']
for sg, g in p7.groupby('bid_sigma'):
    c, r = g[g.label == 'cost_bid'], g[g.label == 'rules_proximity']
    rows.append(f"| {sg} | {fmt(ok(c).regret.mean(), ci(ok(c).regret))} | {100*(c.yielder == c.ref_yielder).mean():.0f}% | {fmt(ok(r).regret.mean(), ci(ok(r).regret))} | {rate(c.success.astype(bool))} |")
md.append('\n'.join(rows))
fig, ax = plt.subplots(figsize=(6, 3.5))
for lab in ['cost_bid', 'rules_proximity']:
    g = ok(p7[p7.label == lab]).groupby('bid_sigma').regret.agg(['mean', ci]); ax.errorbar(g.index, g['mean'], yerr=g['ci'], marker='o', capsize=3, label=lab)
ax.set_xlabel('bid noise σ (log-normal)'); ax.set_ylabel('regret vs oracle [s]'); ax.grid(alpha=.3); ax.legend()
fig.tight_layout(); fig.savefig(F / 'S7_regret_vs_noise.png', dpi=130); plt.close(fig)
md.append('\n![S7](fig/S7_regret_vs_noise.png)\n')

# S8 comms stress
s8 = pd.read_csv(D / 'S8_comms_stress.csv')
H('S8 — Comms stress (conflict-detection range × robot speed × loss × latency; 20 seeds)')
s8['geom'] = 'detect ' + s8['agent_params.detect_range'].astype(str) + ' m, v ' + s8['robot.v_max'].astype(str)
s8['comms'] = 'loss ' + s8['comms.loss'].astype(str) + ', lat ' + s8['comms.latency'].astype(str)
for metric in ['success', 'collision']:
    md.append(f'\n**{metric} rate [%]** (rows: detection range and v_max; columns: loss and latency)\n')
    for lab in ['fixed_priority', 'rules_default', 'rules_proximity', 'cost_bid']:
        g = s8[s8.label == lab]
        pv = (g.pivot_table(index='geom', columns='comms', values=metric, aggfunc='mean') * 100).round(0)
        md.append(f'\n`{lab}`\n\n' + pv.to_markdown())
md.append('\n**pooled over all comms levels**\n')
t = s8.groupby(['label', 'geom']).agg(success=('success', 'mean'), collision=('collision', 'mean'), deadlock=('deadlock', 'mean'), both=('n_yielders', lambda v: (v >= 2).mean())).mul(100).round(1)
md.append(t.to_markdown())
g = s8[s8.label == 'cost_bid']; pv = g.pivot_table(index='geom', columns='comms', values='success', aggfunc='mean') * 100
fig, ax = plt.subplots(figsize=(10, 3.6)); im = ax.imshow(pv.values, vmin=0, vmax=100, cmap='RdYlGn', aspect='auto')
ax.set_xticks(range(len(pv.columns)), pv.columns, rotation=45, ha='right', fontsize=7); ax.set_yticks(range(len(pv.index)), pv.index, fontsize=7)
for (i, j), v in np.ndenumerate(pv.values): ax.text(j, i, f'{v:.0f}', ha='center', va='center', fontsize=7)
ax.set_title('cost_bid success %'); fig.colorbar(im); fig.tight_layout(); fig.savefig(F / 'S8_cost_bid_success.png', dpi=130); plt.close(fig)
md.append('\n![S8](fig/S8_cost_bid_success.png)\n')

# S8b extreme comms
p8b = D / 'S8b_comms_extreme.csv'
if p8b.exists():
    s8b = pd.read_csv(p8b)
    H('S8b — Extreme comms (v_max 0.5 m/s; detection 1.5 | 6 m; loss 0.9–0.99; latency 2–8 s; 20 seeds)')
    t = s8b.groupby(['label', 'agent_params.detect_range', 'comms.loss', 'comms.latency']).agg(
        success=('success', 'mean'), collision=('collision', 'mean'), deadlock=('deadlock', 'mean'),
        both_yielded=('n_yielders', lambda v: (v >= 2).mean())).mul(100).round(0)
    md.append(t.to_markdown())

# S9 payments
H('S9 — Clarke-pivot payments under misreports (bay x ∈ {2,4,6}; u_B ∈ {1,3}; 60 seeds)')
md.extend(s9_markdown(pd.read_csv(D / 'S9_payments.csv')))

# S10 repeated encounters
s10 = pd.read_csv(D / 'S10_repeated.csv')
H('S10 — Repeated encounters (50 sequences × 20 encounters; random bay x ∈ [1,7] m and B delay U[0,8] s)')
md.append('Per-encounter costs come from forced-yielder runs; each rule is then applied to the same encounter sequence. `credit_lλ` yields the robot minimising total delay + λ·(own cumulative delay − other\'s).\n')
cost = s10[s10.rule == 'cost'].set_index('seq').total
rows = ['| Rule | total delay / sequence [s] | extra vs cost-optimal | Jain (cumulative delays) | \\|cum_A − cum_B\\| [s] | A yields / 20 |', '|---|---|---|---|---|---|']
for rule in ['fixed_priority', 'cost', 'alternate', 'credit_l0.25', 'credit_l0.5', 'credit_l1.0', 'credit_l2.0']:
    g = s10[s10.rule == rule].set_index('seq')
    ex = 100 * (g.total / cost - 1); gap = (g.cum_A - g.cum_B).abs()
    rows.append(f"| `{rule}` | {fmt(g.total.mean(), ci(g.total))} | {ex.mean():+.1f}% | {fmt(g.jain.mean(), ci(g.jain), 3)} | {fmt(gap.mean(), ci(gap))} | {g.yields_A.mean():.1f} |")
md.append('\n'.join(rows))
(D / 'results_r2.md').write_text('\n'.join(md) + '\n')
print('\n'.join(md))
