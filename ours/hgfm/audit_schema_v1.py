"""Audit `mas-traj/1` exports from medical-aegis before they feed HGFM (round 26).

Checks, per record:
  1. step whitelist      no label-bearing field on any step
  2. injection leak      text added by prompt injection (injected vs clean input diff) and
                         the injected instruction never appear in any step / task / final text
  3. sources             every source id resolves to an earlier step / task / observation;
                         "unlisted": a mid-body probe of an earlier output appears in the input
                         but neither it nor any listed source contains that probe
                         (excludes transitive quotation, per medical-aegis round 7)
                         and the probe is not text from the task itself (agents quote the
                         question/options verbatim; 83 false positives on the pilot before this)
  4. token side-channel  for response_corruption steps, completion_tokens describe the clean
                         pre-corruption call; we report |output chars / completion_tokens| for
                         corrupted vs other steps (a detectable gap = a label leak)
Then builds the UTH and prints hypergraph statistics per framework.
Usage: python -m ours.hgfm.audit_schema_v1 <export.jsonl> [...]
"""
import json, sys, statistics as st
from collections import defaultdict
from ours.hgfm.uth import build_uth, STEP_FIELDS_ALLOWED

def norm(s): return " ".join(str(s).split())
def msgs_text(ms): return norm(" ".join(m["content"] if isinstance(m.get("content"), str) else json.dumps(m.get("content"), ensure_ascii=False) for m in ms or []))
def mid_probes(o, k=50, n=3):
    o = norm(o)
    if len(o) < 3 * k: return [o[len(o)//4: len(o)//4 + k]] if len(o) >= 2 * k else []
    a, b = len(o) // 5, len(o) - len(o) // 5 - k
    return [o[a + i * (b - a) // max(n - 1, 1): a + i * (b - a) // max(n - 1, 1) + k] for i in range(n)]

def audit(rec):
    issues = defaultdict(int)
    steps = rec["steps"]; ids = {s["step_id"]: i for i, s in enumerate(steps)}
    obs = {"task:obs:" + o.get("id", "").removeprefix("obs:") for o in rec["task"].get("observations") or []}
    for s in steps:
        bad = set(s) - STEP_FIELDS_ALLOWED
        if bad: issues["step_field_not_whitelisted:" + ",".join(sorted(bad))] += 1
    all_text = norm(json.dumps({"task": rec["task"], "steps": rec["steps"], "final": rec.get("final")}, ensure_ascii=False))
    for inj in (rec.get("labels") or {}).get("injection") or []:
        s = steps[ids[inj["step_id"]]] if inj.get("step_id") in ids else None
        if inj.get("injected_input_messages") and s is not None:
            clean, dirty = msgs_text(s.get("input_messages")), msgs_text(inj["injected_input_messages"])
            added = dirty.replace(clean, "") if clean in dirty else ""
            for p in mid_probes(added) or ([added[:60]] if len(added) > 20 else []):
                if p and p in all_text: issues["prompt_injection_text_in_steps"] += 1
            if "UPDATED INSTRUCTION" in all_text: issues["injection_marker_in_steps"] += 1
    outs = [norm(s.get("output") or "") for s in steps]
    task_txt = norm(json.dumps(rec["task"], ensure_ascii=False))   # agents quote the question verbatim
    for i, s in enumerate(steps):
        inp = msgs_text(s.get("input_messages"))
        listed = [x if isinstance(x, str) else x["step_id"] for x in s.get("sources") or []]
        for x in listed:
            if x.startswith("task"):
                if x.startswith("task:obs:") and x not in obs: issues["unknown_obs_source"] += 1
                continue
            if x not in ids or ids[x] >= i: issues["bad_source_ref"] += 1
        listed_txt = " ".join(outs[ids[x]] for x in listed if x in ids)
        for j in range(i):
            if steps[j]["step_id"] in listed: continue
            for p in mid_probes(outs[j]):
                if p in inp and p not in listed_txt and p not in task_txt:
                    issues["unlisted_read"] += 1; break
    return issues

def rc_token_gap(recs):
    """chars-per-completion-token for corrupted vs untouched LLM steps."""
    cor, oth = [], []
    for r in recs:
        rc = {x["step_id"] for x in r["labels"].get("injection") or [] if x.get("strategy") == "response_corruption" and x.get("applied")}
        for s in r["steps"]:
            ct = s.get("completion_tokens"); o = s.get("output") or ""
            if s.get("kind") == "tool" or not ct: continue
            (cor if s["step_id"] in rc else oth).append(len(o) / ct)
    return cor, oth

def main(paths):
    recs = [json.loads(l) for p in paths for l in open(p)]
    tot = defaultdict(int); per_fw = defaultdict(list)
    for r in recs:
        for k, v in audit(r).items(): tot[k] += v
        per_fw[r["framework"]].append(r)
    print(f"records={len(recs)}  audit issues: {dict(tot) or 'none'}")
    cor, oth = rc_token_gap(recs)
    if cor and oth:
        print(f"token side-channel: chars/completion_token  corrupted median={st.median(cor):.2f} (n={len(cor)})  other median={st.median(oth):.2f} (n={len(oth)})")
    print(f"{'framework':20s} {'fam':16s} runs  nodes  steps agents read|tail|mean/max  read_new mean  events  ev.size  structured")
    for fw, rs in sorted(per_fw.items()):
        g = [build_uth(r) for r in rs]
        ns = [sum(1 for n in x["nodes"].values() if n["type"] in ("step", "tool")) for x in g]
        ag = [sum(1 for n in x["nodes"].values() if n["type"] == "agent") for x in g]
        rd = [len(e["tail"]) for x in g for e in x["edges"] if e["type"] == "read"]
        rn = [len(e["tail"]) for x in g for e in x["edges"] if e["type"] == "read_new"]
        ev = [len(e["members"]) for x in g for e in x["edges"] if e["type"] == "event"]
        sc = sum(1 for x in g for n in x["nodes"].values() if n["type"] == "step" and n["structured"])
        stp = sum(1 for x in g for n in x["nodes"].values() if n["type"] == "step")
        print(f"{fw:20s} {rs[0]['framework_family']:16s} {len(rs):4d} {st.mean(len(x['nodes']) for x in g):6.1f} {st.mean(ns):6.1f} {st.mean(ag):5.1f}  {st.mean(rd):5.1f}/{max(rd):3d}       {st.mean(rn):5.1f}     {len(ev)/len(g):5.1f}  {st.mean(ev) if ev else 0:5.1f}   {sc}/{stp}")

if __name__ == "__main__":
    main(sys.argv[1:])
