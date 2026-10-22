"""Is the sham step distinguishable from the normal step in the SAME slot (same question, agent, phase, round, k-th)?
If yes, sham itself leaves a signature; if ~0.5 while role-matched is high, the gap is slot selection."""
import gzip, json, collections, sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
from sentence_transformers import SentenceTransformer
rs = [json.loads(l) for l in gzip.open(sys.argv[1], 'rt')]
def slots(r):
    occ = collections.Counter(); out = {}
    for s in r['steps']:
        k = (s['agent_id'], s['phase'], s['round']); occ[k] += 1; out[k + (occ[k],)] = s
    return out
normal = collections.defaultdict(list)
for r in rs:
    if not r['labels'].get('injection'): normal[(r['framework'], r['question_id'])].append(slots(r))
m = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cpu')
def auc_cv(pos, neg, gpos, gneg):
    X = m.encode(pos + neg, batch_size=64, normalize_embeddings=True); y = np.r_[np.ones(len(pos)), np.zeros(len(neg))]; g = np.r_[gpos, gneg]
    s = np.zeros(len(y))
    for tr, te in GroupKFold(5).split(X, y, g):
        s[te] = LogisticRegression(max_iter=2000).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    a = roc_auc_score(y, s); qs = np.unique(g); rng = np.random.default_rng(0); b = []
    for _ in range(500):
        pick = set(rng.choice(qs, len(qs))); ii = [i for i in range(len(y)) if g[i] in pick]
        if len(set(y[ii])) == 2: b.append(roc_auc_score(y[ii], s[ii]))
    return a, np.percentile(b, 2.5), np.percentile(b, 97.5), len(pos), len(neg)
for fw in sorted({r['framework'] for r in rs}):
    for kind in (True, 'style', None):
        pos, neg, gp, gn, rpos, rneg, rgp, rgn = [], [], [], [], [], [], [], []
        for r in rs:
            inj = r['labels'].get('injection')
            if r['framework'] != fw or not inj or inj[0]['strategy'] != 'prompt_injection' or (inj[0].get('injection_process') or {}).get('sham') != kind: continue
            sl = slots(r); tgt = [k for k, s in sl.items() if s['step_id'] == inj[0]['step_id']]
            if not tgt: continue
            k = tgt[0]; q = r['question_id']
            same = [n[k]['output'] for n in normal[(fw, q)] if k in n]
            if not same: continue
            pos.append(sl[k]['output'] or ''); gp.append(q); neg += [x or '' for x in same]; gn += [q] * len(same)
        if pos:
            a, lo, hi, npos, nneg = auc_cv(pos, neg, gp, gn)
            name = {True: 'sham', 'style': 'sham_style', None: 'PI'}[kind]
            print(f'{fw:14s} {name:10s} vs SAME-SLOT normal  AUROC {a:.3f} [{lo:.3f}, {hi:.3f}]  n_pos={npos} n_neg={nneg}', flush=True)
