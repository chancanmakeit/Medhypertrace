"""Round 84: trivial-baseline audit of the medical-aegis protocol-v3 eval set (eval_v3_2026-11-04). Offline, no API.

  python trivial_baselines.py <medical-aegis>/data_runs/eval_v3_2026-11-04

Per job: parents with >= 1 positive and >= 1 other point. Within-trajectory AUROC (positive vs every other point of the
same parent; ties 0.5) of trivial scores computed from the frozen parent run only:
  len   = characters of step t's output;  pos = relative position t / (n-1);  early = -pos.
Also the contrast "positive vs stage-1-stable" (all 4 stage-1 finals equal), which medical-aegis asked about (Q4).
Positives whose D(t) is empty (t = last LLM step of the parent) are reported separately and excluded from the main rows.
Mean over parents; 95% CI by parent bootstrap (parents = distinct questions here, K=1).
"""
import gzip, json, glob, os, sys, random
from collections import defaultdict


def auroc(pos, neg):
    if not pos or not neg: return None
    return sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg) / (len(pos) * len(neg))


def boot(x, B=2000, seed=0):
    if not x: return None
    rng = random.Random(seed); m = sum(x) / len(x)
    bs = sorted(sum(rng.choice(x) for _ in x) / len(x) for _ in range(B))
    return m, bs[int(0.025 * B)], bs[int(0.975 * B) - 1]


def main(d):
    # parent file per job (the parents' `dataset` field is not reliable: MM / MAM runs say medxpertqa-text / _text)
    pf = {"mam_heartbeat_a": "mam__normal_audio_heartbeat_a", "mam_heartbeat_b": "mam__normal_audio_heartbeat_b",
          "mam_sounddr": "mam__normal_audio_sounddr", "triage_agent": "triage_agent__normal_triage"}
    for ds in ("kvasir_vqa_x1", "medxpertqa_mm", "pathvqa", "slake"): pf["mm_" + ds] = "mdagents__normal_mm_" + ds

    def parents(job):
        par = {}
        for l in gzip.open(os.path.join(d, "parents", pf.get(job, job + "__normal_eval") + ".jsonl.gz"), "rt"):
            r = json.loads(l)
            par[(r["id"], int(r["run_index"]))] = [h for h in r["injection_log"]["conversation_history"] if isinstance(h.get("input_messages"), list)]
        return par
    print(f"{'job':20s} {'parents+':>8s} {'pos':>4s} {'pos_last':>8s} | {'AUROC len':>22s} | {'AUROC pos(late)':>22s} | {'pos vs stable: len':>22s} | share pos at t=0")
    for job in sorted(os.listdir(d)):
        p = os.path.join(d, job, "labels_v3.jsonl.gz")
        if not os.path.exists(p): continue
        by = defaultdict(list); par = parents(job); miss = 0
        for l in gzip.open(p, "rt"):
            L = json.loads(l); fw, model, ds, qid, mode, ri = L["target"]["run_id"].split("|")
            st = par.get((qid, int(ri[1:])))
            t = L["target"]["t_index"]
            if st is None or t >= len(st) or st[t].get("step_id") not in L["target"]["step_ids"]: miss += 1; continue
            n = len(st)
            s = L.get("statistics") or {}
            by[L["target"]["run_id"]].append({"pos": L["judgment"] == "positive", "last": t == n - 1,
                                             "stable": s.get("stage") == 1 and L["judgment"] == "undetermined",
                                             "len": len(st[t].get("content") or st[t].get("response") or ""),
                                             "rel": t / max(n - 1, 1), "t": t})
        res = defaultdict(list); npos = nlast = 0; t0 = []
        for rid, pts in by.items():
            P = [q for q in pts if q["pos"] and not q["last"]]; nlast += sum(q["pos"] and q["last"] for q in pts)
            if not P: continue
            npos += len(P); t0 += [q["t"] == 0 for q in P]
            O = [q for q in pts if not q["pos"]]; S = [q for q in pts if q["stable"]]
            for k in ("len", "rel"):
                a = auroc([q[k] for q in P], [q[k] for q in O])
                if a is not None: res[k].append(a)
            a = auroc([q["len"] for q in P], [q["len"] for q in S])
            if a is not None: res["len_vs_stable"].append(a)
        f = lambda b: "n/a" if not b else f"{b[0]:.3f} [{b[1]:.3f},{b[2]:.3f}]"
        print(f"{job:20s} {len(res['len']):8d} {npos:4d} {nlast:8d} | {f(boot(res['len'])):>22s} | {f(boot(res['rel'])):>22s} | "
              f"{f(boot(res['len_vs_stable'])):>22s} | {sum(t0)}/{len(t0)}" + (f"  [unmatched labels {miss}]" if miss else ""))


if __name__ == "__main__":
    main(sys.argv[1])
