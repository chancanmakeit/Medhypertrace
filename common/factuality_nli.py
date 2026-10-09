r"""
Real NLI-based factuality provider (RefChecker-style, open-source, static-text).

This is NOT a placeholder — it is a working detector. It follows RefChecker's NLI-checker
design (amazon-science/RefChecker): decompose a step's text into atomic claims, then use a
small open-source NLI model to check each claim against a reference/context. A claim that
the context does NOT entail (i.e. neutral/contradiction) counts as suspicious.
Suspiciousness(step) = 1 - entailed_claims / total_claims.

Why this variant (vs. full RefChecker): RefChecker's triplet extractor needs an LLM
(GPT-4/Claude/Mixtral). We avoid that dependency by using rule-based claim splitting +
a small NLI model (RoBERTa/DeBERTa-MNLI), so the whole thing runs offline on CPU/GPU with
no API. This is exactly RefChecker's "NLI-based checker" branch, which the paper shows is
competitive and uses small pre-trained LMs (RoBERTa-NLI).

Static-trajectory friendly: needs only the step text + a reference string. No resampling
of the original agent (unlike SelfCheckGPT / Semantic Entropy).

WHAT COUNTS AS THE REFERENCE (context) — choose per experiment:
  * "prior-steps"  : concatenation of earlier steps in the SAME trajectory. Detects claims
                     unsupported by the conversation so far (in-trajectory grounding).
  * "gold-answer"  : the trajectory's known correct answer (traj.correct_answer). Detects
                     claims inconsistent with ground truth — closest to "factual error".
  * external KB    : plug your own retrieval; pass reference text in `context`.
The wrapper below builds "prior-steps" by default; pass context= to override.

USAGE (server, with transformers installed):
    from common.factuality_nli import NLIChecker, build_nli_provider
    prov = build_nli_provider(model="cross-encoder/nli-deberta-v3-small",
                              reference="prior-steps")
    # then: train_hgnn ... with this provider (see integration note at bottom)

Models known to work as `model` (all open, small, CPU-loadable):
    cross-encoder/nli-deberta-v3-small     (~140MB, fast)
    MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli
    roberta-large-mnli                      (RefChecker's RoBERTa-NLI baseline)
"""
from __future__ import annotations

import re

import numpy as np


# ------------------------------------------------------------------ claim splitting
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def split_claims(text: str, min_len: int = 15):
    """Rule-based atomic-claim splitter (no LLM). Splits on sentence boundaries and
    semicolons; drops very short fragments and pure boilerplate. Good enough for the
    NLI checker; swap for an LLM triplet extractor if you want full RefChecker fidelity."""
    if not text:
        return []
    text = text.strip()
    parts = []
    for sent in _SENT_SPLIT.split(text):
        for frag in sent.split(";"):
            frag = frag.strip()
            if len(frag) >= min_len:
                parts.append(frag)
    return parts


# ------------------------------------------------------------------ NLI checker
class NLIChecker:
    """Wraps a HF sequence-classification NLI model. entail_prob(premise, hypothesis)
    returns P(entailment). Lazily loads the model so importing this file is cheap and
    does not require transformers unless you actually build a checker."""

    def __init__(self, model: str = "cross-encoder/nli-deberta-v3-small",
                 device: str = "auto", batch_size: int = 32):
        self.model_name = model
        self.device = device
        self.batch_size = batch_size
        self._tok = None
        self._model = None
        self._entail_idx = None

    def _lazy(self):
        if self._model is not None:
            return
        try:
            import torch
            from transformers import (AutoModelForSequenceClassification,
                                      AutoTokenizer)
        except Exception as e:
            raise RuntimeError(
                "NLIChecker needs `transformers` + `torch`. Install them on the GPU box; "
                "this detector cannot run where they're unavailable.") from e
        dev = self.device
        if dev == "auto":
            dev = "cuda" if torch.cuda.is_available() else "cpu"
        self._torch = torch
        self._tok = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name).to(dev).eval()
        self._dev = dev
        # find the "entailment" label index from the model config
        id2label = {int(k): v.lower() for k, v in
                    self._model.config.id2label.items()}
        self._entail_idx = next((i for i, l in id2label.items()
                                 if "entail" in l), None)
        if self._entail_idx is None:
            # common ordering fallback: [contradiction, neutral, entailment]
            self._entail_idx = len(id2label) - 1

    def entail_probs(self, premise: str, hypotheses):
        """Return P(entailment) for each (premise, hypothesis)."""
        self._lazy()
        if not hypotheses:
            return []
        torch = self._torch
        out = []
        for i in range(0, len(hypotheses), self.batch_size):
            chunk = hypotheses[i:i + self.batch_size]
            enc = self._tok([premise] * len(chunk), chunk, truncation=True,
                            padding=True, max_length=512, return_tensors="pt").to(self._dev)
            with torch.no_grad():
                logits = self._model(**enc).logits
                probs = torch.softmax(logits, dim=-1)[:, self._entail_idx]
            out.extend(probs.detach().cpu().tolist())
        return out


# ------------------------------------------------------------------ provider factory
def build_nli_provider(model: str = "cross-encoder/nli-deberta-v3-small",
                       reference: str = "prior-steps",
                       device: str = "auto", entail_thresh: float = 0.5):
    """Build an NLIFactualityProvider wired to a real HF NLI checker + rule-based claim
    splitter. `reference` controls what each claim is checked against:
      'prior-steps' (default) | 'gold-answer' | 'none' (uses the `context` arg passed in).
    Returns a provider whose score_steps(steps, context) yields per-step suspiciousness.
    """
    from common.factuality_provider import NLIFactualityProvider

    checker = NLIChecker(model=model, device=device)

    def nli_model(premise: str, hypothesis: str) -> float:
        return checker.entail_probs(premise, [hypothesis])[0]

    prov = NLIFactualityProvider(nli_model=nli_model, claim_splitter=split_claims)

    # wrap score_steps to build the reference from the trajectory context automatically
    base_score = prov.score_steps

    def score_steps(steps, context: str = ""):
        scores = np.zeros(len(steps), np.float32)
        for i, s in enumerate(steps):
            txt = getattr(s, "content", "") or ""
            claims = split_claims(txt)
            if not claims:
                continue
            if reference == "prior-steps":
                ref = " ".join((getattr(p, "content", "") or "") for p in steps[:i])
            elif reference == "gold-answer":
                ref = context  # caller passes traj.correct_answer here
            else:
                ref = context
            if not ref.strip():
                # no reference available -> cannot verify -> abstain (0), not a false hit
                continue
            probs = checker.entail_probs(ref, claims)
            entailed = sum(1 for p in probs if p >= entail_thresh)
            scores[i] = 1.0 - entailed / len(claims)
        return scores

    prov.score_steps = score_steps  # type: ignore
    prov.name = f"nli:{model.split('/')[-1]}:{reference}"
    return prov


# ------------------------------------------------------------------ offline self-test
if __name__ == "__main__":
    # verifies claim splitting works with NO model (the NLI part needs transformers).
    demo = ("The patient has type 2 diabetes. Metformin 500 mg twice daily is indicated; "
            "the HbA1c target is below 7%. I agree with the plan.")
    claims = split_claims(demo)
    print(f"split into {len(claims)} claims:")
    for c in claims:
        print("  -", c)
    print("\nNLI checking requires transformers+torch (run on the GPU box):")
    print("  from common.factuality_nli import build_nli_provider")
    print("  prov = build_nli_provider(reference='prior-steps')")
