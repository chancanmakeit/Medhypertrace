# C6 Runpod pilot (round 45–46), 1×A40 Secure, pod l3s761kur3bb6j (deleted after results were pushed)

Ran 04:21:45–~05:02 UTC 2026-10-22 (≈41 min at $0.59/h ≈ $0.40 compute; billing record not yet posted when checked).
Script `scripts/runpod_c6_pilot.sh`; files here are copied verbatim from branch `runpod-c6-pilot` (commit 7425058).

## Throughput / memory (Qwen3-8B bf16, LoRA q/k/v r=8, bs 4 × accum 4, max_len 2048, grad checkpointing)
`ckpt_pilot__train_stats.json`: steady 884 real tokens/s (995,702 tokens in 50 optimizer steps; padding 18%),
peak allocated 20.16 GB, peak reserved 23.41 GB; nvidia-smi max 24,309 MiB.

## Zero-shot Qwen3-8B (text prompts, no training, MedAgentAudit 399 human instances)
LQD pooled macro AUROC 0.616 [0.557, 0.673]; QD 0.614. Per fold: colacare 0.645, healthcareagent 0.736, mac 0.647,
mdagents n=14 (nan), medagent 0.602, reconcile 0.540.
Paired vs the encoder (C5 `scratch`, 3-seed average, same 399 instances, this sandbox): encoder 0.655, zeroshot
0.616, diff −0.039 [−0.117, +0.040]. Post-hoc rank-average of the two (equal weights, not tuned): 0.688, diff vs
encoder +0.034 [−0.013, +0.081] — exploratory only.
Weak codes for the zero-shot LLM: 2.1.2 0.38, 1.2.1 0.45, 2.1.1 0.48; strong: 1.1.1 0.79, 3.1.1 0.74, 3.2.1 0.73.

## Caveats
- `LQD_mac__eval_pilot_graph.json` is the 800-pair pipeline check (0.527, n=67): meaningless as a result, and it was
  built with the leaky pre-fix graph tokens (round 45 fix in `export_graph_emb.py`, commit e3d503c).
- Zero-shot prompts include candidate steps ranked by the fold encoder's out-of-sample scores on test runs; not affected
  by the leakage.
