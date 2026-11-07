#!/usr/bin/env bash
# Line 2 driver (PostTrain pre-registration v1), Linux #2 GPUs 0,1 (user, round 96). Resumable: a run is skipped when its
# scores.json exists; progress in $PT/status. Waits for the line-3 gate's corpus feature extraction (GPU 1) to finish.
#   cd $C && setsid nohup bash scripts/linux2_run_posttrain.sh > $W/posttrain/driver.log 2>&1 < /dev/null &
# Order: P-TT -> P-MED (7 folds, base) -> P-MED/TT (7 folds, P-TT init) -> evaluation -> bridge P-MED from lm / icpt.
set -u
ENV=/data/ekyang/anaconda3/envs/mht-swift; export PATH=$ENV/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
W=/data1/ekyang/cgh/CODE/mht_work; PT=$W/posttrain; V2=/data1/ekyang/cgh/CODE/Medhypertrace/MedHyperTrace-v2; IC=$W/icpt
BASE=/data1/ekyang/cgh/cache/huggingface_hub/hub/models--Qwen--Qwen3-8B; MED=$IC/hf/icpt/med_ww; OAT=$W/e1e3/oat_src
GPUS=${GPUS:-0,1}; PORT=${PORT:-29571}; mkdir -p $PT
FOLDS="mdagents llm_debate medagents_mc mac_groupchat agentverse triage_agent mam"
st() { echo "[$(date -u +%F' '%T)] $*" >> $PT/status; }
run() {  # $1 out-name, rest = lora_score args
  local o=$PT/$1; shift; [ -s $o/scores.json ] && return 0
  ( cd $V2 && CUDA_VISIBLE_DEVICES=$GPUS python -m torch.distributed.run --nproc_per_node 2 --master_port $PORT -m hgfm.posttrain.lora_score \
      --oat $OAT --med_ww $MED --out $o "$@" > $o.log 2>&1 ) && st "DONE $(basename $o)" || { st "FAIL $(basename $o)"; return 1; }
}
st "START posttrain driver gpus=$GPUS"
until grep -qs "DONE featscorpus_base\|FAIL featscorpus_base" $W/outcome/status; do sleep 120; done
run ptt --model $BASE --train tt --tt_dir $W/e4/tt_ww || exit 1
for f in $FOLDS; do run pmed_$f --model $BASE --train med --fold $f || exit 1; done
for f in $FOLDS; do run pmedtt_$f --model $BASE --train med --fold $f --init_state $PT/ptt/best_state.pt || exit 1; done
( cd $V2 && python -m hgfm.posttrain.posttrain_eval med --base_feats $IC/featsmed_base.pt --med_ww $MED \
    --arm "pmed=$PT/pmed_*" --arm "pmedtt=$PT/pmedtt_*" --arm "ptt=$PT/ptt" --ref "flofo=$IC/med_prefix_base.json:agg" \
    --pairs pmed-flofo pmedtt-pmed ptt-flofo pmed-longest pmedtt-flofo --out $PT/eval_med.json > $PT/eval_med.out 2>&1 ) && st "DONE eval med" || st "FAIL eval med"
( cd $V2 && python -m hgfm.posttrain.posttrain_eval pub --w $W --clusters $W/stage0/cluster_ci/clusters.json --ptt $PT/ptt \
    --out $PT/eval_pub.json > $PT/eval_pub.out 2>&1 ) && st "DONE eval pub" || st "FAIL eval pub"
# bridge (secondary, pre-registration §3): does mid-training help post-training?
for arm in lm icpt; do for f in $FOLDS; do run pmed${arm}_$f --model $IC/$arm/Qwen3-8B-icpt_$arm --train med --fold $f || exit 1; done; done
( cd $V2 && python -m hgfm.posttrain.posttrain_eval med --base_feats $IC/featsmed_base.pt --med_ww $MED \
    --arm "pmed=$PT/pmed_*" --arm "pmedlm=$PT/pmedlm_*" --arm "pmedicpt=$PT/pmedicpt_*" \
    --pairs pmedlm-pmed pmedicpt-pmed pmedicpt-pmedlm --out $PT/eval_bridge.json > $PT/eval_bridge.out 2>&1 ) && st "DONE eval bridge" || st "FAIL eval bridge"
st "ALL DONE"
