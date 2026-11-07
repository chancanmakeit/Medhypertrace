# Line 2: post-training with counterfactual attribution labels — pre-registration v1 (round 96, 2026-11-07, before any result of this line)

**Background:** mid-training (stage 0, interaction-CPT) gives no gain after length / position control. The only stable positive signal so far comes from supervised labels: in E4, BEFT trained on TracerTraj reached controlled 0.63–0.64 on WW / TEgc.

Line 2 asks: if the backbone is fine-tuned directly (LoRA, not only biases) with counterfactual / branch labels, does the attribution ability, after length / position control, clearly exceed "frozen features + trained head"? This is the same family of routes as AgenTracer / AEGIS (post-training), but with our control-based evaluation.

## 1. Arms
All share: Qwen3-8B; inputs serialised as OAT (same as E4 / stage 0); step representation = mean of the step's last-layer tokens (prefix, causal); head = LayerNorm + Linear.

| Code | Training | Initialisation | Labels |
|---|---|---|---|
| **F-LOFO** (existing) | frozen features + agg head, leave-one-framework-out | base | medical branch labels (A1) |
| **F-TT** | frozen features + linear head, trained on TracerTraj train | base | TT train |
| **P-TT** | LoRA r16 / α32 / all-linear, dropout 0.05, + head; lr 1e-4 (head 1e-3), 2 epochs, effective batch 32 trajectories, training trajectories ≤ 16,384 tokens (same as BEFT); best by tt_val rank-AUROC (twice per epoch) | base | TT train (2,608) |
| **P-MED** | same LoRA recipe; leave-one-framework-out, 7 folds (mdagents, llm_debate, medagents_mc, mac_groupchat, agentverse, triage_agent, mam), each fold trained on the evaluable parents of the other 6 frameworks; loss = med_eval listwise (mean over positives of −log p); ≤ 3 epochs; early stopping on a question-grouped 10% hold-out of the training frameworks (mean AUROC, twice per epoch) | base | medical branch labels (A1) |
| **P-MED/TT** | same as P-MED | P-TT's merged weights + head | TT, then medical |

- Scoring: training-time limit 16k; at scoring time native ≤ 32k and YaRN ×4 for ≤ 131k (same as E4).
- P-TT scores WW / TEgc / TT_test and all medical eval parents (zero-shot).
- P-MED scores only the held-out framework of each fold.
- One training seed (compute limit, stated).

## 2. Hypotheses and rules (same statistics as interaction-CPT §4: per-parent / per-trajectory AUROC, controlled = OLS on log step length + relative position with fixed effects, matched grid of 6 points, question-clustered bootstrap)
| No. | Comparison | Evaluation | Status |
|---|---|---|---|
| **HP1** | P-MED − F-LOFO | medical branching set, 237 parents, controlled, pooled | **primary** |
| HP2 | P-TT − F-TT | public WW + TEgc (356 trajectories, jac0.7 clusters), controlled rank-AUROC; plus zero-shot on the medical set | secondary |
| HP3 | P-MED/TT − P-MED | medical set | secondary (does TT pretraining transfer) |
| HP4 | P-MED and P-TT minus the longest-step baseline | raw and controlled | reported |

- Rules: HOLDS = CI lower > 0 and ≥ 4 / 6 grid points with the same sign; NULL = CI upper < +0.04; otherwise UNDETERMINED.
- **The rule for HP1 decides whether line 2 is worth expanding:** HOLDS → request quotes for more medical branch labels (corpus pool, paid) and run in-domain post-training at scale; NULL → stop this route.
- **Absolute bar (reported, not a rule):** whether the controlled AUROC of P-MED / P-TT exceeds 0.60, i.e. a clear step beyond the current ~0.57.

## 3. Bridge to line 3 (secondary, compute permitting)
- P-MED initialised from the merged lm / icpt / (if trained) ocpt models, compared with P-MED (base). This tests "does mid-training help post-training".
- E4's BEFT version was NULL; this is the LoRA version.

## 4. Paid extension (not executed in this round)
- Ask medical-aegis to quote protocol-v3 branch labels on the corpus pool for **failed** runs of the 4 seen frameworks (corpus questions disjoint from eval). Purpose: train P-MED on disjoint questions without cross-fitting.
- Generation only after the user approves. It does not block §1–§2.

## 5. Risks
- **Small P-MED training set:** each fold trains on ~200 parents, so LoRA may overfit. Mitigated by early stopping, ≤ 3 epochs and r16; P-MED/TT provides a warmer starting point.
- **The labels themselves are correlated with step length:** a learned model can also learn the length shortcut. The controlled metric and the matched grid are the main readouts, and raw values are reported alongside.
- **Positive noise:** about 11–17% of positives are consistent with noise (permutation FDR); this affects all arms equally.

## 6. Products
- Code: `hgfm/posttrain/` (LoRA step scoring, LOFO driver, external-score evaluation).
- Results: `results/posttrain/README.md`.
