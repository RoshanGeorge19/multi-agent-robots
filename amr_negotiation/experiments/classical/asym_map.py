"""Asymmetric map knowledge: robots know different bay sets (corridor_two_bays). Run from the repo root: python experiments/classical/asym_map.py"""
import collections
import multiprocessing as mp
from pathlib import Path

import numpy as np

from amr_negotiation import sim2d
from amr_negotiation import sweep as SW

ROOT = Path(__file__).resolve().parents[2]

KN={'full':(None,None),'A:bay0':(['bay0'],None),'A:bay1':(['bay1'],None),'B:bay0':(None,['bay0']),
    'A:bay0|B:bay1':(['bay0'],['bay1']),'A:none':([],None),'A:none|B:none':([],[])}
def run(a):
    kn,pol,loss,seed,share=a
    ka,kb=KN[kn]
    ov={'comms.loss':loss,'agents.1.start_delay':float(np.random.default_rng(seed).uniform(0,8))}
    sc=SW.apply_overrides(SW.load_scenario(str(ROOT / 'configs/scenarios/corridor_two_bays.yaml')),SW._overrides(ov))
    sc.agents[0].known_refuges, sc.agents[1].known_refuges = ka, kb
    p={'name':pol} if pol!='rules_default' else {'name':'rule_based','rulebook':str(ROOT / 'configs/rulebooks/default.yaml')}
    if share: p['agent_params']={'share_map':True}
    r=sim2d.run_episode(sc,p,seed=seed,record=True)
    ev=collections.Counter(e['event'] for e in r['events'])
    return a,r['success'],r['deadlock'],r['collision'],r.get('total_delay'),ev['refuge_learned'],ev['decision_mismatch']
if __name__=='__main__':
    jobs=[(k,p,l,s,sh) for k in KN for p in ['fixed_priority','rules_default','cost_bid'] for l in (0.0,0.5) for s in range(10) for sh in (False,True)]
    with mp.Pool(8) as pool: res=pool.map(run,jobs)
    base={(a[1],a[2],a[3],a[4]):td for a,s,d,c,td,_,_ in res if a[0]=='full'}
    agg=collections.defaultdict(list)
    for a,s,d,c,td,lr,mm in res: agg[(a[0],a[1],a[2],'share' if a[4] else 'own')].append((s,d,c,td,td-base[(a[1],a[2],a[3],a[4])],lr,mm))
    print('knowledge policy loss | succ dead coll | mean delay | mean extra vs full | learned mismatch')
    for k,v in agg.items():
        z=np.array(v,dtype=float)
        print(k, '|', int(z[:, 0].sum()), int(z[:, 1].sum()), int(z[:, 2].sum()),
              f'| {z[:, 3].mean():.1f} | {z[:, 4].mean():+.1f} | {int(z[:, 5].sum())} {int(z[:, 6].sum())}')
