# Training-speed measurements on Linux #2 (round 72, 2026-10-28)

Hardware: 4x RTX A6000 48 GB, **compute capability 8.6** (Ampere GA102; A100 is 8.0). `nvidia-smi topo -m`: every GPU
pair is **SYS** (PCIe through the inter-socket link), no NVLink; GPUs 0/1 on NUMA 0, 2/3 on NUMA 1. Software: torch 2.6.0,
transformers 4.57.6, ms-swift 4.6.0, flash-attn 2.7.4.post1, **liger-kernel 0.7.0** (0.8.x refuses transformers < 5.0).

## Micro-benchmark (`scripts/bench_train_speed.py`, one GPU, Qwen3-8B, LoRA r64 all-linear, flash-attn 2, bf16)
Seconds per forward+backward of one sequence (mean of 3), peak memory. "lm" = causal-LM loss (TAPT); "head" = hidden
states -> small scoring head, no vocabulary logits (stand-in for E4).

| mode | Liger | grad ckpt | 1k | 4k | 8k | 16k |
|---|---|---|---|---|---|---|
| lm | no | on | 0.97 s / 18.0 GiB | 3.55–3.61 s / 24.1 GiB | 7.40 s / 32.3 GiB | **OOM** |
| lm | yes | on | 0.87 s / 16.9 GiB | 3.06–3.11 s / 18.4 GiB | 6.35 s / 20.8 GiB | 14.2 s / 25.7 GiB |
| lm | no / yes | off | – | **OOM** | OOM | OOM |
| head | no | on | – | 3.49 s / 18.7 GiB | 7.07 s / 21.4 GiB | 15.6 s / 26.8 GiB |
| head | yes | on | – | 2.91 s / 18.4 GiB | 6.11 s / 20.9 GiB | 13.7 s / 25.8 GiB |
| head | no / yes | off | – | **OOM** | OOM | OOM |

- Liger is numerically equivalent: with the same LoRA init, loss differs by ≤ 5e-4 and the LoRA gradient norm by 0.05%
  (4k) / 0.2% (1k).
- Liger: +14–17% (lm), +12–20% (head) per step; memory −24% (4k) / −36% (8k) for lm, and 16k fits only with Liger.
- Gradient checkpointing cannot be switched off for LoRA r64 all-linear on Qwen3-8B even at 4k tokens (activations), with
  or without Liger.
- Per-token cost at 1k vs 4k differs by only ~9%: with batch size 1 there is no padding to remove.

## End-to-end `swift pt` smoke (TAPT recipe, e2 S corpus, GPUs 2+3 DDP, accum 4, 10 steps)
| setting | runtime | memory | loss at step 10 | corpus fraction after 10 steps |
|---|---|---|---|---|
| baseline | 69.4 s | 31.9 GiB | 0.7645 | 0.02 |
| `--use_liger_kernel true` | 67.2 s (−3%) | 31.6 GiB | 0.7655 | 0.02 |
| Liger + `--packing true` (binpack, 4096) | 125.2 s | 31.6 GiB | – (different batches) | 0.05 |

- In the real TAPT run Liger gives only ~3%: chunks are short (median ~2.3k characters, mean ~4.6k), so the vocabulary
  logits are small and per-micro-batch overhead dominates.
- Packing processes ~2.5x the corpus per step for ~1.9x the time → **~1.3x throughput** (the logged epoch fraction has two
  decimals, so the range is roughly 1.0–2.0x). It also triples the tokens per optimizer step, so a packed run is not the
  same recipe as the earlier TAPT runs (learning rate / steps would have to be re-chosen).
