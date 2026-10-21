"""Content-free structural prior for the step label: P(step is the earliest injected | position index, role),
counted on the TRAIN split; on each test trajectory pick the argmax step. Uses no step text at all, so it is the
right control for "does the step head read content". Same subsets as strategy_split_eval.py; merged into its json."""
import collections, json, os, sys
_r = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _r)
from analysis.strategy_split_eval import acting, subset_of, wilson  # noqa: E402
from common.data import load_jsonl  # noqa: E402
from common.paths import FILES, SPLITS_JSON  # noqa: E402

sp = json.load(open(SPLITS_JSON))
path = os.path.join(_r, "analysis", "strategy_split_eval.json")
rep = json.load(open(path))
for fw in rep:
    trajs = load_jsonl(FILES[fw])
    tr_ids, te_ids = set(sp[fw]["train_task_ids"]), set(sp[fw]["test_task_ids"])
    hit, tot = collections.Counter(), collections.Counter()
    for t in trajs:
        if t.id not in tr_ids:
            continue
        for i, s in enumerate(acting(t)):
            key = (i, s.orig_agent_name if fw != "mdagents" or s.orig_agent_name != "Expert" else "Expert")
            tot[key] += 1; hit[key] += s.turn == t.labels.earliest_error_turn
    p = lambda k: (hit[k] + 0.5) / (tot[k] + 1)  # noqa: E731
    test = [t for t in trajs if t.id in te_ids and t.labels.earliest_error_turn is not None]
    pred = []
    for t in test:
        a = acting(t)
        best = max(range(len(a)), key=lambda i: (p((i, a[i].orig_agent_name)), -i))
        pred.append(a[best].turn)
    subs = [subset_of(t) for t in test]
    for sub, row in rep[fw].items():
        idx = [i for i, s in enumerate(subs) if sub in s]
        k = sum(pred[i] == test[i].labels.earliest_error_turn for i in idx)
        row["structure_prior"] = {"k": k, "rate": round(k / len(idx), 3) if idx else None, "ci95": wilson(k, len(idx))}
json.dump(rep, open(path, "w"), indent=1)
print(f"{'fw':16s}{'subset':13s}{'n':>5s}{'first':>7s}{'struct':>8s}{'tmpl':>7s}{'empty':>7s}{'MHT':>7s}  MHT-struct")
for fw, r in rep.items():
    for sub, row in r.items():
        if row["n"]:
            print(f"{fw:16s}{sub:13s}{row['n']:5d}{row['first_step']['rate']:7.2f}{row['structure_prior']['rate']:8.2f}"
                  f"{row['template']['rate']:7.2f}{row['empty']['rate']:7.2f}{row['mht_mean']:7.3f}  {row['mht_mean']-row['structure_prior']['rate']:+.3f}"
                  f"   struct CI {row['structure_prior']['ci95']}")
