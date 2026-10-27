"""S9 payments analysis: Clarke-pivot mechanism under misreports (see experiments/classical/run_studies_r2.py).

    python experiments/analysis/analyse_payments.py results     # -> results/payments.md

Utilities are in seconds of urgency-weighted delay (negative). "Predicted" uses the planner's cost model, under
which Clarke pivot is dominant-strategy truthful; "realized" uses the delays measured in the simulation.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from analyse_helpers import ci, fmt

KEY = ['u_B', 'x', 'seed']


def utilities(df):
    df = df.copy()
    yA = df.yielder == 'A'
    for i in 'AB':
        own = np.where(yA, df[f't_Ay_{i}'], df[f't_By_{i}'])
        urg = 1.0 if i == 'A' else df.u_B
        df[f'pred_none_{i}'] = -own
        df[f'pred_vcg_{i}'] = -own - df[f'pay_{i}']
        df[f'real_vcg_{i}'] = -urg * df[f'delay_{i}'] - df[f'pay_{i}']
        # previous S9 rule: the proceeder pays the reported cost of the chosen outcome to the bank
        rep_total = np.where(yA, df.r_Ay_A + df.r_Ay_B, df.r_By_A + df.r_By_B)
        proceeds = np.where(yA, i == 'B', i == 'A')
        df[f'pred_old_{i}'] = -own - np.where(proceeds, rep_total, 0.0)
        df[f'fp_{i}'] = -df[f't_By_{i}']  # fixed priority: B always yields, no transfers
    df['true_cost'] = np.where(yA, df.t_Ay_A + df.t_Ay_B, df.t_By_A + df.t_By_B)
    df['revenue'] = df.pay_A + df.pay_B
    return df


def s9_markdown(raw):
    df = utilities(raw[raw.success.astype(bool)])
    md = [(f'{len(raw)} episodes, {int(raw.success.sum())} successful, {int(raw.collision.fillna(False).astype(bool).sum())} '
          'collisions. Failed episodes are excluded from the utility tables.\n')]
    truth = df[(df.who == 'A') & (df.k == 1.0)].set_index(KEY)
    # incentive table
    md.append('Gain from misreporting = deviator utility minus its utility in the same encounter with everyone truthful '
              '(mean ± 95% CI; for `AB` the sum over both robots). "Profitable" = share of encounters with gain > 0.01 s.\n')
    hdr = ('| who misreports | k | yielder changed | no transfers, predicted | previous rule, predicted | '
           'Clarke, predicted | Clarke, profitable | Clarke, realized | total cost change [s] |')
    rows = [hdr, '|' + '---|' * 9]
    for (who, k), g in df[df.k != 1.0].groupby(['who', 'k']):
        j = g.set_index(KEY).join(truth, rsuffix='_t', how='inner')
        gain = {m: sum(j[f'{m}_{i}'] - j[f'{m}_{i}_t'] for i in who) for m in ('pred_none', 'pred_old', 'pred_vcg', 'real_vcg')}
        ch = 100 * (j.yielder != j.yielder_t).mean()
        dc = j.true_cost - j.true_cost_t
        rows.append(f"| {who} | {k} | {ch:.0f}% | {fmt(gain['pred_none'].mean(), ci(gain['pred_none']), 2)} | "
                    f"{fmt(gain['pred_old'].mean(), ci(gain['pred_old']), 2)} | {fmt(gain['pred_vcg'].mean(), ci(gain['pred_vcg']), 2)} | "
                    f"{100 * (gain['pred_vcg'] > 0.01).mean():.0f}% | {fmt(gain['real_vcg'].mean(), ci(gain['real_vcg']), 2)} | "
                    f"{fmt(dc.mean(), ci(dc), 2)} |")
    md.append('\n'.join(rows))
    # budget and participation, truthful reports
    md.append('\nTruthful reports, by B\'s urgency. Revenue = Σ payments to the bank (the mechanism never runs a deficit). '
              '"Worse than fixed priority" = share of encounters where the robot\'s predicted utility, payment included, '
              'is below its utility under fixed priority without transfers (B always yields).\n')
    rows = [('| u_B | n | true total cost [s] | revenue [s] | revenue / total cost | max payment [s] | '
            'A worse than fixed priority | B worse than fixed priority |'), '|' + '---|' * 8]
    for u, g in truth.reset_index().groupby('u_B'):
        rows.append(f"| {u:g} | {len(g)} | {fmt(g.true_cost.mean(), ci(g.true_cost))} | {fmt(g.revenue.mean(), ci(g.revenue))} | "
                    f"{100 * g.revenue.sum() / g.true_cost.sum():.0f}% | {g[['pay_A', 'pay_B']].max().max():.1f} | "
                    f"{100 * (g.pred_vcg_A < g.fp_A - 0.01).mean():.0f}% | {100 * (g.pred_vcg_B < g.fp_B - 0.01).mean():.0f}% |")
    md.append('\n'.join(rows))
    return md


if __name__ == '__main__':
    D = Path(sys.argv[1])
    md = ['# S9 — Clarke-pivot payments under misreports (bay x ∈ {2,4,6}; u_B ∈ {1,3}; 60 seeds)\n',
          *s9_markdown(pd.read_csv(D / 'S9_payments.csv'))]
    (D / 'payments.md').write_text('\n'.join(md) + '\n')
    print('\n'.join(md))
