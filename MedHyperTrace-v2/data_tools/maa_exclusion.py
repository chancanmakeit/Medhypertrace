"""MAA exclusion list: build it, and check any trajectory file against it (round 57).

MedAgentAudit (MAA) is MedHyperTrace's zero-shot evaluation set (600 questions: MedQA, MedXpertQA-text, PubMedQA,
PathVQA, SLAKE, VQA-RAD, 100 each). No MAA question may enter any training or mid-training corpus. medical-aegis
draws from the same benchmark pools, so the list is meant to be enforced at generation / export time, too.

Normalisation (`norm_stem`): cut the options block (first of "\\n Options:", "\\nAnswer Choices", "\\n(A) / A. / A:"),
lower-case, replace every non-alphanumeric run by one space, strip.

A query matches an MAA question when
  1. exact: its norm_stem equals an MAA norm_stem, AND, if the MAA question has images, the image file names overlap
     (VQA questions such as "is liver present" repeat across images, so the stem alone is not identity); or
  2. probe (only stems >= 200 chars): the 60-char window at characters 100-160 of one stem occurs in the other.
     The window sits in the case body; the first and last 60 characters are shared boilerplate in medical items
     ("a 27 year old woman comes to the physician ...", "... which of the following is the most likely ...") and
     gave only false positives (rounds 55 and 57).
Probe hits are candidates for manual review, exact hits are exclusions.

`recall` (round 60, after medical-aegis issue round 40-41 / TerminalHorizon appendix G.4) catches paraphrased stems:
for every distinct query it lists the top-k most similar MAA stems by TF-IDF cosine (word 1-2 grams) and by word
5-gram Jaccard. These are only candidates for human / LLM review: no threshold removes anything automatically.

Usage:
  python -m data_tools.maa_exclusion build <maa_mas_traj.jsonl> <out.json> [--extra anchor_overlap.json]
  python -m data_tools.maa_exclusion check <exclusion.json> <file.jsonl> [--query-field task.query] [--images-field task.images]
  python -m data_tools.maa_exclusion recall <exclusion.json> <file.jsonl> --out pairs.jsonl [--k 3] [--query-field ...]
"""
import argparse, hashlib, json, re, sys
from collections import defaultdict

VERSION = "maa_exclusion_v1"
_OPT = re.compile(r"\n\s*Options:|\nAnswer Choices|\n\s*\(?A[\).:]\s")


def norm_stem(q):
    q = _OPT.split(q or "")[0]
    return re.sub(r"[^a-z0-9]+", " ", q.lower()).strip()


def _get(rec, path):
    for k in path.split("."):
        rec = rec.get(k) if isinstance(rec, dict) else None
    return rec


def build(maa_path, out, extra=None):
    ent = {}
    for line in open(maa_path):
        r = json.loads(line); qid = r["question_id"]
        if qid in ent: continue
        s = norm_stem(r["task"]["query"])
        ent[qid] = {"question_id": qid, "dataset": r["task"].get("dataset"), "images": sorted(r["task"].get("images") or []),
                    "norm_stem": s, "norm_stem_sha1": hashlib.sha1(s.encode()).hexdigest()}
    doc = {"version": VERSION, "n_questions": len(ent), "normalisation": __doc__.split("Normalisation")[1].split("A query")[0].strip(),
           "entries": sorted(ent.values(), key=lambda e: e["question_id"]), "extra_exclusions": json.load(open(extra)) if extra else []}
    json.dump(doc, open(out, "w"), indent=0, ensure_ascii=False)
    print(f"{len(ent)} MAA questions -> {out}")


def check(excl_path, path, qf="task.query", imf="task.images"):
    doc = json.load(open(excl_path)); by_stem = defaultdict(list)
    for e in doc["entries"]: by_stem[e["norm_stem"]].append(e)
    long = [e for e in doc["entries"] if len(e["norm_stem"]) >= 200]
    blob = "\n".join(e["norm_stem"] for e in long)
    n = 0; exact, probe = [], []
    seen = set()
    for i, line in enumerate(open(path)):
        r = json.loads(line); q = _get(r, qf)
        if not q: continue
        s = norm_stem(q); ims = set(_get(r, imf) or [])
        key = (s, tuple(sorted(ims)))
        if key in seen: continue
        seen.add(key); n += 1
        for e in by_stem.get(s, []):
            if not e["images"] or ims & set(e["images"]): exact.append((i, e["question_id"]))
        if len(s) >= 200:
            w = s[100:160]
            if w in blob: probe.append((i, [e["question_id"] for e in long if w in e["norm_stem"]]))
            else:
                hits = [e["question_id"] for e in long if e["norm_stem"][100:160] in s]
                if hits: probe.append((i, hits))
    print(f"{path}: {n} distinct queries; exact matches {len(exact)}; probe candidates {len(probe)}")
    for i, q in exact[:20]: print("  EXACT line", i, q)
    for i, q in probe[:20]: print("  PROBE line", i, q)
    return exact, probe


def _ngrams(s, n=5):
    w = s.split(); return {" ".join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))} or {s}


def recall(excl_path, path, out, k=3, qf="task.query"):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    doc = json.load(open(excl_path)); E = doc["entries"]; stems = [e["norm_stem"] for e in E]
    qs = []
    for line in open(path):
        q = _get(json.loads(line), qf)
        if q: qs.append(norm_stem(q))
    qs = sorted(set(qs))
    vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True).fit(stems + qs)
    S = linear_kernel(vec.transform(qs), vec.transform(stems))
    eng = [_ngrams(s) for s in stems]
    with open(out, "w") as f:
        for i, q in enumerate(qs):
            top_t = S[i].argsort()[::-1][:k]
            qn = _ngrams(q); jac = [len(qn & g) / len(qn | g) for g in eng]
            top_j = sorted(range(len(E)), key=lambda j: -jac[j])[:k]
            for j in sorted(set(top_t) | set(top_j)):
                f.write(json.dumps({"query_stem": q[:400], "maa_question_id": E[j]["question_id"], "maa_stem": E[j]["norm_stem"][:400],
                                    "tfidf_cos": round(float(S[i, j]), 4), "jaccard5": round(jac[j], 4)}) + "\n")
    print(f"{len(qs)} distinct queries -> review candidates in {out} (top-{k} by TF-IDF and by 5-gram Jaccard)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("maa"); b.add_argument("out"); b.add_argument("--extra")
    c = sub.add_parser("check"); c.add_argument("excl"); c.add_argument("file")
    c.add_argument("--query-field", default="task.query"); c.add_argument("--images-field", default="task.images")
    r = sub.add_parser("recall"); r.add_argument("excl"); r.add_argument("file"); r.add_argument("--out", required=True)
    r.add_argument("--k", type=int, default=3); r.add_argument("--query-field", default="task.query")
    a = ap.parse_args()
    if a.cmd == "build": build(a.maa, a.out, a.extra)
    elif a.cmd == "check": check(a.excl, a.file, a.query_field, a.images_field)
    else: recall(a.excl, a.file, a.out, a.k, a.query_field)
