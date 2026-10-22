# C6 on Linux #2: LoRA fine-tuning of Qwen3-8B with graph tokens (MedAgentAudit, human 400)

**Taxonomy: MedAgentAudit only.** Every number here is on the MedAgentAudit (MAA) human-annotated instances
(10 MAA failure codes, human majority labels). Nothing is pooled with MAST-based results (HANDOFF §0.33).

Run: `scripts/linux2_run_c6.sh` (rounds 47–54, 2026-10-22 09:30–18:50 UTC, 3× RTX A6000, plain PyTorch `hgfm/llm/train.py`).
7 splits (6 LQD folds = leave-one-MAS-out with no shared questions, plus QD = question-disjoint) × {graph, text} LoRA
fine-tuning, plus the untrained model (zeroshot) on the text prompts. Scoring: logit(yes) − logit(no), instance score =
max over the instance's prompts, macro AUROC over the 10 codes; 399 of the 400 human instances are scorable.

## Files
| file | content |
|---|---|
| `c6_scores.csv` | one row per human instance (399): code, human label, auditor label, LQD fold, scores for {lqd,qd}×{graph,text,zeroshot}, and the graph-token ablation scores `{lqd,qd}_abl_<mode>` |
| `c6_summary.json` | per-file eval summaries (n, macro AUROC, CI, per-code AUROC), ablation summaries per fold + pooled LQD, paired comparisons (`compare_c6`), training stats (seconds, steps, tok/s, peak memory), queue status |
| `compare_gt_6fold.out` | round-54 graph-vs-text output of the earlier comparison script |
Per-file eval JSONs, checkpoints and logs stay on Linux #2 under `/data1/ekyang/cgh/CODE/mht_work/` (no git there); the
CSV holds every per-instance score, so all pooled numbers below can be recomputed from it (checked in the sandbox).

## Main results (macro AUROC, n = 399)
| split | graph | text | zeroshot |
|---|---|---|---|
| LQD (6 folds pooled) | 0.701 [0.650, 0.758] | 0.716 [0.665, 0.770] | 0.611 [0.552, 0.667] |
| QD | 0.780 [0.734, 0.830] | 0.768 [0.722, 0.816] | 0.611 [0.550, 0.668] |

Paired bootstrap (1000, same instances) of the macro-AUROC difference:
| split | graph − text | graph − zeroshot | text − zeroshot |
|---|---|---|---|
| LQD pooled | −0.014 [−0.047, +0.020] | +0.091 [+0.023, +0.155] | +0.105 [+0.042, +0.161] |
| QD | +0.011 [−0.021, +0.044] | +0.168 [+0.100, +0.231] | +0.157 [+0.090, +0.223] |

Per LQD fold (graph / text / zeroshot): colacare 0.778 / 0.816 / 0.633 (n=92); healthcareagent 0.599 / 0.638 / **0.739**
(n=70); mac 0.790 / 0.821 / 0.647 (n=67); medagent 0.735 / 0.769 / 0.619 (n=107); reconcile 0.663 / 0.629 / 0.537
(n=49); mdagents n=14 (no code has both labels, no per-fold AUROC; counted in the pooled numbers).

## Graph-token ablation (`hgfm/llm/graph_ablation.py`, round 54)
Same graph checkpoint, same prompts; only the graph vectors change. `none` reproduces eval.py exactly (max |Δ| = 0 on
all 7 splits). Δ = mode − none, paired bootstrap CI; |Δscore| relative to the SD of the unperturbed scores; ρ = Spearman
with the unperturbed scores.
| mode | LQD pooled Δ AUROC | LQD |Δscore| / ρ | QD Δ AUROC | QD |Δscore| / ρ |
|---|---|---|---|---|
| zero_state (HGFM state = 0, type flag kept) | −0.016 [−0.055, +0.021] | 0.43 sd / 0.850 | −0.005 [−0.023, +0.012] | 0.23 sd / 0.960 |
| mean_state (eval-set mean per kind) | +0.027 [−0.005, +0.059] | 0.21 sd / 0.936 | −0.009 [−0.031, +0.012] | 0.21 sd / 0.952 |
| zero_emb (projector output = 0) | +0.010 [−0.020, +0.040] | 0.27 sd / 0.913 | −0.016 [−0.039, +0.005] | 0.26 sd / 0.942 |
| shuffle_0 (vectors of another run) | +0.004 [−0.034, +0.040] | 0.27 sd / 0.907 | −0.024 [−0.051, +0.000] | 0.22 sd / 0.930 |
| shuffle_1 | +0.018 [−0.016, +0.051] | 0.25 sd / 0.924 | −0.009 [−0.035, +0.015] | 0.20 sd / 0.944 |
| shuffle_2 | +0.004 [−0.030, +0.033] | 0.24 sd / 0.928 | −0.007 [−0.035, +0.022] | 0.21 sd / 0.937 |

## Reading
1. **Fine-tuning helps a lot; graph tokens do not.** Both fine-tuned variants beat the untrained model by 0.09–0.17
   (CIs exclude 0). Graph vs text: −0.014 on LQD and +0.011 on QD, both CIs contain 0.
2. **The model reacts to the graph tokens, but not in a way that carries attribution signal across MAS.** Perturbing
   them moves scores by 0.2–0.4 SD (ranking correlation with the unperturbed scores 0.85–0.96), yet LQD AUROC does not drop under any perturbation
   (all CIs contain 0; mean_state is even +0.027). On QD (MAS seen in training) every perturbation lowers AUROC by
   0.005–0.024, shuffle_0's CI reaching 0.000: at most a small in-distribution contribution. This matches phase 1
   (`results/phase1_maa/`): structure did not transfer zero-shot across MAS with the encoder alone either.
3. The earlier interim reading (round 51, 3 folds: graph worse than text, CI excluding 0) did not hold on 6 folds.
4. healthcareagent is the one fold where both fine-tuned variants are below zeroshot (0.599 / 0.638 vs 0.739; wide CI).

## Caveats
- **The text baseline is not structure-free.** `build_sft.py` picks each prompt's candidate steps with the fold's
  encoder ranking (and the same candidates for graph and text, by design). So graph − text measures only what the
  graph *tokens* add on top of encoder-selected context, not the value of structure as a whole. For the same reason the
  zeroshot prompts depend on the split: 48/399 instances have different zeroshot scores under LQD vs QD (the pooled
  macro AUROC happens to be 0.611 in both).
- bf16 logits quantise scores to steps of 0.125 (63 distinct values for LQD graph), so there are many ties; AUROC counts
  ties as 0.5.
- No graph–text alignment stage was trained before SFT; the projector is learned only from the yes/no SFT signal.
  The graph encoder was trained on half of the training runs (round 45 leakage fix).
- Training: graph 6,432 s and text 6,284 s per fold on average; 297–353 optimizer steps; 992–1,040 tok/s;
  peak allocated 20.0 GB, peak reserved 26.7 GB.
