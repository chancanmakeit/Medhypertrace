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

Usage:
  python -m data_tools.maa_exclusion build <maa_mas_traj.jsonl> <out.json> [--extra anchor_overlap.json]
  python -m data_tools.maa_exclusion check <exclusion.json> <file.jsonl> [--query-field task.query] [--images-field task.images]
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("maa"); b.add_argument("out"); b.add_argument("--extra")
    c = sub.add_parser("check"); c.add_argument("excl"); c.add_argument("file")
    c.add_argument("--query-field", default="task.query"); c.add_argument("--images-field", default="task.images")
    a = ap.parse_args()
    if a.cmd == "build": build(a.maa, a.out, a.extra)
    else: check(a.excl, a.file, a.query_field, a.images_field)
