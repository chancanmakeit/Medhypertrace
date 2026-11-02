"""Round 78: zero-API check of the 'successful runs are alike' intuition (motivation 2 for mid-training).
Data: medical-aegis anchor normal runs (llama-4-maverick, 100 MedXpertQA questions x K=3, 4 frameworks).
Rule (fixed before computing): within-question comparisons only; TF-IDF (sublinear, word 1-2gram) cosine distance,
vectoriser fit per framework on all runs; text = concatenated step responses.
  2C1W questions: delta_C = mean d(C,W) - d(C,C)
  1C2W questions: delta_W = mean d(C,W) - d(W,W), split by whether the two wrong runs chose the same option
'Anna Karenina' predicts delta_C > 0 and delta_C > delta_W; if same-option WW pairs are as close as CC pairs,
the regularity is answer agreement, not success. Also reported (question-confounded): mean pairwise distance in
3C vs 0C questions. Views: full trajectory; all steps but the last (final decision removed).
Usage: python analysis/success_regularity_check.py <medical-aegis>/data_runs/anchor_llama_2026-10-21
"""
import sys, gzip, json, collections, itertools, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_distances
D = sys.argv[1]; rng = np.random.default_rng(0)
def txt(r, drop_last):
    h = r['injection_log']['conversation_history']
    if drop_last: h = h[:-1]
    return '\n'.join(str(s.get('response') or s.get('content') or '') for s in h)
def pred(r):
    return (r.get('verification') or {}).get('regex_extracted')
def boot(x, B=2000):
    x = np.asarray(x); 
    if len(x) < 2: return (float('nan'),)*3
    m = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(B)]
    return x.mean(), np.percentile(m, 2.5), np.percentile(m, 97.5)
out = {}
for view in ['full', 'drop_last']:
    pool = collections.defaultdict(list)
    for fw in ['llm_debate', 'mdagents', 'medagents_mc', 'mac_groupchat']:
        rows = [json.loads(l) for l in gzip.open(f'{D}/{fw}__normal.jsonl.gz')]
        X = TfidfVectorizer(sublinear_tf=True, ngram_range=(1, 2), min_df=2).fit_transform([txt(r, view == 'drop_last') for r in rows])
        Dm = cosine_distances(X)
        byq = collections.defaultdict(list)
        for i, r in enumerate(rows): byq[r['question_id']].append(i)
        res = collections.defaultdict(list)
        for q, idx in byq.items():
            if len(idx) != 3: continue
            c = [i for i in idx if rows[i]['is_correct']]; w = [i for i in idx if not rows[i]['is_correct']]
            pd = np.mean([Dm[a, b] for a, b in itertools.combinations(idx, 2)])
            if len(c) == 3: res['disp_3C'].append(pd)
            if len(c) == 0: res['disp_0C'].append(pd)
            if len(c) == 2:
                res['dC'].append(np.mean([Dm[a, w[0]] for a in c]) - Dm[c[0], c[1]]); res['dCC'].append(Dm[c[0], c[1]])
            if len(c) == 1:
                same = pred(rows[w[0]]) is not None and pred(rows[w[0]]) == pred(rows[w[1]])  # 'answer' is the GOLD in this export
                v = np.mean([Dm[c[0], b] for b in w]) - Dm[w[0], w[1]]
                res['dW'].append(v); res['dW_same' if same else 'dW_diff'].append(v)
                res['dWW_same' if same else 'dWW_diff'].append(Dm[w[0], w[1]])
        for k, v in res.items(): pool[k] += v
        out[(view, fw)] = {k: (len(v),) + tuple(round(float(t), 4) for t in boot(v)) for k, v in sorted(res.items())}
    out[(view, 'POOLED')] = {k: (len(v),) + tuple(round(float(t), 4) for t in boot(v)) for k, v in sorted(pool.items())}
for (view, fw), d in out.items():
    print(f'== {view} / {fw}')
    for k, v in d.items(): print(f'   {k:9s} n={v[0]:3d}  mean {v[1]:+.4f}  [{v[2]:+.4f}, {v[3]:+.4f}]')
