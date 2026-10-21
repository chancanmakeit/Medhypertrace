r"""
Generate the framework-specific MAIN results table (LaTeX) from one or more
set-prediction result JSONs (as produced by baselines/whowhen/eval_set_unified.py, and
by the same-format dumps you can emit for ours / pointwise / med-SFT).

Every method is scored under ONE metric family:
    Agent-Micro-F1 | Error-Micro-F1 | Pair-Micro-F1 | Step-Acc
reported per framework. (Macro variants are in the json too; --metric macro switches.)

INPUT: one or more json files, each shaped {framework: {method: {metric: value, ...}}}.
Method keys are used as row labels (remapped to nice names via NAME_MAP). Merging several
files lets you drop in ours/pointwise/med-SFT results next to the Who&When set variants
without re-running them together.

USAGE
  # from the Who&When set metrics alone:
  python baselines/make_main_table.py --in set_metrics.json --out_tex docs/table_main.tex

  # merge several result files into one table (later files override on key clashes):
  python baselines/make_main_table.py --in set_metrics.json ours.json pointwise.json \
      --out_tex docs/table_main.tex

  # macro instead of micro:
  python baselines/make_main_table.py --in set_metrics.json --metric macro --out_tex ...
"""
import argparse
import json

# framework column order + display names
FRAMEWORKS = ["mdagents", "dylan", "llm_debate", "clinical_agent", "clinical_agent5"]
FRAMEWORK_TEX = {
    "mdagents": "MDAgents", "dylan": "DyLAN", "llm_debate": "LLM-Debate",
    "clinical_agent": "ClinicalAgent", "clinical_agent5": "ClinicalAgent5",
}
# method row order + display names. Add ours/pointwise/med-SFT keys here when merged in.
NAME_MAP = {
    "all_at_once_set": r"Who\&When (all-at-once)$^\dagger$",
    "step_by_step_set": r"Who\&When (step-by-step)$^\dagger$",
    "sdbl_set": r"SDBL$^\dagger$",
    "pointwise": "Pointwise",
    "aegis_med_sft": "AEGIS-med-SFT",
    "ours": r"\textbf{MedHyperTrace (ours)}",
}
METHOD_ORDER = ["all_at_once_set", "step_by_step_set", "sdbl_set",
                "pointwise", "aegis_med_sft", "ours"]


def load_and_merge(paths):
    merged = {}
    for p in paths:
        d = json.load(open(p))
        for fw, methods in d.items():
            merged.setdefault(fw, {}).update(methods)
    return merged


def cell(m, level, metric):
    """Return formatted value for a metric cell, or '--' if missing.
    level in {agent, error, pair}; metric in {micro, macro} -> f1; or 'step'."""
    if m is None:
        return "--"
    if level == "step":
        v = m.get("step_acc")
        return "--" if v is None else f"{v*100:.1f}"
    key = f"{level}_{metric}_f1"
    v = m.get(key)
    return "--" if v is None else f"{v:.1f}"


def bold_max(values):
    """Given list of (idx, float-or-None), return set of idxs holding the max."""
    nums = [(i, v) for i, v in values if v is not None]
    if not nums:
        return set()
    mx = max(v for _, v in nums)
    return {i for i, v in nums if abs(v - mx) < 1e-9}


def build_table(merged, metric="micro"):
    methods = [m for m in METHOD_ORDER
               if any(m in merged.get(fw, {}) for fw in FRAMEWORKS)]
    frameworks = [fw for fw in FRAMEWORKS if fw in merged]

    # 4 metric columns per framework
    metric_cols = [("Agent", "agent"), ("Error", "error"),
                   ("Pair", "pair"), ("Step", "step")]

    lines = []
    lines.append(r"\begin{table*}[t]")
    lines.append(r"\centering")
    lines.append(r"\caption{Failure attribution on the fixed test set of each framework, "
                 r"under a unified set-prediction metric family: Agent/Error/Pair-Micro-F1 "
                 r"and Step-Accuracy (all $\times 100$). $^\dagger$ zero-shot LLM baselines "
                 r"in their set-prediction variant. Best per column in \textbf{bold}.}")
    lines.append(r"\label{tab:main}")
    ncol = 1 + len(frameworks) * len(metric_cols)
    lines.append(r"\resizebox{\textwidth}{!}{%")
    lines.append(r"\begin{tabular}{l" + "cccc" * len(frameworks) + "}")
    lines.append(r"\toprule")
    # framework header row (spans 4 each)
    hdr = ["Method"]
    for fw in frameworks:
        hdr.append(r"\multicolumn{4}{c}{" + FRAMEWORK_TEX[fw] + "}")
    lines.append(" & ".join(hdr) + r" \\")
    # cmidrule under each framework block
    cmids = []
    start = 2
    for _ in frameworks:
        cmids.append(r"\cmidrule(lr){%d-%d}" % (start, start + 3))
        start += 4
    lines.append(" ".join(cmids))
    # metric sub-header
    sub = [""]
    for _ in frameworks:
        sub += ["Agent", "Error", "Pair", "Step"]
    lines.append(" & ".join(sub) + r" \\")
    lines.append(r"\midrule")

    # precompute bold winners per (framework, metric) column
    winners = {}
    for fw in frameworks:
        for _, lvl in metric_cols:
            vals = []
            for mi, meth in enumerate(methods):
                m = merged.get(fw, {}).get(meth)
                if m is None:
                    vals.append((mi, None)); continue
                if lvl == "step":
                    v = m.get("step_acc")
                    vals.append((mi, None if v is None else v * 100))
                else:
                    vals.append((mi, m.get(f"{lvl}_{metric}_f1")))
            winners[(fw, lvl)] = bold_max(vals)

    for mi, meth in enumerate(methods):
        row = [NAME_MAP.get(meth, meth)]
        for fw in frameworks:
            m = merged.get(fw, {}).get(meth)
            for _, lvl in metric_cols:
                c = cell(m, lvl, metric)
                if c != "--" and mi in winners[(fw, lvl)]:
                    c = r"\textbf{" + c + "}"
                row.append(c)
        # visually separate ours (last block) if present
        if meth == "ours":
            lines.append(r"\midrule")
        lines.append(" & ".join(row) + r" \\")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}}")
    lines.append(r"\end{table*}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inputs", nargs="+", required=True,
                    help="one or more set-metrics json files (merged in order)")
    ap.add_argument("--metric", choices=["micro", "macro"], default="micro")
    ap.add_argument("--out_tex", default="docs/table_main.tex")
    args = ap.parse_args()

    merged = load_and_merge(args.inputs)
    tex = build_table(merged, args.metric)
    with open(args.out_tex, "w") as f:
        f.write(tex + "\n")

    # console preview
    print(f"metric family: {args.metric}-F1 (+ Step-Acc)\n")
    hdr = f"{'method':28s}" + "".join(f"{FRAMEWORK_TEX[fw][:11]:>12s}"
                                      for fw in FRAMEWORKS if fw in merged)
    print(hdr)
    for meth in METHOD_ORDER:
        if not any(meth in merged.get(fw, {}) for fw in FRAMEWORKS):
            continue
        cells = []
        for fw in FRAMEWORKS:
            if fw not in merged:
                continue
            m = merged[fw].get(meth)
            cells.append("--" if m is None
                         else f"A{cell(m,'agent',args.metric)}/P{cell(m,'pair',args.metric)}")
        label = meth.replace("_set", "").replace("_", "-")
        print(f"{label:28s}" + "".join(f"{c:>12s}" for c in cells))
    print(f"\nwrote {args.out_tex}")


if __name__ == "__main__":
    main()
