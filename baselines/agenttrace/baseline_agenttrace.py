"""
AgentTrace reproduction (Wang et al., arXiv:2603.14688) — deterministic root-cause
localization, implemented from the paper's spec (the repo cited in the paper's
reproducibility statement is not publicly reachable, so this follows the described
algorithm exactly; no LLM involved).

Method per the paper:
  1. Build a CAUSAL GRAPH over execution events (here: acting steps) with three edge
     types: sequential (execution order), communication (message passing between
     agents), and data dependency (shared artifacts / content reuse).
  2. From the failure event (the final output), run BACKWARD BFS to collect the
     causal ancestor set = root-cause candidates.
  3. Rank candidates by a WEIGHTED LINEAR SCORE over five feature groups
     (group weights from the paper): position 0.70, structural 0.20, content 0.05,
     flow 0.03, confidence 0.02.
  4. Output a ranked list of candidate root-cause steps (we score Top-1/Top-3 against
     the earliest injected step, and agent-hit of the top-1 step).

Feature groups (17 features condensed to the paper's groups; exact per-feature
definitions are not fully enumerated in the paper text, so each group uses the
canonical signals it names):
  position   : earliness (1 - idx/N), graph distance to failure node, is agent's first step
  structural : out-degree, betweenness centrality, #descendants reaching the failure
  content    : error/uncertainty keyword rate, length z-score
  flow       : out-degree change vs previous step of same agent (branching anomaly)
  confidence : hedging-language marker rate ("might", "unsure", "possibly", ...)
"""
import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)

import sys
from collections import defaultdict, deque

import numpy as np

from common.data import load_jsonl
from common.paths import FILES
from common.splits import load_split

W = {"position": 0.70, "structural": 0.20, "content": 0.05,
     "flow": 0.03, "confidence": 0.02}

_ERR_KW = ("error", "wrong", "incorrect", "mistake", "fail", "cannot", "unable",
           "contradict", "inconsistent")
_HEDGE_KW = ("might", "may", "possibly", "perhaps", "unsure", "not sure", "unclear",
             "i think", "likely", "assume")


def _sig(txt):
    return "".join(txt.split())[:60]


def build_causal_graph(steps):
    """Return adjacency (u->v sets) over step indices with the paper's 3 edge types."""
    n = len(steps)
    adj = defaultdict(set)
    radj = defaultdict(set)

    def add(u, v):
        if u != v:
            adj[u].add(v)
            radj[v].add(u)

    # 1) sequential: execution order
    for i in range(n - 1):
        add(i, i + 1)
    # 2) communication: step j consumed content of step i (input_messages containment)
    sigs = [_sig(s.content) for s in steps]
    for j, s in enumerate(steps):
        joined = "".join("".join(str(m.get("content", "")).split())
                         for m in s.input_messages)
        if not joined:
            continue
        for i in range(j):
            if sigs[i] and sigs[i] in joined and steps[i].agent_name != s.agent_name:
                add(i, j)
    # 3) data dependency: content reuse regardless of agent (shared artifact)
    for j, s in enumerate(steps):
        body = "".join(s.content.split())
        for i in range(j):
            if sigs[i] and sigs[i] in body:
                add(i, j)
    return adj, radj


def _betweenness(adj, n):
    """Brandes betweenness on the (small) DAG-ish graph."""
    bc = np.zeros(n)
    for s in range(n):
        S, P = [], defaultdict(list)
        sigma = np.zeros(n); sigma[s] = 1
        d = np.full(n, -1); d[s] = 0
        Q = deque([s])
        while Q:
            v = Q.popleft(); S.append(v)
            for w_ in adj.get(v, ()):
                if d[w_] < 0:
                    d[w_] = d[v] + 1; Q.append(w_)
                if d[w_] == d[v] + 1:
                    sigma[w_] += sigma[v]; P[w_].append(v)
        delta = np.zeros(n)
        while S:
            w_ = S.pop()
            for v in P[w_]:
                if sigma[w_] > 0:
                    delta[v] += (sigma[v] / sigma[w_]) * (1 + delta[w_])
            if w_ != s:
                bc[w_] += delta[w_]
    return bc / max(bc.max(), 1e-9)


def rank_root_causes(traj):
    steps = [s for s in traj.steps if not s.is_input]
    n = len(steps)
    if n == 0:
        return []
    adj, radj = build_causal_graph(steps)
    failure = n - 1                                   # final output event

    # backward BFS -> candidate ancestors (incl. failure itself, per paper's ranking)
    cand = set()
    Q = deque([failure])
    while Q:
        v = Q.popleft()
        for u in radj.get(v, ()):
            if u not in cand:
                cand.add(u); Q.append(u)
    cand.add(failure)
    cand = sorted(cand)

    # graph distance to failure (backward)
    dist = {failure: 0}
    Q = deque([failure])
    while Q:
        v = Q.popleft()
        for u in radj.get(v, ()):
            if u not in dist:
                dist[u] = dist[v] + 1; Q.append(u)
    maxd = max(dist.values()) if dist else 1

    out_deg = np.array([len(adj.get(i, ())) for i in range(n)], float)
    out_deg_n = out_deg / max(out_deg.max(), 1e-9)
    bc = _betweenness(adj, n)
    # descendants reaching failure
    desc_hit = np.zeros(n)
    for i in cand:
        desc_hit[i] = 1.0
    lens = np.array([len(s.content) for s in steps], float)
    lz = np.abs((lens - lens.mean()) / (lens.std() + 1e-9))
    lz = lz / max(lz.max(), 1e-9)

    first_of_agent = {}
    for i, s in enumerate(steps):
        first_of_agent.setdefault(s.agent_name, i)

    prev_out = {}
    scores = []
    for i in cand:
        s = steps[i]
        low = s.content.lower()
        # position group
        earliness = 1.0 - i / max(n - 1, 1)
        dist_norm = dist.get(i, maxd) / max(maxd, 1)
        is_first = 1.0 if first_of_agent[s.agent_name] == i else 0.0
        f_pos = (earliness + dist_norm + is_first) / 3
        # structural group
        f_str = (out_deg_n[i] + bc[i] + desc_hit[i]) / 3
        # content group
        kw = sum(low.count(k) for k in _ERR_KW) / max(len(low.split()), 1)
        f_con = min(kw * 20, 1.0) * 0.5 + lz[i] * 0.5
        # flow group: branching anomaly vs this agent's previous step
        po = prev_out.get(s.agent_name)
        f_flow = abs(out_deg_n[i] - po) if po is not None else 0.0
        prev_out[s.agent_name] = out_deg_n[i]
        # confidence group
        hg = sum(low.count(k) for k in _HEDGE_KW) / max(len(low.split()), 1)
        f_conf = min(hg * 20, 1.0)

        score = (W["position"] * f_pos + W["structural"] * f_str +
                 W["content"] * f_con + W["flow"] * f_flow +
                 W["confidence"] * f_conf)
        scores.append((score, i))
    scores.sort(reverse=True)
    return [(steps[i].turn, steps[i].agent_name, sc) for sc, i in scores]


def evaluate(name, path):
    trajs = load_jsonl(path)
    _, te = load_split(name)
    te_trajs = [t for t in trajs if t.id in te]
    top1 = top3 = ahit = tot = 0
    for t in te_trajs:
        ranked = rank_root_causes(t)
        if not ranked or t.labels.earliest_error_turn is None:
            continue
        tot += 1
        gold = t.labels.earliest_error_turn
        turns = [r[0] for r in ranked]
        if turns[0] == gold:
            top1 += 1
        if gold in turns[:3]:
            top3 += 1
        faulty_roles = {r for (r, _) in t.labels.faulty_instances}
        if ranked[0][1] in faulty_roles:
            ahit += 1
    return {"step_top1": top1 / max(tot, 1), "step_top3": top3 / max(tot, 1),
            "agent_hit@1": ahit / max(tot, 1), "n": tot}


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    targets = FILES if which == "all" else {which: FILES[which]}
    print("AgentTrace reproduction (deterministic causal-graph RCA, fixed test set)")
    for name, path in targets.items():
        m = evaluate(name, path)
        print(f"  [{name:11s}] step Top-1={m['step_top1']:.3f} Top-3={m['step_top3']:.3f} "
              f"agent-hit@1={m['agent_hit@1']:.3f} (n={m['n']})")
