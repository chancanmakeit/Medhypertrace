"""
Run the three Who&When protocols across all frameworks and report the unified
metric set used elsewhere in this repo:

    agent-hit@1 | step Top-1 | step Top-3 | FM-type accuracy

NOTES ON THE METRICS
  * agent-hit@1 : predicted agent is in the trajectory's faulty role set.
  * step Top-1  : predicted step index == index of the earliest injected step.
  * step Top-3  : Who&When protocols emit a SINGLE step, so a genuine Top-3 does not
                  exist for them. We report a |pred - gold| <= 1 tolerance band as the
                  nearest honest analogue and label it "step +/-1" in the table --
                  it is NOT comparable to a ranked Top-3 from a scoring method.
  * FM-type acc : Who&When does not predict MAST failure modes at all. We add a
                  SEPARATE classification query (the trajectory + the 14 FM options,
                  answer with one label) so the column is populated without altering
                  the three original protocols. This is an EXTENSION of Who&When, and
                  must be labelled as such in the paper.

Small local models (e.g. SmolLM2-135M) are capability-limited on this task; always
report the trivial-predictor control (--controls) alongside, since degenerate protocol
fallbacks can coincide numerically with constant predictors.
"""
import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)

import argparse
import json
import re
import time

from common.data import load_jsonl, FM_TYPES
from common.paths import FILES
from common.splits import load_split
from baselines.whowhen.baseline_whowhen import (METHODS, acting_turns, ct2_backend,
                                                hf_backend, mock_backend)


def prompt_fm(traj, agent_name):
    turns = acting_turns(traj)
    ctx = "\n".join(f"Step {i} ({s.agent_name}): {s.content[:220]}"
                    for i, s in enumerate(turns))
    opts = ", ".join(FM_TYPES)
    who = f"Agent '{agent_name}' introduced the first error." if agent_name else \
          "An agent introduced the first error."
    return (f"Conversation:\n{ctx}\n\n{who}\n"
            f"Question: which failure mode best describes that error?\n"
            f"Choose exactly one from: {opts}.\n"
            f"Reply with only the failure mode code (e.g. FM-2.4) and nothing else.")


def parse_fm(text):
    m = re.search(r"FM-\s*(\d)\s*\.\s*(\d)", text, re.IGNORECASE)
    if not m:
        return None
    code = f"FM-{m.group(1)}.{m.group(2)}"
    return code if code in FM_TYPES else None


def gold_step_index(traj):
    turns = acting_turns(traj)
    for i, s in enumerate(turns):
        if s.turn == traj.labels.earliest_error_turn:
            return i
    return None


def subsample(te_trajs, limit, seed=0):
    """Deterministic random subsample of the fixed test set (NOT the head of the
    list, which would bias toward particular tasks)."""
    if not limit or limit >= len(te_trajs):
        return te_trajs
    import random
    return [te_trajs[i] for i in sorted(random.Random(seed).sample(range(len(te_trajs)), limit))]


def run_framework(name, llm, methods, limit=None, do_fm=True, verbose=False, workers=1):
    trajs = load_jsonl(FILES[name])
    _, te = load_split(name)
    te_trajs = subsample([t for t in trajs if t.id in te], limit)

    from concurrent.futures import ThreadPoolExecutor

    def _parallel_map(func, items):
        if workers <= 1:
            return [func(x) for x in items]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            return list(ex.map(func, items))

    out = {}
    for meth in methods:
        fn = METHODS[meth]
        t0 = time.time()
        # stage 1: attribution — each trajectory independent, run concurrently so a
        # vLLM server batches the in-flight requests (binary_search stays serial WITHIN
        # a trajectory but many trajectories run at once).
        preds = _parallel_map(lambda t: fn(t, llm), te_trajs)
        # stage 2: FM classification — one extra independent call per trajectory.
        if do_fm:
            fm_outs = _parallel_map(lambda tp: parse_fm(llm("", prompt_fm(tp[0], tp[1]))),
                                    list(zip(te_trajs, [p[0] for p in preds])))
        else:
            fm_outs = [None] * len(te_trajs)

        a_hit = s1 = s_band = fm_hit = fm_n = n = 0
        for t, (pred_agent, pred_step), fm in zip(te_trajs, preds, fm_outs):
            n += 1
            faulty = {r for (r, _) in t.labels.faulty_instances}
            gi = gold_step_index(t)
            if pred_agent and any(fr in pred_agent or pred_agent in fr for fr in faulty):
                a_hit += 1
            if pred_step is not None and gi is not None:
                if pred_step == gi:
                    s1 += 1
                if abs(pred_step - gi) <= 1:
                    s_band += 1
            if do_fm:
                gold_fms = {f for fs in t.labels.instance_fms.values() for f in fs}
                fm_n += 1
                if fm and fm in gold_fms:
                    fm_hit += 1
        dt = time.time() - t0
        out[meth] = {"agent_hit@1": a_hit / max(n, 1), "step_top1": s1 / max(n, 1),
                     "step_band1": s_band / max(n, 1),
                     "fm_acc": (fm_hit / fm_n) if fm_n else None,
                     "n": n, "sec": dt,
                     # raw counts for correct POOLED aggregation across frameworks
                     # (pool = sum hits / sum n, NOT mean of per-framework ratios)
                     "_counts": {"a_hit": a_hit, "s1": s1, "s_band": s_band,
                                 "fm_hit": fm_hit, "fm_n": fm_n, "n": n}}
        if verbose:
            print(f"    [{name}/{meth}] done in {dt:.0f}s (workers={workers})", flush=True)
    return out


def trivial_controls(name, limit=None):
    """Constant predictors that use NO model — the sanity floor every LLM number
    must be compared against."""
    trajs = load_jsonl(FILES[name])
    _, te = load_split(name)
    te_trajs = subsample([t for t in trajs if t.id in te], limit)
    res = {}
    for tag in ("first_step", "last_step"):
        a = s1 = band = fm = n = 0
        for t in te_trajs:
            turns = acting_turns(t)
            if not turns:
                continue
            n += 1
            idx = 0 if tag == "first_step" else len(turns) - 1
            gi = gold_step_index(t)
            faulty = {r for (r, _) in t.labels.faulty_instances}
            if turns[idx].agent_name in faulty:
                a += 1
            if gi is not None:
                if idx == gi:
                    s1 += 1
                if abs(idx - gi) <= 1:
                    band += 1
            gold_fms = {f for fs in t.labels.instance_fms.values() for f in fs}
            if "FM-3.2" in gold_fms:          # most frequent FM = majority-class guess
                fm += 1
        res[tag] = {"agent_hit@1": a / max(n, 1), "step_top1": s1 / max(n, 1),
                    "step_band1": band / max(n, 1), "fm_acc": fm / max(n, 1), "n": n,
                    "_counts": {"a_hit": a, "s1": s1, "s_band": band,
                                "fm_hit": fm, "fm_n": n, "n": n}}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["hf", "ct2", "openai", "mock"], default="hf")
    ap.add_argument("--model", default="HuggingFaceTB/SmolLM2-135M-Instruct")
    ap.add_argument("--tokenizer", default=None)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--compute_type", default="float32")
    ap.add_argument("--frameworks", nargs="+", default=list(FILES))
    ap.add_argument("--methods", nargs="+", default=list(METHODS))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no_fm", action="store_true")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--base_url", default=None, help="vLLM/OpenAI server, e.g. http://localhost:8000/v1")
    ap.add_argument("--api_key", default="EMPTY")
    ap.add_argument("--workers", type=int, default=1,
                    help="concurrent trajectories in flight (feeds vLLM continuous batching)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.backend == "hf":
        llm = hf_backend(args.model, device=args.device)
        tag = args.model
    elif args.backend == "ct2":
        llm = ct2_backend(args.model, args.tokenizer, compute_type=args.compute_type,
                          device=args.device)
        tag = f"{args.model} ({args.compute_type})"
    elif args.backend == "openai":
        from baselines.whowhen.baseline_whowhen import openai_backend
        llm = openai_backend(args.model, base_url=args.base_url, api_key=args.api_key)
        tag = f"{args.model} @ {args.base_url}"
    else:
        llm = mock_backend(); tag = "mock"

    print(f"Who&When protocols — backend={tag}")
    print(f"metrics: agent-hit@1 | step Top-1 | step +/-1 | FM-type acc\n")
    all_res = {}
    for name in args.frameworks:
        all_res[name] = run_framework(name, llm, args.methods, args.limit,
                                      do_fm=not args.no_fm, verbose=True, workers=args.workers)
        for meth, m in all_res[name].items():
            fm = f"{m['fm_acc']:.3f}" if m["fm_acc"] is not None else "  -  "
            print(f"  [{name:14s}/{meth:13s}] agent={m['agent_hit@1']:.3f} "
                  f"step1={m['step_top1']:.3f} step±1={m['step_band1']:.3f} "
                  f"FM={fm} (n={m['n']}, {m['sec']:.0f}s)", flush=True)
    if args.controls:
        print("\nTrivial controls (no model):")
        for name in args.frameworks:
            for tag2, m in trivial_controls(name, args.limit).items():
                print(f"  [{name:14s}/{tag2:13s}] agent={m['agent_hit@1']:.3f} "
                      f"step1={m['step_top1']:.3f} step±1={m['step_band1']:.3f} "
                      f"FM={m['fm_acc']:.3f} (n={m['n']})")
    if args.out:
        json.dump(all_res, open(args.out, "w"), indent=1)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
