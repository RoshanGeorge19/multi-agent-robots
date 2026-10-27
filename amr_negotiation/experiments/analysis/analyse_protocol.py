"""S8c protocol ablation: data/raw/classical/S8c_protocol_ablation.csv.gz -> data/tables/classical/protocol_ablation.md."""
import sys
from pathlib import Path

import pandas as pd
from analyse_helpers import wilson

D = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / 'data'
d = pd.read_csv(D / 'raw' / 'classical' / 'S8c_protocol_ablation.csv.gz')
d[['policy', 'arm']] = d.label.str.split('|', expand=True)
rows = [('| Policy | commit | state guard | bay check | n | success [95% CI] | deadlocks | collisions (95% upper) '
         '| delay, successes (s) | both started yielding |'), '|---|---|---|---|---|---|---|---|---|---|']
for (pol, arm), g in d.groupby(['policy', 'arm'], sort=False):
    f = dict(kv.split('=') for kv in arm.split(','))
    n, s, c = len(g), int(g.success.sum()), int(g.collision.sum())
    lo, hi = wilson(s, n); chi = wilson(c, n)[1]
    ok = g[g.success.astype(bool)].total_delay
    rows.append(f"| `{pol}` | {f['commit']} | {f['state']} | {f['bay']} | {n} | {100 * s / n:.1f}% [{100 * lo:.1f}–{100 * hi:.1f}] "
                f"| {int(g.deadlock.sum())} | {c} ({100 * chi:.2f}%) | {ok.mean():.1f} ± {1.96 * ok.sem():.1f} | {100 * (g.n_yields >= 2).mean():.1f}% |")
keys = ['policy', 'seed'] + [c for c in d.columns if c.split('.')[0] in ('agent_params', 'comms', 'robot', 'agents')]
d['other'] = d.arm.str.replace(r',bay=\d', '', regex=True)
on = d[d.arm.str.endswith('bay=1')].set_index(keys + ['other']).sort_index()
off = d[d.arm.str.endswith('bay=0')].set_index(keys + ['other']).sort_index()
inert = bool(on.index.equals(off.index) and (on.success.values == off.success.values).all()
             and on.total_delay.fillna(-1).equals(off.total_delay.fillna(-1)))
md = ['# S8c protocol ablation', '',
      ('Extreme comms grid of S8b (loss 0.9/0.97/0.99, latency 2/4/8 s, detect range 1.5/6 m, v_max 0.5 m/s, '
      'B start delay U[0, 8] s, 20 seeds per cell). commit = wait for the peer\'s decision; state guard = STATE-message '
      'rules that detect both robots yielding (same refuge / to each other); bay check = lidar-occupied bays count as taken. '
      'Delays are means over successful episodes (± 95% CI half-width).'), ''] + rows + ['',
      f'Bay-check arms are episode-for-episode identical to the arms without it: {inert}.']
(D / 'tables' / 'classical' / 'protocol_ablation.md').write_text('\n'.join(md) + '\n')
print('\n'.join(md))
