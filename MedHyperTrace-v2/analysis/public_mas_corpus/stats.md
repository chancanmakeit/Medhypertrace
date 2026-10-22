# Public MAS failure-attribution datasets: trajectory-text token stats

Tokenizer: Qwen/Qwen3-8B (add_special_tokens=False). Only natural-language trajectory content is counted (task question, message/step contents, final output, tool-call argument *values*); JSON keys, labels, annotations, injection metadata excluded. Generated 2026-10-22 in the local sandbox (/home/claude/public_mas).

## Summary

| Dataset | Trajectories | Steps (total / p50) | Total tokens | Global exact-dedup tokens | p50 / p90 / p99 / max per traj | >8K / >32K | Top benchmarks (token share) |
|---|---|---|---|---|---|---|---|
| AEGIS (all injected) | 9533 | 113438 / 10 | 57.33M | 49.12M | 5089 / 9945 / 27982 / 81024 | 1596 / 58 | SciBench 23%, MATH 20%, HumanEval 15%, MMLU 13% |
| MAST-Data | 1642 | not measured | 45.81M | 22.28M | 2389 / 109204 / 196847 / 512476 | 601 / 367 | ProgramDev-v2 66%, ProgramDev 20%, GAIA 8%, SWE-Bench-Lite 2% |
| Who&When | 184 | 4092 / 10 | 1.43M | 1.40M | 2838 / 23694 / 55720 / 73496 | 42 / 11 | GAIA 57%, AssistantBench 43% |
| TraceElephant | 220 | 5960 / 21 | 7.30M | 6.78M | 19842 / 78337 / 157040 / 173184 | 201 / 69 | GAIA 67%, AssistantBench 20%, SWE-bench 13% |
| Who&When-Pro (text, real files only) | 311 | 9641 / 31 | 0.46M | 0.22M | 1380 / 2221 / 2831 / 3168 | 0 / 0 | alfworld/alfagent 100% |
| PatronusAI/TRAIL | gated - not downloaded | not measured | not measured | not measured | not measured | not measured | needs user to accept HF terms |

Total tokens = sum over trajectories as stored, except TraceElephant, where per-step inputs repeat the cumulative context: there it is the unique message texts within each trace (raw as stored: 55.91M). Global exact-dedup = unique segment texts across the whole dataset (segment = turn/message; MAST = blank-line paragraph of the raw log).

## AEGIS (Fancylalala/AEGIS, parquet export)

- Clean (no injection) runs: **0**. Injected runs: **9533** (every row has num_injected_agents>=1, injected_agents non-empty, is_injection_successful=True). There is no clean subset to separate.
- Token parts: task 0.94M, normal turns 47.30M, turns flagged is_injected 6.01M, final_output 3.08M. Note: response_corruption injections also alter un-flagged downstream turns; only explicitly flagged turns can be separated.
- Unique task queries: 1397 across 9533 rows (heavy question reuse). Models per metadata: gpt-4o-mini 9,260, unknown-model 273 (magentic_one).

### AEGIS by split

| group | n | tokens_total | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|
| train | 7146 | 42612152 | 5071 | 9850 | 1187 | 40 | 74.3% |
| validation | 1787 | 10872509 | 5102 | 10289 | 304 | 13 | 19.0% |
| test | 600 | 3844375 | 5261 | 10684 | 105 | 5 | 6.7% |

### AEGIS by framework

| group | n | tokens_total | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|
| llm_debate | 2404 | 17399736 | 6689 | 11847 | 764 | 0 | 30.4% |
| macnet | 2359 | 11686379 | 4678 | 7039 | 86 | 0 | 20.4% |
| agentverse | 2449 | 9857018 | 3400 | 7725 | 202 | 0 | 17.2% |
| dylan | 1567 | 8845787 | 5290 | 9806 | 230 | 0 | 15.4% |
| smoagents | 481 | 6118264 | 6875 | 26464 | 201 | 36 | 10.7% |
| magentic_one | 273 | 3421852 | 4681 | 31511 | 113 | 22 | 6.0% |

### AEGIS by benchmark

| group | n | tokens_total | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|
| SciBench | 1905 | 13054304 | 6444 | 11507 | 566 | 0 | 22.8% |
| MATH | 2083 | 11403362 | 5104 | 9576 | 356 | 0 | 19.9% |
| HumanEval | 1532 | 8429519 | 5342 | 8456 | 187 | 0 | 14.7% |
| MMLU | 1481 | 7456862 | 4717 | 8167 | 147 | 0 | 13.0% |
| GSM8K | 1778 | 7444873 | 4134 | 5965 | 26 | 0 | 13.0% |
| smol+gaia | 481 | 6118264 | 6875 | 26464 | 201 | 36 | 10.7% |
| magentic+gaia | 273 | 3421852 | 4681 | 31511 | 113 | 22 | 6.0% |

### AEGIS by domain

| group | n | tokens_total | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|
| math | 3861 | 18848235 | 4506 | 8159 | 382 | 0 | 32.9% |
| science-reasoning | 1905 | 13054304 | 6444 | 11507 | 566 | 0 | 22.8% |
| web/agentic-QA | 754 | 9540116 | 6631 | 30354 | 314 | 58 | 16.6% |
| code | 1532 | 8429519 | 5342 | 8456 | 187 | 0 | 14.7% |
| knowledge-QA | 1481 | 7456862 | 4717 | 8167 | 147 | 0 | 13.0% |

## MAST-Data (mcemri/MAST-Data, parquet export)

- Each trace is a raw framework log string (timestamps, config paths, pip/docker output included). Steps are not uniformly parseable: **not measured**. Paragraph-level exact dedup cuts 45.81M to 22.28M (ChatDev logs repeat prompts heavily).
- ChatDev alone is 83% of tokens. Question extracted (for exact overlap) for 846/1642 traces; full-text containment check covers all.

### MAST by framework

| group | n | tokens_total | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|
| ChatDev | 330 | 37796637 | 108056 | 180429 | 330 | 330 | 82.5% |
| Magentic | 195 | 3841342 | 16419 | 32699 | 195 | 20 | 8.4% |
| MetaGPT | 430 | 1248252 | 2177 | 6351 | 1 | 0 | 2.7% |
| HyperAgent | 30 | 1135014 | 15912 | 118387 | 28 | 10 | 2.5% |
| AG2 | 597 | 815502 | 1126 | 1983 | 2 | 0 | 1.8% |
| OpenManus | 30 | 562094 | 14160 | 36687 | 29 | 4 | 1.2% |
| AppWorld | 30 | 411543 | 8946 | 32452 | 16 | 3 | 0.9% |

### MAST by benchmark

| group | n | tokens_total | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|
| ProgramDev-v2 | 400 | 30234106 | 50045 | 172148 | 200 | 200 | 66.0% |
| ProgramDev | 390 | 9372877 | 2498 | 67813 | 160 | 134 | 20.5% |
| GAIA | 195 | 3841342 | 16419 | 32699 | 195 | 20 | 8.4% |
| SWE-Bench-Lite | 30 | 1135014 | 15912 | 118387 | 28 | 10 | 2.5% |
| Test-C | 30 | 411543 | 8946 | 32452 | 16 | 3 | 0.9% |
| Olympiad | 206 | 326417 | 1249 | 2358 | 1 | 0 | 0.7% |
| GSM | 223 | 292768 | 1050 | 1892 | 1 | 0 | 0.6% |
| MMLU | 168 | 196317 | 1167 | 1557 | 0 | 0 | 0.4% |

### MAST by domain

| group | n | tokens_total | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|
| software-dev | 790 | 39606983 | 6607 | 153807 | 360 | 334 | 86.5% |
| web/agentic-QA | 195 | 3841342 | 16419 | 32699 | 195 | 20 | 8.4% |
| SWE | 30 | 1135014 | 15912 | 118387 | 28 | 10 | 2.5% |
| math | 429 | 619185 | 1117 | 2279 | 2 | 0 | 1.4% |
| app-agent (AppWorld) | 30 | 411543 | 8946 | 32452 | 16 | 3 | 0.9% |
| knowledge-QA | 168 | 196317 | 1167 | 1557 | 0 | 0 | 0.4% |

## Who&When (Kevin355/Who_and_When)

- Benchmark inferred from question_ID format (UUID = GAIA, 64-hex = AssistantBench). Hand-Crafted = Magentic-One logs; Algorithm-Generated = CaptainAgent.

### Who&When by config

| group | n | tokens_total | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|
| Hand-Crafted | 58 | 1024454 | 10258 | 36695 | 37 | 10 | 71.6% |
| Algorithm-Generated | 126 | 406572 | 2113 | 5626 | 5 | 1 | 28.4% |

### Who&When by benchmark

| group | n | tokens_total | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|
| GAIA | 128 | 818386 | 2380 | 14874 | 19 | 6 | 57.2% |
| AssistantBench | 56 | 612640 | 6272 | 27146 | 23 | 5 | 42.8% |

## TraceElephant (TraceElephant/TraceElephant, data.zip 596.6 MB)

- Archive: 2,827 entries = 2,070 PNG (578.7 MB, screenshots under magentic-runs-*/<run>/images/) + 440 JSON (252.2 MB) + 317 dirs. 220 traces, each = step_records.json + trace_metadata.json.
- What it is: a failure-attribution set with *full LLM-call records* per step (input messages, output, tool calls, token usage) and per-trace labels mistake_agent / mistake_step / mistake_reason (+ SWE-bench test status). Subsets: captain-agent on GAIA (73) / AssistantBench (12), Magentic-One on GAIA (74) / AssistantBench (17), SWE-agent on SWE-bench (44); model gpt-4o. 135 of its 176 GAIA/AssistantBench traces contain a Who&When question (first 80 normalized chars), so it is largely a full-context re-run of Who&When tasks (same question pool; do not count both as independent tasks).
- Images inside input messages: 6146 (not tokenized). Raw-as-stored tokens 55.91M vs within-trace unique 7.30M.

### TraceElephant by framework

| group | n | tokens_total | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|
| magentic | 91 | 4706696 | 46395 | 93192 | 78 | 54 | 64.5% |
| captain | 85 | 1620825 | 15282 | 28959 | 81 | 7 | 22.2% |
| swe-agent | 44 | 973866 | 17082 | 37361 | 42 | 8 | 13.3% |

### TraceElephant by benchmark

| group | n | tokens_total | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|
| GAIA | 147 | 4888957 | 19182 | 78281 | 130 | 46 | 67.0% |
| AssistantBench | 29 | 1438564 | 36890 | 87072 | 29 | 15 | 19.7% |
| SWE-bench | 44 | 973866 | 17082 | 37361 | 42 | 8 | 13.3% |

## Who&When-Pro (tmpxv7/who-when-pro, data_release.tar.gz 3.50 GB, sha256 verified)

- **The release is largely broken**: of 11072 trace JSON entries, 9845 are relative symlinks pointing outside the archive (../../../../mmagent/..., ../../../../PixelCraft/...) - dangling, no content. All 3,899 image-modality traces and 5,946 of 6,257 text traces are dangling. Real files: 311 text traces (alfworld/alfagent only) + 916 video traces (lvbench: dvd 168, eva 748) + 21,851 video frames (10,991 jpg / 655 MB, 10,860 png / 2.95 GB; counted while streaming, never extracted to disk). Repo history has no other data copy (earlier commit only has eval code).
- Dangling text traces by benchmark/framework: bigcodebench/macnet=170, bigcodebench/metagpt=25, dabench/smolagents=327, dacode/smolagents=306, databench/smolagents=818, dsqa/smolagents=830, gaia/magentic-one=302, gpqa/debate=74, gpqa/dylan=69, humaneval/macnet=18, kramabench/smolagents=82, livecodebench_pro/macnet=73, livecodebench_pro/metagpt=56, math/debate=144, math/mathchat=304, mmlu_pro/debate=56, mmlu_pro/mathchat=315, scibench/debate=171, scibench/dylan=83, scibench/mathchat=301, simpleqa_verified/magentic-one=509, tablebench/smolagents=913
- Dangling image traces: browsecomp_vl/smolagents=298, chartqapro/pixelcraft=679, charxiv/pixelcraft=1055, evochart/pixelcraft=668, mmmu_pro/debate=107, mmsearch/smolagents=831, mmsearch_plus/smolagents=261

### Text modality (311 real alfworld/alfagent traces, 135 distinct task+split keys)

| part | tokens |
|---|---|
| pre-injection prefix (turns with step < gt.step, incl. task prompt) | 273,336 |
| injected step (step == gt.step) | 23,117 |
| post-injection turns | 168,184 |
| total | 464,637 |
| **prefix deduplicated by (task, exact turn text)** | **140,288** |
| all turns deduplicated by (task, exact turn text) | 252,891 |

Video (counts requested; text tokens reported only as extra): 916 traces, text-in-JSON 4.02M (prefix 3,756,023 / injected 49,515 / post 215,050; prefix dedup 2,969,298). Image modality: 3,899 listed, 0 readable.

## Overlap with MAA medical corpus

MAA: 14370 rows, 559 unique normalized task.query (437 with >=12 words). Local copy /home/claude/data_maa_v2/maa_mas_traj.jsonl (same 14,370 lines as Linux #2 file).

| dataset | questions checked | exact matches | MAA queries contained in any segment | trajectories containing one |
|---|---|---|---|---|
| AEGIS | 9533 | 0 | 0 | 0 |
| MAST | 846 | 0 | 0 | 0 |
| Who&When | 184 | 0 | 0 | 0 |
| TraceElephant | 220 | 0 | 0 | 0 |
| Who&When-Pro | 1227 | 0 | 0 | 0 |

Cross-check: first 60 normalized chars of each of 554 MAA queries (>=40 chars) substring-searched in full normalized text of every dataset (incl. raw JSON): 0 hits in all 5; planted positive control found.

## Downloads

Local sandbox (HF direct): all files OK first attempt - parquets 0.3-150 MB/s, TraceElephant data.zip 596.6 MB in 7.2 s (83 MB/s), who-when-pro tar.gz 3.50 GB in 12.3 s (284 MB/s).

Linux #2 via proxy 127.0.0.1:23333 (speed sample only): W&W parquets 28 / 46 KB/s, AEGIS test 4.7 MB in 59 s (80 KB/s), AEGIS validation 13.2 MB in 176 s (75 KB/s). At ~75 KB/s: all parquets (~263 MB) ~1 h, TraceElephant zip ~2.2 h, who-when-pro tar.gz ~13 h (and ~85% of it is video frames). Recommendation: transfer extracted text (JSONL, tens of MB) from the sandbox instead.

TRAIL (PatronusAI/TRAIL): gated=auto, requires accepting terms on HF with the user's account; not attempted.
