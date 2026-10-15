"""Leakage check of ALL 360 MAFA package traces (dev + test, eval_split_v1) against MedHyperTrace's training data.
Uses trace CONTENT only (no labels). The leakage FLAG is `same_framework_train`: the same question STEM (text before
the options, normalised, plus the same images for image questions; MAFA interface doc §6.6) appears in the same framework's synthetic TRAIN split -- ids and full
text both miss MMLU-Pro variants. `same_framework_any` additionally flags stems present only in that framework's
synthetic test split (not used for training, reported for completeness). Single-step content matches are listed for reference only: step-only matches
without a shared question are formulaic outputs (e.g. ClinicalAgent5's Reasoner weighted-average line), not leakage."""
import collections, hashlib, json, os, sys
_r = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _r)
from common.data import load_jsonl  # noqa: E402
from common.paths import FILES, SPLITS_JSON  # noqa: E402

M = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/mafa-human-ai-annotation"
h = lambda x: hashlib.sha1(x.encode()).hexdigest()  # noqa: E731
import re  # noqa: E402
STEM_MARK = re.compile(r"\bOptions:|Answer Choices:?")


def qn(q, images=()):
    """Question STEM (text before the option list; whole text for the clinical-trial frameworks), normalised, plus
    the image file names; case-insensitive (MAFA §6.6: e.g. MM-89 "what is the diagnosis?"). MMLU-Pro variants share a stem but differ in the option set/order, so neither ids nor
    full text catch them. Image questions often share a generic stem ("What is the diagnosis?") with a DIFFERENT
    image, so for them the images must match too."""
    q = q or ""
    m = STEM_MARK.search(q)
    return h(" ".join((q[:m.start()] if m else q).split()).lower() + "||" + "|".join(sorted(images or ())))
sp = json.load(open(SPLITS_JSON))
step_ix, trace_ix, q_ix = collections.defaultdict(set), collections.defaultdict(set), collections.defaultdict(set)
for fw, p in FILES.items():
    tr, te = set(sp[fw]["train_task_ids"]), set(sp[fw]["test_task_ids"])
    for t in load_jsonl(p):
        tag = f"{fw}/{'train' if t.id in tr else 'test' if t.id in te else 'none'}"
        hs = [h(s.content) for s in t.steps]
        for s, x in zip(t.steps, hs):
            if len(s.content.strip()) >= 20:
                step_ix[x].add(tag)
        trace_ix[tuple(hs)].add(tag); q_ix[qn(t.query, t.images)].add(tag)
split = json.load(open(os.path.join(M, "review_packages/eval_split_v1.json")))
es = {**{x: "dev" for x in split["dev"]}, **{x: "test" for x in split["test"]}}
items = {it["id"]: it for it in json.load(open(os.path.join(M, "review_packages/mast_v1.json")))["items"]}
agg = collections.Counter(); rows = []
for tid, it in items.items():
    hs = tuple(h(s["content"]) for s in it["steps"])
    tr_hit = sorted(trace_ix.get(hs, set()))
    st_hit = sorted({tag for s in it["steps"] if len((s["content"] or "").strip()) >= 20 for tag in step_ix.get(h(s["content"]), set())})
    q_hit = sorted(q_ix.get(qn(it["question"], it.get("images")), set()))
    same_fw_train = f"{it['framework']}/train" in set(q_hit) | set(tr_hit)
    same_fw_any = any(x.startswith(it['framework'] + "/") for x in set(q_hit) | set(tr_hit))
    key = f"{es[tid]}/{it['split']}"
    agg[key + ":n"] += 1; agg[key + ":trace"] += bool(tr_hit); agg[key + ":step"] += bool(st_hit)
    agg[key + ":question_any"] += bool(q_hit); agg[key + ":same_fw_train"] += same_fw_train
    agg[key + ":same_fw_any"] += same_fw_any
    rows.append({"trace_id": tid, "eval_set": es[tid], "split": it["split"], "framework": it["framework"],
                 "trace_match": tr_hit, "step_match": st_hit, "question_match": q_hit, "same_framework_train": same_fw_train,
                 "same_framework_any": same_fw_any, "not_in_train_only": same_fw_any and not same_fw_train})
out = os.path.join(_r, "eval_mafa", "out_v2", "leakage_package.json")
json.dump({"summary": dict(agg), "rows": rows}, open(out, "w"), indent=1)
for k in sorted({k.split(":")[0] for k in agg}):
    print(f"{k:12s} n={agg[k+':n']:3d}  whole-trace {agg[k+':trace']}  any step {agg[k+':step']}  same question (any synthetic split) {agg[k+':question_any']}  same framework TRAIN {agg[k+':same_fw_train']}  same framework any split {agg[k+':same_fw_any']}")
print("faulty flagged:", [(r["eval_set"], r["trace_id"].rsplit("#", 1)[1], "train" if r["same_framework_train"] else "not-in-train")
                         for r in rows if r["split"] == "faulty" and r["same_framework_any"]])
print("frameworks with question overlap:", collections.Counter(f"{r['framework']}->{','.join(r['question_match'])}" for r in rows if r['question_match']))
