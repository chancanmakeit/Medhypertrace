#!/usr/bin/env bash
# Reproduce the MAFA human-like-v1 evaluation. Run from the MedHyperTrace repo root.
# Needs: MAFA repo at $MAFA (pinned 908bc74) with `bash scripts/fetch_data.sh` done;
#        MHT_DATA_DIR pointing at the extracted AEGIS-custom-dataset (scripts/restore_env.sh).
set -euo pipefail
MAFA=${MAFA:-/home/claude/mafa-human-ai-annotation}
OUT=eval_mafa/out; mkdir -p $OUT
python3 eval_mafa/adapter.py "$MAFA"                       # §2 sha1 alignment (must be 17/17)
python3 eval_mafa/leakage_check.py "$MAFA" $OUT/leakage.json   # §3 leakage
for s in 0 1 2; do python3 eval_mafa/predict.py --seed $s --mafa_root "$MAFA" --out_dir $OUT; done
L=$MAFA/results/human_like_eval/labels_v1.jsonl
for v in "" _agenthead; do
  for t in ALL MAST MedAgentAudit; do
    T=""; [ $t != ALL ] && T="--taxonomy $t"
    python3 $MAFA/scripts/eval_attribution.py --labels $L --pred $OUT/medhypertrace_pred$v.jsonl $T --out $OUT/report${v}_$t.json >/dev/null
  done
  for s in 1 2; do
    python3 $MAFA/scripts/eval_attribution.py --labels $L --pred $OUT/medhypertrace_pred${v}_seed$s.jsonl --out $OUT/report${v}_ALL_seed$s.json >/dev/null
  done
done
python3 eval_mafa/error_analysis.py "$MAFA" $OUT
python3 eval_mafa/context_in_distribution.py $OUT
python3 eval_mafa/make_report.py $OUT "$MAFA"
# label views added in MAFA cc1606f (defect layer only): orig / code / excl_const
T=$MAFA/results/human_like_eval/traces_v1.jsonl
for v in orig code excl_const; do
  python3 $MAFA/scripts/eval_attribution.py --labels $L --traces $T --view $v --pred $OUT/medhypertrace_pred.jsonl --out $OUT/report_view_$v.json >/dev/null
done
