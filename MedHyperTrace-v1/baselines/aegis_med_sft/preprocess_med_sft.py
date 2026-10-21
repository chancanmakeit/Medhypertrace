"""
Build AEGIS-med-SFT training data from our medical MAS dataset.

Produces verl 0.7 SFT parquets (messages format) + per-framework eval jsonls, for
either output variant, using the FIXED task-level split (splits.json) so the SFT is
trained/evaluated on exactly the same tasks as our HGNN (no leakage, comparable).

Train = union of the three frameworks' train tasks (mixed-benchmark SFT, like AEGIS).
A val_frac of TRAIN tasks is held out by task id. Test = each framework's test tasks.

Usage:
  python preprocess_med_sft.py --variant no_step   --agent_key instance --out data_med_nostep
  python preprocess_med_sft.py --variant with_step --agent_key instance --out data_med_withstep

Then on your GPU box, point train_sft-v2.sh at the produced sft/ parquets:
  DATA_DIR=./data_med_nostep bash train_sft-v2.sh ./data_med_nostep ./outputs/aegis-med-sft
(The script reads $DATA_DIR/sft/{train,val}.parquet with data.messages_key=messages.)
"""
from __future__ import annotations

import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)


import argparse
import json
import os
import random
import sys

import pandas as pd

from common.data import load_jsonl
from baselines.aegis_med_sft.aegis_med import build_prompt, build_target_json

from common.paths import FILES, SPLITS_JSON


def load_splits():
    return json.load(open(SPLITS_JSON))


def sft_row(traj, variant, agent_key):
    return {
        "messages": [
            {"role": "user", "content": build_prompt(traj, variant, agent_key)},
            {"role": "assistant", "content": build_target_json(traj, variant, agent_key)},
        ],
        "id": traj.id,
        "framework": traj.framework,
    }


def eval_row(traj, variant, agent_key):
    """Bridge-schema row for evaluation (GT carried in output.faulty_agents,
    incl. earliest_error_step when variant=with_step)."""
    tgt = json.loads(build_target_json(traj, variant, agent_key))
    acting = [s for s in traj.steps if not s.is_input]
    conv = [{"step": s.turn,
             "agent_name": (f"{s.agent_name} {s.role_index}" if agent_key == "instance"
                            else s.agent_name),
             "content": s.content} for s in acting]
    return {
        "id": traj.id,
        "metadata": {"framework": traj.framework, "benchmark": traj.framework,
                     "num_agents": len(traj.instances)},
        "input": {"query": traj.query, "conversation_history": conv,
                  "final_output": traj.final_response},
        "output": tgt,   # {"faulty_agents":[{agent_name,error_type}], "earliest_error_step": N}
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["no_step", "with_step"], default="no_step")
    ap.add_argument("--agent_key", choices=["instance", "role"], default="instance")
    ap.add_argument("--out", default="data_med")
    ap.add_argument("--val_frac", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    splits = load_splits()
    os.makedirs(os.path.join(args.out, "sft"), exist_ok=True)
    os.makedirs(os.path.join(args.out, "eval"), exist_ok=True)

    # ---- gather train trajectories across frameworks (train tasks only) ----
    train_trajs, test_by_fw = [], {}
    for name, path in FILES.items():
        trajs = load_jsonl(path)
        tr_ids = set(splits[name]["train_task_ids"])
        te_ids = set(splits[name]["test_task_ids"])
        train_trajs += [t for t in trajs if t.id in tr_ids]
        test_by_fw[name] = [t for t in trajs if t.id in te_ids]

    # ---- task-level val holdout from train ----
    train_tasks = sorted({t.id for t in train_trajs})
    rng = random.Random(args.seed)
    rng.shuffle(train_tasks)
    n_val = max(1, int(len(train_tasks) * args.val_frac))
    val_tasks = set(train_tasks[:n_val])
    tr = [t for t in train_trajs if t.id not in val_tasks]
    va = [t for t in train_trajs if t.id in val_tasks]

    pd.DataFrame([sft_row(t, args.variant, args.agent_key) for t in tr]).to_parquet(
        os.path.join(args.out, "sft", "train.parquet"), index=False)
    pd.DataFrame([sft_row(t, args.variant, args.agent_key) for t in va]).to_parquet(
        os.path.join(args.out, "sft", "val.parquet"), index=False)
    print(f"SFT[{args.variant}/{args.agent_key}] train={len(tr)} val={len(va)} "
          f"(train_tasks={len(train_tasks)-n_val}, val_tasks={n_val})")

    # ---- per-framework eval jsonls (test tasks) ----
    for name, trajs in test_by_fw.items():
        rows = [eval_row(t, args.variant, args.agent_key) for t in trajs]
        p = os.path.join(args.out, "eval", f"med_{name}.jsonl")
        with open(p, "w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"  eval[{name}] {len(rows)} samples -> {p}")


if __name__ == "__main__":
    main()
