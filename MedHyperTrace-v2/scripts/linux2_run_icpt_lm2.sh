#!/usr/bin/env bash
# Round 91: restart of the LM-CPT arm after the user stopped it in round 88 (step 55 / 791 on GPUs 0,1, no checkpoint).
# Same corpus, recipe and seed as the pre-registration; differences: GPUs 2,3 (same A6000 type, same 2-GPU DDP,
# same accumulation 16), run after the interaction arm, full checkpoints every 100 steps (SAVE_STEPS) so an
# interruption resumes instead of restarting. Then the final stage (stage A / label efficiency / med_eval / compare) on GPU 2.
#   cd $C && setsid nohup bash scripts/linux2_run_icpt_lm2.sh > /data1/ekyang/cgh/CODE/mht_work/icpt/driver_lm2.log 2>&1 &
# Re-runnable: every step is skipped when done; training resumes from the last checkpoint.
ICPT_LIB=1 source "$(dirname "$0")/linux2_run_icpt.sh"
export SAVE_STEPS=${SAVE_STEPS:-100} FG=${FG:-2}
st "START lm2 driver (lm arm on GPUs 2,3 after the icpt arm; SAVE_STEPS=$SAVE_STEPS; final on GPU $FG)"
# 1 wait until the interaction arm has finished training + features (it holds GPUs 2,3)
until grep -qs "DONE arm icpt" $IC/status; do
  grep -qsE "FAIL (train icpt|arm icpt|feats_icpt|featsmed_icpt|featsq_icpt|featsqmed_icpt)" $IC/status && { st "lm2: icpt arm FAIL, stop"; exit 1; }
  sleep 300
done
# 2 once: move the round-88 lm FAIL / KILLED lines out of the status file (final() stops on any FAIL line) and the killed run dir
if [ ! -e $IC/status.r88 ]; then
  cp $IC/status $IC/status.r88
  grep -vE "FAIL|KILLED|PAUSED" $IC/status.r88 > $IC/status
  st "status rotated: round-88 lm FAIL / KILLED lines kept in status.r88"
fi
[ -d $IC/lm ] && [ ! -e $IC/lm_killed_r88 ] && ! ls -d $IC/lm/ckpt/checkpoint-* >/dev/null 2>&1 && mv $IC/lm $IC/lm_killed_r88
# 3 LM-CPT arm on GPUs 2,3 (train -> merge -> prefix / query features on public + medical)
arm lm $COR/lm.jsonl 2,3 29541 pt || exit 1
# 4 final
final
