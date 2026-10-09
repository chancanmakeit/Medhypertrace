"""MedHyperTrace inference on the MAFA human-like eval set (feasibility + error analysis only).

There is no saved MedHyperTrace checkpoint, so for each framework present in the eval set
we train ONE model with the code's DEFAULT hyperparameters (train_hgnn.get_args defaults:
tfidf features, struct=1, relation backbone, prop=0.1, margin=0.5, 20 epochs, bs=16,
hidden=128, lr=2e-3, seed 0) on that framework's FIXED synthetic-injection train split
(common/splits.json; its val part only calibrates the per-FM thresholds, as in the normal
pipeline). The MAFA labels are never used for training, model selection or thresholds.

Decision rules (fixed BEFORE scoring, not chosen on the eval rows):
  step_scores  softmax of the step head over the trace's acting steps (head is trained
               listwise on the earliest faulty step)
  pred_step    argmax step_scores
  agent_scores sigmoid of the agent head (trained on "agent is faulty"), max over our
               instances mapping to one MAFA uid
  pred_agent   PRIMARY  (rule "step-owner"): the agent that executed pred_step
               SECONDARY(rule "agent-head"): argmax agent_scores  -> separate file
  pred_codes   MAST rows only: per FM code, max over agents of the pair-head probability,
               monotonically rescaled so the code's val-calibrated threshold maps to 0.5
               (the scorer thresholds at 0.5; this preserves the method's own decision).
               MedAgentAudit rows: no pred_codes (the method has no MedAgentAudit head).

Usage: python eval_mafa/predict.py [--seed 0] [--mafa_root ...] [--out_dir eval_mafa/out]
"""
import argparse
import json
import os
import random
import sys

_r = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _r not in sys.path:
    sys.path.insert(0, _r)

import numpy as np  # noqa: E402
import torch  # noqa: E402

from common.data import FM_TYPES  # noqa: E402
from eval_mafa.adapter import load_eval  # noqa: E402
from ours import train_hgnn as T  # noqa: E402


def seed_all(s):
    torch.manual_seed(s); np.random.seed(s); random.seed(s)


def rescale(p, thr):
    thr = min(max(float(thr), 1e-6), 1 - 1e-6)
    return 0.5 * p / thr if p < thr else 0.5 + 0.5 * (p - thr) / (1 - thr)


@torch.no_grad()
def infer(model, sample, feat_dim):
    model.eval()
    b = T.collate([sample], feat_dim)
    sl, al, pl = model(b["feats"], b["type_ids"], b["type_slices"], b["incidence"])
    return (torch.softmax(sl, 0).numpy(), torch.sigmoid(al).numpy(), torch.sigmoid(pl).numpy())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--mafa_root", default="/home/claude/mafa-human-ai-annotation")
    ap.add_argument("--out_dir", default="eval_mafa/out")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    rows = load_eval(a.mafa_root)
    labels = [json.loads(x) for x in open(
        os.path.join(a.mafa_root, "results/human_like_eval/labels_v1.jsonl"), encoding="utf-8")]
    tax_of = {}
    for L in labels:
        tax_of.setdefault(L["trace_id"], []).append(L["taxonomy"])

    args = T.get_args(["x"])                      # code defaults, untouched
    fws = sorted({t["framework"] for t, _, _ in rows})
    models, meta = {}, {"seed": a.seed, "config": {k: v for k, v in vars(args).items()
                                                    if k not in ("target",)}, "frameworks": {}}
    for fw in fws:
        seed_all(a.seed)
        print(f"== training {fw} (defaults, seed {a.seed})", flush=True)
        model, fz, thr, feat_dim, res = T.run(name=fw, args=args)
        models[fw] = (model, fz, thr, feat_dim)
        meta["frameworks"][fw] = {"synthetic_test_step_top1": round(res[fw]["step_top1"], 3),
                                  "synthetic_test_n": len(res[fw]["te_trajs"]),
                                  "fm_thresholds": {FM_TYPES[j]: round(float(thr[j]), 2)
                                                    for j in range(len(FM_TYPES))}}

    prim, sec, detail = [], [], []
    for t, traj, m in rows:
        model, fz, thr, feat_dim = models[t["framework"]]
        s = T.build_sample(traj, fz, args.struct, None)
        sp, ap_, pp = infer(model, s, feat_dim)
        acting = {f"s{x.turn}": x for x in traj.steps if not x.is_input}
        step_scores = {m["turn2sid"][acting[sid].turn]: float(sp[j]) for j, sid in enumerate(s["step_ids"])}
        uid_of = {}
        agent_scores, code_p = {}, {}
        for k, aid in enumerate(s["agent_ids"]):
            name, idx = aid[3:].rsplit("#", 1)
            uid = m["inst2uid"][(name, int(idx))]
            uid_of[aid] = uid
            agent_scores[uid] = max(agent_scores.get(uid, 0.0), float(ap_[k]))
            for j, fm in enumerate(FM_TYPES):
                code_p[fm] = max(code_p.get(fm, 0.0), float(pp[k, j]))
        pred_step = max(step_scores, key=step_scores.get)
        sid2uid = {m["turn2sid"][x.turn]: m["inst2uid"][x.instance] for x in acting.values()}
        owner = sid2uid[pred_step]
        head = max(agent_scores, key=agent_scores.get)
        codes = {fm: round(rescale(code_p[fm], thr[j]), 4) for j, fm in enumerate(FM_TYPES)}
        for tax in tax_of.get(t["trace_id"], []):
            base = {"trace_id": t["trace_id"], "taxonomy": tax,
                    "agent_scores": {u: round(v, 4) for u, v in agent_scores.items()},
                    "step_scores": {k: round(v, 4) for k, v in sorted(step_scores.items())},
                    "pred_step": pred_step}
            if tax == "MAST":
                base["pred_codes"] = codes
            prim.append({**base, "pred_agent": owner})
            sec.append({**base, "pred_agent": head})
        detail.append({"trace_id": t["trace_id"], "framework": t["framework"],
                       "pred_step": pred_step, "pred_agent_step_owner": owner,
                       "pred_agent_head": head, "step_scores": step_scores,
                       "agent_scores": agent_scores, "code_probs_raw": code_p,
                       "step_agents": sid2uid})

    suffix = "" if a.seed == 0 else f"_seed{a.seed}"
    for name, data in [(f"medhypertrace_pred{suffix}.jsonl", prim),
                       (f"medhypertrace_pred_agenthead{suffix}.jsonl", sec)]:
        with open(os.path.join(a.out_dir, name), "w", encoding="utf-8") as f:
            for d in data:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
    json.dump(detail, open(os.path.join(a.out_dir, f"detail{suffix}.json"), "w"), indent=1, ensure_ascii=False)
    json.dump(meta, open(os.path.join(a.out_dir, f"model_meta{suffix}.json"), "w"), indent=1)
    print(f"wrote {len(prim)} prediction rows for {len(rows)} traces to {a.out_dir}")


if __name__ == "__main__":
    main()
