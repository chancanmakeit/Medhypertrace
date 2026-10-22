# C6 (LLM layer) GPU sizing and Runpod quote — round 44, 2026-10-21 20:58 PDT

## Measured inputs (sandbox, fold LQD:mac, `prepare_maa.sh` steps 5–6 with `--max_train 8000`)
- Training pairs: 6,326 (capped by available auditor positives × neg_ratio 1, not by max_train) — expect ~6–8k per fold.
- Qwen3-8B tokenizer, chat template, thinking off: prompt+answer tokens mean 1,238, p50 1,232, p90 1,574, p99 1,812, max 2,150;
  0.2% exceed max_len 2048 (truncated). 7.83 M tokens per fold-epoch (≈9 M with batch padding at bs 4).
- Runs: 7 folds (6 LQD + QD) × 2 trained variants (graph, text) = 14 trainings of 1 epoch; zeroshot and eval are small (≈91 prompts per fold).

## Memory estimate (not yet measured on GPU)
| item | GB |
|---|---|
| Qwen3-8B weights bf16 (8.2 B params, untied lm_head) | ≈16.4 |
| LoRA q/k/v r=8 (≈5.3 M) + projector (≈17.6 M) + AdamW states | <0.5 |
| activations, grad checkpointing, bs 4 × ≤2048: saved layer inputs 36 × 4×2048×4096×2 B | ≈2.4 |
| one recomputed layer (MLP 12,288 wide, attention) | ≈1–2 |
| CUDA context + allocator slack | ≈2–4 |
| **total** | **≈23–26** |
Without gradient checkpointing activations alone are ≈45 GB → `--grad_ckpt` is required below 80 GB.
Verdict: 48 GB cards fit with margin; 32 GB (RTX 5090) probably fits but tight; 24 GB cards do not fit at bs 4.

## Time / cost estimate (assumption: 6·N FLOPs per token = 4.9e10, MFU 35–40%; to be replaced by a measured pilot)
Prices: Secure Cloud on-demand $/GPU-h from `list-gpu-types`, read 2026-10-22 ~03:58 UTC.
| GPU (48–80 GB) | $/GPU-h | stock 1x / 4x | est. tok/s | h per fold | 14 trainings GPU-h | est. compute $ |
|---|---|---|---|---|---|---|
| A40 48GB | 0.59 | HIGH / HIGH | ≈1,100 | ≈2.3 | ≈32 | ≈19 |
| RTX A6000 48GB | 0.59 | LOW / NONE | ≈1,100 | ≈2.3 | ≈32 | ≈19 |
| L40S 48GB | 1.09 | MEDIUM / LOW | ≈2,600 | ≈1.0 | ≈14 | ≈15 |
| A100 SXM 80GB | 1.79 | MEDIUM / LOW | ≈2,500 | ≈1.0 | ≈14 | ≈25 |
| H100 SXM 80GB | 3.99 | MEDIUM / LOW | ≈7,000 | ≈0.4 | ≈5 | ≈20 |
Not included: per-pod setup (model download ≈16 GB, data prep ≈30–60 min CPU), eval, idle time, disk storage (price not read).
