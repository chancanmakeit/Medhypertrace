r"""
Pluggable factuality-score provider (for the S- signature tier: model-inherent failures
that leave NO in-trajectory structural trace and can only be caught with external world
knowledge).

DESIGN GOAL — do not reinvent hallucination detection. The 2024-2025 literature already
has strong, mostly-open black-box detectors. We define ONE interface; any of them plugs
in as a node feature. The hypergraph stays the ATTRIBUTOR; the detector is a FEATURE
PROVIDER. This lets the three-tier ablation (pure-structure -> +propagation -> +external
factuality) run by swapping providers, and keeps the contribution boundary honest:
we integrate external factual checking into structural attribution; we do not claim a
new hallucination detector.

INTERFACE
    provider.score_steps(steps, context) -> np.ndarray[n] in [0,1]
        one "factual suspiciousness" score per acting step (1 = likely hallucinated).
    The score becomes an extra node-feature dim (see structural_features integration).

WHY A NODE FEATURE (not a separate model): a step's factuality is local evidence; the
hypergraph then propagates/aggregates it through agg/ctx/role/phase edges exactly like
the structural priors. So "was this hallucination believed downstream?" is answered by
the SAME propagation machinery, not a bolt-on.

PROVIDERS
  NullFactualityProvider   default. returns zeros -> identical to current behaviour.
                           (pure-structure tier of the ablation.)
  NLIFactualityProvider    STUB. black-box, static-trajectory-friendly: decompose a step
                           into atomic claims, run an NLI model (entailment vs the
                           provided context / a reference), suspiciousness = fraction of
                           claims NOT entailed. Fits RefChecker / decomposed-entailment
                           style detectors. NO resampling needed -> works on our static
                           logs. (Fill in a real NLI model to activate.)
  MedFactualityProvider    STUB. medical-domain detector (e.g. MedHallu-style judge or a
                           clinical-KB check). Same interface; swap the scoring backend.

IMPORTANT CONSTRAINT (documented so nobody wires the wrong detector):
  Consistency/sampling detectors (SelfCheckGPT, Semantic Entropy) need to RESAMPLE the
  same agent on the same question. Our trajectories are STATIC (already run), so those
  are not directly usable unless you can re-run the agent. Prefer NLI/entailment-based
  (static-text) or medical-judge providers. See docs/factuality_providers.md.

All providers are optional and OFF by default: with the Null provider the node feature
is unchanged from the current pipeline, so existing numbers are byte-identical.
"""
from __future__ import annotations

import numpy as np


class FactualityProvider:
    """Interface. Return one suspiciousness score in [0,1] per acting step."""

    name = "base"

    def score_steps(self, steps, context: str = "") -> np.ndarray:
        raise NotImplementedError

    # convenience: providers may cache; default no-op
    def warmup(self, all_steps=None):
        return self


class NullFactualityProvider(FactualityProvider):
    """Default: no external factuality signal. Node feature stays 0 -> current behaviour.
    This is the 'pure-structure' tier of the three-tier ablation."""

    name = "null"

    def score_steps(self, steps, context: str = "") -> np.ndarray:
        return np.zeros(len(steps), np.float32)


class HeuristicFactualityProvider(FactualityProvider):
    """A cheap, dependency-free PLACEHOLDER signal so the plumbing can be exercised on
    CPU without any model download. It is NOT a real detector and must NOT be reported as
    one — it merely flags steps dense in unverifiable quantitative claims (doses, numeric
    thresholds, units), which correlate weakly with fabrication risk in clinical text.
    Use only for wiring/ablation-harness tests; swap for NLIFactualityProvider for real
    numbers."""

    name = "heuristic"

    def __init__(self):
        import re
        # doses / numbers with medical-ish units, percentages, comparators
        self._pat = re.compile(
            r"\b\d+(?:\.\d+)?\s?(?:mg|mcg|µg|ug|ml|mmhg|mmol|mm|cm|kg|%|units?|"
            r"mg/dl|mg/kg|iu)\b|\b\d+(?:\.\d+)?\s?(?:times|fold)\b", re.IGNORECASE)

    def score_steps(self, steps, context: str = "") -> np.ndarray:
        out = np.zeros(len(steps), np.float32)
        for i, s in enumerate(steps):
            txt = getattr(s, "content", "") or ""
            if not txt:
                continue
            n_claims = len(self._pat.findall(txt))
            # squash to [0,1); more numeric medical claims -> higher suspiciousness prior
            out[i] = 1.0 - 1.0 / (1.0 + 0.5 * n_claims)
        return out


class NLIFactualityProvider(FactualityProvider):
    """STUB for a black-box, static-text detector (RefChecker / decomposed entailment).
    Plug a real NLI model into `_entails`. Suspiciousness = 1 - (entailed_claims / claims).

    This provider is static-trajectory-friendly: it needs only the step text and a
    reference/context, no resampling of the original agent."""

    name = "nli"

    def __init__(self, nli_model=None, claim_splitter=None):
        self._nli = nli_model            # callable(premise, hypothesis) -> P(entail)
        self._split = claim_splitter     # callable(text) -> list[str] atomic claims

    def _entails(self, premise: str, claim: str) -> float:
        if self._nli is None:
            raise RuntimeError(
                "NLIFactualityProvider needs an NLI model. Pass nli_model=callable"
                "(premise,hypothesis)->entail_prob. See docs/factuality_providers.md.")
        return float(self._nli(premise, claim))

    def score_steps(self, steps, context: str = "") -> np.ndarray:
        out = np.zeros(len(steps), np.float32)
        for i, s in enumerate(steps):
            txt = getattr(s, "content", "") or ""
            claims = self._split(txt) if self._split else ([txt] if txt else [])
            if not claims:
                continue
            entailed = sum(1 for c in claims if self._entails(context, c) >= 0.5)
            out[i] = 1.0 - entailed / len(claims)
        return out


class MedFactualityProvider(FactualityProvider):
    """STUB for a medical-domain detector (MedHallu-style judge, clinical-KB check, or a
    RAG-grounded verifier). Same interface; provide a `judge(step_text, context)->[0,1]`.
    Keep the scoring backend swappable so the paper can cite whichever SOTA detector is
    used without changing the attribution model."""

    name = "medical"

    def __init__(self, judge=None):
        self._judge = judge              # callable(step_text, context) -> suspiciousness

    def score_steps(self, steps, context: str = "") -> np.ndarray:
        if self._judge is None:
            raise RuntimeError(
                "MedFactualityProvider needs a judge callable. See "
                "docs/factuality_providers.md for candidate open detectors (MedHallu, "
                "KnowHalu, RefChecker).")
        out = np.zeros(len(steps), np.float32)
        for i, s in enumerate(steps):
            txt = getattr(s, "content", "") or ""
            out[i] = float(self._judge(txt, context)) if txt else 0.0
        return out


# registry so train_hgnn can select via a flag string
PROVIDERS = {
    "null": NullFactualityProvider,
    "heuristic": HeuristicFactualityProvider,
    "nli": NLIFactualityProvider,
    "medical": MedFactualityProvider,
}


def get_provider(name: str = "null", **kwargs) -> FactualityProvider:
    """Factory. Default 'null' keeps the pipeline byte-identical to no-factuality.

    'nli' returns a REAL, wired NLI detector (RefChecker-style, open-source, offline) via
    common.factuality_nli.build_nli_provider — pass model=/reference=/device= through
    kwargs. The bare NLIFactualityProvider class stays available for custom wiring.
    """
    if name == "nli":
        # real detector: claim split + HF NLI checker (needs transformers+torch)
        from common.factuality_nli import build_nli_provider
        return build_nli_provider(
            model=kwargs.get("model", "cross-encoder/nli-deberta-v3-small"),
            reference=kwargs.get("reference", "prior-steps"),
            device=kwargs.get("device", "auto"),
            entail_thresh=kwargs.get("entail_thresh", 0.5))
    if name not in PROVIDERS:
        raise ValueError(f"unknown factuality provider '{name}'. "
                         f"choices: {list(PROVIDERS)}")
    return PROVIDERS[name](**kwargs)
