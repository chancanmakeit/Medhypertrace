#!/usr/bin/env bash
# E1b (round 68, pre-registration addendum docs/design/E1-E3_prereg_v1.md §E1b): OAT with the E2 checkpoints S and R as
# proxy LLM, exactly the E1 pipeline (same patched OAT, SDPA attention as in E1 so the proxies stay comparable).
# S on GPU 2, R on GPU 3, in parallel. Resumable; status in $D/status.
set -u
ENV=/data/ekyang/anaconda3/envs/mht-swift; export PATH=$ENV/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false
W=/data1/ekyang/cgh/CODE/mht_work; D=$W/e1e3
st() { echo "[$(date -u +%F' '%T)] $*" >> $D/status; }
e1() {  # $1 proxy name, $2 model dir, $3 gpu  (identical to linux2_run_e1e3.sh)
  local O=$D/oat_$1
  [ -d $O ] || cp -r $D/oat_src $O
  cd $O
  for ds in mcp_atlas who_and_when traceelephant_gc; do
    CUDA_VISIBLE_DEVICES=$3 OAT_MODEL_NAME=$2 OAT_LAST_LAYER_ONLY=1 OAT_LEN=le32k python run_pipeline.py extract --dataset $ds --model-name $2 >> $D/e1_$1.log 2>&1 || { st "FAIL e1 extract $1 $ds"; return 1; }
    CUDA_VISIBLE_DEVICES=$3 OAT_MODEL_NAME=$2 OAT_LAST_LAYER_ONLY=1 OAT_LEN=gt32k OAT_YARN=4 python run_pipeline.py extract --dataset $ds --model-name $2 >> $D/e1_$1.log 2>&1 || { st "FAIL e1 extract-yarn $1 $ds"; return 1; }
    st "e1 $1 extracted $ds ($(ls outputs/hidden_states_mean/$ds | wc -l) files)"
  done
  for tgt in who_and_when traceelephant_gc; do
    CUDA_VISIBLE_DEVICES=$3 python run_pipeline.py ood --train-dataset mcp_atlas --test-dataset $tgt >> $D/e1_$1_ood_$tgt.log 2>&1 || { st "FAIL e1 ood $1 $tgt"; return 1; }
  done
  st "DONE e1 $1"
}
st "START e1b (proxies S, R)"
( e1 S $D/e2_S/Qwen3-8B-e2_S 2 ) &
( e1 R $D/e2_R/Qwen3-8B-e2_R 3 ) &
wait
st "E1B DONE"
