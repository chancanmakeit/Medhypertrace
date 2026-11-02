# TracerTraj public release audit (round 71, 2026-10-28)

Source: AgenTracer GitHub release `data-v1.0.0`, asset `agentracer-data-v1.0.0.zip` (23,997,287 B, md5
f1384beba8ddc552cc9078e78fbbb935), downloaded to Linux #2 `mht_work/tracertraj/` through the server's socks proxy (the
sandbox cannot reach GitHub release assets). The release README says it is an expanded version, not identical to the
paper's TracerTraj-2.5K. Script `data_tools/tracertraj_audit.py`, output `audit.json`.

| split | rows | index convention | agents | median / max steps | test question also in train |
|---|---|---|---|---|---|
| agentic train / test | 1,500 / 600 | **1-indexed** (never 0, max = len(history)) | **every step is "assistant"** (no agent labels) | 7 / 42 | 1 / 600 |
| coding train / test | 1,141 / 127 | 0-indexed (agent matches the labelled step 100%) | MetaGPT roles | 14 / 304 | 0 |
| math train / test | 567 / 63 | 0-indexed | named experts | 7 / 11 | **21 / 63** |

- sha256 of all six files match MANIFEST.json. Agentic `error_source`: Injection Error 1,306 / 516, Diagnosis Error
  (counterfactual) 194 / 84 — the labels are mostly by construction (fault injection).
- ~~No overlap with our held-out E3 sets~~ **Corrected in round 75:** 0 rows share an *exact* normalised question or a
  step text of >= 200 characters, but near-duplicate questions are common: 110 of the 358 E3 trajectories (WW 49, TEgc
  61; the split "WW 47, TEgc 59" written here in round 75 is the >= 0.5 split, corrected round 79) have a TracerTraj train-file question with word-set Jaccard >= 0.3 (106 >= 0.5, 51 >= 0.7, 6 >= 0.9) -- the same
  GAIA tasks with a format instruction prepended ("Please answer in a concise format ..."). The trajectories and labels
  differ (other MAS, injected faults), the tasks do not. E4 re-scored without these 110: `results/e4/README.md`.
- The manifest reports 0 *exact* train/test overlap, but 21 of 63 math test questions also appear in math train.
- Trivial step-level baselines (exact index): the length shortcut that works on Who&When does **not** work here
  (longest step: agentic test 5.7%, coding test 1.6%, math test 22.2% vs random 14.2% / 7.2% / 20.2%; last step agentic
  test 19.7%). Injected faults sit at sampled positions, so a model trained on these labels cannot learn "pick the
  longest step".

- **Round 79 (Stage 0 manifest, `results/stage0_manifest/`):** TracerTraj **test is mostly a near-duplicate of train at the task
  level**: 621 of 768 test trajectories have a train-file question with Jaccard >= 0.3 (321 at >= 0.5, 131 at >= 0.7). The test
  set was only de-duplicated by exact normalised question (round 73). The ~0.92 in-domain rank-AUROC in E4 is therefore not a
  held-out-task number; E4's verdicts used WW / TEgc, not TT test.
