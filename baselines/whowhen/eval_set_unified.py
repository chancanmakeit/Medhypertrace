r"""
Unified evaluation under ONE metric family for every method.

All methods produce, per trajectory, a SET of (agent, FM) pairs. We score with:

  * Agent-Micro-F1  — set overlap at the agent level, pooled over all trajectories
  * Error-Micro-F1  — set overlap at the failure-mode level, pooled
  * (optionally Pair / Macro via compute_metrics — same call returns them)
  * Step-Accuracy   — earliest predicted faulty step == earliest injected step

Why this metric family (formulas, for the paper):

  Let a trajectory have predicted pair-set P and ground-truth pair-set G.
  Project to a level L in {agent, error, pair}:  P_L, G_L are the sets at that level
  (agent: keep agent names; error: keep FM codes; pair: keep full pairs).

    TP_i = |P_L,i ∩ G_L,i|      FP_i = |P_L,i \ G_L,i|      FN_i = |G_L,i \ P_L,i|

  MICRO-F1 pools counts across all N trajectories first, then forms one F1:
    P_micro = Σ_i TP_i / Σ_i (TP_i + FP_i)
    R_micro = Σ_i TP_i / Σ_i (TP_i + FN_i)
    Micro-F1 = 2 · P_micro · R_micro / (P_micro + R_micro)

  MACRO-F1 computes F1 per class c (each agent name / each FM code / each pair-class),
  accumulating that class's TP/FP/FN across all trajectories, then unweighted-averages:
    F1_c = 2·TP_c / (2·TP_c + FP_c + FN_c);   Macro-F1 = mean_c F1_c

  STEP-ACCURACY (single-point, not a set — kept as accuracy, not F1, because the
  ground-truth "when" is the single earliest injected step, the field convention):
    Step-Acc = (1/N) Σ_i 1[ earliest_pred_step_i == earliest_gt_step_i ]
  where earliest_pred_step_i is the 0-based acting-step index of the earliest step that
  the method flags (for set methods: earliest accused step; for ours/pointwise/med-SFT:
  their predicted earliest step).

binary_search is intentionally absent: it is single-point by construction and cannot
form a pair-set without becoming a different algorithm. Its accuracy-only numbers, and
the ORIGINAL single-prediction step_by_step, belong in an appendix (see
run_whowhen_table.py for the accuracy-based single-prediction reporting).
r"""
import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)

import argparse
import json
import time

from common.aegis_metrics import compute_metrics
from common.data import load_jsonl
from common.paths import FILES
from common.splits import load_split
from baselines.whowhen.baseline_whowhen import (SET_METHODS, acting_turns, ct2_backend,
                                                hf_backend, mock_backend)


def gold_pairs(traj):
    """Ground-truth (agent, FM) set for a trajectory."""
    out = []
    for (role, ri), fms in traj.labels.instance_fms.items():
        for fm in fms:
            out.append((role, fm))
    return out


def gold_earliest_step_idx(traj):
    turns = acting_turns(traj)
    return next((i for i, s in enumerate(turns)
                 if s.turn == traj.labels.earliest_error_turn), None)


def evaluate_set(name, method, llm, limit=None, workers=1):
    trajs = load_jsonl(FILES[name])
    _, te = load_split(name)
    te_trajs = [t for t in trajs if t.id in te]
    if limit:
        te_trajs = te_trajs[:limit]

    fn = SET_METHODS[method]

    def one(t):
        return fn(t, llm)

    if workers > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as ex:
            outs = list(ex.map(one, te_trajs))
    else:
        outs = [one(t) for t in te_trajs]

    preds, gts = [], []
    s_hit = s_tot = 0
    for t, (pairs, est) in zip(te_trajs, outs):
        preds.append(pairs)
        gts.append(gold_pairs(t))
        gi = gold_earliest_step_idx(t)
        if gi is not None:
            s_tot += 1
            if est is not None and est == gi:
                s_hit += 1
    m = compute_metrics(preds, gts)
    m["step_acc"] = s_hit / max(s_tot, 1)
    m["n"] = len(te_trajs)
    # raw material for CORRECT pooling across frameworks: pooled Micro-F1 must be computed
    # from concatenated pred/gt sets (i.e. summed TP/FP/FN), NOT by averaging per-framework
    # F1. step is pooled via summed hit/total counts.
    m["_raw"] = {"preds": preds, "gts": gts, "s_hit": s_hit, "s_tot": s_tot}
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["openai", "hf", "ct2", "mock"], default="mock")
    ap.add_argument("--model", default="mock-model")
    ap.add_argument("--base_url", default=None)
    ap.add_argument("--api_key", default="EMPTY")
    ap.add_argument("--tokenizer", default=None)
    ap.add_argument("--compute_type", default="float32")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--frameworks", nargs="+", default=list(FILES))
    ap.add_argument("--methods", nargs="+", default=list(SET_METHODS))
    ap.add_argument("--out", default=None)
    ap.add_argument("--pooled_out", default=None,
                    help="write framework-agnostic pooled metrics json (correct "
                         "Micro-F1 pooling via concatenated pred/gt sets)")
    args = ap.parse_args()

    if args.backend == "openai":
        from baselines.whowhen.baseline_whowhen import openai_backend
        llm = openai_backend(args.model, base_url=args.base_url, api_key=args.api_key)
    elif args.backend == "hf":
        llm = hf_backend(args.model, device=args.device)
    elif args.backend == "ct2":
        llm = ct2_backend(args.model, args.tokenizer, compute_type=args.compute_type,
                          device=args.device)
    else:
        llm = mock_backend()

    print("Set-prediction unified metrics: Agent/Error-Micro-F1 + Step-Acc")
    print(f"{'framework':16s} {'method':18s} {'Agent-mi':>8s} {'Error-mi':>8s} "
          f"{'Pair-mi':>8s} {'Step-Acc':>8s} {'n':>5s}")
    all_res = {}
    # accumulators for the framework-agnostic (pooled) row of each method
    pool_raw = {meth: {"preds": [], "gts": [], "s_hit": 0, "s_tot": 0}
                for meth in args.methods}
    for name in args.frameworks:
        all_res[name] = {}
        for meth in args.methods:
            t0 = time.time()
            m = evaluate_set(name, meth, llm, args.limit, args.workers)
            raw = m.pop("_raw")
            pool_raw[meth]["preds"].extend(raw["preds"])
            pool_raw[meth]["gts"].extend(raw["gts"])
            pool_raw[meth]["s_hit"] += raw["s_hit"]
            pool_raw[meth]["s_tot"] += raw["s_tot"]
            all_res[name][meth] = m
            print(f"{name:16s} {meth:18s} {m['agent_micro_f1']:8.1f} "
                  f"{m['error_micro_f1']:8.1f} {m['pair_micro_f1']:8.1f} "
                  f"{m['step_acc']:8.3f} {m['n']:5d}  ({time.time()-t0:.0f}s)", flush=True)

    # POOLED across all frameworks: score concatenated pred/gt (correct Micro-F1 pooling)
    pooled = {}
    print("\n--- pooled across frameworks (framework-agnostic) ---")
    print(f"{'method':18s} {'Agent-mi':>8s} {'Error-mi':>8s} {'Pair-mi':>8s} "
          f"{'Step-Acc':>8s} {'n':>5s}")
    for meth in args.methods:
        pr = pool_raw[meth]
        cm = compute_metrics(pr["preds"], pr["gts"])
        cm["step_acc"] = pr["s_hit"] / max(pr["s_tot"], 1)
        cm["n"] = len(pr["preds"])
        pooled[meth] = cm
        print(f"{meth:18s} {cm['agent_micro_f1']:8.1f} {cm['error_micro_f1']:8.1f} "
              f"{cm['pair_micro_f1']:8.1f} {cm['step_acc']:8.3f} {cm['n']:5d}")

    if args.out:
        json.dump(all_res, open(args.out, "w"), indent=1)
        print(f"\nwrote {args.out}")
    if args.pooled_out:
        # shape: {"pooled": {method: {metrics}}}  -> consumed by make_agnostic_table.py
        json.dump({"pooled": pooled}, open(args.pooled_out, "w"), indent=1)
        print(f"wrote {args.pooled_out} (framework-agnostic pooled metrics)")


if __name__ == "__main__":
    main()
