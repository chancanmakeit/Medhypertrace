"""Fixed task-level split loader — every method reads the SAME train/test tasks."""
import json
from common.paths import SPLITS_JSON

def load_split(name):
    d = json.load(open(SPLITS_JSON))[name]
    return set(d["train_task_ids"]), set(d["test_task_ids"])
