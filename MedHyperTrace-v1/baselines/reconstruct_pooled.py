"""Reconstruct EXACT pooled Micro-F1 from a per-framework set_metrics.json plus the
dataset (gold-pair counts are deterministic). For each framework/method/level:
  TP+FN = sum|G_level|  (recomputed from data, level-projected gold sets)
  TP = micro_r/100 * (TP+FN)
  TP+FP = TP / (micro_p/100)      => FP = (TP+FN)*... etc.
Sum TP/FP/FN across frameworks, then pooled Micro-F1 = 2TP/(2TP+FP+FN).
Step: pooled = sum(step_acc*n_step) — but we only have step_acc and n (n_step≈n minus
masked; here all frameworks have masked=0 so n_step=n). Weighted by n.
"""
import sys, json
sys.path.insert(0, '.')
from common.data import load_jsonl
from common.paths import FILES
from common.splits import load_split

def gold_counts(name, level):
    trajs = load_jsonl(FILES[name]); _, te = load_split(name)
    tot = 0
    for t in trajs:
        if t.id not in te: continue
        pairs = [(r, fm) for (r, ri), fms in t.labels.instance_fms.items() for fm in fms]
        if level == 'agent':
            s = {a for a, _ in pairs}
        elif level == 'error':
            s = {e for _, e in pairs}
        else:
            s = set(pairs)
        tot += len(s)
    return tot

d = json.load(open('set_metrics.json'))
methods = list(next(iter(d.values())).keys())
levels = ['agent', 'error', 'pair']
# precompute gold counts per framework/level
gc = {name: {lv: gold_counts(name, lv) for lv in levels} for name in d}

pooled = {}
for meth in methods:
    acc = {lv: {'TP':0.0,'FP':0.0,'FN':0.0} for lv in levels}
    step_hit = step_n = 0
    for name in d:
        m = d[name][meth]
        n = m['n']
        for lv in levels:
            gcount = gc[name][lv]            # = TP+FN
            r = m[f'{lv}_micro_r']/100.0
            p = m[f'{lv}_micro_p']/100.0
            TP = r * gcount
            FN = gcount - TP
            FP = (TP/p - TP) if p > 0 else 0.0
            acc[lv]['TP'] += TP; acc[lv]['FP'] += FP; acc[lv]['FN'] += FN
        step_hit += m['step_acc']*n; step_n += n
    out = {'n': int(step_n)}
    for lv in levels:
        TP,FP,FN = acc[lv]['TP'],acc[lv]['FP'],acc[lv]['FN']
        P = TP/(TP+FP) if TP+FP>0 else 0.0
        R = TP/(TP+FN) if TP+FN>0 else 0.0
        F1 = 2*P*R/(P+R) if P+R>0 else 0.0
        out[f'{lv}_micro_f1'] = F1*100
    out['step_acc'] = step_hit/step_n
    pooled[meth] = out
json.dump({'pooled': pooled}, open('/tmp/ww_pooled.json','w'), indent=1)
print("reconstructed pooled metrics:")
for meth,m in pooled.items():
    print(f"  {meth:18s} Agent={m['agent_micro_f1']:.1f} Error={m['error_micro_f1']:.1f} "
          f"Pair={m['pair_micro_f1']:.1f} Step={m['step_acc']*100:.1f} n={m['n']}")
