"""Round 43 checks on medical-aegis gate7_export.jsonl.gz (anchor runs, commit 4cdbf84).
1. read-set fill targets in normal runs: same-phase candidates > true sources, and read set != the slot's
   modal read set (slot = agent_id, phase, round, k-th occurrence)
2. markdown rate ('###' or '**') of injected steps vs normal steps in the SAME slot of the same question
Usage: python -I fill_and_format.py <gate7_export.jsonl.gz>
"""
import gzip, json, collections, sys
import numpy as np
rs = [json.loads(l) for l in gzip.open(sys.argv[1], 'rt')]
def slots(r):
    occ = collections.Counter(); out = {}
    for s in r['steps']:
        k = (s['agent_id'], s['phase'], s['round']); occ[k] += 1; out[k + (occ[k],)] = s
    return out
norm = [r for r in rs if not r['labels'].get('injection')]
pat = collections.defaultdict(collections.Counter); rows = []
for r in norm:
    st = r['steps']; pos = {s['step_id']: i for i, s in enumerate(st)}; occ = collections.Counter()
    for i, s in enumerate(st):
        slot = (r['framework'], s['agent_id'], s['phase'], s['round']); occ[slot] += 1; slot = slot + (occ[slot],)
        src = {pos[x['step_id']] for x in (s.get('sources') or []) if x['step_id'] in pos}
        if not src: continue
        ph = {st[j]['phase'] for j in src}
        if len([j for j in range(i) if st[j]['phase'] in ph]) <= len(src): continue
        key = tuple(sorted((st[j]['agent_id'], st[j]['phase'], st[j]['round']) for j in src)); pat[slot][key] += 1; rows.append((slot, key))
tot, und = collections.Counter(), collections.Counter()
for slot, key in rows:
    tot[slot[0]] += 1; und[slot[0]] += pat[slot][key] != max(pat[slot].values())
print('fill targets (same-phase choice):', dict(tot)); print('  ... and not the slot-modal read set:', dict(und))
normal = collections.defaultdict(list)
for r in norm: normal[(r['framework'], r['question_id'])].append(slots(r))
md = lambda t: ('###' in t) or ('**' in t)
for fw in sorted({r['framework'] for r in rs}):
    for kind, name in ((True, 'sham'), ('style', 'sham_style'), (None, 'PI')):
        a, b = [], []
        for r in rs:
            inj = r['labels'].get('injection')
            if r['framework'] != fw or not inj or inj[0]['strategy'] != 'prompt_injection' or (inj[0].get('injection_process') or {}).get('sham') != kind: continue
            sl = slots(r); k = [k for k, s in sl.items() if s['step_id'] == inj[0]['step_id']]
            if not k: continue
            same = [n[k[0]]['output'] or '' for n in normal[(fw, r['question_id'])] if k[0] in n]
            if same: a.append(md(sl[k[0]]['output'] or '')); b += [md(x) for x in same]
        print(f'{fw:14s} {name:10s} markdown rate: injected {np.mean(a):.2f} (n={len(a)})  same-slot normal {np.mean(b):.2f} (n={len(b)})')
