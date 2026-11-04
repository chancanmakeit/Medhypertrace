"""Round 84: false-positive calibration of medical-aegis protocol v3 (eval_v3_2026-11-04). Offline, no API.

  python null_calibration.py <medical-aegis>/data_runs/eval_v3_2026-11-04

Protocol v3 (scripts/branch_v3_analysis.py): stage 1 = branch reps 0-1 + control reps 0-1; all 4 finals equal -> stop.
Else 6 + 6; reference = MODAL CONTROL answer (tie: control rep 0); one-sided Fisher (control matches reference more
often than branch), p < 0.05 -> positive.

Null H0: t has no effect, so the 12 finals of a point are exchangeable between arms. Conditional on each stage-2 point's
observed multiset of 12 finals, we draw random assignments of the 12 finals to the 12 slots (b0..b5, c0..c5) and
re-apply the full rule (stage-1 screen on b0, b1, c0, c1; reference; Fisher). P0 = P(called positive | multiset, reached
stage 2) under H0; sum(P0) over stage-2 points = expected positives if t never mattered (conditional on reaching stage 2).
Rules compared:
  ctrl_mode  : the protocol as run (reference chosen from the control arm)
  pooled_mode: reference = mode of all 12 finals (symmetric in the arms; tie -> lexicographically smallest)
E0 is conditional on the observed multisets, which also contain real effects (more spread than under H0), so
E0 / observed is a rough upper-bound FDR estimate.
"""
import gzip, json, os, sys, random
from collections import Counter, defaultdict
from scipy.stats import fisher_exact

ALPHA = 0.05
PV = {(a, b): fisher_exact([[a, 6 - a], [b, 6 - b]], alternative="greater")[1] for a in range(7) for b in range(7)}


def call(br, ct, rule):
    if len({br[0], br[1], ct[0], ct[1]}) == 1: return False
    if rule == "pooled_mode":
        cnt = Counter(br + ct); top = max(cnt.values()); ref = sorted(k for k, v in cnt.items() if v == top)[0]
    else:
        cnt = Counter(ct); top = max(cnt.values())
        ref = ct[0] if cnt[ct[0]] == top else sorted(k for k, v in cnt.items() if v == top)[0]
    a, b = sum(x == ref for x in ct), sum(x == ref for x in br)
    return PV[(a, b)] < ALPHA


def main(d, R=2000, seed=0):
    rng = random.Random(seed); out = {}
    for fw in sorted(os.listdir(d)):
        p = os.path.join(d, fw, "labels_v3.jsonl.gz")
        if not os.path.exists(p): continue
        agg = defaultdict(float); n2 = 0; n_all = 0; reported = 0
        for l in gzip.open(p, "rt"):
            r = json.loads(l); n_all += 1; s = r.get("statistics") or {}
            reported += r["judgment"] == "positive"
            if s.get("stage") != 2: continue
            br = [str(x) for x in s["branch_finals"]]; ct = [str(x) for x in s["control_finals"]]
            if len(br) != 6 or len(ct) != 6: continue
            n2 += 1
            for rule in ("ctrl_mode", "pooled_mode"): agg["obs_" + rule] += call(br, ct, rule)
            pool = br + ct; hits = Counter(); reach = 0
            for _ in range(R):
                rng.shuffle(pool); b_, c_ = pool[:6], pool[6:]
                if len({b_[0], b_[1], c_[0], c_[1]}) == 1: continue
                reach += 1
                for rule in ("ctrl_mode", "pooled_mode"): hits[rule] += call(b_, c_, rule)
            for rule in ("ctrl_mode", "pooled_mode"): agg["null_" + rule] += hits[rule] / max(reach, 1)
        out[fw] = {"points": n_all, "stage2": n2, "reported_positive": reported, **{k: round(v, 1) for k, v in agg.items()}}
    tot = defaultdict(float)
    for v in out.values():
        for k, x in v.items(): tot[k] += x
    out["TOTAL"] = {k: round(v, 1) for k, v in tot.items()}
    print(f"{'job':24s} {'pts':>6s} {'st2':>5s} {'rep+':>5s} | {'ctrl_mode obs':>13s} {'E0':>6s} {'FDR~':>5s} | {'pooled obs':>10s} {'E0':>6s} {'FDR~':>5s}")
    for fw, v in out.items():
        f1 = v["null_ctrl_mode"] / v["obs_ctrl_mode"] if v.get("obs_ctrl_mode") else float("nan")
        f2 = v["null_pooled_mode"] / v["obs_pooled_mode"] if v.get("obs_pooled_mode") else float("nan")
        print(f"{fw:24s} {v['points']:6.0f} {v['stage2']:5.0f} {v['reported_positive']:5.0f} | {v.get('obs_ctrl_mode',0):13.0f} {v.get('null_ctrl_mode',0):6.1f} {f1:5.2f} | "
              f"{v.get('obs_pooled_mode',0):10.0f} {v.get('null_pooled_mode',0):6.1f} {f2:5.2f}")
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "null_calibration.json"), "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
