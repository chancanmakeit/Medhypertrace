# Audit of the medical-aegis protocol-v3 branching eval set (round 84, 2026-11-04)

Offline, no API. Data: medical-aegis `data_runs/eval_v3_2026-11-04/` (repo HEAD 0bf6609; report
`docs/requests/samples/eval_v3_2026-11-04/REPORT.md`). 11,436 points, 324 positives (claim
`outcome_sensitive_under_protocol`), backbone gemini-2.5-flash-lite, eval question pool `datasets/data/pools_v1/eval.json`.

## 1. False positives of the v3 rule (`null_calibration.py` → `null_calibration.out`)
The v3 rule takes the reference answer from the control arm's own mode, then tests "control matches the reference more
often than branch" (one-sided Fisher, 6 vs 6, p < 0.05). Choosing the reference from the arm tested as "higher" biases
toward positives. Under H0 (t has no effect, the 12 finals are exchangeable between arms) we permute the 12 observed
finals over the 12 slots (2,000 draws per stage-2 point) and re-apply the whole rule including the stage-1 screen.
E0 = sum over stage-2 points of P(called positive | multiset, reached stage 2).

| | points | stage 2 | positives | E0 (as run) | FDR ≈ E0 / positives | positives with a pooled-mode reference | E0 | FDR ≈ |
|---|---|---|---|---|---|---|---|---|
| total | 11,436 | 2,125 | 324 | 46.8 | 0.14 | 248 | 27.1 | 0.11 |
| AgentVerse | 2,087 | 674 | 99 | 16.0 | 0.16 | 81 | 10.0 | 0.12 |
| mdagents | 2,975 | 552 | 97 | 12.7 | 0.13 | 77 | 7.0 | 0.09 |
| llm_debate | 2,100 | 443 | 61 | 7.8 | 0.13 | 42 | 4.3 | 0.10 |
| MedAgents | 741 | 114 | 16 | 2.9 | 0.18 | 9 | 1.6 | 0.18 |

Small jobs (MAC, triage, MAM, multimodal) are in the `.out` file; their counts are too small for a stable rate.
E0 conditions on observed multisets that include real effects, so it is a rough upper-bound estimate. The per-test null
rate at stage 2 is about 2.2% (Fisher at 6 vs 6 is conservative); the false positives come from testing about 2,100
points. **Reading:** about one positive in seven is compatible with noise. No relabelling is needed, but each positive
should carry its permutation p-value, and future batches should use a reference that is symmetric in the arms (pooled
mode) or a permutation test.

## 2. Trivial baselines on the eval set (`trivial_baselines.py` → `trivial_baselines.out`)
Within-trajectory AUROC of trivial scores computed from the frozen parent only (positive vs every other point of the
same parent; parents with ≥ 1 positive; positives at the parent's last LLM step, an approximation of "D(t) empty",
are excluded):

| job | parents | positives | step length | relative position (late) | positive vs stage-1-stable, length |
|---|---|---|---|---|---|
| AgentVerse | 85 | 98 | 0.761 [0.704, 0.810] | 0.328 | 0.747 |
| llm_debate | 35 | 41 | 0.814 [0.745, 0.879] | 0.303 | 0.867 |
| mdagents | 62 | 82 | **0.538 [0.467, 0.608]** | 0.528 | 0.547 |
| MedAgents | 10 | 16 | 0.724 [0.557, 0.872] | 0.272 | 0.775 |
| MAC | 8 | 8 | 0.972 | 0.113 | 0.964 |

**Except for mdagents, positives are longer and earlier than the other steps of the same run.** The labelling
procedure does not use length, so this is most likely real (long early analysis steps matter more for the outcome),
not an artefact. But a "longest step" scorer already reaches 0.76–0.81 within trajectories, so any attribution
result on this set must be reported with length / position baselines and the controlled metric (standing rule,
round 68). mdagents is the cleanest subset.

## 3. Data notes for medical-aegis
- In the parent files, the `dataset` field is wrong for the four multimodal sets (`medxpertqa-text`) and the three MAM
  audio sets (`medxpertqa_text`). `trivial_baselines.py` therefore picks the parent file per job.
- "D(t) empty" is not an explicit label field. The last-LLM-step approximation gives AgentVerse 1 / MedAgents 0 /
  MAM heartbeat_a 0 such positives; the medical-aegis report says 5 / 1 / 1.
