"""
Fill docs/table_agnostic_baselines.tex with real numbers.

Framework-agnostic baselines are scored on the POOLED test set (all 5 frameworks'
fixed test splits combined). Pooling is done correctly by summing raw hit counts and
dividing by the total n -- NOT by averaging per-framework ratios (which would over-
weight small frameworks).

Rows:
  * Who&When all-at-once / step-by-step / binary-search  -> computed here via the LLM
    backend (use --backend openai --base_url <vLLM> on your GPU box).
  * AEGIS-SFT (OOD transfer) -> not an LLM-judge protocol; supply its pooled metrics
    via --aegis_ood_json (a small json: {"agent_hit@1":.., "step_acc":.., "fm_acc":..})
    produced from your evaluate-v3.py run over the med_eval bridge files. If omitted,
    that row stays "--".
  * Trivial controls (first/last step) -> computed here, no model.

Usage (GPU box, real model):
  python baselines/whowhen/fill_agnostic_table.py \
      --backend openai --model Qwen/Qwen2.5-7B-Instruct \
      --base_url http://localhost:8000/v1 --workers 32 \
      --aegis_ood_json ood_pooled.json \
      --out_tex docs/table_agnostic_baselines.filled.tex

Sandbox check (no GPU, meaningless numbers, verifies plumbing + tex generation):
  python baselines/whowhen/fill_agnostic_table.py --backend mock --limit 10 \
      --out_tex /tmp/tbl.tex
"""
import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)

import argparse
import json

from common.paths import FILES
from baselines.whowhen.baseline_whowhen import (METHODS, ct2_backend, hf_backend,
                                                mock_backend)
from baselines.whowhen.run_whowhen_table import run_framework, trivial_controls


def pool(per_framework_counts):
    """Sum raw counts across frameworks, then form ratios. Returns (agent, step, fm)."""
    a = sum(c["a_hit"] for c in per_framework_counts)
    s = sum(c["s1"] for c in per_framework_counts)
    fm_hit = sum(c["fm_hit"] for c in per_framework_counts)
    n = sum(c["n"] for c in per_framework_counts)
    fm_n = sum(c["fm_n"] for c in per_framework_counts)
    return (a / max(n, 1), s / max(n, 1),
            (fm_hit / fm_n) if fm_n else None, n)


def fmt(x):
    return "--" if x is None else f"{x:.3f}"


TEMPLATE = r"""% Auto-filled by fill_agnostic_table.py. Model: {model}. Pooled n={n}.
\begin{{table}}[t]
\centering
\caption{{Framework-agnostic failure attribution (zero-shot LLM baselines), evaluated
on the pooled test set across all five multi-agent frameworks ($n{{=}}{n}$).
Who\&When variants use \texttt{{{model_tex}}}; AEGIS-SFT is the out-of-domain transfer of a
general-domain SFT model. FM-Acc for Who\&When is an added classification query.}}
\label{{tab:agnostic-baselines}}
\begin{{tabular}}{{lccc}}
\toprule
Method & Agent-Hit@1 & Step-Acc & FM-Acc \\
\midrule
Who\&When (all-at-once)   & {aao_a} & {aao_s} & {aao_f} \\
Who\&When (step-by-step)  & {sbs_a} & {sbs_s} & {sbs_f} \\
Who\&When (binary-search) & {bin_a} & {bin_s} & {bin_f} \\
AEGIS-SFT (OOD transfer)  & {ood_a} & {ood_s} & {ood_f} \\
\midrule
\multicolumn{{4}}{{l}}{{\footnotesize\textit{{Trivial controls (no model, sanity floor):}}}} \\
Constant ``first step''   & {fst_a} & {fst_s} & {fst_f} \\
Constant ``last step''    & {lst_a} & {lst_s} & {lst_f} \\
\bottomrule
\end{{tabular}}
\end{{table}}
"""


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
    ap.add_argument("--limit", type=int, default=None, help="per-framework cap (sandbox)")
    ap.add_argument("--frameworks", nargs="+", default=list(FILES))
    ap.add_argument("--aegis_ood_json", default=None,
                    help='json with pooled AEGIS-SFT-OOD metrics: '
                         '{"agent_hit@1":..,"step_acc":..,"fm_acc":..}')
    ap.add_argument("--out_tex", default="docs/table_agnostic_baselines.filled.tex")
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

    methods = ["all_at_once", "step_by_step", "binary_search"]
    # collect per-framework counts for each method
    counts = {m: [] for m in methods}
    ctrl_counts = {"first_step": [], "last_step": []}
    for name in args.frameworks:
        res = run_framework(name, llm, methods, args.limit, do_fm=True,
                            verbose=True, workers=args.workers)
        for m in methods:
            counts[m].append(res[m]["_counts"])
        for tag, r in trivial_controls(name, args.limit).items():
            ctrl_counts[tag].append(r["_counts"])

    pooled = {m: pool(counts[m]) for m in methods}
    ctrl = {tag: pool(ctrl_counts[tag]) for tag in ctrl_counts}
    n_total = pooled["all_at_once"][3]

    # AEGIS-SFT-OOD row (supplied externally)
    if args.aegis_ood_json:
        o = json.load(open(args.aegis_ood_json))
        ood = (o.get("agent_hit@1"), o.get("step_acc"), o.get("fm_acc"))
    else:
        ood = (None, None, None)

    model_tex = args.model.replace("_", r"\_")
    tex = TEMPLATE.format(
        model=args.model, model_tex=model_tex, n=n_total,
        aao_a=fmt(pooled["all_at_once"][0]), aao_s=fmt(pooled["all_at_once"][1]), aao_f=fmt(pooled["all_at_once"][2]),
        sbs_a=fmt(pooled["step_by_step"][0]), sbs_s=fmt(pooled["step_by_step"][1]), sbs_f=fmt(pooled["step_by_step"][2]),
        bin_a=fmt(pooled["binary_search"][0]), bin_s=fmt(pooled["binary_search"][1]), bin_f=fmt(pooled["binary_search"][2]),
        ood_a=fmt(ood[0]), ood_s=fmt(ood[1]), ood_f=fmt(ood[2]),
        fst_a=fmt(ctrl["first_step"][0]), fst_s=fmt(ctrl["first_step"][1]), fst_f=fmt(ctrl["first_step"][2]),
        lst_a=fmt(ctrl["last_step"][0]), lst_s=fmt(ctrl["last_step"][1]), lst_f=fmt(ctrl["last_step"][2]),
    )
    with open(args.out_tex, "w") as f:
        f.write(tex)
    print("\n=== pooled results (n=%d) ===" % n_total)
    for m in methods:
        a, s, fm, _ = pooled[m]
        print(f"  {m:14s} agent={fmt(a)} step={fmt(s)} fm={fmt(fm)}")
    for tag in ctrl:
        a, s, fm, _ = ctrl[tag]
        print(f"  {tag:14s} agent={fmt(a)} step={fmt(s)} fm={fmt(fm)}")
    print(f"\nwrote {args.out_tex}")


if __name__ == "__main__":
    main()
