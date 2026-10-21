"""Fold definitions for MedAgentAudit experiments (round 35).

Every question is answered by all 6 MAS x 4 LLMs, so plain leave-one-MAS-out leaks the
question (model can memorise question difficulty from other MAS): round-35 measurement,
v0 no-structure outcome AUROC 0.82-0.90 under LOMO vs 0.62 question-disjoint.
LQD = leave-one-MAS-out AND question-disjoint: questions are split once into
B (all 285 human-eval questions + 15 more by hash, 300 total) and A (the other 300);
fold m trains on MAS != m restricted to A and tests on MAS m restricted to B.
QD = all MAS, train on A, test on B (in-distribution w.r.t. MAS, question-disjoint).
"""
import hashlib


def question_halves(G, human_qids, size_b=300):
    qs = sorted({g["qid"] for g in G})
    rest = sorted((q for q in qs if q not in human_qids), key=lambda q: hashlib.md5(q.encode()).hexdigest())
    B = set(human_qids) | set(rest[:max(0, size_b - len(human_qids))])
    return set(qs) - B, B


def folds(G, human_qids, kinds=("LQD", "QD")):
    A, B = question_halves(G, human_qids); out = []
    if "LQD" in kinds:
        for m in sorted({g["mas"] for g in G}):
            out.append(("LQD:" + m, [g for g in G if g["mas"] != m and g["qid"] in A], [g for g in G if g["mas"] == m and g["qid"] in B]))
    if "QD" in kinds:
        out.append(("QD", [g for g in G if g["qid"] in A], [g for g in G if g["qid"] in B]))
    if "LOMO" in kinds:
        for m in sorted({g["mas"] for g in G}):
            out.append(("LOMO:" + m, [g for g in G if g["mas"] != m], [g for g in G if g["mas"] == m]))
    return out
