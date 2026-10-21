r"""
Dataset analysis for the paper (quantitative + structural), in the spirit of the
data-analysis sections of Who&When / Who&When Pro.

Produces:
  1. Scale table       : per-framework total / train / test (task-level split)
  2. Structure table   : steps, #agents, multi-fault %, #responsible agents
  3. FM distribution   : all 14 MAST types, injection counts + coverage
  4. Agent-role profile: distinct roles per framework, most faulted roles
  5. Modality note      : which frameworks carry images (multimodal)
  6. Fault-position     : where in the trajectory the earliest injected error sits

Run:  MHT_DATA_DIR=... python analysis/dataset_analysis.py --out docs/dataset_stats.md
Text tables print to stdout AND (with --out) write a markdown report.
"""
import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != "/" and not _os.path.isdir(_os.path.join(_r, "common")):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)

import argparse
import json
from collections import Counter

import numpy as np

from common.data import load_jsonl, FM_TYPES
from common.paths import FILES
from common.splits import load_split


def _frameworks(subset):
    """Resolve the framework subset (canonical order), or all five if None."""
    if not subset:
        return list(FILES)
    bad = [f for f in subset if f not in FILES]
    if bad:
        raise SystemExit(f"unknown framework(s) {bad}; valid: {list(FILES)}")
    return [f for f in FILES if f in subset]


def scale_table(fws):
    rows, tot = [], [0, 0, 0]
    for name in fws:
        trajs = load_jsonl(FILES[name])
        tr, te = load_split(name)
        ntr = sum(1 for t in trajs if t.id in tr)
        nte = sum(1 for t in trajs if t.id in te)
        n = len(trajs)
        rows.append((name, n, ntr, nte, 100 * nte / n))
        tot[0] += n; tot[1] += ntr; tot[2] += nte
    return rows, tot


def structure_table(fws):
    rows = []
    for name in fws:
        trajs = load_jsonl(FILES[name])
        steps = [len([s for s in t.steps if not s.is_input]) for t in trajs]
        nag = [len(t.instances) for t in trajs]
        resp = [len({a for a, _ in t.labels.instance_fms.keys()}) for t in trajs]
        multi_pct = 100 * sum(1 for m in resp if m > 1) / len(trajs)
        rows.append((name, np.mean(steps), int(np.median(steps)), max(steps),
                     np.mean(nag), multi_pct, np.mean(resp)))
    return rows


def fm_distribution(fws):
    fm_all = Counter()
    per_fw = {}
    for name in fws:
        trajs = load_jsonl(FILES[name])
        c = Counter()
        for t in trajs:
            for inst, fms in t.labels.instance_fms.items():
                for fm in fms:
                    c[fm] += 1; fm_all[fm] += 1
        per_fw[name] = c
    return fm_all, per_fw


def role_profile(fws):
    rows = []
    for name in fws:
        trajs = load_jsonl(FILES[name])
        roles = Counter()
        faulted = Counter()
        for t in trajs:
            for a, _ in t.instances:
                roles[a] += 1
            for a, _ in t.labels.instance_fms.keys():
                faulted[a] += 1
        top = ", ".join(f"{r}({n})" for r, n in faulted.most_common(3))
        rows.append((name, len(roles), top))
    return rows


def modality_note(fws):
    note = {}
    for name in fws:
        has_img = 0
        for line in open(FILES[name]):
            r = json.loads(line)
            if r.get("images"):
                has_img += 1
        note[name] = has_img
    return note


def fault_position(fws):
    """Where does the earliest injected error sit? (normalized position in 0..1)"""
    rows = []
    for name in fws:
        trajs = load_jsonl(FILES[name])
        pos = []
        for t in trajs:
            acting = [s for s in t.steps if not s.is_input]
            if not acting:
                continue
            gi = next((i for i, s in enumerate(acting)
                       if s.turn == t.labels.earliest_error_turn), None)
            if gi is not None and len(acting) > 1:
                pos.append(gi / (len(acting) - 1))
        if pos:
            rows.append((name, np.mean(pos), np.median(pos)))
    return rows


def escape_rate(fws, annotations_path=None):
    r"""ESCAPE-RATE skeleton (the key Nature-story validation).

    Definition: the escape rate is the fraction of REAL failures that cannot be attributed
    to a norm-violation (V(τ)=∅) — i.e. model-inherent (class B) failures that "escape" the
    MAST-14 architecture-coordination ontology. A non-trivial escape rate (e.g. 15-30%) is
    what makes the paper's core claim ("a class of failures escapes attribution") stand.

    This CANNOT be computed from the synthetic AEGIS data: every synthetic failure was
    injected as one of MAST-14, so by construction its escape rate is ~0. It requires REAL
    expert annotations carrying the V(τ) / A-B field (see docs/annotation_protocol.md §3.5).

    annotations_path: a jsonl where each line is one annotated failure with at least:
        {"framework":..., "traj_id":..., "attribution":"A"|"B"|"uncertain",
         "norm_violated": true|false|null, "fm_type": "FM-x.y"|null}
    When absent, this returns a not-available marker and prints how to produce it.

    Returns dict: per-framework and pooled {n_annotated, n_B, escape_rate, n_uncertain}.
    """
    if not annotations_path or not _os_exists(annotations_path):
        return {"available": False,
                "reason": "no real annotations yet; escape rate is undefined on synthetic "
                          "data (all injected as MAST-14). Provide --annotations <jsonl> "
                          "with A/B (V(τ)) labels once expert annotation is available."}
    rows = [json.loads(l) for l in open(annotations_path) if l.strip()]
    per = {}
    for r in rows:
        fw = r.get("framework", "?")
        if fws and fw not in fws:
            continue
        d = per.setdefault(fw, {"n": 0, "B": 0, "unc": 0})
        d["n"] += 1
        attr = (r.get("attribution") or "").upper()
        if attr == "B":
            d["B"] += 1
        elif attr not in ("A", "B"):
            d["unc"] += 1
    # pooled
    tot = {"n": sum(d["n"] for d in per.values()),
           "B": sum(d["B"] for d in per.values()),
           "unc": sum(d["unc"] for d in per.values())}
    for d in list(per.values()) + [tot]:
        d["escape_rate"] = (100 * d["B"] / d["n"]) if d["n"] else None
    return {"available": True, "per_framework": per, "pooled": tot}


def _os_exists(p):
    import os
    return os.path.exists(p)


def render(fws, out=None, annotations=None):
    L = []
    def p(s=""):
        print(s); L.append(s)

    p(f"(分析框架: {', '.join(fws)})\n")

    rows, tot = scale_table(fws)
    p("## 1. 数据集规模(task-level split)\n")
    p("| framework | total | train | test | test% |")
    p("|---|--:|--:|--:|--:|")
    for name, n, ntr, nte, pct in rows:
        p(f"| {name} | {n} | {ntr} | {nte} | {pct:.1f}% |")
    p(f"| **合计** | **{tot[0]}** | **{tot[1]}** | **{tot[2]}** | "
      f"**{100*tot[2]/tot[0]:.1f}%** |")

    p("\n## 2. 轨迹结构\n")
    p("| framework | 步数均/中/max | agent均 | 多故障% | 责任agent均 |")
    p("|---|--:|--:|--:|--:|")
    for name, mstep, medstep, mxstep, mag, mpct, mresp in structure_table(fws):
        p(f"| {name} | {mstep:.1f}/{medstep}/{mxstep} | {mag:.1f} | "
          f"{mpct:.1f}% | {mresp:.2f} |")

    fm_all, per_fw = fm_distribution(fws)
    total = sum(fm_all.values())
    p("\n## 3. 故障模式(MAST-14)分布\n")
    p(f"总注入 {total} 次,覆盖 "
      f"{sum(1 for fm in FM_TYPES if fm_all.get(fm,0)>0)}/14 类。\n")
    p("| FM | count | share |")
    p("|---|--:|--:|")
    for fm in FM_TYPES:
        n = fm_all.get(fm, 0)
        p(f"| {fm} | {n} | {100*n/total:.1f}% |" if total else f"| {fm} | 0 | - |")

    p("\n## 4. Agent 角色画像\n")
    p("| framework | 不同角色数 | 最常出错角色(次数) |")
    p("|---|--:|---|")
    for name, nrole, top in role_profile(fws):
        p(f"| {name} | {nrole} | {top} |")

    p("\n## 5. 模态\n")
    note = modality_note(fws)
    p("| framework | 带图像轨迹数 | 模态 |")
    p("|---|--:|---|")
    for name, n in note.items():
        p(f"| {name} | {n} | {'多模态(含医学影像)' if n else '纯文本'} |")

    p("\n## 6. 故障位置(最早注入错误步的归一化位置,0=开头 1=结尾)\n")
    p("| framework | 位置均值 | 位置中位 |")
    p("|---|--:|--:|")
    for name, mp, medp in fault_position(fws):
        p(f"| {name} | {mp:.2f} | {medp:.2f} |")

    p("\n## 7. 逃逸率(核心指标,依赖真实标注)\n")
    er = escape_rate(fws, annotations)
    if not er["available"]:
        p(f"> 暂不可用:{er['reason']}")
        p(">")
        p("> 合成数据上逃逸率恒≈0(全部按 MAST-14 注入),此指标必须用真实标注(带 A/B "
          "即 V(τ) 字段)。有标注后:--annotations real_labels.jsonl。")
    else:
        p("| framework | 已标注 | B类(逃逸) | 逃逸率 | 不确定 |")
        p("|---|--:|--:|--:|--:|")
        for fw, d in er["per_framework"].items():
            p(f"| {fw} | {d['n']} | {d['B']} | {d['escape_rate']:.1f}% | {d['unc']} |")
        tp = er["pooled"]
        p(f"| **合计** | **{tp['n']}** | **{tp['B']}** | "
          f"**{tp['escape_rate']:.1f}%** | **{tp['unc']}** |")

    if out:
        with open(out, "w") as f:
            f.write("# 数据集分析\n\n" + "\n".join(L) + "\n")
        print(f"\nwrote {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frameworks", nargs="+", default=None,
                    help="restrict analysis to a subset (default: all five)")
    ap.add_argument("--annotations", default=None,
                    help="jsonl of real expert annotations with A/B (V(tau)) labels")
    ap.add_argument("--out", default=None, help="write markdown report")
    args = ap.parse_args()
    fws = _frameworks(args.frameworks)
    render(fws, args.out, args.annotations)


if __name__ == "__main__":
    main()
