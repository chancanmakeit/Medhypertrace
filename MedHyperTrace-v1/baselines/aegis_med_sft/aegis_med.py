"""
AEGIS-med-SFT common utilities — the in-domain (medical) counterpart to your
aegis_common.py, supporting BOTH output variants:

  variant="no_step"   target = {"faulty_agents":[{"agent_name","error_type"}]}
                       (faithful to AEGIS; scored by agent/error/pair F1)
  variant="with_step" target = {"faulty_agents":[{"agent_name","error_type","error_step"}]}
                       (adds "when"; scored by agent/error/pair F1 + step Top-1)

Design choices matching our earlier decisions:
  * INSTANCE granularity: replicated roles are disambiguated ("Expert 0/1/2") in BOTH
    the rendered conversation and the target, so the model can ground instance-level
    predictions. For non-replicated frameworks (dylan/llm_debate) instance == role.
  * error_step uses the same step number rendered in the log ([Step N]), so train/eval
    are self-consistent. Pairs with no resolvable injection step get error_step=null.
  * Agent/error/pair metrics reuse your compute_metrics verbatim (aegis_metrics.py).
    Step is scored separately (Top-1: predicted step for a matched pair == gt step).

Medical FM examples replace AEGIS's code-centric examples to help clinical grounding;
the 14 MAST codes themselves are unchanged.
"""
from __future__ import annotations

import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)


import json
import re
from typing import Optional

from common.data import Trajectory, FM_TYPES
from common.aegis_metrics import compute_metrics, _norm_agent

# ---- MAST menu with medical examples (codes identical to AEGIS) -----------------------
FM_MENU_MED = """### Task Execution Errors (FM-1.x):
- FM-1.1: Task specification deviation (e.g., asked to assess a CT, the agent analyzes the patient history instead).
- FM-1.2: Role specification deviation (e.g., a Radiologist agent starts prescribing medication, the Pharmacologist's role).
- FM-1.3: Add redundant steps (e.g., re-orders a lab test already reported earlier in the consult).
- FM-1.4: Remove/ignore conversation history (e.g., ignores an allergy stated earlier by another specialist).
- FM-1.5: Remove termination conditions (e.g., keeps requesting tests without ever converging on a diagnosis).

### Communication & Coordination Errors (FM-2.x):
- FM-2.1: Repeat handled tasks (e.g., re-derives a differential another agent already finalized).
- FM-2.2: Make request ambiguous (e.g., tells another agent to "check the imaging" without specifying modality or finding).
- FM-2.3: Deviate from main goal (e.g., discusses epidemiology while the case needs an urgent treatment decision).
- FM-2.4: Hide important information (e.g., notices a contraindication but does not surface it to the team).
- FM-2.5: Ignore other agents (e.g., disregards a pathologist's correction to the tumor grade).
- FM-2.6: Inconsistent reasoning (e.g., states the mass is benign in one turn and malignant later with no new evidence).

### Quality & Verification Errors (FM-3.x):
- FM-3.1: Premature termination (e.g., declares a final diagnosis before required labs return).
- FM-3.2: Remove verification steps (e.g., the aggregator adopts an answer without cross-checking specialists).
- FM-3.3: Incorrect verification (e.g., "confirms" a reading against the wrong image or criterion)."""

_OUT_NOSTEP = (
    '{{"faulty_agents": [{{"agent_name": "XXX", "error_type": "FM-X.X"}}]}}')
# with_step adds ONE trajectory-level field: the earliest step at which any error
# was introduced (Who&When "when"). This matches the HGNN / Who&When step definition
# so all methods share one step metric (earliest-error-step Top-1).
_OUT_WITHSTEP = (
    '{{"faulty_agents": [{{"agent_name": "XXX", "error_type": "FM-X.X"}}], '
    '"earliest_error_step": N}}')

_PROMPT = """## ROLE AND GOAL
You are a meticulous Medical Multi-Agent System (MAS) Quality Assurance analyst. Your sole purpose is to analyze clinical consultation logs among AI agents to identify and categorize agent errors using a strict set of definitions.

## ERROR DEFINITIONS
You MUST use the exact error codes below.
{fm_menu}

## ANALYSIS WORKFLOW
1. Internally analyze the conversation turn by turn, checking each agent's action against the definitions.
2. Compile all identified faults into the required JSON. If no errors, output an empty list.

## STRICT OUTPUT FORMAT
Your final response MUST BE A SINGLE, VALID JSON OBJECT and nothing else. No explanatory text, no markdown fences.
{step_clause}
**Correct Format:**
{out_format}

**Example for No Errors:**
{{"faulty_agents": []}}

## CONVERSATION TO ANALYZE:
\"\"\"
{conversation_text}
\"\"\"

## YOUR ANALYSIS (JSON ONLY):"""

_STEP_CLAUSE = ("You MUST also output \"earliest_error_step\": the single integer step "
                "number (as shown in [Step N]) at which the FIRST error in the whole "
                "conversation was introduced.\n")


# ---- instance-aware serialization ----------------------------------------------------
def _agent_surface(agent_name: str, role_index: int, agent_key: str) -> str:
    if agent_key == "instance":
        return f"{agent_name} {role_index}"
    return agent_name


def serialize_conversation(traj: Trajectory, agent_key: str = "instance") -> str:
    parts = [f"Task:\n{traj.query}\n", "Conversation Log:"]
    for s in traj.steps:
        if s.is_input:
            continue
        name = _agent_surface(s.agent_name, s.role_index, agent_key)
        parts.append(f"\n[Step {s.turn}] {name}:\n{s.content}")
    if traj.final_response:
        parts.append(f"\nFinal Output:\n{traj.final_response}")
    return "\n".join(parts)


def build_prompt(traj: Trajectory, variant: str = "no_step",
                 agent_key: str = "instance") -> str:
    return _PROMPT.format(
        fm_menu=FM_MENU_MED,
        step_clause=_STEP_CLAUSE if variant == "with_step" else "",
        out_format=_OUT_WITHSTEP if variant == "with_step" else _OUT_NOSTEP,
        conversation_text=serialize_conversation(traj, agent_key),
    )


def build_target_json(traj: Trajectory, variant: str = "no_step",
                      agent_key: str = "instance") -> str:
    pairs = []
    for (a, ri), fms in traj.labels.instance_fms.items():
        for fm in sorted(fms):
            pairs.append({"agent_name": _agent_surface(a, ri, agent_key),
                          "error_type": fm})
    obj = {"faulty_agents": pairs}
    if variant == "with_step":
        # single trajectory-level "when" = earliest injected step (same label the
        # HGNN / Who&When use). None only if no injected step exists (never happens
        # in this dataset, but handled defensively).
        obj["earliest_error_step"] = traj.labels.earliest_error_turn
    return json.dumps(obj, ensure_ascii=False)


# ---- parsing (both variants) ---------------------------------------------------------
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_OBJ_RE = re.compile(r"\{(?:[^{}]|\{[^{}]*\})*\"faulty_agent[s]?\"(?:[^{}]|\{[^{}]*\})*\}",
                      re.DOTALL)


def _try_json(s):
    try:
        return json.loads(s)
    except Exception:
        return None


def _relax(s):
    """Best-effort repair of near-JSON: strip trailing commas, convert single quotes."""
    s2 = re.sub(r",\s*([}\]])", r"\1", s)          # trailing commas
    o = _try_json(s2)
    if o is not None:
        return o
    s3 = s2.replace("'", '"')                        # single -> double quotes
    return _try_json(s3)


def parse_prediction(text: str):
    """Return (well_formed, pairs, earliest_step). pairs = [(agent,fm)...];
    earliest_step = int trajectory-level step (or None) for with_step outputs.

    Hardened: strips <think> reasoning, code fences, and leading prose; tolerates
    trailing commas / single quotes; accepts key variants (faulty_agent[s],
    agent/name, error_type/failure_mode/fm); grabs the JSON object even when wrapped
    in explanatory text. These recover format-drift failures that are NOT model
    capability failures — genuine garbage still fails."""
    if not isinstance(text, str):
        return False, [], None
    c = _THINK_RE.sub("", text).strip()            # drop <think>...</think>
    c = re.sub(r"^```(?:json)?", "", c).strip()
    c = re.sub(r"```$", "", c).strip()

    obj = _try_json(c) or _relax(c)
    if not isinstance(obj, dict):
        # find the JSON object embedded in prose (prefer one containing faulty_agents)
        cands = _OBJ_RE.findall(c) or _JSON_RE.findall(c)
        for frag in sorted(cands, key=len, reverse=True):
            obj = _try_json(frag) or _relax(frag)
            if isinstance(obj, dict):
                break

    if not isinstance(obj, dict):
        return False, [], None
    # key variants for the list. NOTE: an empty list [] is a VALID prediction ("no
    # responsible agent"), so we must check key PRESENCE, not truthiness — `[] or ...`
    # would wrongly fall through and misreport a valid empty prediction as a parse error.
    fa = None
    for k in ("faulty_agents", "faulty_agent", "agents", "predictions"):
        if k in obj:
            fa = obj[k]
            break
    if not isinstance(fa, list):
        return False, [], None
    pairs = []
    for it in fa:
        if not isinstance(it, dict):
            continue
        a = it.get("agent_name") or it.get("agent") or it.get("name") or it.get("role")
        e = (it.get("error_type") or it.get("failure_mode") or it.get("fm") or
             it.get("error") or it.get("fm_error_type"))
        if isinstance(a, str) and isinstance(e, str):
            pairs.append((a.strip(), e.strip().upper()))
    est = (obj.get("earliest_error_step") if obj.get("earliest_error_step") is not None
           else obj.get("earliest_step"))
    earliest_step = int(est) if isinstance(est, (int, float)) else None
    return True, pairs, earliest_step


# ---- step scoring (with_step): trajectory-level earliest-error-step Top-1 ------------
def step_top1(pred_step_list, gt_step_list):
    """Fraction of trajectories where the predicted earliest_error_step equals the GT
    earliest error step. Same metric/definition as HGNN & Who&When step Top-1, so all
    methods share one step column. gt_step comes from traj.labels.earliest_error_turn."""
    tot = correct = 0
    for pred, gt in zip(pred_step_list, gt_step_list):
        if gt is None:
            continue
        tot += 1
        if pred is not None and int(pred) == int(gt):
            correct += 1
    return (correct / tot if tot else 0.0), tot


# --- retained for reference: the old per-pair step scorer is intentionally removed ---
def _deprecated_pair_step_accuracy(pred_step_of_list, gt_step_map_list):  # noqa
    matched = correct = 0
    for pred_steps, gtm in zip(pred_step_of_list, gt_step_map_list):
        for key, gt_st in gtm.items():
            if key in pred_steps and pred_steps[key] == gt_st:
                correct += 1
    return correct / matched if matched else 0.0, matched
SYSTEM = "You are a helpful assistant for multi-agent failure attribution."
