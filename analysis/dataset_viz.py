r"""
Dataset visualizations (descriptive; no annotations needed). Produces publication-style
figures for the dataset section. Escape-rate / signature figures that need real
annotations are stubbed and print how to enable them.

Figures:
  fig1_length_dist.png    trajectory-length distribution per framework
  fig2_fm_bar.png         MAST-14 failure-mode distribution (bar)
  fig3_fault_position.png normalized position of earliest injected error (density)
  fig4_multifault.png     distribution of #responsible agents (multi-fault profile)
  fig5_fw_fm_heatmap.png  framework x FM heatmap (share within framework)

Run: MHT_DATA_DIR=... python analysis/dataset_viz.py --outdir docs/figs
     [--frameworks mdagents dylan ...]
"""
import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != "/" and not _os.path.isdir(_os.path.join(_r, "common")):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)

import argparse
from collections import Counter

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from common.data import load_jsonl, FM_TYPES
from common.paths import FILES


def _frameworks(subset):
    if not subset:
        return list(FILES)
    bad = [f for f in subset if f not in FILES]
    if bad:
        raise SystemExit(f"unknown framework(s) {bad}; valid: {list(FILES)}")
    return [f for f in FILES if f in subset]


def _load(fws):
    return {name: load_jsonl(FILES[name]) for name in fws}


def fig_length_dist(data, outdir):
    plt.figure(figsize=(7, 4))
    for name, trajs in data.items():
        lens = [len([s for s in t.steps if not s.is_input]) for t in trajs]
        plt.hist(lens, bins=range(1, max(lens) + 2), alpha=0.5, label=name)
    plt.xlabel("trajectory length (acting steps)")
    plt.ylabel("count")
    plt.title("Trajectory length distribution")
    plt.legend(fontsize=8)
    plt.tight_layout()
    p = f"{outdir}/fig1_length_dist.png"
    plt.savefig(p, dpi=150); plt.close()
    return p


def fig_fm_bar(data, outdir):
    fm_all = Counter()
    for trajs in data.values():
        for t in trajs:
            for _, fms in t.labels.instance_fms.items():
                for fm in fms:
                    fm_all[fm] += 1
    counts = [fm_all.get(fm, 0) for fm in FM_TYPES]
    plt.figure(figsize=(8, 4))
    plt.bar(range(len(FM_TYPES)), counts, color="#4C72B0")
    plt.xticks(range(len(FM_TYPES)), FM_TYPES, rotation=60, ha="right", fontsize=7)
    plt.ylabel("injection count")
    plt.title("Failure-mode (MAST-14) distribution")
    plt.tight_layout()
    p = f"{outdir}/fig2_fm_bar.png"
    plt.savefig(p, dpi=150); plt.close()
    return p


def fig_fault_position(data, outdir):
    plt.figure(figsize=(7, 4))
    for name, trajs in data.items():
        pos = []
        for t in trajs:
            acting = [s for s in t.steps if not s.is_input]
            gi = next((i for i, s in enumerate(acting)
                       if s.turn == t.labels.earliest_error_turn), None)
            if gi is not None and len(acting) > 1:
                pos.append(gi / (len(acting) - 1))
        if pos:
            plt.hist(pos, bins=20, range=(0, 1), density=True, alpha=0.4, label=name)
    plt.xlabel("normalized position of earliest error (0=start, 1=end)")
    plt.ylabel("density")
    plt.title("Where the earliest injected error occurs")
    plt.legend(fontsize=8)
    plt.tight_layout()
    p = f"{outdir}/fig3_fault_position.png"
    plt.savefig(p, dpi=150); plt.close()
    return p


def fig_multifault(data, outdir):
    plt.figure(figsize=(7, 4))
    names = list(data)
    maxk = 1
    dist_by_fw = {}
    for name, trajs in data.items():
        ks = [len({a for a, _ in t.labels.instance_fms.keys()}) for t in trajs]
        c = Counter(ks); dist_by_fw[name] = c
        maxk = max(maxk, max(ks) if ks else 1)
    xs = list(range(1, maxk + 1))
    w = 0.8 / max(len(names), 1)
    for i, name in enumerate(names):
        c = dist_by_fw[name]
        tot = sum(c.values())
        ys = [100 * c.get(k, 0) / tot for k in xs]
        plt.bar([x + i * w for x in xs], ys, width=w, label=name)
    plt.xlabel("# responsible agents per trajectory")
    plt.ylabel("% of trajectories")
    plt.title("Multi-fault profile")
    plt.xticks([x + 0.4 for x in xs], xs)
    plt.legend(fontsize=8)
    plt.tight_layout()
    p = f"{outdir}/fig4_multifault.png"
    plt.savefig(p, dpi=150); plt.close()
    return p


def fig_fw_fm_heatmap(data, outdir):
    fws = list(data)
    mat = np.zeros((len(fws), len(FM_TYPES)))
    for r, name in enumerate(fws):
        c = Counter()
        for t in data[name]:
            for _, fms in t.labels.instance_fms.items():
                for fm in fms:
                    c[fm] += 1
        tot = sum(c.values()) or 1
        for j, fm in enumerate(FM_TYPES):
            mat[r, j] = 100 * c.get(fm, 0) / tot
    plt.figure(figsize=(9, 3 + 0.3 * len(fws)))
    im = plt.imshow(mat, aspect="auto", cmap="viridis")
    plt.colorbar(im, label="% within framework")
    plt.yticks(range(len(fws)), fws, fontsize=8)
    plt.xticks(range(len(FM_TYPES)), FM_TYPES, rotation=60, ha="right", fontsize=7)
    plt.title("Framework x failure-mode preference")
    plt.tight_layout()
    p = f"{outdir}/fig5_fw_fm_heatmap.png"
    plt.savefig(p, dpi=150); plt.close()
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frameworks", nargs="+", default=None)
    ap.add_argument("--outdir", default="docs/figs")
    args = ap.parse_args()
    fws = _frameworks(args.frameworks)
    _os.makedirs(args.outdir, exist_ok=True)
    data = _load(fws)
    made = [
        fig_length_dist(data, args.outdir),
        fig_fm_bar(data, args.outdir),
        fig_fault_position(data, args.outdir),
        fig_multifault(data, args.outdir),
        fig_fw_fm_heatmap(data, args.outdir),
    ]
    for p in made:
        print("wrote", p)
    print("\nNote: signature (2x3 A/B x S+/S~/S-) and escape-rate figures need real "
          "annotations — add them once annotation is available.")


if __name__ == "__main__":
    main()
