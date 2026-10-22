"""Same-slot lexical detectors on medical-aegis fmt_val export, raw text vs format-normalised text (round 47).
Positives: injected step (PI or sham, note_version old/fmt_v1); negatives: normal steps in the SAME slot
(question, agent_id, phase, round, k-th) of the same question. LR on tfidf_punct (\S+ tokens, case kept)
or char 3-5 grams; GroupKFold(5) by question; bootstrap CI by question.
Usage: python -I lexical_norm.py <fmt_val_export.jsonl.gz>
"""
import gzip, json, collections, re, sys
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score

def norm(t):
    t = t or ""
    t = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", t)            # headings
    t = re.sub(r"(?m)^\s*(?:[-*+•]|\d+[.)])\s+", "", t)     # list markers
    t = re.sub(r"[*_`]+", "", t)                             # emphasis / code marks
    t = re.sub(r"\[([A-Za-z]{1,12})\]", r"\1", t)            # [YES] -> YES
    return re.sub(r"\s+", " ", t).strip()

rs = [json.loads(l) for l in gzip.open(sys.argv[1], "rt")]
def slots(r):
    occ = collections.Counter(); out = {}
    for s in r["steps"]:
        k = (s["agent_id"], s["phase"], s["round"]); occ[k] += 1; out[k + (occ[k],)] = s
    return out
normal = collections.defaultdict(list)
for r in rs:
    if not r["labels"].get("injection"): normal[(r["framework"], r["question_id"])].append(slots(r))

def auc_cv(texts, y, g, kind):
    vec = (lambda: TfidfVectorizer(token_pattern=r"(?u)\S+", lowercase=False, min_df=2, sublinear_tf=True)) if kind == "punct" else \
          (lambda: TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True))
    y = np.array(y); g = np.array(g); s = np.zeros(len(y))
    for tr, te in GroupKFold(5).split(texts, y, g):
        v = vec(); X = v.fit_transform([texts[i] for i in tr])
        s[te] = LogisticRegression(max_iter=3000).fit(X, y[tr]).predict_proba(v.transform([texts[i] for i in te]))[:, 1]
    a = roc_auc_score(y, s); qs = np.unique(g); rng = np.random.default_rng(0); b = []
    for _ in range(500):
        pick = set(rng.choice(qs, len(qs))); ii = [i for i in range(len(y)) if g[i] in pick]
        if len(set(y[ii])) == 2: b.append(roc_auc_score(y[ii], s[ii]))
    return a, np.percentile(b, 2.5), np.percentile(b, 97.5)

print(f"{'framework':14s} {'kind':5s} {'note':7s} {'feat':5s}  raw AUROC [CI]            normalised AUROC [CI]")
for fw in sorted({r["framework"] for r in rs}):
    for sham, kind in ((None, "PI"), (True, "sham")):
        for note in (None, "fmt_v1"):
            T, y, g = [], [], []
            for r in rs:
                inj = r["labels"].get("injection")
                if r["framework"] != fw or not inj: continue
                i = inj[0]
                if i["strategy"] != "prompt_injection" or (i.get("injection_process") or {}).get("sham") != sham or i.get("note_version") != note: continue
                sl = slots(r); k = [k for k, s in sl.items() if s["step_id"] == i["step_id"]]
                if not k: continue
                same = [n[k[0]]["output"] for n in normal[(fw, r["question_id"])] if k[0] in n]
                if not same: continue
                T.append(sl[k[0]]["output"] or ""); y.append(1); g.append(r["question_id"])
                T += [x or "" for x in same]; y += [0] * len(same); g += [r["question_id"]] * len(same)
            if sum(y) < 10: continue
            for feat in ("punct", "char"):
                a = auc_cv(T, y, g, feat); b = auc_cv([norm(t) for t in T], y, g, feat)
                print(f"{fw:14s} {kind:5s} {note or 'old':7s} {feat:5s}  {a[0]:.2f} [{a[1]:.2f}, {a[2]:.2f}]   ->   {b[0]:.2f} [{b[1]:.2f}, {b[2]:.2f}]   n_pos={sum(y)}", flush=True)
