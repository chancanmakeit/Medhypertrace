# Interaction CPT (pre-registration v1) — results (round 95, 2026-11-07)

**Pre-registration:** `docs/design/InteractionCPT_prereg_v1.md` (amendments A1–A4). All runs finished 2026-11-06 02:23 UTC.
- **Primary statistic (A4):** H1 = interaction-CPT − LM-CPT on the medical branching set:
  - prefix features + bidirectional aggregator head (`agg`), leave-one-framework-out, controlled (residual) per-parent AUROC;
  - pooled over frameworks, question-clustered bootstrap.
- **Raw outputs on Linux #2 `mht_work/icpt/`:**
  - medical: `med_compare_{prefix,query}.{out,json}`, `med_{prefix,query}_{base,lm,icpt}.json`;
  - public data: `le_{prefix,query}/`, `le_analysis.{out,json}` (`scripts/icpt_le_analyze.py`), `stageA_{prefix,query}{.log,/}`;
  - diagnostics: `diag/`.

## Verdict
**H1 is NULL.** Following the pre-registered rule, this interaction-objective recipe stops, and its corpus is not expanded.

| H1: icpt − lm, controlled AUROC (95% CI, clustered by question) | n parents / questions | raw | matched grid median (same sign) | rule |
|---|---|---|---|---|
| **prefix + agg (primary)**: **+0.002 [−0.010, +0.014]** | 237 / 207 | −0.017 | −0.017 (0/6) | **NULL** |
| seen frameworks | 98 / 90 | | | −0.005 [−0.016, +0.008] NULL |
| unseen frameworks | 139 / 132 | | | +0.006 [−0.011, +0.024] NULL |
| prefix + linear | | | | −0.005 [−0.023, +0.013] NULL |
| prefix + MLP | | | | −0.044 [−0.069, −0.020] NULL (icpt worse) |
| query interface + agg (secondary) | | | | +0.014 [−0.017, +0.045] UNDETERMINED (unseen +0.053 [+0.016, +0.093], but grid 0/6 same sign) |

**The NULL is robust across read-out heads:**
- No head or interface gives icpt − lm a positive interval together with a consistent matched grid.
- Under the MLP head, icpt is significantly worse.

## Secondary comparisons (reported only; they do not change the decision)
Medical set, prefix + agg, controlled:

| comparison | pooled | seen | unseen |
|---|---|---|---|
| H2 icpt − base | +0.007 [−0.011, +0.022] NULL | +0.020 [+0.001, +0.039] HOLDS (grid 5/6) | −0.003 NULL |
| H3 lm − base | +0.005 [−0.014, +0.023] NULL | +0.024 [+0.008, +0.041] HOLDS (grid 6/6) | −0.009 NULL |

- **Only "seen frameworks" shows a small gain (~+0.02), and it is the same for both CPT arms.** On seen frameworks the CPT corpora contain the same frameworks and the same backbone on different questions (prereg §7), so this reads as in-distribution adaptation, not an effect of the interaction objective.
- Under the MLP head, lm − base pooled +0.046 [+0.012, +0.079] HOLDS. The base MLP head is the weakest base read-out (controlled 0.532 vs linear 0.565 / agg 0.569), so this mostly reflects the MLP head's instability on base features.

**Absolute levels (mean over parents, raw / controlled):**

| arm | prefix + agg | prefix + linear |
|---|---|---|
| base | 0.676 / 0.569 | 0.735 / 0.565 |
| lm | 0.715 / 0.573 | 0.738 / 0.573 |
| icpt | 0.698 / 0.575 | 0.719 / 0.569 |

- Longest-step baseline 0.680 / 0.441; earliest step 0.641 / 0.500.
- **Without length / position control, the learned heads are at or just above the longest-step baseline. After control, all three arms sit at ~0.57.**

### H4 — public data (WW + TEgc, controlled label-efficiency area, n ∈ {100, 300, 1000} × 5 draws, jac0.7 clusters, 356 traj / 170 clusters)
| interface / head | icpt − lm | icpt − base | lm − base |
|---|---|---|---|
| prefix / agg (main) | −0.017 [−0.028, −0.007] | +0.000 [−0.014, +0.015] | +0.018 [+0.004, +0.032] |
| prefix / linear | −0.011 [−0.023, +0.001] | +0.003 | +0.014 [−0.005, +0.032] |
| query / agg | +0.008 [−0.009, +0.024] | −0.021 [−0.041, −0.000] | −0.029 [−0.047, −0.008] |

- Full-label stage A, prefix + agg, pooled WW + TEgc controlled rank-AUROC: base 0.582, lm 0.564, icpt 0.581. TT_test: 0.914 / 0.928 / 0.924.
- **On the main interface, interaction CPT is not better than LM CPT on public data either (slightly worse).**
- **The query interface gets worse after either kind of CPT.**

## Diagnostics
**Loss diagnostic (base vs tapt_clean, 240 eval parents):**
- target content ΔNLL: tapt format −0.08 [−0.18, +0.02]; OAT format +0.19 [+0.14, +0.25];
- the receiver chat-format column is dominated by template-boundary surprisal spikes and is not comparable (see RUN_v0.93, `analysis/icpt_loss_diag/recv_check.py`).

**Interface diagnostic:** see A4. Note the aggregator's weakness on WW out-of-distribution.

## Deviations from the pre-registration
1. **LM arm:** stopped by the user at step 55 (round 88), then retrained from scratch on GPUs 2,3 after the icpt arm (round 92). Same corpus, recipe and seed; checkpoints every 100 steps; 791 steps for both runs.
2. **icpt arm steps:** 1,075, vs 791 for lm. Effective target tokens are ~24M (icpt) vs ~40M (lm).
3. **Training seeds:** one per arm (§7).
4. **M-new endpoint:** duckcoding, differs from the evaluation parents' endpoint (A4).
5. **A1 sensitivity analysis** (judgment labels) is not yet computed.

## Interpretation (beyond the pre-registered rule)
Stage 0 (LM CPT) and this experiment agree:
- On both public and medical failure-attribution benchmarks, continued pretraining of Qwen3-8B, plain or with interaction objectives, does not improve frozen-feature attribution once step length and position are controlled.
- The only positive signals are small in-distribution gains on seen frameworks. Those are shared by both arms, so they are not specific to modelling interactions.
