"""
Who&When baseline (Zhang et al., ICML 2025) faithfully adapted to our medical MAS data.

Reproduces the three official protocols from
  github.com/mingyin1/Agents_Failure_Attribution (Automated_FA/Lib/utils.py):
    * all_at_once   — whole trajectory in one prompt, model returns Agent+Step+Reason
    * step_by_step  — walk turns, ask Yes/No "is this step the error", stop at first Yes
    * binary_search — recursively narrow to the half containing the decisive error

Prompts, the step-numbering convention (0-indexed turn), and the agent field
(`name`) are copied from the official repo. The single culprit that Who&When
predicts is scored against our labels as:
    agent-acc : predicted agent ∈ faulty_instances' role set   (multi-fault aware)
    step-acc  : predicted step == earliest error step (their "when")

The LLM backend is pluggable via `llm_call`. Nothing here needs a GPU except the
model endpoint you point it at; the formatting/parsing is verified with a mock.
"""
from __future__ import annotations

import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)


import re
import sys
from dataclasses import dataclass
from typing import Callable, Optional

from common.data import load_jsonl, Trajectory

# --------------------------------------------------------------------------------------
# LLM backend: plug in Azure/OpenAI/local. Signature: (system, user) -> text.
# --------------------------------------------------------------------------------------
LLMCall = Callable[[str, str], str]


def openai_backend(model="gpt-4o", base_url=None, api_key=None,
                   max_tokens=1024, temperature=0.0) -> LLMCall:
    """OpenAI-compatible chat backend (works for vLLM/local servers via base_url).
    The OpenAI client is thread-safe, so this backend can be shared across the threads
    spawned by evaluate_parallel() — concurrent requests let a vLLM server batch them."""
    from openai import OpenAI
    client = OpenAI(base_url=base_url, api_key=api_key)

    def call(system: str, user: str) -> str:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            max_tokens=max_tokens, temperature=temperature,
        )
        return (r.choices[0].message.content or "").strip()
    return call


def openai_backend_batch(model="gpt-4o", base_url=None, api_key=None,
                         max_tokens=1024, temperature=0.0, workers=16):
    """Returns a batch callable: list[(system,user)] -> list[str], issuing all requests
    concurrently against a vLLM/OpenAI server. Use for run_step_by_step_batched (within-
    trajectory parallelism). Also usable as a plain LLMCall via .single()."""
    from concurrent.futures import ThreadPoolExecutor
    from openai import OpenAI
    client = OpenAI(base_url=base_url, api_key=api_key)

    def one(su):
        system, user = su
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            max_tokens=max_tokens, temperature=temperature,
        )
        return (r.choices[0].message.content or "").strip()

    def batch(prompts):
        if not prompts:
            return []
        with ThreadPoolExecutor(max_workers=min(workers, len(prompts))) as ex:
            return list(ex.map(one, prompts))

    batch.single = lambda system, user: one((system, user))  # type: ignore
    return batch


def ct2_backend(model_dir, tokenizer_dir=None, compute_type="float32",
                max_input=512, max_new=48, device="auto", threads=1) -> LLMCall:
    """Local CTranslate2 seq2seq backend (e.g. tinyteapot / flan-T5 family).

    NOTE on compute_type: for tinyteapot (77M T5) int8 quantization DESTROYS output
    quality (verified: gibberish / semantic drift), while CT2 float32 is both correct
    and ~23x faster than HF fp32. Default is therefore float32, not int8.

    device='auto' -> cuda if a CUDA-enabled CT2 build + GPU is present, else cpu.
    """
    import ctranslate2
    from transformers import AutoTokenizer
    if device == "auto":
        try:
            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            device = "cpu"
    tok = AutoTokenizer.from_pretrained(tokenizer_dir or model_dir)
    tr = ctranslate2.Translator(model_dir, device=device, compute_type=compute_type,
                                inter_threads=1, intra_threads=threads)

    def call(system: str, user: str) -> str:
        text = f"{system}\n{user}" if system else user
        ids = tok(text, truncation=True, max_length=max_input).input_ids
        src = tok.convert_ids_to_tokens(ids)
        res = tr.translate_batch([src], max_decoding_length=max_new,
                                 beam_size=1)
        hyp = res[0].hypotheses[0]
        return tok.decode(tok.convert_tokens_to_ids(hyp), skip_special_tokens=True).strip()
    return call


def hf_backend(model_id="HuggingFaceTB/SmolLM2-135M-Instruct", device="auto",
               max_new=48, max_input=3072, dtype=None) -> LLMCall:
    """Local HuggingFace causal-LM backend (SmolLM2 / Qwen2.5-Instruct / ...).

    device='auto' -> device_map='auto' when accelerate+CUDA are available, else CPU.
    Greedy decoding (temperature 0) for reproducibility.
    """
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    tok = AutoTokenizer.from_pretrained(model_id)
    use_cuda = torch.cuda.is_available()
    if dtype is None:
        dtype = torch.bfloat16 if use_cuda else torch.float32
    kw = {"dtype": dtype}
    if device == "auto" and use_cuda:
        kw["device_map"] = "auto"
    model = AutoModelForCausalLM.from_pretrained(model_id, **kw).eval()
    if device != "auto":
        model = model.to(device)

    def call(system: str, user: str) -> str:
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": user}]
        try:
            text = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        except Exception:
            text = (system + "\n" if system else "") + user
        ids = tok(text, return_tensors="pt", truncation=True, max_length=max_input)
        ids = {k: v.to(model.device) for k, v in ids.items()}
        with torch.no_grad():
            out = model.generate(**ids, max_new_tokens=max_new, do_sample=False,
                                 pad_token_id=tok.eos_token_id)
        n_in = ids["input_ids"].shape[1]
        return tok.decode(out[0, n_in:], skip_special_tokens=True).strip()
    return call


# --------------------------------------------------------------------------------------
# Render a trajectory the way Who&When renders `history` (name: content per turn).
# We use ACTING steps only, 0-indexed like the official code.
# --------------------------------------------------------------------------------------
def acting_turns(traj: Trajectory):
    return [s for s in traj.steps if not s.is_input]


# Per-step content cap. The official code sends full content; with small local models
# that overflows the usable context (and costs minutes/трajectory on CPU), so we cap it.
# Set WW_STEP_CHARS=0 for the untruncated official behaviour (use on a GPU box).
STEP_CHARS = int(_os.environ.get("WW_STEP_CHARS", "600"))


def _clip(txt: str) -> str:
    return txt if STEP_CHARS <= 0 or len(txt) <= STEP_CHARS else txt[:STEP_CHARS] + " ..."


def render_history(traj: Trajectory) -> str:
    return "\n".join(f"{s.agent_name}: {_clip(s.content)}" for s in acting_turns(traj))


# ---- Prompt builders (verbatim structure from the official repo) ----------------------
def prompt_all_at_once(traj: Trajectory) -> str:
    chat = render_history(traj)
    return (
        "You are an AI assistant tasked with analyzing a multi-agent conversation "
        "history when solving a real world problem. "
        f"The problem is:  {traj.query}\n"
        f"The Answer for the problem is: {traj.correct_answer}\n"
        "Identify which agent made an error, at which step, and explain the reason "
        "for the error. Here's the conversation:\n\n" + chat +
        "\n\nBased on this conversation, please predict the following:\n"
        "1. The name of the agent who made a mistake that should be directly "
        "responsible for the wrong solution. Directly output the name of the agent.\n"
        "2. In which step the mistake agent first made mistake. Steps are 0-indexed "
        "by turn (the first speaker is step 0, the second is step 1, ...). "
        "Determine the step number where the first mistake occurred.\n"
        "3. The reason for your prediction."
        "Please answer in the format: Agent Name: (Your prediction)\n "
        "Step Number: (Your prediction)\n Reason for Mistake: \n"
    )


def prompt_step_by_step(traj: Trajectory, upto: str, idx: int, agent_name: str) -> str:
    return (
        "You are an AI assistant tasked with evaluating the correctness of each step "
        f"in an ongoing multi-agent conversation. The problem is: {traj.query}. "
        f"The Answer for the problem is: {traj.correct_answer}\n"
        f"Here is the conversation history up to the current step:\n{upto}\n"
        f"The most recent step ({idx}) was by '{agent_name}'.\n"
        f"Determine whether this most recent agent's action (Step {idx}) contains an "
        "error that could lead to an incorrect solution. Avoid being overly critical; "
        "focus on errors that clearly derail the process. "
        "Respond ONLY in the format: 1. Yes/No.\n2. Reason: [explanation]"
    )


def prompt_binary(traj: Trajectory, seg: str, rng: str, up: str, low: str) -> str:
    return (
        "You are an AI assistant analyzing a segment of a multi-agent conversation. "
        "Identify which half of the segment contains the single decisive error.\n"
        f"The problem is: {traj.query}\n"
        f"The Answer for the problem is: {traj.correct_answer}\n"
        f"Review the following conversation segment {rng}:\n\n{seg}\n\n"
        f"Predict whether the most critical error is in the upper half ({up}) or the "
        f"lower half ({low}). Respond with ONLY 'upper half' or 'lower half'."
    )


# ======================================================================================
# SET-PREDICTION variants. These output a SET of (agent, FM) pairs per trajectory, so
# that Who&When-style zero-shot methods can be scored with the SAME Agent/Error-Micro-F1
# used for the set-prediction methods (ours / pointwise / med-SFT). This makes every
# method comparable under one metric family instead of accuracy-vs-F1 across two tables.
#
# Covered: all_at_once_set, step_by_step_set, sdbl_set.
# NOT covered: binary_search — its divide-and-conquer mechanism is intrinsically single-
# point localization and cannot yield a set without becoming a different algorithm; it is
# therefore dropped from the unified F1 table (its single-prediction accuracy can still be
# reported separately in an appendix).
# ======================================================================================
from common.data import FM_TYPES

_FM_LIST = ", ".join(FM_TYPES)


def _parse_pairs(text, agent_names):
    """Extract a set of (agent, FM) pairs from free-form output. Accepts lines like
    'Agent: Reasoner | FM-3.2' or 'Reasoner: FM-3.2' or JSON-ish listings. Falls back to
    matching any known agent name co-occurring with an FM code on the same line."""
    pairs = set()
    for line in text.splitlines():
        fms = re.findall(r"FM-\s*(\d)\s*\.\s*(\d)", line, re.IGNORECASE)
        if not fms:
            continue
        hit_agent = None
        low = line.lower()
        cand = [(low.index(n.lower()), n) for n in agent_names if n.lower() in low]
        if cand:
            hit_agent = min(cand)[1]
        for a, b in fms:
            code = f"FM-{a}.{b}"
            if code in FM_TYPES and hit_agent:
                pairs.add((hit_agent, code))
    # fallback: agents named anywhere + first FM seen (keeps recall > 0 for weak models)
    if not pairs:
        low = text.lower()
        named = [n for n in agent_names if n.lower() in low]
        fm = re.search(r"FM-\s*(\d)\s*\.\s*(\d)", text)
        if named and fm:
            code = f"FM-{fm.group(1)}.{fm.group(2)}"
            if code in FM_TYPES:
                pairs = {(named[0], code)}
    return sorted(pairs)


def _parse_agents_only(text, agent_names):
    """Extract just the set of accused agents (for methods/prompts that name agents
    without committing to an FM). FM is left as a sentinel to be filled by a follow-up
    or scored at agent level only."""
    low = text.lower()
    return sorted({n for n in agent_names if n.lower() in low})


def prompt_all_at_once_set(traj):
    chat = render_history(traj)
    return (
        "You are analyzing a failed multi-agent conversation. "
        f"The problem is: {traj.query}\n"
        f"The correct answer is: {traj.correct_answer}\n"
        "Identify ALL agents that made an error contributing to the failure, and for "
        "each, the failure mode from this list: " + _FM_LIST + ".\n"
        "Here is the conversation:\n\n" + chat +
        "\n\nList every responsible (agent, failure mode) pair, one per line, as:\n"
        "Agent: <name> | <FM-code>\n"
        "Include all that apply; do not limit to one."
    )


def prompt_step_fm(traj, upto, idx, agent_name):
    """After a step is judged faulty, ask which FM it is (for step_by_step_set)."""
    return (
        f"In this multi-agent conversation for problem: {traj.query}\n"
        f"The correct answer is: {traj.correct_answer}\n"
        f"Conversation up to the current step:\n{upto}\n"
        f"Step {idx} by '{agent_name}' was judged to contain an error. "
        "Which failure mode best describes it? Choose one from: " + _FM_LIST + ".\n"
        "Reply with ONLY the FM code (e.g. FM-3.2)."
    )


def prompt_sdbl_scope(traj):
    """SDBL stage 1: delineate the SCOPE — which agents fall in the suspect region."""
    chat = render_history(traj)
    names = ", ".join(sorted({s.agent_name for s in acting_turns(traj)}))
    return (
        "You are localizing errors in a failed multi-agent conversation via two stages. "
        "STAGE 1 (scope): identify the set of agents whose actions plausibly fall within "
        "the error-bearing region — be inclusive, this is a shortlist.\n"
        f"The problem is: {traj.query}\nThe correct answer is: {traj.correct_answer}\n"
        f"Agents present: {names}\n\nConversation:\n\n{chat}\n\n"
        "List the shortlisted agent names, comma-separated."
    )


def prompt_sdbl_localize(traj, scope_agents):
    """SDBL stage 2: within the scope, commit to (agent, FM) pairs."""
    chat = render_history(traj)
    return (
        "STAGE 2 (localize): within the shortlisted agents "
        f"[{', '.join(scope_agents)}], identify every agent that actually made an error "
        "and its failure mode from: " + _FM_LIST + ".\n"
        f"The problem is: {traj.query}\nThe correct answer is: {traj.correct_answer}\n"
        f"\nConversation:\n\n{chat}\n\n"
        "List each responsible (agent, failure mode) pair, one per line:\n"
        "Agent: <name> | <FM-code>"
    )


def run_all_at_once_set(traj, llm):
    """Set-prediction variant of all-at-once. Returns (pairs, earliest_step_idx)."""
    names = sorted({s.agent_name for s in acting_turns(traj)})
    out = llm("You are a helpful assistant skilled in analyzing conversations.",
              prompt_all_at_once_set(traj))
    pairs = _parse_pairs(out, names)
    # step: earliest step whose agent is among the accused (or single-pred parse fallback)
    est = _earliest_step_for_agents(traj, {a for a, _ in pairs})
    return pairs, est


def run_step_by_step_set(traj, llm):
    """Set variant: collect ALL steps judged faulty (not just the first), then ask the FM
    for each. Returns (pairs, earliest_faulty_step_idx)."""
    turns = acting_turns(traj)
    hist = ""
    faulty = []          # (idx, agent_name)
    for idx, s in enumerate(turns):
        hist += f"Step {idx} - {s.agent_name}: {_clip(s.content)}\n"
        out = llm("You are a precise step-by-step conversation evaluator.",
                  prompt_step_by_step(traj, hist, idx, s.agent_name))
        o = out.lower().strip()
        if o.startswith("1. yes") or o.startswith("yes") or o.startswith("1.yes"):
            faulty.append((idx, s.agent_name))
    pairs = set()
    for idx, agent in faulty:
        fm_out = llm("You are a failure-mode classifier.",
                     prompt_step_fm(traj, hist, idx, agent))
        m = re.search(r"FM-\s*(\d)\s*\.\s*(\d)", fm_out)
        if m:
            code = f"FM-{m.group(1)}.{m.group(2)}"
            if code in FM_TYPES:
                pairs.add((agent, code))
    est = faulty[0][0] if faulty else None
    return sorted(pairs), est


def run_sdbl_set(traj, llm):
    """SDBL: stage-1 scope delineation -> stage-2 localization. Returns (pairs, est)."""
    names = sorted({s.agent_name for s in acting_turns(traj)})
    scope_out = llm("You are localizing errors, stage 1.", prompt_sdbl_scope(traj))
    scope = _parse_agents_only(scope_out, names) or names
    loc_out = llm("You are localizing errors, stage 2.",
                  prompt_sdbl_localize(traj, scope))
    pairs = _parse_pairs(loc_out, names)
    est = _earliest_step_for_agents(traj, {a for a, _ in pairs})
    return pairs, est


def _earliest_step_for_agents(traj, agents):
    """0-based index of the earliest acting step executed by any accused agent."""
    if not agents:
        return None
    turns = acting_turns(traj)
    for i, s in enumerate(turns):
        if s.agent_name in agents:
            return i
    return None


SET_METHODS = {"all_at_once_set": run_all_at_once_set,
               "step_by_step_set": run_step_by_step_set,
               "sdbl_set": run_sdbl_set}


# ---- Output parsing (matches evaluate.py regexes) -------------------------------------
def parse_agent_step(text: str, agent_names=None):
    """Primary: the official 'Agent Name: X / Step Number: N' template.
    Fallback (needed for small models that ignore the format): search the free-form
    text for any known agent name and for a step index. This measures attribution
    ability rather than format compliance; without it a 77M model scores ~0 purely
    on formatting. Fallbacks are only used when the template is absent."""
    a = re.search(r"Agent Name:\s*([\w \-]+)", text, re.IGNORECASE)
    s = re.search(r"Step Number:\s*(\d+)", text, re.IGNORECASE)
    agent = a.group(1).strip() if a else None
    step = int(s.group(1)) if s else None

    if agent is None and agent_names:
        low = text.lower()
        hits = [(low.index(n.lower()), n) for n in agent_names if n.lower() in low]
        if hits:
            agent = min(hits)[1]          # earliest-mentioned known agent
    if step is None:
        m = re.search(r"\[?\s*Step\s*#?\s*(\d+)", text, re.IGNORECASE)
        if m:
            step = int(m.group(1))
        else:
            m2 = re.search(r"\b(\d{1,2})\b", text)
            if m2:
                step = int(m2.group(1))
    return agent, step


# --------------------------------------------------------------------------------------
# The three protocols. Each returns (pred_agent_name, pred_step_turn_index_0based).
# --------------------------------------------------------------------------------------
def run_all_at_once(traj, llm: LLMCall):
    out = llm("You are a helpful assistant skilled in analyzing conversations.",
              prompt_all_at_once(traj))
    names = sorted({s.agent_name for s in acting_turns(traj)})
    return parse_agent_step(out, names)


def run_step_by_step(traj, llm: LLMCall):
    turns = acting_turns(traj)
    hist = ""
    for idx, s in enumerate(turns):
        hist += f"Step {idx} - {s.agent_name}: {_clip(s.content)}\n"
        out = llm("You are a precise step-by-step conversation evaluator.",
                  prompt_step_by_step(traj, hist, idx, s.agent_name))
        o = out.lower().strip()
        if o.startswith("1. yes") or o.startswith("yes") or o.startswith("1.yes"):
            return s.agent_name, idx
    return (turns[-1].agent_name, len(turns) - 1) if turns else (None, None)


def run_binary_search(traj, llm: LLMCall):
    turns = acting_turns(traj)
    if not turns:
        return None, None

    def rec(start, end):
        if start >= end:
            return start
        seg = "\n".join(f"{turns[i].agent_name}: {_clip(turns[i].content)}"
                        for i in range(start, end + 1))
        mid = start + (end - start) // 2
        out = llm("You are an AI assistant specializing in localizing errors.",
                  prompt_binary(traj, seg, f"from step {start} to step {end}",
                                f"from step {start} to step {mid}",
                                f"from step {mid+1} to step {end}")).lower()
        if "upper half" in out:
            return rec(start, mid)
        if "lower half" in out:
            return rec(min(mid + 1, end), end)
        return rec(start, mid)  # default upper on ambiguity

    step = rec(0, len(turns) - 1)
    return turns[step].agent_name, step


# Single-prediction protocols (accuracy-only; appendix). binary_search is single-point
# by construction; step_by_step here is the ORIGINAL early-return version. For the unified
# Micro-F1 table use SET_METHODS (all_at_once_set / step_by_step_set / sdbl_set) instead.
METHODS = {"all_at_once": run_all_at_once,
           "step_by_step": run_step_by_step,
           "binary_search": run_binary_search}


# --------------------------------------------------------------------------------------
# Evaluation — single-culprit predictions scored against our multi-fault labels.
# --------------------------------------------------------------------------------------
@dataclass
class WWResult:
    agent_acc: float
    step_acc: float
    n: int


def evaluate(trajs, method: str, llm: LLMCall, limit: Optional[int] = None) -> WWResult:
    fn = METHODS[method]
    faulty_role_sets = []
    correct_a = correct_s = n = 0
    for t in (trajs[:limit] if limit else trajs):
        pred_agent, pred_step = fn(t, llm)
        n += 1
        faulty_roles = {r for (r, _) in t.labels.faulty_instances}
        # step-level GT: earliest error step -> its 0-based turn index among acting steps
        turns = acting_turns(t)
        gold_step_idx = None
        for i, s in enumerate(turns):
            if s.turn == t.labels.earliest_error_turn:
                gold_step_idx = i
                break
        if pred_agent and any(fr in pred_agent or pred_agent in fr for fr in faulty_roles):
            correct_a += 1
        if pred_step is not None and pred_step == gold_step_idx:
            correct_s += 1
    return WWResult(correct_a / max(n, 1), correct_s / max(n, 1), n)


def _score(trajs, preds) -> WWResult:
    """Score a list of (pred_agent, pred_step) against trajs (shared by serial/parallel)."""
    correct_a = correct_s = n = 0
    for t, (pred_agent, pred_step) in zip(trajs, preds):
        n += 1
        faulty_roles = {r for (r, _) in t.labels.faulty_instances}
        turns = acting_turns(t)
        gold_step_idx = next((i for i, s in enumerate(turns)
                              if s.turn == t.labels.earliest_error_turn), None)
        if pred_agent and any(fr in pred_agent or pred_agent in fr for fr in faulty_roles):
            correct_a += 1
        if pred_step is not None and pred_step == gold_step_idx:
            correct_s += 1
    return WWResult(correct_a / max(n, 1), correct_s / max(n, 1), n)


def evaluate_parallel(trajs, method: str, llm: LLMCall, limit: Optional[int] = None,
                      workers: int = 16) -> WWResult:
    """Cross-trajectory parallel evaluation. Each trajectory is processed by one worker;
    the protocol function runs unchanged inside that worker (so binary_search's within-
    trajectory dependency and step_by_step's early-return are preserved). With `workers`
    trajectories in flight at once, an OpenAI-compatible vLLM server batches them via
    continuous batching — this is what actually saturates tensor/data-parallel serving.

    workers=1 is equivalent to serial evaluate(). Ordering of results is preserved.
    """
    from concurrent.futures import ThreadPoolExecutor

    fn = METHODS[method]
    items = trajs[:limit] if limit else trajs
    preds = [None] * len(items)

    def work(i):
        return i, fn(items[i], llm)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, pred in ex.map(work, range(len(items))):
            preds[i] = pred
    return _score(items, preds)


def run_step_by_step_batched(traj, llm_batch):
    """Within-trajectory parallel variant of step_by_step. Instead of asking about each
    step sequentially (stopping at the first 'yes'), it asks about ALL steps at once via
    a batched backend, then returns the FIRST step judged faulty — identical semantics to
    the sequential early-return, but every per-step query is issued concurrently.

    llm_batch: takes a list of (system, user) and returns a list of outputs.
    Use with a batched backend (openai_backend_batch). Falls back to per-call if the
    backend is a plain LLMCall.
    """
    turns = acting_turns(traj)
    if not turns:
        return None, None
    hist = ""
    prompts = []
    for idx, s in enumerate(turns):
        hist += f"Step {idx} - {s.agent_name}: {_clip(s.content)}\n"
        prompts.append(("You are a precise step-by-step conversation evaluator.",
                        prompt_step_by_step(traj, hist, idx, s.agent_name)))
    outs = llm_batch(prompts)
    for idx, out in enumerate(outs):
        o = out.lower().strip()
        if o.startswith("1. yes") or o.startswith("yes") or o.startswith("1.yes"):
            return turns[idx].agent_name, idx
    return turns[-1].agent_name, len(turns) - 1


# --------------------------------------------------------------------------------------
# Mock backend to VERIFY formatting/parsing without a real LLM (used in __main__).
# --------------------------------------------------------------------------------------
def mock_backend() -> LLMCall:
    """Deterministic stand-in: 'all-at-once' -> a parseable canned answer;
    step/binary -> always 'No'/'upper half'. Proves the plumbing end-to-end."""
    def call(system: str, user: str) -> str:
        if "upper half" in user:
            return "upper half"
        if "Respond ONLY in the format" in user:
            return "1. No.\n2. Reason: looks fine."
        return "Agent Name: Aggregator\nStep Number: 0\nReason for Mistake: mock."
    return call


if __name__ == "__main__":
    from common.paths import FILES
    llm = mock_backend()
    print("Who&When adapter — plumbing check with MOCK backend (numbers are meaningless):")
    for name, path in FILES.items():
        trajs = load_jsonl(path)
        for m in METHODS:
            r = evaluate(trajs, m, llm, limit=20)
            print(f"  [{name:11s}] {m:13s} agent_acc={r.agent_acc:.2f} "
                  f"step_acc={r.step_acc:.2f} (n={r.n})")
    print("\nTo run for real, e.g.:")
    print("  from baseline_whowhen import openai_backend, evaluate, load_jsonl")
    print("  llm = openai_backend(model='gpt-4o', base_url='http://localhost:8000/v1', api_key='x')")
    print("  evaluate(load_jsonl(path), 'all_at_once', llm)")
