"""
Pointwise (no-structure) baseline for three-level failure attribution.

Encoder: TF-IDF over step text + light metadata (offline-safe; HF is not reachable in
this sandbox). A stronger sentence encoder can replace `StepFeaturizer.text_matrix`
later without touching the rest.

LEAKAGE CONTROL:
  * Split is BY TASK id (variants of the same question never cross train/test).
  * Features use ONLY observable signals — never injection_applied / fm_error_type /
    injection_strategy / injection_process (those are labels).

Tasks:
  agent-level : per agent-instance binary "is this instance faulty" (multi-label/traj)
  mode-level  : per agent-instance 14-way multi-label over FM types
  step-level  : rank acting steps, predict the earliest error step (Who&When "when")
Metrics mirror AEGIS: Micro-F1 / Macro-F1 for agent & mode; Top-1 / Top-3 for step.
"""

import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)

import sys
from collections import defaultdict

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics import f1_score

from common.data import load_jsonl, FM_TYPES, FM_INDEX

from common.paths import FILES
SEED = 0


# --------------------------------------------------------------------------------------
# Build a flat table of (trajectory, agent-instance) rows + a step table.
# --------------------------------------------------------------------------------------
def agent_rows(trajs):
    """One row per (traj, acting agent-instance). Text = concat of that instance's steps."""
    rows = []
    for ti, t in enumerate(trajs):
        by_inst = defaultdict(list)
        for s in t.steps:
            if not s.is_input:
                by_inst[s.instance].append(s)
        for inst, steps in by_inst.items():
            text = " ".join(s.content for s in steps)
            meta = {
                "agent_name": inst[0],
                "coarse": steps[0].coarse,
                "n_steps": len(steps),
                "mean_len": np.mean([len(s.content) for s in steps]),
                "first_turn": min(s.turn for s in steps),
                "rel_pos": min(s.turn for s in steps) / max(1, len(t.steps)),
            }
            y_agent = int(inst in t.labels.faulty_instances)
            y_mode = np.zeros(len(FM_TYPES), dtype=int)
            for fm in t.labels.instance_fms.get(inst, set()):
                if fm in FM_INDEX:
                    y_mode[FM_INDEX[fm]] = 1
            rows.append({"ti": ti, "task": t.id, "text": text, "meta": meta,
                         "y_agent": y_agent, "y_mode": y_mode})
    return rows


def featurize(rows_train, rows_all):
    tfidf = TfidfVectorizer(max_features=8000, ngram_range=(1, 2), min_df=3,
                            sublinear_tf=True)
    tfidf.fit([r["text"] for r in rows_train])
    X_text = tfidf.transform([r["text"] for r in rows_all])

    cat = [[r["meta"]["agent_name"], r["meta"]["coarse"]] for r in rows_all]
    ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=True)
    ohe.fit([[r["meta"]["agent_name"], r["meta"]["coarse"]] for r in rows_train])
    X_cat = ohe.transform(cat)

    num = np.array([[r["meta"]["n_steps"], r["meta"]["mean_len"],
                     r["meta"]["first_turn"], r["meta"]["rel_pos"]] for r in rows_all],
                   dtype=float)
    num = (num - num.mean(0)) / (num.std(0) + 1e-6)
    X = sparse.hstack([X_text, X_cat, sparse.csr_matrix(num)]).tocsr()
    return X


def task_split(trajs, test_frac=0.3, seed=SEED):
    tasks = sorted({t.id for t in trajs})
    rng = np.random.default_rng(seed)
    rng.shuffle(tasks)
    n_test = max(1, int(len(tasks) * test_frac))
    test_tasks = set(tasks[:n_test])
    tr = [i for i, t in enumerate(trajs) if t.id not in test_tasks]
    te = [i for i, t in enumerate(trajs) if t.id in test_tasks]
    return set(tr), set(te)


def run_agent_mode(trajs, name):
    tr_idx, te_idx = task_split(trajs)
    rows = agent_rows(trajs)
    rows_tr = [r for r in rows if r["ti"] in tr_idx]
    rows_te = [r for r in rows if r["ti"] in te_idx]
    X = featurize(rows_tr, rows)
    tr_mask = np.array([r["ti"] in tr_idx for r in rows])
    te_mask = ~tr_mask
    Xtr, Xte = X[tr_mask], X[te_mask]

    # ---- agent-level ----
    ya = np.array([r["y_agent"] for r in rows])
    clf = LogisticRegression(max_iter=1000, class_weight="balanced", C=1.0)
    clf.fit(Xtr, ya[tr_mask])
    pa = clf.predict(Xte)
    ya_te = ya[te_mask]
    agent_micro = f1_score(ya_te, pa, average="binary", zero_division=0)
    # majority / random lower bounds
    maj = np.full_like(ya_te, int(ya[tr_mask].mean() > 0.5))
    agent_maj = f1_score(ya_te, maj, average="binary", zero_division=0)

    # ---- mode-level (per-instance 14-way multilabel) ----
    Ym = np.stack([r["y_mode"] for r in rows])
    Ytr, Yte = Ym[tr_mask], Ym[te_mask]
    preds = np.zeros_like(Yte)
    for k in range(len(FM_TYPES)):
        if Ytr[:, k].sum() == 0:
            continue
        c = LogisticRegression(max_iter=500, class_weight="balanced")
        c.fit(Xtr, Ytr[:, k])
        preds[:, k] = c.predict(Xte)
    mode_micro = f1_score(Yte, preds, average="micro", zero_division=0)
    mode_macro = f1_score(Yte, preds, average="macro", zero_division=0)

    # role-collapsed agent metric (secondary)
    return {
        "name": name, "n_rows": len(rows), "n_test_rows": int(te_mask.sum()),
        "agent_F1": agent_micro, "agent_majority_F1": agent_maj,
        "mode_microF1": mode_micro, "mode_macroF1": mode_macro,
    }


def run_step(trajs, name):
    """Rank acting steps within each trajectory; predict earliest error step.
    Feature per step = its own tfidf/meta; label = (turn == earliest_error_turn).
    We train a step-level 'is-error' scorer and take argmax per trajectory as Top-1."""
    tr_idx, te_idx = task_split(trajs)
    # build per-step rows
    srows = []
    for ti, t in enumerate(trajs):
        acting = [s for s in t.steps if not s.is_input]
        for s in acting:
            srows.append({
                "ti": ti, "task": t.id, "turn": s.turn,
                "text": s.content,
                "meta": [len(s.content), s.turn, s.turn / max(1, len(t.steps))],
                "agent": s.agent_name, "coarse": s.coarse,
                "is_err": int(s.turn == t.labels.earliest_error_turn),
                "masked": t.labels.step_masked,
            })
    srows = [r for r in srows if not r["masked"]]
    rows_tr = [r for r in srows if r["ti"] in tr_idx]

    tfidf = TfidfVectorizer(max_features=6000, ngram_range=(1, 2), min_df=3,
                            sublinear_tf=True)
    tfidf.fit([r["text"] for r in rows_tr])
    Xt = tfidf.transform([r["text"] for r in srows])
    ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=True)
    ohe.fit([[r["agent"], r["coarse"]] for r in rows_tr])
    Xc = ohe.transform([[r["agent"], r["coarse"]] for r in srows])
    num = np.array([r["meta"] for r in srows], float)
    num = (num - num.mean(0)) / (num.std(0) + 1e-6)
    X = sparse.hstack([Xt, Xc, sparse.csr_matrix(num)]).tocsr()

    tr_mask = np.array([r["ti"] in tr_idx for r in srows])
    y = np.array([r["is_err"] for r in srows])
    clf = LogisticRegression(max_iter=1000, class_weight="balanced")
    clf.fit(X[tr_mask], y[tr_mask])
    scores = clf.decision_function(X)

    # group test rows by trajectory, compute Top-1/Top-3 hit on earliest error step
    by_traj = defaultdict(list)
    for i, r in enumerate(srows):
        if r["ti"] in te_idx:
            by_traj[r["ti"]].append((scores[i], r["turn"], r["is_err"]))
    top1 = top3 = tot = 0
    # position baseline: always guess the earliest turn
    pos_top1 = 0
    for ti, lst in by_traj.items():
        if not any(z[2] for z in lst):
            continue
        tot += 1
        order = sorted(lst, key=lambda z: -z[0])
        gold = [z[1] for z in lst if z[2] == 1]
        if order[0][1] in gold:
            top1 += 1
        if any(o[1] in gold for o in order[:3]):
            top3 += 1
        earliest_turn = min(z[1] for z in lst)
        if earliest_turn in gold:
            pos_top1 += 1
    return {"name": name, "step_top1": top1 / max(tot, 1),
            "step_top3": top3 / max(tot, 1),
            "step_earliest_pos_top1": pos_top1 / max(tot, 1),
            "n_eval_traj": tot}


if __name__ == "__main__":
    print("=" * 92)
    print("POINTWISE TF-IDF BASELINE  (task-level split, no injection features)")
    print("=" * 92)
    for name, path in FILES.items():
        trajs = load_jsonl(path)
        am = run_agent_mode(trajs, name)
        st = run_step(trajs, name)
        print(f"\n[{name}]  rows={am['n_rows']} (test {am['n_test_rows']}), "
              f"step-eval trajs={st['n_eval_traj']}")
        print(f"  agent-level  F1={am['agent_F1']:.3f}   (majority LB {am['agent_majority_F1']:.3f})")
        print(f"  mode-level   micro-F1={am['mode_microF1']:.3f}  macro-F1={am['mode_macroF1']:.3f}")
        print(f"  step-level   Top-1={st['step_top1']:.3f}  Top-3={st['step_top3']:.3f}   "
              f"(earliest-turn heuristic Top-1 {st['step_earliest_pos_top1']:.3f})")
