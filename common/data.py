"""
MedHyperTrace — unified data layer for the AEGIS medical MAS error-trajectory dataset.

Handles all five frameworks (mdagents / dylan / llm_debate / clinical_agent / clinical_agent5) with a
single Trajectory schema, extracts the three-level ground truth, and builds the
heterogeneous hypergraph (step / agent / phase nodes; agg / ctx / role / phase edges).

Design decisions locked with the researcher:
  * agent-level unit  = INSTANCE (agent_name, role_index); a role-collapsed view is
                        also exposed for a secondary metric.
  * step-level label  = earliest injected step (Who&When "when"): min `step` among
                        steps with injection_applied=True. Masked only if no such step
                        exists (empirically never happens in this dataset).
  * agent/mode labels = taken from injection_log.multi_injection_info (authoritative),
                        NOT from the per-step injection_applied flags, because ~17% of
                        llm_debate trajectories have a planned faulty agent that was
                        never marked applied in conversation_history.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# --------------------------------------------------------------------------------------
# MAST failure-mode taxonomy (from AEGIS / MAST). Category = first digit.
#   FM-1.x  Specification & design issues
#   FM-2.x  Inter-agent misalignment
#   FM-3.x  Verification / termination issues
# --------------------------------------------------------------------------------------
FM_TYPES = [
    "FM-1.1", "FM-1.2", "FM-1.3", "FM-1.4", "FM-1.5",
    "FM-2.1", "FM-2.2", "FM-2.3", "FM-2.4", "FM-2.5", "FM-2.6",
    "FM-3.1", "FM-3.2", "FM-3.3",
]
FM_INDEX = {fm: i for i, fm in enumerate(FM_TYPES)}


def fm_category(fm: str) -> int:
    """1 / 2 / 3 for the three MAST super-categories (hierarchical consistency)."""
    return int(fm.split("-")[1].split(".")[0])


def coarse_phase(phase: str) -> str:
    """Collapse framework-specific phase strings to a canonical sub-task label so that
    same-subtask steps from multiple agents form a genuine n-ary phase hyperedge.
    e.g. 'expert_answer/Breast Radiologist' -> 'expert_answer'. The fine-grained
    specialty is kept separately on the Step (see Step.specialty) as a node feature."""
    if not phase:
        return "unknown"
    return phase.split("/", 1)[0].strip().lower()


def phase_specialty(phase: str) -> str:
    """The fine-grained part after '/', e.g. 'Breast Radiologist'. '' if none."""
    return phase.split("/", 1)[1].strip() if "/" in phase else ""


# --------------------------------------------------------------------------------------
# Format-robust accessors — the three files disagree on where things live.
# --------------------------------------------------------------------------------------
def get_final_response(rec: dict) -> str:
    """Final system answer. dylan/mdagents: injection_log.response or top-level response;
    llm_debate: injection_log.final_output.response."""
    il = rec.get("injection_log", {})
    fo = il.get("final_output")
    if isinstance(fo, dict) and fo.get("response"):
        return fo["response"]
    if il.get("response"):
        return il["response"]
    return rec.get("response", "")


def get_framework(rec: dict, override: Optional[str] = None) -> str:
    """Canonical framework name. If `override` is given (the FILES key for the source
    file), it is authoritative — this is how clinical_agent vs clinical_agent5 are told
    apart, since their records are schema-identical and share the 'clinical_agent'
    substring. Falls back to injection_log.framework, then to _source_file heuristics."""
    if override:
        return override
    il = rec.get("injection_log", {})
    fw = il.get("framework")
    if fw:
        return fw
    src = (rec.get("_source_file", "") + rec.get("_source_config_label", "")).lower()
    if "dylan" in src:
        return "dylan"
    if "debate" in src:
        return "llm_debate"
    if "mdagent" in src:
        return "mdagents"
    # clinical_agent5 must be checked before clinical_agent (substring containment)
    if "clinical_agent5" in src or "200-500" in src:
        return "clinical_agent5"
    if "clinical_agent" in src:
        return "clinical_agent"
    return "unknown"


# --------------------------------------------------------------------------------------
# Unified schema
# --------------------------------------------------------------------------------------
@dataclass
class Step:
    turn: int                      # 1-indexed, monotonic across all three formats
    agent_name: str
    role_index: int
    phase: str
    is_input: bool                 # llm_debate "User" turns are inputs, not agent actions
    content: str
    input_messages: list[dict] = field(default_factory=list)  # what this step consumed
    injection_applied: bool = False
    fm_error_type: Optional[str] = None
    injection_strategy: Optional[str] = None
    orig_agent_name: str = ""      # pre-refinement name (e.g. 'Expert' before -> specialist)

    @property
    def instance(self) -> tuple[str, int]:
        return (self.agent_name, self.role_index)

    @property
    def coarse(self) -> str:
        return coarse_phase(self.phase)

    @property
    def specialty(self) -> str:
        return phase_specialty(self.phase)


@dataclass
class Labels:
    faulty_instances: set[tuple[str, int]]      # agent-level (instance) GT
    faulty_roles: set[str]                       # agent-level (role-collapsed) GT
    instance_fms: dict[tuple[str, int], set[str]]  # (instance) -> {fm}, mode-level pairs
    fm_set: set[str]                             # trajectory-level set of fm types
    earliest_error_turn: Optional[int]           # step-level GT (Who&When "when")
    step_masked: bool                            # True if no injected step to supervise


@dataclass
class Trajectory:
    id: str
    framework: str
    query: str
    correct_answer: str
    final_response: str
    is_correct: bool
    steps: list[Step]
    labels: Labels
    images: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def instances(self) -> list[tuple[str, int]]:
        """Distinct agent instances that actually acted (exclude pure input/User turns)."""
        seen, out = set(), []
        for s in self.steps:
            if s.is_input:
                continue
            if s.instance not in seen:
                seen.add(s.instance)
                out.append(s.instance)
        return out


# --------------------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------------------
def _norm_input_messages(im: Any) -> list[dict]:
    if isinstance(im, list):
        return [m for m in im if isinstance(m, dict)]
    return []


# ======================================================================================
# Per-framework agent-identity refinement.
#
# Some frameworks give every instance of a role the SAME generic agent_name, while the
# real identity lives elsewhere in the record. There is NO reliable framework-agnostic
# way to detect this (where the identity hides is a per-framework data convention), so we
# keep an EXPLICIT registry: one refinement function per framework that needs it. A
# framework with no entry is left untouched (its agent_name is already the real identity).
#
# Currently only mdagents needs refinement. When a NEW framework needs it, add one entry
# below keyed by its framework name, returning the refined identity from whatever field
# that framework actually uses (do NOT assume it looks like mdagents). See the mdagents
# function for the expected signature: (raw_step_dict, base_name) -> refined_name.
# ======================================================================================

def _refine_mdagents(raw: dict, base_name: str) -> str:
    """mdagents: all 5 experts share agent_name='Expert'; the specialist identity is in
    phase as 'expert_answer/<Specialist>'. Promote the specialist to be the agent
    identity. Experts are recruited per-question (not fixed), so read it dynamically.
    Only the 'Expert' role is refined; Recruiter/Aggregator keep their names."""
    if base_name == "Expert":
        phase = raw.get("phase", "") or ""
        if phase.startswith("expert_answer/"):
            spec = phase.split("/", 1)[1].strip()
            if spec and not spec.isdigit():
                return spec
    return base_name


# framework name -> refiner(raw_step_dict, base_name) -> refined_name
# Add new frameworks here ONLY when you have actually inspected their data and know where
# the identity lives. Absent frameworks are intentionally left unrefined.
_AGENT_REFINERS = {
    "mdagents": _refine_mdagents,
}


def _refine_agent_name(raw: dict, framework: str, base_name: str) -> str:
    refiner = _AGENT_REFINERS.get(framework)
    return refiner(raw, base_name) if refiner else base_name


def parse_step(raw: dict, framework: str) -> Step:
    turn = raw.get("step")
    if turn is None:  # fall back to alternate ordering keys
        turn = raw.get("msg_index", raw.get("node_id", 0))
    base_name = raw.get("agent_name") or raw.get("role") or "unknown"
    agent_name = _refine_agent_name(raw, framework, base_name)
    return Step(
        turn=int(turn),
        agent_name=agent_name,
        role_index=int(raw.get("role_index", 0)),
        phase=raw.get("phase", ""),
        is_input=bool(raw.get("is_input", False)),
        content=str(raw.get("content", "") or ""),
        input_messages=_norm_input_messages(raw.get("input_messages")),
        injection_applied=bool(raw.get("injection_applied", False)),
        fm_error_type=raw.get("fm_error_type"),
        injection_strategy=raw.get("injection_strategy"),
        orig_agent_name=base_name,
    )


def extract_labels(rec: dict, steps: list[Step]) -> Labels:
    il = rec.get("injection_log", {})
    mi = il.get("multi_injection_info", []) or []

    faulty_instances: set[tuple[str, int]] = set()
    faulty_roles: set[str] = set()
    instance_fms: dict[tuple[str, int], set[str]] = {}
    fm_set: set[str] = set()

    # Map an injected (role, role_index) to the refined agent identity, when the parser
    # promoted a more specific name (e.g. mdagents 'Expert'+idx -> 'Breast Radiologist').
    # Exact match on (orig_agent_name, role_index) makes this deterministic.
    def refined_name(role, ridx):
        for s in steps:
            if s.is_input:
                continue
            if s.orig_agent_name == role and s.role_index == ridx:
                return s.agent_name
        return role

    # Authoritative agent/mode labels from multi_injection_info.
    for m in mi:
        role = m.get("injected_role")
        ridx = m.get("injected_role_index")
        fm = m.get("fm_error_type")
        if role is None or ridx is None:
            continue
        name = refined_name(role, int(ridx))
        inst = (name, int(ridx))
        faulty_instances.add(inst)
        faulty_roles.add(name)
        if fm:
            fm_set.add(fm)
            instance_fms.setdefault(inst, set()).add(fm)

    # Fallback / augmentation: any applied step also counts (covers rare mi omissions).
    applied = [s for s in steps if s.injection_applied]
    for s in applied:
        faulty_instances.add(s.instance)
        faulty_roles.add(s.agent_name)
        if s.fm_error_type:
            fm_set.add(s.fm_error_type)
            instance_fms.setdefault(s.instance, set()).add(s.fm_error_type)

    # Step-level: earliest injected step (Who&When "when").
    if applied:
        earliest = min(s.turn for s in applied)
        masked = False
    else:
        earliest = None
        masked = True

    return Labels(
        faulty_instances=faulty_instances,
        faulty_roles=faulty_roles,
        instance_fms=instance_fms,
        fm_set=fm_set,
        earliest_error_turn=earliest,
        step_masked=masked,
    )


def parse_record(rec: dict, framework_override: Optional[str] = None) -> Trajectory:
    framework = get_framework(rec, framework_override)
    il = rec.get("injection_log", {})
    ch = il.get("conversation_history", []) or []
    steps = [parse_step(s, framework) for s in ch]
    steps.sort(key=lambda s: s.turn)
    labels = extract_labels(rec, steps)
    gt = rec.get("ground_truth", {}) or {}
    return Trajectory(
        id=rec.get("id", ""),
        framework=framework,
        query=rec.get("query", ""),
        correct_answer=gt.get("correct_answer", rec.get("answer", "")),
        final_response=get_final_response(rec),
        is_correct=bool(rec.get("is_correct", False)),
        steps=steps,
        labels=labels,
        images=rec.get("images", []) or [],
        raw=rec,
    )


def load_jsonl(path: str | Path) -> list[Trajectory]:
    # Resolve the canonical framework name from the FILES mapping (authoritative), so
    # clinical_agent vs clinical_agent5 are labelled correctly regardless of record fields.
    fw_override = None
    try:
        from common.paths import FILES
        import os
        rp = os.path.realpath(str(path))
        for k, v in FILES.items():
            if os.path.realpath(str(v)) == rp:
                fw_override = k
                break
    except Exception:
        pass
    trajs = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            trajs.append(parse_record(json.loads(line), fw_override))
    return trajs


def load_all(data_dir: str | Path) -> list[Trajectory]:
    data_dir = Path(data_dir)
    out = []
    for p in sorted(data_dir.glob("*.jsonl")):
        out.extend(load_jsonl(p))
    return out


# --------------------------------------------------------------------------------------
# Heterogeneous hypergraph construction
# --------------------------------------------------------------------------------------
# Node id scheme: strings so the graph is inspectable/debuggable.
#   step nodes  : "s{turn}"
#   agent nodes : "a::{agent_name}#{role_index}"      (instance granularity)
#   phase nodes : "p::{phase}"
# Hyperedges are sets of node ids, typed by ("agg" | "ctx" | "role" | "phase").
@dataclass
class HyperGraph:
    step_nodes: list[str]
    agent_nodes: list[str]
    phase_nodes: list[str]
    hyperedges: list[dict]  # {type, nodes:set[str], meta:dict}

    @property
    def num_nodes(self) -> int:
        return len(self.step_nodes) + len(self.agent_nodes) + len(self.phase_nodes)


def _agent_id(inst: tuple[str, int]) -> str:
    return f"a::{inst[0]}#{inst[1]}"


def _step_id(turn: int) -> str:
    return f"s{turn}"


def _phase_id(phase: str) -> str:
    return f"p::{phase}"


def _content_ref_edges(steps: list[Step]) -> list[dict]:
    """E_ctx: for each step, connect it to prior steps whose content it consumed.
    We approximate 'consumed' by substring containment of a prior step's content
    (or a distinctive prefix) inside this step's input_messages. This is a cheap,
    reproducible heuristic; a learned/embedding version can replace it later.
    """
    edges = []
    # Precompute a distinctive signature per prior step (first 60 non-space chars).
    def sig(txt: str) -> str:
        return "".join(txt.split())[:60]

    prior_sigs = [(s.turn, sig(s.content)) for s in steps]
    for s in steps:
        joined_input = "".join(
            "".join(str(m.get("content", "")).split()) for m in s.input_messages
        )
        if not joined_input:
            continue
        referenced = {t for (t, g) in prior_sigs if t < s.turn and g and g in joined_input}
        if referenced:
            nodes = {_step_id(t) for t in referenced} | {_step_id(s.turn)}
            edges.append({"type": "ctx", "nodes": nodes,
                          "meta": {"consumer": s.turn, "sources": sorted(referenced)}})
    return edges


def build_hypergraph(traj: Trajectory) -> HyperGraph:
    acting = [s for s in traj.steps if not s.is_input]

    step_nodes = [_step_id(s.turn) for s in acting]
    instances = traj.instances
    agent_nodes = [_agent_id(i) for i in instances]
    phases = []
    for s in acting:
        pid = _phase_id(s.coarse)          # coarse-grained: multiple agents share a phase
        if pid not in phases:
            phases.append(pid)

    hyperedges: list[dict] = []

    # E_role: each agent instance + all of its step nodes.
    for inst in instances:
        member_steps = {_step_id(s.turn) for s in acting if s.instance == inst}
        hyperedges.append({
            "type": "role",
            "nodes": {_agent_id(inst)} | member_steps,
            "meta": {"instance": inst},
        })

    # E_phase: each phase node + all step nodes in that (coarse) phase.
    for pid in phases:
        member_steps = {_step_id(s.turn) for s in acting if _phase_id(s.coarse) == pid}
        hyperedges.append({
            "type": "phase",
            "nodes": {pid} | member_steps,
            "meta": {"phase": pid},
        })

    # E_agg: aggregation / final-consensus steps consume all upstream acting steps.
    # Detect aggregator turns by phase or agent name; connect them with all prior
    # acting steps as one n-ary consensus edge.
    agg_keywords = ("aggreg", "final", "consensus", "summar")
    for s in acting:
        is_agg = (
            any(k in s.phase.lower() for k in agg_keywords)
            or "aggregator" in s.agent_name.lower()
        )
        if is_agg:
            upstream = {_step_id(u.turn) for u in acting if u.turn < s.turn}
            if upstream:
                hyperedges.append({
                    "type": "agg",
                    "nodes": upstream | {_step_id(s.turn)},
                    "meta": {"aggregator_turn": s.turn},
                })

    # E_ctx: information-inheritance hyperedges.
    hyperedges.extend(_content_ref_edges(acting))

    return HyperGraph(
        step_nodes=step_nodes,
        agent_nodes=agent_nodes,
        phase_nodes=phases,
        hyperedges=hyperedges,
    )
