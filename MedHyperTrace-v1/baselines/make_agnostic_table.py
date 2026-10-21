r"""
Generate the framework-AGNOSTIC main table (LaTeX): one row per method, four columns
(Agent-Micro-F1 | Error-Micro-F1 | Pair-Micro-F1 | Step-Acc), computed on the POOLED
test set (all frameworks combined).

CORRECT POOLING. Micro-F1 must be computed from summed TP/FP/FN across frameworks, i.e.
by scoring the CONCATENATED prediction/ground-truth sets — NOT by averaging per-framework
F1 (that would over-weight small frameworks and is numerically wrong). Therefore this
tool consumes "pooled" json files emitted directly by the evaluators:

  {"pooled": {method: {agent_micro_f1, error_micro_f1, pair_micro_f1, step_acc, n}}}

produced by:
  eval_set_unified.py  --pooled_out <f>   (Who&When set variants; pools internally)
  # ours / pointwise / med-SFT: emit the same {"pooled":{...}} shape from their evaluators
  #   (hgnn_unified_eval / pointwise_unified_eval already dump per-framework; add a pooled
  #    dump the same way, or pass their raw pred/gt through compute_metrics once on the
  #    concatenation — see make_pooled_from_raw() helper below for a scripted merge).

Multiple pooled files merge by method key (later overrides on clash).

USAGE
  python baselines/make_agnostic_table.py --in ww_pooled.json ours_pooled.json \
      --out_tex docs/table_agnostic_main.tex
"""
import argparse
import json

NAME_MAP = {
    "all_at_once_set": r"Who\&When (all-at-once)$^\dagger$",
    "step_by_step_set": r"Who\&When (step-by-step)$^\dagger$",
    "sdbl_set": r"SDBL$^\dagger$",
    "pointwise": "Pointwise",
    "aegis_sft_ood": "AEGIS-SFT (OOD)",
    "aegis_med_sft": "AEGIS-med-SFT",
    "ours": r"\textbf{MedHyperTrace (ours)}",
}
METHOD_ORDER = ["all_at_once_set", "step_by_step_set", "sdbl_set",
                "aegis_sft_ood", "pointwise", "aegis_med_sft", "ours"]


def load_and_merge(paths):
    merged = {}
    for p in paths:
        d = json.load(open(p))
        pooled = d.get("pooled", d)     # accept {"pooled":{...}} or a bare {method:{...}}
        merged.update(pooled)
    return merged


def cellval(m, level):
    if m is None:
        return None
    if level == "step":
        v = m.get("step_acc")
        return None if v is None else v * 100
    return m.get(f"{level}_micro_f1")


def fmt(v):
    return "--" if v is None else f"{v:.1f}"


def build(merged):
    methods = [m for m in METHOD_ORDER if m in merged]
    cols = [("Agent-Micro-F1", "agent"), ("Error-Micro-F1", "error"),
            ("Pair-Micro-F1", "pair"), ("Step-Acc", "step")]

    # bold winners per column
    winners = {}
    for _, lvl in cols:
        vals = [(mi, cellval(merged[m], lvl)) for mi, m in enumerate(methods)]
        nums = [(i, v) for i, v in vals if v is not None]
        if nums:
            mx = max(v for _, v in nums)
            winners[lvl] = {i for i, v in nums if abs(v - mx) < 1e-9}
        else:
            winners[lvl] = set()

    n = merged[methods[0]].get("n", "?") if methods else "?"
    L = []
    L.append(r"\begin{table}[t]")
    L.append(r"\centering")
    L.append(r"\caption{Framework-agnostic failure attribution on the pooled test set of "
             r"all five frameworks ($n{=}%s$), under a unified set-prediction metric "
             r"family (all $\times100$). Micro-F1 is pooled over concatenated "
             r"predictions. $^\dagger$ zero-shot LLM baselines (set-prediction variant). "
             r"Best per column in \textbf{bold}.}" % str(n))
    L.append(r"\label{tab:agnostic-main}")
    L.append(r"\begin{tabular}{lcccc}")
    L.append(r"\toprule")
    L.append("Method & " + " & ".join(c for c, _ in cols) + r" \\")
    L.append(r"\midrule")
    for mi, meth in enumerate(methods):
        if meth == "ours":
            L.append(r"\midrule")
        row = [NAME_MAP.get(meth, meth)]
        for _, lvl in cols:
            v = cellval(merged[meth], lvl)
            c = fmt(v)
            if v is not None and mi in winners[lvl]:
                c = r"\textbf{" + c + "}"
            row.append(c)
        L.append(" & ".join(row) + r" \\")
    L.append(r"\bottomrule")
    L.append(r"\end{tabular}")
    L.append(r"\end{table}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inputs", nargs="+", required=True,
                    help='pooled json files: {"pooled":{method:{metrics}}}')
    ap.add_argument("--out_tex", default="docs/table_agnostic_main.tex")
    args = ap.parse_args()
    merged = load_and_merge(args.inputs)
    tex = build(merged)
    with open(args.out_tex, "w") as f:
        f.write(tex + "\n")
    print("pooled framework-agnostic table:")
    print(f"{'method':28s} {'Agent':>7s} {'Error':>7s} {'Pair':>7s} {'Step':>7s}")
    for meth in METHOD_ORDER:
        if meth not in merged:
            continue
        m = merged[meth]
        print(f"{meth:28s} {fmt(cellval(m,'agent')):>7s} {fmt(cellval(m,'error')):>7s} "
              f"{fmt(cellval(m,'pair')):>7s} {fmt(cellval(m,'step')):>7s}")
    print(f"\nwrote {args.out_tex}")


if __name__ == "__main__":
    main()
