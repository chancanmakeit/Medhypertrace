# Public MAS failure-attribution datasets, round 55: AgentRx and TRAIL (gated) trajectory-text token stats

Tokenizer: Qwen/Qwen3-8B (add_special_tokens=False). Same protocol as stats.md / stats_r53.md: only natural-language trajectory content is counted (task question, message/step contents, final output, tool-call argument values, tool results); JSON keys, labels, annotations, injection metadata, repairs/counterfactuals excluded. Generated 2026-10-22 in the local sandbox after the user was granted access to both gated repos; raw data under /home/claude/public_mas/raw/ (not in the repo), scripts `scripts/*_r55.py` (helpers imported verbatim from `measure_r53.py` / `overlap_r53.py`).

## Summary

| Dataset | Trajectories | Steps (total / p50) | Total tokens | Global exact-dedup tokens | p50 / p90 / p99 / max per traj | >8K / >32K | Top benchmarks (token share) |
|---|---|---|---|---|---|---|---|
| microsoft/AgentRx (all; natural failures) | 87 | 4057 / 36 | 1.22M | 1.13M | 8454 / 35135 / 60331 / 73496 | 45 / 10 | magentic_one (GAIA/AssistantBench) 84%, tau_retail 16% |
| - AgentRx magentic (Magentic-One, MAS) | 58 | 2993 / 32 | 1.02M | 1.01M | 10258 / 36695 / 64770 / 73496 | 37 / 10 | magentic_one (GAIA/AssistantBench) 100% |
| - AgentRx tau_retail (single agent) | 29 | 1064 / 36 | 0.20M | 0.12M | 5869 / 8738 / 15258 / 16867 | 8 / 0 | tau_retail 100% |
| PatronusAI/TRAIL (all; natural runs) | 148 | 1268 / 5 | 3.40M | 3.25M | 13714 / 50037 / 105653 / 136085 | 90 / 39 | GAIA 75%, SWE-bench Lite 25% |
| - TRAIL GAIA (manager + search_agent) | 117 | 803 / 3 | 2.54M | 2.45M | 8228 / 48960 / 112499 / 136085 | 59 / 31 | GAIA 100% |
| - TRAIL SWE-bench Lite (single CodeAgent) | 31 | 465 / 14 | 0.87M | 0.80M | 21660 / 55310 / 79819 / 87611 | 31 / 8 | SWE-bench Lite 100% |

Total tokens = sum over trajectories, except TRAIL: every LLM span re-sends the full agent memory, and step/tool outputs are re-wrapped into later inputs, so TRAIL's per-trajectory figure is within-trace unique segments (raw as stored, incl. the repeated context: 16.71M; GAIA 9.56M, SWE-bench 7.14M). Steps: AgentRx = rows of `steps` (one substep each); TRAIL = `Step N` CHAIN spans of all agents (TRAIL also has 1974 LLM spans). Global exact-dedup = unique segment texts across the dataset (segment = message/substep for AgentRx; LLM input message / output / tool-call argument value / tool output / step output for TRAIL).

## Grand total of new, non-medical, non-duplicated tokens

union over AgentRx + TRAIL (all trajectory text), exact segment dedup between them, segments already present in ANY previously measured set removed (old 5 from r51: AEGIS, MAST-Data, Who&When, TraceElephant, Who&When-Pro tmpxv7 real files; all r53 sets: CORRECT-Error, AFTraj, ARIA, Who&When-Pro mirror text+video, AgentErrorBench, MAScope MAST-clean/LG-Ctrl/Inject-Mix, ATBench, ATBench500; segmentation identical to r53), trajectories flagged medical removed (keyword heuristic >=2 distinct medical terms in the task question); a segment shared by a natural/clean and an injected trajectory is credited to natural/clean.

Deduped against (segment hashes rebuilt from re-downloaded raw data with the r53 segmentation code, 551,102 distinct segments): OLD:Who&When, OLD:TraceElephant, OLD:MAST, OLD:AEGIS, OLD:Who&When-Pro(tmpxv7), CORRECT-Error, AFTraj, ARIA, WhoWhenPro-mirror (text), WhoWhenPro-mirror (video), AgentErrorBench, MAScope/MAST-clean, MAScope/LG-Ctrl, MAScope/Inject-Mix, ATBench/ATBench, ATBench/ATBench500.

| scope | (a) natural / clean | (b) injected | total | removed as already in prior sets |
|---|---|---|---|---|
| AgentRx + TRAIL, all | 3.37M | 0.00M | 3.37M | 1.01M |
| MAS only (AgentRx magentic + TRAIL GAIA) | 2.45M | 0.00M | 2.45M | 1.01M |
| MAS only, strict (TRAIL GAIA restricted to the 47 traces where search_agent actually ran) | 1.93M | 0.00M | 1.93M | 1.01M |

Per-dataset contribution (after cross-set dedup, in order of crediting):

| dataset | natural/clean | injected | removed as prior dup | medical trajectories removed (n / tokens) |
|---|---|---|---|---|
| AgentRx/magentic | 0.00M | 0.00M | 1.01M | 0 / 0.00M |
| AgentRx/tau_retail | 0.12M | 0.00M | 0.00M | 0 / 0.00M |
| TRAIL/gaia | 2.45M | 0.00M | 0.00M | 0 / 0.00M |
| TRAIL/swe_bench | 0.80M | 0.00M | 0.00M | 0 / 0.00M |

Removed-as-duplicate tokens by first matching prior set (all scope): OLD:Who&When 1,010,507, WhoWhenPro-mirror (text) 71, ARIA 42, ATBench/ATBench500 21, OLD:MAST 19, AFTraj 11, ATBench/ATBench 9.

Both datasets contain **no injected trajectories**, so column (b) is 0. Combined with round 53 (77.88M all / 70.46M MAS-only new tokens over the old 5), the r55 sets add 3.37M (all) / 2.45M (MAS only) on top; the r55 dedup was run against the r53 sets as well, so the figures are additive.

## Per-dataset notes

### 1. microsoft/AgentRx

- License CC-BY-4.0 (card and README); gated=auto. Downloaded with the user's read token: 5 files, 5.2 MB, no 403. Paper: Barke et al. 2026, arXiv 2602.02475.
- Config `trajectories`: magentic_dataset.jsonl (58 trajectories) and tau_retail_dataset.jsonl (29); config `default` = label files magentic_one.jsonl (44 labelled trajectories) and tau_retail.jsonl (29). 334 annotated failures. Labels: per-failure step_number + failure_category + failed_agent + free-text reasons, plus a designated root-cause failure (agent + step + category). **Only 44 of the 58 magentic trajectories have labels**; all 29 tau trajectories do.
- **Natural failures** (all trajectories are failed runs; no injection, no clean subset).
- **The magentic split is Who&When Hand-Crafted re-packaged**: 58 trajectories vs 58 W&W Hand-Crafted rows; 2993 / 2993 substep texts occur verbatim among W&W Hand-Crafted message contents, 58 / 58 trajectories fully contained; 53 instructions match a W&W Hand-Crafted question exactly. Consequently it contributes 0 new tokens (its 1.01M dedup tokens are all already in Who&When). Its new value is only the re-annotation (multiple failures per trace with categories, root cause) on top of W&W's single mistake_agent/mistake_step.
- tau_retail: **single agent** (role assistant with tool calls) talking to an LLM-simulated user (role user) under a retail policy (role system, identical in all 29 traces, so global dedup removes 28 copies); assistant tool calls are JSON lists, only argument values are counted; tool results are JSON product/order records. Multi-agent only in the sense of agent + user simulator.
- Agents seen (trajectories containing the role): magentic {'Assistant': 21, 'Orchestrator': 58, 'WebSurfer': 57, 'human': 58, 'ComputerTerminal': 3, 'FileSurfer': 10}; tau_retail {'assistant': 29, 'system': 29, 'tool': 29, 'user': 29}.
- Medical-flagged trajectories: 0 (0.00M).
- MAA overlap: 0 exact normalized question matches (87 questions); first-60-char probes: 0 / 554 hits over 4M normalized chars; planted control found = True.
- Cross-dataset question overlap (58 distinct questions): OLD:Who&When exact 55 / first-60 57, OLD:TraceElephant exact 43 / first-60 44, ARIA exact 26 / first-60 29, AFTraj exact 26 / first-60 28, TRAIL/gaia exact 23 / first-60 26, WhoWhenPro-mirror (text) exact 0 / first-60 7, AgentErrorBench exact 5 / first-60 6. (AgentRx/tau_retail: none.)

#### AgentRx by split

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| magentic | 58 | 1024211 | 1010507 | 10258 | 36695 | 37 | 10 | 84.0% |
| tau_retail | 29 | 195405 | 119848 | 5869 | 8738 | 8 | 0 | 16.0% |

#### AgentRx magentic by token part

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| turn | - | 1024211 | - | - | - | - | - | 100.0% |

#### AgentRx tau_retail by token part

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| task | - | 3632 | - | - | - | - | - | 1.9% |
| system | - | 34916 | - | - | - | - | - | 17.9% |
| turn | - | 29544 | - | - | - | - | - | 15.1% |
| tool_result | - | 122335 | - | - | - | - | - | 62.6% |
| toolcall_arg | - | 4978 | - | - | - | - | - | 2.5% |

### 2. PatronusAI/TRAIL

- License MIT (card); gated=auto with extra terms: do not reshare outside a gated or private HF repository. **The card's 'Out-of-Scope Use' says it must not be used for training systems intended to automate human evaluation; evaluation and benchmarking only.** This restricts TRAIL to evaluation in MedHyperTrace. Downloaded 299 files, 241.1 MB, no 403.
- Files: data/gaia-*.parquet (117 rows) + data/swe_bench-*.parquet (31 rows), columns `trace` (OpenTelemetry/OpenInference span tree as JSON string) and `labels`; the per-trace JSON files under GAIA/ and SWE Bench/ are byte-for-byte the same traces (all 148 parsed objects identical), processed_annotations_* = labels. One labels string has a trailing comma (parsed after removing it). The card says 118 GAIA / 30 SWE-bench traces; the files hold 117 / 31.
- Labels: 841 span-level errors (span id + category + evidence + description + impact {'HIGH': 304, 'MEDIUM': 363, 'LOW': 174}) in 144 of 148 traces, plus trace-level scores (reliability, security, instruction adherence, plan optimality). No responsible-agent field: the agent is only implied by the span. Top categories: Formatting Errors 196, Instruction Non-compliance 153, Goal Deviation 64, Resource Abuse 57, Tool-related 53, Language-only 50, Task Orchestration 46, Tool Selection Errors 44. The 4 traces without any annotated error are classed `no_annotated_error` (credited to natural/clean).
- **Natural runs** (no injection; for SWE-bench the card says 'added instructional constraints to organically introduce errors', i.e. prompted, not injected into the trace). GAIA: HF OpenDeepResearch (smolagents CodeAgent manager with a managed ToolCallingAgent `search_agent`), o3-mini. SWE-bench Lite: single smolagents CodeAgent, claude-3-7-sonnet.
- **Single- vs multi-agent**: SWE-bench traces are single-agent. GAIA traces are configured as manager + search_agent, but the search_agent actually ran in only 47 of 117 traces; the others are effectively single-agent. Hence the 'strict' MAS-only row above.
- Extraction: every LLM input message (system / user / assistant / tool-response; tool-call messages reduced to their argument values) + LLM output content and tool-call argument values + TOOL span argument values and outputs + CHAIN step outputs + AGENT task and output + exception messages. Output-side segments whose text already occurs inside an input message of the same trace are dropped (4,047 dropped, 554 kept), then within-trace unique. Excluded: span metadata, tool JSON schemas/descriptions, invocation parameters, OTel `logs` (function arguments/outputs of main/get_examples_to_answer, which include the GAIA gold answer and annotator metadata), stack traces, labels and scores. The system prompts (CodeAgent instructions, ~1.6M GAIA + 0.9M SWE-bench tokens raw) are part of the trajectory and counted. SWE-bench has a single distinct system prompt (431 occurrences), which the within-trace and global dedup collapse to one copy; GAIA has 293 distinct system messages over 1,154 occurrences (many embed the task or the agent memory, e.g. the final 'Earlier you were asked ...' call), so dedup removes only part of them (GAIA global dedup 2.54M -> 2.45M). processed_annotations_* files equal the `labels` column for 148/148 traces.
- Cross-check: a simpler rule (unique LLM input/output message strings per trace, tool-call messages kept as raw text) gives 3.64M vs 3.40M here.
- Unique questions: GAIA 116 for 117 traces; SWE-bench 22 issues for 31 traces (1 trace has no AGENT span; its task is still counted via the LLM input messages). SWE-bench repos: sqlfluff 13, astroid 5, pydicom 5, pvlib 4, marshmallow 2, pyvista 1.
- Medical-flagged trajectories: 0 (0.00M).
- MAA overlap: 0 exact normalized question matches (147 questions); first-60-char probes: 0 / 554 hits over 139M normalized chars (full raw trace + labels); planted control found = True.
- Cross-dataset question overlap (116 distinct questions): AFTraj exact 104 / first-60 112, ARIA exact 105 / first-60 112, OLD:TraceElephant exact 77 / first-60 82, OLD:Who&When exact 75 / first-60 79, OLD:AEGIS exact 45 / first-60 48, WhoWhenPro-mirror (text) exact 0 / first-60 38, AgentRx/magentic exact 23 / first-60 26. Same GAIA questions as the prior sets, but different runs (OpenDeepResearch / o3-mini): only 143 of its dedup tokens are exact segments of a prior set. TRAIL/swe_bench: no question overlap.

#### TRAIL by split

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| gaia | 117 | 2537690 | 2452029 | 8228 | 48960 | 59 | 31 | 74.5% |
| swe_bench | 31 | 866382 | 798741 | 21660 | 55310 | 31 | 8 | 25.5% |

#### TRAIL by class

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| natural_fail | 144 | 3358011 | 3208373 | 13714 | 51003 | 87 | 39 | 98.6% |
| no_annotated_error | 4 | 46061 | 46061 | 11771 | 15432 | 3 | 0 | 1.4% |

#### TRAIL GAIA by token part (raw, before within-trace dedup)

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| input_message | - | 3497319 | - | - | - | - | - | 36.6% |
| system | - | 1599438 | - | - | - | - | - | 16.7% |
| input_toolcall | - | 114386 | - | - | - | - | - | 1.2% |
| input_tool_result | - | 4109829 | - | - | - | - | - | 43.0% |
| output | - | 36579 | - | - | - | - | - | 0.4% |
| tool_result | - | 203321 | - | - | - | - | - | 2.1% |
| agent_output | - | 730 | - | - | - | - | - | 0.0% |
| output_toolcall | - | 730 | - | - | - | - | - | 0.0% |
| tool_arg | - | 40 | - | - | - | - | - | 0.0% |

#### TRAIL SWE-bench by token part (raw, before within-trace dedup)

| group | n | tokens_total | tokens_global_exact_dedup | p50 | p90 | n_gt_8k | n_gt_32k | share |
|---|---|---|---|---|---|---|---|---|
| system | - | 872344 | - | - | - | - | - | 12.2% |
| input_message | - | 1810630 | - | - | - | - | - | 25.3% |
| input_toolcall | - | 871515 | - | - | - | - | - | 12.2% |
| input_tool_result | - | 3534656 | - | - | - | - | - | 49.5% |
| agent_output | - | 4489 | - | - | - | - | - | 0.1% |
| step_output | - | 15816 | - | - | - | - | - | 0.2% |
| output | - | 27289 | - | - | - | - | - | 0.4% |
| tool_arg | - | 4489 | - | - | - | - | - | 0.1% |
| exception_msg | - | 3744 | - | - | - | - | - | 0.1% |

## Overlap with the MAA medical corpus

MAA: 559 unique normalized queries; 554 first-60-char probes (queries >= 40 chars). MAA rebuilt from the public repo GuihaiChen1998/nature-sub-record (anonymous clone, GIT_LFS_SKIP_SMUDGE=1; 'MedAgentAudit-datasets_and_logs-9.2 - 1.zip.00{1,2,3}' cat-merged, unzipped twice, converted with data_tools.maa_to_mas_traj: 14,370 rows, same as r51/r53). Searched text = every string value of every row (JSON-in-string parsed), normalized.

| dataset | questions checked | exact matches | probe hits | chars searched | planted control |
|---|---|---|---|---|---|
| AgentRx | 87 | 0 | 0 | 4M | True |
| TRAIL | 147 | 0 | 0 | 139M | True |

## Downloads

Local sandbox, HF direct, read token from file (never printed or stored): 304 files OK (246.3 MB), 0 failed. microsoft/AgentRx {'files': 5, 'mb': 5.2}, PatronusAI/TRAIL {'files': 299, 'mb': 241.1}. Prior sets re-downloaded unauthenticated with download.py (old 5, incl. the 3.5 GB tmpxv7 tarball, extracted with extract_wwp.py) and download_r53.py (r53 sets) because the sandbox had been reset.
