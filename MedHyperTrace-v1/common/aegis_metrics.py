"""Vendored verbatim from the user's AEGIS_Reproduce/aegis_common.py so every
method is scored by the IDENTICAL Agent/Error/Pair Micro/Macro-F1 function.
Do not edit — keep byte-identical to the repo to guarantee metric parity."""
from __future__ import annotations
def _norm_agent(name: str) -> str:
    """Case- and whitespace-insensitive agent comparison.

    The training data has inconsistent casing (e.g. 'Assistant1' vs
    'assistant1' for Dylan). Without normalization, the reward function would
    reject genuinely-correct predictions and the F1 numbers would be
    artificially low. The paper doesn't spell this out explicitly, but
    matching strict-case would be unfaithful to what 'correct attribution'
    actually means.
    """
    return name.strip().lower()


# ---------------------------------------------------------------------------
# Hierarchical reward (paper §5.2)
# ---------------------------------------------------------------------------
# Default coefficients. The paper doesn't pin down exact values, so I picked
# numbers that respect the described inequalities: c_pair > c_agent + c_error
# (so getting the full pair is better than getting the parts separately) and
# c_bonus is small. p_fp dominates Sraw if the model spams predictions.
DEFAULT_REWARD_COEFFS = dict(
    c_pair=1.0,
    c_agent=0.3,
    c_error=0.2,
    c_bonus=0.1,
    p_fp=0.3,
    p_dup=0.2,    # per-duplicate penalty (subtracted from Sraw)
    p_quant=0.2,  # per-extra-prediction penalty beyond 2|P_gt|
    r_mal=-1.0,   # malformed JSON
)


def hierarchical_reward(
    pred_pairs: list[tuple[str, str]],
    gt_pairs: list[tuple[str, str]],
    well_formed: bool,
    coeffs: dict | None = None,
) -> float:
    """Compute R(y_hat, y_gt) per paper §5.2.

    Returns a normalized scalar reward in roughly [-1, 1+]. The exact upper
    bound depends on coefficient choices; what matters for GRPO is the
    *relative* reward within a group, so we just need a stable, dense signal.
    """
    c = {**DEFAULT_REWARD_COEFFS, **(coeffs or {})}

    if not well_formed:
        return c["r_mal"]

    # Normalize for matching
    gt_pairs_n = [(_norm_agent(a), e) for a, e in gt_pairs]
    pred_pairs_n = [(_norm_agent(a), e) for a, e in pred_pairs]

    gt_pair_set = set(gt_pairs_n)
    gt_agent_set = {a for a, _ in gt_pairs_n}
    gt_error_set = {e for _, e in gt_pairs_n}

    # Track which agents/errors have already received partial credit so each
    # can contribute at most once (paper: "non-repeatable partial credits").
    rewarded_pairs: set[tuple[str, str]] = set()
    rewarded_agents: set[str] = set()
    rewarded_errors: set[str] = set()

    s_raw = c["c_bonus"]

    # Duplicate detection: count repeats among well-formed predictions.
    seen: dict[tuple[str, str], int] = {}
    for p in pred_pairs_n:
        seen[p] = seen.get(p, 0) + 1
    n_dup = sum(v - 1 for v in seen.values() if v > 1)
    s_dup = c["p_dup"] * n_dup

    # Quantity penalty for excessive predictions beyond 2|P_gt|.
    cap = 2 * max(len(gt_pairs_n), 1)
    n_excess = max(0, len(pred_pairs_n) - cap)
    s_quant = c["p_quant"] * n_excess

    for (a, e) in pred_pairs_n:
        if (a, e) in gt_pair_set and (a, e) not in rewarded_pairs:
            s_raw += c["c_pair"]
            rewarded_pairs.add((a, e))
            rewarded_agents.add(a)
            rewarded_errors.add(e)
        elif a in gt_agent_set and a not in rewarded_agents:
            s_raw += c["c_agent"]
            rewarded_agents.add(a)
        elif e in gt_error_set and e not in rewarded_errors:
            s_raw += c["c_error"]
            rewarded_errors.add(e)
        else:
            # full false positive: agent and error both not in GT (or already credited)
            s_raw -= c["p_fp"]

    s_raw -= s_dup
    s_raw -= s_quant

    # Normalize by the max attainable score: everything correct, no penalties.
    s_max = max(len(gt_pairs_n), 1) * c["c_pair"] + c["c_bonus"]
    return s_raw / s_max


# ---------------------------------------------------------------------------
# Evaluation metrics (paper §6: Pair / Agent / Error × Micro / Macro F1)
# ---------------------------------------------------------------------------
def _safe_div(n: float, d: float) -> float:
    return n / d if d > 0 else 0.0


def _prf(tp: float, fp: float, fn: float) -> tuple[float, float, float]:
    p = _safe_div(tp, tp + fp)
    r = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * p * r, p + r)
    return p, r, f1


def compute_metrics(
    predictions: list[list[tuple[str, str]]],
    ground_truths: list[list[tuple[str, str]]],
) -> dict[str, float]:
    """Compute Micro/Macro F1 at Pair, Agent, and Error level.

    For Micro F1 we aggregate TP/FP/FN counts across all samples then compute
    one F1. For Macro F1 we compute per-class F1 (per agent / per error / per
    pair-class) and average. The paper reports both because the dataset is
    long-tailed: Micro is dominated by frequent classes, Macro shows whether
    the model handles rare ones.

    Note on Macro at the Agent level: 'class' = a specific agent name (case
    normalized). Same for Error and Pair levels. This matches the paper's
    framing — "F1-score for each class (e.g., each of the 14 error modes)
    independently and then takes the unweighted average."
    """
    assert len(predictions) == len(ground_truths)
    n = len(predictions)

    # Normalize all
    pred_n = [[(_norm_agent(a), e) for a, e in p] for p in predictions]
    gt_n = [[(_norm_agent(a), e) for a, e in g] for g in ground_truths]

    # Per-class accumulators: class -> [tp, fp, fn]
    pair_classes: dict[tuple[str, str], list[float]] = {}
    agent_classes: dict[str, list[float]] = {}
    error_classes: dict[str, list[float]] = {}

    # Micro accumulators
    micro_pair = [0.0, 0.0, 0.0]
    micro_agent = [0.0, 0.0, 0.0]
    micro_error = [0.0, 0.0, 0.0]

    def _bump(d: dict, key, idx):
        if key not in d:
            d[key] = [0.0, 0.0, 0.0]
        d[key][idx] += 1

    for i in range(n):
        p_pairs = set(pred_n[i])
        g_pairs = set(gt_n[i])
        p_agents = {a for a, _ in pred_n[i]}
        g_agents = {a for a, _ in gt_n[i]}
        p_errors = {e for _, e in pred_n[i]}
        g_errors = {e for _, e in gt_n[i]}

        # --- Pair level ---
        tp = p_pairs & g_pairs
        fp = p_pairs - g_pairs
        fn = g_pairs - p_pairs
        micro_pair[0] += len(tp); micro_pair[1] += len(fp); micro_pair[2] += len(fn)
        for k in tp: _bump(pair_classes, k, 0)
        for k in fp: _bump(pair_classes, k, 1)
        for k in fn: _bump(pair_classes, k, 2)

        # --- Agent level ---
        tp = p_agents & g_agents
        fp = p_agents - g_agents
        fn = g_agents - p_agents
        micro_agent[0] += len(tp); micro_agent[1] += len(fp); micro_agent[2] += len(fn)
        for k in tp: _bump(agent_classes, k, 0)
        for k in fp: _bump(agent_classes, k, 1)
        for k in fn: _bump(agent_classes, k, 2)

        # --- Error level ---
        tp = p_errors & g_errors
        fp = p_errors - g_errors
        fn = g_errors - p_errors
        micro_error[0] += len(tp); micro_error[1] += len(fp); micro_error[2] += len(fn)
        for k in tp: _bump(error_classes, k, 0)
        for k in fp: _bump(error_classes, k, 1)
        for k in fn: _bump(error_classes, k, 2)

    def _macro(classes: dict) -> float:
        if not classes:
            return 0.0
        f1s = []
        for _, (tp, fp, fn) in classes.items():
            _, _, f1 = _prf(tp, fp, fn)
            f1s.append(f1)
        return sum(f1s) / len(f1s) if f1s else 0.0

    pp, pr, pf = _prf(*micro_pair)
    ap, ar, af = _prf(*micro_agent)
    ep, er, ef = _prf(*micro_error)

    return {
        "pair_micro_p": pp * 100, "pair_micro_r": pr * 100, "pair_micro_f1": pf * 100,
        "pair_macro_f1": _macro(pair_classes) * 100,
        "agent_micro_p": ap * 100, "agent_micro_r": ar * 100, "agent_micro_f1": af * 100,
        "agent_macro_f1": _macro(agent_classes) * 100,
        "error_micro_p": ep * 100, "error_micro_r": er * 100, "error_micro_f1": ef * 100,
        "error_macro_f1": _macro(error_classes) * 100,
    }
