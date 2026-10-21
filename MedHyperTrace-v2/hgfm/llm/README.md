# LLM layer of MedHyperTrace-v2 (C6 + simplest C7), round 38

HyperG / GraphGPT-style graph soft tokens: the HGFM v0.2 hypergraph encoder produces one vector per step node and per
interaction hyperedge; a 2-layer projector maps them into the LLM's embedding space; each `<graph>` placeholder in the
instruction is replaced by its vector. The LLM is frozen except LoRA on q/k/v (r=8, alpha=32, dropout 0.1, as in HyperG).
The answer is constrained to yes/no; score = logit(yes) − logit(no).

```
MAA mas-traj/1 ──► HGFM v0.2 encoder (per fold, never sees test MAS) ──► graph_tokens.pt  (h: steps×192, m: edges×192)
          └──────► build_sft: question + final answer + K candidate steps "<graph> + excerpt" + M hyperedges "<graph> instr"
                              + official code definition/guideline + "Target step … present? yes/no"
                   ──► train (LoRA + projector, CE on answer token) ──► eval (400 human instances, LQD pooled)
```

| file | stage |
|---|---|
| `export_graph_emb.py` | 1. train the encoder on a fold's train part, export node/edge vectors + encoder step probabilities for train and test runs |
| `build_sft.py` | 2. instruction data. Train = LLM-auditor labels of TRAIN runs (balanced per code); eval = human instances in TEST runs. `--no_graph` = same prompts, no graph tokens (text-only baseline); `--no_excerpt` = graph-only |
| `model.py` | `GraphTokenLM`: placeholder replacement, projector, LoRA; logits computed only at answer positions (memory) |
| `train.py` | 3. LoRA + projector training (`--grad_ckpt` recommended) |
| `eval.py` | 4. per-fold human AUROC; `--zero_shot` = untrained LLM on text prompts |
| `pool.py` | pool the 6 LQD folds exactly like `results/phase1_maa` |
| `../../scripts/prepare_maa.sh` | stages 0–2 end to end (download MAA release, convert, align human labels, embed, export, build SFT) |
| `../../scripts/run_llm_folds.sh` | stages 3–4 for all folds, one fold per GPU, then pooling |

## Running on the 4×A6000 server

```bash
cd MedHyperTrace-v2
pip install -r requirements.txt            # torch, transformers>=4.56, peft, sentence-transformers, scikit-learn
bash scripts/prepare_maa.sh  /data/mht                     # ~1–2 h, mostly CPU (embedding 86k texts; faster on GPU)
bash scripts/run_llm_folds.sh /data/mht Qwen/Qwen3-8B graph     # main model
bash scripts/run_llm_folds.sh /data/mht Qwen/Qwen3-8B text      # same prompts without graph tokens
bash scripts/run_llm_folds.sh /data/mht Qwen/Qwen3-8B zeroshot  # untrained LLM reference
```
Comparisons that matter (paired bootstrap over the same 400 instances, as in phase 1): graph vs text (does the hypergraph
add anything once an LLM reads the text?), text vs encoder-only v0.2 (0.645), and all vs the auditor (0.886, the ceiling
we are distilling from — it reads the whole trace with a strong LLM).

**Rough cost (not measured on GPU yet):** Qwen3-8B bf16 ≈ 16 GB + activations at 2048 tokens with gradient checkpointing
≈ 25–30 GB per A6000, bs 4. 20k training pairs per fold ≈ 2–3 h per fold; 7 folds on 4 GPUs ≈ 2 rounds ≈ 5–6 h per
variant. Start with `prepare_maa.sh /data/mht "" 8000` (8k pairs per fold) for a first pass of ~1 h per fold.
Smaller first try: `Qwen/Qwen3-4B` or `Qwen/Qwen2.5-7B-Instruct`.

## What was verified in the sandbox (CPU, 7 GB RAM)
End-to-end smoke test on a QD subsample (600 train / 300 test runs) with `Qwen/Qwen2.5-0.5B-Instruct`, fp32:
encoder export → SFT build (graph and text) → 12-step training → eval → pooling all run; graph-token/placeholder counts
and edge order are asserted. The smoke AUROC (n=20) is meaningless and not reported.

## Known limits / next
- Training labels are auditor labels (weak); human labels are only used for evaluation.
- No self-supervised pretraining of the encoder yet (C5); the encoder is the phase-1 supervised one.
- Responsibility layer (which step caused the failure) needs the medical-aegis anchor data, not MAA.
