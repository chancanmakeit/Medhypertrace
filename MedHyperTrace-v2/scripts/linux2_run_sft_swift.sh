#!/usr/bin/env bash
# MS-Swift SFT for the graph-token LM on Linux #2 (round 55: SFT migrated from hgfm/llm/train.py to `swift sft`).
# Same queue design as linux2_run_c6.sh: one worker per GPU pulling "<fold> <variant>" lines from $Q/jobs.
# Hyper-parameters equal train.py's defaults (effective batch 16, lr 1e-4, projector lr 1e-3, 1 epoch, max_len 2048,
# LoRA r 8 / alpha 32 / dropout 0.1 on q,k,v, grad checkpointing); see hgfm/llm/swift_plugin/README.md.
# Batch: BS x ACCUM, default 4 x 4 as in train.py (2 x 8 is the same objective: every answer is 2 tokens and swift
# normalises per accumulation window). Swift's logged memory(GiB) is max *reserved* memory: 46.3 GB with both 4x4 and
# 2x8 in 20-step Qwen3-8B smokes (train.py: 26.7 GB reserved); expandable_segments is set to limit fragmentation.
# Usage:  GPUS="2 3" FOLDS="LQD_mac QD" VARIANTS="graph text" bash linux2_run_sft_swift.sh
#         MAX_STEPS=20 (optional) -> short run for throughput / memory checks (no eval, output dir suffixed _smokeN)
# Outputs per fold dir F: F/ckpt_swift_<tag>_<v>/checkpoint-*/ (adapter + projector.pt), F/eval_swift_<tag>_<v>.json
# (same format as eval.py, so hgfm.llm.pool / compare scripts work with tag "swift_<tag>").
# Logging: wandb if the server is logged in (WANDB_API_KEY set or api.wandb.ai in ~/.netrc), else tensorboard.
set -u
ENV=/data/ekyang/anaconda3/envs/mht-swift
export PATH=$ENV/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false USE_HF=1 WANDB_PROJECT=${WANDB_PROJECT:-medhypertrace} PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
unset all_proxy ALL_PROXY http_proxy https_proxy
LM=${LM:-/data1/ekyang/cgh/cache/huggingface_hub/hub/models--Qwen--Qwen3-8B}; TAG=$(basename $LM)
L=${L:-/data1/ekyang/cgh/CODE/mht_work/maa/llm}; Q=${Q:-/data1/ekyang/cgh/CODE/mht_work/swift_queue}
V2=/data1/ekyang/cgh/CODE/Medhypertrace/MedHyperTrace-v2; P=$V2/hgfm/llm/swift_plugin
GPUS=${GPUS:-"2 3"}; FOLDS=${FOLDS:-"LQD_colacare LQD_healthcareagent LQD_mac LQD_mdagents LQD_medagent LQD_reconcile QD"}
VARIANTS=${VARIANTS:-"graph text"}; MAX_STEPS=${MAX_STEPS:-0}; BS=${BS:-4}; ACCUM=${ACCUM:-4}
if [ -n "${WANDB_API_KEY:-}" ] || grep -qs api.wandb.ai ~/.netrc; then REPORT=wandb; else REPORT=tensorboard; fi
mkdir -p $Q/logs; cd $V2
if [ ! -s $Q/jobs ]; then for f in $FOLDS; do for v in $VARIANTS; do echo "$f $v"; done; done > $Q/jobs; fi

job() {  # $1 gpu, $2 fold, $3 variant
  local g=$1 f=$2 v=$3 d=$L/$2 out ck extra=""
  out=$d/ckpt_swift_${TAG}_$v; [ "$MAX_STEPS" -gt 0 ] && { out=${out}_smoke${MAX_STEPS}_bs$BS; extra="--max_steps $MAX_STEPS --save_strategy no"; }
  [ -s $d/sft_$v/swift_train.jsonl ] || python $P/prepare_data.py $d/sft_$v/train.jsonl $d/sft_$v/swift_train.jsonl || return 1
  if ! ls -d $out/checkpoint-* >/dev/null 2>&1 || [ "$MAX_STEPS" -gt 0 ]; then
    CUDA_VISIBLE_DEVICES=$g MHT_GRAPH_TOKENS=$d/graph_tokens.pt swift sft --external_plugins $P/plugin.py \
      --model $LM --model_type graph_token_lm --template graph_token --torch_dtype bfloat16 \
      --tuner_type graph_lora --lora_rank 8 --lora_alpha 32 --lora_dropout 0.1 --target_modules q_proj k_proj v_proj \
      --optimizer graph_token --learning_rate 1e-4 --aligner_lr 1e-3 --weight_decay 0 \
      --lr_scheduler_type constant --warmup_ratio 0 --max_grad_norm 1.0 \
      --per_device_train_batch_size $BS --gradient_accumulation_steps $ACCUM --num_train_epochs 1 \
      --max_length 2048 --gradient_checkpointing true \
      --dataset $d/sft_$v/swift_train.jsonl --split_dataset_ratio 0 --strict true --dataloader_num_workers 4 \
      --save_strategy epoch --save_only_model true --logging_steps 20 --seed 0 --data_seed 0 \
      --output_dir $out --add_version false --report_to $REPORT --run_name ${f}_${v} $extra || return 1
  fi
  [ "$MAX_STEPS" -gt 0 ] && return 0
  ck=$(ls -d $out/checkpoint-* | sort -V | tail -1)
  [ -s $d/eval_swift_${TAG}_$v.json ] || CUDA_VISIBLE_DEVICES=$g MHT_GRAPH_TOKENS=$d/graph_tokens.pt python $P/eval_swift.py \
      --lm $LM --ckpt $ck --data $d/sft_$v/eval_human.jsonl --out $d/eval_swift_${TAG}_$v.json
}
worker() {  # $1 gpu
  while true; do
    exec 8>$Q/lock; flock 8; J=$(head -1 $Q/jobs); [ -n "$J" ] && sed -i 1d $Q/jobs; flock -u 8
    [ -z "$J" ] && break
    set -- $1 $J; echo "[$(date -u +%F' '%T)] GPU$1 START $2 $3 (report_to=$REPORT max_steps=$MAX_STEPS bs=$BS x $ACCUM)" >> $Q/status
    if job $1 $2 $3 > $Q/logs/$2_$3${MAX_STEPS/#0/}_bs$BS.log 2>&1; then echo "[$(date -u +%F' '%T)] GPU$1 DONE $2 $3" >> $Q/status
    else echo "[$(date -u +%F' '%T)] GPU$1 FAIL $2 $3" >> $Q/status; fi
  done
}
for g in $GPUS; do worker $g & done; wait
echo "[$(date -u +%F' '%T)] queue empty" >> $Q/status
