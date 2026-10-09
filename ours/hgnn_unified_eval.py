"""
Unified-metric evaluation for MedHyperTrace v2: derive per-trajectory (agent, FM)
pairs from the PAIR head using per-class thresholds calibrated on val (improvement
A+F), score with the vendored compute_metrics at BOTH granularities, plus the step
sub-metric (earliest-error-step Top-1/Top-3).

Usage: python ours/hgnn_unified_eval.py [framework|all] [--features ...] [--struct ...]
       (accepts all train_hgnn flags)
"""
import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)

import sys
import numpy as np
import torch

from common.data import FM_TYPES
from common.aegis_metrics import compute_metrics
from common.paths import FILES
from ours import train_hgnn as T


def _inst(aid):
    body = aid[3:]
    name, idx = body.rsplit("#", 1)
    return name, int(idx)


def _surface(name, idx, gran):
    return f"{name} {idx}" if gran == "instance" else name


@torch.no_grad()
def predict_pairs(model, samples, feat_dim, thr, gran):
    model.eval()
    preds = []
    for s in samples:
        b = T.collate([s], feat_dim)
        _, _, pl = model(b["feats"], b["type_ids"], b["type_slices"], b["incidence"])
        prob = torch.sigmoid(pl).numpy()
        pset = set()
        for k, aid in enumerate(s["agent_ids"]):
            name, idx = _inst(aid)
            surf = _surface(name, idx, gran)
            for j in range(len(FM_TYPES)):
                if prob[k, j] > thr[j]:
                    pset.add((surf, FM_TYPES[j]))
        preds.append(sorted(pset))
    return preds


def gt_pairs(te_trajs, gran):
    out = []
    for t in te_trajs:
        ps = {( _surface(a, ri, gran), fm)
              for (a, ri), fms in t.labels.instance_fms.items() for fm in fms}
        out.append(sorted(ps))
    return out


def main(argv):
    target = argv[0] if argv and not argv[0].startswith("-") else "all"
    args = T.get_args([a for a in argv if a.startswith("-") or
                       argv.index(a) > 0 and argv[argv.index(a)-1].startswith("-")]) \
        if False else T.get_args(["x"] + [a for a in argv[1:]])
    targets = list(FILES) if target == "all" else [target]
    # --frameworks restricts the subset when target is 'all'
    subset = None
    for i, a in enumerate(argv):
        if a == "--frameworks":
            subset = []
            for b in argv[i + 1:]:
                if b.startswith("-"):
                    break
                subset.append(b)
    if subset and target == "all":
        bad = [f for f in subset if f not in FILES]
        if bad:
            raise SystemExit(f"unknown framework(s) {bad}; valid: {list(FILES)}")
        targets = [f for f in FILES if f in subset]
    # optional json dump for make_main_table.py (shape {framework:{"ours":{metrics}}})
    json_out = None
    for i, a in enumerate(argv):
        if a == "--json_out" and i + 1 < len(argv):
            json_out = argv[i + 1]
    pooled_out = None
    for i, a in enumerate(argv):
        if a == "--pooled_out" and i + 1 < len(argv):
            pooled_out = argv[i + 1]
    gran_out = "instance"
    for i, a in enumerate(argv):
        if a == "--report_gran" and i + 1 < len(argv):
            gran_out = argv[i + 1]
    dump = {}
    # accumulators for correct pooled Micro-F1 (concatenate preds/gts, score once)
    pool_preds, pool_gts = [], []
    pool_shit = pool_stot = 0
    hdr = (f"{'framework':<12}{'gran':<10}{'Agent-mi':>9}{'Agent-ma':>9}"
           f"{'Error-mi':>9}{'Error-ma':>9}{'Pair-mi':>9}{'Pair-ma':>9}")
    for name in targets:
        model, fz, thr, feat_dim, res = T.run(name=name, args=args)
        m = res[name]
        print("\n" + hdr)
        for gran in ["instance", "role"]:
            preds = predict_pairs(model, m["te_samples"], feat_dim, thr, gran)
            gts = gt_pairs(m["te_trajs"], gran)
            cm = compute_metrics(preds, gts)
            print(f"{name:<12}{gran:<10}{cm['agent_micro_f1']:>9.1f}"
                  f"{cm['agent_macro_f1']:>9.1f}{cm['error_micro_f1']:>9.1f}"
                  f"{cm['error_macro_f1']:>9.1f}{cm['pair_micro_f1']:>9.1f}"
                  f"{cm['pair_macro_f1']:>9.1f}")
            if gran == gran_out:
                cm = dict(cm)
                cm["step_acc"] = m["step_top1"]        # unify key name with set eval
                cm["n"] = len(m["te_trajs"])
                dump.setdefault(name, {})["ours"] = cm
                # accumulate for pooled (use the reported granularity)
                pool_preds.extend(preds)
                pool_gts.extend(gts)
                pool_shit += m["step_top1"] * len(m["te_trajs"])
                pool_stot += len(m["te_trajs"])
        print(f"  step: Top-1={m['step_top1']:.3f} Top-3={m['step_top3']:.3f} "
              f"(n_test={len(m['te_trajs'])})")
    if json_out:
        import json
        json.dump(dump, open(json_out, "w"), indent=1)
        print(f"\nwrote {json_out} (report_gran={gran_out})")
    if pooled_out:
        import json
        cm = compute_metrics(pool_preds, pool_gts)
        cm["step_acc"] = (pool_shit / pool_stot) if pool_stot else None
        cm["n"] = len(pool_preds)
        json.dump({"pooled": {"ours": cm}}, open(pooled_out, "w"), indent=1)
        print(f"wrote {pooled_out} (framework-agnostic pooled, gran={gran_out})")


if __name__ == "__main__":
    main(sys.argv[1:])
