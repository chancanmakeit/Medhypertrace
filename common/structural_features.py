"""
Structural prior features per acting step (improvement C).

These are the signals GraphTracer and AgentTrace hand-weight; here they become node
features so the hypergraph model LEARNS how to fuse them (vs. AgentTrace's fixed
position weight 0.70 / GraphTracer's fixed alpha). 7 dims per step:

  0 earliness          1 - idx/(N-1)
  1 dist_to_failure    normalized backward-BFS distance to the final step
  2 out_degree         normalized, on the info-dependency graph (IDG)
  3 betweenness        normalized Brandes betweenness on the IDG
  4 impact             0.6*out_degree + 0.4*betweenness  (GraphTracer's score)
  5 is_first_of_agent  1 if this is the agent's first step
  6 len_z              |content length z-score| (normalized)

Agent/phase nodes receive zeros for these dims.
"""
import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)

from collections import defaultdict, deque

import numpy as np

N_STRUCT = 7


def _sig(txt):
    return "".join(txt.split())[:60]


def _idg(steps):
    adj = defaultdict(set)
    radj = defaultdict(set)
    sigs = [_sig(s.content) for s in steps]
    for j, s in enumerate(steps):
        joined = "".join("".join(str(m.get("content", "")).split())
                         for m in s.input_messages)
        body = "".join(s.content.split())
        hay = joined + body
        for i in range(j):
            if sigs[i] and sigs[i] in hay:
                adj[i].add(j)
                radj[j].add(i)
    return adj, radj


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


def structural_features(steps):
    """steps: acting Step list (chronological). Returns [n, N_STRUCT] float32."""
    n = len(steps)
    if n == 0:
        return np.zeros((0, N_STRUCT), np.float32)
    adj, radj = _idg(steps)
    out_deg = np.array([len(adj.get(i, ())) for i in range(n)], float)
    out_deg = out_deg / max(out_deg.max(), 1e-9)
    bc = _betweenness(adj, n)
    impact = 0.6 * out_deg + 0.4 * bc

    dist = {n - 1: 0}
    Q = deque([n - 1])
    while Q:
        v = Q.popleft()
        for u in radj.get(v, ()):
            if u not in dist:
                dist[u] = dist[v] + 1; Q.append(u)
    maxd = max(dist.values()) if dist else 1

    lens = np.array([len(s.content) for s in steps], float)
    lz = np.abs((lens - lens.mean()) / (lens.std() + 1e-9))
    lz = lz / max(lz.max(), 1e-9)

    first = {}
    for i, s in enumerate(steps):
        first.setdefault(s.agent_name, i)

    F = np.zeros((n, N_STRUCT), np.float32)
    for i, s in enumerate(steps):
        F[i, 0] = 1.0 - i / max(n - 1, 1)
        F[i, 1] = dist.get(i, maxd) / max(maxd, 1)
        F[i, 2] = out_deg[i]
        F[i, 3] = bc[i]
        F[i, 4] = impact[i]
        F[i, 5] = 1.0 if first[s.agent_name] == i else 0.0
        F[i, 6] = lz[i]
    return F


# Optional: structural features + one appended factuality dim (S- tier). Kept as a
# SEPARATE function so the default pipeline (structural_features) is byte-identical.
# With the Null provider this returns exactly the 7 structural dims + a zero column,
# so enabling the plumbing without a real detector does not change learned behaviour
# beyond adding a constant-zero feature.
N_STRUCT_FACT = N_STRUCT + 1


def structural_features_with_factuality(steps, provider=None, context: str = ""):
    """[n, N_STRUCT+1]: the 7 structural priors plus a factuality suspiciousness dim in
    [0,1] from a pluggable provider (see common/factuality_provider.py). provider=None
    -> Null (zero column). Only the step (acting) nodes get a score; agent/phase nodes
    receive 0 for this dim as they do for the structural dims."""
    base = structural_features(steps)                       # [n, 7]
    if provider is None:
        from common.factuality_provider import NullFactualityProvider
        provider = NullFactualityProvider()
    fact = provider.score_steps(steps, context).astype(np.float32).reshape(-1, 1)  # [n,1]
    if fact.shape[0] != base.shape[0]:
        fact = np.zeros((base.shape[0], 1), np.float32)
    return np.concatenate([base, fact], axis=1)             # [n, 8]
