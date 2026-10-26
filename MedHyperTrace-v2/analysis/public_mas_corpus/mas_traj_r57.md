# Public MAS datasets -> mas-traj/1: conversion and validation (round 57)

Converters: `MedHyperTrace-v2/data_tools/public_to_mas_traj/` (conventions and per-framework source rules in its README.md). Data (not in the repo): `/home/claude/public_mas/mas_traj/<dataset>.jsonl.gz`. Raw numbers: `mas_traj_r57.json`; two example records per dataset (strings cut at 300 chars): `samples_r57/`. Generated 2026-10-26.

Validation per dataset: (a) medical-aegis `export_schema_v1.check()` imported from their file, unchanged; (b) their `scripts/sources_provenance_analysis.py` run unchanged on a decompressed copy; (c) text-match statistics where per-step inputs exist; (d) `python -m data_tools.maa_exclusion check docs/interfaces/maa_exclusion_v1.json` (task.query / task.images); (e) counts and token sums (o200k = output_tokens_est tokenizer; Qwen3-8B = tokenizer of stats*.md); (f) each converter re-run, sha256 compared.

## Summary

| dataset | records | check() pass | dup run_ids | frameworks (family) | llm / tool steps | MAA exact / probe | deterministic |
|---|---|---|---|---|---|---|---|
| who_and_when | 184 | 184 | 0 | captainagent 126 (groupchat), magentic_one 58 (groupchat) | 3721 / 313 | 0 / 0 | True |
| traceelephant | 220 | 220 | 0 | captainagent 85 (groupchat), magentic_one 91 (groupchat), swe_agent 44 (swe_agent) | 5960 / 1081 | 0 / 0 | True |
| mast_data | 1642 | 1642 | 0 | ag2_groupchat 168 (groupchat), ag2_mathchat 429 (ag2_mathchat), appworld_mas 30 (appworld_mas), chatdev 332 (chatdev), hyperagent 28 (hyperagent), magentic_one 195 (groupchat), metagpt 430 (metagpt), openmanus 30 (openmanus) | 25506 / 3327 | 0 / 0 | True |
| aria | 22237 | 22237 | 0 | ag2_student_verifier 2558 (ag2_student_verifier), magentic_one 2369 (groupchat), metagpt 3809 (metagpt), openmanus 13501 (openmanus) | 68970 / 39077 | 0 / 0 | True |
| aftraj | 1548 | 1548 | 0 | aftraj_expert_team 137 (groupchat), agents_handoff 821 (agents_handoff), single_tool_agent 62 (single_tool_agent), smolagents 528 (smolagents) | 12673 / 4950 | 0 / 0 | True |
| mascope | 260 | 260 | 0 | langgraph_centralized 23 (langgraph_centralized), langgraph_decentralized 9 (debate), langgraph_layered 23 (langgraph_layered), langgraph_shared_pool 25 (langgraph_shared_pool), mascope_autogen 55 (groupchat), mascope_crewai 31 (crewai), mascope_debate 94 (debate) | 2391 / 0 | 0 / 0 | True |
| agentrx_tau | 29 | 29 | 0 | tau_bench_agent 29 (tau_bench_agent) | 751 / 284 | 0 / 0 | True |

Kept / skipped: Who&When all 184; TraceElephant all 220; MAST-Data all 1642 (0 parse failures); ARIA 22,237 of 24,468 (2,231 core-medical MMLU episodes removed, identical to r53's count; 1,402 OpenManus roll-up events dropped as duplicates); AFTraj 1,548 (1,162 safe + 386 natural failures; 728 injected skipped); MAScope 260 clean (80 LG-Ctrl + 180 Inject-Mix; 1,109 injected skipped; MAST-clean skipped as a subset of MAST-Data); AgentRx tau_retail 29 (AgentRx magentic not re-converted: attached to 44 Who&When records as labels.external.agentrx).

## (e) Sanity: counts and tokens vs earlier stats

| dataset | records (ref) | Qwen3-8B tokens of query + step outputs | reference tokens | o200k llm outputs | o200k tool outputs | why they differ |
|---|---|---|---|---|---|---|
| who_and_when | 184 (184) | 1,420,681 | 1,431,026 | 1,174,468 | 132,952 | all 184; stats count task + every history message |
| traceelephant | 220 (220) | 1,471,108 | 7,301,387 | 563,231 | 781,544 | stats = unique message texts within a trace INCLUDING input contexts (page text, tool observations: 55.14M raw input_context); ours = outputs only (inputs are kept in input_messages) |
| mast_data | 1642 (1642) | 10,074,807 | 45,810,384 | 9,350,827 | 354,834 | stats = every blank-line paragraph of the raw log incl. config tables, pip/docker output, ChatDev phase prompts and repeated conclusions (paragraph dedup 22.28M); ours = agent messages + tool outputs only (ChatDev: utterance blocks are 14.5% of a log's characters) |
| aria | 22237 (22237) | 42,125,404 | 42,740,319 | 27,325,533 | 10,206,292 | reference = r53 ARIA minus its 2,231 core-medical MMLU episodes (same removal rule); r53 also counted tool-call argument values (0.13M) separately |
| aftraj | 1548 (1548) | 998,584 | 1,457,714 | 355,030 | 478,764 | reference = r53 clean + natural_fail classes; r53 counted tool-call argument values (0.27M here) and thoughts that are repeated inside the content twice (0.16M) |
| mascope | 260 (260) | 999,244 | 1,006,255 | 961,825 | 0 | reference = r53 clean classes of LG-Ctrl + Inject-Mix (paragraphs); we drop the [system] session line |
| agentrx_tau | 29 (29) | 155,511 | 195,405 | 27,188 | 100,447 | the system policy moved to task.observations (34,916 Qwen tokens) and tool-call arguments (4,978) are not in our sum; adding them gives exactly the r55 figure |

## (b) Read set determined by slot (partner script, round-41 definition)

`slot_determined` = share of llm steps whose read set (sources keyed as (agent, phase, round, k-th occurrence)) equals the most common read set of their slot (framework, phase, round, agent); `mode_share` = share of the most common (phase, round offset, agent) pattern per (framework, phase). Weighted over phases per framework (full per-phase table in the JSON):

| dataset | framework | llm steps | slot_determined (weighted) | lowest phases |
|---|---|---|---|---|
| who_and_when | captainagent | 796 | 0.39 | expert_turn 0.28, task_assignment 1.00 |
| who_and_when | magentic_one | 2925 | 0.10 | replan 0.04, instruction 0.08, progress_ledger 0.08 |
| traceelephant | captainagent | 1746 | 0.17 | chat_summary 0.04, speaker_selection 0.10, expert_turn 0.11 |
| traceelephant | magentic_one | 2663 | 0.17 | replan 0.01, update_facts 0.01, final_answer 0.03 |
| traceelephant | swe_agent | 1551 | 0.03 | agent_step 0.03 |
| mast_data | ag2_groupchat | 585 | 0.47 | agent_turn 0.47 |
| mast_data | ag2_mathchat | 1012 | 0.42 | assistant_turn 0.42 |
| mast_data | appworld_mas | 1028 | 0.05 | agent_code 0.05 |
| mast_data | chatdev | 12531 | 0.18 | LanguageChoose 0.10, DemandAnalysis 0.16, CodeReviewComment 0.19 |
| mast_data | hyperagent | 2800 | 0.05 | inner_step 0.03, planner 0.05, report_to_planner 0.10 |
| mast_data | magentic_one | 4522 | 0.13 | final_answer 0.06, instruction 0.09, agent_response 0.10 |
| mast_data | metagpt | 2144 | 0.60 | SimpleReviewer 0.50, SimpleTester 0.50, SimpleCoder 1.00 |
| mast_data | openmanus | 884 | 0.06 | think 0.03, plan 1.00 |
| aria | ag2_student_verifier | 7384 | 0.59 | verifier_turn 0.52, student_turn 0.66 |
| aria | magentic_one | 25207 | 0.40 | final_answer 0.22, instruction 0.35, agent_response 0.36 |
| aria | metagpt | 15236 | 1.00 | architect 1.00, engineer 1.00, product_manager 1.00 |
| aria | openmanus | 21143 | 0.64 | think 0.64 |
| aftraj | aftraj_expert_team | 1199 | 0.24 | verification_expert_turn 0.05, statistics_expert_turn 0.24, manager_turn 0.31 |
| aftraj | agents_handoff | 8322 | 0.16 | verifier_turn 0.05, mathsolver_turn 0.13, codewriter_turn 0.25 |
| aftraj | single_tool_agent | 771 | 0.08 | tasksolver_turn 0.08 |
| aftraj | smolagents | 2381 | 0.36 | manager_turn 0.27, search_agent_turn 0.72 |
| mascope | langgraph_centralized | 133 | 0.63 | hub 0.33, agent_turn 0.95 |
| mascope | langgraph_decentralized | 108 | 1.00 | agent_turn 1.00 |
| mascope | langgraph_layered | 115 | 1.00 | agent_turn 1.00 |
| mascope | langgraph_shared_pool | 300 | 0.33 | agent_turn 0.33 |
| mascope | mascope_autogen | 743 | 0.15 | manager 0.14, agent_turn 0.17 |
| mascope | mascope_crewai | 146 | 0.66 | agent_turn 0.57, leader_plan 1.00 |
| mascope | mascope_debate | 846 | 1.00 | agent_turn 1.00 |
| agentrx_tau | tau_bench_agent | 751 | 0.08 | agent_turn 0.06, user_turn 0.12 |

Reading: for protocol-inferred data the read set is a deterministic function of the step sequence, so a low value says that the SEQUENCE varies within a slot (e.g. "every earlier step of the thread" gives a different set at every position), not that inference is uncertain. Rules of the form "fixed predecessor roles" give 1.00 (MetaGPT ARIA, debate rounds, layered pipeline, plans / facts calls). Cumulative-history rules (group chats, agent memory, Magentic-One threads, ChatDev phases) score low by construction. TraceElephant is the only text_match set: its values measure real variation of the recorded inputs. The partner's script needed no adaptation (return code 0 on all files).

## (c) Text-match statistics (TraceElephant, the only dataset with per-step inputs)

| framework | llm steps with inputs | share with zero inferred sources | sources | share text_match |
|---|---|---|---|---|
| captainagent | 1746 | 0.062 | 13843 | 0.947 |
| magentic_one | 2663 | 0.043 | 12941 | 1.000 |
| swe_agent | 1551 | 0.028 | 52388 | 0.979 |

Transitive matches dropped (a later listed source quotes the candidate): 1319. Non-text_match sources there are protocol: tool step <- its call (SWE-agent, 1,081) and speaker-selection control (CaptainAgent, 733). Zero-source steps are mostly first calls (facts / role matching / first SWE step, which read only the task).

## (d) MAA exclusion

- who_and_when: /tmp/claude-0/-home-claude/9b735e89-5a87-5eae-b05f-ab9afe1203be/scratchpad/val/who_and_when.jsonl: 142 distinct queries; exact matches 0; probe candidates 0
- traceelephant: /tmp/claude-0/-home-claude/9b735e89-5a87-5eae-b05f-ab9afe1203be/scratchpad/val/traceelephant.jsonl: 174 distinct queries; exact matches 0; probe candidates 0
- mast_data: /tmp/claude-0/-home-claude/9b735e89-5a87-5eae-b05f-ab9afe1203be/scratchpad/val/mast_data.jsonl: 953 distinct queries; exact matches 0; probe candidates 0
- aria: /tmp/claude-0/-home-claude/9b735e89-5a87-5eae-b05f-ab9afe1203be/scratchpad/val/aria.jsonl: 15703 distinct queries; exact matches 0; probe candidates 0
- aftraj: /tmp/claude-0/-home-claude/9b735e89-5a87-5eae-b05f-ab9afe1203be/scratchpad/val/aftraj.jsonl: 1381 distinct queries; exact matches 0; probe candidates 0
- mascope: /tmp/claude-0/-home-claude/9b735e89-5a87-5eae-b05f-ab9afe1203be/scratchpad/val/mascope.jsonl: 165 distinct queries; exact matches 0; probe candidates 0
- agentrx_tau: /tmp/claude-0/-home-claude/9b735e89-5a87-5eae-b05f-ab9afe1203be/scratchpad/val/agentrx_tau.jsonl: 29 distinct queries; exact matches 0; probe candidates 0

## Label mapping checks

- Who&When: mistake_step mapped to a step for 181/184 (3 Hand-Crafted indices point past the history). At the mapped step the named agent equals mistake_agent in 175, differs in 6 (dataset-internal: e.g. index on `Orchestrator (-> WebSurfer)` for a WebSurfer mistake, or on a Computer_terminal output for an expert).
- TraceElephant: mapped 218/220 (2 AssistantBench traces have mistake_step `none` / `Step 36`); TraceElephant's own step agent_name equals mistake_agent in all 218. Note our agent_id differs from that name for Magentic-One ledger calls (we attribute the call to the Orchestrator).
- AFTraj: 386/386 mapped, agent equals mistake_agent in all.
- ARIA: first-bad events without a step: 254 point at the task message (221 Magentic-One, 33 MetaGPT), 140 at OpenManus roll-up events that we drop as duplicates (see open questions).

## Open questions / convention problems

1. **Family of Magentic-One** (W&W, TraceElephant, MAST, ARIA; ~2,900 runs): mapped to `groupchat` by the in-doubt rule (MagenticOneGroupChat = AutoGen group chat with LLM speaker selection). If the partner considers the ledger architecture distinct, change one line in the registry (own_family `magentic_one`). Same question, smaller, for AFTraj expert team and `langgraph_decentralized` -> debate.
2. **Slot-determinacy is not informative for cumulative-history protocols** (see (b)); we suggest also reporting it with sources keyed by relative position ("all earlier steps of the thread") before comparing frameworks.
3. **Steps that are not LLM calls** have no kind in the schema besides llm/tool: framework template messages (AG2 group-chat introduction, ARIA's "Review and finalize" request, OpenManus run summaries, MAST AppWorld delivered messages) are exported as `tool` steps; Who&When Hand-Crafted `Orchestrator (thought)` lines such as "Next speaker WebSurfer" and the termination line are exported as llm steps although they are derived from the ledger call. A third kind (e.g. `system`) would express this better.
4. **Inputs that are not steps**: Magentic-One page text (TraceElephant) and ChatDev phase prompts enter inputs but are neither steps nor task observations; `task.observations` is meant for shared observations. The partner might want a `kind: "environment"` step.
5. **ARIA localization pointing at the task message or at a roll-up** (394 episodes): no step to point at. Options: keep roll-ups as tool steps (adds duplicated text to the corpus), or map to the last step summarised.
6. **MAST-Data MMLU (AG2 group chat, 168 runs) contains medical questions** (it has no subject field); the MAA exclusion finds 0 overlaps, but unlike ARIA no medical filter was applied (not requested). Decide whether to filter with the r53 keyword heuristic.
7. TraceElephant `is_correct` is set False for all traces (every trace carries a mistake annotation; SWE tests fail), not recomputed from the answers; Who&When likewise. MAST-Data `is_correct` is null except AG2 GSM-Plus (`other_data.correct`).

## Left undone

- Nothing of the requested list; all 7 datasets converted and validated. Not done (out of scope): injected datasets, TRAIL, AgentErrorBench, ATBench, RAISER; validation of text-match inference against the partner's recorded sources (planned with their data).

## Round 61 revision (after medical-aegis spot check, issue round 43)

The partner re-ran our converters, spot-checked 140 records against the raw data (every non-empty output found verbatim;
no annotation text leaked into steps or task), and reported items A–E. Changes (all converters re-run; old outputs kept
in `/home/claude/public_mas/mas_traj_r57_backup/`):

- **`kind: "environment"` + `env_type`** (partner schema note `docs/mas_traj_schema_notes.md` in medical-aegis; their
  `check()` validates it): template messages formerly forced into `tool` are now `environment/template`
  (AG2 group-chat introduction, ARIA review request and OpenManus run summaries, AppWorld message forwarding);
  ARIA workspace artifacts are `environment/tool_output`; the tau-bench simulated user is `environment/user_simulator`.
  Environment steps are never attribution candidates; a dataset label that points at one is kept and flagged
  (`labels.external.label_on_environment`).
- **A, TraceElephant tool calls:** when `message.tool_calls` is empty the calls are taken from `tool_logs`
  (359 SWE-agent and 51 CaptainAgent llm steps); labelled SWE-agent steps that were empty: 18 -> 1; tool steps 1,081 -> 1,447.
- **B, agent naming in labels:** Who&When and TraceElephant labels now carry `mistake_agent_id` (the converted `agent_id`
  of the labelled step) next to the dataset's `mistake_agent`; Who&When's 3 out-of-range `mistake_step`s are flagged
  `mistake_step_unmapped`.
- **C, AgentRx tau:** the retail policy was not dropped: it is `task.observations[obs:policy]` and every agent step cites
  it as a source (kept there, as the spec intends for observations). Simulated-user turns are now
  `environment/user_simulator` (248 steps); **11 of the 29 runs have at least one AgentRx failure label on a
  simulated-user step** (flagged).
- **D, ARIA first-bad events without a step:** `first_bad_unmapped_event_ids` (394 runs) and `first_bad_on_task`
  (254 runs: the first bad event is the task message / start event); exclude these from step-level evaluation.
- **E, ChatDev Reflection forwards:** a `Reflection` step whose output equals the previous step's (whitespace-normalised)
  is `environment/template` (99 steps, the partner's count).
- **MAST AG2 group chat (MMLU):** the r53 medical keyword rule (>= 2 distinct medical terms in the question) now applies;
  12 runs dropped (1,642 -> 1,630).

| dataset | records | check() problems | kinds | environment types | label_on_environment | first_bad_on_task | MAA exact / probe |
|---|---|---|---|---|---|---|---|
| aftraj | 1548 | 0 | {'llm': 12673, 'tool': 4950} | - | 0 | 0 | 0 / 0 |
| agentrx_tau | 29 | 0 | {'environment': 248, 'llm': 503, 'tool': 284} | {'user_simulator': 248} | 11 | 0 | 0 / 0 |
| aria | 22237 | 0 | {'llm': 68970, 'tool': 24018, 'environment': 15059} | {'template': 14657, 'tool_output': 402} | 52 | 254 | 0 / 0 |
| mascope | 260 | 0 | {'llm': 2391} | - | 0 | 0 | 0 / 0 |
| mast_data | 1630 | 0 | {'llm': 25359, 'environment': 1482, 'tool': 1921} | {'template': 1482} | 0 | 0 | 0 / 0 |
| traceelephant | 220 | 0 | {'llm': 5960, 'tool': 1447} | - | 0 | 0 | 0 / 0 |
| who_and_when | 184 | 0 | {'llm': 3721, 'tool': 313} | - | 0 | 0 | 0 / 0 |
