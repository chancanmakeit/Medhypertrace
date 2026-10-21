"""Label-free look at what MedHyperTrace does on the 360 real MAFA package traces: which step it picks, how often
that equals first-step / the content-free structure prior, and how confident it is. Uses NO MAFA label.
Input: eval_mafa/out_pkg/detail.json (predict.py on review_packages/mast_v1.json)."""
import collections, importlib.util, json, os, sys
_r = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _r)
spec = importlib.util.spec_from_file_location("ev", os.path.join(_r, "eval_mafa", "evaluate.py"))
ev = importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)
M = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/mafa-human-ai-annotation"
items = json.load(open(os.path.join(M, "review_packages", "mast_v1.json")))["items"]
sp = ev.structure_prior(items)
det = {d["trace_id"]: d for d in json.load(open(os.path.join(_r, "eval_mafa", "out_pkg", "detail.json")))}
out = collections.defaultdict(collections.Counter)
for it in items:
    d = det[it["id"]]; fw = it["framework"]; top = d["top_step"]
    out[fw]["n"] += 1; out[fw]["same_as_first_step"] += top == it["steps"][0]["id"]
    out[fw]["same_as_structure_prior"] += top == sp[(None, it["id"])]["pred_step"]
    out[fw]["top_prob_ge_0.95"] += max(d["step_scores"].values()) >= 0.95
    out[fw]["n_steps_max"] = max(out[fw]["n_steps_max"], len(it["steps"]))
    out[fw]["chosen:" + top] += 1
json.dump({k: dict(v) for k, v in out.items()}, open(os.path.join(_r, "analysis", "mht_behavior_realtraces.json"), "w"), indent=1)
for fw, v in sorted(out.items()):
    print(fw, dict(v))
