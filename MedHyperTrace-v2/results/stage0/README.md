# Stage 0 results (rounds 79–81, 2026-11-02/03)

Pre-registration: `docs/design/Stage0_prereg_v1.md` (commit 30a4862; amendment 9df9dc0; appendix A1 3fd6fdd), written before
any Stage-0 result. Analysis script `scripts/stage0_analyze.py` (cd5877c, md5 4866a10d) was committed before any output was
viewed. Full printout: `analysis_final.out` (this directory; md5 8813b347…). Per-trajectory JSON on Linux #2:
`mht_work/stage0/analysis_final.json`. Evaluation: Who&When 182 + TraceElephant groupchat 174 = **356** evaluable
trajectories, pooled. Candidates = model steps. "controlled" = OLS residual on [log step tokens, relative position,
has_code] with trajectory fixed effects (round-68 rule). "matched" = round-75 matched-pair rank-AUROC (r 1.5, w 0.25).
Paired bootstrap over trajectories, 95% CI. Null bound (round 75): CI upper < +0.04.

## Proxies
| proxy | corpus | tokens | eval-question overlap* |
|---|---|---|---|
| base | Qwen3-8B | — | — |
| tapt | TAPT pilot v1 (ARIA capped 10M) | 24.46M | 270 / 356 |
| tapt_clean | TAPT rules minus 379 runs that near-duplicate eval questions (A1) | 24.38M | 0 |
| S / R | E2 success-only / all-outcome | 6.06M / 6.09M | 118 / 205 |
| shuf | R with step order shuffled inside every chunk, ids renumbered | 6.08M | = R |
| irr | WikiText-103 windows with exactly R's chunk lengths | 6.09M | 0 |
| full | all clean converted public + anchor normal, filtered | 34.42M | 0 |

\*Direct overlap, Jaccard >= 0.3 (`results/stage0_manifest/`).

## Pre-registered verdicts
| question | comparison | primary statistic | result [95% CI] | verdict |
|---|---|---|---|---|
| Q1 label efficiency | tapt − base | LE area, linear head, controlled | +0.014 [−0.005, +0.034] | **NULL** |
| Q1′ (A1, takes precedence) | tapt_clean − base | same | +0.016 [−0.003, +0.035] | **NULL** |
| Q2 negative controls | R vs shuf vs irr | E1 OAT matched (1.5, 0.25) | R − irr +0.031 [−0.001, +0.066]; R − shuf −0.007 [−0.030, +0.017]; irr − base +0.022 [−0.019, +0.069] | **UNDETERMINED** (rule 4) |
| Q3 dose | full − tapt | LE area (+ E1 matched) | −0.000 [−0.009, +0.007] (E1 −0.010 [−0.043, +0.020]) | **NULL** |
| Q3′ (A1, takes precedence) | full − tapt_clean | same | −0.002 [−0.010, +0.005] (E1 +0.004 [−0.026, +0.035]) | **NULL** |

LE area = mean over n ∈ {100, 300, 1000} TracerTraj labels (question-grouped nested subsets, 5 draws) of the controlled
pooled rank-AUROC of a frozen-feature step-scoring head (E4 stage-A recipe).

## Descriptive (no verdicts)
**Label efficiency, all proxies − base (LE area, controlled; linear / MLP head):**

| proxy | linear | MLP |
|---|---|---|
| S | +0.015 [+0.001, +0.030] | +0.003 [−0.011, +0.016] |
| R | +0.027 [+0.012, +0.042] | +0.006 [−0.008, +0.019] |
| shuf | +0.024 [+0.008, +0.039] | +0.011 [−0.003, +0.024] |
| irr | −0.009 [−0.021, +0.004] | **−0.019 [−0.031, −0.007]** |
| tapt | +0.014 [−0.005, +0.034] | −0.015 [−0.033, +0.001] |
| tapt_clean | +0.016 [−0.003, +0.035] | +0.003 [−0.013, +0.019] |
| full | +0.014 [−0.002, +0.029] | −0.006 [−0.021, +0.008] |

**Full-label stage A (E4 recipe, 3 seeds), controlled, proxy − base:**
- linear head: everything spans 0 (tapt −0.009, S −0.013, R −0.004, shuf +0.015, full +0.002, tapt_clean +0.015
  [−0.012, +0.040]) **except irr −0.042 [−0.066, −0.018]**;
- MLP head: **almost every mid-trained proxy is worse** — tapt −0.035 [−0.062, −0.012], S −0.042 [−0.066, −0.018], shuf
  −0.046 [−0.073, −0.020], full −0.046 [−0.073, −0.020], irr −0.055 [−0.076, −0.032]; R −0.021 [−0.042, +0.001] and
  tapt_clean −0.020 [−0.045, +0.002] span 0;
- pairs: tapt − tapt_clean linear −0.023 [−0.039, −0.010], MLP −0.015 [−0.028, −0.001]; full − tapt_clean MLP −0.026
  [−0.043, −0.010]; full − tapt spans 0 for both heads.

**E1 (OAT) matched (1.5, 0.25) − base:** tapt +0.059 [+0.015, +0.107], S +0.043 [−0.010, +0.091], R +0.054 [+0.008,
+0.099], shuf +0.061 [+0.020, +0.108], full +0.049 [+0.004, +0.099], tapt_clean +0.045 [+0.002, +0.090], irr +0.022
[−0.019, +0.069]. **Controlled (OLS) E1: every proxy − base within ±0.02, all CIs include 0** (shuf +0.017 [−0.002, +0.036]).

**Task overlap:** tapt − tapt_clean, E1 matched +0.013 [−0.014, +0.041], LE area −0.002 (from the table). tapt − base E1
matched on the 270 overlapping trajectories +0.077 [+0.024, +0.129] vs +0.002 [−0.077, +0.088] on the 86 non-overlapping
ones (only 52 have matched pairs).

## Reading
1. **Mid-training by language modelling on MAS trajectories does not improve supervised attribution, at any label budget
   tested, and adding data (24.4M → 34.4M) does nothing.** All four pre-registered label-efficiency / dose verdicts are
   NULL under the round-75 null bound. The A1 versions (no evaluation-question overlap) agree with the originals.
2. **Task overlap did not drive the old numbers.** tapt and tapt_clean are indistinguishable on every readout; the
   overlap / no-overlap split of tapt − base is too small on the clean side to mean anything (52 trajectories).
3. **Small, head-dependent label-efficiency signals for 6M-token MAS corpora** (linear head only; R, shuf, S), but not for
   the larger corpora and not with the MLP head. Non-monotonic in tokens; treat as noise-level until replicated.
4. **Trajectory order is not what helps.** shuf ≈ R on every readout (E1 matched −0.007, LE area linear R +0.027 vs shuf
   +0.024). Whatever mid-training adds, it is not learned from the sequential / causal structure of trajectories.
5. **With full labels, mid-training tends to hurt the supervised readout under length control,** most clearly with the MLP
   head (−0.035 to −0.055 for tapt, S, shuf, full, irr; E4 already showed this for tapt). Generic text (irr) is the only
   proxy that also hurts the linear head. So at full label budget, mid-trained features are at best neutral.
6. **The E1 matched-pair gain (~+0.05) is real but fragile:** present for every MAS-text proxy including the shuffled one,
   smaller and n.s. for irr, and ~0 under the OLS length/position control. Whether it reflects MAS content or generic drift
   is exactly Q2, which is undetermined (R − irr lower bound −0.001).

## Deviations
- **Code bug (introduced in round 79):** adding the label-efficiency mode to `hgfm/e4/e4_probe.py` put the rest of the
  `parse_args()` line inside the new `if`, so non-LE mode had no `dev`; the full-label stage A for shuf / irr / full failed
  at 00:07 and was rerun after the fix (md5 c780bb7f) at 03:23. The LE mode was unaffected. Runtime only.
- First driver launch: torchrun port clash (full and nc_shuf both on 29500) → restart with explicit ports (log
  `status.first_launch_port_clash`).
- full and tapt_clean trained with flash-attn 2 (TAPT, S, R, shuf, irr: SDPA); bf16-level difference.
- Manifest overlap uses the direct rule, not connected components (components chain into one 14k-item group at 0.3).
- BEFT n = 100 was deferred to after tapt_clean (appendix A1); BEFT n = 100 / 300 are descriptive single-draw runs and are
  reported separately when complete (`mht_work/stage0/beft_*`).
- Bootstrap CIs move by ±0.002 between runs (shared RNG stream); numbers here are from `analysis_final.out`.

## Addendum (check 5, 2026-11-03 08:10 UTC): BEFT at n = 100 / 300 — descriptive only

v_proj-bias-only fine-tuning (E4 stage B recipe, accum 4 per amendment 9df9dc0) on the first draw of the question-grouped
nested subsets; one run each, **no decision is drawn from these** (pre-registration: single draw, descriptive).
`python -m hgfm.e4.e4_beft_eval --feats e4/feats_base.pt --runs base=stage0/beft_base_n<n> tapt=stage0/beft_tapt_n<n>`
→ `mht_work/stage0/beft_eval_n{100,300}.json`. Rank-AUROC (step-level acc@1 in brackets); "resid" = controlled for
log step tokens / relative position / has_code with trajectory fixed effects.

| n | init | WW raw | TEgc raw | pooled raw | pooled resid | TT_test resid |
|---|---|---|---|---|---|---|
| 100 | base | 0.558 (0.209) | 0.674 (0.178) | 0.615 (0.194) | 0.606 (0.166) | 0.721 (0.409) |
| 100 | tapt | 0.671 (0.220) | 0.607 (0.126) | 0.640 (0.174) | 0.607 (0.157) | 0.776 (0.467) |
| 300 | base | 0.595 (0.170) | 0.664 (0.195) | 0.629 (0.183) | 0.636 (0.177) | 0.817 (0.504) |
| 300 | tapt | 0.697 (0.231) | 0.662 (0.184) | 0.680 (0.208) | 0.634 (0.166) | 0.850 (0.544) |
| — | longest step | 0.691 (0.247) | 0.655 (0.115) | 0.673 (0.183) | 0.472 (0.087) | 0.484 (0.091) |

tapt − base, pooled WW + TEgc (n = 356, paired trajectory bootstrap):
- n = 100: raw +0.025 [−0.007, +0.060]; controlled +0.001 [−0.030, +0.035].
- n = 300: raw +0.051 [+0.019, +0.083]; controlled −0.002 [−0.035, +0.034].

Reading: same pattern as stage A and E4 — the raw tapt advantage on the transfer benchmarks is a step-length effect
(raw tapt at n = 300 is 0.680 vs the longest-step baseline 0.673; controlled difference ≈ 0), and WW and TEgc move in
opposite directions. On the in-distribution TracerTraj test split tapt is higher (+0.055 / +0.033 controlled), but 621 /
768 of those test trajectories have near-duplicate questions in TracerTraj train (manifest), so this is not evidence of
transfer. Nothing here changes the Stage 0 conclusion.
