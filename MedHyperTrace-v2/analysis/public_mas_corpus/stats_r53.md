# Public MAS failure-attribution datasets, round 53: trajectory-text token stats

Tokenizer: Qwen/Qwen3-8B (add_special_tokens=False). Same protocol as stats.md: only natural-language trajectory content is counted (task question, message/step contents, final output, tool-call argument values, tool results); JSON keys, labels, annotations, injection metadata, repairs/counterfactuals excluded. Generated 2026-10-22 in the local sandbox; raw data under /home/claude/public_mas/raw/, scripts `scripts/*_r53.py`.

## Summary

| Dataset | Trajectories | Steps (total / p50) | Total tokens | Global exact-dedup tokens | p50 / p90 / p99 / max per traj | >8K / >32K | Top benchmarks (token share) |
|---|---|---|---|---|---|---|---|
| microsoft/AgentRx | gated - not downloaded | not measured | not measured | not measured | not measured | not measured | gated, user must accept terms |
| CORRECT-Error (all injected) | 2226 | 26311 / 10 | 16.35M | 14.71M | 4983 / 15480 / 20818 / 96863 | 902 / 5 | wikimqa 43%, hotpot 28%, musique 18%, arc 5% |
| AFTraj (safe+unsafe) | 2276 | 26306 / 11 | 1.82M | 1.26M | 467 / 1395 / 6553 / 13823 | 9 / 0 | MATH 28%, coding/humaneval 13%, coding/mbpp 10%, HotpotQA 7% |
| ARIA (all; incl. medical MMLU) | 24468 | 128009 / 3 | 46.36M | 42.64M | 282 / 3722 / 24560 / 70768 | 1673 / 47 | mmlu 53%, olympiadbench 25%, gaia 8%, gsm-plus 6% |
| Who&When-Pro mirror, text | 6257 | 39060 / 4 | 17.69M | 11.39M | 1641 / 6880 / 13816 / 23473 | 440 / 0 | dsqa/smolagents 26%, simpleqa_verified/magentic-one 6%, math/debate 6%, scibench/debate 6% |
| Who&When-Pro mirror, video (text-in-JSON only) | 916 | 3579 / 3 | 4.01M | 3.01M | 1024 / 14664 / 63472 / 80070 | 131 / 15 | lvbench/dvd 81%, lvbench/eva 19% |
| AgentErrorBench (single-agent) | 200 | 10026 / 60 | 4.24M | 3.60M | 16046 / 41780 / 63824 / 69173 | 175 / 32 | alfworld 53%, webshop 32%, gaia 15% |
| MAScope MAST-clean (MAST subset) | 851 | not measured | 30.24M | 19.95M | 7647 / 110540 / 193940 / 512476 | 422 / 270 | ProgramDev-v2 60%, ProgramDev 29%, GAIA 10% |
| MAScope LG-Ctrl | 408 | 6475 / 13 | 2.03M | 1.70M | 3565 / 11777 / 15852 / 19290 | 95 / 0 | planning 100% |
| MAScope Inject-Mix | 961 | 16452 / 14 | 3.41M | 2.73M | 3673 / 6377 / 7920 / 8710 | 2 / 0 | planning 54%, rag 32%, tooluse 14% |
| RogerYao/RAISER | 0 (labels only) | - | 0 | 0 | - | - | references AEGIS/CORRECT/MAST/TE/TRAIL/W&W traces |
| ATBench (1,000; single-agent) | 1000 | 9009 / 8 | 3.20M | 3.17M | 1092 / 2687 / 80608 / 100357 | 30 / 25 | indirect_prompt_injection 44%, unreliable_or_misinformation 20%, safe 19%, inherent_agent_failures 9% |
| ATBench500 (single-agent) | 500 | 4486 / 10 | 0.71M | 0.70M | 1142 / 2797 / 4927 / 6869 | 0 / 0 | safe 34%, indirect_prompt_injection 12%, direct_prompt_injection 9%, tool_description_injection 8% |

Total tokens = sum over trajectories as stored, except AgentErrorBench, whose user prompts re-embed earlier observations: there it is within-trace unique lines (raw as stored: 21.79M). ARIA excludes OpenManus `agent_run_completed` roll-ups that re-concatenate the step outputs. Global exact-dedup = unique segment texts across the dataset (segment = message/turn/event; MAScope = blank-line paragraph as for MAST; AgentErrorBench = line).

## Grand total of new, non-medical, non-duplicated tokens

union over r53 datasets (text only; WWP video excluded; AgentRx gated; RAISER has no text), exact segment dedup across all r53 sets, segments already present in the old 5 sets removed, trajectories flagged medical removed (ARIA MMLU core-medical subjects + keyword heuristic >=2 distinct medical terms in the task question elsewhere); a segment shared by a natural/clean and an injected trajectory is credited to natural/clean.

| scope | (a) natural / clean | (b) injected | total | removed as already in old 5 sets |
|---|---|---|---|---|
| all r53 text sets | 45.48M | 32.40M | 77.88M | 20.18M |
| MAS only (drops AgentErrorBench, ATBench, ATBench500) | 41.07M | 29.38M | 70.46M | 20.18M |

Per-dataset contribution (after cross-set dedup, in order of crediting):

| dataset | natural/clean | injected | medical trajectories removed (n / tokens) |
|---|---|---|---|
| AFTraj | 1.13M | 0.12M | 1 / 0.00M |
| ARIA | 39.03M | 0.00M | 2258 / 3.63M |
| AgentErrorBench | 3.60M | 0.00M | 0 / 0.00M |
| MAScope/LG-Ctrl | 0.35M | 1.35M | 0 / 0.00M |
| MAScope/Inject-Mix | 0.56M | 2.13M | 9 / 0.03M |
| ATBench/ATBench | 0.58M | 2.57M | 12 / 0.01M |
| ATBench/ATBench500 | 0.22M | 0.44M | 27 / 0.04M |
| CORRECT-Error | 0.00M | 14.68M | 3 / 0.03M |
| WhoWhenPro-mirror (text) | 0.00M | 11.10M | 40 / 0.14M |

## Per-dataset notes

### 1. microsoft/AgentRx

- **Gated (gated=auto): all 4 data files return 403 GatedRepoError with the provided read token; the user must accept the terms on HF.** README is public: license CC-BY-4.0; failed trajectories from tau-retail and Magentic-One with step-level failure categories, failed_agent per failure and a designated root-cause failure (agent + step + category). Files: magentic_dataset.jsonl 4.2 MB, tau_retail_dataset.jsonl 0.83 MB, plus label files. Natural failures (no injection mentioned). Not measured.

### 2. yifanyu/CORRECT-Error

- License Apache-2.0. 2,226 trajectories, **all error-injected** (Magentic-One runs, then contextual error injection; no clean subset). Labels: mistake_agent + mistake_step (decisive error) + free-text reason (often empty). Generators: gpt-4o-mini / gpt-5-nano.
- Injected trajectories, token parts: prefix 6,410,633, injected_step 910,140, post 9,032,251; prefix+task deduplicated by (task, exact segment) = 6,069,141.
- Unique questions 1264 (task reuse across generators/injections). Medical-flagged trajectories: 3 (0.03M; {'heuristic': 3}).
- MAA overlap: 0 exact normalized question matches (2220 questions); first-60-char probes: 0 / 554 hits over 60M normalized chars; planted control found = True.
- Cross-dataset question overlap (1264 distinct questions): AFTraj exact 249 / first-60 271, OLD:AEGIS exact 15 / first-60 25, ARIA exact 18 / first-60 20, OLD:TraceElephant exact 14 / first-60 16, OLD:Who&When exact 14 / first-60 15, WhoWhenPro-mirror (text) exact 0 / first-60 13.

#### CORRECT-Error by benchmark

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| wikimqa | 733 | 6957974 | 6257779 | 8931 | 16412 | 374 | 0 | 42.5% |
| hotpot | 578 | 4556458 | 4072609 | 5721 | 15388 | 262 | 1 | 27.9% |
| musique | 312 | 2974284 | 2687845 | 11366 | 15836 | 177 | 1 | 18.2% |
| arc | 304 | 820223 | 732433 | 333 | 12248 | 43 | 2 | 5.0% |
| math500 | 157 | 452162 | 437912 | 1122 | 7049 | 13 | 1 | 2.8% |
| gaia | 50 | 309453 | 256128 | 5588 | 12943 | 18 | 0 | 1.9% |
| mmlu_pro | 92 | 282470 | 268870 | 547 | 12894 | 15 | 0 | 1.7% |

#### CORRECT-Error by generator

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| gpt-5-nano | 1908 | 15246870 | 13674474 | 6154 | 15843 | 860 | 4 | 93.2% |
| gpt-4o-mini | 318 | 1106154 | 1086949 | 1654 | 10616 | 42 | 1 | 6.8% |

### 3. ZBox008003/AFTraj (AFTraj-2K)

- License CC-BY-4.0. Classes: clean 1162 (1.09M), natural_fail 386 (0.37M), injected 728 (0.37M). Safe = verified-successful (clean) runs; unsafe = 728 injected into verified-safe runs + 386 naturally failed runs labelled by a multi-judge propose-verify pipeline ('diagnosed'). Labels: mistake_step (k*) + mistake_agent (a*) + optional reason. Injected traces share their prefix with the safe originals (removed by exact dedup).
- Injected trajectories, token parts: prefix 214,966, injected_step 57,169, post 91,206, task 2,854; prefix+task deduplicated by (task, exact segment) = 207,564.
- Medical-flagged trajectories: 1 (0.00M; {'heuristic': 1}).
- MAA overlap: 0 exact normalized question matches (2276 questions); first-60-char probes: 0 / 554 hits over 7M normalized chars; planted control found = True.
- Cross-dataset question overlap (1381 distinct questions): OLD:AEGIS exact 466 / first-60 480, ARIA exact 248 / first-60 280, CORRECT-Error exact 249 / first-60 271, OLD:Who&When exact 88 / first-60 104, OLD:TraceElephant exact 88 / first-60 103, WhoWhenPro-mirror (text) exact 0 / first-60 91.

#### AFTraj by domain/class

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| agentic/clean | 405 | 562213 | 453531 | 350 | 4880 | 4 | 0 | 30.8% |
| agentic/natural_fail | 322 | 297514 | 226287 | 438 | 2326 | 3 | 0 | 16.3% |
| math/clean | 396 | 279917 | 244446 | 518 | 1222 | 2 | 0 | 15.3% |
| coding/clean | 361 | 245362 | 150743 | 594 | 1102 | 0 | 0 | 13.5% |
| coding/injected | 247 | 162560 | 118761 | 569 | 1153 | 0 | 0 | 8.9% |
| math/injected | 333 | 156762 | 134441 | 393 | 744 | 0 | 0 | 8.6% |
| math/natural_fail | 64 | 72708 | 65410 | 853 | 2370 | 0 | 0 | 4.0% |
| agentic/injected | 148 | 46873 | 46673 | 322 | 526 | 0 | 0 | 2.6% |

#### AFTraj by benchmark

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| MATH | 793 | 509387 | 355586 | 475 | 1067 | 2 | 0 | 27.9% |
| coding/humaneval | 251 | 231285 | 115536 | 840 | 1395 | 0 | 0 | 12.7% |
| coding/mbpp | 357 | 176637 | 72200 | 468 | 753 | 0 | 0 | 9.7% |
| HotpotQA | 476 | 131000 | 127510 | 287 | 395 | 0 | 0 | 7.2% |
| GAIA | 200 | 106836 | 100234 | 473 | 823 | 0 | 0 | 5.9% |
| agentic/movie_multi | 11 | 83949 | 64397 | 7554 | 9837 | 4 | 0 | 4.6% |
| agentic/stats_multi | 12 | 77759 | 49532 | 5560 | 7825 | 1 | 0 | 4.3% |
| agentic/movie_award | 12 | 74384 | 63193 | 6448 | 7089 | 0 | 0 | 4.1% |
| agentic/research_papers | 11 | 55413 | 45844 | 4884 | 6065 | 0 | 0 | 3.0% |
| agentic/geo_population | 10 | 49380 | 36292 | 4934 | 6782 | 1 | 0 | 2.7% |
| agentic/stats_simple | 11 | 46390 | 34218 | 4240 | 4876 | 0 | 0 | 2.5% |
| agentic/geo_compare | 12 | 36183 | 29777 | 3214 | 3873 | 0 | 0 | 2.0% |
| agentic/unsafe_research | 18 | 33904 | 16069 | 1321 | 3280 | 0 | 0 | 1.9% |
| agentic/indirect_injection | 8 | 25838 | 16619 | 2689 | 5785 | 0 | 0 | 1.4% |
| agentic/health_advisory | 5 | 24015 | 18661 | 4008 | 6188 | 0 | 0 | 1.3% |
| agentic/sports_record | 12 | 21768 | 17610 | 1755 | 2327 | 0 | 0 | 1.2% |
| agentic/unsafe_geo | 18 | 16655 | 7897 | 872 | 1113 | 0 | 0 | 0.9% |
| agentic/quarterly_report | 4 | 16402 | 12677 | 4105 | 4532 | 0 | 0 | 0.9% |
| agentic/record_audit | 5 | 14927 | 11177 | 3007 | 3276 | 0 | 0 | 0.8% |
| agentic/log_incident | 5 | 13025 | 8748 | 2520 | 3028 | 0 | 0 | 0.7% |
| agentic/vendor_invoice | 5 | 10265 | 6209 | 2328 | 2375 | 0 | 0 | 0.6% |
| agentic/stale_db | 4 | 10164 | 8664 | 2516 | 2721 | 0 | 0 | 0.6% |
| agentic/market_research | 1 | 9377 | 8835 | 9377 | 9377 | 1 | 0 | 0.5% |
| agentic/vendor_onboarding | 5 | 9084 | 6211 | 1812 | 1856 | 0 | 0 | 0.5% |
| agentic/premature_payment | 5 | 8801 | 4570 | 1745 | 2368 | 0 | 0 | 0.5% |
| agentic/customer_refund | 5 | 8421 | 6697 | 1586 | 1919 | 0 | 0 | 0.5% |
| agentic/wrong_count | 5 | 7697 | 6092 | 1500 | 1646 | 0 | 0 | 0.4% |
| agentic/unsafe_movie | 8 | 6984 | 3304 | 868 | 981 | 0 | 0 | 0.4% |
| agentic/credential_lookup | 5 | 5598 | 2994 | 1109 | 1200 | 0 | 0 | 0.3% |
| agentic/unsafe_premature | 1 | 1690 | 748 | 1690 | 1690 | 0 | 0 | 0.1% |
| agentic/unsafe_wrong | 1 | 691 | 358 | 691 | 691 | 0 | 0 | 0.0% |

### 4. Edlison/ARIA

- License: none declared on the card (no license field). 24,468 episodes (train 14,683 / validation 4,895 / test 4,890). Frameworks AG2, OpenManus, MetaGPT, Magentic-One; benchmarks GAIA, GSM-Plus, HumanEval, MMLU, OlympiadBench, SWE-bench-Lite. **Natural runs (no injection)**: natural_fail 19849 (39.78M), clean 4619 (6.58M) (clean = source_success True). Labels are model-generated: first-bad event ids (step), primary/secondary error codes (category), responsible agents. Repairs/replacement events and counterfactuals excluded.
- Token parts: turn 38.66M, tool_result 3.81M, final 2.37M, task 1.32M, rollup_dup 0.43M, toolcall_arg 0.13M, artifact 0.08M. tool_result = OpenManus after_act contents that equal/contain the tool_results (counted once, not twice). OpenManus agent_run_completed roll-ups: {'rollup_dup': 1403, 'final': 13116} (rollup_dup = >=80% re-concatenated step outputs, excluded from totals; 'final' kept).
- **MMLU = 11848 episodes (24.78M), subject read from the 'Subject:' line (11848 detected), 6557 distinct questions. Medical subjects (anatomy, clinical_knowledge, college_biology, college_medicine, high_school_biology, human_aging, medical_genetics, nutrition, professional_medicine, virology): 2231 episodes, 3.62M tokens (3.59M dedup).** Borderline (high_school_psychology, human_sexuality, professional_psychology): 543 episodes, 0.69M (kept).
- Medical subjects: clinical_knowledge 589 (0.80M), anatomy 309 (0.50M), college_biology 261 (0.19M), college_medicine 240 (0.38M), virology 208 (0.16M), nutrition 186 (0.57M), human_aging 177 (0.57M), professional_medicine 115 (0.11M), high_school_biology 103 (0.27M), medical_genetics 43 (0.06M).
- Medical-flagged trajectories: 2258 (3.63M; {'heuristic': 27, 'mmlu_subject': 2231}). = the 2231 MMLU medical-subject episodes + non-MMLU tasks hit by the keyword heuristic (mostly GSM-Plus word problems set in a hospital/clinic - false positives, dropped anyway).
- MAA overlap: 0 exact normalized question matches (24468 questions); first-60-char probes: 0 / 554 hits over 183M normalized chars; planted control found = True.
- Cross-dataset question overlap (16919 distinct questions): AFTraj exact 248 / first-60 280, OLD:AEGIS exact 190 / first-60 189, OLD:TraceElephant exact 106 / first-60 106, OLD:Who&When exact 104 / first-60 104, WhoWhenPro-mirror (text) exact 0 / first-60 68, OLD:MAST exact 43 / first-60 47.

#### ARIA by framework

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| magentic-one | 2524 | 19435343 | 19330919 | 4444 | 20599 | 1071 | 15 | 41.9% |
| openmanus | 14519 | 11399043 | 7837766 | 114 | 464 | 410 | 26 | 24.6% |
| ag2 | 2902 | 8009331 | 7993095 | 1601 | 5627 | 178 | 6 | 17.3% |
| metagpt | 4523 | 7519789 | 7487700 | 1355 | 2875 | 14 | 0 | 16.2% |

#### ARIA by benchmark

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| mmlu | 11848 | 24777403 | 24561472 | 1071 | 3848 | 984 | 0 | 53.4% |
| olympiadbench | 1461 | 11563701 | 8807137 | 3305 | 21827 | 463 | 19 | 24.9% |
| gaia | 337 | 3863518 | 3830285 | 6210 | 31222 | 129 | 25 | 8.3% |
| gsm-plus | 10177 | 2743741 | 2193124 | 115 | 728 | 8 | 0 | 5.9% |
| swe-bench-lite | 402 | 2710219 | 2656492 | 4127 | 16542 | 84 | 3 | 5.8% |
| humaneval | 243 | 704924 | 591130 | 2647 | 4959 | 5 | 0 | 1.5% |

#### ARIA by class

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| natural_fail | 19849 | 39784397 | 37057917 | 260 | 4639 | 1500 | 38 | 85.8% |
| clean | 4619 | 6579109 | 5589237 | 371 | 2098 | 173 | 9 | 14.2% |

#### ARIA by host model

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| llama31-70b | 13855 | 22525587 | 21811691 | 146 | 2317 | 1000 | 0 | 48.6% |
| claude-opus-4-8 | 688 | 8371635 | 5619097 | 8179 | 27081 | 344 | 18 | 18.1% |
| qwen3-32b-nonthinking | 2461 | 4147100 | 4136466 | 1456 | 2790 | 3 | 0 | 8.9% |
| claude-sonnet-4-6 | 512 | 4055671 | 4052220 | 5981 | 16084 | 160 | 6 | 8.7% |
| gpt-5-5-xhigh | 138 | 2203071 | 2169961 | 11718 | 36521 | 85 | 19 | 4.8% |
| qwen3-8b-nonthinking | 5429 | 2028932 | 1876569 | 130 | 876 | 5 | 0 | 4.4% |
| gpt-5-5-high | 674 | 1538436 | 1511314 | 843 | 1240 | 46 | 3 | 3.3% |
| gpt-5-5-medium | 711 | 1493074 | 1472801 | 937 | 4012 | 30 | 1 | 3.2% |

### 5. Leoxx/whowhen_pro (Who&When Pro mirror)

- License CC-BY-4.0. **The mirror gives readable text traces: 6257 text rows (all 6,257 listed in the broken tmpxv7 release, incl. the 5,946 that were dangling symlinks there) + 916 video rows.** All injected (one injected error per trace; no clean subset). Labels: agent + step (or round/position/stage) + error mode (17 modes / 6 categories).
- vs tmpxv7: real tmpxv7 files {'video': 916, 'text': 311}; mirror traces whose query matches a tmpxv7 real file: {'text': 311, 'video': 916}; mirror traces with >=95% of tokens in tmpxv7 segments: {'text': 311, 'video': 906}.
- Injection located (prefix/injected/post split possible) per modality/framework/located: {'text/alfagent/True': 311, 'text/macnet/True': 261, 'text/metagpt/True': 81, 'text/smolagents/True': 3199, 'text/smolagents/False': 77, 'text/magentic-one/True': 811, 'text/debate/True': 445, 'text/dylan/True': 152, 'text/mathchat/True': 920, 'video/dvd/True': 168, 'video/eva/True': 748}. Marker used: step_number == ground_truth.step (alfagent, smolagents; 77 smolagents traces have gt.step beyond the recorded steps -> 'unlocated'), is_injected flag (macnet, metagpt, mathchat, debate/dylan turns), phase contains 'injected' (magentic-one), injected flag (video). Injected trajectories, token parts: prefix 10,000,203, injected_step 2,139,963, post 4,912,657, unlocated 633,380; prefix+task deduplicated by (task, exact segment) = 4,663,554.
- Medical heuristic is conservative and noisy (e.g. dabench 'vaccinations per hundred people' table questions are flagged); flagged traces are dropped from the grand total.
- Single- vs multi-agent: alfagent and smolagents are single-agent (3,587 of 6,257 text traces); magentic-one, macnet, metagpt, debate, dylan, mathchat are multi-agent.
- image / image_gui splits (6.8 GB / 11.2 GB, images embedded) not downloaded; 32 KB range peek shows the same row schema ['id', 'framework', 'benchmark', 'task'] (first rows: ['smolagents', 'browsecomp_vl'], ['agentoccam', 'webvoyager']).
- Medical-flagged trajectories: 40 (0.14M; {'heuristic': 40}).
- MAA overlap: 0 exact normalized question matches (7173 questions); first-60-char probes: 0 / 554 hits over 76M normalized chars; planted control found = True.
- Cross-dataset question overlap (2599 distinct questions): OLD:AEGIS exact 0 / first-60 99, AFTraj exact 0 / first-60 91, ARIA exact 0 / first-60 68, OLD:Who&When exact 0 / first-60 29, OLD:TraceElephant exact 0 / first-60 28, CORRECT-Error exact 0 / first-60 13.

#### Who&When-Pro mirror text by benchmark/framework

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| dsqa/smolagents | 830 | 4625490 | 2815396 | 4773 | 10680 | 181 | 0 | 26.2% |
| simpleqa_verified/magentic-one | 509 | 1082273 | 668658 | 1509 | 3998 | 4 | 0 | 6.1% |
| math/debate | 144 | 1065693 | 902017 | 7752 | 10632 | 59 | 0 | 6.0% |
| scibench/debate | 171 | 1020052 | 876755 | 5517 | 9188 | 31 | 0 | 5.8% |
| tablebench/smolagents | 913 | 964587 | 719901 | 813 | 1829 | 1 | 0 | 5.5% |
| dacode/smolagents | 306 | 923088 | 523229 | 2598 | 4552 | 7 | 0 | 5.2% |
| scibench/dylan | 83 | 915643 | 669395 | 10591 | 13960 | 71 | 0 | 5.2% |
| gaia/magentic-one | 302 | 868471 | 377794 | 2123 | 5329 | 8 | 0 | 4.9% |
| gpqa/dylan | 69 | 825851 | 695314 | 11792 | 15042 | 64 | 0 | 4.7% |
| databench/smolagents | 818 | 749292 | 459571 | 816 | 1407 | 0 | 0 | 4.2% |
| math/mathchat | 304 | 529765 | 286973 | 1430 | 2564 | 2 | 0 | 3.0% |
| scibench/mathchat | 301 | 526919 | 275476 | 1534 | 2085 | 0 | 0 | 3.0% |
| mmlu_pro/mathchat | 315 | 518078 | 244149 | 1514 | 2312 | 0 | 0 | 2.9% |
| dabench/smolagents | 327 | 488928 | 313752 | 1230 | 2626 | 0 | 0 | 2.8% |
| bigcodebench/macnet | 170 | 483291 | 258471 | 2761 | 3761 | 0 | 0 | 2.7% |
| alfworld/alfagent | 311 | 464637 | 220917 | 1380 | 2221 | 0 | 0 | 2.6% |
| livecodebench_pro/macnet | 73 | 379577 | 224335 | 4985 | 7401 | 1 | 0 | 2.1% |
| gpqa/debate | 74 | 363599 | 302396 | 4463 | 6836 | 3 | 0 | 2.1% |
| livecodebench_pro/metagpt | 56 | 302269 | 204232 | 5148 | 6898 | 0 | 0 | 1.7% |
| kramabench/smolagents | 82 | 271944 | 148018 | 2873 | 5411 | 2 | 0 | 1.5% |
| mmlu_pro/debate | 56 | 246236 | 181801 | 3733 | 8111 | 6 | 0 | 1.4% |
| bigcodebench/metagpt | 25 | 43061 | 31078 | 1534 | 2327 | 0 | 0 | 0.2% |
| humaneval/macnet | 18 | 27459 | 15393 | 1436 | 2148 | 0 | 0 | 0.2% |

Video (text-in-JSON only, not in grand total): 916 traces, 4.01M. Injected trajectories, token parts: prefix 3,743,860, injected_step 49,500, post 214,907; prefix+task deduplicated by (task, exact segment) = 2,962,387.

### 6. davide221/agenterrorbench

- License: none declared on the card. 200 trajectories (train 139 / validation 31 / test 30) - this is AgentDebug's AgentErrorBench: **single-agent** (ALFWorld 100, GAIA 50, WebShop 50; GPT-4o, Llama3.3-70B, Qwen3-8B). **Natural failures** (all failed; no clean subset, no injection). Labels: critical_failure_step + module (memory/reflection/planning/action/system) + failure type, plus per-step annotations.
- Each user turn re-embeds recent observations (GAIA pages are re-pasted every step): raw as stored 21.79M vs within-trace unique lines 4.24M.
- Medical-flagged trajectories: 0 (0.00M; {}).
- MAA overlap: 0 exact normalized question matches (200 questions); first-60-char probes: 0 / 554 hits over 75M normalized chars; planted control found = True.
- Cross-dataset question overlap (98 distinct questions): AFTraj exact 15 / first-60 17, ARIA exact 14 / first-60 16, OLD:Who&When exact 14 / first-60 15, OLD:TraceElephant exact 11 / first-60 12, OLD:AEGIS exact 5 / first-60 6, WhoWhenPro-mirror (text) exact 0 / first-60 3.

#### AgentErrorBench by benchmark

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| alfworld | 100 | 2253278 | 1909141 | 15212 | 43095 | 100 | 21 | 53.2% |
| webshop | 50 | 1356192 | 1221574 | 27396 | 42848 | 47 | 10 | 32.0% |
| gaia | 50 | 628697 | 473529 | 10725 | 22918 | 28 | 1 | 14.8% |

#### AgentErrorBench by model

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| Qwen3-8B | 62 | 1842232 | 1673793 | 32831 | 55207 | 47 | 31 | 43.5% |
| GPT-4o | 81 | 1288172 | 1078624 | 14256 | 23394 | 76 | 1 | 30.4% |
| Llama3.3-70B-Turbo | 57 | 1107763 | 980948 | 17440 | 30378 | 52 | 0 | 26.1% |

### 7. mascope/mascope-bench

- License CC-BY-4.0 (MAST-clean retains MAST upstream terms). Labels: trace-level MAST-14 multi-label failure categories + communication-topology label; no agent/step labels.
- **MAST-clean (851 traces) vs mcemri/MAST-Data: {'exact_string': 851}. Duplicates (exact or paragraph-Jaccard >= 0.9): 851 / 851.** Framework counts MAST-clean {'MetaGPT': 430, 'ChatDev': 256, 'Magentic': 165} vs MAST-Data {'ChatDev': 330, 'MetaGPT': 430, 'OpenManus': 30, 'Magentic': 195, 'AG2': 597, 'AppWorld': 30, 'HyperAgent': 30}. Dedup tokens 19.95M, of which not already MAST paragraphs: 0.00M. Natural runs (MAST); traces with >=1 MAST failure code: 773 of 851 (the rest are all-zero, i.e. no annotated failure).
- LG-Ctrl: injected 328 (1.66M), clean 80 (0.37M). Anomaly-injection-derived synthetic runs (LangGraph / AutoGen-based debate etc.) on planning/RAG tasks; anomaly 'None' rows are the uninjected controls (clean). No step marker for the injection inside the raw string. Labels with any MAST code: 328.
- Inject-Mix: injected 781 (2.78M), clean 180 (0.64M). Anomaly-injection-derived synthetic runs (LangGraph / AutoGen-based debate etc.) on planning/RAG tasks; anomaly 'None' rows are the uninjected controls (clean). No step marker for the injection inside the raw string. Labels with any MAST code: 781.
- Medical-flagged trajectories: 0 (0.00M; {}). Medical-flagged trajectories: 0 (0.00M; {}). Medical-flagged trajectories: 9 (0.03M; {'heuristic': 9}).
- MAA overlap: 0 exact normalized question matches (1369 questions); first-60-char probes: 0 / 554 hits over 144M normalized chars; planted control found = True.
- Cross-dataset question overlap (130 distinct questions): OLD:MAST exact 130 / first-60 130.

#### MAST-clean by framework

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| ChatDev | 256 | 25827960 | 16232572 | 94785 | 160455 | 256 | 256 | 85.4% |
| Magentic | 165 | 3161640 | 2889128 | 15893 | 31331 | 165 | 14 | 10.5% |
| MetaGPT | 430 | 1248252 | 826694 | 2177 | 6351 | 1 | 0 | 4.1% |

#### LG-Ctrl by anomaly

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| None | 80 | 370638 | 349981 | 3503 | 11816 | 18 | 0 | 18.2% |
| loop_failure | 63 | 345774 | 335071 | 5007 | 12126 | 16 | 0 | 17.0% |
| over_constraint | 58 | 318372 | 258214 | 2744 | 15039 | 15 | 0 | 15.7% |
| information_loss | 53 | 301216 | 244633 | 4880 | 11260 | 14 | 0 | 14.8% |
| goal_hijack | 55 | 251415 | 190975 | 3196 | 10336 | 9 | 0 | 12.4% |
| silent_pass | 61 | 246058 | 225749 | 2590 | 8846 | 12 | 0 | 12.1% |
| deadlock | 38 | 197580 | 190110 | 4738 | 11816 | 11 | 0 | 9.7% |

#### Inject-Mix by anomaly

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| None | 180 | 635617 | 569869 | 3658 | 6190 | 0 | 0 | 18.6% |
| information_loss | 145 | 635328 | 495154 | 4608 | 7753 | 2 | 0 | 18.6% |
| goal_hijack | 139 | 492763 | 354112 | 4060 | 5982 | 0 | 0 | 14.4% |
| silent_pass | 78 | 288757 | 269687 | 3749 | 6375 | 0 | 0 | 8.5% |
| loop_failure | 76 | 284167 | 253472 | 4335 | 6425 | 0 | 0 | 8.3% |
| deadlock | 68 | 259802 | 229301 | 4111 | 6418 | 0 | 0 | 7.6% |
| verification_failure | 79 | 225844 | 207413 | 2779 | 5309 | 0 | 0 | 6.6% |
| over_constraint | 68 | 215083 | 168569 | 2001 | 7253 | 0 | 0 | 6.3% |
| pollution | 73 | 205066 | 174857 | 2619 | 5287 | 0 | 0 | 6.0% |
| tool_result_drop | 19 | 62335 | 53504 | 3330 | 5036 | 0 | 0 | 1.8% |
| retry_loop | 14 | 42377 | 35503 | 2534 | 5208 | 0 | 0 | 1.2% |
| action_spec_drift | 11 | 35348 | 33477 | 3135 | 5574 | 0 | 0 | 1.0% |
| false_success | 11 | 28143 | 20139 | 2362 | 4019 | 0 | 0 | 0.8% |

#### Inject-Mix by framework

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| v2_debate | 507 | 2127808 | 1756335 | 4583 | 6546 | 0 | 0 | 62.4% |
| v2_autogen | 284 | 940037 | 663899 | 2880 | 6024 | 2 | 0 | 27.6% |
| v2_crewai | 170 | 342785 | 313104 | 1767 | 3865 | 0 | 0 | 10.1% |

### 8. RogerYao/RAISER

- License `other`, deliberately: LICENSE_DATA.md says the package does not redistribute third-party trace content and grants no rights to it; source identifiers stay subject to each upstream repo's license/access terms (AEGIS MIT, CORRECT-Error Apache-2.0, MAST-Data and TraceElephant CC-BY-4.0, Who&When unspecified, TRAIL MIT + gated, evaluation only, never reshared outside an approved gated/private repo); maintainers may later add a license for the original annotations only.
- **No trajectory text.** All 7 data files hold IDs, hashes, binary role labels, confidences and outcomes; the longest string in any column is 92 chars (trace_id). 3,121 traces referenced (model_benchmark: 484 gold + 2,637 silver) from AEGIS, CORRECT-Error, MAST-Data, TraceElephant, TRAIL, Who&When - all already covered or gated. Labels: event-level (step) six binary roles (source, propagator, missed_verifier, contract_violation, symptom, repair_leverage); human_gold 1,600 candidate-role pairs. Trajectory tokens: 0.
- MAA overlap: 0 exact normalized question matches (0 questions); first-60-char probes: 0 / 554 hits over 4M normalized chars; planted control found = True.

### 9. AI45Research/ATBench

- ATBench: injected 497 (2.60M), clean 503 (0.59M). Medical-flagged trajectories: 12 (0.01M; {'heuristic': 12}).
- ATBench500: injected 250 (0.47M), clean 250 (0.24M). Medical-flagged trajectories: 27 (0.04M; {'heuristic': 27}).
- License Apache-2.0. **Single-agent** tool-use trajectories (roles user / agent / environment only). **Fully synthetic**: planner-generated blueprint, risk injection, simulated tool calls and tool responses; unsafe = risk injected by construction, safe = no risk. Labels: trajectory-level safe/unsafe + risk_source / failure_mode / real_world_harm categories (+ reason in ATBench); no step or agent labels. Root `test.json` is byte-identical to ATBench500/test.json (not counted twice).
- MAA overlap: 0 exact normalized question matches (1500 questions); first-60-char probes: 0 / 554 hits over 14M normalized chars; planted control found = True.
- Cross-dataset question overlap (1000 distinct questions): none.

#### ATBench by class

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| injected | 497 | 2601805 | 2581747 | 1137 | 3824 | 30 | 25 | 81.4% |
| clean | 503 | 593869 | 588900 | 1047 | 2103 | 0 | 0 | 18.6% |

#### ATBench500 by class

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| injected | 250 | 469345 | 465625 | 1656 | 3266 | 0 | 0 | 66.2% |
| clean | 250 | 239597 | 237755 | 877 | 1666 | 0 | 0 | 33.8% |

## Overlap with the MAA medical corpus

MAA: 559 unique normalized queries; 554 first-60-char probes (queries >= 40 chars). Searched text = every string value of every row (JSON-in-string parsed), normalized.

| dataset | questions checked | exact matches | probe hits | chars searched | planted control |
|---|---|---|---|---|---|
| CORRECT-Error | 2220 | 0 | 0 | 60M | True |
| AFTraj | 2276 | 0 | 0 | 7M | True |
| ARIA | 24468 | 0 | 0 | 183M | True |
| WhoWhenPro-mirror | 7173 | 0 | 0 | 76M | True |
| AgentErrorBench | 200 | 0 | 0 | 75M | True |
| MAScope | 1369 | 0 | 0 | 144M | True |
| ATBench | 1500 | 0 | 0 | 14M | True |
| RAISER | 0 | 0 | 0 | 4M | True |

## Downloads

Local sandbox, HF direct: 45 files OK (403 MB), all first attempt. AgentRx: 4 data files 403 (gated). Leoxx/whowhen_pro image/image_gui (18 GB) and video frames (3.6 GB) not downloaded.
