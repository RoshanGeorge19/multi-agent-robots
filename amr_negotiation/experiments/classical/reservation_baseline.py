"""Corridor-reservation baseline vs the negotiating policies, and a stronger reference than the best forced yielder.

    python experiments/classical/reservation_baseline.py [DATA_DIR=data]   # -> raw/classical/reservation.csv.gz + tables/classical/reservation.md

`reservation`: a robot that is still outside the corridor while an oncoming robot is inside parks in its end room
until that robot has passed (first come, first served); if both get in, they fall back to the default rulebook.
References, per encounter (same bay, start delay and seed):
  best forced yielder = min(forced A, forced B)          ("oracle" in the earlier reports)
  best of strategies  = min(forced A, forced B, reservation)
"""
import math
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'analysis'))
from analyse_helpers import ci, fmt, wilson  # noqa: E402

from amr_negotiation import load_scenario, run_episode
from amr_negotiation.cli import apply_overrides, parse_set

ROOT = Path(__file__).resolve().parents[2]
POLICIES = {'reservation': {'name': 'reservation'}, 'fixed_priority': {'name': 'fixed_priority'},
            'rules_default': {'name': 'rule_based'}, 'cost_bid': {'name': 'cost_bid'},
            'forced_A': {'name': 'forced', 'yielder': 'A'}, 'forced_B': {'name': 'forced', 'yielder': 'B'}}
BAYS = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0)
SEEDS = 30


def job(args):
    label, x, seed = args
    sd = round(float(np.random.default_rng(20_000 + seed).uniform(0, 8)), 3)
    sc = apply_overrides(load_scenario(ROOT / 'configs/scenarios/corridor_single_bay.yaml'),
                         parse_set([f'bays.0.x={x}', f'agents.1.start_delay={sd}']))
    r = run_episode(sc, POLICIES[label], seed=seed)
    return {'label': label, 'x': x, 'sd': sd, 'seed': seed, 'success': r['success'], 'collision': r['collision'],
            'deadlock': r['deadlock'], 'total_delay': r.get('total_delay'), 'makespan': r.get('makespan'),
            'yielder': r.get('yielder'), 'rule': r.get('rule'),
            'delay_A': r['agents']['A'].get('delay'), 'delay_B': r['agents']['B'].get('delay')}


def report(df):
    key = ['x', 'seed']
    d = df.assign(cost=np.where(df.success.astype(bool), df.total_delay, math.inf)).pivot_table(
        index=key, columns='label', values='cost')
    d['best_forced'] = d[['forced_A', 'forced_B']].min(axis=1)
    d['best_of_strategies'] = d[['forced_A', 'forced_B', 'reservation']].min(axis=1)
    n = len(d)
    md = [(f'{len(df)} episodes; {n} encounters (bay x ∈ {{1…7}} m × {SEEDS} seeds, B start delay U[0, 8] s per seed). '
          'Delays include every episode (a failure would count as ∞; there are none if every success rate is 100%).\n'),
          ('| Policy | success | collisions | total delay [s] | excess vs best forced yielder [s] | '
          'excess vs best of strategies [s] |'), '|---|---|---|---|---|---|']
    for lab in ['reservation', 'fixed_priority', 'rules_default', 'cost_bid', 'best_forced', 'best_of_strategies']:
        g = df[df.label == lab]
        succ = (f'{100 * g.success.mean():.1f}% [{100 * wilson(int(g.success.sum()), len(g))[0]:.0f}–'
                f'{100 * wilson(int(g.success.sum()), len(g))[1]:.0f}]') if len(g) else '—'
        coll = int(g.collision.sum()) if len(g) else '—'
        e1, e2 = d[lab] - d.best_forced, d[lab] - d.best_of_strategies
        md.append(f'| `{lab}` | {succ} | {coll} | {fmt(d[lab].mean(), ci(d[lab]))} | {fmt(e1.mean(), ci(e1))} | '
                  f'{fmt(e2.mean(), ci(e2))} |')
    better = (d.reservation < d.best_forced - 0.1)
    md.append(f'\n`reservation` beats the best forced yielder by > 0.1 s in {int(better.sum())}/{n} encounters '
              f'({100 * better.mean():.0f}%); mean gain there {(d.best_forced - d.reservation)[better].mean():.1f} s.')
    by_x = (d.reservation - d.best_forced).groupby(level='x').agg(['mean', ci])
    md.append('\nExcess of `reservation` over the best forced yielder by bay position [s]: '
              + ', '.join(f'x={x:g}: {fmt(r["mean"], r["ci"])}' for x, r in by_x.iterrows()))
    return md


if __name__ == '__main__':
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'data'
    jobs = [(lab, x, s) for lab in POLICIES for x in BAYS for s in range(SEEDS)]
    with mp.Pool(8) as pool:
        df = pd.DataFrame(pool.map(job, jobs, chunksize=8))
    (out / 'raw' / 'classical').mkdir(parents=True, exist_ok=True); (out / 'tables' / 'classical').mkdir(parents=True, exist_ok=True)
    df.to_csv(out / 'raw' / 'classical' / 'reservation.csv.gz', index=False)
    md = ['# Corridor-reservation baseline and best-of-strategies reference\n', *report(df)]
    (out / 'tables' / 'classical' / 'reservation.md').write_text('\n'.join(md) + '\n')
    print('\n'.join(md))
