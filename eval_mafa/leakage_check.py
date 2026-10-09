"""MAFA doc §3 leakage check: are any of the 17 eval traces in MedHyperTrace's training data?

Training data = AEGIS-custom-dataset-8-13 synthetic-injection files (common.paths.FILES),
split by common/splits.json (task level). The MAFA eval traces come from the separate
real-fault files *_fm_clean_none_none-allfalse.jsonl.

Checks, per eval trace:
  1. file + line      : same source file and line   (the doc's primary key)
  2. trace sha1       : identical full step-content sequence in any training record
  3. step sha1        : any single step content identical to a training step
                        (empty / trivially short contents reported separately)
  4. task             : same task id or same query text (an injected variant of the same
                        question). NOT trajectory leakage by the doc's definition, but a model
                        could memorise task-specific signal, so it is reported.
"""
import collections
import json
import os
import sys

_r = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _r not in sys.path:
    sys.path.insert(0, _r)

from common.data import load_jsonl  # noqa: E402
from common.paths import FILES, SPLITS_JSON  # noqa: E402
from eval_mafa.adapter import load_eval, sha1  # noqa: E402

TRIVIAL = 20  # step contents shorter than this (chars) are reported as trivial matches


def main(mafa_root, out_path):
    rows = load_eval(mafa_root)
    splits = json.load(open(SPLITS_JSON))
    eval_fws = sorted({t["framework"] for t, _, _ in rows})

    # index all 5 frameworks (a joint model would see all of them)
    step_index = collections.defaultdict(set)      # sha1 -> {(fw, split, rec_id)}
    trace_index = collections.defaultdict(set)
    task_index = collections.defaultdict(set)      # id -> {(fw, split)}
    query_index = collections.defaultdict(set)
    files = {}
    for fw, path in FILES.items():
        files[fw] = os.path.realpath(path)
        tr_ids = set(splits[fw]["train_task_ids"])
        te_ids = set(splits[fw]["test_task_ids"])
        for t in load_jsonl(path):
            sp = "train" if t.id in tr_ids else ("test" if t.id in te_ids else "none")
            key = (fw, sp, t.id)
            hs = [sha1(s.content) for s in t.steps]
            for h in hs:
                step_index[h].add(key)
            trace_index[tuple(hs)].add(key)
            task_index[t.id].add((fw, sp))
            query_index[sha1(t.query.strip())].add((fw, sp))

    report = {"training_files": files, "eval_frameworks": eval_fws, "traces": [], "summary": {}}
    agg = collections.Counter()
    for t, traj, _ in rows:
        src = os.path.realpath(os.path.join(mafa_root, t["source"]["file"]))
        file_line = any(src == p for p in files.values())
        hs = tuple(s["content_sha1"] for s in t["steps"])
        trace_hit = sorted(trace_index.get(hs, set()))
        step_hits, trivial_hits = [], []
        for s in t["steps"]:
            hit = step_index.get(s["content_sha1"])
            if not hit:
                continue
            n = len(next(x.content for x in traj.steps if sha1(x.content) == s["content_sha1"]))
            (trivial_hits if n < TRIVIAL else step_hits).append(
                {"step": s["id"], "chars": n, "in": sorted({f"{fw}/{sp}" for fw, sp, _ in hit})})
        rid = str(t["source"]["record_id"])
        task_hit = sorted(f"{fw}/{sp}" for fw, sp in task_index.get(rid, set()))
        query_hit = sorted(f"{fw}/{sp}" for fw, sp in query_index.get(sha1(traj.query.strip()), set()))
        same_fw_train = any(h.startswith(t["framework"] + "/train") for h in task_hit + query_hit)
        r = {"trace_id": t["trace_id"], "file_line_match": file_line, "trace_sha1_match": trace_hit,
             "nontrivial_step_matches": step_hits, "trivial_step_matches": trivial_hits,
             "task_id_match": task_hit, "query_match": query_hit,
             "same_task_in_same_framework_train": same_fw_train}
        report["traces"].append(r)
        agg["file_line"] += file_line
        agg["trace_sha1"] += bool(trace_hit)
        agg["any_nontrivial_step"] += bool(step_hits)
        agg["task_or_query_any"] += bool(task_hit or query_hit)
        agg["task_same_fw_train"] += same_fw_train
    n = len(rows)
    report["summary"] = {k: f"{v}/{n}" for k, v in agg.items()}
    json.dump(report, open(out_path, "w"), indent=1, ensure_ascii=False)
    for r in report["traces"]:
        print(f"{r['trace_id'][:62]:<62} file={int(r['file_line_match'])} trace={len(r['trace_sha1_match'])} "
              f"steps={[x['step'] for x in r['nontrivial_step_matches']]} "
              f"trivial={[x['step'] for x in r['trivial_step_matches']]} task={r['task_id_match']} "
              f"query={r['query_match']}")
    print("\nsummary:", report["summary"])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/home/claude/mafa-human-ai-annotation",
         sys.argv[2] if len(sys.argv) > 2 else "eval_mafa/out/leakage.json")
