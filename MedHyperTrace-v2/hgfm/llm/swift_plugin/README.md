# MS-Swift training path for the graph-token LM (`swift_plugin/`)

Trains the same model as `hgfm/llm/train.py` (GraphTokenLM) with `swift sft` (ms-swift **4.6.0**, the version on the
GPU server), so the **graph** and **text** variants run through one identical MS-Swift code path. They differ only in
the data: graph rows carry `<graph>` placeholders plus `graph_refs`; text rows have neither.

| file | role |
|---|---|
| `plugin.py` | `--external_plugins` file. Registers model_type `graph_token_lm`, template `graph_token`, tuner_type `graph_lora`, optimizer `graph_token` |
| `prepare_data.py` | converts a `build_sft.py` jsonl to swift rows (`messages` + `run_id` + `graph_refs` as a JSON string) |
| `eval_swift.py` | `eval.py` for swift checkpoints: logit(yes) − logit(no), same output JSON (works with `hgfm.llm.pool`) |
| `tests/` | `make_synthetic.py` (random fold), `test_equivalence.py` (checks a–c, e), `run_smoke.sh` (check d + e) |

## How graph vectors flow through MS-Swift
1. **Data.** `prepare_data.py` keeps `run_id` and `graph_refs`. The plugin adds both keys to swift's standard dataset
   columns, so the loader keeps them and they reach `Template.encode` as `extra_kwargs`.
2. **Template `graph_token` (`_encode`).** Same code as `train.encode`: the prompt is
   `apply_chat_template([system, user], add_generation_prompt=True, enable_thinking=False)` and the answer is
   `"yes"/"no" + eos`. Loss is on the answer only. If the row is longer than `--max_length`, the head of the prompt is
   cut, and the graph vectors (`hgfm.llm.model.graph_vectors`, read from `$MHT_GRAPH_TOKENS`) whose placeholders were
   cut are dropped from the front (`g[-n_ph:]`). Rows never go past `max_length`, so swift's own truncation never runs.
3. **Collator.** Swift pads `input_ids`, `labels` and `attention_mask` (padding on the right). The plugin adds
   `graph_vecs` [B, G_max, 194] (zero-padded) and `graph_counts` [B], but only when the batch has placeholders.
4. **Model `graph_token_lm`.** The base LM is loaded with `<graph>` added to the tokenizer and the embeddings resized
   to `len(tokenizer)`, exactly like GraphTokenLM. It also gets the submodule `graph_proj` = Linear(194, H) → ReLU →
   Linear(H, H). The model is registered as multimodal, so swift's trainer installs `Template.pre_forward_hook`, the
   hook it uses for VLM image features. In that hook, `_post_encode` builds `inputs_embeds`: it looks up the token
   embeddings and puts `graph_proj(vec)` at each `<graph>` position, in row-major order (= GraphTokenLM.embed). For
   text batches there are no graph tensors, so the hook passes `input_ids` through unchanged.
5. **Tuner `graph_lora`.** PEFT LoRA built from `--lora_rank/--lora_alpha/--lora_dropout/--target_modules` (same
   `LoraConfig` call as GraphTokenLM). The projector is trainable; everything else is frozen. Each checkpoint holds the
   PEFT adapter, `projector.pt` (GraphTokenLM.proj keys) and `graph_token_meta.json`. Like train.py, the resized
   embeddings are not saved. `from_pretrained` loads the adapter and the projector, and `--resume_from_checkpoint`
   uses the same function.
6. **Optimizer `graph_token`.** AdamW with two groups: LoRA at `--learning_rate` (1e-4) and the projector at
   `--aligner_lr` (1e-3), with weight decay from `--weight_decay` (0).

## Commands (one fold `F`, one GPU per fold as in `run_llm_folds.sh`)
```bash
cd /data1/ekyang/cgh/CODE/Medhypertrace            # conda env `ms-swift` (ms-swift 4.6.0)
P=MedHyperTrace-v2/hgfm/llm/swift_plugin; F=/data/mht/<fold>    # F has graph_tokens.pt, sft_graph/, sft_text/
for V in graph text; do python $P/prepare_data.py $F/sft_$V/train.jsonl $F/sft_$V/swift_train.jsonl; done
```
Graph variant (for the text variant, change only `sft_graph` → `sft_text` and the output dir):
```bash
CUDA_VISIBLE_DEVICES=0 USE_HF=1 MHT_GRAPH_TOKENS=$F/graph_tokens.pt \
swift sft --external_plugins $P/plugin.py \
  --model Qwen/Qwen3-8B --model_type graph_token_lm --template graph_token --torch_dtype bfloat16 \
  --tuner_type graph_lora --lora_rank 8 --lora_alpha 32 --lora_dropout 0.1 --target_modules q_proj k_proj v_proj \
  --optimizer graph_token --learning_rate 1e-4 --aligner_lr 1e-3 --weight_decay 0 \
  --lr_scheduler_type constant --warmup_ratio 0 --max_grad_norm 1.0 \
  --per_device_train_batch_size 4 --gradient_accumulation_steps 4 --num_train_epochs 1 \
  --max_length 2048 --gradient_checkpointing true \
  --dataset $F/sft_graph/swift_train.jsonl --split_dataset_ratio 0 --strict true --dataloader_num_workers 4 \
  --save_strategy epoch --save_only_model true --logging_steps 20 --seed 0 \
  --output_dir $F/ckpt_swift_graph --report_to tensorboard
```
Optional flags (documented, not required):
- **W&B:** `--report_to wandb --run_name <fold>_graph` (set `WANDB_PROJECT=medhypertrace` first; `WANDB_MODE=offline`
  if the server has no internet).
- **DeepSpeed:** `--deepspeed zero2` (or `zero3`) under `NPROC_PER_NODE=<n>`. The effective batch is
  bs × accum × n_gpu, so with 4 GPUs use `--gradient_accumulation_steps 1` to keep 16. DeepSpeed needs bf16 mixed
  precision, which is the default with `--torch_dtype bfloat16`.
- `--bf16 false` (single GPU without DeepSpeed) skips autocast. It then reproduces train.py's pure-bf16 numerics.

Evaluate (output has the same format as `eval.py`):
```bash
MHT_GRAPH_TOKENS=$F/graph_tokens.pt python $P/eval_swift.py --lm Qwen/Qwen3-8B \
  --ckpt $F/ckpt_swift_graph/v0-*/checkpoint-<N> --data $F/sft_graph/eval_human.jsonl --out $F/eval_swift_graph.json
```
For the text variant use `sft_text/eval_human.jsonl`. `--zero_shot` scores the untrained model.

## Verified in the sandbox (CPU, fp32, Qwen2.5-0.5B-Instruct, max_len 512, synthetic fold of 20 + 6 rows)
`python tests/make_synthetic.py D && (prepare_data for sft_{graph,text}/{train,eval_human}) &&
python tests/test_equivalence.py --lm <0.5B dir> --syn D --qwen3 <Qwen3-8B tokenizer dir> && bash tests/run_smoke.sh <0.5B dir> D`
- (a) Same weights and the same 4-row batch go through swift's real `Seq2SeqTrainer._prepare_inputs` +
  `compute_loss` (which uses `logits_to_keep`). Loss |Δ| is 4.8e-7 (graph) and 1.2e-6 (text). Gradients of all
  148/144 trainable tensors match: cosine ≥ 0.9999995, max |Δ| / max |g| ≤ 1.6e-5.
- (b) Embeddings at the 51 placeholders equal `graph_proj(vec)` exactly (Δ = 0). All other embeddings equal the token
  embeddings, and the full tensor equals `GraphTokenLM.embed` (Δ = 0).
- (c) `input_ids`, `labels` and graph vectors equal `train.encode` + `train.batches` for every row of both variants:
  at max_len 512 (16/20 rows truncated, 2 vectors dropped) and at max_len 300 (20/20 truncated, 75 dropped). The
  same holds with the Qwen3-8B tokenizer, where `enable_thinking=False` matters.
- (d) `run_smoke.sh` ran 10 steps of `swift sft` for each variant (bs 2 × accum 2 to keep CPU time down; ≈18 s/step).
  Both finished and saved `adapter_model.safetensors` (3.0 MB, LoRA only) and `projector.pt`. Final logged loss was
  0.447 (graph) and 0.320 (text).
- (e) logit(yes) − logit(no) on 6 eval prompts, scored by `eval_swift.py` from each saved checkpoint, matched
  `GraphTokenLM(ckpt=…)` used as in `eval.py`: max |Δ| 9.5e-6 (graph) and 7.6e-6 (text). The `eval_swift.py` CLI
  wrote the same scores to its JSON.

## Known differences from train.py (not semantic, but not bit-identical runs)
- **Data order.** Swift shuffles with its own sampler (`--data_seed`); train.py uses `random.shuffle` with `--seed`.
  The two variants under swift share the same order.
- **Accumulation edge.** train.py drops the micro-batches left after the last full accumulation window. HF Trainer
  takes one more step on them. Swift normalises the loss by the number of answer tokens in the window. Every answer
  is 2 tokens (yes/no + eos), so this equals train.py's mean of micro-batch means for full windows.
- **Precision.** Default swift bf16 uses autocast; train.py uses a pure-bf16 model. `--bf16 false` matches train.py.
- **Initialisation.** Projector initialisation and the resized `<graph>` embedding row are random in both. The row is
  never used as an input. It only enters the softmax normaliser, and it does not affect logit(yes) − logit(no).
- **`enable_thinking`.** The template always passes `enable_thinking=False`. train.py passes it only when the
  tokenizer path contains "qwen3". This is identical for `Qwen/Qwen3-8B`. With a local Qwen3 directory whose name
  lacks "qwen3", train.py would have kept thinking mode.
- **Not supported.** `--packing`, `--padding_free`, `--target_modules all-linear` (pass the list explicitly), and
  generation via `swift infer` (use `eval_swift.py`).
