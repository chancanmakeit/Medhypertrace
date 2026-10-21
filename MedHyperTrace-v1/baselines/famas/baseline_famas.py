"""
FAMAS baseline (Ge, Xie, Li, Pei, Zhang; arXiv:2509.13782, "Who is Introducing the
Failure? Automatically Attributing Failures of Multi-Agent Systems via Spectrum
Analysis").

Spectrum-based failure attribution: given a failing trajectory tau_0, gather a
population of runs of the SAME task, abstract every step into an
<AGENT, ACTION-STATE-cluster> triple, build coverage/frequency matrices, and rank
the triples of tau_0 by the paper's suspiciousness formula. Exact formulas
(Eq. 2-8 of the paper, implemented verbatim):

    gamma      = nc_eta / nc_agent                              (Eq. 2)
    beta       = f_eta / f_agent                                (Eq. 3)
    alpha      = 1 + log_{1/lambda}(f_{0j})                     (Eq. 4)
    n^l_cf     = sum_p lambda^{f_pj - 1}   over failing p with f_pj > 0
    n^l_cs     = likewise over succeeding p                     (Eq. 5)
    K2^lambda  = 1/2 * ( n^l_cf / (n^l_cf + n_uf)
                       + n^l_cf / (n^l_cf + n^l_cs) )           (Eq. 7)
    S(eta)     = [alpha * K2^lambda] * [1 + beta] * [1 + gamma] (Eq. 6)

Ranking: triples of tau_0 in descending S; top-1 = attribution (paper's strict
criterion). Paper config: k = 20 replays, lambda = 0.9.

============================ ADAPTATION NOTES (read!) =============================
The original FAMAS REPLAYS the unmodified MAS k times per task (~105 min/case; the
replay + LLM abstraction stage is the bottleneck). Our dataset is static, so this
implementation supports three population sources:

  --population variants   (default, runnable NOW) the failing population for a task
      = the OTHER injected variants of the same task in the dataset. DEVIATION from
      the paper: these are differently-injected runs, not replays of an unmodified
      system; and with no successful runs available, n^l_cs = 0 (Kulczynski2 stays
      well-defined -- this is exactly why FAMAS-Tarantula collapsed in their RQ2 --
      but the success contrast is absent). Treat these numbers as the
      "variant-spectrum" preliminary.
  --success_dir DIR       add successful trajectories (jsonl per framework, same
      schema, e.g. produced by your AEGIS runners with clean configs) to restore the
      success contrast (n^l_cs > 0).
  --replay_dir DIR        the faithful mode: point at replay logs you generate on
      your GPU/API box (jsonl per framework; each record needs the task `id`,
      `conversation_history` in the dataset schema, and a boolean `success`).

Abstraction: our logs are structured, so AGENT comes for free (no LLM parsing
needed). ACTION-STATE clustering is done per agent group (as in the paper) with
TF-IDF cosine + greedy threshold clustering (deterministic, local) instead of LLM
semantic clustering; --cluster_thresh controls granularity. An LLM clustering hook
can be added on your side if you want full fidelity to their Qwen2.5-72B setup.

Scoring: top-1 triple -> its agent (agent-hit vs faulty role set) and the earliest
step of that triple in tau_0 (vs earliest injected step, our unified step metric);
we also report step Top-3 via the top-3 distinct triples.
"""
import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)

import argparse
import math
import os
from collections import defaultdict

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from common.data import load_jsonl
from common.paths import FILES
from common.splits import load_split

LAMBDA = 0.9          # paper default (RQ3 optimum 0.9-0.95)
CLUSTER_THRESH = 0.6  # cosine threshold for greedy action-state clustering


# ------------------------------------------------------------------ abstraction
def cluster_actions(pop_steps, thresh=CLUSTER_THRESH):
    """Per-agent greedy cosine clustering of step contents (paper Step 1.2:
    group by agent first, then cluster action-state descriptions).
    pop_steps: list of (traj_idx, step) across the population.
    Returns {(traj_idx, turn): triple_id}, triple_id = f"{agent_name}::c{cid}"."""
    by_agent = defaultdict(list)
    for ti, s in pop_steps:
        by_agent[s.agent_name].append((ti, s))
    assign = {}
    for agent, items in by_agent.items():
        texts = [s.content[:2000] for _, s in items]
        if len(texts) == 1:
            assign[(items[0][0], items[0][1].turn)] = f"{agent}::c0"
            continue
        try:
            X = TfidfVectorizer(max_features=2048).fit_transform(texts)
            sim = cosine_similarity(X)
        except ValueError:                     # all-empty vocabulary
            for ti, s in items:
                assign[(ti, s.turn)] = f"{agent}::c0"
            continue
        cid_of = [-1] * len(items)
        reps = []                              # (cluster_id, rep_index)
        for i in range(len(items)):
            best, best_sim = -1, thresh
            for cid, r in reps:
                if sim[i, r] >= best_sim:
                    best, best_sim = cid, sim[i, r]
            if best < 0:
                best = len(reps)
                reps.append((best, i))
            cid_of[i] = best
        for (ti, s), cid in zip(items, cid_of):
            assign[(ti, s.turn)] = f"{agent}::c{cid}"
    return assign


# ------------------------------------------------------------------ spectrum core
def famas_rank(trajs_steps, outcomes, lam=LAMBDA):
    """trajs_steps: list over population of [triple_id per step] (index 0 = tau_0,
    which must be failing). outcomes: list of 0(fail)/1(success).
    Returns triples of tau_0 sorted by descending S (paper Eq. 6)."""
    universe = sorted({t for traj in trajs_steps for t in traj})
    idx = {t: j for j, t in enumerate(universe)}
    P, m = len(trajs_steps), len(universe)
    F = np.zeros((P, m))
    for p, traj in enumerate(trajs_steps):
        for t in traj:
            F[p, idx[t]] += 1
    C = (F > 0).astype(float)
    O = np.array(outcomes)

    agents = sorted({t.split("::")[0] for t in universe})
    aidx = {a: i for i, a in enumerate(agents)}
    a_of = np.array([aidx[t.split("::")[0]] for t in universe])
    F_ag = np.zeros((P, len(agents)))
    C_ag = np.zeros((P, len(agents)))
    for j in range(m):
        F_ag[:, a_of[j]] += F[:, j]
    C_ag = (F_ag > 0).astype(float)

    fail_rows = np.where(O == 0)[0]
    succ_rows = np.where(O == 1)[0]

    scores = {}
    for t in set(trajs_steps[0]):              # only triples present in tau_0
        j = idx[t]
        a = a_of[j]
        # Eq. 2 / Eq. 3
        gamma = C[:, j].sum() / max(C_ag[:, a].sum(), 1e-9)
        beta = F[:, j].sum() / max(F_ag[:, a].sum(), 1e-9)
        # Eq. 4 (log base 1/lam; f_{0j} >= 1 since t occurs in tau_0)
        alpha = 1.0 + math.log(max(F[0, j], 1.0)) / math.log(1.0 / lam)
        # Eq. 5
        n_cf = sum(lam ** (F[p, j] - 1) for p in fail_rows if F[p, j] > 0)
        n_cs = sum(lam ** (F[p, j] - 1) for p in succ_rows if F[p, j] > 0)
        n_uf = sum(1 for p in fail_rows if F[p, j] == 0)
        # Eq. 7 (n_uf is the plain count, per paper)
        if n_cf <= 0:
            k2 = 0.0
        else:
            k2 = 0.5 * (n_cf / (n_cf + n_uf) + n_cf / (n_cf + n_cs))
        # Eq. 6
        scores[t] = (alpha * k2) * (1.0 + beta) * (1.0 + gamma)
    return sorted(scores.items(), key=lambda kv: -kv[1])


# ------------------------------------------------------------------ evaluation
def _acting(t):
    return [s for s in t.steps if not s.is_input]


def evaluate(name, path, population="variants", success_dir=None, replay_dir=None,
             lam=LAMBDA, thresh=CLUSTER_THRESH, max_pop=30, limit=None, seed=0):
    trajs = load_jsonl(path)
    _, te = load_split(name)
    te_trajs = [t for t in trajs if t.id in te]
    if limit:
        te_trajs = te_trajs[:limit]

    by_task = defaultdict(list)
    for i, t in enumerate(trajs):
        by_task[t.id].append(t)

    extra = defaultdict(list)                   # task -> [(traj, outcome)]
    for d, out in ((success_dir, 1), (replay_dir, None)):
        if not d:
            continue
        f = os.path.join(d, f"{name}.jsonl")
        if os.path.exists(f):
            for t in load_jsonl(f):
                o = out if out is not None else int(getattr(t, "success", 0))
                extra[t.id].append((t, o))

    rng = np.random.default_rng(seed)
    a_hit = s1 = s3 = tot = 0
    for t0 in te_trajs:
        pop = [(t0, 0)]
        others = [x for x in by_task[t0.id] if x is not t0]
        if population == "variants":
            if len(others) > max_pop:
                others = list(rng.choice(np.array(others, dtype=object),
                                         max_pop, replace=False))
            pop += [(x, 0) for x in others]
        pop += extra.get(t0.id, [])
        if len(pop) < 2:
            continue

        pop_steps = [(pi, s) for pi, (tr, _) in enumerate(pop) for s in _acting(tr)]
        assign = cluster_actions(pop_steps, thresh)
        trajs_steps = [[assign[(pi, s.turn)] for s in _acting(tr)]
                       for pi, (tr, _) in enumerate(pop)]
        ranked = famas_rank(trajs_steps, [o for _, o in pop], lam)
        if not ranked:
            continue
        tot += 1
        gold = t0.labels.earliest_error_turn
        faulty = {r for (r, _) in t0.labels.faulty_instances}
        # top-1 triple -> agent + earliest step of that triple in tau_0
        acting0 = _acting(t0)
        def earliest_turn(trip):
            return min(s.turn for s in acting0
                       if assign[(0, s.turn)] == trip)
        top_agent = ranked[0][0].split("::")[0]
        if top_agent in faulty:
            a_hit += 1
        turns_top3 = [earliest_turn(trip) for trip, _ in ranked[:3]]
        if turns_top3 and turns_top3[0] == gold:
            s1 += 1
        if gold in turns_top3:
            s3 += 1
    return {"agent_hit@1": a_hit / max(tot, 1), "step_top1": s1 / max(tot, 1),
            "step_top3": s3 / max(tot, 1), "n": tot}


# ------------------------------------------------------------------ self-test
def selftest():
    """Synthetic mini-spectrum with a known culprit: appears (repeatedly) in every
    failing run, never in successes; a ubiquitous planning action appears once
    everywhere. The culprit must rank first."""
    fail = [["Orch::plan", "Web::bad_search", "Web::bad_search", "File::read"],
            ["Orch::plan", "Web::bad_search", "File::read"],
            ["Orch::plan", "Web::bad_search", "Web::bad_search"]]
    succ = [["Orch::plan", "Web::good_search", "File::read"],
            ["Orch::plan", "Web::good_search"]]
    ranked = famas_rank(fail + succ, [0, 0, 0, 1, 1])
    names = [t for t, _ in ranked]
    assert names[0] == "Web::bad_search", f"selftest FAILED: {ranked}"
    assert dict(ranked)["Web::bad_search"] > dict(ranked)["Orch::plan"]
    print("selftest OK — culprit ranked #1:",
          [(t, round(s, 3)) for t, s in ranked])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--population", choices=["variants"], default="variants")
    ap.add_argument("--success_dir", default=None)
    ap.add_argument("--replay_dir", default=None)
    ap.add_argument("--lam", type=float, default=LAMBDA)
    ap.add_argument("--cluster_thresh", type=float, default=CLUSTER_THRESH)
    ap.add_argument("--max_pop", type=int, default=30)
    ap.add_argument("--frameworks", nargs="+", default=list(FILES))
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    if args.selftest:
        selftest()
        raise SystemExit(0)
    mode = "variants" + (" + successes" if args.success_dir else
                         "" if not args.replay_dir else " + replays")
    print(f"FAMAS (spectrum, population={mode}, lambda={args.lam}) — fixed test set")
    for name in args.frameworks:
        m = evaluate(name, FILES[name], population=args.population,
                     success_dir=args.success_dir, replay_dir=args.replay_dir,
                     lam=args.lam, thresh=args.cluster_thresh,
                     max_pop=args.max_pop, limit=args.limit)
        print(f"  [{name:11s}] agent-hit@1={m['agent_hit@1']:.3f} "
              f"step Top-1={m['step_top1']:.3f} Top-3={m['step_top3']:.3f} (n={m['n']})")
