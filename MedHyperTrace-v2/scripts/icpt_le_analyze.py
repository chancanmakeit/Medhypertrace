"""Round 95: InteractionCPT pre-registration §4.2 / H4 -- label efficiency on public data (WW + TEgc, controlled area).

Reuses scripts/stage0_analyze.py unchanged (le_metrics / compare_le / per_traj / matched) and the question-clustered
bootstrap of scripts/stage0_cluster_ci.py (jac0.7, 170 clusters; prereg §4.2 says "按题目聚类(jac0.7)").
Only the label-efficiency file location differs: $W/icpt/le_<iface>/le_<head>_<proxy>.json (written by the icpt driver's
final() with the same stage0/subsets.json draws).

  python scripts/icpt_le_analyze.py --w <mht_work> --clusters <mht_work>/stage0/cluster_ci/clusters.json --out <json>
"""
import argparse, json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import stage0_analyze as S       # noqa: E402
import stage0_cluster_ci as C    # noqa: E402

PAIRS = (("icpt", "lm"), ("icpt", "base"), ("lm", "base"))   # H4 order: H1-like, H2-like, H3-like
HEADS = ("agg", "linear", "mlp")                               # agg = main interface (A4); linear named in §1 table


class IcptData(S.Data):
    def __init__(self, W, iface):
        super().__init__(W, None); self.iface = iface

    def le(self, head, proxy):
        p = os.path.join(self.W, "icpt", f"le_{self.iface}", f"le_{head}_{proxy}.json")
        if not os.path.exists(p): return None
        d = json.load(open(p))["scores"]
        return {n: {S.K(k): v for k, v in d[f"{head}_{proxy}_n{n}"].items() if S.K(k)[0] in S.EVAL_DS}
                for n in S.SIZES if f"{head}_{proxy}_n{n}" in d}

    def clean_keys(self, x, y, supervised): return set()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--w"); ap.add_argument("--clusters"); ap.add_argument("--out")
    a = ap.parse_args()
    C.CL.update(json.load(open(a.clusters))["jac0.7"]); S.boot = C.boot_cluster
    R = {}
    for iface in ("prefix", "query"):
        D = IcptData(a.w, iface); rng = np.random.default_rng(0)
        for h in HEADS:
            for x, y in PAIRS:
                r = S.compare_le(D, rng, h, x, y)
                if r is None: print(f"{iface} {h} {x}-{y}: missing"); continue
                g = [r[f"n{n}"]["matched"].get("diff") for n in S.SIZES]
                R[f"{iface}/{h}/{x}-{y}"] = r
                b = r["area_resid"]; ab = r["abs"]
                print(f"{iface:6s} {h:6s} {x}-{y:5s} area resid {b['diff']:+.4f} [{b['ci95'][0]:+.4f}, {b['ci95'][1]:+.4f}] "
                      f"n={b['n']}/{b.get('n_clusters')}cl raw {r['area_raw']['diff']:+.4f} -> {r['verdict']}"
                      f" | abs {x} {ab[x]['area_resid']:.3f} {y} {ab[y]['area_resid']:.3f}"
                      f" | matched n100/300/1000 " + " ".join(f"{v:+.3f}" if v is not None else "na" for v in g), flush=True)
    json.dump(R, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
