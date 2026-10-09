"""
ECHO baseline (Banerjee, Nair, Borogovac; arXiv:2510.04886v2, "Where Did It All Go
Wrong? A Hierarchical Look into Multi-Agent Error Attribution").

Faithful reproduction of the FINAL implementation (I4, "Decoupled Attribution"):

  1. HIERARCHICAL CONTEXT (paper §3.1 + Appendix A.3): each step is rendered at a
     detail level determined by its positional distance from an anchor:
       distance 1     -> full content            (L1, ExtractFullContext)
       distance 2-3   -> key decisions           (L2, extract_key_decision)
       distance 4-6   -> brief summaries         (L3, summarize_agent)
       distance > 6   -> milestones              (L4, obtain_milestones)
     The extraction functions below are PORTED VERBATIM from Appendix A.3 (regex
     patterns unchanged). The paper defines C per target agent; for the panel
     analysts that read the whole trace we anchor the hierarchy at the FINAL step
     (where the failure manifests) — this interpretation is documented because the
     paper does not pin down the unified rendering (§3.2 "conversation summaries").
  2. OBJECTIVE ANALYSIS (paper §3.2 + A.5): a panel of k=3 analysts sampled from a
     pool of 6 roles (Conservative / Liberal / Detail-Focused / Pattern-Focused /
     Skeptical / General), temperatures varied in [0.3, 0.9]. Role prompts are
     reconstructed from the paper's verbatim role specifications (A.5's exact prompt
     text is not fully included in the arXiv HTML). Each analyst outputs JSON:
     investigation summary, per-step error likelihoods with evidence, a primary
     conclusion (attribution type, responsible agent(s), mistake step, confidence),
     and alternative hypotheses.
  3. DECOUPLED ATTRIBUTION (I4, Algorithm 1): the panel runs twice — an agent-level
     phase and a step-level phase (t in {agent, step}).
  4. CONSENSUS VOTING (paper §3.3 + A.7): filter analyses with confidence < delta
     (paper: delta = 0.3), aggregate agent votes and step votes weighted by
     confidence, plus disagreement analysis (conclusion diversity, confidence
     spread; review flag when spread > 0.5).

Scoring follows our unified protocol: agent-acc (predicted agent in the faulty role
set) and step Top-1 (== earliest injected step). Ground truth (correct answer) is
included by default like our other LLM baselines; pass --no_gt for the without-GT
condition from the paper.

Backend is pluggable (OpenAI-compatible / mock). Like Who&When, the real run needs
an LLM endpoint on your GPU/API box; the mock verifies plumbing end-to-end here.
"""
import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)

import argparse
import json
import random
import re
from collections import defaultdict

from common.data import load_jsonl
from common.paths import FILES
from common.splits import load_split

DELTA = 0.3          # min confidence threshold (paper §4.1)
K_ANALYSTS = 3       # panel size sampled per scenario (paper §4.1)
TEMPS = [0.3, 0.6, 0.9]

# --------------------------------------------------------------------------------------
# Appendix A.3 — hierarchical context extraction (ported verbatim; regexes unchanged)
# --------------------------------------------------------------------------------------
def extract_key_decision(agent_content, max_words=50, context_type="decision_quality"):
    if not agent_content.strip():
        return "No content available"
    if context_type == "handoff":
        patterns = [
            r"(?:received|got|obtained|from)\s+([^.!?]*[.!?])",
            r"(?:passing|providing|sending|to)\s+([^.!?]*[.!?])",
            r"(?:based on|using)\s+([^.!?]*[.!?])",
            r"(?:will|need to|should)\s+([^.!?]*(?:next|continue)[^.!?]*[.!?])",
        ]
    elif context_type == "decision_quality":
        patterns = [
            r"(?:I (?:conclude|determine|decide|believe|think))\s+([^.!?]*[.!?])",
            r"(?:Therefore|Thus|So|Hence),?\s+([^.!?]*[.!?])",
            r"(?:The (?:answer|solution|result))\s+(?:is|appears)\s+([^.!?]*[.!?])",
            r"(?:Based on|Given)\s+([^.!?]*[.!?])",
        ]
    elif context_type == "error_propagation":
        patterns = [
            r"(?:error|mistake|wrong|incorrect|failed)\s+([^.!?]*[.!?])",
            r"(?:cannot|unable|couldn't|can't)\s+([^.!?]*[.!?])",
            r"(?:However|But|Unfortunately)\s+([^.!?]*[.!?])",
        ]
    else:
        patterns = [
            r"(?:I (?:will|should|need to|decided to|conclude that|believe|think|determine)) ([^.!?]*[.!?])",
            r"(?:Therefore|Thus|So|Hence),? ([^.!?]*[.!?])",
            r"(?:The answer|The result|The solution) (?:is|appears to be|seems to be) ([^.!?]*[.!?])",
            r"Let me ([^.!?]*[.!?])",
            r"(?:My approach|My strategy|My plan) (?:is|will be) ([^.!?]*[.!?])",
        ]
    for pattern in patterns:
        matches = re.findall(pattern, agent_content, re.IGNORECASE)
        if matches:
            decision = matches[0].strip()
            words = decision.split()[:max_words]
            return " ".join(words) + ("..." if len(decision.split()) > max_words else "")
    sentences = agent_content.split(". ")
    if sentences:
        first = sentences[0].strip()
        if not first.endswith("."):
            first += "."
        words = first.split()[:max_words]
        return " ".join(words) + ("..." if len(first.split()) > max_words else "")
    words = agent_content.split()[:max_words]
    return " ".join(words) + ("..." if len(agent_content.split()) > max_words else "")


def summarize_agent(agent_content, max_words=20, context_type="general"):
    if not agent_content.strip():
        return "No content available"
    cleaned = " ".join(agent_content.split())
    if context_type == "handoff":
        patterns = [r"(?:received|got|obtained)\s+([^.!?]*[.!?])",
                    r"(?:providing|sending)\s+([^.!?]*[.!?])"]
    elif context_type == "decision_quality":
        patterns = [r"(?:conclude|determine|decide)\s+([^.!?]*[.!?])",
                    r"(?:Therefore|Thus|So),?\s+([^.!?]*[.!?])"]
    elif context_type == "error_propagation":
        patterns = [r"(?:error|mistake|failed)\s+([^.!?]*[.!?])",
                    r"(?:cannot|unable)\s+([^.!?]*[.!?])"]
    else:
        patterns = [
            r"(?:In conclusion|To conclude|Therefore|Thus|So|Hence),? ([^.!?]*[.!?])",
            r"(?:The (?:answer|result|solution|output)) (?:is|appears to be|seems to be) ([^.!?]*[.!?])",
            r"(?:I (?:found|determined|concluded|calculated)) ([^.!?]*[.!?])",
        ]
    for pattern in patterns:
        matches = re.findall(pattern, cleaned, re.IGNORECASE)
        if matches:
            s = matches[0].strip()
            words = s.split()[:max_words]
            return " ".join(words) + ("..." if len(s.split()) > max_words else "")
    sentences = cleaned.split(". ")
    if sentences:
        first = sentences[0].strip()
        words = first.split()[:max_words]
        return " ".join(words) + ("..." if len(first.split()) > max_words else "")
    words = cleaned.split()[:max_words]
    return " ".join(words) + ("..." if len(cleaned.split()) > max_words else "")


def obtain_milestones(agent_content, max_words=15, context_type="general"):
    if not agent_content.strip():
        return "No milestones available"
    cleaned = " ".join(agent_content.split())
    if context_type == "handoff":
        patterns = [
            r"(?:received|obtained|got)\s+([^.!?]*(?:from|data|information)[^.!?]*[.!?])",
            r"(?:provided|sent|passed)\s+([^.!?]*(?:to|data|information)[^.!?]*[.!?])",
            r"(?:completed|finished)\s+([^.!?]*(?:handoff|transfer)[^.!?]*[.!?])",
        ]
    elif context_type == "decision_quality":
        patterns = [
            r"(?:decided|determined|concluded)\s+([^.!?]*[.!?])",
            r"(?:evaluated|assessed|analyzed)\s+([^.!?]*[.!?])",
            r"(?:final decision|ultimate choice)\s*[:-]?\s*([^.!?]*[.!?])",
        ]
    elif context_type == "error_propagation":
        patterns = [
            r"(?:error|mistake|failure)\s+(?:occurred|detected)\s+([^.!?]*[.!?])",
            r"(?:identified|found)\s+(?:error|issue|problem)\s+([^.!?]*[.!?])",
            r"(?:corrected|fixed|resolved)\s+([^.!?]*[.!?])",
        ]
    else:
        patterns = [
            r"(?:completed|finished|achieved|accomplished)\s+([^.!?]*[.!?])",
            r"(?:created|generated|produced|built)\s+([^.!?]*[.!?])",
            r"(?:step\s+\d+|phase\s+\d+|stage\s+\d+)\s*[:-]?\s*([^.!?]*[.!?])",
            r"(?:successfully|finally)\s+([^.!?]*[.!?])",
        ]
    for pattern in patterns:
        matches = re.findall(pattern, cleaned, re.IGNORECASE)
        if matches:
            m = matches[0].strip()
            words = m.split()[:max_words]
            return " ".join(words) + ("..." if len(m.split()) > max_words else "")
    sentences = cleaned.split(". ")
    if sentences:
        first = sentences[0].strip()
        words = first.split()[:max_words]
        return " ".join(words) + ("..." if len(first.split()) > max_words else "")
    words = cleaned.split()[:max_words]
    return " ".join(words) + ("..." if len(cleaned.split()) > max_words else "")


def hierarchical_render(steps, anchor_idx):
    """Render the whole trace with detail graded by distance from anchor_idx
    (distance bands per Appendix A.3: 1 full / 2-3 key / 4-6 summary / >6 milestone)."""
    lines = []
    for i, s in enumerate(steps):
        d = abs(i - anchor_idx)
        if d <= 1:
            body, lvl = s.content, "FULL"
        elif d <= 3:
            body, lvl = extract_key_decision(s.content), "KEY"
        elif d <= 6:
            body, lvl = summarize_agent(s.content), "SUMMARY"
        else:
            body, lvl = obtain_milestones(s.content), "MILESTONE"
        lines.append(f"[Step {i} | {s.agent_name} | {lvl}] {body}")
    return "\n".join(lines)


# --------------------------------------------------------------------------------------
# §3.2 — analyst roles (specs verbatim from the paper; prompt text reconstructed)
# --------------------------------------------------------------------------------------
ROLES = {
    "conservative": "You are a Conservative Analyst: require strong, clear evidence "
        "for attribution, prefer single-agent attributions, maintain high confidence "
        "thresholds, and only attribute with definitive proof.",
    "liberal": "You are a Liberal Analyst: consider multi-agent error scenarios, "
        "identify subtle error patterns, accept moderate confidence thresholds, and "
        "make attributions with reasonable evidence.",
    "detail": "You are a Detail-Focused Analyst: examine specific evidence and exact "
        "wording, identify subtle inconsistencies, focus on fine-grained analysis, "
        "and prioritize concrete evidence over patterns.",
    "pattern": "You are a Pattern-Focused Analyst: recognize broader reasoning "
        "chains, track error propagation patterns, identify recurring themes, and "
        "analyze overall reasoning structure.",
    "skeptical": "You are a Skeptical Analyst: question underlying assumptions, "
        "explore alternative explanations, challenge conventional attributions, and "
        "examine the validity of the ground truth.",
    "general": "You are a General Analyst: maintain a balanced perspective, consider "
        "all evidence types equally, focus on obvious, impactful errors, and provide "
        "a baseline objective evaluation.",
}

_OUT_SPEC = (
    "Respond with ONLY a JSON object: "
    '{"investigation_summary": str, '
    '"step_evaluations": [{"step": int, "error_likelihood": float, "evidence": str}], '
    '"primary_conclusion": {"attribution_type": "single_agent"|"multi_agent", '
    '"responsible_agents": [str], "mistake_step": int, "confidence": float}, '
    '"alternative_hypotheses": [str]}'
)


def analyst_prompt(phase, traj, ctx, use_gt):
    gt = f"Ground Truth Answer: {traj.correct_answer}\n" if use_gt else ""
    focus = ("identifying WHICH AGENT(S) are responsible for the failure"
             if phase == "agent" else
             "pinpointing the SPECIFIC STEP where the first decisive error occurred")
    return (
        f"Analyze this failed multi-agent interaction, focusing on {focus}.\n"
        f"Original Query: {traj.query}\n{gt}"
        f"Final (wrong) Answer: {traj.final_response}\n\n"
        "Conversation (hierarchical detail; FULL near the failure, compressed farther "
        "away):\n" + ctx + "\n\n"
        "Evaluate every step's error likelihood in [0,1] with evidence, then give a "
        "primary conclusion with a confidence score in [0,1] and alternative "
        "hypotheses. Attribute only to steps with explicit reasoning.\n" + _OUT_SPEC
    )


def parse_analysis(text):
    try:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        obj = json.loads(m.group(0)) if m else None
    except Exception:
        obj = None
    if not isinstance(obj, dict):
        return None
    pc = obj.get("primary_conclusion") or {}
    return {
        "agents": [a for a in pc.get("responsible_agents", []) if isinstance(a, str)],
        "step": pc.get("mistake_step") if isinstance(pc.get("mistake_step"), (int, float)) else None,
        "conf": float(pc.get("confidence", 0.0) or 0.0),
    }


# --------------------------------------------------------------------------------------
# §3.3 / A.7 — consensus voting
# --------------------------------------------------------------------------------------
def consensus(analyses, delta=DELTA):
    kept = [a for a in analyses if a and a["conf"] >= delta]
    if not kept:
        kept = [a for a in analyses if a]           # fall back to all parseable
    agent_votes, step_votes = defaultdict(float), defaultdict(float)
    confs = []
    for a in kept:
        confs.append(a["conf"])
        for ag in a["agents"]:
            agent_votes[ag.strip()] += a["conf"]
        if a["step"] is not None:
            step_votes[int(a["step"])] += a["conf"]
    top_agent = max(agent_votes, key=agent_votes.get) if agent_votes else None
    top_step = max(step_votes, key=step_votes.get) if step_votes else None
    spread = (max(confs) - min(confs)) if confs else 0.0
    return top_agent, top_step, {"confidence_spread": spread,
                                 "needs_review": spread > 0.5,
                                 "n_kept": len(kept)}


# --------------------------------------------------------------------------------------
# ECHO end-to-end for one trajectory (I4: decoupled agent + step phases)
# --------------------------------------------------------------------------------------
def run_echo(traj, llm, use_gt=True, rng=None, k=K_ANALYSTS, seed=0):
    # Deterministic per-trajectory role sampling: seed from the trajectory id so results
    # are independent of execution order — required for parallel evaluation to match
    # serial. (A shared rng would make role assignment depend on scheduling.)
    if rng is None:
        rng = random.Random(f"{seed}:{traj.id}")
    acting = [s for s in traj.steps if not s.is_input]
    if not acting:
        return None, None
    ctx = hierarchical_render(acting, anchor_idx=len(acting) - 1)
    roles = rng.sample(list(ROLES), k)
    results = {}
    for phase in ("agent", "step"):
        analyses = []
        for j, role in enumerate(roles):
            out = llm(ROLES[role], analyst_prompt(phase, traj, ctx, use_gt),
                      TEMPS[j % len(TEMPS)])
            analyses.append(parse_analysis(out))
        results[phase] = analyses
    top_agent, _, _ = consensus(results["agent"])
    _, top_step, _ = consensus(results["step"])
    return top_agent, top_step


# --------------------------------------------------------------------------------------
# Backends + evaluation
# --------------------------------------------------------------------------------------
def openai_backend(model, base_url=None, api_key="EMPTY"):
    from openai import OpenAI
    client = OpenAI(base_url=base_url, api_key=api_key)

    def call(system, user, temperature):
        r = client.chat.completions.create(
            model=model, temperature=temperature, max_tokens=1500,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}])
        return (r.choices[0].message.content or "").strip()
    return call


def mock_backend():
    def call(system, user, temperature):
        return json.dumps({
            "investigation_summary": "mock",
            "step_evaluations": [{"step": 0, "error_likelihood": 0.9, "evidence": "m"}],
            "primary_conclusion": {"attribution_type": "single_agent",
                                   "responsible_agents": ["Aggregator"],
                                   "mistake_step": 0, "confidence": 0.8},
            "alternative_hypotheses": []})
    return call


def evaluate(name, llm, use_gt=True, limit=None, seed=0, workers=1):
    trajs = load_jsonl(FILES[name])
    _, te = load_split(name)
    te_trajs = [t for t in trajs if t.id in te]
    if limit:
        te_trajs = te_trajs[:limit]

    def one(t):
        # per-trajectory deterministic rng -> parallel result == serial result
        return run_echo(t, llm, use_gt=use_gt, rng=random.Random(f"{seed}:{t.id}"))

    if workers > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(one, te_trajs))
    else:
        results = [one(t) for t in te_trajs]

    a_hit = s_hit = tot = 0
    for t, (pa, ps) in zip(te_trajs, results):
        acting = [s for s in t.steps if not s.is_input]
        gold_idx = next((i for i, s in enumerate(acting)
                         if s.turn == t.labels.earliest_error_turn), None)
        tot += 1
        faulty = {r for (r, _) in t.labels.faulty_instances}
        if pa and any(fr in pa or pa in fr for fr in faulty):
            a_hit += 1
        if ps is not None and gold_idx is not None and int(ps) == gold_idx:
            s_hit += 1
    return {"agent_acc": a_hit / max(tot, 1), "step_acc": s_hit / max(tot, 1), "n": tot}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["openai", "mock"], default="mock")
    ap.add_argument("--model", default="gpt-4o")
    ap.add_argument("--base_url", default=None)
    ap.add_argument("--api_key", default="EMPTY")
    ap.add_argument("--no_gt", action="store_true")
    ap.add_argument("--frameworks", nargs="+", default=list(FILES))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=1, help="concurrent trajectories (feeds vLLM batching)")
    args = ap.parse_args()
    llm = mock_backend() if args.backend == "mock" else \
        openai_backend(args.model, args.base_url, args.api_key)
    tag = "mock (numbers meaningless)" if args.backend == "mock" else args.model
    print(f"ECHO baseline — backend={tag}, GT={'off' if args.no_gt else 'on'}")
    for name in args.frameworks:
        m = evaluate(name, llm, use_gt=not args.no_gt, limit=args.limit, workers=args.workers)
        print(f"  [{name:11s}] agent_acc={m['agent_acc']:.3f} "
              f"step_acc={m['step_acc']:.3f} (n={m['n']})")
