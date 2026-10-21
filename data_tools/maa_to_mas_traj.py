"""Convert MedAgentAudit (MAA) release logs to mas-traj/1 (round 33).

Source: GuihaiChen1998/nature-sub-record, MedAgentAudit-datasets_and_logs-9.2,
`github_release_files/audit_results/{mas}_{dataset}_{llm}.jsonl` (14,370 runs).
Taxonomy: MedAgentAudit (10 codes). Kept apart from MAST experiments (HANDOFF 0.33).

Per round, steps are emitted in the order plan, inquiry, opinions[], synthesis,
reviews[], decision; then `final_decision_log` (colacare / medagent).
agent_id follows the auditor's ids so audit items map onto steps:
  colacare  opinions/reviews doctor_i, synthesis/decision meta
  healthcareagent  plan planner, opinions PreliminaryAnalyzer, reviews Safety*Agent,
                   decision decision-maker
  mac       opinions doctor_i, decision supervisor
  mdagents  opinions expert_*, decision final_decision_maker
  medagent  opinions/reviews doctor_i, synthesis meta, decision decision
  reconcile opinions/reviews agent_i (no decision step; final = predicted_answer)
Read sets:
  logs with llm_input (colacare, healthcareagent, mdagents, medagent): a prior step is
    a source if >= 1 mid-body probe of its explanation appears in this step's input
    (question text excluded); provenance.sources = "matched". Steps logged without
    llm_input in these MAS (medagent reviews, healthcareagent inquiry) fall back to a
    same-round protocol rule (review <- synthesis, inquiry <- plan), how = "protocol".
  mac, reconcile (no llm_input): protocol inference, provenance.sources = "protocol":
    mac = group chat, every step reads all earlier steps;
    reconcile = round r reads all steps of round r-1 (round-1 reviews read round-1 opinions).
Labels (labels side only): gold, is_correct, audit.items[{round, agent_id, phase, code,
present}] from the LLM auditor (source "llm_auditor"), complexity_level (mdagents).
Usage: python data_tools/maa_to_mas_traj.py <release_dir> <out.jsonl>
"""
import glob, json, os, re, sys

FAMILY = {"mac": "groupchat", "mdagents": "mdagents", "reconcile": "debate",
          "colacare": "maa_colacare", "healthcareagent": "maa_healthcareagent", "medagent": "maa_medagent"}
DESC = {
    "colacare": "ColaCare: domain doctors give independent opinions, a meta agent synthesises a report, doctors review it (agree / disagree); repeated until consensus, then the meta agent decides.",
    "healthcareagent": "HealthcareAgent: a planner, an inquiry stage, a preliminary analyser, three safety reviewers (ethics, emergency, error), then a decision maker.",
    "mac": "MAC: several doctors discuss in a shared group chat under a supervisor who decides when consensus is reached and gives the answer.",
    "mdagents": "MDAgents: a complexity classifier routes the case; intermediate cases recruit a team of experts who answer, then a final decision maker aggregates.",
    "medagent": "MedAgent: domain doctors give opinions, a meta agent synthesises, doctors review the synthesis, a decision agent gives the answer.",
    "reconcile": "ReConcile: agents answer independently, then for further rounds each agent reads all agents' previous answers and revises (round-table discussion); final answer by vote.",
}
STATUS_CODE = {  # audit_result status field -> MedAgentAudit code
    "factual_hallucination_status": "1.1.1", "modality_neglect_status": "1.2.1",
    "role_task_alignment": "2.1.1", "knowledge_activation_status": "2.1.2",
    "interaction_redundancy": "2.2.1", "conflict_resolution_status": "2.2.2",
    "suppression_status": "3.1.1", "authority_bias_status": "3.1.2",
    "neglect_of_conflict_status": "3.1.3", "inter_round_consistency_status": "3.2.1",
}
STEP_PHASE = {"opinions": "analysis", "reviews": "review", "synthesis": "synthesis",
              "decision": "decision", "plan": "plan", "inquiry": "inquiry"}
SINGLE_AGENT = {("colacare", "synthesis"): "meta", ("colacare", "decision"): "meta",
                ("healthcareagent", "plan"): "planner", ("healthcareagent", "inquiry"): "inquirer",
                ("healthcareagent", "decision"): "decision-maker", ("mac", "decision"): "supervisor",
                ("mdagents", "decision"): "final_decision_maker", ("medagent", "synthesis"): "meta",
                ("medagent", "decision"): "decision", ("reconcile", "decision"): "decision"}


def norm(s): return " ".join(str(s).split())


def flat(x):
    if x is None: return ""
    if isinstance(x, str): return x
    if isinstance(x, dict): return "\n".join(f"{k}: {flat(v)}" for k, v in x.items())
    if isinstance(x, list): return "\n".join(flat(v) for v in x)
    return str(x)


def msg_text(m):
    c = (m or {}).get("content")
    if isinstance(c, list): return "\n".join(p.get("text", "") for p in c if isinstance(p, dict))
    return c or ""


def to_step(mas, phase_key, item, rnd, order):
    log = item.get("log", item) if isinstance(item, dict) else {}
    po = log.get("parsed_output") or {}
    agent = item.get("agent_id") if isinstance(item, dict) and item.get("agent_id") else SINGLE_AGENT.get((mas, phase_key), phase_key)
    li = log.get("llm_input") or {}
    msgs = [{"role": "system", "content": msg_text(li.get("system_message"))},
            {"role": "user", "content": msg_text(li.get("user_message"))}] if li else []
    body = flat(po.get("explanation")) or flat(po.get("reason")) or flat(po.get("questions")) or flat({k: v for k, v in po.items() if k not in ("answer", "agree")})
    out = ""
    if po.get("answer") is not None: out += f"Answer: {po.get('answer')}\n"
    if po.get("agree") is not None: out += f"Agree: {po.get('agree')}\n"
    out += body
    st = {k: po[k] for k in ("answer", "agree", "consensus_reached") if k in po}
    return {"step_id": f"s{order}", "order": order, "kind": "llm", "agent_id": agent,
            "agent_role": item.get("specialty") if isinstance(item, dict) and item.get("specialty") else agent,
            "phase": STEP_PHASE.get(phase_key, phase_key), "round": rnd, "event_ids": [f"round{rnd}_{STEP_PHASE.get(phase_key, phase_key)}"],
            "input_messages": msgs, "sources": [], "output": out.strip(), "structured": st,
            "_probe_src": norm(body)}


def probes(t, q, k=50):
    t = norm(t)
    if len(t) < 2 * k: return []
    cand = [t[len(t) // 5: len(t) // 5 + k], t[len(t) // 2: len(t) // 2 + k], t[-len(t) // 5 - k: -len(t) // 5]]
    return [p for p in cand if p not in q]


def convert(rec, mas, dataset, llm):
    ch = rec.get("case_history") or {}
    steps, order = [], 0
    for rd in ch.get("rounds") or []:
        r = rd.get("round")
        for key in ("plan", "inquiry", "opinions", "synthesis", "reviews", "decision"):
            v = rd.get(key)
            if not v: continue
            for it in (v if isinstance(v, list) else [v]):
                steps.append(to_step(mas, key, it, r, order)); order += 1
    if ch.get("final_decision_log"):
        last_r = steps[-1]["round"] if steps else 1
        steps.append(to_step(mas, "decision", ch["final_decision_log"], last_r, order)); order += 1
    q = norm(rec.get("question", "")) + " " + norm(json.dumps(rec.get("options", {}), ensure_ascii=False))
    has_inputs = any(s["input_messages"] for s in steps)
    for i, s in enumerate(steps):
        if has_inputs and not s["input_messages"]:
            # step logged without llm_input (medagent reviews, healthcareagent inquiry):
            # protocol fallback by phase within the same round
            r = s["round"]; same = [t for t in steps[:i] if t["round"] == r]
            want = {"review": ["synthesis"] if any(t["phase"] == "synthesis" for t in same) else ["analysis"],
                    "inquiry": ["plan"], "decision": ["review", "synthesis"], "analysis": []}.get(s["phase"], [])
            s["sources"] = [{"step_id": t["step_id"], "how": "protocol"} for t in same if t["phase"] in want]
        elif has_inputs:
            inp = norm(" ".join(m["content"] for m in s["input_messages"]))
            if not inp: continue
            s["sources"] = [{"step_id": steps[j]["step_id"], "how": "matched"} for j in range(i)
                            if any(p in inp for p in probes(steps[j]["_probe_src"], q))]
        elif mas == "mac":
            s["sources"] = [{"step_id": steps[j]["step_id"], "how": "protocol"} for j in range(i)]
        elif mas == "reconcile":
            r = s["round"]
            prev = [t for t in steps[:i] if t["round"] == r - 1] or ([t for t in steps[:i] if t["round"] == r and t["phase"] == "analysis"] if s["phase"] == "review" else [])
            s["sources"] = [{"step_id": t["step_id"], "how": "protocol"} for t in prev]
    for s in steps: s.pop("_probe_src")
    # audit items -> labels; map (round, agent_id, phase) to the LAST matching step
    items = []
    idx = {}
    for s in steps: idx[(s["round"], s["agent_id"], s["phase"])] = s["step_id"]
    for rd in (ch.get("audit") or {}).get("rounds") or []:
        r = rd.get("round")
        for code_key, lst in rd.items():
            if code_key == "round": continue
            for e in lst or []:
                ar = e.get("audit_result") or {}
                for fld, val in ar.items():
                    if fld in STATUS_CODE:
                        items.append({"round": r, "agent_id": e.get("agent_id"), "phase": e.get("step"),
                                      "step_id": idx.get((r, e.get("agent_id"), e.get("step"))),
                                      "code": STATUS_CODE[fld], "present": str(val) == "1"})
    gold, pred = rec.get("ground_truth"), rec.get("predicted_answer")
    final_src = [steps[-1]["step_id"]] if steps and steps[-1]["phase"] == "decision" else [s["step_id"] for s in steps if s["round"] == (steps[-1]["round"] if steps else 1)]
    opts = rec.get("options") or {}
    return {
        "schema_version": "mas-traj/1", "run_id": f"maa|{mas}|{llm}|{dataset}|{rec['qid']}",
        "question_id": f"{dataset}/{rec['qid']}", "run_mode": "natural", "run_index": 0, "seed": None,
        "framework": f"maa_{mas}", "framework_family": FAMILY[mas], "framework_description": DESC[mas],
        "model": {"name": llm, "temperature": None, "max_tokens": None},
        "task": {"dataset": dataset, "query": rec.get("question", "") + "\n\nOptions:\n" + "\n".join(f"{k}. {v}" for k, v in opts.items()),
                 "images": [rec["image_path"]] if rec.get("image_path") else [], "observations": []},
        "steps": steps, "final": {"answer": pred, "source_step_ids": final_src},
        "labels": {"gold": gold, "is_correct": (pred == gold), "audit": {"taxonomy": "MedAgentAudit", "source": "llm_auditor", "items": items},
                   "complexity_level": rec.get("complexity_level")},
        "provenance": {"source": "MedAgentAudit-datasets_and_logs-9.2", "sources": "matched" if has_inputs else "protocol",
                       "sources_recorded": False, "input_messages_clean": True, "unmapped_audit_items": sum(1 for x in items if x["step_id"] is None)},
    }


def main(release, out):
    n = 0
    with open(out, "w") as fo:
        for f in sorted(glob.glob(os.path.join(release, "audit_results", "*.jsonl"))):
            mas, rest = os.path.basename(f)[:-6].split("_", 1)
            dataset, llm = rest.rsplit("_", 1)
            for l in open(f):
                fo.write(json.dumps(convert(json.loads(l), mas, dataset, llm), ensure_ascii=False) + "\n"); n += 1
    print("converted", n)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
