#!/usr/bin/env bash
# E4 driver on Linux #2 (pre-registration docs/design/E4_prereg_v1.md). Status in $E4/status. Resumable stage by stage.
#  1 wait for the four stage-A feature files (hgfm.e4.e4_features, launched separately)
#  2 stage A probe (GPU 0, small) -- in the background, in parallel with stage B
#  3 stage B smoke test (8 trajectories, GPUs 0,1), then BEFT base (GPUs 0,1) and BEFT tapt (GPUs 2,3) in parallel
#  4 stage B evaluation; "ALL DONE"
set -u
ENV=/data/ekyang/anaconda3/envs/mht-swift; export PATH=$ENV/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
W=/data1/ekyang/cgh/CODE/mht_work; D=$W/e1e3; E4=$W/e4; V2=/data1/ekyang/cgh/CODE/Medhypertrace/MedHyperTrace-v2; TW=$E4/tt_ww
BASE=/data1/ekyang/cgh/cache/huggingface_hub/hub/models--Qwen--Qwen3-8B; TAPT=$W/midtrain/tapt_pilot_v1/Qwen3-8B-tapt_pilot_v1
st() { echo "[$(date -u +%F' '%T)] $*" >> $E4/status; }
cd $V2
for n in base tapt S R; do
  while [ ! -s $E4/feats_$n.pt ]; do
    pgrep -f "e4_features.*feats_$n.pt" > /dev/null || { st "FAIL features $n (no process, no output)"; exit 1; }; sleep 60
  done
done
st "DONE features"
if ! grep -q "DONE stageA" $E4/status; then
  ( CUDA_VISIBLE_DEVICES=0 python -m hgfm.e4.e4_probe --feats base=$E4/feats_base.pt tapt=$E4/feats_tapt.pt S=$E4/feats_S.pt R=$E4/feats_R.pt \
      --out $E4/stageA > $E4/stageA.log 2>&1 && st "DONE stageA" || st "FAIL stageA" ) &
fi
beft() {  # $1 name $2 model $3 gpus $4 port [$5 extra]
  [ -s $E4/beft_$1/scores.json ] && return 0
  CUDA_VISIBLE_DEVICES=$3 python -m torch.distributed.run --nproc_per_node 2 --master_port $4 -m hgfm.e4.e4_beft --oat $D/oat_src \
    --model $2 --data_dir $TW --out $E4/beft_$1 ${5:-} >> $E4/beft_$1.log 2>&1 && st "DONE beft $1" || { st "FAIL beft $1"; return 1; }
}
if ! grep -q "DONE beft smoke" $E4/status; then
  beft smoke $BASE 0,1 29511 "--max_train 8 --epochs 1 --accum 2" || exit 1
fi
( beft base $BASE 0,1 29512 ) & ( beft tapt $TAPT 2,3 29513 ) & wait
if [ -s $E4/beft_base/scores.json ] && [ -s $E4/beft_tapt/scores.json ]; then
  python -m hgfm.e4.e4_beft_eval --feats $E4/feats_base.pt --runs base=$E4/beft_base tapt=$E4/beft_tapt --out $E4/stageB.json > $E4/stageB.out 2>&1 \
    && st "DONE stageB eval" || st "FAIL stageB eval"
fi
while pgrep -f "hgfm.e4.e4_probe" > /dev/null; do sleep 60; done
st "ALL DONE"
