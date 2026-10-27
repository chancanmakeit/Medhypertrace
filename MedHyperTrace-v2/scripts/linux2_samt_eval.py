# round 64: SAMT v1 evaluation. Taxonomy: MedAgentAudit only (human instances, macro AUROC over the MAA codes).
# Runs (MS-Swift SFT, prompts identical to the base runs; only the graph vectors / projector start differ):
#   base_graph / base_text   base Qwen3-8B, per-fold supervised encoder tokens, seeds 0/1/2 (round 60 seed study)
#   samt                     SAMT encoder tokens + SAMT-aligned projector (lr 1e-4), graph, seeds 0/1
#   encOnly                  SAMT encoder tokens + random projector (lr 1e-3), graph, seeds 0/1   (control)
#   samt_zero / samt_shuf    SAMT checkpoints evaluated with zeroed / cross-run shuffled graph tokens (if present)
# Metrics: macro AUROC over codes with both classes ("main", as rounds 60-62) and over codes with >= 2 positives and
# >= 2 negatives ("robust", round 62: LQD_mac has two single-positive codes). Paired bootstrap 1000 over instances;
# seed ensemble = mean of z-scored instance scores.
# Writes midtrain/samt_v1/samt_v1_eval.json and samt_v1_scores.csv.
import json, csv, os, numpy as np
from scipy.stats import rankdata
def roc_auc_score(y, s):
    """Mann-Whitney AUROC with average ranks for ties (= sklearn.metrics.roc_auc_score for binary y), ~100x faster."""
    y = np.asarray(y); r = rankdata(np.asarray(s, dtype=float)); n1 = int(y.sum()); n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
W = os.environ.get("MHT_WORK", "/data1/ekyang/cgh/CODE/mht_work"); L = f"{W}/maa/llm"; OUT = f"{W}/midtrain/samt_v1"
BASE = "models--Qwen--Qwen3-8B"
def tag(s, T): return f"swift_{T}" if s == 0 else f"swift_s{s}_{T}"
RUNS = {"base_graph": (BASE, "graph", (0, 1, 2)), "base_text": (BASE, "text", (0, 1, 2)),
        "samt": ("samt_v1", "graph", (0, 1)), "encOnly": ("samt_v1_encOnly", "graph", (0, 1)),
        "samt_zero": ("samt_v1_zero", "graph", (0, 1)), "samt_shuf": ("samt_v1_shuf", "graph", (0, 1))}
def load(f, s, T, v):
    p = f"{L}/{f}/eval_{tag(s, T)}_{v}.json"
    return {r["inst"]: r for r in json.load(open(p))["rows"]} if os.path.exists(p) else None
def macro(keys, src, minc=1):
    out = []
    for c in sorted({src[k]["code"] for k in keys}):
        kk = [k for k in keys if src[k]["code"] == c]; y = [src[k]["human"] for k in kk]
        if sum(y) >= minc and len(y) - sum(y) >= minc: out.append(roc_auc_score(y, [src[k]["score"] for k in kk]))
    return float(np.mean(out))
def paired(A, B, minc=1, n=1000):
    ks = sorted(set(A) & set(B)); rng = np.random.default_rng(0); d = []
    for _ in range(n):
        b = [ks[i] for i in rng.integers(0, len(ks), len(ks))]
        try: d.append(macro(b, A, minc) - macro(b, B, minc))
        except Exception: pass
    a, b = macro(ks, A, minc), macro(ks, B, minc)
    return dict(n=len(ks), A=a, B=b, diff=a - b, ci95=[float(np.nanpercentile(d, 2.5)), float(np.nanpercentile(d, 97.5))])
def ens(runs):
    ks = sorted(set.intersection(*[set(r) for r in runs])); zs = []
    for r in runs:
        a = np.array([r[k]["score"] for k in ks]); zs.append((a - a.mean()) / (a.std() + 1e-9))
    m = np.mean(zs, 0)
    return {k: dict(runs[0][k], score=float(m[i])) for i, k in enumerate(ks)}
def fmt(p): return f"{p['A']:.3f} vs {p['B']:.3f} diff {p['diff']:+.3f} [{p['ci95'][0]:+.3f}, {p['ci95'][1]:+.3f}]"
res = {"per_run": [], "summary": {}, "compare": {}}; rows = []
COMP = [("samt", "base_text", "main: aligned graph tokens vs text-only"), ("samt", "base_graph", "SAMT vs supervised-encoder graph"),
        ("samt", "encOnly", "alignment effect (same tokens, projector init)"), ("encOnly", "base_graph", "encoder swap only"),
        ("encOnly", "base_text", "encoder swap vs text"), ("samt", "samt_zero", "C6 diagnosis: real vs zeroed tokens"),
        ("samt", "samt_shuf", "C6 diagnosis: real vs shuffled tokens")]
for f in ("QD", "LQD_mac"):
    R = {}
    for name, (T, v, ss) in RUNS.items():
        got = {s: load(f, s, T, v) for s in ss}
        R[name] = {s: D for s, D in got.items() if D is not None}
    for name, D in R.items():
        if not D: continue
        for s, X in D.items():
            ks = sorted(X)
            res["per_run"].append(dict(fold=f, run=name, seed=s, n=len(ks), main=macro(ks, X), robust=macro(ks, X, 2)))
            for k in ks: rows.append([f, name, s, k, X[k]["code"], X[k]["human"], X[k]["score"]])
        for met in ("main", "robust"):
            au = [r[met] for r in res["per_run"] if r["fold"] == f and r["run"] == name]
            res["summary"][f"{f}/{met}/{name}"] = dict(seeds=sorted(D), aurocs=au, mean=float(np.mean(au)), sd=float(np.std(au, ddof=1)) if len(au) > 1 else None)
            print(f"{f:8s} {met:6s} {name:11s} {' '.join(f'{x:.3f}' for x in au)}  mean {np.mean(au):.3f}")
    for a, b, what in COMP:
        if not R.get(a) or not R.get(b): continue
        for met, minc in (("main", 1), ("robust", 2)):
            out = {}
            for s in sorted(set(R[a]) & set(R[b])):
                out[f"same_seed_s{s}"] = paired(R[a][s], R[b][s], minc)
            out["ensemble"] = paired(ens(list(R[a].values())), ens(list(R[b].values())), minc)
            res["compare"][f"{f}/{met}/{a}-{b}"] = dict(what=what, **out)
            print(f"{f:8s} {met:6s} {a}-{b} ({what}): ens {fmt(out['ensemble'])}; " +
                  "; ".join(f"{k[-2:]} {v['diff']:+.3f} [{v['ci95'][0]:+.3f},{v['ci95'][1]:+.3f}]" for k, v in out.items() if k.startswith("same")))
json.dump(res, open(f"{OUT}/samt_v1_eval.json", "w"), indent=1, default=float)
with open(f"{OUT}/samt_v1_scores.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["fold", "run", "seed", "inst", "code", "human", "score"]); w.writerows(rows)
print("rows", len(rows))
