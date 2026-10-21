"""Does the step head's gain on prompt_injection come from EMPTY injected steps? Seed 0, earliest_PI subset,
split by whether the labelled earliest step is empty (<5 chars). Compared with the structural prior."""
import collections, json, os, random, sys
_r = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _r)
import numpy as np, torch  # noqa: E401,E402
from analysis.strategy_split_eval import acting, subset_of, model_preds  # noqa: E402
from common.data import load_jsonl  # noqa: E402
from common.paths import FILES, SPLITS_JSON  # noqa: E402
from ours import train_hgnn as T  # noqa: E402

sp = json.load(open(SPLITS_JSON)); args = T.get_args(["x"]); out = {}
for fw in sys.argv[1:]:
    trajs = load_jsonl(FILES[fw])
    tr_ids, te_ids = set(sp[fw]["train_task_ids"]), set(sp[fw]["test_task_ids"])
    train = [t for t in trajs if t.id in tr_ids]
    test = [t for t in trajs if t.id in te_ids and t.labels.earliest_error_turn is not None]
    hit, tot = collections.Counter(), collections.Counter()
    for t in train:
        for i, s in enumerate(acting(t)):
            tot[(i, s.orig_agent_name)] += 1; hit[(i, s.orig_agent_name)] += s.turn == t.labels.earliest_error_turn
    pr = lambda k: (hit[k] + .5) / (tot[k] + 1)  # noqa: E731
    struct = [acting(t)[max(range(len(acting(t))), key=lambda i: (pr((i, acting(t)[i].orig_agent_name)), -i))].turn for t in test]
    random.seed(0); np.random.seed(0); torch.manual_seed(0)
    fz = T.make_featurizer("tfidf", train, None); tr, va = T.split_val(train)
    model, _, fd = T.train_model(tr, va, fz, args)
    mht = model_preds(model, [T.build_sample(t, fz, args.struct, None) for t in test], fd, test)
    res = {}
    for i, t in enumerate(test):
        if "earliest_PI" not in subset_of(t):
            continue
        g = t.labels.earliest_error_turn
        e = len(next(s for s in t.steps if s.turn == g).content.strip()) < 5
        key = "gold_step_empty" if e else "gold_step_nonempty"
        r = res.setdefault(key, {"n": 0, "mht": 0, "struct": 0})
        r["n"] += 1; r["mht"] += mht[i] == g; r["struct"] += struct[i] == g
    out[fw] = res
    for k, r in res.items():
        print(f"{fw:16s} earliest_PI {k:19s} n={r['n']:4d}  MHT {r['mht']}/{r['n']}={r['mht']/r['n']:.2f}  struct {r['struct']}/{r['n']}={r['struct']/r['n']:.2f}", flush=True)
json.dump(out, open(os.path.join(_r, "analysis", "pi_empty_split.json"), "w"), indent=1)
