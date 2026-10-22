# r55: segment hashes + task questions of ALL previously measured sets (old 5 from r51 + every r53 set),
# built by executing measure_r53.py's own loading/segmentation code (everything before "# Summaries") with a
# hash-only finalize(), so the segmentation is byte-identical to round 53. No tokenization of prior sets is needed.
# Output: /home/claude/public_mas/prior_segments_r55.pkl  {source: set(hash)}, {source: set(norm question)}
# Run: python -I prior_segments_r55.py   (needs the r51 + r53 raw downloads and wwp_inventory.json from extract_wwp.py)
import os, pickle, time, collections
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "measure_r53.py")).read()
head, rest = src.split("# 2. CORRECT-Error", 1)
body = rest.split("# Summaries", 1)[0]
NS = {"__name__": "prior_r55"}
exec(compile(head, "measure_r53.py:head", "exec"), NS)

SEG = collections.defaultdict(set); QS = collections.defaultdict(set); NTRAJ = collections.Counter()
def finalize(ds, trajs):
    for t in trajs:
        name = t["ds"] + (f" ({t['modality']})" if t.get("modality") else "")
        name = name.split("/")[0] if name.startswith(("ARIA/", "AgentErrorBench/")) else name
        excl = t.get("exclude_parts", set())
        for s, p in t["segs"]:
            if p not in excl and isinstance(s, str) and s.strip(): SEG[name].add(NS["h"](s))
        q = t.get("question")
        if isinstance(q, str) and len(NS["norm"](q)) >= 20: QS[name].add(NS["norm"](q))
        NTRAJ[name] += 1
    NS["log"]("hashed", ds, len(trajs))
NS["finalize"] = finalize
exec(compile("# 2. CORRECT-Error" + body, "measure_r53.py:body", "exec"), NS)

# old 5 (r51 segmentation as reproduced in measure_r53.py): OLD_SEG maps hash -> first old dataset
for k, ds in NS["OLD_SEG"].items(): SEG["OLD:" + ds].add(k)
for ds, qs in NS["OLD_Q"].items(): QS["OLD:" + ds] |= {x for x in qs if len(x) >= 20}
out = dict(seg=dict(SEG), questions=dict(QS), n_traj=dict(NTRAJ), built=time.strftime("%Y-%m-%d %H:%M:%S"))
pickle.dump(out, open("/home/claude/public_mas/prior_segments_r55.pkl", "wb"), protocol=5)
print({k: len(v) for k, v in SEG.items()})
print("DONE")
