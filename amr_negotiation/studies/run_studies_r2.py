"""Round-2 studies (S7-S10), building on run_studies.py.

    python studies/run_studies_r2.py studies/results [S7_noisy_bids S8_comms_stress S9_payments S10_repeated]
    python studies/analyse_r2.py studies/results

S7  noisy self-estimates in cost_bid: each robot's bid is multiplied by exp(sigma * N(0,1)).
    The noise is drawn from (episode seed, robot id, conflict time), so both robots see the
    same noisy bid, i.e. each robot reports its own noisy estimate truthfully.
S8  comms stress: shorter conflict-detection range and faster robots x loss x latency.
S9  payments: Clarke-pivot (VCG) mechanism, `policies.decide_clarke`. Robot A, robot B, or both
    (collusion) report k x their true predicted costs, k in K9; B's urgency 1 or 3.
S10 repeated encounters: 20 encounters per sequence between A and B, with random bay position
    and arrival offset. The cost of each robot yielding is measured once per encounter with
    forced-yielder runs; the selection rules (fixed priority, cost, alternation, credit-weighted
    cost) are then compared on the same encounters.
"""
import csv
import math
import multiprocessing as mp
import sys
import zlib
from pathlib import Path

import numpy as np
import run_studies as RS

from amr_negotiation import policies as POL
from amr_negotiation import sim2d

ROOT = RS.ROOT
S = str(ROOT / 'scenarios/corridor_single_bay.yaml')
NOISE = {'sigma': 0.0, 'seed': 0}
_bid = POL.yield_bid


def _noisy_bid(Y, P, sc, objective='total_delay'):
    b = _bid(Y, P, sc, objective)
    if NOISE['sigma'] <= 0 or not math.isfinite(b):
        return b
    h = zlib.crc32(f"{NOISE['seed']}|{Y.id}|{round(Y.t, 1)}".encode())
    return b * math.exp(NOISE['sigma'] * np.random.default_rng(h).standard_normal())


POL.yield_bid = _noisy_bid
PROX = {'name': 'rule_based', 'rulebook': RS.RB['rules_proximity'], 'label': 'rules_proximity'}
DEF = {'name': 'rule_based', 'rulebook': RS.RB['rules_default'], 'label': 'rules_default'}


def job(args):
    study, scen, pol, assign, seed = args
    pol = dict(pol)
    NOISE.update(sigma=float(assign.get('bid_sigma', 0.0)) if pol['name'] == 'cost_bid' else 0.0, seed=seed)
    ap = {k.split('.', 1)[1]: v for k, v in assign.items() if k.startswith('agent_params.')}
    if ap:
        pol['agent_params'] = {**pol.get('agent_params', {}), **ap}
    core = {k: v for k, v in assign.items() if not k.startswith('agent_params.') and k != 'bid_sigma'}
    row = RS.job((study, scen, pol, core, seed))
    row.update(assign)
    return row


K9 = (0.25, 0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 2.0, 4.0)


def job9(args):
    """One Clarke-pivot episode where robot(s) `who` report k x their true predicted costs."""
    who, k, u_b, x, sd, seed = args
    sc = RS.SW.apply_overrides(RS.SW.load_scenario(S), RS.SW._overrides(
        {'bays.0.x': x, 'agents.1.start_delay': sd, 'agents.1.urgency': u_b}))
    r = sim2d.run_episode(sc, {'name': 'clarke', 'report_scale': dict.fromkeys(who, k)}, seed=seed)
    d = next((d for d in r['decisions'] if 'payments' in d), {})
    row = {'who': who, 'k': k, 'u_B': u_b, 'x': x, 'sd': sd, 'seed': seed, 'success': r['success'],
           'collision': r.get('collision'), 'yielder': d.get('yielder'), 'total_delay': r.get('total_delay'),
           'delay_A': r['agents']['A'].get('delay'), 'delay_B': r['agents']['B'].get('delay')}
    for key in ('types', 'reports'):
        for o, v in (d.get(key) or {}).items():
            row.update({f'{key[0]}_{o}y_{i}': c for i, c in v.items()})
    row.update({f'pay_{i}': p for i, p in (d.get('payments') or {}).items()})
    return row


def job10(seq):
    rng = np.random.default_rng(50_000 + seq)
    enc = []
    for e in range(20):
        x, sd = round(float(rng.uniform(1.0, 7.0)), 2), round(float(rng.uniform(0.0, 8.0)), 2)
        sc = RS.SW.apply_overrides(RS.SW.load_scenario(S), RS.SW._overrides({'bays.0.x': x, 'agents.1.start_delay': sd}))
        c = {'seq': seq, 'enc': e, 'x': x, 'sd': sd}
        for y in ('A', 'B'):
            r = sim2d.run_episode(sc, {'name': 'forced', 'yielder': y}, seed=seq * 100 + e)
            ok = r['success']
            c[f'{y}_yields_dA'] = r['agents']['A'].get('delay') if ok else math.inf
            c[f'{y}_yields_dB'] = r['agents']['B'].get('delay') if ok else math.inf
        enc.append(c)
    return enc


def eval10(encs, rule, lam=0.0):
    D = {'A': 0.0, 'B': 0.0}; last = None; n_yield = {'A': 0, 'B': 0}
    for c in encs:
        tot = {y: c[f'{y}_yields_dA'] + c[f'{y}_yields_dB'] for y in 'AB'}
        if rule == 'fixed_priority':
            y = 'B'
        elif rule == 'cost':
            y = min('AB', key=lambda q: tot[q])
        elif rule == 'alternate':
            y = min('AB', key=lambda q: tot[q]) if last is None else ('A' if last == 'B' else 'B')
            if not math.isfinite(tot[y]):
                y = 'A' if y == 'B' else 'B'
        else:  # credit: the robot that has suffered less so far is cheaper to make yield
            y = min('AB', key=lambda q: tot[q] + lam * (D[q] - D['B' if q == 'A' else 'A']))
        D['A'] += c[f'{y}_yields_dA']; D['B'] += c[f'{y}_yields_dB']; last = y; n_yield[y] += 1
    x = [max(0.0, D['A']), max(0.0, D['B'])]
    jain = 1.0 if sum(v * v for v in x) == 0 else sum(x) ** 2 / (2 * sum(v * v for v in x))
    return {'total': D['A'] + D['B'], 'cum_A': D['A'], 'cum_B': D['B'], 'jain': jain, 'yields_A': n_yield['A'], 'yields_B': n_yield['B']}


def write(path, rows):
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(rows)


STUDIES = {
 'S7_noisy_bids': {'scenario': 'scenarios/corridor_single_bay.yaml', 'seeds': 30,
                       'policies': [{'name': 'cost_bid'}, PROX, {'name': 'oracle'}],
                       'grid': {'bid_sigma': [0.0, 0.1, 0.25, 0.5, 1.0], 'bays.0.x': [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]},
                       'random': {'agents.1.start_delay': [0.0, 8.0]}},
 'S8_comms_stress': {'scenario': 'scenarios/corridor_single_bay.yaml', 'seeds': 20,
                         'policies': [{'name': 'fixed_priority'}, DEF, PROX, {'name': 'cost_bid'}],
                         'grid': {'agent_params.detect_range': [6.0, 3.0, 1.5], 'robot.v_max': [0.26, 0.5],
                               'comms.loss': [0.0, 0.5, 0.9], 'comms.latency': [0.05, 0.5, 2.0]},
                         'random': {'agents.1.start_delay': [0.0, 8.0]}},
 'S8c_protocol_ablation': {'scenario': 'scenarios/corridor_single_bay.yaml', 'seeds': 20,
                              'policies': [{'name': n, 'label': f'{n}|{lab}', 'agent_params': ap}
                                           for n in ('fixed_priority', 'cost_bid')
                                           for lab, ap in (('both', {}), ('commit_only', {'bay_check': False}),
                                                           ('bay_check_only', {'commit': False}),
                                                           ('neither', {'commit': False, 'bay_check': False}))],
                              'grid': {'agent_params.detect_range': [1.5, 6.0], 'robot.v_max': [0.5],
                                    'comms.loss': [0.9, 0.97, 0.99], 'comms.latency': [2.0, 4.0, 8.0]},
                              'random': {'agents.1.start_delay': [0.0, 8.0]}},
 'S8b_comms_extreme': {'scenario': 'scenarios/corridor_single_bay.yaml', 'seeds': 20,
                           'policies': [{'name': 'fixed_priority'}, DEF, PROX, {'name': 'cost_bid'}],
                           'grid': {'agent_params.detect_range': [1.5, 6.0], 'robot.v_max': [0.5],
                                 'comms.loss': [0.9, 0.97, 0.99], 'comms.latency': [2.0, 4.0, 8.0]},
                           'random': {'agents.1.start_delay': [0.0, 8.0]}},
}

if __name__ == '__main__':
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    names = sys.argv[2:] or [*STUDIES, 'S9_payments', 'S10_repeated']
    smoke = bool(__import__('os').environ.get('SMOKE'))
    with mp.Pool(8) as pool:
        for n in names:
            if n in STUDIES:
                spec = dict(STUDIES[n], seeds=1 if smoke else STUDIES[n]['seeds'])
                rows = pool.map(job, RS.build(n, spec), chunksize=4)
            elif n == 'S9_payments':
                jobs = []
                for seed in range(3 if smoke else 60):
                    sd = round(float(np.random.default_rng(10_000 + seed).uniform(0, 8)), 3)
                    jobs += [(who, k, u, x, sd, seed) for who in ('A', 'B', 'AB') for k in K9 for u in (1.0, 3.0)
                             for x in (2.0, 4.0, 6.0) if not (k == 1.0 and who != 'A')]
                rows = pool.map(job9, jobs, chunksize=4)
            elif n == 'S10_repeated':
                seqs = pool.map(job10, range(2 if smoke else 50))
                rows = [dict(c) for s in seqs for c in s]
                write(out / 'S10_encounters.csv', rows)
                ev = []
                for s in seqs:
                    for rule, lam in [('fixed_priority', 0), ('cost', 0), ('alternate', 0)] + [('credit', v) for v in (0.25, 0.5, 1.0, 2.0)]:
                        ev.append(dict(seq=s[0]['seq'], rule=rule if rule != 'credit' else f'credit_l{lam}', **eval10(s, rule, lam)))
                rows = ev
            write(out / f'{n}.csv', rows)
            print(n, len(rows), 'rows', flush=True)
