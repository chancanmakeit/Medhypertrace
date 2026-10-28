"""E3 (round 67): TraceElephant groupchat runs (mas-traj/1) -> Who&When-format JSON for the OAT pipeline.

  python te_to_ww.py <traceelephant.jsonl.gz> <out_dir>   -> <out_dir>/Algorithm-Generated/<i>.json + manifest.json

Only framework_family == "groupchat" (Magentic-One, CaptainAgent; 176 runs). The 44 swe_agent runs were in the TAPT / SAMT
corpora and are excluded (pre-registration E1-E3 v1). Each file has the Who&When keys OAT reads: history
[{name, role, content}], mistake_step (index into history), mistake_agent, question. llm steps -> role "assistant",
name = agent_role (or agent_id); tool / environment steps -> name "Computer_terminal" (OAT's Algorithm-Generated rule
treats exactly those as non-model steps), content = output, or the tool calls as JSON if the output is empty.
Runs whose labelled mistake_step_id is not among the steps are dropped and listed in the manifest.
"""
import gzip, json, os, sys


def main(src, out):
    d = os.path.join(out, "Algorithm-Generated"); os.makedirs(d, exist_ok=True)
    man = {"source": os.path.basename(src), "kept": [], "dropped_unmappable": []}
    i = 0
    for l in gzip.open(src, "rt", encoding="utf-8"):
        r = json.loads(l)
        if r["framework_family"] != "groupchat":
            continue
        ext = r["labels"]["external"]; m = ext.get("mistake_step_id")
        ids = [s["step_id"] for s in r["steps"]]
        if m not in ids:
            man["dropped_unmappable"].append(r["run_id"]); continue
        hist = []
        for s in r["steps"]:
            out_txt = s.get("output") or ""
            if s["kind"] == "llm":
                hist.append({"name": s.get("agent_role") or s["agent_id"], "role": "assistant", "content": out_txt})
            else:
                if not out_txt.strip() and s.get("tool_calls"):
                    out_txt = json.dumps([{"name": t.get("name"), "arguments": t.get("arguments")} for t in s["tool_calls"]], ensure_ascii=False)
                hist.append({"name": "Computer_terminal", "role": "user", "content": out_txt})
        rec = {"question": r["task"].get("query") or "", "history": hist, "mistake_step": ids.index(m),
               "mistake_agent": ext.get("mistake_agent", ""), "framework": r["framework"], "run_id": r["run_id"]}
        json.dump(rec, open(os.path.join(d, f"{i}.json"), "w"), ensure_ascii=False)
        man["kept"].append({"file": f"{i}.json", "run_id": r["run_id"], "framework": r["framework"]}); i += 1
    json.dump(man, open(os.path.join(out, "manifest.json"), "w"), indent=1)
    print(f"kept {len(man['kept'])}, dropped (mistake step not mappable) {len(man['dropped_unmappable'])} -> {d}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
