"""Build the MedAgentAudit human-evaluation set (400 instances) aligned to mas-traj/1 runs.
Each instance: (mas, llm, dataset, qid, code, target agent_id, target phase) + 3 human
verdicts -> majority; plus the LLM auditor's label (the sampling stratum: positive files
= auditor said 1). Output jsonl rows with run_id so they can be matched to converted runs.
Usage: python data_tools/maa_human_eval.py <release_dir> <out.jsonl>
"""
import glob, json, os, re, sys, collections
MAS = {"colacare": "colacare", "healthcareagent": "healthcareagent", "mac": "mac", "mdagents": "mdagents",
       "medagent": "medagent", "reconcile": "reconcile"}
def key_mas(x): return re.sub(r"[^a-z]", "", x.lower())
def main(rel, out):
    inst = []
    for f in sorted(glob.glob(os.path.join(rel, "human_eval/structured_logs_for_audit_human_evaluation/*.jsonl"))):
        for l in open(f):
            r = json.loads(l); t = r["instruction_text"]
            a = re.search(r"Target agent:\s*(\S+)", t); s = re.search(r"opinions on (\w+) step", t)
            inst.append({"qid": r["qid"], "mas": key_mas(r["mas"]), "llm": r["llm"], "dataset": r["dataset"],
                         "code": r["failure_code"], "agent_id": a.group(1) if a else None,
                         "phase": s.group(1) if s else None, "auditor": int(str(r["mas_audit_result"]) == "1")})
    votes = collections.defaultdict(list)
    for f in sorted(glob.glob(os.path.join(rel, "human_eval/results/audit_results/*.json"))):
        for k, v in json.load(open(f))["annotations"].items():
            votes[(v["caseId"], key_mas(v["mas"]), v["llm"], v["taxonomyKey"])].append(v["verdict"])
    n_amb = 0
    with open(out, "w") as fo:
        for x in inst:
            vs = votes.get((x["qid"], x["mas"], x["llm"], x["code"]), [])
            y = sum(v == "yes" for v in vs)
            x["votes"] = vs; x["human"] = int(y * 2 > len(vs)) if vs else None
            x["run_id"] = f"maa|{x['mas']}|{x['llm']}|{x['dataset']}|{x['qid']}"
            fo.write(json.dumps(x) + "\n")
    keys = collections.Counter((x["qid"], x["mas"], x["llm"], x["code"]) for x in inst)
    print("instances", len(inst), "with votes", sum(1 for x in inst if votes.get((x['qid'], x['mas'], x['llm'], x['code']))),
          "dup keys", sum(1 for v in keys.values() if v > 1))
if __name__ == "__main__": main(sys.argv[1], sys.argv[2])
