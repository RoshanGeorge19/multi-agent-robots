"""Convoy (A, C eastbound) vs B: group_bid vs pairwise policies, with B equal / urgent (x3) / loaded. 72 runs per cell."""
import collections
import multiprocessing as mp
from pathlib import Path

from amr_negotiation import sim2d
from amr_negotiation import sweep as SW

ROOT = Path(__file__).resolve().parents[1]
def run(a):
    pol, case, x0, x1, sd, seed, loss = a
    ov = {'bays.0.x': x0, 'bays.1.x': x1, 'agents.2.start_delay': sd, 'comms.loss': loss}
    ov.update({'none': {}, 'B_urgent': {'agents.2.urgency': 3.0}, 'B_loaded': {'agents.2.loaded': 'true'}}[case])
    sc = SW.apply_overrides(SW.load_scenario(str(ROOT / 'scenarios/corridor_convoy.yaml')), SW._overrides(ov))
    p = {'name': pol} if pol != 'rules_default' else {'name': 'rule_based', 'rulebook': str(ROOT / 'rulebooks/default.yaml')}
    r = sim2d.run_episode(sc, p, seed=seed)
    u = {ag.id: ag.urgency for ag in sc.agents}
    wd = sum(u[i] * v['delay'] for i, v in r['agents'].items()) if r['success'] else None
    return (case, pol), r['success'], r['collision'], r.get('total_delay'), wd
if __name__ == '__main__':
    jobs = [(p, c, x0, x1, sd, s, l) for c in ('none', 'B_urgent', 'B_loaded') for p in ('fixed_priority', 'rules_default', 'cost_bid', 'group_bid')
            for x0 in (2.0, 4.0) for x1 in (6.0, 8.0) for sd in (0.0, 4.0, 8.0) for s in range(3) for l in (0.0, 0.5)]
    with mp.Pool(4) as pool: res = pool.map(run, jobs)
    agg = collections.defaultdict(list)
    for k, s, c, td, wd in res: agg[k].append((s, c, td, wd))
    for k in sorted(agg):
        v = agg[k]; ok = [x for x in v if x[0]]
        print(k, 'n', len(v), 'succ', len(ok), 'coll', sum(x[1] for x in v),
              'delay', round(sum(x[2] for x in ok) / len(ok), 1), 'urg-w delay', round(sum(x[3] for x in ok) / len(ok), 1))
