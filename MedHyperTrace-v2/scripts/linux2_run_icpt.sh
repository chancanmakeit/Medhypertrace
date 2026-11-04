#!/usr/bin/env bash
# Interaction-CPT experiment driver on Linux #2 (pre-registration docs/design/InteractionCPT_prereg_v1.md). Resumable:
# every step is skipped when its output exists; progress in $IC/status ("FAIL ..." lines stop the lane that wrote them).
#   setsid nohup bash scripts/linux2_run_icpt.sh > $IC/driver.log 2>&1 &
# lane 0 (GPU 3, immediately): base features on the medical eval parents (prefix + query interfaces) -> med_eval base
# then, once $IC/hf/icpt/corpus/READY exists (corpus built in the sandbox from M-new + M-anchor + public, via HF):
# lane L (GPUs 0,1): train LM-CPT (swift pt)  -> features (prefix + query; public + medical)
# lane I (GPUs 2,3): train interaction-CPT (swift sft, MODE=sft) -> same features
# final (GPU 0): stage-A full-label + label efficiency on public (both interfaces, base / lm / icpt); med_eval for the arms
#                and the pre-registered comparisons.
set -u
ENV=/data/ekyang/anaconda3/envs/mht-swift; export PATH=$ENV/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
W=/data1/ekyang/cgh/CODE/mht_work; IC=$W/icpt; D=$W/e1e3; TW=$W/e4/tt_ww; V2=/data1/ekyang/cgh/CODE/Medhypertrace/MedHyperTrace-v2
BASE=/data1/ekyang/cgh/cache/huggingface_hub/hub/models--Qwen--Qwen3-8B
MED=$IC/hf/icpt/med_ww; COR=$IC/hf/icpt/corpus; mkdir -p $IC
PUB="who_and_when traceelephant_gc dir:$TW/train=tt_train dir:$TW/val=tt_val dir:$TW/test=tt_test"
st() { echo "[$(date -u +%F' '%T)] $*" >> $IC/status; }
merged() { grep -qs "DONE merged" $1/status; }
fx() {   # $1 module (e4.e4_features | icpt.feat_query) $2 model $3 out $4 gpu $5 data specs
  [ -s $3 ] && return 0
  ( cd $V2 && CUDA_VISIBLE_DEVICES=$4 python -m hgfm.$1 --oat $D/oat_src --model $2 --out $3 --data $5 > $3.log 2>&1 ) \
    && st "DONE $(basename $3)" || { st "FAIL $(basename $3)"; return 1; }
}
medscore() {   # $1 name $2 feats $3 out
  [ -s $3 ] && return 0
  ( cd $V2 && CUDA_VISIBLE_DEVICES= python -m hgfm.icpt.med_eval score --feats $2 --ww $MED --out $3 > $3.log 2>&1 ) \
    && st "DONE medscore $1" || { st "FAIL medscore $1"; return 1; }
}
train() {  # $1 arm $2 corpus $3 gpus $4 port $5 mode
  merged $IC/$1 && return 0
  st "START train $1"
  MASTER_PORT=$4 MODE=$5 CORPUS=$2 OUT=$IC/$1 GPUS=$3 NAME=icpt_$1 ATTN=flash_attn bash $V2/scripts/linux2_run_tapt.sh \
    && merged $IC/$1 && st "DONE train $1" || { st "FAIL train $1"; return 1; }
}
arm() {   # $1 arm $2 corpus $3 gpus "a,b" $4 port $5 mode
  local g1=${3%%,*} g2=${3##*,}
  train $1 $2 $3 $4 $5 || return 1
  local M=$IC/$1/Qwen3-8B-icpt_$1
  ( fx e4.e4_features $M $IC/feats_$1.pt $g1 "$PUB" && fx e4.e4_features $M $IC/featsmed_$1.pt $g1 "dir:$MED=med" ) &
  ( fx icpt.feat_query $M $IC/featsq_$1.pt $g2 "$PUB" && fx icpt.feat_query $M $IC/featsqmed_$1.pt $g2 "dir:$MED=med" ) &
  wait
  for f in feats featsmed featsq featsqmed; do [ -s $IC/${f}_$1.pt ] || { st "FAIL arm $1 ($f missing)"; return 1; }; done
  st "DONE arm $1"
}
lane0() {
  fx e4.e4_features $BASE $IC/featsmed_base.pt 3 "dir:$MED=med" && fx icpt.feat_query $BASE $IC/featsqmed_base.pt 3 "dir:$MED=med" || return 1
  medscore base_prefix $IC/featsmed_base.pt $IC/med_prefix_base.json; medscore base_query $IC/featsqmed_base.pt $IC/med_query_base.json
  st "DONE lane 0"
}
final() {
  until grep -qs "DONE arm lm" $IC/status && grep -qs "DONE arm icpt" $IC/status && grep -qs "DONE lane 0" $IC/status; do
    grep -qs "FAIL" $IC/status && { st "final: FAIL seen, stop"; return 1; }; sleep 300; done
  until [ -s $IC/diag/featsq_base.pt ]; do sleep 300; done   # base query features on public come from the interface diagnostic
  for I in prefix query; do
    if [ $I = prefix ]; then B=$W/e4/feats_base.pt; p=feats; else B=$IC/diag/featsq_base.pt; p=featsq; fi
    [ -s $IC/stageA_$I/e4a_linear.json ] || ( cd $V2 && CUDA_VISIBLE_DEVICES=0 python -m hgfm.e4.e4_probe --feats base=$B lm=$IC/${p}_lm.pt icpt=$IC/${p}_icpt.pt \
        --out $IC/stageA_$I > $IC/stageA_$I.log 2>&1 ) && st "DONE stageA $I" || st "FAIL stageA $I"
    [ -s $IC/le_$I/le_linear_icpt.json ] || ( cd $V2 && CUDA_VISIBLE_DEVICES=0 python -m hgfm.e4.e4_probe --feats base=$B lm=$IC/${p}_lm.pt icpt=$IC/${p}_icpt.pt \
        --subsets $W/stage0/subsets.json --out $IC/le_$I > $IC/le_$I.log 2>&1 ) && st "DONE le $I" || st "FAIL le $I"
    medscore lm_$I $IC/${p}med_lm.pt $IC/med_${I}_lm.json; medscore icpt_$I $IC/${p}med_icpt.pt $IC/med_${I}_icpt.json
    ( cd $V2 && python -m hgfm.icpt.med_eval compare --arms base=$IC/med_${I}_base.json lm=$IC/med_${I}_lm.json icpt=$IC/med_${I}_icpt.json \
        --out $IC/med_compare_$I.json > $IC/med_compare_$I.out 2>&1 ) && st "DONE compare $I" || st "FAIL compare $I"
  done
  st "ALL DONE"
}
st "START icpt driver"
lane0 &
( until [ -s $COR/READY ]; do sleep 300; done; st "corpus ready"
  arm lm $COR/lm.jsonl 0,1 29541 pt & arm icpt $COR/icpt.jsonl 2,3 29542 sft & wait ) &
final &
wait
