"""Label-validity filters for the old AEGIS-custom-dataset-8-13 records (round 26).

1. clinical_agent / clinical_agent5: if every applied injection used `direct_prepend`,
   the injection was semantically void (probability task_type silently fell back to mcq;
   medical-aegis rounds 6-7). Measured: ca 151/402, ca5 614/1052. -> exclude from
   attribution supervision / evaluation; usable as unlabeled natural failures.
2. clinical_agent5 only: Planner output is read by no later step (0/1052 by mid-body
   probes on clean inputs), so a Planner injection cannot propagate -> drop Planner
   from the faulty-agent set (265/1052 records). In 6-agent clinical_agent the Planner
   output IS read by the ClinicalAgent orchestrator (397/402), so keep it there.
"""
def is_void_injection(rec: dict, framework: str) -> bool:
    if framework not in ("clinical_agent", "clinical_agent5"):
        return False
    applied = [s for s in rec["injection_log"]["conversation_history"] if s.get("injection_applied")]
    return bool(applied) and all((s.get("injection_process") or {}).get("injection_method") != "llm_rewrite" for s in applied)

def effective_faulty_agents(rec: dict, framework: str) -> set:
    applied = [s for s in rec["injection_log"]["conversation_history"] if s.get("injection_applied")]
    names = {s.get("agent_name") for s in applied}
    if framework == "clinical_agent5":
        names.discard("Planner")
    return names
