"""Round 83 sensitivity analysis: stage-0 intervals with a question-clustered bootstrap.

The pre-registration (docs/design/Stage0_prereg_v1.md) fixed a paired bootstrap over trajectories. Who&When Hand-Crafted,
Who&When Algorithm-Generated and TraceElephant groupchat often contain the same question, so trajectories are not
independent. This wrapper re-runs scripts/stage0_analyze.py unchanged except for `boot`: clusters (questions) are drawn
with replacement (each draw keeps every trajectory of the cluster, repeats kept), the statistic is the mean over all
trajectories drawn. Point estimates are identical to the pre-registered analysis; only the intervals change. Verdicts
use the same rule (CI lower > 0 -> HOLDS; CI upper < +0.04 -> NULL; else UNDETERMINED). This is a sensitivity
analysis, not a replacement of the pre-registered result.

  python scripts/stage0_cluster_ci.py --clusters <json {cluster_name: {"dataset|id": cluster_id}}> --which jac0.7 \
      --w <mht_work> --clean <eval_clean_keys.json> --out <json>

Trajectories missing from the map are their own cluster.
"""
import json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import stage0_analyze as S   # noqa: E402

CL = {}


def boot_cluster(d, rng, B=1000):
    keys = list(d)
    x = np.array([d[k] for k in keys], float)
    if not len(x): return {"n": 0}
    groups = {}
    for i, k in enumerate(keys):
        ks = k if isinstance(k, str) else "|".join(k)   # stage0_analyze keys are (dataset, id) tuples
        groups.setdefault(CL.get(ks, "__self__" + ks), []).append(i)
    if all(c.startswith("__self__") for c in groups): raise SystemExit("no trajectory matched the cluster map")
    g = list(groups.values()); sums = np.array([x[ix].sum() for ix in g]); cnts = np.array([len(ix) for ix in g])
    bs = []
    for _ in range(B):
        pick = rng.integers(0, len(g), len(g))
        bs.append(sums[pick].sum() / cnts[pick].sum())
    return {"n": int(len(x)), "n_clusters": len(g), "diff": float(x.mean()),
            "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}


if __name__ == "__main__":
    argv = sys.argv[1:]
    cpath = argv[argv.index("--clusters") + 1]; which = argv[argv.index("--which") + 1]
    CL.update(json.load(open(cpath))[which])
    for opt in ("--clusters", "--which"):
        i = argv.index(opt); del argv[i:i + 2]
    S.boot = boot_cluster
    sys.argv = [sys.argv[0]] + argv
    S.main()
