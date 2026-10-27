#!/usr/bin/env bash
# Structure-aware mid-training SAMT v1 on Linux #2 (round 64; design docs/design/SAMT_design_v1.md), end to end:
#   1 verify   samt_featurise reproduces the MAA graph cache the SFT encoder was trained on (abort otherwise)
#   2 cache    featurise the SAMT runs (public + anchors) on GPU
#   3 samt     swift sft, LLM frozen, HGFM v0.2 encoder + projector trained end to end (4 GPUs, DDP)
#   4 export   graph tokens for every MAA run with the SAMT encoder (one file for all folds) + shape check vs QD/LQD_mac
#   5 probe    held-out runs: real vs shuffled vs zeroed graph tokens vs untrained (does the frozen LLM read them?)
#   6 sft      run_sft_swift.sh, graph variant, QD + LQD_mac x seeds 0/1, two configs:
#                samt_v1          SAMT tokens + SAMT projector init, projector lr 1e-4
#                samt_v1_encOnly  SAMT tokens + random projector, projector lr 1e-3 (original recipe)
#              text variant = base seed study (round 60): the LLM is frozen in SAMT, so it is unchanged.
# Every stage is skipped when its output exists, so re-running the script resumes. Status: $D/status.
# Usage: setsid nohup bash linux2_run_samt.sh > $D/driver.log 2>&1 &     (MAX_STEPS=N: SAMT smoke only, stages 1-3)
set -u
ENV=/data/ekyang/anaconda3/envs/mht-swift
export PATH=$ENV/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false USE_HF=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
unset all_proxy ALL_PROXY http_proxy https_proxy
W=/data1/ekyang/cgh/CODE/mht_work; D=${D:-$W/midtrain/samt_v1}; V2=/data1/ekyang/cgh/CODE/Medhypertrace/MedHyperTrace-v2
LM=${LM:-/data1/ekyang/cgh/cache/huggingface_hub/hub/models--Qwen--Qwen3-8B}
MINILM=$(ls -d /data1/ekyang/cgh/cache/huggingface_hub/hub/all-MiniLM-L6-v2/snapshots/* | head -1)
MAA=$W/maa; GPUS=${GPUS:-0,1,2,3}; NP=$(echo $GPUS | tr ',' '\n' | wc -l); MAX_STEPS=${MAX_STEPS:-0}
LR=${LR:-3e-4}; EPOCHS=${EPOCHS:-2}; BS=${BS:-2}; ACC=${ACC:-$((32 / (NP * BS)))}
if [ -n "${WANDB_API_KEY:-}" ] || grep -qs api.wandb.ai ~/.netrc; then REPORT=wandb; else REPORT=tensorboard; fi
st() { echo "[$(date -u +%F' '%T)] $*" >> $D/status; }
die() { st "FAIL $*"; exit 1; }
mkdir -p $D; cd $V2

# 1 verify feature parity with the MAA cache
if ! grep -qs "VERIFY OK" $D/verify.log; then
  st "START verify"
  CUDA_VISIBLE_DEVICES=${GPUS%%,*} python -m hgfm.midtrain.samt_featurise verify $MAA/maa_mas_traj.jsonl $MAA/emb/graphs_v02_gold0.pkl \
    --minilm $MINILM --n 300 > $D/verify.log 2>&1 || die "verify (see verify.log)"
  st "DONE verify $(tail -2 $D/verify.log | head -1)"
fi
# 2 graph cache of the SAMT runs
if [ ! -s $D/cache.pkl ]; then
  st "START cache"
  CUDA_VISIBLE_DEVICES=${GPUS%%,*} python -m hgfm.midtrain.samt_featurise build $D/data/runs.jsonl.gz $D/cache.pkl --minilm $MINILM \
    > $D/cache.log 2>&1 || die "cache"
  st "DONE cache $(tail -1 $D/cache.log)"
fi
# 3 SAMT training
OUT=$D/ckpt; extra=""; [ "$MAX_STEPS" -gt 0 ] && { OUT=$D/smoke_ckpt; extra="--max_steps $MAX_STEPS --save_strategy no"; }
if ! ls -d $OUT/checkpoint-* >/dev/null 2>&1 || [ "$MAX_STEPS" -gt 0 ]; then
  st "START samt gpus=$GPUS bs=$BS accum=$ACC lr=$LR epochs=$EPOCHS max_steps=$MAX_STEPS"
  CUDA_VISIBLE_DEVICES=$GPUS NPROC_PER_NODE=$NP MHT_GRAPH_CACHE=$D/cache.pkl swift sft --external_plugins $V2/hgfm/midtrain/samt_plugin.py \
    --model $LM --model_type graph_enc_lm --template graph_enc --torch_dtype bfloat16 --tuner_type graph_align \
    --learning_rate $LR --lr_scheduler_type cosine --warmup_ratio 0.05 --weight_decay 0 --max_grad_norm 1.0 \
    --per_device_train_batch_size $BS --gradient_accumulation_steps $ACC --num_train_epochs $EPOCHS \
    --max_length 3072 --attn_impl sdpa --gradient_checkpointing true --ddp_find_unused_parameters true \
    --dataset $D/data/train.jsonl --split_dataset_ratio 0 --strict true --dataloader_num_workers 4 \
    --save_strategy epoch --save_only_model true --logging_steps 5 --seed 0 --data_seed 0 \
    --output_dir $OUT --add_version false --report_to $REPORT --run_name samt_v1 $extra > $D/samt.log 2>&1 || die "samt"
  [ "$MAX_STEPS" -gt 0 ] && { st "SMOKE DONE"; exit 0; }
  st "DONE samt"
fi
CK=$(ls -d $D/ckpt/checkpoint-* | sort -V | tail -1)
# 4 MAA graph tokens from the SAMT encoder
if [ ! -s $D/graph_tokens_samt.pt ]; then
  st "START export $CK"
  CUDA_VISIBLE_DEVICES=${GPUS%%,*} python -m hgfm.midtrain.samt_export $CK $MAA/emb/graphs_v02_gold0.pkl $D/graph_tokens_samt.pt \
    --check $MAA/llm/QD/graph_tokens.pt $MAA/llm/LQD_mac/graph_tokens.pt > $D/export.log 2>&1 || die "export"
  st "DONE export $(head -1 $D/export.log)"
fi
# 5 probe on held-out runs (GPU 0, synchronous: an 8B probe next to an 8B SFT job on one A6000 could run out of memory)
if [ ! -s $D/probe_result.json ]; then
  st "START probe"
  ( CUDA_VISIBLE_DEVICES=${GPUS%%,*} python -m hgfm.midtrain.samt_probe --lm $LM --ckpt $CK --cache $D/cache.pkl --probe $D/data/probe.jsonl \
      --out $D/probe_result.json --bs 8 > $D/probe.log 2>&1 && st "DONE probe" || st "FAIL probe" )
fi
# 6 SFT on MAA, graph variant only (text = base seed study)
for cfg in samt_v1 samt_v1_encOnly; do
  Q=$D/sft_queue_$cfg; mkdir -p $Q
  grep -qs "queue empty" $Q/status && continue
  st "START sft $cfg"
  if [ $cfg = samt_v1 ]; then export MHT_PROJ_INIT=$CK/projector.pt; PL=1e-4; else unset MHT_PROJ_INIT; PL=1e-3; fi
  LM=$LM TAG=$cfg GTOK=$D/graph_tokens_samt.pt PROJ_LR=$PL GPUS="${GPUS//,/ }" FOLDS="QD LQD_mac" VARIANTS="graph" SEEDS="0 1" Q=$Q \
    bash $W/run_sft_swift.sh || die "sft $cfg"
  st "DONE sft $cfg $(grep -c DONE $Q/status) done / $(grep -c FAIL $Q/status) failed"
done
unset MHT_PROJ_INIT
st "ALL DONE"
