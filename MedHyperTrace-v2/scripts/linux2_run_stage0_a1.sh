#!/usr/bin/env bash
# Stage 0 addendum A1 driver (docs/design/Stage0_prereg_v1.md, appendix A1). Status lines go to $S0/status (prefix "A1").
# Runs on GPUs 0,1 after lane A of linux2_run_stage0.sh has finished its shuf / irr features. Lane A's BEFT n=100 runs are
# deferred to the end of this script: before launch, placeholder files beft_{base,tapt}_n100/scores.json
# ({"placeholder": ...}) were created so lane A skips them; this script deletes them and runs the two BEFT jobs itself.
#  1 wait for "DONE lane A" (or a lane-A failure)
#  2 train tapt_clean (TAPT recipe minus eval-question near-duplicates; flash-attn; GPUs 0,1; port 29533)
#  3 E1 OAT (GPU 0) + E4 features (GPU 1) for tapt_clean
#  4 stage A full-label (base vs tapt_clean, -> $S0/stageA_clean) and label efficiency (-> $S0/le, base files reused)
#  5 BEFT n=100 for base and tapt (deferred from lane A)
set -u
ENV=/data/ekyang/anaconda3/envs/mht-swift; export PATH=$ENV/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
W=/data1/ekyang/cgh/CODE/mht_work; S0=$W/stage0; D=$W/e1e3; E4=$W/e4; TW=$E4/tt_ww; HF=$S0/hf/stage0
V2=/data1/ekyang/cgh/CODE/Medhypertrace/MedHyperTrace-v2
BASE=/data1/ekyang/cgh/cache/huggingface_hub/hub/models--Qwen--Qwen3-8B; TAPT=$W/midtrain/tapt_pilot_v1/Qwen3-8B-tapt_pilot_v1
TC=$S0/tapt_clean/Qwen3-8B-tapt_clean
st() { echo "[$(date -u +%F' '%T)] A1 $*" >> $S0/status; }
merged() { grep -qs "DONE merged" $1/status; }
st "START (waiting for lane A)"
until grep -qs "DONE lane A\|FAIL train nc_irr\|FAIL nc_shuf" $S0/status; do sleep 120; done
if ! merged $S0/tapt_clean; then
  st "START train tapt_clean"
  MASTER_PORT=29533 CORPUS=$HF/tapt_clean.jsonl OUT=$S0/tapt_clean GPUS=0,1 NAME=tapt_clean ATTN=flash_attn bash $V2/scripts/linux2_run_tapt.sh \
    && merged $S0/tapt_clean && st "DONE train tapt_clean" || { st "FAIL train tapt_clean"; exit 1; }
fi
if ! grep -qs "A1 DONE e1 tapt_clean" $S0/status; then
  O=$D/oat_tapt_clean; [ -d $O ] || cp -r $D/oat_src $O
  ( cd $O
    for ds in mcp_atlas who_and_when traceelephant_gc; do
      CUDA_VISIBLE_DEVICES=0 OAT_MODEL_NAME=$TC OAT_LAST_LAYER_ONLY=1 OAT_LEN=le32k python run_pipeline.py extract --dataset $ds --model-name $TC >> $S0/e1_tapt_clean.log 2>&1 || exit 1
      CUDA_VISIBLE_DEVICES=0 OAT_MODEL_NAME=$TC OAT_LAST_LAYER_ONLY=1 OAT_LEN=gt32k OAT_YARN=4 python run_pipeline.py extract --dataset $ds --model-name $TC >> $S0/e1_tapt_clean.log 2>&1 || exit 1
    done
    for tgt in who_and_when traceelephant_gc; do
      CUDA_VISIBLE_DEVICES=0 python run_pipeline.py ood --train-dataset mcp_atlas --test-dataset $tgt >> $S0/e1_tapt_clean_ood_$tgt.log 2>&1 || exit 1
    done ) && st "DONE e1 tapt_clean" || st "FAIL e1 tapt_clean" &
fi
if [ ! -s $S0/feats_tapt_clean.pt ]; then
  ( cd $V2 && CUDA_VISIBLE_DEVICES=1 python -m hgfm.e4.e4_features --oat $D/oat_src --model $TC --out $S0/feats_tapt_clean.pt \
      --data who_and_when traceelephant_gc dir:$TW/train=tt_train dir:$TW/val=tt_val dir:$TW/test=tt_test > $S0/feats_tapt_clean.log 2>&1 ) \
    && st "DONE feats tapt_clean" || st "FAIL feats tapt_clean"
fi
wait
if [ -s $S0/feats_tapt_clean.pt ]; then
  [ -s $S0/stageA_clean/e4a_mlp.json ] || ( cd $V2 && CUDA_VISIBLE_DEVICES=1 python -m hgfm.e4.e4_probe --feats base=$E4/feats_base.pt tapt_clean=$S0/feats_tapt_clean.pt \
      --out $S0/stageA_clean > $S0/stageA_clean.log 2>&1 ) && st "DONE stageA tapt_clean" || st "FAIL stageA tapt_clean"
  ( cd $V2 && CUDA_VISIBLE_DEVICES=1 python -m hgfm.e4.e4_probe --feats base=$E4/feats_base.pt tapt_clean=$S0/feats_tapt_clean.pt \
      --subsets $S0/subsets.json --out $S0/le > $S0/le_tapt_clean.log 2>&1 ) && st "DONE le tapt_clean" || st "FAIL le tapt_clean"
fi
for n in base tapt; do
  grep -qs placeholder $S0/beft_${n}_n100/scores.json && rm -f $S0/beft_${n}_n100/scores.json
done
python -c "import json; d=json.load(open('$S0/subsets.json')); json.dump(d['draws']['0']['100'], open('$S0/ids_n100.json','w'))"
for spec in "base $BASE 29521" "tapt $TAPT 29522"; do
  set -- $spec
  [ -s $S0/beft_$1_n100/scores.json ] && continue
  st "START beft $1_n100"
  ( cd $V2 && CUDA_VISIBLE_DEVICES=0,1 python -m torch.distributed.run --nproc_per_node 2 --master_port $3 -m hgfm.e4.e4_beft --oat $D/oat_src \
      --model $2 --data_dir $TW --out $S0/beft_$1_n100 --train_ids $S0/ids_n100.json --epochs 10 --accum 4 --evals_per_epoch 1 >> $S0/beft_$1_n100.log 2>&1 ) \
    && st "DONE beft $1_n100" || st "FAIL beft $1_n100"
done
st "ALL DONE"
