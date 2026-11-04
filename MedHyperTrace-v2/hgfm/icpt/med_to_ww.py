"""Interaction-CPT pre-registration §4.1: medical-aegis protocol-v3 eval parents -> Who&When-format JSON for the OAT
serialisation (both read-out interfaces), plus the label table.

  python -m hgfm.icpt.med_to_ww <eval_v3 dir> <out_dir>

Input: <eval_v3 dir>/parents_mastraj/*.mastraj.jsonl.gz (mas-traj/1 normal runs; duplicates across *_x files dropped
by run_id) and <eval_v3 dir>/<job>/labels_v3.jsonl.gz.
Output:
  <out>/Algorithm-Generated/<i>.json  {question, history [{name, role, content}], mistake_step 0 (unused), run_id, ...}
     history = every step in order (te_to_ww rule: llm -> role assistant, name = agent_role or agent_id; tool /
     environment -> name "Computer_terminal", which OAT treats as a non-model step). Images / audio are not rendered.
  <out>/manifest.json  [{file, run_id, framework, question_id, step_ids}]   (history index i <-> step_ids[i])
  <out>/labels.jsonl   one row per labelled point: {job, run_id, question_id, step_id, judgment, positive, last_call_only}
     positive (pre-registration amendment A1) = stage 2 and statistics.p_value_pooled < 0.05, i.e. the arm-symmetric
     pooled-reference rule for every batch; `judgment` (control reference in the first batch) is kept for sensitivity.
     last_call_only = context.dt_empty and not context.downstream_regenerated (medical-aegis round 56).
Only parents that carry at least one label are written. DyLAN has no stage-2 labels (all undetermined) and is kept.
"""
import glob, gzip, json, os, sys


def main(src, out):
    d = os.path.join(out, "Algorithm-Generated"); os.makedirs(d, exist_ok=True)
    labels = []
    for p in sorted(glob.glob(os.path.join(src, "*", "labels_v3.jsonl.gz"))):
        job = os.path.basename(os.path.dirname(p))
        for l in gzip.open(p, "rt", encoding="utf-8"):
            L = json.loads(l); c = L.get("context") or {}; s = L.get("statistics") or {}
            pv = s.get("p_value_pooled") if s.get("stage") == 2 else None
            if s.get("stage") == 2 and pv is None: raise SystemExit(f"stage-2 point without p_value_pooled in {job}")
            labels.append({"job": job, "run_id": L["target"]["run_id"], "step_id": L["target"]["step_ids"][0],
                           "judgment": L["judgment"], "positive": pv is not None and pv < 0.05,
                           "last_call_only": bool(c.get("dt_empty")) and not bool(c.get("downstream_regenerated"))})
    need = {x["run_id"] for x in labels}
    runs = {}
    for p in sorted(glob.glob(os.path.join(src, "parents_mastraj", "*.mastraj.jsonl.gz"))):
        for l in gzip.open(p, "rt", encoding="utf-8"):
            r = json.loads(l)
            if r["run_id"] in need and r["run_id"] not in runs: runs[r["run_id"]] = r
    missing = need - set(runs)
    if missing: raise SystemExit(f"{len(missing)} labelled run_ids have no parent, e.g. {sorted(missing)[:3]}")
    man = []
    for i, rid in enumerate(sorted(runs)):
        r = runs[rid]; hist = []
        for s in r["steps"]:
            t = s.get("output") or ""
            if s["kind"] == "llm":
                hist.append({"name": s.get("agent_role") or s["agent_id"], "role": "assistant", "content": t})
            else:
                if not t.strip() and s.get("tool_calls"):
                    t = json.dumps([{"name": x.get("name"), "arguments": x.get("arguments")} for x in s["tool_calls"]], ensure_ascii=False)
                hist.append({"name": "Computer_terminal", "role": "user", "content": t})
        json.dump({"question": r["task"].get("query") or "", "history": hist, "mistake_step": 0, "mistake_agent": "",
                   "framework": r["framework"], "run_id": rid}, open(os.path.join(d, f"{i}.json"), "w"), ensure_ascii=False)
        man.append({"file": f"{i}.json", "id": f"Algorithm-Generated/{i}.json", "run_id": rid, "framework": r["framework"],
                    "question_id": r["question_id"], "step_ids": [s["step_id"] for s in r["steps"]],
                    "is_llm": [s["kind"] == "llm" for s in r["steps"]]})
    qid = {m["run_id"]: m["question_id"] for m in man}
    with open(os.path.join(out, "labels.jsonl"), "w") as f:
        for x in labels: f.write(json.dumps({**x, "question_id": qid[x["run_id"]]}) + "\n")
    json.dump(man, open(os.path.join(out, "manifest.json"), "w"))
    print(f"{len(man)} parents, {len(labels)} labelled points, {sum(x['positive'] for x in labels)} positives (pooled rule; {sum(x['judgment'] == 'positive' for x in labels)} by judgment) -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
