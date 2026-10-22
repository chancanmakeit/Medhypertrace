# round 56: MS-Swift vs train.py on the same fold (LQD_mac): per variant macro AUROC, paired bootstrap of the
# difference (same instances), Spearman of instance scores, and swift-vs-train.py graph-minus-text.
# Copy of /data1/ekyang/cgh/CODE/mht_work/swift_vs_trainpy.py on Linux #2. Usage: python linux2_swift_vs_trainpy.py [fold]
import json, sys, numpy as np
from sklearn.metrics import roc_auc_score
from scipy.stats import spearmanr
L, F, T = "/data1/ekyang/cgh/CODE/mht_work/maa/llm", sys.argv[1] if len(sys.argv) > 1 else "LQD_mac", "models--Qwen--Qwen3-8B"
def load(p): return {r["inst"]: r for r in json.load(open(p))["rows"]}
def macro(keys, src):
    out = []
    for c in sorted({src[k]["code"] for k in keys}):
        kk = [k for k in keys if src[k]["code"] == c]; y = [src[k]["human"] for k in kk]
        if len(set(y)) == 2: out.append(roc_auc_score(y, [src[k]["score"] for k in kk]))
    return float(np.mean(out))
def paired(A, B, n=1000):
    ks = sorted(set(A) & set(B)); rng = np.random.default_rng(0); d = []
    for _ in range(n):
        b = [ks[i] for i in rng.integers(0, len(ks), len(ks))]; d.append(macro(b, A) - macro(b, B))
    return len(ks), macro(ks, A), macro(ks, B), np.nanpercentile(d, 2.5), np.nanpercentile(d, 97.5)
R = {}
for v in ("graph", "text"):
    R[("swift", v)] = load(f"{L}/{F}/eval_swift_{T}_{v}.json"); R[("torch", v)] = load(f"{L}/{F}/eval_{T}_{v}.json")
out = {}
for v in ("graph", "text"):
    S, P = R[("swift", v)], R[("torch", v)]; ks = sorted(set(S) & set(P))
    n, a, b, lo, hi = paired(S, P); rho = spearmanr([S[k]["score"] for k in ks], [P[k]["score"] for k in ks])[0]
    out[v] = dict(n=n, swift=a, train_py=b, diff=a - b, ci95=[lo, hi], spearman=rho)
    print(f"{v:5s} n={n} swift {a:.3f} train.py {b:.3f} diff {a-b:+.3f} [{lo:+.3f}, {hi:+.3f}] spearman {rho:.3f}")
for eng in ("swift", "torch"):
    n, a, b, lo, hi = paired(R[(eng, "graph")], R[(eng, "text")])
    out[f"{eng}_graph_minus_text"] = dict(n=n, graph=a, text=b, diff=a - b, ci95=[lo, hi])
    print(f"{eng:5s} graph - text: {a:.3f} - {b:.3f} = {a-b:+.3f} [{lo:+.3f}, {hi:+.3f}]")
json.dump(out, open(f"{L}/{F}/swift_vs_trainpy.json", "w"), indent=1)
