#!/usr/bin/env bash
# Data pipeline for the LLM layer on a GPU server (round 38). Run from MedHyperTrace-v2/.
#   bash scripts/prepare_maa.sh <work_dir> [folds] [max_train]
#   folds: comma list of fold names (default: all 6 LQD folds + QD)
# Steps: 1 fetch MedAgentAudit release  2 convert to mas-traj/1  3 align the 400 human instances
#        4 MiniLM embeddings (graph pickles are cached on first load)  5 per-fold HGFM v0.2 encoder
#        + graph tokens  6 SFT data, graph-token and text-only versions.
# Every step skips work that already exists, so the script can be re-run after a failure.
set -euo pipefail
W=${1:?work dir}; FOLDS=${2:-}; MAXTR=${3:-20000}
mkdir -p "$W"; cd "$(dirname "$0")/.."

# 1. MedAgentAudit release (public repo; the user confirmed permission to use it)
if [ ! -d "$W/maa/github_release_files" ]; then
  [ -d "$W/nature-sub-record" ] || GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/GuihaiChen1998/nature-sub-record "$W/nature-sub-record"
  mkdir -p "$W/maa" && cat "$W"/nature-sub-record/"MedAgentAudit-datasets_and_logs-9.2 - 1.zip."00{1,2,3} > "$W/maa/outer.zip"
  (cd "$W/maa" && unzip -q -o outer.zip && find . -name "*.zip" ! -name outer.zip -exec unzip -q -o {} \;)
  R=$(find "$W/maa" -type d -name github_release_files | head -1); [ "$R" = "$W/maa/github_release_files" ] || mv "$R" "$W/maa/"
fi
REL="$W/maa/github_release_files"

# 2-4. conversion, human alignment, embeddings
[ -s "$W/maa_mas_traj.jsonl" ] || python -m data_tools.maa_to_mas_traj "$REL" "$W/maa_mas_traj.jsonl"
[ -s "$W/maa_human400.jsonl" ] || python -m data_tools.maa_human_eval "$REL" "$W/maa_human400.jsonl"
# embeddings: restore the cache stored in the repo (data/maa_emb_minilm), else compute (~50 min CPU)
[ -s "$W/emb/emb.npy" ] || bash scripts/restore_maa_emb.sh "$W/emb" || python -m hgfm.embed_maa "$W/maa_mas_traj.jsonl" "$W/emb"

# 5. encoder per fold + graph tokens (CPU is fine: ~minutes per fold)
python -m hgfm.llm.export_graph_emb "$W/maa_mas_traj.jsonl" "$W/emb" "$W/maa_human400.jsonl" data/anchor_overlap_qids.json "$W/llm" "$FOLDS" 0

# 6. SFT data: graph-token prompts and the same prompts without graph tokens (text-only baseline)
for d in "$W"/llm/*/; do
  [ -s "$d/sft_graph/train.jsonl" ] || python -m hgfm.llm.build_sft "$W/maa_mas_traj.jsonl" "$d/graph_tokens.pt" "$W/maa_human400.jsonl" data/maa_code_definitions.json "$d/sft_graph" --max_train "$MAXTR"
  [ -s "$d/sft_text/train.jsonl" ]  || python -m hgfm.llm.build_sft "$W/maa_mas_traj.jsonl" "$d/graph_tokens.pt" "$W/maa_human400.jsonl" data/maa_code_definitions.json "$d/sft_text" --max_train "$MAXTR" --no_graph
done
echo "done: $W/llm/<fold>/{graph_tokens.pt,sft_graph,sft_text}"
