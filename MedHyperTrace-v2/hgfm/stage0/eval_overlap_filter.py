"""Stage 0 (round 79): drop corpus runs whose task question is a near-duplicate of a responsibility-layer evaluation
question (Who&When 184 + TraceElephant groupchat; round-75 rule: normalised word set, Jaccard >= 0.3).

  python -m hgfm.stage0.eval_overlap_filter --public_dir <mas_traj> --anchor a.jsonl.gz ... --corpus in.jsonl --out out.jsonl --report r.json
Run ids are resolved to questions through the source files (corpus rows carry dataset + run_id).
"""
import argparse, glob, gzip, json, os, re
from collections import Counter, defaultdict

WORD = re.compile(r"[a-z0-9]+")
def words(q): return set(WORD.findall((q or "").lower()))
def jac(a, b): return len(a & b) / max(1, len(a | b))


def read(p):
    with (gzip.open if p.endswith(".gz") else open)(p, "rt", encoding="utf-8") as f:
        for l in f:
            if l.strip(): yield json.loads(l)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--public_dir"); ap.add_argument("--anchor", nargs="*", default=[])
    ap.add_argument("--corpus"); ap.add_argument("--out"); ap.add_argument("--report"); ap.add_argument("--thr", type=float, default=0.3)
    a = ap.parse_args()
    q = {}; evalq = []
    for p in sorted(glob.glob(os.path.join(a.public_dir, "*.jsonl.gz"))):
        ds = os.path.basename(p).split(".")[0]
        for r in read(p):
            q[(ds, r["run_id"])] = r["task"].get("query") or ""
            if ds == "who_and_when" or (ds == "traceelephant" and r.get("framework_family") == "groupchat"):
                evalq.append((ds, r["run_id"], words(r["task"].get("query"))))
    for p in a.anchor:
        for r in read(p): q[("anchor_" + r["framework"], r["run_id"])] = r["task"].get("query") or ""
    inv = defaultdict(set)
    for i, (_, _, w) in enumerate(evalq):
        for t in w: inv[t].add(i)
    rep = Counter(); hits = {}; best = {}
    keys = set()
    for l in open(a.corpus, encoding="utf-8"):
        r = json.loads(l); keys.add((r["dataset"], r["run_id"]))
    for k in keys:
        w = words(q.get(k)); cand = Counter(i for t in w for i in inv.get(t, ()))
        m = max((jac(w, evalq[i][2]) for i in cand), default=0.0); best[k] = m
        if m >= a.thr: hits[k] = m
    drop_tok = Counter(); n = Counter()
    with open(a.out, "w", encoding="utf-8") as fo:
        for l in open(a.corpus, encoding="utf-8"):
            r = json.loads(l); k = (r["dataset"], r["run_id"]); n[r["dataset"]] += 1
            if k in hits: rep[r["dataset"] + "_chunks_dropped"] += 1; continue
            fo.write(l)
    byds = Counter(k[0] for k in hits); allds = Counter(k[0] for k in keys)
    out = {"thr": a.thr, "n_eval_questions": len(evalq), "runs_dropped_by_dataset": dict(byds), "runs_by_dataset": dict(allds),
           "chunks_dropped": dict(rep), "runs_with_jaccard_ge_0.5": sum(1 for v in best.values() if v >= 0.5),
           "runs_with_jaccard_ge_0.7": sum(1 for v in best.values() if v >= 0.7)}
    json.dump(out, open(a.report, "w"), indent=1); print(json.dumps(out))


if __name__ == "__main__":
    main()
