# SAMT v1 — structure-aware mid-training (round 64)

Design: `../../docs/design/SAMT_design_v1.md`. Frozen Qwen3-8B; HGFM v0.2 encoder (from scratch) + projector trained end
to end on 11,987 question rows whose answers are carried by the graph tokens (O1 content match, O2 read set, O3 readers,
O4 option answer). Corpus = TAPT pilot rules (public + anchor normal runs, no MAA, no groupchat family). Driver
`../../scripts/linux2_run_samt.sh`; Linux #2 dir `mht_work/midtrain/samt_v1/`.

## Training (2026-10-27 05:37–07:32 UTC)
750 optimizer steps (2 epochs, effective batch 32, lr 3e-4 cosine, warmup 5%), 4 × A6000, ~9 s/step, 29–34 GB per GPU,
no failures. 19.08M trainable parameters (encoder 1.50M + projector). Answer-token loss (logged steps):
step 1 2.41 → 75 0.20 → 150 0.11 → 300 0.11 → 450 0.07 → 600 0.06 → 750 0.09 (token accuracy 0.73 → 0.96–0.98).
Export: 12,409 MAA runs → `graph_tokens_samt.pt`; node / edge counts equal the per-fold token files for every run
(QD 9,313, LQD_mac 3,703 runs, 0 mismatches).

## Probe gate (held-out runs, never trained on; `probe_summary.json`)
Teacher-forced exact match of the answer (= greedy decoding reproduces it). real = the run's own tokens; shuffle =
states of random nodes / edges of another held-out run (the text is unchanged: what the trained model gets from text);
zero = states set to 0; untrained = fresh encoder + projector. Paired bootstrap 1000 for real − shuffle.

| objective | n | real | shuffle | zero | untrained | real − shuffle [95% CI] |
|---|---|---|---|---|---|---|
| O1 content match (4-way) | 193 | 0.632 | 0.544 | 0.440 | 0.275 | +0.088 [+0.031, +0.150] |
| O2 read set | 128 | **0.984** | 0.508 | 0.109 | 0.000 | **+0.477 [+0.391, +0.555]** |
| O3 readers | 138 | **0.986** | 0.217 | 0.036 | 0.000 | **+0.768 [+0.696, +0.841]** |
| O4 option answer (anchors) | 132 | 0.856 | 0.750 | 0.788 | 0.720 | +0.106 [+0.061, +0.159] |

Per dataset (real / shuffle, n): O2 aftraj 1.00/0.70 (43), anchor medagents_mc 1.00/0.17 (12), aria 1.00/0.63 (24),
mast_data 0.95/0.32 (37); O3 aftraj 1.00/0.10 (42), medagents_mc 0.92/0.42 (12), aria 1.00/0.17 (48), mast_data 0.95/0.50
(22); O1 aftraj 0.80/0.70, aria 0.72/0.62, mast_data 0.63/0.47, but the three medical anchors 0.31/0.31 (llm_debate),
0.62/0.81 (mdagents), 0.25/0.25 (medagents_mc); O4 llm_debate 0.88/0.85, mdagents 0.83/0.63, medagents_mc 0.86/0.78.

### Reading
1. **Gate passed for structure.** With its own graph tokens the frozen LLM answers read-set and reader questions almost
   perfectly (0.98–0.99) on every source, including the medical anchors; with another run's tokens it falls to what the
   text allows (0.22–0.51). The tokens carry interaction structure in a form the LLM reads — the thing C6 found missing.
2. **Content is weak, and absent on medical runs.** O1 gains only +0.09 overall and nothing on the three medical anchor
   frameworks, where the options are same-agent / same-phase excerpts on one question. A 384-d MiniLM summary does not
   separate near-identical medical reasoning; content has to come from the excerpt text (the intended split: hypergraph
   for structure, LLM for content).
3. **O4** +0.11 overall, mostly mdagents (+0.21); in llm_debate the visible text already gives 0.85.
4. `untrained` is not a text-only baseline (it fails the answer format: 0.00 on O2 / O3); `zero` is out of distribution
   (below shuffle). The text-only reference is `shuffle`.
5. Per-source probe accuracy: the text-only level differs a lot by source (O2 shuffle 0.17–0.70), but with real tokens
   every source is at 0.92–1.00, so the structural readout works on every source. This is NOT the "data-source
   identifiability" audit promised in round 61 (corrected in round 65 after medical-aegis issue #2): that audit has to
   predict the source from what the model actually sees (input text / graph tokens) and check for source -> label
   shortcuts within comparable strata; it is still open.

Whether readable structure helps MAA attribution is the SFT question (next section).

## SFT on MedAgentAudit (2026-10-27 07:43–12:06 UTC) — no measurable gain; one unresolved cross-MAS hint
**Taxonomy: MedAgentAudit only.** Same MS-Swift SFT recipe and the same `sft_graph` prompts as the base runs; only the
graph vectors (SAMT encoder, one file for all folds) and the projector start differ. samt = SAMT-aligned projector,
lr 1e-4; encOnly = SAMT tokens with a random projector, lr 1e-3 (the original recipe); base_text / base_graph = round-60
seed study (3 seeds; text is unchanged by SAMT because the LLM is frozen). samt_zero / samt_shuf = samt checkpoints
evaluated with zeroed / cross-run shuffled tokens. Full output `samt_v1_eval.out` (paired bootstrap 1000; seed ensemble
= mean z-score). Per-instance scores and the JSON stay on Linux #2 (`mht_work/midtrain/samt_v1/samt_v1_scores.csv`,
`samt_v1_eval.json`). LQD_mac primary metric = codes with >= 2 positives and >= 2 negatives (5 codes, n = 51; agreed
with medical-aegis in issue round 44/64); all-codes metric alongside. On QD both metrics are identical.

| split | metric | base_text | base_graph | samt | encOnly | samt_zero | samt_shuf |
|---|---|---|---|---|---|---|---|
| QD (n=399) | main | 0.780 ± 0.002 | 0.782 ± 0.013 | 0.793 / 0.793 | 0.806 / 0.803 | 0.746 / 0.719 | 0.790 / 0.773 |
| LQD_mac | robust (n=51) | 0.793 ± 0.005 | 0.821 ± 0.009 | 0.863 / 0.826 | 0.771 / 0.798 | 0.738 / 0.780 | 0.796 / 0.826 |
| LQD_mac | all codes (n=67) | 0.809 ± 0.032 | 0.826 ± 0.061 | 0.866 / 0.816 | 0.717 / 0.832 | 0.812 / 0.712 | 0.783 / 0.780 |

Paired differences, seed ensembles [95% CI]:
| comparison | QD | LQD_mac robust | LQD_mac all codes |
|---|---|---|---|
| samt − base_text (main question) | +0.017 [−0.011, +0.043] | +0.046 [−0.040, +0.149] | +0.033 [−0.038, +0.131] |
| samt − base_graph | −0.001 [−0.032, +0.028] | +0.036 [−0.048, +0.143] | +0.026 [−0.050, +0.125] |
| samt − encOnly (alignment init) | −0.003 [−0.033, +0.027] | +0.046 [−0.033, +0.139] | +0.033 [−0.029, +0.132] |
| encOnly − base_text (encoder swap) | +0.020 [+0.000, +0.040] | +0.000 [−0.089, +0.083] | +0.000 [−0.094, +0.071] |
| samt − samt_zero | **+0.063 [+0.020, +0.104]** | +0.095 [−0.093, +0.242] | +0.068 [−0.061, +0.207] |
| samt − samt_shuf (run-specific use) | +0.011 [−0.009, +0.031] | +0.034 [−0.035, +0.175] | +0.060 [−0.026, +0.164] |

Per code on QD (exploratory, not pre-registered; n = 39–40 per code, AUROC SE ≈ 0.07): samt − base_text ranges from
−0.036 (1.1.1) to +0.074 (3.2.1), with no group of codes standing out beyond that noise level.

### Reading
1. **QD: no measurable gain.** samt − base_text +0.017 (upper bound +0.043), the same size as the base graph − text gap of
   round 60. The alignment initialisation adds nothing (samt − encOnly −0.003).
2. **The SFT model still does not use run-specific token content on QD.** Zeroing the tokens costs −0.063 (CI excludes 0),
   but zeroed tokens are out of distribution (in the probe, zero was below shuffle too); with shuffled, in-distribution
   tokens the cost is only +0.011 (n.s.) — the same picture as the C6 diagnosis (round 54: QD −0.005 to −0.024). The
   probe showed that the frozen LLM CAN read structure from these tokens; attribution SFT on MAA labels does not learn
   to rely on it.
3. **LQD_mac (cross-MAS): direction consistent with a transfer gain, not resolvable.** On the robust metric both SAMT seeds
   (0.863, 0.826) are above all three base-text seeds (0.787–0.796, SD 0.005) and above encOnly, and real > shuffled in
   seed 0 (+0.066 [+0.010, +0.203]). But n = 51 instances: every ensemble CI includes 0. Only the pooled 6-fold LQD can
   say whether this is real.
4. **Practical:** a single label-free SAMT encoder (never trained on MAA) gives graph VECTORS at least as good for the
   LLM as the per-fold supervised encoders (encOnly − base_graph +0.002 on QD). Caveat: the prompts' candidate steps
   are still the ones ranked by each fold's supervised encoder (`step_prob`, unchanged sft_graph prompts), so the
   per-fold encoder is still used for candidate selection; only its graph-vector role is shown to be replaceable.
5. **Why readability does not turn into attribution signal (hypotheses, not tested):** most MAA defect codes are content
   judgments about one step (the per-code picture shows no structural group); and the SFT prompt already states the
   structure in text (event lines name how many and which phases a step read), so the tokens add little beyond the text.
   Structure should matter more for the responsibility layer (which step caused a wrong answer), e.g. medical-aegis's
   branch data, than for MAA's defect layer.
