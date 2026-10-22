# MS-Swift vs train.py on one full fold (LQD_mac), round 56

**Taxonomy: MedAgentAudit only** (human instances of the LQD_mac fold, n = 67; macro AUROC over codes).

Setup: `scripts/linux2_run_sft_swift.sh` (`GPUS="2 3" FOLDS=LQD_mac VARIANTS="graph text"`), ms-swift 4.6.0 in env `mht-swift`,
same data, same hyper-parameters as `hgfm/llm/train.py` (bs 4 × accum 4, lr 1e-4, projector lr 1e-3, 1 epoch,
max_len 2048, LoRA r 8 / α 32 / dropout 0.1 on q,k,v, gradient checkpointing), `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`.
Started 2026-10-22 19:11 UTC on GPU 2 (graph) and GPU 3 (text) of Linux #2 (RTX A6000 48 GB). Comparison script:
`mht_work/swift_vs_trainpy.py` (paired bootstrap 1000 over the same 67 instances).

## Run facts
| | MS-Swift graph | MS-Swift text | train.py graph | train.py text |
|---|---|---|---|---|
| optimizer steps | 345 | 345 | 345 | 345 |
| wall time (train) | 7,065 s | 6,857 s | 6,670 s | 6,529 s |
| s / step | 20.5 | 19.9 | 19.3 | 18.9 |
| peak reserved memory | 33.4 GB | 33.0 GB | 23.9 GB | 23.6 GB |
| final train loss | 0.341 | 0.374 | — | — |
No OOM. Swift is about 5–6 % slower per step and reserves about 9.5 GB more memory than train.py on this fold
(the 46.3 GB seen in the 20-step smokes was without expandable_segments). Both checkpoints store the projector in
bf16 and the LoRA weights in fp32, identical to train.py's checkpoints.

## Scores
| variant | MS-Swift | train.py | swift − train.py [95% CI] | Spearman of instance scores |
|---|---|---|---|---|
| graph | 0.878 | 0.790 | +0.088 [−0.010, +0.181] | 0.891 |
| text | 0.830 | 0.821 | +0.009 [−0.083, +0.088] | 0.921 |

| engine | graph − text [95% CI] |
|---|---|
| MS-Swift | +0.048 [−0.005, +0.138] |
| train.py | −0.031 [−0.088, +0.012] |

## Reading
- The migration works end to end at full scale: a complete epoch on Qwen3-8B, checkpoint, eval, no OOM.
- The two engines give different models (instance-score Spearman 0.89 / 0.92), as expected: data order (swift's own
  sampler vs `random.shuffle`), autocast vs pure bf16 compute, and the last partial accumulation window differ
  (`hgfm/llm/swift_plugin/README.md`, "Known differences"). Neither score difference is significant on n = 67.
- **The sign of graph − text flips between the two runs on the same fold** (+0.048 vs −0.031). Run-to-run training
  variance on one fold is therefore of the same size as the graph-vs-text effect we have been trying to measure. The C6
  result (graph − text −0.014 on LQD, +0.011 on QD, both CIs containing 0) comes from one training run per fold and
  should be read with that in mind: conclusions about graph tokens need several seeds per fold.
- One fold and one run per engine cannot tell whether swift is systematically better for the graph variant.
