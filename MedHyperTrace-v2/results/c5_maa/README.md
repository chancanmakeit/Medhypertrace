# C5 self-supervised pretraining on MedAgentAudit (rounds 41–42)

MedAgentAudit taxonomy only. Code `hgfm/ssl_v02.py`, checks `analysis/c5_summary.py`. LQD (leave-one-MAS-out and
question-disjoint) 6 folds, 3 seeds (0,1,2), 5 pretraining epochs, 5 fine-tuning epochs; 399 human instances.

## Fine-tuned (pretrain → same supervised training as train_v02), human macro AUROC

| setting | seed 0 | seed 1 | seed 2 | seed-avg score | diff vs scratch [95% CI, paired bootstrap] |
|---|---|---|---|---|---|
| scratch | 0.640 | 0.671 | 0.637 | 0.655 [0.599, 0.711] | — |
| strict | 0.636 | 0.624 | 0.657 | 0.643 [0.587, 0.700] | −0.011 [−0.041, +0.018] |
| shuffle (read tails randomised) | 0.625 | 0.672 | 0.671 | 0.662 [0.608, 0.719] | +0.008 [−0.020, +0.038] |
| trans (transductive, report separately) | 0.654 | 0.645 | 0.681 | 0.672 [0.617, 0.728] | +0.017 [−0.012, +0.050] |

Per seed the sign of every difference flips (strict: −0.004 / −0.048 / +0.020). Seed spread of scratch alone (0.034)
is larger than any effect. **No evidence that C5 pretraining helps zero-shot transfer**, strict or transductive.

## Label-free scores (pretrained encoder only, no labels; each step masked alone), seed-averaged

| score | strict | shuffle | trans |
|---|---|---|---|
| answer-flow surprise | **0.606 [0.536, 0.662]** | 0.594 [0.532, 0.647] | 0.541 [0.481, 0.594] |
| reconstruction error | 0.478 | 0.452 | 0.521 |

Untrained scalar baselines on the same instances: answer≠majority 0.471, answer≠final 0.511, disagree flag 0.503,
position 0.485, random 0.472. Answer-flow surprise is above these, but the read-edge-shuffled control is as good
(0.594), so the signal does not come from the read structure (event / agent hyperedges are intact in that control).
Transductive is lower (0.541); unexplained.

## Consistency with phase 1
Seed-0 scratch is the phase-1 v0.2 `full` code path. Per-fold outcome AUROC matches phase 1 exactly on mdagents
and reconcile and differs by 0.002–0.009 on three folds; pooled human 0.640 vs 0.645. Re-runs inside this sandbox
are bit-identical (pilot = full run), so the drift is environmental (torch build / threads, not recorded in phase 1);
it is an order of magnitude below the seed spread. Compare settings only within this run.

## Fill objective
Only ~9,900 usable targets in MAA (72% colacare review), absent from most folds' held-out MAS; the pretext could not
be evaluated on held-out MAS (n_fill_test = 0 for most folds). Its value depends on medical-aegis data with logged sources.
