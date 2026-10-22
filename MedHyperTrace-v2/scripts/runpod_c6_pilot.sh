#!/usr/bin/env bash
# Unattended C6 pilot on a 1-GPU Runpod pod (round 45).
# Started by the pod's start command after it cloned the repo to /workspace/repo:
#   bash /workspace/repo/MedHyperTrace-v2/scripts/runpod_c6_pilot.sh
# Env: GH_TOKEN (Runpod secret, used only in an HTTP header, never echoed), LIMIT (pilot training pairs, default 800),
#      BRANCH (results branch, default runpod-c6-pilot), LM (default Qwen/Qwen3-8B).
# Steps: deps -> prepare_maa.sh (all folds) -> pilot LoRA training on LQD_mac (graph variant, LIMIT pairs:
#        peak memory + tokens/s) + eval of that checkpoint (pipeline check only) -> zeroshot variant on all folds
#        + pooling -> push logs/results to BRANCH -> stop the pod.
set -uo pipefail
W=/workspace/mht; R=/workspace/repo; OUT=/workspace/out; LIMIT=${LIMIT:-800}; BRANCH=${BRANCH:-runpod-c6-pilot}; LM=${LM:-Qwen/Qwen3-8B}
export HF_HOME=/workspace/hf PIP_ROOT_USER_ACTION=ignore TOKENIZERS_PARALLELISM=false
mkdir -p "$W" "$OUT"
exec > >(tee -a "$OUT/pilot.log") 2>&1
log() { echo "[PILOT $(date -u +%H:%M:%S)] $*"; }
if [ -f "$OUT/DONE" ]; then log "already finished earlier; idle"; sleep infinity; fi
AUTH="AUTHORIZATION: basic $(printf 'x-access-token:%s' "${GH_TOKEN:-}" | base64 -w0)"

push_results() {
  local status=$1
  log "collecting results (status=$status)"
  local D="$R/MedHyperTrace-v2/results/c6_runpod_pilot"; mkdir -p "$D"
  cp "$OUT"/pilot.log "$OUT"/nvsmi.csv "$OUT"/env.txt "$D"/ 2>/dev/null
  for f in "$W"/llm/*/eval_*.json "$W"/llm/pooled_*.json "$W"/llm/LQD_mac/ckpt_pilot/train_stats.json "$W"/llm/LQD_mac/ckpt_pilot/train_args.json; do
    [ -f "$f" ] && cp "$f" "$D/$(basename "$(dirname "$f")")__$(basename "$f")"
  done
  echo "$status" > "$D/STATUS"
  cd "$R" && git checkout -q -B "$BRANCH" && git add -A MedHyperTrace-v2/results/c6_runpod_pilot \
    && git -c user.name="runpod-pilot" -c user.email="chancanmakeit@gmail.com" commit -qm "C6 Runpod pilot results ($status)" \
    && git -c http.extraheader="$AUTH" push -q -f origin "$BRANCH" && log "pushed to branch $BRANCH" || log "PUSH FAILED"
}
finish() {
  local rc=$?
  [ -f "$OUT/DONE" ] && return
  touch "$OUT/DONE"; kill %1 2>/dev/null
  push_results "$([ $rc -eq 0 ] && echo ok || echo "failed rc=$rc at: $STAGE")"
  log "ALL DONE rc=$rc; stopping pod"
  command -v runpodctl >/dev/null && [ -n "${RUNPOD_POD_ID:-}" ] && runpodctl stop pod "$RUNPOD_POD_ID"
  sleep infinity
}
trap finish EXIT
set -e

STAGE=env; log "stage env"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv | tee "$OUT/env.txt"
nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv -l 30 > "$OUT/nvsmi.csv" &
cd "$R/MedHyperTrace-v2"
pip install -q "transformers>=4.56" "peft>=0.17" accelerate sentence-transformers scikit-learn huggingface_hub
python -c "import torch,transformers,peft; print('torch',torch.__version__,'cuda',torch.version.cuda,'transformers',transformers.__version__,'peft',peft.__version__)" | tee -a "$OUT/env.txt"
python -c "from huggingface_hub import snapshot_download; snapshot_download('$LM')" > "$OUT/hf_download.log" 2>&1 &
HF_PID=$!

STAGE=prepare; log "stage prepare_maa (all folds)"
bash scripts/prepare_maa.sh "$W" "" 8000
ls "$W/llm"
log "waiting for model download"; wait $HF_PID

STAGE=pilot_train; log "stage pilot training: LQD_mac graph, $LIMIT pairs"
F="$W/llm/LQD_mac"
python -m hgfm.llm.train --lm "$LM" --data "$F/sft_graph/train.jsonl" --tokens "$F/graph_tokens.pt" --out "$F/ckpt_pilot" --grad_ckpt --limit "$LIMIT"
STAGE=pilot_eval; log "stage pilot eval (pipeline check only; $LIMIT-pair checkpoint, AUROC not meaningful)"
python -m hgfm.llm.eval --lm "$LM" --ckpt "$F/ckpt_pilot" --data "$F/sft_graph/eval_human.jsonl" --tokens "$F/graph_tokens.pt" --out "$F/eval_pilot_graph.json"

STAGE=zeroshot; TAG=$(basename "$LM")_zeroshot
for d in "$W"/llm/*/; do
  log "stage zeroshot $(basename "$d")"
  python -m hgfm.llm.eval --lm "$LM" --zero_shot --data "$d/sft_text/eval_human.jsonl" --tokens "$d/graph_tokens.pt" --out "$d/eval_$TAG.json"
done
python -m hgfm.llm.pool "$W/llm" "$TAG"
STAGE=done; log "pilot finished"
