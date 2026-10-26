#!/usr/bin/env bash
# round 62: wait for the TAPT pilot merge, then SFT (MS-Swift) on the merged model: QD + LQD_mac x {graph,text} x seeds {0,1}
# Copy of /data1/ekyang/cgh/CODE/mht_work/midtrain/chain_sft.sh on Linux #2.
W=/data1/ekyang/cgh/CODE/mht_work; T=$W/midtrain/tapt_pilot_v1
while ! grep -q -E "DONE merged|FAIL" $T/status; do sleep 120; done
grep -q FAIL $T/status && { echo "[$(date -u +%F' '%T)] chain aborted: tapt failed" >> $T/status; exit 1; }
cd $W && LM=$T/Qwen3-8B-tapt_pilot_v1 GPUS="0 1 2 3" FOLDS="QD LQD_mac" VARIANTS="graph text" SEEDS="0 1" Q=$W/midtrain/sft_queue bash run_sft_swift.sh
echo "[$(date -u +%F' '%T)] chain: sft queue finished" >> $T/status
