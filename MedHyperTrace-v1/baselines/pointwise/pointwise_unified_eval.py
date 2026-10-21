"""
Unified evaluation so ALL methods are compared with ONE metric system.

Every method (HGNN, pointwise, AEGIS-SFT, Who&When) is reduced to a per-trajectory
list of (agent_role, FM_code) pairs, then scored by the user's own
compute_metrics -> Agent / Error / Pair  ×  Micro / Macro-F1, on the fixed test set
(splits.json). This is the fair, apples-to-apples table.

Granularity: ROLE (bare agent_name), to match how AEGIS-SFT was trained on general
data. Step-level (Top-1/Top-3) is NOT here — it is a separate sub-table for methods
that predict "when" (ours + Who&When); AEGIS-SFT does not predict step at all.

This file also computes the pointwise baseline's UNIFIED numbers directly so you can
see the alignment immediately. HGNN and SFT plug in the same way (predictions dict).
"""

import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)

import json
import sys
from collections import defaultdict

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from common.data import load_jsonl, FM_TYPES, FM_INDEX
from common.aegis_metrics import compute_metrics, _norm_agent

from common.paths import DATA_DIR as DATA, SPLITS_JSON, FILES


def load_split(name):
    d = json.load(open(SPLITS_JSON))[name]
    return set(d["train_task_ids"]), set(d["test_task_ids"])


def gt_pairs_role(traj):
    """Ground-truth (role, fm) pairs at ROLE granularity."""
    return [(a, fm) for (a, ri), fms in traj.labels.instance_fms.items()
            for fm in sorted(fms)]


def score(pred_by_i, gt_by_i):
    """pred_by_i / gt_by_i: parallel lists of pair-lists. Returns AEGIS metrics dict."""
    return compute_metrics(pred_by_i, gt_by_i)


# --------------------------------------------------------------------------------------
# Pointwise pair predictor (ROLE granularity) to produce UNIFIED numbers now.
# For each (traj, role) we predict a 14-dim FM multilabel; pairs = fired (role, fm).
# --------------------------------------------------------------------------------------
def role_rows(trajs):
    rows = []
    for ti, t in enumerate(trajs):
        by_role = defaultdict(list)
        for s in t.steps:
            if not s.is_input:
                by_role[s.agent_name].append(s)      # collapse role_index -> role
        gt_fms = defaultdict(set)
        for (a, ri), fms in t.labels.instance_fms.items():
            gt_fms[a] |= fms
        for role, steps in by_role.items():
            text = " ".join(s.content for s in steps)
            y = np.zeros(len(FM_TYPES), int)
            for fm in gt_fms.get(role, set()):
                if fm in FM_INDEX:
                    y[FM_INDEX[fm]] = 1
            rows.append({"ti": ti, "task": t.id, "role": role, "text": text, "y": y})
    return rows


def run_pointwise_unified(name, path):
    trajs = load_jsonl(path)
    tr_ids, te_ids = load_split(name)
    rows = role_rows(trajs)
    tr = [r for r in rows if r["task"] in tr_ids]
    te_mask = np.array([r["task"] in te_ids for r in rows])

    tfidf = TfidfVectorizer(max_features=8000, ngram_range=(1, 2), min_df=3,
                            sublinear_tf=True)
    tfidf.fit([r["text"] for r in tr])
    X = tfidf.transform([r["text"] for r in rows])
    tr_mask = np.array([r["task"] in tr_ids for r in rows])
    Y = np.stack([r["y"] for r in rows])

    P = np.zeros((len(rows), len(FM_TYPES)), int)
    for k in range(len(FM_TYPES)):
        if Y[tr_mask, k].sum() == 0:
            continue
        c = LogisticRegression(max_iter=500, class_weight="balanced")
        c.fit(X[tr_mask], Y[tr_mask, k])
        P[:, k] = c.predict(X)

    # assemble per-trajectory predicted / gt pair lists (test only)
    te_trajs = [t for t in trajs if t.id in te_ids]
    id2idx = {id(t): j for j, t in enumerate(te_trajs)}
    pred_lists = [[] for _ in te_trajs]
    # map rows (test) to their trajectory
    ti_to_pos = {}
    for j, t in enumerate(trajs):
        if t.id in te_ids:
            ti_to_pos[j] = None
    # rebuild: need row.ti -> te position
    te_ti = {}
    pos = 0
    for j, t in enumerate(trajs):
        if t.id in te_ids:
            te_ti[j] = pos
            pos += 1
    for i, r in enumerate(rows):
        if not te_mask[i]:
            continue
        p = te_ti[r["ti"]]
        for k in range(len(FM_TYPES)):
            if P[i, k]:
                pred_lists[p].append((r["role"], FM_TYPES[k]))
    gt_lists = [gt_pairs_role(t) for t in te_trajs]
    return compute_metrics(pred_lists, gt_lists), len(te_trajs)


if __name__ == "__main__":
    import sys as _s
    json_out = None
    if "--json_out" in _s.argv:
        json_out = _s.argv[_s.argv.index("--json_out") + 1]
    print("=" * 96)
    print("UNIFIED metrics (your compute_metrics) — POINTWISE baseline, ROLE granularity,")
    print("fixed test set. Same scorer will apply to HGNN and your AEGIS-SFT outputs.")
    print("=" * 96)
    hdr = f"{'framework':<12}{'Agent-mi':>9}{'Agent-ma':>9}{'Error-mi':>9}{'Error-ma':>9}{'Pair-mi':>9}{'Pair-ma':>9}"
    print(hdr)
    dump = {}
    for name, path in FILES.items():
        m, n = run_pointwise_unified(name, path)
        print(f"{name:<12}{m['agent_micro_f1']:>9.1f}{m['agent_macro_f1']:>9.1f}"
              f"{m['error_micro_f1']:>9.1f}{m['error_macro_f1']:>9.1f}"
              f"{m['pair_micro_f1']:>9.1f}{m['pair_macro_f1']:>9.1f}   (n_test={n})")
        d = dict(m)
        d["n"] = n
        d.setdefault("step_acc", None)   # pointwise has no step prediction -> '--'
        dump.setdefault(name, {})["pointwise"] = d
    print("\nNote: 'Pair' here == what I previously loosely called 'mode' (agent+FM jointly).")
    print("      AEGIS-SFT will report the SAME six columns on the SAME test files.")
    if json_out:
        import json
        json.dump(dump, open(json_out, "w"), indent=1)
        print(f"\nwrote {json_out}")
