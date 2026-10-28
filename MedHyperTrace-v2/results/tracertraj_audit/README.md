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
- **No overlap with our held-out E3 sets**: 0 rows share a normalised question, and 0 share any step text of >= 200
  characters, with Who&When (184) or TraceElephant groupchat (174).
- The manifest reports 0 *exact* train/test overlap, but 21 of 63 math test questions also appear in math train.
- Trivial step-level baselines (exact index): the length shortcut that works on Who&When does **not** work here
  (longest step: agentic test 5.7%, coding test 1.6%, math test 22.2% vs random 14.2% / 7.2% / 20.2%; last step agentic
  test 19.7%). Injected faults sit at sampled positions, so a model trained on these labels cannot learn "pick the
  longest step".
