# public_to_mas_traj: public MAS failure-attribution datasets -> mas-traj/1 (MHT round 57)

These converters turn the public, non-medical, non-injected multi-agent trajectory datasets into the
trajectory schema `mas-traj/1` of medical-aegis (`scripts/export_schema_v1.py`, spec
`docs/requests/2026-10-19_from_medhypertrace_HGFM_trajectory_spec_v1.md` incl. v1.1). The output is meant
as a mid-training corpus: text and structure in `task` / `steps` / `final`; the datasets' own annotations
live only in `labels` (for later evaluation / analysis).

## Run

```
cd MedHyperTrace-v2
python -m data_tools.public_to_mas_traj.<module> --raw /home/claude/public_mas/raw --out <file.jsonl.gz>
python -m data_tools.public_to_mas_traj.validate --datasets <names...> --tmp <scratch dir> \
    --out analysis/public_mas_corpus/mas_traj_r57.json
```

| dataset (output name) | module | raw input | kept |
|---|---|---|---|
| who_and_when | `whowhen` | Kevin355/Who_and_When (+ microsoft/AgentRx magentic labels) | all 184 |
| traceelephant | `traceelephant` | TraceElephant/TraceElephant data.zip | all 220 |
| mast_data | `mast` | mcemri/MAST-Data | all 1642 |
| aria | `aria` | Edlison/ARIA | 22,237 (2,231 core-medical MMLU removed) |
| aftraj | `aftraj` | ZBox008003/AFTraj | safe 1,162 + natural failures 386 (728 injected skipped) |
| mascope | `mascope` | mascope/mascope-bench | clean LG-Ctrl 80 + clean Inject-Mix 180 (MAST-clean skipped: subset of MAST-Data) |
| agentrx_tau | `agentrx_tau` | microsoft/AgentRx tau_retail | all 29 (single agent) |

Data files are written to `/home/claude/public_mas/mas_traj/` (not in the repo), each with a
`<name>.convert_report.json`. Converters are deterministic (gzip mtime 0, source order); `validate` re-runs
each converter and compares sha256. Not converted (out of scope): injected datasets (AEGIS public,
CORRECT, Who&When-Pro), TRAIL (licence: evaluation only), AgentErrorBench, ATBench, RAISER.

## Conventions (all in `common.py`; agreed with medical-aegis in their reply to our r57 comment)

* **Layout** exactly as `export_schema_v1.convert()`: record fields `schema_version, run_id, question_id,
  run_mode, run_index, seed, framework, framework_family, framework_description, model, task{dataset, query,
  images, observations}, steps, final{answer, response, source_step_ids}, labels, provenance`; step fields
  `step_id, order, kind, agent_id, agent_role, agent_label, phase, round, event_ids, input_messages, sources,
  output, structured, tool_calls, finish_reason, output_tokens_est`. `step_id = s<order>`. Tool steps
  (`kind "tool"`) have `input_messages null`, `output_tokens_est null` and the result in
  `tool_calls[].result` (as the partner's tool steps).
* **question_id** `<benchmark>/<native id>` when the dataset has one (GAIA task_id, AssistantBench id,
  SWE-bench instance_id, HumanEval index, AppWorld task id, MAScope task_id, tau-retail id), else
  `<benchmark>/q_<sha1(norm_stem(question))[:12]>` with `data_tools.maa_exclusion.norm_stem`. The benchmark
  prefix is normalised (`QID_BENCH`: GSM -> GSM-Plus, Olympiad -> OlympiadBench, SWE-Bench-Lite -> SWE-bench,
  ...) so the same task gets the same id in every dataset; `task.dataset` keeps the dataset's own name.
* **run_index** = index among runs of the same (framework, question_id, model) in source order; `seed null`.
  **run_id** = `<dataset>|<framework>|<model or unknown-model>|<question_id>|<run_mode>|r<run_index>`
  (partner format with the source dataset in front; uniqueness asserted).
* **run_mode** `"normal"` for every run here (no injections); `labels.is_correct` = the dataset's outcome
  (null when unknown); dataset annotations go to `labels.external = {dataset, taxonomy, ...}` with native
  step / event indices AND the mapped `step_id`s; `labels.injection` stays `[]`.
* **framework / framework_family** from `framework_registry_public.yaml`. A public framework with the same
  architecture as a partner medical family takes that family (`groupchat`, `debate`, ...), conservative when
  in doubt; `family_reason` gives the evidence, `own_family` the architecture name otherwise. Decisions:

  | framework | family | why |
  |---|---|---|
  | magentic_one | groupchat | AutoGen group chat with an LLM orchestrator choosing the next speaker over a broadcast thread (MagenticOneGroupChat); ledgers differ -> in doubt -> groupchat |
  | captainagent | groupchat | nested AG2 GroupChat; TraceElephant logs the manager's LLM speaker selection |
  | ag2_groupchat (MAST MMLU) | groupchat | AG2 GroupChat with chat_manager introduction, data-dependent speaker order |
  | aftraj_expert_team | groupchat | AutoGen agentchat team (ThoughtEvent, Computer_terminal, Manager + experts) |
  | mascope_autogen | groupchat | manager emits `next_speaker` JSON = LLM speaker selection |
  | mascope_debate | debate | 3 debaters x 3 rounds, each round reads the peers' previous round |
  | langgraph_decentralized | debate | peers revise after reading each other's latest proposals (in doubt -> debate) |
  | ag2_mathchat, ag2_student_verifier, chatdev, metagpt, hyperagent, openmanus, appworld_mas, smolagents, agents_handoff, langgraph_layered / _centralized / _shared_pool, mascope_crewai | own name | fixed two-agent chats, chat chains, SOP pipelines, planner+interns, handoffs, hierarchical crews: no medical family has these architectures |
  | swe_agent, single_tool_agent, tau_bench_agent, (openmanus) | own name | single agent (`multi_agent: false`), kept for completeness |

* **Missing fields**: `input_messages null` and `provenance.input_messages_clean null` when the dataset has
  no per-step input (all but TraceElephant, where it is `true`); `phase` = the framework's own stage name
  (prompt signature / log marker / role), `"unknown"` only where not derivable; `round` null except MAScope
  debate / decentralized (explicit rounds).
* **sources**: every item `{"step_id", "how", "inferred"}` with `how` in {verbatim, excerpt,
  structured_field, summary, control} (partner semantics: verbatim = whole output enters the input; excerpt
  = a part; structured_field = a parsed field; control = selected / routed this step, no text; summary =
  a summary of the source) and `inferred` in {text_match, protocol}; `provenance.sources_recorded = false`.
  `[]` = the step reads no earlier step (e.g. it reads only the task); task observations are referenced as
  `task:obs:<id>`. No `null` sources are produced.
* **output_tokens_est**: `tiktoken o200k_base` (the partner's exporter tokenizer), `provenance.output_tokenizer`.
* **Leak safety**: steps carry no label keys (partner `check()` LABEL_KEYS / INJECTION_MARKERS pass on every
  record); gold patches / answers / correctness fields that some raw logs embed (MAST AG2 GSM-Plus
  `other_data`, HyperAgent `patch`) are kept out of `task` and `steps`.

## Source inference

### text_match (datasets with per-step inputs: TraceElephant)
`common.infer_text_sources`: probes from the BODY of each earlier output (whitespace-normalised; outputs
< 25 chars give no probe; < 100 chars -> the whole text; else three 50-char windows at 20 / 50 / 80 %),
as in medical-aegis `check_trajectory_sources.probes()` (body, not the opener) and our MAA converter.
A probe that also occurs in the task question is ignored. An earlier step is a source when >= 1 probe
occurs in this step's input text (message contents + tool-call arguments of input messages);
`how = verbatim` when the whole normalised output occurs, else `excerpt`. Transitive copies are dropped:
a candidate is not counted when each matched probe occurs in the input no more often than in the outputs of
the other matched candidates (a later step quoting it explains the match; counting occurrences keeps
direct reads in cumulative contexts). For tool-call-only outputs the probe text is the call arguments.
Exceptions (protocol): speaker-selection outputs (agent names) are not probed; the next expert turn gets a
`control` source from that selection; a tool step reads its issuing call (`structured_field`).
TraceElephant tool steps are created for every `tool` message whose `tool_call_id(s)` answer a recorded
call (SWE-agent); Magentic-One page results are not logged as tool messages (they enter later inputs as
agent messages), so those calls stay on the llm step.

### protocol rules (no per-step inputs)

| framework | rule | basis |
|---|---|---|
| magentic_one (W&W Hand-Crafted) | broadcast messages = (re)plan, Orchestrator instruction, agent answers, terminal output; progress ledger and agents read the broadcast thread since the last (re)plan (verbatim); next-speaker / stalled / satisfied / termination thoughts and the instruction read the latest ledger (structured_field); agents also get `control` from the latest ledger; ComputerTerminal reads the last llm message (excerpt) | Magentic-One paper (Fourney et al. 2024) / AutoGen LedgerOrchestrator: messages are broadcast, ledgers are orchestrator-internal, agents are reset and the plan re-broadcast on replanning; checked against TraceElephant inputs (agent inputs = task ledger + broadcast messages, no ledger JSON) |
| magentic_one (MAST, ARIA; console logs without ledger calls) | task ledger: []; instruction, agent answers, final answer read the thread since the last task ledger (verbatim); ARIA's `['Agent']` speaker list reads the instruction (structured_field) and gives `control` to the next agent answer; replan ledger reads the old thread | same |
| captainagent (W&W Algorithm-Generated) | shared group chat: every turn reads all earlier turns (verbatim); the first message (task + plan from the captain) reads []; Computer_terminal reads the previous turn (excerpt) | AG2 GroupChat broadcasts every message to all agents; confirmed by TraceElephant expert inputs (system + all earlier messages) |
| ag2_mathchat | two-agent chat: every llm turn reads all earlier turns; proxy (code execution) reads the last assistant turn (excerpt); the proxy's initial prompt = task | AG2 MathChat (Wu et al. 2023) |
| ag2_groupchat | shared thread (as captainagent); `exitcode:` messages are executions of the previous turn's code | AG2 GroupChat |
| ag2_student_verifier (ARIA) | chat 1 Student <-> Python Assistant: each turn reads all earlier turns of chat 1; the templated "Review and finalize" message reads everything before it (it embeds the transcript); chat 2 Verifier <-> Python Assistant: each turn reads chat 2 so far | message content (transcript embedded in the review request), fixed speaker order |
| chatdev | within a phase chat: every utterance reads the earlier utterances of that chat (verbatim); and the conclusion (last utterance) of the latest instance of each earlier phase (structured_field: placeholders such as modality, language, codes, comments) | ChatDev (Qian et al. 2024) chat chain; phase prompt tables in the logs show the placeholders |
| metagpt (MAST) | SimpleCoder reads [] (requirement = task); SimpleTester reads SimpleCoder + SimpleReviewer + own messages; SimpleReviewer reads SimpleTester + own | MetaGPT `examples/build_customized_multi_agents.py` (`_watch` lists; actions use the role's memory) |
| metagpt (ARIA) | PM []; Architect <- PM; Engineer <- PM, Architect; QA <- PM (acceptance contract), Engineer | MetaGPT SOP subscriptions; QA texts check against the acceptance contract and "the Engineer's" solution |
| hyperagent | Planner <- all earlier Planner steps and intern reports; intern inner step <- latest Planner step (excerpt: the subgoal) + same intern's inner steps since it; report <- those inner steps (summary) | HyperAgent (Phan et al. 2024) planner/intern design; "Intern Name / Subgoal" lines in the logs |
| openmanus | think <- every earlier step (agent memory) and the plan (structured_field); tool result <- its think call (structured_field); ARIA run summaries <- all steps (summary) | OpenManus ToolCallAgent memory persists across plan steps |
| appworld_mas | each agent loop (supervisor, each app-agent loop instance) is a conversation: llm steps read the earlier steps of the same loop; delivered messages / execution outputs read the issuing llm step | log structure ("Entering / Exiting <app> Agent message loop") |
| smolagents (AFTraj) | Manager reads its whole memory (all earlier steps); search_agent reads the delegating Manager step (structured_field: the task argument) | smolagents managed agents |
| agents_handoff, aftraj_expert_team, single_tool_agent (AFTraj) | shared conversation: llm turns read all earlier steps; environment / Computer_terminal reads the last llm turn | Swarm / Agents-SDK handoff keeps one conversation; AutoGen group chat broadcast |
| langgraph_layered | each agent reads the previous layer (previous step) | MAScope LG-Ctrl layered = pipeline (sequence A,B,C,D,E in every clean trace) |
| langgraph_centralized | hub reads every earlier step; a worker reads the hub's latest message (structured_field when it is a `{"next_worker", "task"}` JSON) | hub JSON in the traces |
| langgraph_decentralized, mascope_debate | round r reads all round r-1 turns; round 1 reads [] | fixed round-robin (3 agents x k rounds) |
| langgraph_shared_pool, mascope_autogen | every earlier message | shared pool / shared AutoGen thread |
| mascope_crewai | leader plan []; task i reads the leader plan (structured_field) + the outputs of its `depends_on` tasks (all 31 clean traces align task list and executors) | CrewAI task dependencies in the leader JSON |
| tau_bench_agent | agent reads the policy (`task:obs:policy`) and the whole conversation; the user simulator reads only the agent's text replies and its own turns; a tool result reads its call | tau-bench user simulation |

## Dataset-specific notes
* **Who&When**: Hand-Crafted `history[0]` (human task) is task.query, not a step; `mistake_step` indexes
  `history`, mapped to `mistake_step_id`. AgentRx magentic labels (44 of 58 trajectories have labels; all 58
  are text-identical to Who&When Hand-Crafted position by position) are attached as `labels.external.agentrx`.
* **TraceElephant**: `agent_id` is the agent that made the call (from the prompt), so a Magentic-One
  ledger call that TraceElephant files under `WebSurfer` is an `orchestrator` step; the dataset's own
  attribution is kept in `labels.external.step_agent_names` (mistake_agent agrees with it at mistake_step
  in all mapped cases). Input screenshots stay references (`{'type':'image','image_file':...}`).
* **MAST-Data**: the log format is detected from the text (2 rows labelled HyperAgent are ChatDev logs;
  flagged `labels.external.format_mismatch`). Dropped log content: config tables, pip / docker output,
  HTTP / token lines, ChatDev `[Start Chat]` phase prompts and repeated system-prompt brackets / seminar
  conclusions, `[Update Codes]` dumps (inputs, not outputs). OpenManus task text is truncated in the logs
  ("...", `provenance.task_query_truncated`). 4 MetaGPT logs have an empty requirement.
* **ARIA**: event ids -> step ids in `labels.external.event_step_map`; first-bad events that are the task
  message or a dropped roll-up have no step (`null` in `first_bad_step_ids`).
