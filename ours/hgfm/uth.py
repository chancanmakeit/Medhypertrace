"""Unified Trajectory Hypergraph (UTH) builder for `mas-traj/1` records (round 26).

Input: one record of the medical-aegis schema v1 export (labels physically separated
from steps). Output: a framework-agnostic directed hypergraph. Only fields under
`task`, `steps`, `final` and `framework_description` are read; `labels`, `run_mode`,
`run_id` and `provenance` are never touched (they are label-bearing metadata).

Nodes (all text-attributed):
  task                      the question / query
  obs:<id>                  shared observations (sensor blocks, audio, images, demos)
  step:<sid>                one LLM call or tool call (text = output)
  agent:<agent_id>          one agent identity, stable across phases
  final                     the system's final answer
Hyperedges (directed: tail -> head):
  read      tail = sources of a step (+ task/obs), head = the step     [one per step]
  read_new  same, but only sources the agent had not seen before       [one per step, may be empty]
  event     all steps sharing an event_id (vote round, discussion turn) [undirected]
  agent     all steps by one agent_id                                  [undirected]
  final     tail = final.source_step_ids, head = final
Edge-level attributes keep `how` (verbatim / excerpt / structured_field) per member.
"""
from __future__ import annotations
from collections import defaultdict

STEP_FIELDS_ALLOWED = {
    "step_id", "order", "kind", "agent_id", "agent_role", "agent_label", "phase", "round",
    "event_ids", "input_messages", "sources", "output", "structured", "tool_calls",
    "finish_reason", "prompt_tokens", "completion_tokens", "reasoning_tokens", "reasoning",
    "tool_stub",
}
# NOTE: prompt/completion/reasoning token counts are NOT used as features: on
# response_corruption steps they describe the clean pre-corruption call (label leak).


def _src_id(x):
    return x if isinstance(x, str) else x.get("step_id")


def _src_how(x):
    return "verbatim" if isinstance(x, str) else (x.get("how") or "verbatim")


def _node_of(src: str) -> str:
    if src.startswith("task:obs:"):
        return "obs:" + src[len("task:obs:"):]
    if src.startswith("task"):
        return "task"
    return "step:" + src


def build_uth(rec: dict) -> dict:
    steps = rec["steps"]
    nodes = {"task": {"type": "task", "text": rec["task"].get("query", "")},
             "final": {"type": "final", "text": str((rec.get("final") or {}).get("answer"))}}
    for o in rec["task"].get("observations") or []:
        oid = o.get("id", "")
        nodes["obs:" + oid.removeprefix("obs:")] = {"type": "observation", "text": o.get("text") or o.get("content") or "",
                                                    "modality": o.get("modality")}
    edges = []
    seen = defaultdict(set)          # agent_id -> node ids already read or produced
    by_event, by_agent = defaultdict(list), defaultdict(list)
    for s in steps:
        sid = "step:" + s["step_id"]
        aid = s.get("agent_id") or f"anon:{s.get('agent_role')}"
        nodes[sid] = {"type": "tool" if s.get("kind") == "tool" else "step", "text": s.get("output") or "",
                      "agent": aid, "role": s.get("agent_role"), "phase": s.get("phase"), "round": s.get("round"),
                      "order": s.get("order"), "structured": s.get("structured") or {}}
        nodes.setdefault("agent:" + aid, {"type": "agent", "text": s.get("agent_role") or aid})
        tail = [(_node_of(_src_id(x)), _src_how(x)) for x in s.get("sources") or []]
        edges.append({"type": "read", "tail": tail, "head": sid})
        new = [(n, h) for n, h in tail if n not in seen[aid]]
        edges.append({"type": "read_new", "tail": new, "head": sid})
        seen[aid] |= {n for n, _ in tail} | {sid}
        for e in s.get("event_ids") or []:
            by_event[e].append(sid)
        by_agent[aid].append(sid)
    # Derived events where the framework records `round` but no event_ids
    # (dylan, llm_debate, triage_agent): one event per (phase, round).
    for s in steps:
        if not s.get("event_ids") and s.get("round") is not None and s.get("kind") != "tool":
            by_event[f"derived:{s.get('phase')}:r{s['round']}"].append("step:" + s["step_id"])
    # Derived parallel cohorts: >=2 steps with the same non-empty read set that do not
    # read each other (mdagents expert panel, ConSensus modality interpreters, lanes).
    cohorts = defaultdict(list)
    for s in steps:
        key = tuple(sorted(_src_id(x) for x in s.get("sources") or []))
        if key and s.get("kind") != "tool":
            cohorts[(s.get("round"), key)].append(s["step_id"])
    for (_, key), mem in cohorts.items():
        if len(mem) >= 2 and not (set(mem) & set(key)):
            by_event["derived:cohort:" + "+".join(mem)] = ["step:" + m for m in mem]
    for e, mem in by_event.items():
        if len(mem) >= 2:
            edges.append({"type": "event", "id": e, "members": mem})
    for a, mem in by_agent.items():
        edges.append({"type": "agent", "id": a, "members": ["agent:" + a] + mem})
    fin = [("step:" + x, "verbatim") for x in (rec.get("final") or {}).get("source_step_ids") or []]
    edges.append({"type": "final", "tail": fin, "head": "final"})
    return {"framework": rec.get("framework"), "family": rec.get("framework_family"),
            "description": rec.get("framework_description"), "nodes": nodes, "edges": edges}
