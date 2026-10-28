"""E4 stage B evaluation: BEFT scores (base vs tapt init) with the same metrics / length control as stage A.

  python -m hgfm.e4.e4_beft_eval --feats <feats_base.pt> --runs base=<dir> tapt=<dir> --out <json>

Covariates (step token counts, has_code, candidate set) come from the stage-A feature file (same tokenizer and text).
"""
import argparse, json
import torch

from hgfm.e4.e4_eval import evaluate
from hgfm.e4.e4_probe import EVAL, load


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--feats"); ap.add_argument("--runs", nargs="+"); ap.add_argument("--out")
    a = ap.parse_args(); rows, _ = load(a.feats); scores = {}
    for spec in a.runs:
        name, d = spec.split("="); sc = json.load(open(f"{d}/scores.json"))
        scores[f"beft_{name}"] = {tuple(k.split("|", 1)): [v] for k, v in sc.items()}
    common = set.intersection(*[set(v) for v in scores.values()]) & {k for k in rows if k[0] in EVAL}
    for st in scores: scores[st] = {k: v for k, v in scores[st].items() if k in common}
    for k in common: assert len(scores["beft_base"][k][0]) == len(rows[k]["cand"]), k
    meta = {k: {kk: rows[k][kk] for kk in ("cand", "label", "ntok", "code", "n_steps")} for k in common}
    res = evaluate(scores, meta, [("beft_tapt", "beft_base")]); res["n_eval"] = len(common)
    json.dump(res, open(a.out, "w"), indent=1)
    for kind in ("raw", "resid"):
        for st, v in res["summary"][kind].items():
            print(kind, f"{st:14s}", "  ".join(f"{sn} a1 {x['acc1']:.3f} r {x['rauc']:.3f} (n={x['n']})" for sn, x in v.items()))
        print("DECISION-INPUT beft_tapt - beft_base", kind, res["paired"].get(f"beft_tapt - beft_base / pooled / {kind} / rauc"))


if __name__ == "__main__":
    main()
