"""Stage 2 of the LLM layer (C6/C7): build graph-token instruction data (round 38).

Task "defect" (MedAgentAudit defect layer, binary per (target step, code)):
  prompt = question + options + system final answer [+ ground truth in --gold mode]
         + up to K candidate steps, each "[sid] agent | phase | round r <graph>" + excerpt
           (target step, its read sources, then the encoder's highest-scoring steps)
         + up to M interaction hyperedges incident to the target, each "<graph> instruction"
         + the code's official name / definition / guideline (from the human-eval sheets)
         + "Target: step [sid] ... Is this failure mode present? Answer yes or no."
  answer = "yes" / "no".  2.1.1 (role assignment) is asked at run level.
Training pairs: LLM-auditor labels of the fold's TRAIN runs (all positives, negatives
subsampled to --neg_ratio x positives per code, capped by --max_train).
Eval pairs: the 400 human instances whose run is in the fold's TEST split (label = human
majority; the auditor label is kept for reference only).
Each <graph> placeholder is matched, in order, by an entry of "graph_refs":
  ["node", step_index] or ["edge", edge_index] into graph_tokens.pt[run_id].
--no_graph writes the same prompts without placeholders (text-only baseline);
--no_excerpt drops the excerpts (graph-only).
Usage: python -m hgfm.llm.build_sft <mas_traj.jsonl> <graph_tokens.pt> <human400.jsonl> <code_defs.json> <out_dir>
          [--gold] [--no_graph] [--no_excerpt] [--K 10] [--M 4] [--max_train 20000] [--neg_ratio 1.0]
"""
import argparse, json, os, random, collections
import torch
from hgfm.data_v02 import edges_of
from hgfm.data_maa import CODES

SYSTEM = ("You audit the execution trace of a medical multi-agent system for one specific failure mode. "
          "Each listed step carries a graph token that summarises its position in the interaction hypergraph.")


def step_line(s, i, use_graph, use_excerpt, n_chars=400):
    line = f"[{s['step_id']}] {s['agent_id']} | {s['phase']} | round {s['round']}" + (" <graph>" if use_graph else "")
    if use_excerpt:
        line += "\n    excerpt: " + " ".join((s["output"] or "").split())[:n_chars]
    return line


def build_prompt(r, tok, target_i, code, defs, args):
    st = r["steps"]; sid = {s["step_id"]: i for i, s in enumerate(st)}
    edges = edges_of(r)
    assert tok is None or len(edges) == tok["m"].shape[0], (r["run_id"], len(edges), tok["m"].shape)
    cand = []
    if target_i is not None:
        cand.append(target_i)
        cand += [sid[x["step_id"]] for x in st[target_i]["sources"] if x["step_id"] in sid]
    if tok is not None:
        j = CODES.index(code) if code in CODES else 0
        order = sorted(range(len(st)), key=lambda i: -float(tok["step_prob"][i, j]))
    else:
        order = list(range(len(st)))
    for i in order:
        if len(dict.fromkeys(cand)) >= args.K: break
        cand.append(i)
    cand = sorted(dict.fromkeys(cand))[: args.K]
    refs, lines = [], []
    for i in cand:
        lines.append(step_line(st[i], i, not args.no_graph, not args.no_excerpt))
        if not args.no_graph: refs.append(["node", i])
    ev = [k for k, e in enumerate(edges) if target_i is not None and any(v == target_i for v, _ in e["members"])][: args.M]
    if target_i is None: ev = list(range(len(edges)))[: args.M]
    elines = []
    for k in ev:
        elines.append(("<graph> " if not args.no_graph else "") + edges[k]["instr"])
        if not args.no_graph: refs.append(["edge", k])
    q = r["task"]["query"][:2500]
    head = f"Question:\n{q}\n\nSystem's final answer: {r['final']['answer']}"
    if args.gold: head += f"\nGround-truth answer: {r['labels']['gold']}"
    d = defs[code]
    tgt = (f"Target: step [{st[target_i]['step_id']}] by {st[target_i]['agent_id']} ({st[target_i]['phase']})."
           if target_i is not None else "Target: the role assignment of this run (which specialists were recruited for this case).")
    user = (f"{head}\n\nTrajectory (most relevant steps):\n" + "\n".join(lines) +
            ("\n\nInteraction events around the target:\n" + "\n".join(elines) if elines else "") +
            f"\n\nFailure mode {code}: {d['name']}\nDefinition: {d['definition']}\nGuideline: {d['guideline']}\n\n{tgt} "
            "Is this failure mode present? Answer yes or no.")
    return user, refs


def main():
    ap = argparse.ArgumentParser()
    for a in ("src", "tokens", "human", "defs", "out"): ap.add_argument(a)
    ap.add_argument("--gold", action="store_true"); ap.add_argument("--no_graph", action="store_true"); ap.add_argument("--no_excerpt", action="store_true")
    ap.add_argument("--K", type=int, default=10); ap.add_argument("--M", type=int, default=4)
    ap.add_argument("--max_train", type=int, default=20000); ap.add_argument("--neg_ratio", type=float, default=1.0); ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(); random.seed(args.seed); os.makedirs(args.out, exist_ok=True)
    T = torch.load(args.tokens)   # also needed with --no_graph: split + candidate ranking (same candidates for a fair text-only baseline)
    defs = json.load(open(args.defs)); H = [json.loads(l) for l in open(args.human)]
    hum_by_run = collections.defaultdict(list)
    for h in H: hum_by_run[h["run_id"]].append(h)
    pos, neg, ev = collections.defaultdict(list), collections.defaultdict(list), []
    for l in open(args.src):
        r = json.loads(l); tok = T.get(r["run_id"])
        if tok is None: continue
        sid = {s["step_id"]: i for i, s in enumerate(r["steps"])}
        if tok["split"] == "train":
            seen = set()
            for it in r["labels"]["audit"]["items"]:
                i = sid.get(it["step_id"]) if it["code"] != "2.1.1" else None
                key = (i, it["code"])
                if key in seen or (it["code"] != "2.1.1" and i is None): continue
                seen.add(key); (pos if it["present"] else neg)[it["code"]].append((r["run_id"], i, it["code"]))
        else:
            for h in hum_by_run.get(r["run_id"], []):
                rows = [i for i, s in enumerate(r["steps"]) if s["agent_id"] == h["agent_id"] and s["phase"] == h["phase"]]
                targets = [None] if h["code"] == "2.1.1" else rows
                for i in targets:   # instance score = max over matching steps (as in train_maa)
                    ev.append({"run_id": r["run_id"], "i": i, "code": h["code"], "label": h["human"], "auditor": h["auditor"], "inst": f"{h['run_id']}|{h['code']}"})
    pairs = []
    per_code = args.max_train // max(len(pos), 1)
    for c in pos:
        p = random.sample(pos[c], min(len(pos[c]), per_code // 2 + 1))
        n = random.sample(neg[c], min(len(neg[c]), int(len(p) * args.neg_ratio)))
        pairs += [(x, "yes") for x in p] + [(x, "no") for x in n]
    random.shuffle(pairs)
    need = {x[0][0] for x in pairs} | {e["run_id"] for e in ev}
    recs = {}
    for l in open(args.src):
        r = json.loads(l)
        if r["run_id"] in need: recs[r["run_id"]] = r
    with open(os.path.join(args.out, "train.jsonl"), "w") as f:
        for (run_id, i, code), ans in pairs:
            user, refs = build_prompt(recs[run_id], T[run_id], i, code, defs, args)
            f.write(json.dumps({"run_id": run_id, "system": SYSTEM, "user": user, "graph_refs": refs, "answer": ans, "code": code}) + "\n")
    with open(os.path.join(args.out, "eval_human.jsonl"), "w") as f:
        for e in ev:
            user, refs = build_prompt(recs[e["run_id"]], T[e["run_id"]], e["i"], e["code"], defs, args)
            f.write(json.dumps({**e, "system": SYSTEM, "user": user, "graph_refs": refs}) + "\n")
    print(f"train pairs {len(pairs)} (codes {len(pos)}), eval prompts {len(ev)} -> {args.out}")


if __name__ == "__main__":
    main()
