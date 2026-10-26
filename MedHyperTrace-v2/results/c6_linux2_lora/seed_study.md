# Seed study: graph vs text, MS-Swift, 3 seeds (round 60)

**Taxonomy: MedAgentAudit only** (human instances; macro AUROC over the 10 MAA codes). QD n = 399, LQD_mac n = 67.

Why: on LQD_mac the sign of graph − text flipped between two single training runs (MS-Swift +0.048, train.py −0.031;
`swift_validation.md`), so single-run C6 conclusions were not reliable.

Setup: `scripts/linux2_run_sft_swift.sh` with `SEEDS`, `--seed` = `--data_seed` = s ∈ {0, 1, 2}; otherwise identical to
`swift_validation.md` (Qwen3-8B, LoRA r 8 on q,k,v, bs 4 × 4, 1 epoch). Ran 2026-10-23 02:03–10:01 UTC on GPUs 0/2/3 of
Linux #2, 10 jobs + the earlier LQD_mac seed 0, no failures. Analysis: `scripts/linux2_seed_study.py`
(paired bootstrap 1000 over the same instances). Per-instance scores: `seed_scores.csv`; summary: `seed_study.json`.
The per-seed AUROCs were recomputed in the sandbox from the CSV and match.

## Per seed
| split | seed | graph | text | graph − text [95% CI] |
|---|---|---|---|---|
| QD | 0 | 0.773 | 0.780 | −0.007 [−0.039, +0.026] |
| QD | 1 | 0.797 | 0.782 | +0.015 [−0.019, +0.046] |
| QD | 2 | 0.777 | 0.778 | −0.002 [−0.027, +0.022] |
| LQD_mac | 0 | 0.878 | 0.830 | +0.048 [−0.005, +0.138] |
| LQD_mac | 1 | 0.841 | 0.824 | +0.017 [−0.031, +0.073] |
| LQD_mac | 2 | 0.759 | 0.771 | −0.012 [−0.063, +0.058] |

## Across seeds
| split | graph mean ± SD | text mean ± SD | graph − text mean ± SD | 3-seed ensemble graph − text [95% CI] | train.py single run graph − text |
|---|---|---|---|---|---|
| QD | 0.782 ± 0.013 | 0.780 ± 0.002 | +0.002 ± 0.012 | +0.018 [−0.007, +0.043] (0.805 vs 0.787) | +0.011 [−0.021, +0.044] |
| LQD_mac | 0.826 ± 0.061 | 0.809 ± 0.032 | +0.018 ± 0.030 | +0.008 [−0.022, +0.039] (0.808 vs 0.800) | −0.031 [−0.088, +0.012] |
Ensemble = mean over seeds of z-scored instance scores. Cross-seed Spearman of instance scores: QD graph 0.79–0.87,
text 0.85–0.91; LQD_mac graph 0.88–0.93, text 0.90–0.93.

## Reading
1. **No detectable effect of graph tokens, now with seeds.** Every per-seed CI and both ensemble CIs contain 0. The
   mean difference (+0.002 on QD, +0.018 on LQD_mac) is no larger than its seed-to-seed SD (0.012, 0.030).
2. **Graph tokens add training variance.** The graph variant's AUROC varies more across seeds than text's (QD SD 0.013 vs
   0.002; LQD_mac 0.061 vs 0.032), and its instance rankings agree less across seeds. With the projector trained only by
   the yes/no SFT signal, the extra trainable input mostly adds noise.
3. **Bound on the effect.** On QD (all 399 instances, MAS seen in training), the 3-seed ensemble rules out a graph-token
   gain above ~+0.04 AUROC under this recipe. LQD (cross-MAS zero-shot) was only re-run on one fold, so the
   cross-MAS bound is wider; the C6 single-run pooled LQD result (−0.014 [−0.047, +0.020]) is consistent.
4. The engines agree on average: MS-Swift 3-seed means on QD (0.782 / 0.780) are within 0.02 of the train.py run
   (0.780 / 0.768).
5. Combined with the round-54 ablation (perturbing graph tokens does not lower LQD AUROC), the conclusion is: in this
   recipe the LLM does not use the HGFM graph tokens for attribution. Changing that needs a different training signal
   for the graph tokens (graph–text alignment / structure-aware mid-training), not more seeds of the same SFT.
