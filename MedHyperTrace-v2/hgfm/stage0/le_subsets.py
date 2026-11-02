"""Stage 0 Q1 (pre-registration Stage0_prereg_v1): nested, question-grouped training subsets of TracerTraj train.

  python -m hgfm.stage0.le_subsets --train_dir <tt_ww>/train --out subsets.json [--sizes 100 300 1000 --draws 5]

Eligible = mistake_step inside the history (the label is a candidate step). Groups = normalised question
(lower-case, whitespace collapsed; the rule tracertraj_to_ww.py used for the val split). Draw d: groups in a random order
(seed d), accumulated until >= n trajectories; the sizes are nested (100 subset of 300 subset of 1000) within a draw.
Output {"draws": {"0": {"100": [ids], ...}}, "n_eligible": N} with ids as the OAT loader writes them ("<subdir>/<file>").
"""
import argparse, glob, json, os, random, re
from collections import defaultdict

norm = lambda s: re.sub(r"\s+", " ", (s or "").strip().lower())


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--train_dir"); ap.add_argument("--out")
    ap.add_argument("--sizes", type=int, nargs="+", default=[100, 300, 1000]); ap.add_argument("--draws", type=int, default=5)
    a = ap.parse_args(); groups = defaultdict(list); n = 0
    for p in sorted(glob.glob(os.path.join(a.train_dir, "*", "*.json"))):
        d = json.load(open(p)); ms = int(d["mistake_step"])
        if not 0 <= ms < len(d["history"]): continue
        groups[norm(d["question"])].append(f"{os.path.basename(os.path.dirname(p))}/{os.path.basename(p)}"); n += 1
    keys = sorted(groups); out = {"draws": {}, "n_eligible": n, "n_groups": len(keys)}
    for dr in range(a.draws):
        order = keys[:]; random.Random(dr).shuffle(order); ids, res = [], {}
        for s in sorted(a.sizes):
            for g in order:
                if len(ids) >= s: break
                if groups[g][0] in ids: continue
                ids += groups[g]
            res[str(s)] = list(ids)
        out["draws"][str(dr)] = res
    json.dump(out, open(a.out, "w")); print(json.dumps({"n_eligible": n, "n_groups": len(keys),
          "sizes": {dr: {s: len(v) for s, v in res.items()} for dr, res in out["draws"].items()}}))


if __name__ == "__main__":
    main()
