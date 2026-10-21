"""Row-level error analysis for MedHyperTrace on MAFA human-like-v1 (MAFA doc §6 step 6).

Inputs: predictions (one seed), labels_v1.jsonl, traces_v1.jsonl, detail.json.
Answers:  per-framework errors; systematic later/earlier bias (signed step offset, rank of
the labelled step in the model's step ranking, aggregator/last-step pull); whether a wrong
pred_step lands on ANY labelled-present code step (secondary reference); first-step
baseline per framework; agent-head ranking per trace.
"""
import collections
import json
import os
import sys

MAFA = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/mafa-human-ai-annotation"
OUT = sys.argv[2] if len(sys.argv) > 2 else "eval_mafa/out"
SUF = sys.argv[3] if len(sys.argv) > 3 else ""

labels = [json.loads(x) for x in open(f"{MAFA}/results/human_like_eval/labels_v1.jsonl", encoding="utf-8")]
traces = {json.loads(x)["trace_id"]: json.loads(x) for x in open(f"{MAFA}/results/human_like_eval/traces_v1.jsonl", encoding="utf-8")}
detail = {d["trace_id"]: d for d in json.load(open(f"{OUT}/detail{SUF}.json", encoding="utf-8"))}


def n(s):
    return int(s[1:])


rows, agg = [], collections.defaultdict(collections.Counter)
for L in labels:
    t, d = traces[L["trace_id"]], detail[L["trace_id"]]
    steps = [s["id"] for s in t["steps"]]
    ranking = sorted(d["step_scores"], key=d["step_scores"].get, reverse=True)
    gold, ps = L["earliest_step"], d["pred_step"]
    present_steps = sorted({c["step"] for c in L["codes"].values()
                            if c.get("decision") == "present" and c.get("step")}, key=n)
    agent_rank = sorted(d["agent_scores"], key=d["agent_scores"].get, reverse=True)
    roles = {s["id"]: (s.get("role") or s["agent"].rsplit("-", 1)[0]) for s in t["steps"]}
    r = {
        "row": f"{L['taxonomy']}|{L['trace_id']}", "framework": L["framework"], "taxonomy": L["taxonomy"],
        "n_steps": len(steps), "gold_step": gold, "gold_agent": L["earliest_step_agent"],
        "pred_step": ps, "pred_agent": d["pred_agent_step_owner"], "pred_role": roles[ps],
        "offset": n(ps) - n(gold), "gold_rank_in_model": ranking.index(gold) + 1,
        "pred_is_last": ps == steps[-1], "pred_in_present_code_steps": ps in present_steps,
        "present_code_steps": present_steps, "first_step_baseline_hit": steps[0] == gold,
        "faulty_agents": L["faulty_agents"], "agent_head_top": agent_rank[0],
        "agent_head_top_role": agent_rank[0].rsplit("-", 1)[0],
        "agent_head_top_is_faulty": agent_rank[0] in L["faulty_agents"],
        "step_probs": {k: round(v, 3) for k, v in sorted(d["step_scores"].items(), key=lambda kv: n(kv[0]))},
    }
    rows.append(r)
    fw = r["framework"]
    for key in (fw, "ALL"):
        a = agg[key]
        a["rows"] += 1
        a["when_exact"] += ps == gold
        a["first_step_when_exact"] += r["first_step_baseline_hit"]
        a["pred_later"] += r["offset"] > 0
        a["pred_earlier"] += r["offset"] < 0
        a["pred_last"] += r["pred_is_last"]
        a["wrong_but_on_present_step"] += (ps != gold) and r["pred_in_present_code_steps"]
        a["gold_is_s01"] += gold == steps[0]
        a["pred_is_s01"] += ps == steps[0]
        a[f"pred_role:{r['pred_role']}"] += 1
        a[f"head_top_role:{r['agent_head_top_role']}"] += 1

json.dump({"rows": rows, "by_framework": {k: dict(v) for k, v in agg.items()}},
          open(f"{OUT}/error_analysis{SUF}.json", "w"), indent=1, ensure_ascii=False)

print(f"{'row':<64}{'gold':>6}{'pred':>6}{'off':>5}{'rank':>5} {'pred_role':<18}{'onPresent':>10}")
for r in sorted(rows, key=lambda r: (r["framework"], r["row"])):
    flag = "" if r["pred_step"] == r["gold_step"] else " x"
    print(f"{r['row'][:63]:<64}{r['gold_step']:>6}{r['pred_step']:>6}{r['offset']:>5}"
          f"{r['gold_rank_in_model']:>5} {r['pred_role'][:17]:<18}{str(r['pred_in_present_code_steps']):>10}{flag}")
print()
for k, v in agg.items():
    print(k, dict(v))
