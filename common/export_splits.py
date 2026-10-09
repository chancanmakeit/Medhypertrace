"""Export the FIXED train/test split (task-id level) so every baseline evaluates on
the identical test set. Writes splits.json. All baselines import load_split() from here."""

import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)

import json, sys
import numpy as np
from common.data import load_jsonl

from common.paths import DATA_DIR as DATA, SPLITS_JSON, FILES
TEST_FRAC = 0.3
SEED = 0

def make_split(trajs, test_frac=TEST_FRAC, seed=SEED):
    tasks = sorted({t.id for t in trajs})          # distinct TASK ids (not variants)
    rng = np.random.default_rng(seed)
    rng.shuffle(tasks)
    n_test = max(1, int(len(tasks) * test_frac))
    test_tasks = sorted(tasks[:n_test])
    train_tasks = sorted(tasks[n_test:])
    return train_tasks, test_tasks

def regenerate():
    splits = {}
    for name, path in FILES.items():
        trajs = load_jsonl(path)
        tr, te = make_split(trajs)
        # variant counts per split (records), to show the leakage-free grouping
        tr_recs = sum(1 for t in trajs if t.id in set(tr))
        te_recs = sum(1 for t in trajs if t.id in set(te))
        splits[name] = {
            "seed": SEED, "test_frac": TEST_FRAC,
            "n_tasks_total": len({t.id for t in trajs}),
            "n_train_tasks": len(tr), "n_test_tasks": len(te),
            "n_train_records": tr_recs, "n_test_records": te_recs,
            "train_task_ids": tr, "test_task_ids": te,
        }
        print(f"[{name}] tasks {len(tr)+len(te)} -> train {len(tr)} / test {len(te)} "
              f"| records train {tr_recs} / test {te_recs}")

    with open(SPLITS_JSON, "w") as f:
        json.dump(splits, f, indent=2, ensure_ascii=False)
    print("\nwrote splits.json")
    return splits

# helper other scripts import
def load_split(name):
    with open(SPLITS_JSON) as f:
        s = json.load(f)[name]
    return set(s["train_task_ids"]), set(s["test_task_ids"])

if __name__ == "__main__":
    regenerate()
