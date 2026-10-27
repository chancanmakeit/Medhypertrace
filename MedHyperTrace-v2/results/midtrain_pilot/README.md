# Mid-training pilot v1: text TAPT (round 62) — done: no measurable gain

**Question:** does continued pre-training (task-adaptive, LoRA) of Qwen3-8B on unlabelled multi-agent trajectories improve
MedAgentAudit (MAA) defect-layer attribution after the usual SFT? (Taxonomy: MedAgentAudit only for the evaluation.)

**Corpus** (`hgfm/midtrain/build_corpus.py`; stats `corpus_stats_tapt_pilot_v1.json`): 24.46M Qwen3 tokens, 16,271 chunks
(<= 4,096 tokens, split at step boundaries, task header repeated), 12,874 runs:
ARIA 10.0M (capped; 9,024 runs), MAST-Data 8.0M, medical-aegis anchor normal runs 3.7M (llm_debate, mdagents,
medagents_mc), AFTraj 1.1M, MAScope 0.8M, TraceElephant (SWE-agent) 0.7M, AgentRx tau 0.2M.
* **No MAA data**, so one mid-training run serves every MAA split; 18 anchor runs on the 2 MAA-overlapping questions removed
  (MAA exclusion list v1).
* **framework_family `groupchat` excluded** (Magentic-One, CaptainAgent, AG2 group chat, AFTraj expert team, MAScope AutoGen,
  anchor MAC): MAA's MAC is an AutoGen-GroupChat design, so LQD_mac stays zero-shot at the architecture level.
* Serialisation uses only fields every source has: task, `[s<k>] <agent_role> | <phase_canonical>` + output; environment /
  tool outputs truncated to 2,000 chars (head + tail) for every source; llm outputs never shortened.
* Transfer: private HF dataset `UUUooUUU/mht-midtrain-pilot` (file `tapt_pilot_v1_train.jsonl.gz`, md5 3a3ef54f…).

**TAPT** (`scripts/linux2_run_tapt.sh`): LoRA r 64 / α 128 on all linear layers, lr 1e-4 cosine (3% warm-up), 1 epoch,
4 GPUs × batch 1 × accum 8 (32 chunks / step, ~508 steps), max_length 4,096, sdpa (no packing: flash-attn not installed;
batch 1 means no padding), 0.5% held-out for eval loss. Smoke: 14.7 s/step, 31 GB. Then LoRA merged into the weights
(`Qwen3-8B-tapt_pilot_v1`).

**Evaluation** (`scripts/linux2_midtrain_chain_sft.sh`): the standard MS-Swift graph / text SFT on the merged model, QD and
LQD_mac, seeds 0 and 1; compared with the base-model MS-Swift seed study (`../c6_linux2_lora/seed_study.md`, 3 seeds).

## TAPT run (2026-10-26 19:07–21:11 UTC)
506 optimizer steps, 7,324 s (14.5 s/step), 4 × A6000, no failures; LoRA merged into `Qwen3-8B-tapt_pilot_v1` (16 GB).
Train loss (mean over logged steps): steps 1–50 0.762, 51–150 0.568, 151–300 0.517, 301–506 0.489 (first logged 0.971).
Held-out (0.5% of chunks, 21 eval batches) at the end: loss 0.477, token accuracy 0.867. No held-out loss of the base model
was logged before training, so the drop on held-out text is not measured directly; the first training batches (0.97)
are only an indication.
SFT queue on the merged model ran 21:12–01:16 UTC (`mht_work/midtrain/sft_queue/`), 8 jobs on 4 GPUs, ~2 h each, no failures.

## Result (2026-10-27): no measurable gain from text TAPT
**Taxonomy: MedAgentAudit only** (human instances; macro AUROC over the 10 MAA codes). QD n = 399 (10 codes),
LQD_mac n = 67 (7 scorable codes). Base = MS-Swift seed study of round 60 (seeds 0/1/2); TAPT = same SFT recipe on
`Qwen3-8B-tapt_pilot_v1` (seeds 0/1). Analysis `scripts/linux2_midtrain_eval.py` (Linux #2; paired bootstrap 1000 over
instances; seed ensemble = mean of z-scored instance scores); per-instance scores of all 20 runs
`tapt_pilot_v1_scores.csv.gz`; summary `tapt_pilot_v1_eval.json` / `.out`. Per-run AUROCs recomputed in the sandbox from
the CSV match exactly (`scripts/midtrain_robust_check.py`).

### Per seed and seed means
| split | variant | base s0 / s1 / s2 | base mean ± SD | TAPT s0 / s1 | TAPT mean ± SD |
|---|---|---|---|---|---|
| QD | graph | 0.773 / 0.797 / 0.777 | 0.782 ± 0.013 | 0.767 / 0.791 | 0.779 ± 0.018 |
| QD | text | 0.780 / 0.782 / 0.778 | 0.780 ± 0.002 | 0.790 / 0.792 | 0.791 ± 0.001 |
| LQD_mac | graph | 0.878 / 0.841 / 0.759 | 0.826 ± 0.061 | 0.712 / 0.844 | 0.778 ± 0.093 |
| LQD_mac | text | 0.830 / 0.824 / 0.771 | 0.809 ± 0.032 | 0.704 / 0.724 | 0.714 ± 0.014 |

### TAPT − base, paired over the same instances [95% CI]
| split | variant | same seed s0 | same seed s1 | ensemble TAPT(2) vs base(3) | ensemble TAPT(2) vs base(s0, s1) |
|---|---|---|---|---|---|
| QD | graph | −0.006 [−0.041, +0.024] | −0.006 [−0.038, +0.031] | −0.014 [−0.041, +0.013] (0.791 vs 0.805) | −0.012 [−0.040, +0.017] |
| QD | text | +0.010 [−0.021, +0.044] | +0.010 [−0.020, +0.038] | +0.010 [−0.016, +0.037] (0.797 vs 0.787) | +0.019 [−0.007, +0.049] |
| LQD_mac | graph | −0.166 [−0.269, −0.001] | +0.003 [−0.049, +0.079] | −0.013 [−0.150, +0.096] (0.795 vs 0.808) | −0.059 [−0.172, +0.052] |
| LQD_mac | text | −0.126 [−0.219, +0.086] | −0.100 [−0.196, +0.058] | −0.057 [−0.157, +0.064] (0.743 vs 0.800) | −0.093 [−0.181, +0.065] |

### graph − text under each LM
| split | LM | per seed | mean ± SD | seed ensemble [95% CI] |
|---|---|---|---|---|
| QD | base | −0.007 / +0.015 / −0.002 | +0.002 ± 0.012 | +0.018 [−0.007, +0.043] |
| QD | TAPT | −0.023 / −0.000 | −0.012 ± 0.016 | −0.007 [−0.031, +0.020] |
| LQD_mac | base | +0.048 / +0.017 / −0.012 | +0.018 ± 0.030 | +0.008 [−0.022, +0.039] |
| LQD_mac | TAPT | +0.008 / +0.119 | +0.064 ± 0.078 | +0.052 [−0.074, +0.155] |

### SFT train loss (final, 1 epoch)
| split | variant | base s0 / s1 / s2 | TAPT s0 / s1 |
|---|---|---|---|
| QD | graph | 0.349 / 0.332 / 0.347 | 0.300 / 0.302 |
| QD | text | 0.364 / 0.367 / 0.379 | 0.307 / 0.305 |
| LQD_mac | graph | 0.341 / 0.356 / 0.345 | 0.306 / 0.306 |
| LQD_mac | text | 0.374 / 0.361 / 0.377 | 0.312 / 0.313 |

### LQD_mac is dominated by two single-positive codes
Per-code AUROC, text variant (n, positives; base s0 / s1 / s2 | TAPT s0 / s1):

| code | n (pos) | base | TAPT |
|---|---|---|---|
| 1.1.1 | 9 (3) | 1.00 / 1.00 / 1.00 | 0.97 / 1.00 |
| 1.2.1 | 7 (1) | 0.83 / 0.83 / 0.92 | 0.50 / 0.83 |
| 2.1.2 | 5 (1) | 1.00 / 1.00 / 0.50 | 0.25 / 0.25 |
| 3.1.1 | 11 (4) | 0.71 / 0.79 / 0.71 | 0.86 / 0.75 |
| 3.1.2 | 6 (2) | 0.94 / 1.00 / 1.00 | 1.00 / 1.00 |
| 3.1.3 | 15 (8) | 0.79 / 0.71 / 0.77 | 0.85 / 0.83 |
| 3.2.1 | 10 (2) | 0.53 / 0.44 / 0.50 | 0.50 / 0.41 |
(2.2.1 and 2.2.2 have no positive on LQD_mac and are not scored.) With one positive, a code's AUROC is the rank of a
single instance, so one instance moves the 7-code macro by up to ~0.14. The TAPT text drop on LQD_mac comes almost
entirely from 2.1.2 (one instance ranked lower by both TAPT seeds) and from 1.2.1 in seed 0.

**Robustness metric** (`tapt_pilot_v1_robust.json`): macro over codes with ≥ 2 positives and ≥ 2 negatives (QD: all 10
codes, identical to the main metric; LQD_mac: 5 codes, n = 51):
| split | variant | base mean ± SD (3 seeds) | TAPT mean ± SD (2 seeds) | ensemble TAPT(2) vs base(3) [95% CI] |
|---|---|---|---|---|
| LQD_mac | graph | 0.821 ± 0.009 (0.829 / 0.811 / 0.821) | 0.806 ± 0.047 (0.772 / 0.839) | +0.007 [−0.106, +0.110] (0.821 vs 0.814) |
| LQD_mac | text | 0.793 ± 0.005 (0.796 / 0.787 / 0.796) | 0.816 ± 0.027 (0.836 / 0.797) | +0.020 [−0.049, +0.097] (0.823 vs 0.804) |

graph − text on this metric (seed ensembles): base +0.011 [−0.036, +0.046], TAPT −0.002 [−0.105, +0.074].
On the robust metric the TAPT text "drop" becomes a non-significant +0.02, and the base model's cross-seed SD on
LQD_mac shrinks from 0.03–0.06 to 0.005–0.009: most of the LQD_mac seed variance in the round-60 seed study was the
rank of single positive instances.

## Reading
1. **QD (MAS seen in training): no effect.** Same-seed differences are −0.006 (graph) and +0.010 (text) in both seeds, every
   CI contains 0. The seed-ensemble CIs bound the TAPT effect on QD to below ~+0.04 (text) and ~+0.01 (graph).
2. **LQD_mac (cross-MAS zero-shot): an apparent drop that this fold cannot resolve.** The headline numbers fall (text 0.714
   vs 0.809), but the drop sits in two codes with one positive each; on the codes with ≥ 2 positives and negatives there
   is no drop (table above). Only one same-seed CI excludes 0 (graph s0, upper bound −0.001), and graph s1 is +0.003. This
   also means part of the cross-seed variance of LQD_mac in the round-60 seed study is single-instance rank noise.
   LQD_mac alone cannot detect effects of a few AUROC points; a cross-MAS claim needs the pooled 6-fold LQD.
3. **TAPT made the SFT data easier to fit, not easier to rank.** SFT train loss is lower in every TAPT run (0.30–0.31 vs
   0.33–0.38), consistent with the held-out LM loss falling during TAPT, but this does not carry over to AUROC on human
   labels. Text-only continued pre-training adapts the LM to trajectory text; it does not supply an attribution signal.
4. **graph − text did not grow** (QD −0.012 ± 0.016 vs +0.002 ± 0.012 on base). Expected: text TAPT never trains the graph
   tokens. The open question from C6 (the LLM ignores graph tokens) is untouched by this pilot.
5. **Decision per the round-60 rule** ("scale only on a measurable gain"): **do not scale text-only mid-training**. The
   remaining hypothesis is structure-aware mid-training that gives the graph tokens their own training signal
   (graph–text alignment / phase and source prediction from the hypergraph), to be decided by the user.

**Not done in this pilot:** base-model held-out LM loss (only TAPT's own held-out loss); the "source identifiability" check
promised in round 61 (no labels in text TAPT, so no label–source shortcut to measure; it goes with the structure-aware
version); LQD folds other than mac.
