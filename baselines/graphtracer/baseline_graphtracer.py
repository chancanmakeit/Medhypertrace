"""
GraphTracer structural-core reproduction (Sun et al., arXiv:2510.10581).

GraphTracer's full system has two parts:
  (a) the Information Dependency Graph (IDG) and node IMPACT SCORE
      I(v) = alpha * norm_out_degree(v) + (1 - alpha) * norm_betweenness(v),
      used to identify high-impact nodes (targets for perturbation synthesis and
      the structural signal for attribution), and
  (b) an 8B tracer LLM trained with RL (graph-structural rewards) that reads the
      trajectory and emits the root cause.

Part (b) requires multi-GPU RL training and is OUT OF SCOPE for this sandbox — run
it on your GPU box if desired (their pipeline is not open-sourced; you would have to
rebuild the synthesis + GRPO loop). This file reproduces part (a) faithfully and uses
the impact score directly as the attribution ranker: rank steps by I(v); predicted
root cause = argmax. This is the honest "GraphTracer (structural core)" baseline —
it isolates exactly the graph signal their method is built on.

IDG construction: directed edge u -> v iff step v's input explicitly references the
content produced by step u (information dependency), matching their definition of
"explicit reference extraction" as closely as our logs allow (content-signature
containment over input_messages).
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

ALPHA = 0.6   # weight on out-degree vs betweenness (paper combines the two; expose here)


def _sig(txt):
    return "".join(txt.split())[:60]


def build_idg(steps):
    """Directed info-dependency edges u->v (v consumes u's content)."""
    adj = defaultdict(set)
    sigs = [_sig(s.content) for s in steps]
    for j, s in enumerate(steps):
        joined = "".join("".join(str(m.get("content", "")).split())
                         for m in s.input_messages)
        body = "".join(s.content.split())
        hay = joined + body
        for i in range(j):
            if sigs[i] and sigs[i] in hay:
                adj[i].add(j)
    return adj


def _betweenness(adj, n):
    bc = np.zeros(n)
    for s in range(n):
        S, P = [], defaultdict(list)
        sigma = np.zeros(n); sigma[s] = 1
        d = np.full(n, -1); d[s] = 0
        Q = deque([s])
        while Q:
            v = Q.popleft(); S.append(v)
            for w in adj.get(v, ()):
                if d[w] < 0:
                    d[w] = d[v] + 1; Q.append(w)
                if d[w] == d[v] + 1:
                    sigma[w] += sigma[v]; P[w].append(v)
        delta = np.zeros(n)
        while S:
            w = S.pop()
            for v in P[w]:
                if sigma[w] > 0:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
            if w != s:
                bc[w] += delta[w]
    return bc / max(bc.max(), 1e-9)


def impact_ranking(traj, alpha=ALPHA):
    steps = [s for s in traj.steps if not s.is_input]
    n = len(steps)
    if n == 0:
        return []
    adj = build_idg(steps)
    out_deg = np.array([len(adj.get(i, ())) for i in range(n)], float)
    out_deg = out_deg / max(out_deg.max(), 1e-9)
    bc = _betweenness(adj, n)
    impact = alpha * out_deg + (1 - alpha) * bc
    order = np.argsort(-impact)
    return [(steps[i].turn, steps[i].agent_name, float(impact[i])) for i in order]


def evaluate(name, path, alpha=ALPHA):
    trajs = load_jsonl(path)
    _, te = load_split(name)
    te_trajs = [t for t in trajs if t.id in te]
    top1 = top3 = ahit = tot = 0
    for t in te_trajs:
        ranked = impact_ranking(t, alpha)
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
    print("GraphTracer (structural core: IDG + impact score), fixed test set")
    for name, path in targets.items():
        m = evaluate(name, path)
        print(f"  [{name:11s}] step Top-1={m['step_top1']:.3f} Top-3={m['step_top3']:.3f} "
              f"agent-hit@1={m['agent_hit@1']:.3f} (n={m['n']})")
