#!/usr/bin/env bash
# Mid-training (TAPT) pilot on Linux #2 (round 62): LoRA continued pre-training of Qwen3-8B on the trajectory corpus
# built by hgfm/midtrain/build_corpus.py (text-only jsonl {"text"}, chunks <= 4096 tokens at step boundaries;
# batch 1 per GPU, so no packing / padding is needed), then merge the LoRA into the base weights so the
# SFT driver (linux2_run_sft_swift.sh, LM=<merged dir>) can train its own graph/text LoRA on top.
# Usage: CORPUS=<train.jsonl> OUT=<run dir> GPUS=0,1,2,3 bash linux2_run_tapt.sh   (setsid nohup; log in $OUT/tapt.log)
#        MAX_STEPS=10 for a throughput / memory smoke test (no merge).
#        ATTN: attention kernel, default flash_attn (flash-attn 2.7.4.post1 installed round 68; LoRA fwd+bwd 1.7x faster at
#        4k tokens, 2.4x at 8k, scripts/bench_flash_attn.py). Runs before round 68 (tapt_pilot_v1, e2_S, e2_R) used ATTN=sdpa.
#        LIGER=true: Liger kernel 0.7.0 (RMSNorm / RoPE / SwiGLU / fused linear cross-entropy; round 72, LoRA step +16%,
#        memory -24..-36%, same loss / gradients, scripts/bench_train_speed.py). Default false (all earlier runs).
#        MODE=sft (round 86, interaction-CPT arm): `swift sft` on a {"messages"} jsonl, loss on the assistant turn only;
#        every other argument identical. Default pt (every earlier run).
set -u
ENV=/data/ekyang/anaconda3/envs/mht-swift
export PATH=$ENV/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false USE_HF=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
unset all_proxy ALL_PROXY http_proxy https_proxy
LM=${LM:-/data1/ekyang/cgh/cache/huggingface_hub/hub/models--Qwen--Qwen3-8B}
CORPUS=${CORPUS:?}; OUT=${OUT:?}; GPUS=${GPUS:-0,1,2,3}; MAX_STEPS=${MAX_STEPS:-0}; NAME=${NAME:-tapt_pilot_v1}   # NAME: round 67 (E2), default unchanged
NP=$(echo $GPUS | tr ',' '\n' | wc -l); ACC=${ACC:-$((32 / NP))}
if [ -n "${WANDB_API_KEY:-}" ] || grep -qs api.wandb.ai ~/.netrc; then REPORT=wandb; else REPORT=tensorboard; fi
mkdir -p $OUT; extra=""; [ "$MAX_STEPS" -gt 0 ] && extra="--max_steps $MAX_STEPS --save_strategy no"
echo "[$(date -u +%F' '%T)] START tapt gpus=$GPUS np=$NP accum=$ACC max_steps=$MAX_STEPS" >> $OUT/status
CUDA_VISIBLE_DEVICES=$GPUS NPROC_PER_NODE=$NP swift ${MODE:-pt} \
  --model $LM --model_type qwen3 --template qwen3 --torch_dtype bfloat16 --tuner_type lora --lora_rank 64 --lora_alpha 128 --lora_dropout 0.05 \
  --target_modules all-linear --learning_rate 1e-4 --lr_scheduler_type cosine --warmup_ratio 0.03 --weight_decay 0.01 \
  --per_device_train_batch_size 1 --gradient_accumulation_steps $ACC --num_train_epochs 1 \
  --max_length 4096 --attn_impl ${ATTN:-flash_attn} --use_liger_kernel ${LIGER:-false} ${PACK:+--packing true} --gradient_checkpointing true --dataset $CORPUS --split_dataset_ratio 0.005 \
  --dataloader_num_workers 4 --dataset_num_proc 8 --save_strategy epoch --save_only_model true --logging_steps 5 \
  --seed 0 --data_seed 0 --output_dir $OUT/ckpt --add_version false --report_to $REPORT --run_name $NAME $extra \
  >> $OUT/tapt.log 2>&1 || { echo "[$(date -u +%F' '%T)] FAIL tapt" >> $OUT/status; exit 1; }
[ "$MAX_STEPS" -gt 0 ] && { echo "[$(date -u +%F' '%T)] SMOKE DONE" >> $OUT/status; exit 0; }
CK=$(ls -d $OUT/ckpt/checkpoint-* | sort -V | tail -1)
CUDA_VISIBLE_DEVICES=${GPUS%%,*} swift export --adapters $CK --merge_lora true --output_dir $OUT/Qwen3-8B-$NAME >> $OUT/tapt.log 2>&1 \
  || { echo "[$(date -u +%F' '%T)] FAIL merge" >> $OUT/status; exit 1; }
echo "[$(date -u +%F' '%T)] DONE merged=$OUT/Qwen3-8B-$NAME" >> $OUT/status
