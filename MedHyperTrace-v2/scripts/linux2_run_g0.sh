#!/usr/bin/env bash
# Gate G0 (OutcomeCPT amendment A1, round 97) on Linux #2 GPUs 0,1, ahead of line 2. Resumable (steps skip existing outputs).
#   cd $C && setsid nohup bash scripts/linux2_run_g0.sh > $W/outcome/g0/driver.log 2>&1 < /dev/null &
# GPU 0: Qwen3-8B (post-trained) layers 9,18,27,36 on public (WW, TEgc, TT train/val/test) and medical eval parents.
# GPU 1: Qwen3-8B-Base, same (waits for the line-3 gate's corpus extraction on GPU 1 and for the Base download).
# Then: e4_probe stage A (linear + agg) on all 8 configurations; med_eval score (linear + agg) per configuration; g0_compare.
# When done, the line-2 driver (scripts/linux2_run_posttrain.sh) is restarted on GPUs 0,1.
set -u
ENV=/data/ekyang/anaconda3/envs/mht-swift; export PATH=$ENV/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
W=/data1/ekyang/cgh/CODE/mht_work; G=$W/outcome/g0; V2=/data1/ekyang/cgh/CODE/Medhypertrace/MedHyperTrace-v2; IC=$W/icpt
D=$W/e1e3; TW=$W/e4/tt_ww; MED=$IC/hf/icpt/med_ww; HUB=/data1/ekyang/cgh/cache/huggingface_hub/hub
IT=$HUB/models--Qwen--Qwen3-8B; mkdir -p $G
PUB="who_and_when traceelephant_gc dir:$TW/train=tt_train dir:$TW/val=tt_val dir:$TW/test=tt_test"
st() { echo "[$(date -u +%F' '%T)] $*" >> $G/status; }
fx() {  # $1 model $2 tag $3 gpu
  for part in pub med; do
    [ -s $G/${part}_$2_L36.pt ] && continue
    if [ $part = pub ]; then data="$PUB"; else data="dir:$MED=med"; fi
    ( cd $V2 && CUDA_VISIBLE_DEVICES=$3 python -m hgfm.e4.e4_features --oat $D/oat_src --model $1 --out $G/${part}_$2.pt --layers 9,18,27,36 \
        --data $data > $G/${part}_$2.log 2>&1 ) && st "DONE feats $part $2" || { st "FAIL feats $part $2"; return 1; }
  done
}
st "START g0"
( fx $IT it 0 ) &
( until grep -qs "DONE featscorpus_base\|FAIL featscorpus_base" $W/outcome/status; do sleep 120; done
  until grep -qs "^done" $W/dl_base.log; do sleep 120; done
  BASEM=$(sed -n 's/^done //p' $W/dl_base.log | tail -1); st "Base snapshot $BASEM"
  fx $BASEM b 1 ) &
wait
for t in it b; do for l in 9 18 27 36; do for part in pub med; do [ -s $G/${part}_${t}_L$l.pt ] || { st "FAIL missing ${part}_${t}_L$l"; exit 1; }; done; done; done
F="base=$G/pub_it_L36.pt it9=$G/pub_it_L9.pt it18=$G/pub_it_L18.pt it27=$G/pub_it_L27.pt b9=$G/pub_b_L9.pt b18=$G/pub_b_L18.pt b27=$G/pub_b_L27.pt b36=$G/pub_b_L36.pt"
[ -s $G/stageA/e4a_agg_scores.json ] || ( cd $V2 && CUDA_VISIBLE_DEVICES=0 python -m hgfm.e4.e4_probe --feats $F --heads linear agg --out $G/stageA > $G/stageA.log 2>&1 ) \
  && st "DONE stageA" || { st "FAIL stageA"; exit 1; }
for c in base:it_L36 it9:it_L9 it18:it_L18 it27:it_L27 b9:b_L9 b18:b_L18 b27:b_L27 b36:b_L36; do
  n=${c%%:*}; f=${c##*:}; [ -s $G/med_$n.json ] && continue
  ( cd $V2 && CUDA_VISIBLE_DEVICES= python -m hgfm.icpt.med_eval score --feats $G/med_$f.pt --ww $MED --heads linear agg --out $G/med_$n.json > $G/med_$n.log 2>&1 ) \
    && st "DONE med $n" || { st "FAIL med $n"; exit 1; }
done
( cd $V2 && python -m hgfm.outcome.g0_compare --w $W --g0 $G --clusters $W/stage0/cluster_ci/clusters.json --out $G/g0.json > $G/g0.out 2>&1 ) \
  && st "DONE g0 compare $(grep DECISION $G/g0.out)" || st "FAIL g0 compare"
st "G0 ALL DONE; restarting line-2 driver"
( cd $V2 && setsid nohup bash scripts/linux2_run_posttrain.sh > $W/posttrain/driver.log 2>&1 < /dev/null & )
