#!/usr/bin/env bash
# Layer-18 re-check (docs/design/Layer18_recheck_prereg_v1.md, round 101) on Linux #1. Resumable: every job is skipped
# when its output exists. Progress goes to $O/status.
#   cd /data1/cgh/code/mht && setsid nohup bash MedHyperTrace-v2/scripts/linux1_run_layer18_recheck.sh > runs/l18rc/driver.log 2>&1 < /dev/null &
#
# Feature lanes: one per GPU in $GPUS, all pulling from a single queue ($O/jobs.txt), so the shared GPU that has
# another user's load simply takes fewer jobs. Medical jobs come first, so R1a / R2.5 can start early.
#   medml  : e4_features --layers 9,...,36 on the medical parents (R1a; it, lm, icpt)
#   med18  : e4_features --layers 18 on the medical parents (R2.6 descriptive: tapt S R full irr shuf tapt_clean)
#   qmed18 : feat_query --layer 18 on the medical parents (R2.5 secondary interface; it, lm, icpt)
#   pub18  : e4_features --layers 18 on public WW + TEgc + TT (R2.1-R2.4, H4)
#            Reused, not re-extracted: base = xfer/pub_it_L18.pt, lm = runs/layer18/pub_lm_L18.pt
# CPU lane : med_eval score (linear, agg) on every medical file once all of them exist; then R1a and the medical
#            comparisons (scripts/l18rc_analyze.py)
# Probe lane (GPU ${PG:-0}, after all public files exist): e4_probe stage A + label efficiency, written in the mht_work
#            layout under $O/w; then stage0_analyze / stage0_cluster_ci / icpt_le_analyze and l18rc_analyze r2
set -u
R=/data1/cgh/code/mht; ENV=/home/cgh/anaconda3/envs/ms-swift
export PATH=$ENV/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True HF_HOME=/data1/cgh/cache/huggingface
export PYTHONPATH=$R/MedHyperTrace-v2 OMP_NUM_THREADS=${OMP_NUM_THREADS:-8}
unset all_proxy ALL_PROXY http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
V2=$R/MedHyperTrace-v2; WK=$R/work; D=$WK/e1e3; TW=$WK/e4/tt_ww; MED=$WK/icpt/hf/icpt/med_ww
O=$R/runs/l18rc; F=$O/feats; M=$R/models; LS=9,12,15,18,21,24,27,36; GPUS=${GPUS:-0,1,2,3}
PIT=$R/xfer/pub_it_L18.pt; PLM=$R/runs/layer18/pub_lm_L18.pt
PUB="who_and_when traceelephant_gc dir:$TW/train=tt_train dir:$TW/val=tt_val dir:$TW/test=tt_test"
MEDARMS="tapt S R full irr shuf tapt_clean"; PUBARMS="tapt S R full irr shuf tapt_clean icpt"
mkdir -p $F $O/w/e4 $O/w/stage0 $O/w/icpt; st() { echo "[$(date -u +%F' '%T)] $*" >> $O/status; }

{ for m in it lm icpt; do echo medml $m; done; for m in $MEDARMS; do echo med18 $m; done
  for m in it lm icpt; do echo qmed18 $m; done; for m in $PUBARMS; do echo pub18 $m; done; } > $O/jobs.txt
echo 0 > $O/q.next

chk() { case $1 in medml) echo $F/med_$2_L36.pt;; med18) echo $F/med_$2_L18.pt;; qmed18) echo $F/qmed_$2_L18.pt;; pub18) echo $F/pub_$2_L18.pt;; esac; }
run_job() {  # $1 kind $2 model $3 gpu
  local c; c=$(chk $1 $2); [ -s $c ] && return 0
  local a
  case $1 in
    medml)  a="-m hgfm.e4.e4_features --out $F/med_$2.pt --layers $LS --data dir:$MED=med";;
    med18)  a="-m hgfm.e4.e4_features --out $F/med_$2.pt --layers 18 --data dir:$MED=med";;
    qmed18) a="-m hgfm.icpt.feat_query --out $F/qmed_$2_L18.pt --layer 18 --data dir:$MED=med";;
    pub18)  a="-m hgfm.e4.e4_features --out $F/pub_$2.pt --layers 18 --data $PUB";;
  esac
  case $2 in it|lm|icpt) ;; *) until grep -qs ALLDONE $R/xfer/r101_copy.log; do sleep 60; done ;; esac   # LAN copy from Linux #2
  st "START $1 $2 gpu$3"; cat $M/$2/*.safetensors > /dev/null
  ( cd $V2 && CUDA_VISIBLE_DEVICES=$3 python $a --oat $D/oat_src --model $M/$2 > $F/$1_$2.log 2>&1 ) && [ -s $c ] && st "DONE $1 $2" || st "FAIL $1 $2"
}
next() { ( flock 9; n=$(cat $O/q.next); echo $((n + 1)) > $O/q.next; echo $n ) 9> $O/q.lock; }
lane() { local i line; while :; do i=$(next); line=$(sed -n "$((i + 1))p" $O/jobs.txt); [ -z "$line" ] && break; run_job $line $1; done; st "lane gpu$1 done"; }

medfiles() { for m in it lm icpt; do for l in ${LS//,/ }; do echo $F/med_${m}_L$l.pt; done; done
             for m in $MEDARMS; do echo $F/med_${m}_L18.pt; done; for m in it lm icpt; do echo $F/qmed_${m}_L18.pt; done; }
waitall() {  # $1 = space-separated job kinds whose jobs must all be DONE or FAIL
  local k m; while :; do local open=0
    while read k m; do [[ " $1 " == *" $k "* ]] || continue
      grep -qs "DONE $k $m$\|FAIL $k $m$" $O/status || [ -s $(chk $k $m) ] || open=1; done < $O/jobs.txt
    [ $open = 0 ] && return 0; sleep 60; done
}
cpu_lane() {
  waitall "medml med18 qmed18"; st "medical features complete; scoring"
  medfiles | while read f; do [ -s $f ] && [ ! -s ${f%.pt}.json ] && echo $f; done | \
    xargs -P ${NCPU_JOBS:-4} -I{} bash -c 'f={}; cd '$V2' && CUDA_VISIBLE_DEVICES= python -m hgfm.icpt.med_eval score --feats $f --ww '$MED' --heads linear agg --out ${f%.pt}.json > ${f%.pt}.score.log 2>&1 || echo "[$(date -u +%F" "%T)] FAIL score $(basename $f)" >> '$O'/status'
  st "DONE med scoring ($(ls $F/*.json 2>/dev/null | wc -l) files)"
  ( cd $V2 && python scripts/l18rc_analyze.py med --f $F --out $O/med_results.json > $O/med_results.out 2>&1 ) && st "DONE med analysis (R1a, R2.5, R2.6)" || st "FAIL med analysis"
}
probe_lane() {
  waitall "pub18"; st "public features complete; probes"
  local P="base=$PIT lm=$PLM"; for m in $PUBARMS; do P="$P $m=$F/pub_${m}_L18.pt"; done
  pp() { echo "$P" | tr ' ' '\n' | grep -E "^($(echo $* | tr ' ' '|'))=" | tr '\n' ' '; }
  probe() {  # $1 out dir $2 extra args, rest = proxy names
    local o=$1 x=$2; shift 2; [ -s $o/e4a_mlp.json ] || [ -s $o/le_mlp_${!#}.json ] && return 0
    ( cd $V2 && CUDA_VISIBLE_DEVICES=${PG:-0} python -m hgfm.e4.e4_probe --feats $(pp "$@") $x --out $o > $o.log 2>&1 ) && st "DONE probe $(basename $o)" || st "FAIL probe $(basename $o)"
  }
  probe $O/w/e4/stageA "" base tapt S R
  probe $O/w/stage0/stageA "" base shuf irr full
  probe $O/w/stage0/stageA_clean "" base tapt_clean
  probe $O/w/stage0/le "--subsets $R/xfer/r101/stage0__subsets.json" base tapt S R shuf irr full tapt_clean
  probe $O/w/icpt/stageA_prefix "" base lm icpt
  probe $O/w/icpt/le_prefix "--subsets $R/xfer/r101/stage0__subsets.json" base lm icpt
  [ -d $O/w/stage0/cluster_ci ] || cp -r $WK/stage0/cluster_ci $O/w/stage0/
  ( cd $V2 && python scripts/stage0_analyze.py --w $O/w --clean results/stage0_manifest/eval_clean_keys.json --out $O/stage0_L18.json > $O/stage0_L18.out 2>&1 ) \
    && st "DONE stage0_analyze L18" || st "FAIL stage0_analyze L18"
  ( cd $V2 && python scripts/icpt_le_analyze.py --w $O/w --clusters $O/w/stage0/cluster_ci/clusters.json --out $O/icpt_le_L18.json > $O/icpt_le_L18.out 2>&1 ) \
    && st "DONE icpt_le_analyze L18" || st "FAIL icpt_le_analyze L18"
  ( cd $V2 && python scripts/l18rc_analyze.py pub --w $O/w --stage0 $O/stage0_L18.json --med $O/med_results.json --out $O/pub_results.json > $O/pub_results.out 2>&1 ) \
    && st "DONE pub analysis (R2.1-R2.4 + Holm)" || st "FAIL pub analysis"
}
st "START l18rc driver (GPUs $GPUS)"
for g in ${GPUS//,/ }; do lane $g & done
cpu_lane &
probe_lane &
wait
st "ALL DONE"
