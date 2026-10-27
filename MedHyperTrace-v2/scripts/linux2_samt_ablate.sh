#!/usr/bin/env bash
# round 64: after linux2_run_samt.sh has finished ("ALL DONE" in $D/status), evaluate the SAMT SFT checkpoints
# (QD + LQD_mac x seeds 0/1) with zeroed and with cross-run shuffled graph tokens (C6 diagnosis on SAMT), one eval per
# GPU, then run linux2_samt_eval.py. Outputs eval_swift[_s1]_samt_v1_{zero,shuf}_graph.json next to the real ones.
# Usage: setsid nohup bash linux2_samt_ablate.sh > $D/ablate.log 2>&1 &
set -u
ENV=/data/ekyang/anaconda3/envs/mht-swift
export PATH=$ENV/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false USE_HF=1
unset MHT_PROJ_INIT
W=/data1/ekyang/cgh/CODE/mht_work; D=$W/midtrain/samt_v1; L=$W/maa/llm; V2=/data1/ekyang/cgh/CODE/Medhypertrace/MedHyperTrace-v2
P=$V2/hgfm/llm/swift_plugin; LM=/data1/ekyang/cgh/cache/huggingface_hub/hub/models--Qwen--Qwen3-8B
st() { echo "[$(date -u +%F' '%T)] $*" >> $D/status; }
while ! grep -q "ALL DONE" $D/status; do
  pgrep -f linux2_run_samt.sh > /dev/null || { st "ablate: driver ended without ALL DONE, not started"; exit 1; }
  sleep 60
done
cd $V2
[ -s $D/graph_tokens_samt_shuf.pt ] || python -m hgfm.midtrain.samt_ablate_tokens $D/graph_tokens_samt.pt $D/graph_tokens_samt_zero.pt $D/graph_tokens_samt_shuf.pt >> $D/ablate.log 2>&1
st "START ablate evals"
for mode in zero shuf; do
  g=0
  for f in QD LQD_mac; do for s in 0 1; do
    tp=swift_samt_v1; [ $s != 0 ] && tp=swift_s${s}_samt_v1
    ck=$(ls -d $L/$f/ckpt_${tp}_graph/checkpoint-* | sort -V | tail -1)
    out=$L/$f/eval_${tp/samt_v1/samt_v1_$mode}_graph.json
    [ -s $out ] || CUDA_VISIBLE_DEVICES=$g MHT_GRAPH_TOKENS=$D/graph_tokens_samt_$mode.pt python $P/eval_swift.py --lm $LM --ckpt $ck \
        --data $L/$f/sft_graph/eval_human.jsonl --out $out > $D/ablate_${f}_s${s}_$mode.log 2>&1 &
    g=$((g + 1))
  done; done; wait
  st "DONE ablate $mode"
done
python $V2/scripts/linux2_samt_eval.py > $D/samt_v1_eval.out 2>&1 && st "DONE eval (samt_v1_eval.out)" || st "FAIL eval"
