"""Hold-variant Gazebo table: new hold_gz runs + the final-code batch (gazebo_current.jsonl.gz)."""
import gzip
import json
import re
import statistics as st
from pathlib import Path

RAW = Path(__file__).resolve().parents[2] / "data" / "raw" / "gazebo"
B = RAW / "gazebo_current.jsonl.gz"
rows = {}
with gzip.open(B, 'rt') as fh:
    batch_lines = fh.readlines()
for line in batch_lines:
    r = json.loads(line)
    if r['scenario'].startswith(('gz_exp', 'gz_2bay_', 'gz_2bay35_')):
        rows[(r['scenario'], r['policy'], 'batch')] = r
with gzip.open(RAW / "gazebo_hold.jsonl.gz", "rt") as fh:
    lines = fh.readlines()
for line in lines:
    r = json.loads(line)
    rows[(r['scenario'], r['policy'], 'hold_batch')] = r
def first(r, ev):
    return min((e['t'] for e in r.get('events', []) if e.get('event') == ev), default=None)
def key(scen):
    m2 = re.match(r'gz_2bay(35)?_s(\d)', scen)
    if m2: return 'full', 3.5 if m2.group(1) else 6.0, int(m2.group(2))
    m = re.match(r'gz_exp(\w+?)(\d\d)_s(\d)', scen); return m.group(1), int(m.group(2)) / 10, int(m.group(3))
full = {}
for (s, p, b), r in rows.items():
    tag, rng, seed = key(s)
    if tag == 'full':
        full[(p, rng, seed)] = r
out = []
for (s, p, b), r in sorted(rows.items()):
    tag, rng, seed = key(s)
    tot = sum(a['arrival'] for a in r['agents'].values())
    ref = full.get((p, rng, seed)); ex = None if ref is None else tot - sum(a['arrival'] for a in ref['agents'].values())
    tc, td = first(r, 'conflict_detected'), min(d['t'] for d in r['decisions'])
    out.append({"tag": tag, "rng": rng, "seed": seed, "policy": p, "batch": b, "success": r['success'], "collision": r['collision'],
                    "refuge": r['refuge'], "makespan": r['makespan'], "excess": ex, "ttd": None if tc is None else td - tc,
                    "hold_to": sum(e.get('event') == 'hold_timeout' for e in r.get('events', []))})
grp = {}
for o in out:
    grp.setdefault((o['tag'], o['rng'], o['policy'], o['batch']), []).append(o)
print('| cond | range | policy | src | n | succ | coll | refuges | excess vs full [s] | ttd [s] | hold timeouts |')
for k, g in sorted(grp.items()):
    ex = [o['excess'] for o in g if o['excess'] is not None]; tt = [o['ttd'] for o in g if o['ttd'] is not None]
    refs = {}
    for o in g: refs[o['refuge']] = refs.get(o['refuge'], 0) + 1
    print(f"| {k[0]} | {k[1]} | {k[2]} | {k[3]} | {len(g)} | {sum(o['success'] for o in g)} | {sum(o['collision'] for o in g)} | {refs} | "
          f"{st.mean(ex):+.1f} | {st.mean(tt) if tt else float('nan'):.1f} | {sum(o['hold_to'] for o in g)} |" if ex else f"| {k} | n={len(g)} no full ref |")
