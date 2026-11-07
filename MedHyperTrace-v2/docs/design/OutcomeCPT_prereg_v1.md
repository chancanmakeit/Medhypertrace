# Line 3: outcome-aware continued pretraining — pre-registration v1 (round 96, 2026-11-07, before any result of this line)

**Background:** stage 0 (LM-CPT) and the interaction-CPT experiment (`results/icpt/README.md`) are both NULL after length / position control. Line 3 continues mid-training, but must first answer **why it would be different this time**.

**Diagnosis:** none of the earlier objectives ever showed the model a run's **outcome**:
- next-token prediction, receiver-conditioned response and evidence correspondence all learn "what comes next / what was read";
- failure attribution is about "which step changes the outcome".

The medical corpus runs (medical-aegis corpus_v1, 4 frameworks × 1,449 questions) carry a free outcome label `labels.is_correct` (correct rate about 43%). This line tests whether outcome information can be absorbed by mid-training and turned into attribution ability, with no attribution labels at all.

**Order of steps:** gate (frozen features only, no training) → decide by the rule below whether to train → train and evaluate.

## 1. Gate G (zero training; whether to launch §2 depends only on this rule)
**Question:** in base Qwen3-8B frozen features, is the "outcome information" already aligned with branch attribution?

- **Outcome probe:** prefix features of base on the corpus runs (identical to `e4_features`, the A4 primary interface's features). On every LLM step, predict the run's final `is_correct`.
  - Model: LayerNorm + Linear logistic; BCE, each run weighted equally; AdamW lr 1e-3, wd 1e-2, ≤ 20 epochs.
  - Early stopping: on a question-grouped 10% hold-out (step-level AUROC). Seeds 0 / 1 / 2, scores averaged.
  - Training data: the 4 frameworks' corpus runs only. The corpus question pool is disjoint from the eval pool (medical-aegis grouping); no attribution label is used.
- **Attribution score:**
  - On every LLM step t of an eval parent: drop(t) = v(t_prev) − v(t), where v = the probe's predicted probability of being correct;
  - for the first LLM step, v(t_prev) = the mean v of first LLM steps in the training set;
  - a larger drop means the step is more to blame.
- **Evaluation:** identical to the interaction-CPT §4.1 (`hgfm.icpt.med_eval`):
  - the 237 evaluable parents (A1 positives, last-call-only points removed);
  - per-parent AUROC, raw / controlled (OLS on log step length + relative position with parent fixed effects, fitted per framework) / 6-point matched grid;
  - pooled mean, question-clustered bootstrap (1,000 draws).
- **Gate decision (primary = controlled, pooled):**
  - **GO:** controlled AUROC CI lower bound > 0.50, point estimate ≥ 0.53, and ≥ 4 / 6 matched-grid points > 0.50;
  - **NO-GO:** CI upper bound < 0.53;
  - otherwise **UNCLEAR**: no automatic launch; report to the user.
- **Validity check:** the probe's AUROC for predicting `is_correct` at the last LLM step on the corpus hold-out must be ≥ 0.60. Otherwise the probe failed, and the gate is reported as "uninformative" rather than NO-GO.
- **Secondary (reported only):**
  - the score −v(t);
  - seen / unseen framework strata;
  - comparison with the trivial baselines and with the LOFO-supervised agg head (base controlled 0.569);
  - the same probe on lm / icpt arm features (only if corpus features for those arms exist; not needed).

## 2. Outcome-aware CPT (only after GO, or if the user explicitly asks)
- **Arm O (ocpt):** exactly the same corpus, recipe and seed as the existing LM-CPT arm (`results/icpt`). The only change: in the rendering of medical runtime runs (M-new + M-anchor), after each LLM step block add one line `[OUTCOME] correct` / `[OUTCOME] incorrect`, the run's final correctness, written into the text and included in the next-token loss.
  - Anchor runs use `verification.regex_extracted` compared with the gold answer; the public part P is unchanged (no reliable outcomes).
  - The extra tokens are about 0.3% of processed tokens; the ±5% matching to the lm arm is kept.
- **Control:** the existing lm arm (same corpus without outcome lines; 791 steps). This makes it a single-variable ablation, so the existing lm features and evaluation are reused directly.
- **H-O (primary):** ocpt − lm on the medical branching set, prefix + agg, LOFO, controlled, pooled; same statistics and rules as interaction-CPT §4.3:
  - HOLDS: CI lower > 0 and ≥ 4 / 6 grid points with the same sign;
  - NULL: CI upper < +0.04;
  - otherwise UNDETERMINED.
- **Secondary:**
  - ocpt − base;
  - re-running gate G on ocpt features: same method, but the probe and the scoring must use ocpt's own features (corpus features re-extracted). The test is whether the drop score becomes stronger, i.e. whether outcome-awareness was learned into the representation;
  - public WW + TEgc label efficiency, as in interaction-CPT §4.2.
- **Expected leakage risk:** the outcome lines exist only in corpus runs; eval parents never contain them, and at eval time features are extracted from runs without outcome lines. The training questions are disjoint from the eval questions.

## 3. Known risks
- **Weak outcome signal:** MCQ correctness is largely decided by the final answer, so a probe may only learn "is the last step correct" from the last step. Drops at middle steps then become mostly noise. The gate is designed to catch exactly this.
- **Single training seed;** the deviations of the interaction-CPT experiment (§7) carry over.

## 4. Products
- Code: `hgfm/outcome/` (corpus_to_ww, value_gate; ocpt rendering in build_icpt).
- Results: `results/outcome/README.md`.

## Amendments
- **A1 (round 97, 2026-11-07 16:15 UTC; written before any G0 features were extracted and before gate G's results):** add **gate G0 (model × layer)** ahead of gate G. G0 runs on Linux #2 GPUs 0,1 ahead of line 2 (approved by the user).
  - **Motivation (user's question, round 97):** all mid-training so far was done on `Qwen/Qwen3-8B`, the post-trained, aligned hybrid thinking model, not `Qwen3-8B-Base`. Features were always taken from the last layer only. Both confounds were never tested. If either matters, outcome-aware CPT on the old configuration would repeat the same pitfall.
  - **Configurations:** model ∈ {Qwen3-8B (post-trained, current), Qwen3-8B-Base} × layer ∈ {9, 18, 27, 36}.
    - Layer l < 36 = output of decoder layer l (residual stream, before the final norm).
    - 36 = last hidden state after the final norm (the current setting).
    - Step representation is unchanged (mean of the step's tokens in the OAT serialisation); no training of the language model.
  - **Read-outs (frozen, existing recipes unchanged):**
    1. **Medical:** `med_eval score` (LOFO, linear / agg heads), 237 parents, controlled AUROC.
    2. **Public:** `e4_probe` stage A full labels (TT train → WW + TEgc, linear / agg heads), controlled rank-AUROC, 356 trajectories.
  - **Reference:** (post-trained, L36), re-extracted in the same pass as a reproducibility check against the existing feats_base / featsmed_base.
  - **Rule (primary = agg head):**
    - Each configuration is compared with the reference by per-parent / per-trajectory paired differences, question-clustered bootstrap (medical: question_id; public: jac0.7).
    - **Switch:** a configuration is "better" if its medical controlled difference has CI lower > 0 and point ≥ +0.02, and its public controlled difference is not significantly negative (CI upper ≥ 0). Among the "better" ones, take the largest medical point estimate.
      - Gate G and the training of §2 then use that configuration. If the winner is Base, the ocpt and lm control arms are both retrained from Base (on Linux #1 or Linux #2, decided with the user).
    - **No switch:** no configuration qualifies. The configuration stays as is, and this confound is recorded as ruled out at the frozen-feature level.
    - Linear head results are reported only.
  - Base CPT can only test "is it Base that matters" if it is done as a matched pair (Base-lm vs Base-ocpt, and Base-lm vs Qwen3-8B-lm). That will be a separate amendment after G0.
