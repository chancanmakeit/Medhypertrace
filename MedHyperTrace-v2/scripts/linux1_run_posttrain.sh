#!/usr/bin/env bash
# Line 2 driver, Linux #1 copy (round 99). The user moved the remaining folds off Linux #2.
# Identical steps and arguments to scripts/linux2_run_posttrain.sh, except:
#   - paths are Linux #1 ones;
#   - 4 GPUs x --accum 8 instead of 2 x 16, so the effective batch (32) is unchanged.
# P-TT and pmed_mdagents were trained on Linux #2 and copied here; scores.json exists, so they are skipped.
#   cd /data1/cgh/code/mht && setsid nohup bash MedHyperTrace-v2/scripts/linux1_run_posttrain.sh > runs/posttrain_driver.log 2>&1 < /dev/null &
# Order: P-TT -> P-MED (7 folds, base) -> P-MED/TT (7 folds, P-TT init) -> evaluation -> bridge P-MED from lm / icpt.
set -u
ENV=/home/cgh/anaconda3/envs/ms-swift; export PATH=$ENV/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
R=/data1/cgh/code/mht; W=$R/work; PT=$W/posttrain; V2=$R/MedHyperTrace-v2; IC=$W/icpt; unset all_proxy ALL_PROXY
BASE=$R/models/it; MED=$IC/hf/icpt/med_ww; OAT=$W/e1e3/oat_src
GPUS=${GPUS:-0,1,2,3}; NP=${NP:-4}; ACC=${ACC:-8}; PORT=${PORT:-29581}; mkdir -p $PT
FOLDS="mdagents llm_debate medagents_mc mac_groupchat agentverse triage_agent mam"
st() { echo "[$(date -u +%F' '%T)] $*" >> $PT/status; }
run() {  # $1 out-name, rest = lora_score args
  local o=$PT/$1; shift; [ -s $o/scores.json ] && return 0
  ( cd $V2 && CUDA_VISIBLE_DEVICES=$GPUS python -m torch.distributed.run --nproc_per_node $NP --master_port $PORT -m hgfm.posttrain.lora_score \
      --oat $OAT --med_ww $MED --out $o --accum $ACC "$@" > $o.log 2>&1 ) && st "DONE $(basename $o)" || { st "FAIL $(basename $o)"; return 1; }
}
st "START posttrain driver (Linux #1) gpus=$GPUS np=$NP accum=$ACC"
for m in $BASE $R/models/lm $R/models/icpt; do cat $m/*.safetensors > /dev/null; done; st "weights warmed"
run ptt --model $BASE --train tt --tt_dir $W/e4/tt_ww || exit 1
for f in $FOLDS; do run pmed_$f --model $BASE --train med --fold $f || exit 1; done
for f in $FOLDS; do run pmedtt_$f --model $BASE --train med --fold $f --init_state $PT/ptt/best_state.pt || exit 1; done
( cd $V2 && python -m hgfm.posttrain.posttrain_eval med --base_feats $IC/featsmed_base.pt --med_ww $MED \
    --arm "pmed=$PT/pmed_*" --arm "pmedtt=$PT/pmedtt_*" --arm "ptt=$PT/ptt" --ref "flofo=$IC/med_prefix_base.json:agg" \
    --pairs pmed-flofo pmedtt-pmed ptt-flofo pmed-longest pmedtt-flofo --out $PT/eval_med.json > $PT/eval_med.out 2>&1 ) && st "DONE eval med" || st "FAIL eval med"
( cd $V2 && python -m hgfm.posttrain.posttrain_eval pub --w $W --clusters $W/stage0/cluster_ci/clusters.json --ptt $PT/ptt \
    --out $PT/eval_pub.json > $PT/eval_pub.out 2>&1 ) && st "DONE eval pub" || st "FAIL eval pub"
# bridge (secondary, pre-registration §3): does mid-training help post-training?
for arm in lm icpt; do for f in $FOLDS; do run pmed${arm}_$f --model $R/models/$arm --train med --fold $f || exit 1; done; done
( cd $V2 && python -m hgfm.posttrain.posttrain_eval med --base_feats $IC/featsmed_base.pt --med_ww $MED \
    --arm "pmed=$PT/pmed_*" --arm "pmedlm=$PT/pmedlm_*" --arm "pmedicpt=$PT/pmedicpt_*" \
    --pairs pmedlm-pmed pmedicpt-pmed pmedicpt-pmedlm --out $PT/eval_bridge.json > $PT/eval_bridge.out 2>&1 ) && st "DONE eval bridge" || st "FAIL eval bridge"
st "ALL DONE"
