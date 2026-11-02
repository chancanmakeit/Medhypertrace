# Stage 0 Q4: question-grouped manifest and benchmark audit (round 79, 2026-11-02)

Pre-registration: `docs/design/Stage0_prereg_v1.md`, section Q4 (deliverable, no verdict). Script
`data_tools/build_manifest.py` (md5 `430b0171b4af9c088b280c9a93b80a64`, identical copy on Linux #2 in
`Medhypertrace/MedHyperTrace-v2/data_tools/`; the outputs were produced before a final docstring-only edit). Run on Linux #2 (CPU, ~3 min):
`python -m data_tools.build_manifest build ...` -> `mht_work/stage0_manifest/out/`; the MAA links come from
`python -m data_tools.build_manifest maa-edges` in the sandbox (`maa_edges.json`, MAA stems exist only there).

## What was computed
- **Rule (round 75):** word set = `re.findall('[a-z0-9]+', question.lower())`, Jaccard >= 0.3 (also 0.5 / 0.7). Identical word
  sets share one node; candidate pairs come from an exact AllPairs prefix filter (checked against brute force). 21,529 question
  nodes + 600 MAA nodes, 408,036 links >= 0.3.
- **Items (32,242):** Who&When 184 and TraceElephant groupchat 174 (OAT loader ids), TracerTraj `tt_ww` train 2,889 / val 319 /
  test 768 (by domain), all 26,108 public mas-traj/1 runs (7 datasets; md5 = `mas_traj.md5`), 1,200 medical-aegis anchor normal
  runs (100 questions; export union, md5-checked against the sandbox exports), 600 MAA questions.
- **Training sources:** corpora tapt / S / R / full; NC_shuf = R's runs; NC_irr = WikiText (no MAS question, overlap 0 by
  construction); TT train and val; each public dataset (traceelephant without its groupchat family; public who_and_when and
  TE-groupchat are the evaluation sets themselves); anchors.
- **Two overlap notions.** *group* = the item's connected component (prereg wording) contains a member of the source;
  *direct* = some source question has Jaccard >= thr with the item itself (the rule of round 75 and of
  `hgfm/stage0/eval_overlap_filter.py`, used to filter `full`). **Use direct** (see caveat 1).
- **Corpus membership.** S / R / full rows carry `dataset` + `run_id`. The TAPT training file on Linux #2
  (`mht_work/midtrain/tapt_pilot_v1_train.jsonl`) is text-only, so its rows are resolved through the chunk header
  (`Task (<dataset>, framework <fw>):\n<query>`, `build_corpus.py`) = question-level membership: all 16,271 chunks resolved,
  12,880 runs marked (pilot README: 12,874 runs; +6 = other runs with the same framework and question). The header rule was
  validated on S / R / full: 37,232 / 37,232 rows map back to their own run.
- **Audit:** E4 conventions (candidates = model steps, label = mistake_step + 1, evaluable = label among >= 2 candidates);
  trivial baselines through `hgfm.e4.e4_eval` (raw, and "controlled" = OLS on log length / relative position / has_code with
  trajectory fixed effects, fitted per dataset).

## Files
| file | content |
|---|---|
| `overlap.json` | per evaluation set x source: items with >= 1 mate, group / direct x 0.3 / 0.5 / 0.7, all items and E4-evaluable; corpus mapping stats; component stats; WW+TEgc / TT_test direct overlap by corpus:dataset; MAA summary; checks |
| `eval_clean_keys.json` | WW / TEgc keys `dataset\|id` (as in E4 `feats_base.pt`): `clean` (prereg group rule), `clean_direct` (recommended), `clean_incl_TT_val`, and `per_key` with the overlapping sources (tapt, S, R, full, TT_train, TT_val) for every rule / threshold |
| `audit.json` | audit table below, plus controlled first / last baselines, relative position on the step axis |
| `manifest_eval_compact.json` | the 271 groups (>= 0.3) that contain an evaluation item: source counts + evaluation members |
| `maa_edges.json` | MAA <-> anchor and MAA <-> MAA links (stem vs stem) |
| `build.log` | run log |

Full manifests stay on Linux #2 (`mht_work/stage0_manifest/out/manifest.jsonl.gz`, 276 KB, md5 `c8393b839ffe9058bd7f065a45761f14`, one row
per group with every member's source / split / id / corpora; `manifest_eval.jsonl.gz`, 126 KB, md5 `270c52948534f1e6969ca331f49e0237`):
the only server -> sandbox channel is printed text, too costly for 0.4 MB.

## Overlap: WW + TEgc and TracerTraj test (direct, Jaccard >= 0.3, E4-evaluable trajectories)
| eval set | n | tapt | S | R | full | TT_train | TT_val | aria | aftraj | mast_data | mascope | agentrx_tau | traceelephant_nongc | anchors | WW | TEgc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WW | 182 | 123 | 57 | 95 | 0 | 40 | 9 | 121 | 118 | 125 | 0 | 0 | 0 | 0 | 96 | 138 |
| WW_HC | 58 | 29 | 12 | 21 | 0 | 8 | 2 | 29 | 27 | 29 | 0 | 0 | 0 | 0 | 46 | 46 |
| WW_AG | 124 | 94 | 45 | 74 | 0 | 32 | 7 | 92 | 91 | 96 | 0 | 0 | 0 | 0 | 50 | 92 |
| TEgc | 174 | 147 | 61 | 110 | 0 | 50 | 11 | 142 | 137 | 147 | 0 | 0 | 0 | 0 | 133 | 100 |
| WW+TEgc | 356 | 270 | 118 | 205 | 0 | 90 | 20 | 263 | 255 | 272 | 0 | 0 | 0 | 0 | 229 | 238 |
| TT_test | 768 | 75 | 56 | 61 | 52 | 621 | 371 | 60 | 70 | 41 | 1 | 0 | 0 | 0 | 20 | 24 |
| TT_test_agentic | 599 | 38 | 21 | 29 | 14 | 483 | 263 | 31 | 34 | 30 | 1 | 0 | 0 | 0 | 20 | 24 |
| TT_test_coding | 127 | 14 | 14 | 11 | 14 | 119 | 99 | 10 | 14 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| TT_test_math | 42 | 23 | 21 | 21 | 24 | 19 | 9 | 19 | 22 | 11 | 0 | 0 | 0 | 0 | 0 | 0 |

WW+TEgc direct overlap by corpus part: tapt = AFTraj 255, ARIA 182, MAST-Data 16; R = AFTraj 190, ARIA 63; S = AFTraj 81, ARIA 57,
MAST-Data 1 (same GAIA / AssistantBench tasks; e.g. AFTraj smolagents GAIA runs). At 0.5 / 0.7 the WW+TEgc numbers barely move
(tapt 267 / 266, R 199 / 197, S 110 / 110): these are the same tasks, not loose matches. TT train overlap does drop (86 / 38).

Group rule, evaluable (0.3 / 0.5 / 0.7):

| eval set | n | tapt | S | R | full | TT_train | TT_val |
|---|---|---|---|---|---|---|---|
| WW | 182 | 125 / 122 / 121 | 93 / 54 / 53 | 111 / 92 / 91 | 60 / 0 / 0 | 67 / 38 / 13 | 60 / 9 / 6 |
| WW_HC | 58 | 29 / 28 / 27 | 20 / 11 / 11 | 26 / 20 / 20 | 13 / 0 / 0 | 14 / 7 / 2 | 12 / 2 / 1 |
| WW_AG | 124 | 96 / 94 / 94 | 73 / 43 / 42 | 85 / 72 / 71 | 47 / 0 / 0 | 53 / 31 / 11 | 48 / 7 / 5 |
| TEgc | 174 | 147 / 145 / 145 | 102 / 58 / 57 | 127 / 107 / 106 | 70 / 0 / 0 | 81 / 48 / 25 | 73 / 11 / 7 |
| WW+TEgc | 356 | 272 / 267 / 266 | 195 / 112 / 110 | 238 / 199 / 197 | 130 / 0 / 0 | 148 / 86 / 38 | 133 / 20 / 13 |
| TT_test | 768 | 508 / 26 / 15 | 503 / 13 / 8 | 504 / 18 / 12 | 505 / 6 / 4 | 642 / 331 / 139 | 567 / 215 / 66 |
| TT_test_agentic | 599 | 360 / 23 / 14 | 357 / 11 / 8 | 358 / 16 / 12 | 357 / 3 / 3 | 496 / 297 / 136 | 421 / 185 / 66 |
| TT_test_coding | 127 | 121 / 0 / 0 | 121 / 0 / 0 | 121 / 0 / 0 | 121 / 0 / 0 | 121 / 32 / 3 | 121 / 30 / 0 |
| TT_test_math | 42 | 27 / 3 / 1 | 25 / 2 / 0 | 25 / 2 / 0 | 27 / 3 / 1 | 25 / 2 / 0 | 25 / 0 / 0 |

### Key numbers for the 356 evaluation trajectories (WW 182 + TEgc 174)
- **tapt 270, S 118, R 205, full 0, TT_train 90 (TT train file = train+val: 110)** have a near-duplicate question (direct >= 0.3).
- **Clean subset** (no near-duplicate in any of tapt, S, R, full, TT_train): **85** (WW 58, TEgc 27) by the direct rule,
  84 (WW 57, TEgc 27) by the group rule; adding TT_val: 84 / 84. tapt alone leaves 86, so the clean subset is essentially
  "not in TAPT".
- Clean size per comparison (direct / group), useful for the pre-registered sensitivity analysis: tapt 86 / 84; S 238 / 161;
  R (= shuf) 151 / 118; full 356 / 226; TT_train 266 / 208; S+R 137 / 116; tapt+TT_train (Q1) 85 / 84; full+tapt+TT_train (Q3) 85 / 84.
- Within the evaluation sets: 138 of 182 WW trajectories have a TEgc near-duplicate, 96 another WW trajectory (Hand-Crafted and
  Algorithm-Generated reuse the same GAIA / AssistantBench questions).

## Audit table (E4-evaluable trajectories; Acc@1 / rank-AUROC, raw unless stated)
| set | n | cand. median [IQR] | label rel. pos. mean (median) | label = first / last / longest cand. | random | first | last | longest | longest, controlled |
|---|---|---|---|---|---|---|---|---|---|
| WW_HC | 58 | 31.5 [19, 79.75] | 0.44 (0.33) | 0.017 / 0.121 / 0.155 | 0.046 / 0.500 | 0.017 / 0.558 | 0.121 / 0.442 | 0.155 / 0.761 | 0.069 / 0.505 |
| WW_AG | 124 | 6 [5, 7] | 0.39 (0.33) | 0.161 / 0.048 / 0.290 | 0.166 / 0.500 | 0.161 / 0.605 | 0.048 / 0.395 | 0.290 / 0.658 | 0.073 / 0.464 |
| WW | 182 | 7 [6, 17.5] | 0.41 (0.33) | 0.115 / 0.071 / 0.247 | 0.128 / 0.500 | 0.115 / 0.590 | 0.071 / 0.410 | 0.247 / 0.691 | 0.071 / 0.477 |
| TEgc | 174 | 20.5 [11, 39.75] | 0.44 (0.42) | 0.069 / 0.029 / 0.115 | 0.064 / 0.500 | 0.069 / 0.561 | 0.029 / 0.439 | 0.115 / 0.655 | 0.103 / 0.467 |
| WW+TEgc | 356 | 11 [7, 31] | 0.42 (0.40) | 0.093 / 0.051 / 0.183 | 0.097 / 0.500 | 0.093 / 0.576 | 0.051 / 0.424 | 0.183 / 0.673 | 0.087 / 0.472 |
| TT_test_agentic | 599 | 7 [5, 12] | 0.57 (0.52) | 0.015 / 0.197 / 0.055 | 0.142 / 0.500 | 0.015 / 0.434 | 0.197 / 0.566 | 0.055 / 0.414 | 0.107 / 0.495 |
| TT_test_coding | 127 | 13 [12, 25] | 0.42 (0.40) | 0.008 / 0.039 / 0.016 | 0.072 / 0.500 | 0.008 / 0.582 | 0.039 / 0.418 | 0.016 / 0.563 | 0.008 / 0.459 |
| TT_test_math | 42 | 7 [3, 11] | 0.52 (0.50) | 0.000 / 0.095 / 0.310 | 0.206 / 0.500 | 0.000 / 0.483 | 0.095 / 0.517 | 0.310 / 0.626 | 0.119 / 0.404 |
| TT_test | 768 | 8 [5, 13] | 0.54 (0.50) | 0.013 / 0.165 / 0.062 | 0.134 / 0.500 | 0.013 / 0.461 | 0.165 / 0.539 | 0.062 / 0.451 | 0.091 / 0.484 |

Overlap columns for the same sets (direct >= 0.3, group >= 0.3 in brackets):

| set | n | tapt | S | R | full | TT_train | TT_val | any of tapt/S/R/full/TT_train |
|---|---|---|---|---|---|---|---|---|
| WW_HC | 58 | 29 (29) | 12 (20) | 21 (26) | 0 (13) | 8 (14) | 2 (12) | 29 (29) |
| WW_AG | 124 | 94 (96) | 45 (73) | 74 (85) | 0 (47) | 32 (53) | 7 (48) | 95 (96) |
| WW | 182 | 123 (125) | 57 (93) | 95 (111) | 0 (60) | 40 (67) | 9 (60) | 124 (125) |
| TEgc | 174 | 147 (147) | 61 (102) | 110 (127) | 0 (70) | 50 (81) | 11 (73) | 147 (147) |
| WW+TEgc | 356 | 270 (272) | 118 (195) | 205 (238) | 0 (130) | 90 (148) | 20 (133) | 271 (272) |
| TT_test_agentic | 599 | 38 (360) | 21 (357) | 29 (358) | 14 (357) | 483 (496) | 263 (421) | 487 (499) |
| TT_test_coding | 127 | 14 (121) | 14 (121) | 11 (121) | 14 (121) | 119 (121) | 99 (121) | 119 (121) |
| TT_test_math | 42 | 23 (27) | 21 (25) | 21 (25) | 24 (27) | 19 (25) | 9 (25) | 27 (27) |
| TT_test | 768 | 75 (508) | 56 (503) | 61 (504) | 52 (505) | 621 (642) | 371 (567) | 633 (647) |

Reproduced E4 numbers: pooled WW+TEgc random 0.097 / 0.500, longest 0.183 / 0.673, longest controlled 0.087 / 0.472; WW longest
0.247 / 0.691; TEgc 0.115 / 0.655; TT test random 0.134, longest 0.062 / 0.451 (all as in `results/e4/README.md`).
Relative position = index of the label among the candidates / (n - 1). Hand-Crafted WW labels almost never sit on the first
candidate (1.7%) and favour long steps (longest rank-AUROC 0.761); the TracerTraj agentic test labels are often the last
step (19.7%) and anti-correlated with length (0.414).

### Other label sources (descriptive, no step baselines)
| source | layer | what was verified | numbers |
|---|---|---|---|
| MAA human evaluation | defect (step x code, present?) | `mht_work/maa/maa_human400.jsonl` on Linux #2 | 400 instances, 3 votes each; majority yes 158 / no 242; 10 codes x 40; auditor-stratified 200 / 200; 285 questions, 391 runs; MAS medagent 107, colacare 92, healthcareagent 71, mac 67, reconcile 49, mdagents 14. No responsibility (step) label. |
| MAST-Data | trajectory-level failure modes | `mast_data.jsonl.gz` | 1,630 runs, MAST-14 codes; any_failure 1,235 / none 395; 5,133 positive codes; no step index. |
| AgentRx (tau-bench) | step-level root cause | `agentrx_tau.jsonl.gz` | 29 failed runs, all labelled; 39 failure annotations with step numbers, 1 root-cause failure per run. |
| AgentRx (Magentic) | step-level | `who_and_when.convert_report.json` | labels attached to 44 of 58 AgentRx-Magentic trajectories (inside Who&When); 14 without label. Not counted separately here. |
| medical-aegis branching pilot | counterfactual flips | `medical-aegis/docs/requests/samples/position_check_2026-10-27/REPORT.md` table | 79 points, 12 flips (cells sum: llm_debate round 1 20 / 5, round 2 19 / 0, mdagents 40 / 7). From the report table, not re-derived from raw runs. |

MAA vs anchors (stem vs stem): 4 anchor questions link to MAA. 2 are the known identical questions (medxpertqa_text_1499 /
1939, Jaccard 1.0; their anchor runs are excluded from all corpora, verified: their groups have no corpus member). 2 are loose
matches (anchor 1071 ~ MAA 2259 at 0.31, anchor 137 ~ MAA 765 at 0.35) whose anchor runs **are** in tapt / S / R / full; none at
>= 0.5. Non-medical sets are not compared with MAA.

## Caveats and deviations
1. **The connected-component rule degenerates at 0.3.** One component holds 14,262 items (ARIA 10,498, TT train 2,048, AFTraj 662,
   TT test 479, MAST-Data 347, TT val 222, ...), chained through templated questions. Group counts at 0.3 are therefore inflated:
   `full` shows 130 WW+TEgc group-mates although no `full` question is within 0.3 of any of them (direct 0, as the filter
   intends), and every TT coding test item is in the giant group. At 0.5 / 0.7 group and direct agree (largest components 1,028 /
   336). Recommendation: use the direct rule (`clean_direct`); for WW+TEgc it changes the clean subset by one trajectory.
2. **round-75 "110" reproduced:** direct >= 0.3 against the TracerTraj train file (train + val) on the 358 loader trajectories:
   WW 49 + TEgc 61 = 110; >= 0.5: 47 + 59 = 106; >= 0.7: 19 + 32 = 51 (round 75: 110 / 106 / 51). The per-dataset split
   "WW 47, TEgc 59" in `results/tracertraj_audit/README.md` is the >= 0.5 split, not >= 0.3. All 110 are among the 356 evaluable
   trajectories (the 2 non-evaluable WW trajectories do not overlap).
3. **TEgc = 174** (OAT loader). The 176 public TE-groupchat runs all share their word set with a loaded trajectory, so
   nothing is lost.
4. **TracerTraj test is mostly a near-duplicate of train:** 621 / 768 test trajectories have a train question at >= 0.3, 321 at
   >= 0.5, 131 at >= 0.7 (coding 119 / 127 at 0.3). In-domain numbers (~0.92 rank-AUROC) are not held-out at the task level.
5. `full` was filtered against WW+TEgc only; it still overlaps TracerTraj test (52 at 0.3, mostly math 24 / 42 and coding 14).
6. TAPT membership is question-level (header rule), S / R / full run-level; for overlap only the question matters.
7. Anchor questions are compared with MAA after `norm_stem` (options cut) because MAA has stems only; elsewhere anchors use the
   full query like every other item.
