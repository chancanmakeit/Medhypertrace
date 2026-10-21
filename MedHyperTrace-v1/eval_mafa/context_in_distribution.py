"""In-distribution context: step-head top-1 on the synthetic test split vs the first-step baseline."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.data import load_jsonl
from common.paths import FILES, SPLITS_JSON

OUT = sys.argv[1] if len(sys.argv) > 1 else "eval_mafa/out"
sp = json.load(open(SPLITS_JSON))
meta = json.load(open(os.path.join(OUT, "model_meta.json")))
res = {}
for fw in sorted(meta["frameworks"]):
    te = set(sp[fw]["test_task_ids"])
    T = [t for t in load_jsonl(FILES[fw]) if t.id in te and t.labels.earliest_error_turn is not None]
    hit = sum(min(s.turn for s in t.steps if not s.is_input) == t.labels.earliest_error_turn for t in T)
    res[fw] = {"model_step_top1": meta["frameworks"][fw]["synthetic_test_step_top1"],
               "first_step_baseline": round(hit / len(T), 3), "n": len(T)}
json.dump(res, open(os.path.join(OUT, "context_in_distribution.json"), "w"), indent=1)
print(res)
