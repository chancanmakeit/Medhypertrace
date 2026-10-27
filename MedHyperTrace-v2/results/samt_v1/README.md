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
5. Source identifiability (round 61): the text-only level differs a lot by source (O2 shuffle 0.17–0.70), but with real
   tokens every source is at 0.92–1.00, so the structural readout does not depend on which dataset the run came from.

Whether readable structure helps MAA attribution is the SFT question (running; results → `samt_v1_eval.*`).
