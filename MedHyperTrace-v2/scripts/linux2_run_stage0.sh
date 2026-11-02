#!/usr/bin/env bash
# Stage 0 driver on Linux #2 (pre-registration docs/design/Stage0_prereg_v1.md). Resumable; status in $S0/status.
#  lane A (GPUs 0,1): wait for nc_shuf (launched separately) -> train nc_irr -> E1 OAT + E4 features for shuf (GPU 0) and
#                     irr (GPU 1) -> BEFT label efficiency n=100 (base, tapt)
#  lane B (GPUs 2,3): train full (flash-attn) -> E1 OAT (GPU 2) + E4 features (GPU 3) for full -> BEFT n=300 (base, tapt)
#  lane C (GPU 1, small): stage-A label efficiency for the existing proxies base / tapt / S / R
#  lane D (GPU 0, small): once the three new feature files exist: stage-A full-label (E4 recipe) and label efficiency
#                         for shuf / irr / full
# Usage: setsid nohup bash linux2_run_stage0.sh > $S0/driver.log 2>&1 &
set -u
ENV=/data/ekyang/anaconda3/envs/mht-swift; export PATH=$ENV/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
W=/data1/ekyang/cgh/CODE/mht_work; S0=$W/stage0; D=$W/e1e3; E4=$W/e4; TW=$E4/tt_ww; HF=$S0/hf/stage0
V2=/data1/ekyang/cgh/CODE/Medhypertrace/MedHyperTrace-v2
BASE=/data1/ekyang/cgh/cache/huggingface_hub/hub/models--Qwen--Qwen3-8B; TAPT=$W/midtrain/tapt_pilot_v1/Qwen3-8B-tapt_pilot_v1
st() { echo "[$(date -u +%F' '%T)] $*" >> $S0/status; }
merged() { grep -qs "DONE merged" $1/status; }
train() {  # $1 name $2 corpus $3 gpus $4 attention $5 torchrun port (two trainings run at once; default 29500 clashes)
  merged $S0/$1 && return 0
  st "START train $1"
  MASTER_PORT=$5 CORPUS=$2 OUT=$S0/$1 GPUS=$3 NAME=$1 ATTN=$4 bash $V2/scripts/linux2_run_tapt.sh && merged $S0/$1 && st "DONE train $1" || { st "FAIL train $1"; return 1; }
}
e1() {  # $1 proxy name $2 model dir $3 gpu   (identical to linux2_run_e1b.sh; OAT dirs live next to E1's in $D)
  local O=$D/oat_$1
  grep -qs "DONE e1 $1" $S0/status && return 0
  [ -d $O ] || cp -r $D/oat_src $O
  ( cd $O
    for ds in mcp_atlas who_and_when traceelephant_gc; do
      CUDA_VISIBLE_DEVICES=$3 OAT_MODEL_NAME=$2 OAT_LAST_LAYER_ONLY=1 OAT_LEN=le32k python run_pipeline.py extract --dataset $ds --model-name $2 >> $S0/e1_$1.log 2>&1 || exit 1
      CUDA_VISIBLE_DEVICES=$3 OAT_MODEL_NAME=$2 OAT_LAST_LAYER_ONLY=1 OAT_LEN=gt32k OAT_YARN=4 python run_pipeline.py extract --dataset $ds --model-name $2 >> $S0/e1_$1.log 2>&1 || exit 1
    done
    for tgt in who_and_when traceelephant_gc; do
      CUDA_VISIBLE_DEVICES=$3 python run_pipeline.py ood --train-dataset mcp_atlas --test-dataset $tgt >> $S0/e1_$1_ood_$tgt.log 2>&1 || exit 1
    done ) && st "DONE e1 $1" || { st "FAIL e1 $1"; return 1; }
}
feats() {  # $1 name $2 model dir $3 gpu
  [ -s $S0/feats_$1.pt ] && return 0
  ( cd $V2 && CUDA_VISIBLE_DEVICES=$3 python -m hgfm.e4.e4_features --oat $D/oat_src --model $2 --out $S0/feats_$1.pt \
      --data who_and_when traceelephant_gc dir:$TW/train=tt_train dir:$TW/val=tt_val dir:$TW/test=tt_test > $S0/feats_$1.log 2>&1 ) \
    && st "DONE feats $1" || { st "FAIL feats $1"; return 1; }
}
beft() {  # $1 name $2 model $3 gpus $4 port $5 n   (subset = draw 0; epochs 10 / 6; accum 4; 1 validation per epoch)
  [ -s $S0/beft_$1/scores.json ] && return 0
  python -c "import json; d=json.load(open('$S0/subsets.json')); json.dump(d['draws']['0']['$5'], open('$S0/ids_n$5.json','w'))"
  local ep=6; [ "$5" = 100 ] && ep=10
  st "START beft $1"
  ( cd $V2 && CUDA_VISIBLE_DEVICES=$3 python -m torch.distributed.run --nproc_per_node 2 --master_port $4 -m hgfm.e4.e4_beft --oat $D/oat_src \
      --model $2 --data_dir $TW --out $S0/beft_$1 --train_ids $S0/ids_n$5.json --epochs $ep --accum 4 --evals_per_epoch 1 >> $S0/beft_$1.log 2>&1 ) \
    && st "DONE beft $1" || { st "FAIL beft $1"; return 1; }
}
laneA() {
  until merged $S0/nc_shuf; do grep -qs FAIL $S0/nc_shuf/status && { st "FAIL nc_shuf"; return 1; }; sleep 60; done
  st "DONE train nc_shuf (separate launch)"
  train nc_irr $HF/NC_irr.jsonl 0,1 sdpa 29532 || return 1
  ( e1 shuf $S0/nc_shuf/Qwen3-8B-nc_shuf 0; feats shuf $S0/nc_shuf/Qwen3-8B-nc_shuf 0 ) &
  ( e1 irr $S0/nc_irr/Qwen3-8B-nc_irr 1; feats irr $S0/nc_irr/Qwen3-8B-nc_irr 1 ) &
  wait
  beft base_n100 $BASE 0,1 29521 100; beft tapt_n100 $TAPT 0,1 29522 100
  st "DONE lane A"
}
laneB() {
  train full $HF/full.jsonl 2,3 flash_attn 29531 || return 1
  ( e1 full $S0/full/Qwen3-8B-full 2 ) & ( feats full $S0/full/Qwen3-8B-full 3 ) & wait
  beft base_n300 $BASE 2,3 29523 300; beft tapt_n300 $TAPT 2,3 29524 300
  st "DONE lane B"
}
laneC() {
  ( cd $V2 && CUDA_VISIBLE_DEVICES=1 python -m hgfm.e4.e4_probe --feats base=$E4/feats_base.pt tapt=$E4/feats_tapt.pt S=$E4/feats_S.pt R=$E4/feats_R.pt \
      --subsets $S0/subsets.json --out $S0/le > $S0/le_existing.log 2>&1 ) && st "DONE le existing" || st "FAIL le existing"
}
laneD() {
  for n in shuf irr full; do
    until [ -s $S0/feats_$n.pt ]; do grep -qs "FAIL feats $n\|FAIL train" $S0/status && { st "lane D: no feats $n, stop"; return 1; }; sleep 120; done
  done
  until grep -qs "le existing" $S0/status; do sleep 60; done   # lane C finished (it writes the base LE files lane D reuses)
  ( cd $V2 && CUDA_VISIBLE_DEVICES=0 python -m hgfm.e4.e4_probe --feats base=$E4/feats_base.pt shuf=$S0/feats_shuf.pt irr=$S0/feats_irr.pt full=$S0/feats_full.pt \
      --out $S0/stageA > $S0/stageA.log 2>&1 ) && st "DONE stageA new" || st "FAIL stageA new"
  ( cd $V2 && CUDA_VISIBLE_DEVICES=0 python -m hgfm.e4.e4_probe --feats base=$E4/feats_base.pt shuf=$S0/feats_shuf.pt irr=$S0/feats_irr.pt full=$S0/feats_full.pt \
      --subsets $S0/subsets.json --out $S0/le > $S0/le_new.log 2>&1 ) && st "DONE le new" || st "FAIL le new"
}
st "START stage0 driver"
[ -s $S0/subsets.json ] || ( cd $V2 && python -m hgfm.stage0.le_subsets --train_dir $TW/train --out $S0/subsets.json >> $S0/driver.log 2>&1 ) || { st "FAIL subsets"; exit 1; }
laneC & laneA & laneB & laneD & wait
st "ALL DONE"
