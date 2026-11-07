#!/usr/bin/env bash
# OutcomeCPT amendment A2, case L (round 97): G0 picked the post-trained model at layer LAYER (it18).
# Runs on Linux #1: on Linux #2, GPUs 0,1 hold line 2, and the user keeps GPUs 2,3 free.
#   cd /data1/cgh/code/mht && LAYER=18 setsid nohup bash MedHyperTrace-v2/scripts/linux1_run_layer_feats.sh > runs/layer_feats_driver.log 2>&1 < /dev/null &
# Models copied from Linux #2 over the LAN: models/lm = merged LM-CPT arm (icpt/lm/Qwen3-8B-icpt_lm), models/it = Qwen3-8B.
# Steps (each skipped once its output exists):
#   GPU 0: lm arm features at layer LAYER, medical then public;
#   GPU 1: post-trained corpus features at layer LAYER (gate G re-run).
#   Then on CPU:
#     - med_eval score on lm(LAYER);
#     - H-L1 = lm(LAYER) - base(LAYER), compared against G0's med_it<LAYER>.json (copied to xfer/);
#     - value_gate on it(LAYER), with G0's med_it_L<LAYER>.pt as the medical side.
# Public stage A (secondary) runs on Linux #2 after pub_lm_L<LAYER>.pt is copied back.
set -u
R=/data1/cgh/code/mht; ENV=/home/cgh/anaconda3/envs/ms-swift
export PATH=$ENV/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True HF_HOME=/data1/cgh/cache/huggingface
unset all_proxy ALL_PROXY http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
V2=$R/MedHyperTrace-v2; WK=$R/work; D=$WK/e1e3; TW=$WK/e4/tt_ww; MED=$WK/icpt/hf/icpt/med_ww; COR=$WK/outcome/corpus
L=${LAYER:?set LAYER}; O=$R/runs/layer$L; LM=$R/models/lm; IT=$R/models/it
PUB="who_and_when traceelephant_gc dir:$TW/train=tt_train dir:$TW/val=tt_val dir:$TW/test=tt_test"
mkdir -p $O; st() { echo "[$(date -u +%F' '%T)] $*" >> $O/status; }
st "START layer-$L driver (A2 case L)"
for m in $LM $IT; do cat $m/*.safetensors > /dev/null; done; st "weights warmed into page cache"
fx() {  # $1 model $2 output stem $3 gpu $4 data spec (word-split on purpose)
  [ -s ${2}_L$L.pt ] && return 0
  ( cd $V2 && CUDA_VISIBLE_DEVICES=$3 python -m hgfm.e4.e4_features --oat $D/oat_src --model $1 --out $2.pt --layers $L \
      --data $4 > $2.log 2>&1 ) && st "DONE feats $(basename $2)_L$L" || { st "FAIL feats $(basename $2)"; return 1; }
}
( fx $LM $O/med_lm 0 "dir:$MED=med" && fx $LM $O/pub_lm 0 "$PUB" ) &
( fx $IT $O/corpus_it 1 "dir:$COR=corpus" ) &
wait
[ -s $O/med_lm.json ] || ( cd $V2 && CUDA_VISIBLE_DEVICES= python -m hgfm.icpt.med_eval score --feats $O/med_lm_L$L.pt --ww $MED --heads linear agg \
    --out $O/med_lm.json > $O/med_lm_eval.log 2>&1 ) && st "DONE med_eval lm L$L" || st "FAIL med_eval lm"
[ -s $O/hl1.json ] || ( cd $V2 && python - $O/med_lm.json $R/xfer/med_it$L.json $O/hl1.json > $O/hl1.out 2>&1 <<'PY'
import json, sys
from hgfm.posttrain.posttrain_eval import cmp
a, b, out = sys.argv[1:4]; A, B = json.load(open(a)), json.load(open(b)); R = {}
for head in ("agg", "linear"):
    R[head] = cmp(A["heads"][head], B["heads"][head], B["parents"]); p = R[head]["pooled"]; m = p["resid"]
    print(f"H-L1 {head}: lm - base (layer) controlled {m['diff']:+.4f} [{m['ci95'][0]:+.4f}, {m['ci95'][1]:+.4f}] grid {p['grid']['same_sign']}/6 {p['verdict']}")
json.dump(R, open(out, "w"), indent=1)
PY
) && st "DONE H-L1 $(grep 'H-L1 agg' $O/hl1.out)" || st "FAIL H-L1"
[ -s $O/gate_it_L$L.json ] || ( cd $V2 && CUDA_VISIBLE_DEVICES= python -m hgfm.outcome.value_gate --corpus_feats $O/corpus_it_L$L.pt --corpus_ww $COR \
    --med_feats $R/xfer/med_it_L$L.pt --med_ww $MED --out $O/gate_it_L$L.json > $O/gate_it_L$L.out 2>&1 ) && st "DONE gate it_L$L" || st "FAIL gate it_L$L"
st "ALL DONE"
