"""Summarise study CSVs -> markdown tables + figures."""
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use('Agg')
import matplotlib.pyplot as plt

D = Path(sys.argv[1]); F = D / 'fig'; F.mkdir(exist_ok=True)
ORDER = ['reactive', 'fixed_priority', 'rules_default', 'rules_proximity', 'cost_bid', 'oracle', 'oracle_w']
from analyse_helpers import ci, fmt, keycols, paired, rate, wilson  # noqa: F401


def table(df, rows, labels):
    out = ['| Policy | ' + ' | '.join(r[0] for r in rows) + ' |', '|---|' + '---|' * len(rows)]
    for lab in labels:
        g = df[df.label == lab]
        if g.empty: continue
        out.append(f'| `{lab}` | ' + ' | '.join(r[1](g) for r in rows) + ' |')
    return '\n'.join(out)
md = []
def H(t): md.append('\n## ' + t + '\n')

# ---------- S1
s1 = pd.read_csv(D / 'S1_baseline.csv'); p1 = paired(s1)
labs = [l for l in ORDER if l in set(s1.label)]
H('S1 — Baseline comparison (single bay; bay x ∈ 1…7 m; B start delay U[0, 8] s; 60 seeds × 7 bay positions)')
ok = lambda g: g[g.success]
md.append(table(p1, [
    ('success', lambda g: rate(g.success)), ('deadlock', lambda g: rate(g.deadlock)), ('collision', lambda g: rate(g.collision)),
    ('total delay [s]', lambda g: fmt(ok(g).total_delay.mean(), ci(ok(g).total_delay))),
    ('regret vs oracle [s]', lambda g: fmt(ok(g).regret.mean(), ci(ok(g).regret))),
    ('same yielder as oracle', lambda g: f"{100*(g.yielder == g.ref_yielder).mean():.0f}%"),
    ('makespan [s]', lambda g: fmt(ok(g).makespan.mean(), ci(ok(g).makespan))),
    ('reverse [m]', lambda g: fmt(ok(g).reverse_dist.mean(), ci(ok(g).reverse_dist), 2)),
    ('time to decide [s]', lambda g: fmt(g.time_to_decide.mean(), ci(g.time_to_decide), 2) if g.time_to_decide.notna().any() else '—'),
    ('msgs', lambda g: f"{g.msgs.mean():.0f}"),
    ('both yielded', lambda g: rate(g.n_yielders >= 2)),
], labs))
fig, ax = plt.subplots(figsize=(7, 4))
for lab in labs:
    g = ok(p1[p1.label == lab]).groupby('bays.0.x').total_delay.mean(); ax.plot(g.index, g.values, marker='o', label=lab)
ax.set_xlabel('bay position x [m] (A enters at 0, B at 8)'); ax.set_ylabel('mean total delay [s]'); ax.legend(fontsize=7); ax.grid(alpha=.3)
fig.tight_layout(); fig.savefig(F / 'S1_delay_vs_bay.png', dpi=130); plt.close(fig)
md.append('\n![S1](fig/S1_delay_vs_bay.png)\n')
md.append('\nRegret vs. oracle by bay position (mean s, successful episodes):\n')
pv = ok(p1).pivot_table(index='label', columns='bays.0.x', values='regret', aggfunc='mean').reindex([l for l in labs if l not in ('oracle',)])
md.append(pv.round(1).to_markdown())
# fairness
H('S5 — Fairness (from S1): who yields, and Jain index of the two robots\' delays')
md.append(table(s1, [('A yields', lambda g: f"{100*(g.yielder == 'A').mean():.0f}%"), ('B yields', lambda g: f"{100*(g.yielder == 'B').mean():.0f}%"),
    ('Jain(delay_A, delay_B)', lambda g: fmt(g.jain.mean(), ci(g.jain), 2)), ('mean delay A [s]', lambda g: f"{ok(g).delay_A.mean():.1f}"), ('mean delay B [s]', lambda g: f"{ok(g).delay_B.mean():.1f}")], labs))

# ---------- S2
s2 = pd.read_csv(D / 'S2_asymmetry.csv'); p2 = paired(s2, 'oracle_w', 'wdelay')
H('S2 — Asymmetric robots (B: urgency 1|3, loaded no|yes, v_max 0.26|0.13 m/s; bay x ∈ {2,4,6}; 30 seeds)')
md.append('Urgency-weighted delay Σ uᵢ·delayᵢ; regret is against the oracle that minimises the weighted delay (`oracle_w`).\n')
md.append(table(p2, [('success', lambda g: rate(g.success)), ('weighted delay [s]', lambda g: fmt(ok(g).wdelay.mean(), ci(ok(g).wdelay))),
    ('regret vs oracle_w [s]', lambda g: fmt(ok(g).regret.mean(), ci(ok(g).regret))), ('same yielder as oracle_w', lambda g: f"{100*(g.yielder == g.ref_yielder).mean():.0f}%"),
    ('B (urgent/loaded/slow) yields', lambda g: f"{100*(g.yielder == 'B').mean():.0f}%")], labs))
md.append('\nRegret vs. oracle_w by condition of robot B (mean s):\n')
p2['cond'] = ('u' + p2['agents.1.urgency'].astype(str) + (p2['agents.1.loaded'].astype(str).str.lower().map({'true': ' loaded', 'false': ''})) + (p2['agents.1.v_max'].map(lambda v: ' slow' if v < 0.2 else '')))
pv2 = ok(p2).pivot_table(index='label', columns='cond', values='regret', aggfunc='mean').reindex([l for l in labs if l != 'oracle_w'])
md.append(pv2.round(1).to_markdown())

# ---------- S3
s3 = pd.read_csv(D / 'S3_comms.csv')
H('S3 — Communication impairment (loss × latency; jitter 0.02 s; neg_timeout 3 s; 30 seeds)')
for metric, name in [('success', 'success rate'), ('collision', 'collision rate'), ('deadlock', 'deadlock rate')]:
    md.append(f'\n**{name} [%]**\n')
    for lab in [l for l in ORDER if l in set(s3.label)]:
        g = s3[s3.label == lab]; pv = g.pivot_table(index='comms.loss', columns='comms.latency', values=metric, aggfunc='mean') * 100
        md.append(f'\n`{lab}` (rows = loss, cols = latency s)\n\n' + pv.round(0).to_markdown())
md.append('\n**agreement and double-yield rates (all impairment levels pooled)**\n')
md.append(table(s3, [('agreement', lambda g: rate(g.agreement.fillna(False).astype(bool))), ('both yielded', lambda g: rate(g.n_yielders >= 2)),
    ('delay when successful [s]', lambda g: fmt(ok(g).total_delay.mean(), ci(ok(g).total_delay)))], [l for l in ORDER if l in set(s3.label)]))
fig, axs = plt.subplots(1, 3, figsize=(11, 3.4), sharey=True)
for ax, lab in zip(axs, [l for l in ORDER if l in set(s3.label)]):
    g = s3[s3.label == lab]; pv = g.pivot_table(index='comms.loss', columns='comms.latency', values='success', aggfunc='mean')
    im = ax.imshow(pv.values * 100, vmin=0, vmax=100, cmap='RdYlGn', aspect='auto'); ax.set_title(lab, fontsize=9)
    ax.set_xticks(range(len(pv.columns)), pv.columns); ax.set_yticks(range(len(pv.index)), pv.index); ax.set_xlabel('latency [s]')
    for (i, j), v in np.ndenumerate(pv.values * 100): ax.text(j, i, f'{v:.0f}', ha='center', va='center', fontsize=7)
axs[0].set_ylabel('packet loss'); fig.colorbar(im, ax=axs, label='success %'); fig.savefig(F / 'S3_success_heatmap.png', dpi=130, bbox_inches='tight'); plt.close(fig)
md.append('\n![S3](fig/S3_success_heatmap.png)\n')

# ---------- S4
s4 = pd.read_csv(D / 'S4_two_bays.csv'); p4 = paired(s4)
H('S4 — Two bays (bay0 x ∈ {2,3,4}, bay1 x ∈ {6,7,8}, bay1 side ±1; B start delay U[0,10] s; 20 seeds)')
md.append(table(p4, [('success', lambda g: rate(g.success)), ('total delay [s]', lambda g: fmt(ok(g).total_delay.mean(), ci(ok(g).total_delay))),
    ('regret vs oracle [s]', lambda g: fmt(ok(g).regret.mean(), ci(ok(g).regret))), ('same yielder as oracle', lambda g: f"{100*(g.yielder == g.ref_yielder).mean():.0f}%"),
    ('refuge used', lambda g: ', '.join(f"{k}:{v}" for k, v in g.refuge.value_counts().items()))], [l for l in ORDER if l in set(s4.label)]))

# ---------- S6
s6 = pd.read_csv(D / 'S6_misreport.csv'); p6 = paired(s6)
H('S6 — Strategic misreporting in cost bidding (B multiplies its yield-cost bid by k; bay x ∈ {2,4,6}; 60 seeds)')
l6 = [l for l in s6.label.unique() if l != 'oracle'] + ['oracle']
md.append(table(p6, [('success', lambda g: rate(g.success)), ('B yields', lambda g: f"{100*(g.yielder == 'B').mean():.0f}%"),
    ("B's delay [s]", lambda g: fmt(ok(g).delay_B.mean(), ci(ok(g).delay_B))), ("A's delay [s]", lambda g: fmt(ok(g).delay_A.mean(), ci(ok(g).delay_A))),
    ('total delay [s]', lambda g: fmt(ok(g).total_delay.mean(), ci(ok(g).total_delay))), ('regret vs oracle [s]', lambda g: fmt(ok(g).regret.mean(), ci(ok(g).regret)))], l6))
(D / 'results.md').write_text('\n'.join(md) + '\n')
print('\n'.join(md))
