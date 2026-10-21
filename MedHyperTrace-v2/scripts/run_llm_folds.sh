#!/usr/bin/env bash
# Train + evaluate the graph-token LM on every fold, one fold per GPU (round 38). Run from MedHyperTrace-v2/.
#   bash scripts/run_llm_folds.sh <work_dir> [lm] [variant] [gpus]
#   variant: graph (default) | text (no graph tokens) | zeroshot (untrained LM, text prompts)
#   gpus: comma list, default 0,1,2,3
set -euo pipefail
W=${1:?work dir}; LM=${2:-Qwen/Qwen3-8B}; V=${3:-graph}; IFS=, read -ra GPUS <<< "${4:-0,1,2,3}"
cd "$(dirname "$0")/.."
TAG=$(basename "$LM")_$V; i=0
for d in "$W"/llm/*/; do
  g=${GPUS[$((i % ${#GPUS[@]}))]}; i=$((i + 1))
  (
    S=sft_graph; F=""; [ "$V" = graph ] || { S=sft_text; F="--no_graph"; }
    if [ "$V" = zeroshot ]; then
      CUDA_VISIBLE_DEVICES=$g python -m hgfm.llm.eval --lm "$LM" --zero_shot --data "$d/$S/eval_human.jsonl" --tokens "$d/graph_tokens.pt" --out "$d/eval_$TAG.json"
    else
      [ -s "$d/ckpt_$TAG/projector.pt" ] || CUDA_VISIBLE_DEVICES=$g python -m hgfm.llm.train --lm "$LM" --data "$d/$S/train.jsonl" --tokens "$d/graph_tokens.pt" --out "$d/ckpt_$TAG" --grad_ckpt $F
      CUDA_VISIBLE_DEVICES=$g python -m hgfm.llm.eval --lm "$LM" --ckpt "$d/ckpt_$TAG" --data "$d/$S/eval_human.jsonl" --tokens "$d/graph_tokens.pt" --out "$d/eval_$TAG.json" $F
    fi
  ) > "$d/log_$TAG.txt" 2>&1 &
  if [ $((i % ${#GPUS[@]})) -eq 0 ]; then wait; fi
done
wait
python -m hgfm.llm.pool "$W/llm" "$TAG"
