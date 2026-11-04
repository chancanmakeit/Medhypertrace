#!/usr/bin/env bash
# Interaction-CPT pre-registration §3 / §6.2: read-out interface diagnostic with base only (round 86).
#   GPU=2 setsid nohup bash scripts/linux2_run_icpt_diag.sh > /dev/null 2>&1 &
# 1 full-trajectory query features of base (hgfm.icpt.feat_query), same data as the stage-0 / E4 prefix features;
# 2 iface_probe: (a) prefix + linear, (b) query + linear, (c) prefix + aggregator; selection on tt_val (controlled).
# Re-runnable: each step is skipped when its output exists. Progress: $O/status.
set -u
ENV=/data/ekyang/anaconda3/envs/mht-swift
export PATH=$ENV/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
W=/data1/ekyang/cgh/CODE/mht_work; V2=/data1/ekyang/cgh/CODE/Medhypertrace/MedHyperTrace-v2; D=$W/e1e3; TW=$W/e4/tt_ww
BASE=/data1/ekyang/cgh/cache/huggingface_hub/hub/models--Qwen--Qwen3-8B
O=$W/icpt/diag; mkdir -p $O; GPU=${GPU:-2}
st() { echo "[$(date -u +%F' '%T)] $*" >> $O/status; }
st "START diag gpu=$GPU"
if [ ! -s $O/featsq_base.pt ]; then
  ( cd $V2 && CUDA_VISIBLE_DEVICES=$GPU python -m hgfm.icpt.feat_query --oat $D/oat_src --model $BASE --out $O/featsq_base.pt \
      --data who_and_when traceelephant_gc dir:$TW/train=tt_train dir:$TW/val=tt_val dir:$TW/test=tt_test > $O/featsq_base.log 2>&1 ) \
    && st "DONE featsq base" || { st "FAIL featsq base"; exit 1; }
fi
if [ ! -s $O/iface.json ]; then
  ( cd $V2 && CUDA_VISIBLE_DEVICES=$GPU python -m hgfm.icpt.iface_probe --prefix $W/e4/feats_base.pt --query $O/featsq_base.pt \
      --out $O/iface.json > $O/iface.log 2>&1 ) && st "DONE iface $(grep SELECTED $O/iface.log)" || { st "FAIL iface"; exit 1; }
fi
if [ ! -s $O/loss_diag.json ]; then   # §6.1 (amendment A3): zero-training loss diagnostic, base vs tapt_clean
  ( cd $V2 && CUDA_VISIBLE_DEVICES=$GPU python -m hgfm.icpt.loss_diag run --runs $W/icpt/hf/icpt/loss_runs.jsonl.gz \
      --models base=$BASE tapt_clean=$W/stage0/tapt_clean/Qwen3-8B-tapt_clean --out $O/loss_diag.jsonl > $O/loss_diag.log 2>&1 \
    && python -m hgfm.icpt.loss_diag analyse --inp $O/loss_diag.jsonl --out $O/loss_diag.json > $O/loss_diag.out 2>&1 ) \
    && st "DONE loss_diag" || { st "FAIL loss_diag"; exit 1; }
fi
st "DIAG ALL DONE"
