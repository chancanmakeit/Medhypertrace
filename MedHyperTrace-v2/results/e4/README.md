# E4 results (rounds 73–74, 2026-10-28)

Pre-registration: `docs/design/E4_prereg_v1.md` (commit 6a21f9d, before any result). Question: does mid-training (TAPT)
make **supervised** attribution post-training better? Training labels: TracerTraj public release (train 2,889 / val 319
/ test 768 after dropping 22 test questions that also occur in train). Primary evaluation: Who&When 182 + TraceElephant
groupchat 174 (pooled 356), never seen in training. Candidates = model steps. "controlled" = scored after OLS on
[log step tokens, relative position, has_code] with trajectory fixed effects, fitted without labels (round-68 rule).
Full outputs on Linux #2: `mht_work/e4/` (`stageA/e4a_{linear,mlp}.json`, `stageA.log`, `stageB.json`, `stageB.out`,
`beft_{base,tapt}/log.jsonl`, scores).

## Verdicts (pre-registered rules)
| stage | comparison | raw rank-AUROC diff [95% CI] | controlled diff [95% CI] | verdict |
|---|---|---|---|---|
| A, linear head | tapt − base | +0.036 [+0.011, +0.063] | −0.009 [−0.036, +0.020] | **length effect** (raw only) |
| A, MLP head | tapt − base | −0.013 [−0.036, +0.011] | **−0.035 [−0.061, −0.010]** | does not hold (tapt worse) |
| B, BEFT (b_v + head) | tapt − base | +0.028 [−0.004, +0.058] | +0.007 [−0.022, +0.038] | **does not hold** |

Companion proxies (stage A, linear, controlled): S − base −0.013 [−0.037, +0.013], R − base −0.004 [−0.028, +0.022]; MLP:
S −0.042 [−0.065, −0.019], R −0.021 [−0.041, +0.001]. **No mid-trained checkpoint improves supervised attribution once
step length is controlled.**

## Scorers (pooled WW + TEgc, n = 356; Acc@1 / rank-AUROC)
| scorer | raw | controlled | TracerTraj test raw (n = 768) |
|---|---|---|---|
| random | 0.097 / 0.500 | 0.097 / 0.500 | 0.134 / 0.500 |
| longest model step | 0.183 / 0.673 | (0.087 / 0.472) | 0.062 / 0.451 |
| A linear, base / tapt | 0.184 / 0.630 · 0.188 / 0.667 | 0.154 / 0.571 · 0.129 / 0.563 | 0.694 / 0.917 · 0.707 / 0.921 |
| A MLP, base / tapt | 0.191 / 0.646 · 0.172 / 0.634 | 0.135 / 0.570 · 0.119 / 0.535 | 0.725 / 0.921 · 0.697 / 0.918 |
| **B BEFT, base / tapt** | 0.202 / 0.603 · 0.194 / 0.631 | **0.191 / 0.632 · 0.188 / 0.638** | 0.742 / 0.918 · 0.751 / 0.931 |

Per dataset (raw, Acc@1 / rank-AUROC): WW — BEFT base 0.220 / 0.598, tapt 0.209 / 0.684, longest step 0.247 / 0.691;
TEgc — BEFT base 0.184 / 0.610, tapt 0.178 / 0.575, longest step 0.115 / 0.655.

## Reading
1. **Mid-training: no value for supervised attribution either.** Same picture as E1 (label-free): mid-trained
   representations give raw gains that disappear (or reverse) under the length control.
2. **Supervised labels do transfer, but modestly.** BEFT (49k trainable values) reaches controlled rank-AUROC 0.63–0.64 on
   the held-out architectures (+0.13 over chance, CI lower +0.10); BEFT − longest step, controlled: base +0.159
   [+0.116, +0.206], tapt +0.166 [+0.122, +0.211]. This is the strongest length-independent signal so far (OAT controlled
   ≈ 0.54–0.59). Because TracerTraj labels are not length-correlated (longest step 0.451 there), the model learns an
   anti-length score, and its controlled numbers on WW / TEgc are *higher* than its raw ones.
3. **Raw numbers still lose to the trivial baseline.** Raw pooled rank-AUROC 0.60–0.67 for every trained scorer vs 0.673 for
   "longest step"; BEFT − longest step raw: base −0.070 [−0.111, −0.026], tapt −0.042 [−0.083, −0.000].
4. **Comparison with AgenTracer (papers' step-level metric):** our WW step-level accuracy is 0.21–0.27 (best: A linear tapt
   0.267; BEFT 0.21–0.22; longest step 0.247), computed among model steps. AgenTracer-8B reports 20.68 (Hand-Crafted) and
   37.30–42.86 (Algorithm-Generated), ≈ 32–36% pooled over WW's 184, with full GRPO on an 8B reasoning model and a
   different (paper) version of TracerTraj. Our scorers are far smaller (frozen LM + head, or b_v only), so this is not a
   like-for-like comparison; it bounds what light-weight supervised scoring achieves.
5. In-domain (TracerTraj test) everything is ~0.92 rank-AUROC / 0.69–0.75 Acc@1: the injected-fault test set is far
   easier than natural failures, and gains there do not predict gains on WW / TEgc (tapt +0.013 in-domain, +0.007
   controlled out-of-domain).

## Deviations / details
- 2 of 4,334 trajectories (> 131,072 tokens) skipped in feature extraction; BEFT training used the 2,608 training
  trajectories ≤ 16,384 tokens (90%); evaluation scored all 1,126 evaluation trajectories (none over the limit).
- Stage B: one seed per initialisation (pre-registered); best checkpoint by validation rank-AUROC (base 0.893, tapt
  0.907, both at the end of epoch 2). Runtime 20:31–23:40 UTC on 2 + 2 GPUs.
- Stage-A seed means: metrics per seed, then mean per trajectory (as E1).
