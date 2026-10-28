# E1–E3 results (round 67, 2026-10-28; corrected and extended in round 68)

> **Correction (round 68, read first).** A trivial baseline the pre-registration did not include — **"the longest model
> step"** — reaches pooled rank-AUROC 0.673 and beats OAT with every proxy. After removing step length, position and code
> content (§5), the E1 gain tapt − base drops from +0.028 [+0.008, +0.047] to **+0.002 [−0.019, +0.023]**, and the same
> holds for the two E1b proxies. E1 still "holds" by the letter of the pre-registered rule, but the gain is almost
> entirely explained by mid-trained proxies making OAT's scores track step length more. It is **not** evidence that
> mid-training improves attribution. Missing the length baseline was a design error in the pre-registration.

Pre-registration: `docs/design/E1-E3_prereg_v1.md` (commit 33dd4f7, written before any result). Analysis:
`scripts/e1e3_analyze.py` (run on Linux #2 at 08:07 UTC, md5 0b70e5c3…), full printout `e1e3_analyze.out`; per-trajectory
JSON on Linux #2 (`mht_work/e1e3/e1e3_results.json`). The exploratory checks (§4) were added **after** seeing the results
(`scripts/e1e3_exploratory.py`, output `mht_work/e1e3/e1e3_exploratory.json`) and are not part of any decision.

**Taxonomy / layer:** responsibility layer (the labelled decisive mistake step), Who&When-style labels only. Nothing here
is merged with MAST or MedAgentAudit numbers.

## Verdicts (pre-registered rules, verbatim from the script)
| | rule | result |
|---|---|---|
| **E1** (TAPT checkpoint as OAT proxy) | pooled tapt − base rank-AUROC CI lower > 0 and Acc@1 diff ≥ 0 | **HOLDS**: rank-AUROC +0.027 [+0.009, +0.047], Acc@1 +0.038; it also holds separately on WW and on TEgc |
| **E1b** (addendum, S / R checkpoints as OAT proxies) | at least one of S − base, R − base with pooled rank-AUROC CI lower > 0 | **REPLICATES (S, R)**: S +0.021 [+0.003, +0.036], R +0.034 [+0.016, +0.052]; see §5 for why this is not an attribution gain |
| **E2** (likelihood ratio S − R) | pooled rank-AUROC beats the best trivial baseline and NLL_base, both CI lower > 0 | **DOES NOT HOLD**: −0.120 [−0.160, −0.081] vs first step, −0.147 [−0.182, −0.112] vs NLL_base; below chance (0.456) |

## 1. Scorers (candidates = model steps; WW n = 182, TEgc n = 174, pooled n = 356)
Acc@1 / Hit@3 / within-trajectory rank-AUROC. OAT rows: metrics per seed, then mean over the 5 seeds per trajectory.

| scorer | WW | TEgc | pooled | pooled ≤ 32k (n = 344, sensitivity) |
|---|---|---|---|---|
| random (expected) | 0.128 / 0.383 / 0.500 | 0.064 / 0.193 / 0.500 | 0.097 / 0.290 / 0.500 | 0.099 / 0.298 / 0.500 |
| first model step | 0.115 / 0.445 / 0.590 | 0.069 / 0.149 / 0.561 | 0.093 / 0.301 / 0.576 | 0.093 / 0.305 / 0.566 |
| last model step | 0.071 / 0.269 / 0.410 | 0.029 / 0.207 / 0.439 | 0.051 / 0.239 / 0.424 | 0.052 / 0.247 / 0.434 |
| position prior (other dataset) | 0.192 / 0.440 / 0.584 | 0.069 / 0.149 / 0.525 | 0.132 / 0.298 / 0.556 | 0.131 / 0.302 / 0.549 |
| **OAT, proxy Qwen3-8B** | 0.130 / 0.423 / 0.540 | 0.145 / 0.354 / 0.653 | 0.137 / 0.389 / 0.595 | 0.142 / 0.398 / 0.592 |
| **OAT, proxy TAPT** | 0.158 / 0.467 / 0.573 | 0.192 / 0.367 / 0.674 | 0.175 / 0.418 / 0.622 | 0.181 / 0.427 / 0.620 |
| NLL_base | 0.148 / 0.473 / 0.598 | 0.075 / 0.167 / 0.607 | 0.112 / 0.323 / 0.603 | 0.110 / 0.326 / 0.595 |
| NLL_tapt − NLL_base (control) | 0.022 / 0.203 / 0.317 | 0.029 / 0.075 / 0.317 | 0.025 / 0.140 / 0.317 | 0.026 / 0.145 / 0.322 |
| **ΔNLL = NLL_S − NLL_R (E2)** | 0.044 / 0.357 / 0.470 | 0.063 / 0.132 / 0.441 | 0.053 / 0.247 / 0.456 | 0.055 / 0.253 / 0.453 |

## 2. Paired differences (bootstrap 1000 over trajectories, 95% CI)
| comparison | set | Acc@1 | Hit@3 | rank-AUROC |
|---|---|---|---|---|
| OAT tapt − OAT base | WW | +0.029 [−0.018, +0.077] | +0.044 [−0.008, +0.092] | **+0.033 [+0.002, +0.068]** |
| | TEgc | **+0.047 [+0.015, +0.085]** | +0.013 [−0.024, +0.051] | **+0.021 [+0.004, +0.038]** |
| | pooled | **+0.038 [+0.009, +0.068]** | +0.029 [−0.005, +0.062] | **+0.027 [+0.009, +0.047]** |
| | pooled ≤ 32k | +0.039 [+0.006, +0.068] | +0.028 [−0.003, +0.063] | +0.028 [+0.009, +0.048] |
| OAT base − first step | WW / TEgc / pooled | +0.014 / +0.076 / +0.044 | – / – / +0.089 | −0.051 [−0.118, +0.018] / **+0.092 [+0.019, +0.163]** / +0.019 [−0.028, +0.063] |
| OAT base − position prior | WW / TEgc / pooled | −0.063 / +0.076 / +0.005 | – / – / +0.092 | −0.045 [−0.113, +0.029] / **+0.127 [+0.064, +0.191]** / +0.039 [−0.011, +0.095] |
| OAT tapt − first step | WW / TEgc / pooled | +0.043 / +0.123 / +0.082 | – / – / +0.117 | −0.017 [−0.086, +0.046] / **+0.113 [+0.046, +0.177]** / +0.046 [−0.001, +0.097] |
| OAT tapt − position prior | WW / TEgc / pooled | −0.034 / +0.123 / +0.043 | – / – / +0.120 | −0.012 [−0.071, +0.051] / **+0.148 [+0.075, +0.214]** / **+0.067 [+0.023, +0.116]** |
| ΔNLL − first step | pooled | −0.039 [−0.067, −0.011] | −0.053 [−0.107, −0.003] | −0.120 [−0.160, −0.081] |
| ΔNLL − NLL_base | pooled | −0.059 [−0.093, −0.028] | −0.076 [−0.126, −0.028] | −0.147 [−0.182, −0.112] |
| ΔNLL − OAT base | pooled | −0.084 [−0.125, −0.045] | −0.142 [−0.210, −0.081] | −0.139 [−0.190, −0.091] |

Full list (also vs last step) in `e1e3_analyze.out`.

## 3. OAT's own pooled step metrics (secondary, for comparison with the paper)
| proxy | WW AUROC | TEgc AUROC | WW / TEgc top-k hit rate | WW / TEgc AUPRC |
|---|---|---|---|---|
| Qwen3-8B | 0.773 ± 0.003 | 0.713 ± 0.003 | 0.423 / 0.354 | 0.126 / 0.107 |
| TAPT | 0.774 ± 0.006 | 0.725 ± 0.005 | 0.467 / 0.367 | 0.122 / 0.108 |
Paper (Qwen3.5-27B proxy, MCP-Atlas → Who&When): AUROC 0.758, Hit@3 0.451. Our 8B reproduction is at the paper's level.
On WW, OAT's pooled AUROC (0.773) looks good, but within trajectories OAT does not beat "first model step" (0.540 vs 0.590):
a large part of the pooled AUROC is between-trajectory scale and position, which is why the pre-registration used
within-trajectory metrics.

## 4. Exploratory (post hoc, not pre-registered; needs confirmation on fresh data)
1. **E1 seed robustness.** Pooled rank-AUROC per seed: base 0.605 / 0.595 / 0.591 / 0.587 / 0.597, tapt 0.629 / 0.617 /
   0.628 / 0.629 / 0.609. Every tapt seed is above every base seed, so the E1 gain is not OAT training noise. (The
   bootstrap CI covers trajectory sampling only.)
2. **The E2 controls have a strong signal with the opposite sign.** NLL_tapt − NLL_base has rank-AUROC 0.317 on both
   datasets, i.e. **NLL_base − NLL_tapt = 0.683** on WW and on TEgc: TAPT lowers the NLL of the mistake step *more* than the
   NLL of the other steps. This is the best single scorer seen, but the sign was not predicted. Position explains only
   part of it: Spearman with step index −0.12 (WW) / −0.18 (TEgc); with the first model step removed from the candidates,
   0.667 (WW, n = 161) / 0.687 (TEgc, n = 162) vs earliest remaining step 0.627 / 0.565 and NLL_base 0.625 / 0.614.
   Reversed ΔNLL (R − S) is weak: 0.530 / 0.559.
   Possible reading (untested): mistake steps contain the generic agent text the TAPT corpus is full of (plans, code,
   tool-call boilerplate, restated tasks), which TAPT learns best; that would also explain why TAPT hidden states help
   OAT. Step length and content type: checked in §5 — most of this signal is step length.
3. Why E2 failed as specified: success-only vs mixed corpora matched within dataset differ only in outcome composition
   (R has 36% success runs), so S and R are near-identical LMs; their difference is small and dominated by noise /
   the domain-adaptation direction, not by "failure-likeness".

## 5. Round 68: step-length confound and E1b (post hoc diagnostics + pre-registered addendum)
Scripts `scripts/e1e3_confounds.py` (output `e1e3_confounds.json`) and `scripts/e1e3_analyze.py` with the E1b addendum
(output `e1e3_analyze_v2.out`). Covariates per candidate step: token length (OAT serialisation, Qwen3 tokenizer), relative
position, has_code. "Residual" = the scorer after an OLS on [log length, relative position, has_code] with trajectory
fixed effects, fitted **without labels**; OAT scores here are seed means (raw values differ by ≤ 0.003 from §1).

**Step length alone is the strongest trivial baseline.** "Longest model step" rank-AUROC: WW 0.691, TEgc 0.655, pooled
0.673 (shortest: 0.309 / 0.345). Mistake steps are long (plans, code, long answers).

| pooled (n = 356), rank-AUROC difference [95% CI] | raw | after length / position / code |
|---|---|---|
| OAT base − longest step | −0.079 [−0.119, −0.039] | – |
| OAT tapt − longest step | −0.051 [−0.096, −0.010] | – |
| NLL_base − NLL_tapt − longest step | +0.010 [−0.025, +0.040] | – |
| **OAT tapt − OAT base (E1)** | +0.028 [+0.008, +0.047] | **+0.002 [−0.019, +0.023]** |
| OAT S − OAT base (E1b) | +0.020 [+0.000, +0.038] | −0.002 [−0.020, +0.017] |
| OAT R − OAT base (E1b) | +0.037 [+0.019, +0.056] | +0.000 [−0.021, +0.020] |
| OAT base − chance | +0.095 [+0.062, +0.126] | +0.043 [+0.010, +0.079] |
| OAT tapt − chance | +0.123 [+0.089, +0.155] | +0.044 [+0.007, +0.079] |
| NLL_base − NLL_tapt − chance | +0.183 [+0.152, +0.210] | +0.087 [+0.057, +0.118] |

Per dataset after the control: OAT base / tapt / S / R = WW 0.500 / 0.501 / 0.494 / 0.492, TEgc 0.587 / 0.590 / 0.590 /
0.597 — OAT has no length-independent signal on Who&When, some on TraceElephant groupchat.

**E1b (pre-registered addendum, written before its results).** Pooled rank-AUROC: base 0.595, S 0.616, R 0.629, tapt 0.622.
Every mid-trained proxy raises it (S − base +0.021, R − base +0.034, CI lower > 0 → "replicates"). There is no dose effect
(R, ~6M tokens, ≥ tapt, ~24.5M), and success-only S is slightly below all-outcome R (−0.013 [−0.021, −0.006]). Together
with the table above: any continued pretraining on agent trajectories shifts OAT's step representation towards step
length, and that is the whole of the "gain".

**Remaining leads (all post hoc):** NLL_base − NLL_tapt keeps +0.087 above chance after the control (0.58 / 0.60). OAT keeps
~+0.04 above chance, all of it on TEgc.

**flash-attn (round 68).** flash-attn 2.7.4.post1 installed in mht-swift (torch 2.6 / cu12 / cp310). On Qwen3-8B vs SDPA:
hidden-state cosine 0.99998; LoRA forward+backward 1.7x faster at 4k tokens, 2.4x at 8k (`scripts/bench_flash_attn.py`).
E1b deliberately kept SDPA so the four proxies are comparable.

## Deviations from the pre-registration
- **n:** TEgc 174 of 176 (2 runs whose `mistake_step_id` is not among the steps, not mappable). WW 182 of 184: in
  Algorithm-Generated/14 and /59 the labelled mistake is a terminal (non-model) step; OAT drops them, and the
  pre-registered candidate rule (model steps only) makes them unevaluable for every scorer. Pooled n = 356 (pre-reg: 360).
- **Seed aggregation** (detail the pre-registration did not fix): metrics per seed, then the mean over the 5 seeds per
  trajectory. Top-k ties broken by step order.
- **E2 scoring rerun:** the first scoring run ran out of memory on the > 32k YaRN pass for all four models (no
  attention_mask → SDPA math kernel, an [L, L] matrix of 10.8 GiB at 76k tokens). Fixed (mask passed as in OAT's extraction;
  resumable output) and rerun 07:48–08:02 UTC; the native-pass numbers are the same code path. The tapt scores were
  produced twice in parallel (GPU 0 and GPU 1 chains); the later write is kept.
- **Shared GPUs:** GPU 1 (and ~1.9 GB of GPU 0) was used by another user, so E1's two proxies ran sequentially on GPU 0
  and E2 training on GPUs 2/3.
- Medical branch points (descriptive only per pre-registration): not run in this round.

## Compute
E1: 05:03–06:10 UTC on 1 GPU (both proxies). E2: S training 55 min and R 58 min on 2 GPUs each; scoring ~13 min × 4 GPUs
(plus ~15 min × 4 for the failed first run). All on Linux #2 (48 GB GPUs).

## What this means (rewritten in round 68)
- Within trajectories, the attribution signal in OAT and in raw NLL on these two held-out sets is mostly **step length**
  (and on WW, position). A one-line "longest step" rule beats OAT with any proxy. Any future responsibility-layer
  evaluation must report length / position baselines and length-controlled numbers; this is now a standing requirement.
- **E1's gain is not an attribution gain.** Mid-training (TAPT, S or R) makes OAT more length-sensitive; after the control the
  difference is +0.002. The pre-registered verdict "E1 holds" stands as recorded but must be read with this correction.
- E2 (likelihood ratio) fails, raw and controlled.
- What is left: OAT ~0.59 on TEgc after the control (independent of the proxy) and the post hoc NLL_base − NLL_tapt residual
  (0.58 / 0.60). Neither is evidence for mid-training yet; both would need a pre-registered test on fresh data with the
  length controls built in.
