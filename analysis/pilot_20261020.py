"""Round 28: shortcut and pairing analysis on the medical-aegis pilot (2026-10-20).

Input: mas-traj/1 export (pilot_export.jsonl, 420 runs; medagents_mc + triage_agent x
mercury-2.5-preview / llama-4-maverick; normal K=4 x 20 questions; PI / RC injections).
Reads labels ONLY to define targets; features come from steps / task.

A. content shortcut:  does a single step's output text reveal that it was injected?
   TF-IDF(1-2 gram) + logistic regression, GroupKFold by question_id (5 folds).
   Positives = injected target steps (applied), split by strategy (RC / PI);
   negatives = steps of the SAME agent role in normal runs (role-matched, so the
   classifier cannot win by recognising the role).
B. topology shortcut: does run structure alone separate inject from normal runs?
   AUROC of #steps and of max(round).
C. role prior:        fraction of inject runs whose injected step is the modal target role.
D. flips:             final wrong while the paired normal runs are >= 50% correct.
E. natural pairing:   per (framework, backbone, question), K normal runs: share of
                      questions with both a correct and a wrong run; first divergence step
                      defined on structured.answer / esi_level / vote, aligned by
                      (agent_id, phase, round, occurrence).
Usage: python analysis/pilot_20261020.py <pilot_export.jsonl>
"""
import json, sys, collections, statistics as st
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score

rows = [json.loads(l) for l in open(sys.argv[1])]
strat = lambda r: next((x.get("strategy") for x in r["labels"].get("injection") or [] if x.get("applied")), "normal")
inj_steps = lambda r: {x["step_id"] for x in r["labels"].get("injection") or [] if x.get("applied")}

def sem(s):
    d = s.get("structured") or {}
    for k in ("answer", "esi_level", "coarse", "vote"):
        if d.get(k) is not None:
            return str(d[k])
    return None

print("=" * 30, "A. content shortcut (single-step text, role-matched negatives)")
for fw in sorted({r["framework"] for r in rows}):
    R = [r for r in rows if r["framework"] == fw]
    for sg in ("response_corruption", "prompt_injection"):
        pos = [(s["output"] or "", r["question_id"], s.get("agent_role")) for r in R if strat(r) == sg
               for s in r["steps"] if s["step_id"] in inj_steps(r)]
        roles = {p[2] for p in pos}
        neg = [(s["output"] or "", r["question_id"], s.get("agent_role")) for r in R if strat(r) == "normal"
               for s in r["steps"] if s.get("agent_role") in roles and s.get("kind") != "tool"]
        if len(pos) < 5: continue
        X = [t for t, _, _ in pos + neg]; y = np.array([1] * len(pos) + [0] * len(neg)); g = [q for _, q, _ in pos + neg]
        sc = np.zeros(len(y))
        for tr, te in GroupKFold(n_splits=5).split(X, y, g):
            v = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
            m = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced").fit(v.fit_transform([X[i] for i in tr]), y[tr])
            sc[te] = m.predict_proba(v.transform([X[i] for i in te]))[:, 1]
        print(f"  {fw:14s} {sg:20s} roles={sorted(roles)} pos={len(pos):3d} neg={len(neg):4d}  AUROC={roc_auc_score(y, sc):.3f}")

print("=" * 30, "B. topology shortcut (inject vs normal runs)")
for fw in sorted({r["framework"] for r in rows}):
    R = [r for r in rows if r["framework"] == fw]
    y = np.array([strat(r) != "normal" for r in R], int)
    ns = np.array([len(r["steps"]) for r in R]); mr = np.array([max((s.get("round") or 0) for s in r["steps"]) for r in R])
    print(f"  {fw:14s} AUROC(#steps)={roc_auc_score(y, ns):.3f}  AUROC(max round)={roc_auc_score(y, mr):.3f}  "
          f"normal #steps={sorted(collections.Counter(ns[y==0]).items())} inject #steps={sorted(collections.Counter(ns[y==1]).items())}")

print("=" * 30, "C. role prior for step localisation")
for fw in sorted({r["framework"] for r in rows}):
    R = [r for r in rows if r["framework"] == fw and strat(r) != "normal"]
    roles = collections.Counter((s.get("agent_id"), s.get("phase")) for r in R for s in r["steps"] if s["step_id"] in inj_steps(r))
    top = roles.most_common(1)[0]
    print(f"  {fw:14s} inject runs={len(R)}  target (agent_id, phase) distribution={dict(roles)}  -> modal-role prior hits {top[1]}/{sum(roles.values())}")

print("=" * 30, "D. flips vs paired normal runs")
by_id = {r["run_id"]: r for r in rows}
grp = collections.defaultdict(list)
for r in rows:
    if strat(r) != "normal": grp[(r["framework"], r["model"]["name"], strat(r))].append(r)
for k, R in sorted(grp.items()):
    flips = wrong = elig = 0
    for r in R:
        pn = [by_id[i] for i in r["labels"].get("paired_normal_run_ids") or [] if i in by_id]
        acc = st.mean(x["labels"]["is_correct"] for x in pn) if pn else None
        wrong += not r["labels"]["is_correct"]
        if acc is not None and acc >= 0.5:
            elig += 1; flips += not r["labels"]["is_correct"]
    print(f"  {k[0]:14s} {k[1]:20s} {k[2]:20s} runs={len(R):2d} final wrong={wrong:2d}  flip={flips}/{elig} (eligible: paired normal acc>=0.5)")

print("=" * 30, "E. natural pairing among K normal runs")
q = collections.defaultdict(list)
for r in rows:
    if strat(r) == "normal": q[(r["framework"], r["model"]["name"], r["question_id"])].append(r)
for fw_bk in sorted({k[:2] for k in q}):
    Q = [v for k, v in q.items() if k[:2] == fw_bk]
    mixed = [v for v in Q if len({x["labels"]["is_correct"] for x in v}) == 2]
    div = collections.Counter(); sem_cov = []
    for v in mixed:
        ok = [x for x in v if x["labels"]["is_correct"]]; bad = [x for x in v if not x["labels"]["is_correct"]]
        for a in ok:
            for b in bad:
                def keyed(r):
                    seen = collections.Counter(); out = []
                    for s in r["steps"]:
                        k = (s.get("agent_id"), s.get("phase"), s.get("round")); seen[k] += 1
                        out.append(((*k, seen[k]), sem(s)))
                    return out
                A, B = dict(keyed(a)), dict(keyed(b))
                order = [k for k, _ in keyed(a)]
                first = next((k for k in order if k in B and A[k] is not None and B[k] is not None and A[k] != B[k]), None)
                div[(first[0], first[1]) if first else ("<none: no semantic divergence on aligned steps>",)] += 1
                sem_cov.append(sum(1 for k in order if A[k] is not None) / len(order))
    print(f"  {fw_bk[0]:14s} {fw_bk[1]:20s} questions={len(Q)} mixed (correct & wrong among K=4)={len(mixed)}  "
          f"semantic-field coverage of aligned steps={st.mean(sem_cov) if sem_cov else 0:.2f}")
    for k, n in div.most_common(6):
        print(f"      first divergence at {k}: {n} pairs")
