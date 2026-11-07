#!/usr/bin/env bash
# OutcomeCPT amendment A2, case B (round 97): Base-lm arm on Linux #1, then features at the G0-winning layer.
#   cd /data1/cgh/code/mht && LAYER=<l> setsid nohup bash MedHyperTrace-v2/scripts/linux1_run_base_lm.sh > runs/base_lm_driver.log 2>&1 < /dev/null &
# 1. Train: Qwen3-8B-Base + the lm-arm corpus/recipe (scripts/linux2_run_tapt.sh), 4-GPU ZeRO-3 x accumulation 8
#    (effective batch 32, same 791 steps). ZeRO-3 is the A2 memory fallback: on these shared GPUs (~26 GB free each)
#    plain DDP OOMs on the logits (smoke 18:37 UTC); ZeRO-3 smoke 18:44 UTC: 20 GiB / GPU, ~76 s / step.
#    Full checkpoints every 100 steps, so it resumes after an interruption.
# 2. Features at layer LAYER (same e4_features serialisation):
#    Base-lm on public + medical; Base on the corpus + medical, for gate G re-run (value_gate) on Base(LAYER).
# Resumable: every step is skipped once its output exists. Status: runs/base_lm/driver_status.
set -u
R=/data1/cgh/code/mht; ENV=/home/cgh/anaconda3/envs/ms-swift
export PATH=$ENV/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True HF_HOME=/data1/cgh/cache/huggingface
unset all_proxy ALL_PROXY http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
V2=$R/MedHyperTrace-v2; WK=$R/work; D=$WK/e1e3; TW=$WK/e4/tt_ww; MED=$WK/icpt/hf/icpt/med_ww; COR=$WK/outcome/corpus
BASEM=/data1/cgh/cache/huggingface/models/Qwen3-8B-Base; O=$R/runs/base_lm; L=${LAYER:?set LAYER}
PUB="who_and_when traceelephant_gc dir:$TW/train=tt_train dir:$TW/val=tt_val dir:$TW/test=tt_test"
mkdir -p $O; st() { echo "[$(date -u +%F' '%T)] $*" >> $O/driver_status; }
st "START base_lm driver LAYER=$L"
M=$O/Qwen3-8B-base_lm
if [ ! -d $M ]; then
  ENV=$ENV LM=$BASEM CORPUS=$R/xfer/lm.jsonl OUT=$O GPUS=0,1,2,3 NAME=base_lm DS=zero3 SAVE_STEPS=100 \
    bash $V2/scripts/linux2_run_tapt.sh || { st "FAIL train (see $O/status, $O/tapt.log)"; exit 1; }
fi
[ -d $M ] || { st "FAIL merged model missing"; exit 1; }
st "DONE train + merge"
fx() {  # $1 model $2 output stem $3 gpu $4 data spec (word-split on purpose)
  [ -s ${2}_L$L.pt ] && return 0
  ( cd $V2 && CUDA_VISIBLE_DEVICES=$3 python -m hgfm.e4.e4_features --oat $D/oat_src --model $1 --out $2.pt --layers $L \
      --data $4 > $2.log 2>&1 ) && st "DONE feats $(basename $2)_L$L" || { st "FAIL feats $(basename $2)"; return 1; }
}
( fx $M $O/pub_blm 0 "$PUB" && fx $M $O/med_blm 0 "dir:$MED=med" ) &
( fx $BASEM $O/med_b 1 "dir:$MED=med" && fx $BASEM $O/corpus_b 1 "dir:$COR=corpus" ) &
wait
for f in pub_blm med_blm med_b corpus_b; do [ -s $O/${f}_L$L.pt ] || { st "FAIL missing ${f}_L$L"; exit 1; }; done
[ -s $O/gate_b_L$L.json ] || ( cd $V2 && CUDA_VISIBLE_DEVICES= python -m hgfm.outcome.value_gate --corpus_feats $O/corpus_b_L$L.pt --corpus_ww $COR \
    --med_feats $O/med_b_L$L.pt --med_ww $MED --out $O/gate_b_L$L.json > $O/gate_b_L$L.out 2>&1 ) && st "DONE gate b_L$L" || st "FAIL gate b_L$L"
st "ALL DONE (copy pub_blm / med_blm features to Linux #2 for med_eval / stage A against G0's b_L$L)"
