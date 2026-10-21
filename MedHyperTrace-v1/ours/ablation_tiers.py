r"""
Three-tier ablation for the structural-signature story (S+ / S~ / S-).

Runs the SAME hypergraph model under three feature/loss configurations and reports the
unified metrics per framework, so you can quantify how much each tier recovers:

  Tier 1  pure structure            --struct 1 --prop 0   --factuality null
          (S+ : in-trajectory structural signals only)
  Tier 2  + propagation consistency --struct 1 --prop 0.1 --factuality null
          (S~ : adds the propagation-consistency loss -> catches believed/propagated
           errors via their downstream footprint)
  Tier 3  + external factuality     --struct 1 --prop 0.1 --factuality nli
          (S- : adds a real NLI factuality feature -> touches isolated hallucinations
           that leave NO in-trajectory trace)

Interpretation for the paper:
  - If Tier 3 > Tier 2 on hallucination-dominated failures (FC0 / F1.1.1), external
    factual checking is NECESSARY -> structural methods have a ceiling at S-.
  - If Tier 3 == Tier 2, structural signal already suffices and external checking is
    redundant. Either way is a publishable result about the LIMIT of structural
    attribution.

This script shells out to ours/train_hgnn.py (needs torch+GPU). On a box without torch it
prints the exact commands instead of running, so you can copy-paste them.

USAGE
  python ours/ablation_tiers.py --frameworks clinical_agent mdagents \
      --features emb --emb_model mxbai --epochs 30 --out ablation.json
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

TIERS = [
    ("t1_structure",   {"struct": "1", "prop": "0.0", "factuality": "null"}),
    ("t2_propagation", {"struct": "1", "prop": "0.1", "factuality": "null"}),
    ("t3_factuality",  {"struct": "1", "prop": "0.1", "factuality": "nli"}),
]


def build_cmd(framework, common_args, tier_args):
    cmd = [sys.executable, os.path.join(HERE, "hgnn_unified_eval.py"), framework]
    cmd += ["--features", common_args["features"]]
    if common_args["features"] in ("emb", "nomic"):
        cmd += ["--emb_model", common_args["emb_model"]]
    cmd += ["--epochs", str(common_args["epochs"])]
    for k, v in tier_args.items():
        cmd += [f"--{k}", v]
    cmd += ["--json_out", f"/tmp/_tier_{framework}.json", "--report_gran", "role"]
    return cmd


def have_torch():
    try:
        import torch  # noqa
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frameworks", nargs="+",
                    default=["clinical_agent", "mdagents"])
    ap.add_argument("--features", default="emb")
    ap.add_argument("--emb_model", default="mxbai")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--out", default="ablation_tiers.json")
    args = ap.parse_args()
    common = {"features": args.features, "emb_model": args.emb_model,
              "epochs": args.epochs}

    runnable = have_torch()
    if not runnable:
        print("torch not available here — printing the commands to run on your GPU box:\n")

    results = {}
    for fw in args.frameworks:
        results[fw] = {}
        for tier_name, tier_args in TIERS:
            cmd = build_cmd(fw, common, tier_args)
            if not runnable:
                print(f"# {fw} / {tier_name}")
                print("  " + " ".join(cmd) + "\n")
                continue
            print(f"=== {fw} / {tier_name} ===", flush=True)
            subprocess.run(cmd, cwd=ROOT, check=False)
            tj = f"/tmp/_tier_{fw}.json"
            if os.path.exists(tj):
                d = json.load(open(tj))
                # hgnn_unified_eval writes {framework: {"ours": metrics}}
                m = d.get(fw, {}).get("ours", {})
                results[fw][tier_name] = {
                    "agent_micro_f1": m.get("agent_micro_f1"),
                    "error_micro_f1": m.get("error_micro_f1"),
                    "pair_micro_f1": m.get("pair_micro_f1"),
                    "step_acc": m.get("step_acc"),
                }

    if not runnable:
        print("After running, re-run this script on the box (it will collect the jsons).")
        return

    json.dump(results, open(args.out, "w"), indent=1)
    print(f"\nwrote {args.out}\n")
    # console table
    print(f"{'framework':16s} {'tier':16s} {'Agent':>7s} {'Error':>7s} "
          f"{'Pair':>7s} {'Step':>7s}")
    for fw, tiers in results.items():
        for tier_name, _ in TIERS:
            m = tiers.get(tier_name, {})
            def f(x): return "--" if x is None else f"{x:.1f}"
            print(f"{fw:16s} {tier_name:16s} {f(m.get('agent_micro_f1')):>7s} "
                  f"{f(m.get('error_micro_f1')):>7s} {f(m.get('pair_micro_f1')):>7s} "
                  f"{f((m.get('step_acc') or 0)*100):>7s}")


if __name__ == "__main__":
    main()
