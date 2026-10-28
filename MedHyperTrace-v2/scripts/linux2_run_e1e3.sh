#!/usr/bin/env bash
# E1 + E2 driver on Linux #2 (round 67; pre-registration docs/design/E1-E3_prereg_v1.md). Resumable; status in $D/status.
#   E1: for proxy in base tapt: OAT extraction (last layer, native <= 32k then YaRN x4 > 32k) of mcp_atlas, who_and_when,
#       traceelephant_gc on its own GPU, then OAT `ood` (MCP-Atlas successes -> WW and -> TEgc, 5 seeds) + `baselines`.
#   E2: success-only (S) and all-outcome (R) LoRA continued pretraining from Qwen3-8B (TAPT recipe, 2 GPUs each, sequential),
#       then per-step NLL of base / tapt / S / R on WW + TEgc (e2_score.py).
set -u
ENV=/data/ekyang/anaconda3/envs/mht-swift; export PATH=$ENV/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false
W=/data1/ekyang/cgh/CODE/mht_work; D=$W/e1e3; V2=/data1/ekyang/cgh/CODE/Medhypertrace/MedHyperTrace-v2
BASE=/data1/ekyang/cgh/cache/huggingface_hub/hub/models--Qwen--Qwen3-8B; TAPT=$W/midtrain/tapt_pilot_v1/Qwen3-8B-tapt_pilot_v1
st() { echo "[$(date -u +%F' '%T)] $*" >> $D/status; }
e1() {  # $1 proxy name, $2 model dir, $3 gpu
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
    CUDA_VISIBLE_DEVICES=$3 python run_pipeline.py baselines --dataset $tgt >> $D/e1_$1_base_$tgt.log 2>&1 || st "WARN e1 baselines $1 $tgt"
  done
  st "DONE e1 $1"
}
mkdir -p $D
# GPU 1 is shared with another user's jobs (and GPU 0 lightly): E1 runs both proxies sequentially on GPU 0
( e1 base $BASE 0 && e1 tapt $TAPT 0 ) &
# E2 training on GPUs 2,3 (sequential: S then R)
for c in S R; do
  if ! grep -qs "DONE merged" $D/e2_$c/status; then
    st "START e2 train $c"
    CORPUS=$D/e2_corpus/$c.jsonl OUT=$D/e2_$c GPUS=2,3 NAME=e2_$c bash $V2/scripts/linux2_run_tapt.sh || { st "FAIL e2 train $c"; break; }
    st "DONE e2 train $c"
  fi
done
wait
# E2 scoring: base/tapt on GPU 0/1, S/R on GPU 2/3
cd $D
score() {  # $1 name $2 model dir $3 gpu
  [ -s $D/e2_scores_$1.json ] || { CUDA_VISIBLE_DEVICES=$3 python $V2/hgfm/e1e3/e2_score.py --oat $D/oat_src --model $2 --out $D/e2_scores_$1.json > $D/e2_score_$1.log 2>&1 && st "DONE e2 score $1" || st "FAIL e2 score $1"; }
}
( score base $BASE 0; score tapt $TAPT 0 ) &
( score S $D/e2_S/Qwen3-8B-e2_S 2 ) &
( score R $D/e2_R/Qwen3-8B-e2_R 3 ) &
wait
st "ALL DONE"
