"""Line 3 gate (OutcomeCPT pre-registration §1): medical-aegis corpus runs (mas-traj/1, with labels.is_correct) ->
Who&When-format JSON for the OAT serialisation, same rendering as hgfm.icpt.med_to_ww.

  python -m hgfm.outcome.corpus_to_ww <out_dir> <corpus_*.mastraj.jsonl.gz ...>

Output: <out>/Algorithm-Generated/<i>.json; <out>/manifest.json [{file, id, run_id, framework, question_id, step_ids,
is_llm, is_correct}]. Runs with is_correct None (invalid / failed execution) are skipped.
"""
import gzip, json, os, sys


def render(r):
    hist = []
    for s in r["steps"]:
        t = s.get("output") or ""
        if s["kind"] == "llm":
            hist.append({"name": s.get("agent_role") or s["agent_id"], "role": "assistant", "content": t})
        else:
            if not t.strip() and s.get("tool_calls"):
                t = json.dumps([{"name": x.get("name"), "arguments": x.get("arguments")} for x in s["tool_calls"]], ensure_ascii=False)
            hist.append({"name": "Computer_terminal", "role": "user", "content": t})
    return hist


def main(out, *paths):
    d = os.path.join(out, "Algorithm-Generated"); os.makedirs(d, exist_ok=True); man = []; seen = set(); skip = 0
    for p in paths:
        for l in gzip.open(p, "rt", encoding="utf-8"):
            r = json.loads(l)
            if r["run_id"] in seen: continue
            seen.add(r["run_id"]); c = (r.get("labels") or {}).get("is_correct")
            if c is None: skip += 1; continue
            i = len(man)
            json.dump({"question": r["task"].get("query") or "", "history": render(r), "mistake_step": 0, "mistake_agent": "",
                       "framework": r["framework"], "run_id": r["run_id"]}, open(os.path.join(d, f"{i}.json"), "w"), ensure_ascii=False)
            man.append({"file": f"{i}.json", "id": f"Algorithm-Generated/{i}.json", "run_id": r["run_id"], "framework": r["framework"],
                        "question_id": r["question_id"], "step_ids": [s["step_id"] for s in r["steps"]],
                        "is_llm": [s["kind"] == "llm" for s in r["steps"]], "is_correct": bool(c)})
    json.dump(man, open(os.path.join(out, "manifest.json"), "w"))
    print(f"{len(man)} runs ({sum(m['is_correct'] for m in man)} correct), {skip} skipped (is_correct None) -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])
