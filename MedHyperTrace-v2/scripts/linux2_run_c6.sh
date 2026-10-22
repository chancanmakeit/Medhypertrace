#!/usr/bin/env bash
# C6 full run on Linux #2 (round 47): 7 folds x {graph,text} LoRA (plain PyTorch, same code for both variants),
# two workers pinned to GPU 2 and GPU 3 pulling from one queue; then zeroshot on the new prompts and pooling.
# Copy of /data1/ekyang/cgh/CODE/mht_work/run_c6.sh (started 2026-10-22 09:30 UTC with setsid nohup).
export PATH=/data/ekyang/anaconda3/envs/sglang/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false
unset all_proxy ALL_PROXY http_proxy https_proxy
LM=/data1/ekyang/cgh/cache/huggingface_hub/hub/models--Qwen--Qwen3-8B; L=/data1/ekyang/cgh/CODE/mht_work/maa/llm; TAGB=$(basename $LM); Q=/data1/ekyang/cgh/CODE/mht_work/c6_queue; mkdir -p $Q/logs
cd /data1/ekyang/cgh/CODE/Medhypertrace/MedHyperTrace-v2
if [ ! -f $Q/jobs ]; then for f in LQD_colacare LQD_healthcareagent LQD_mac LQD_mdagents LQD_medagent LQD_reconcile QD; do echo "$f graph"; echo "$f text"; done > $Q/jobs; fi
job() {  # $1 gpu, $2 fold, $3 variant
  local d=$L/$2 v=$3 S F tag; tag=${TAGB}_$v; S=sft_graph; F=""; [ $v = graph ] || { S=sft_text; F="--no_graph"; }
  if [ ! -s $d/ckpt_$tag/projector.pt ]; then
    CUDA_VISIBLE_DEVICES=$1 python -m hgfm.llm.train --lm $LM --data $d/$S/train.jsonl --tokens $d/graph_tokens.pt --out $d/ckpt_$tag --grad_ckpt $F || return 1
  fi
  [ -s $d/eval_$tag.json ] || CUDA_VISIBLE_DEVICES=$1 python -m hgfm.llm.eval --lm $LM --ckpt $d/ckpt_$tag --data $d/$S/eval_human.jsonl --tokens $d/graph_tokens.pt --out $d/eval_$tag.json $F
}
worker() {  # $1 gpu
  while true; do
    exec 8>$Q/lock; flock 8; J=$(head -1 $Q/jobs); [ -n "$J" ] && sed -i 1d $Q/jobs; flock -u 8
    [ -z "$J" ] && break
    set -- $1 $J; echo "[$(date -u +%F' '%T)] GPU$1 START $2 $3" >> $Q/status
    if job $1 $2 $3 > $Q/logs/$2_$3.log 2>&1; then echo "[$(date -u +%F' '%T)] GPU$1 DONE $2 $3" >> $Q/status
    else echo "[$(date -u +%F' '%T)] GPU$1 FAIL $2 $3" >> $Q/status; fi
  done
}
worker 2 & worker 3 & wait
echo "[$(date -u +%F' '%T)] training queue empty; zeroshot" >> $Q/status
for f in LQD_colacare LQD_healthcareagent LQD_mac LQD_mdagents LQD_medagent LQD_reconcile QD; do d=$L/$f; tag=${TAGB}_zeroshot
  [ -s $d/eval_$tag.json ] || CUDA_VISIBLE_DEVICES=2 python -m hgfm.llm.eval --lm $LM --zero_shot --data $d/sft_text/eval_human.jsonl --tokens $d/graph_tokens.pt --out $d/eval_$tag.json >> $Q/logs/zeroshot.log 2>&1
done
for v in graph text zeroshot; do python -m hgfm.llm.pool $L ${TAGB}_$v >> $Q/pooled.txt 2>&1; done
echo "[$(date -u +%F' '%T)] ALL DONE" >> $Q/status
