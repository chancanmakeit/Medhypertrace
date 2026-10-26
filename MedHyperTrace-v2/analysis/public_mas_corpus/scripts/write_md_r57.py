# r57: write mas_traj_r57.md from mas_traj_r57.json (produced by data_tools.public_to_mas_traj.validate).
# Reference numbers (earlier token stats, Qwen3-8B) are read from stats.json / stats_r53.json / stats_r55.json.
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.dirname(HERE)
R = json.load(open(os.path.join(D, "mas_traj_r57.json")))
S = json.load(open(os.path.join(D, "stats.json"))); S53 = json.load(open(os.path.join(D, "stats_r53.json")))
S55 = json.load(open(os.path.join(D, "stats_r55.json")))
ORDER = ["who_and_when", "traceelephant", "mast_data", "aria", "aftraj", "mascope", "agentrx_tau"]
REF = {
    "who_and_when": (S["Who&When"]["overall"]["n"], S["Who&When"]["overall"]["tokens_total"], "all 184; stats count task + every history message"),
    "traceelephant": (S["TraceElephant"]["overall"]["n"], S["TraceElephant"]["overall"]["tokens_total"],
                      "stats = unique message texts within a trace INCLUDING input contexts (page text, tool observations: 55.14M raw input_context); ours = outputs only (inputs are kept in input_messages)"),
    "mast_data": (S["MAST"]["overall"]["n"], S["MAST"]["overall"]["tokens_total"],
                  "stats = every blank-line paragraph of the raw log incl. config tables, pip/docker output, ChatDev phase prompts and repeated conclusions (paragraph dedup 22.28M); ours = agent messages + tool outputs only (ChatDev: utterance blocks are 14.5% of a log's characters)"),
    "aria": (S53["ARIA"]["overall"]["n"] - S53["ARIA"]["mmlu"]["medical_core"]["n"],
             S53["ARIA"]["overall"]["tokens_total"] - S53["ARIA"]["mmlu"]["medical_core"]["tokens"],
             "reference = r53 ARIA minus its 2,231 core-medical MMLU episodes (same removal rule); r53 also counted tool-call argument values (0.13M) separately"),
    "aftraj": (S53["AFTraj"]["by_class"]["clean"]["n"] + S53["AFTraj"]["by_class"]["natural_fail"]["n"],
               S53["AFTraj"]["by_class"]["clean"]["tokens_total"] + S53["AFTraj"]["by_class"]["natural_fail"]["tokens_total"],
               "reference = r53 clean + natural_fail classes; r53 counted tool-call argument values (0.27M here) and thoughts that are repeated inside the content twice (0.16M)"),
    "mascope": (S53["MAScope/LG-Ctrl"]["by_class"]["clean"]["n"] + S53["MAScope/Inject-Mix"]["by_class"]["clean"]["n"],
                S53["MAScope/LG-Ctrl"]["by_class"]["clean"]["tokens_total"] + S53["MAScope/Inject-Mix"]["by_class"]["clean"]["tokens_total"],
                "reference = r53 clean classes of LG-Ctrl + Inject-Mix (paragraphs); we drop the [system] session line"),
    "agentrx_tau": (S55["AgentRx/tau_retail"]["overall"]["n"], S55["AgentRx/tau_retail"]["overall"]["tokens_total"],
                    "the system policy moved to task.observations (34,916 Qwen tokens) and tool-call arguments (4,978) are not in our sum; adding them gives exactly the r55 figure"),
}
L = []
w = L.append
w("# Public MAS datasets -> mas-traj/1: conversion and validation (round 57)\n")
w("Converters: `MedHyperTrace-v2/data_tools/public_to_mas_traj/` (conventions and per-framework source rules in its README.md). "
  "Data (not in the repo): `/home/claude/public_mas/mas_traj/<dataset>.jsonl.gz`. Raw numbers: `mas_traj_r57.json`; two example records per "
  "dataset (strings cut at 300 chars): `samples_r57/`. Generated 2026-10-26.\n")
w("Validation per dataset: (a) medical-aegis `export_schema_v1.check()` imported from their file, unchanged; (b) their "
  "`scripts/sources_provenance_analysis.py` run unchanged on a decompressed copy; (c) text-match statistics where per-step inputs exist; "
  "(d) `python -m data_tools.maa_exclusion check docs/interfaces/maa_exclusion_v1.json` (task.query / task.images); (e) counts and token sums "
  "(o200k = output_tokens_est tokenizer; Qwen3-8B = tokenizer of stats*.md); (f) each converter re-run, sha256 compared.\n")
w("## Summary\n")
w("| dataset | records | check() pass | dup run_ids | frameworks (family) | llm / tool steps | MAA exact / probe | deterministic |")
w("|---|---|---|---|---|---|---|---|")
for ds in ORDER:
    if ds not in R: continue
    r = R[ds]; a = r["a_check"]
    fws = ", ".join(f"{k} {v['records']} ({v['family']})" for k, v in r["frameworks"].items())
    ll = sum(v.get("steps_llm", 0) for v in r["per_framework"].values()); tl = sum(v.get("steps_tool", 0) for v in r["per_framework"].values())
    w(f"| {ds} | {a['records']} | {a['pass']} | {a['duplicate_run_ids']} | {fws} | {ll} / {tl} | {r['d_maa_exclusion'].get('exact')} / {r['d_maa_exclusion'].get('probe')} | {r['f_determinism']['identical']} |")
w("")
w("Kept / skipped: Who&When all 184; TraceElephant all 220; MAST-Data all 1642 (0 parse failures); ARIA 22,237 of 24,468 (2,231 core-medical "
  "MMLU episodes removed, identical to r53's count; 1,402 OpenManus roll-up events dropped as duplicates); AFTraj 1,548 (1,162 safe + 386 "
  "natural failures; 728 injected skipped); MAScope 260 clean (80 LG-Ctrl + 180 Inject-Mix; 1,109 injected skipped; MAST-clean skipped as a "
  "subset of MAST-Data); AgentRx tau_retail 29 (AgentRx magentic not re-converted: attached to 44 Who&When records as labels.external.agentrx).\n")
w("## (e) Sanity: counts and tokens vs earlier stats\n")
w("| dataset | records (ref) | Qwen3-8B tokens of query + step outputs | reference tokens | o200k llm outputs | o200k tool outputs | why they differ |")
w("|---|---|---|---|---|---|---|")
for ds in ORDER:
    if ds not in R: continue
    e = R[ds]["e_tokens"]; n, t, why = REF[ds]
    w(f"| {ds} | {R[ds]['a_check']['records']} ({n}) | {e['query_plus_step_outputs_qwen3_8b']:,} | {t:,} | {e['llm_output_o200k']:,} | {e['tool_output_o200k']:,} | {why} |")
w("")
w("## (b) Read set determined by slot (partner script, round-41 definition)\n")
w("`slot_determined` = share of llm steps whose read set (sources keyed as (agent, phase, round, k-th occurrence)) equals the most common read set "
  "of their slot (framework, phase, round, agent); `mode_share` = share of the most common (phase, round offset, agent) pattern per (framework, phase). "
  "Weighted over phases per framework (full per-phase table in the JSON):\n")
w("| dataset | framework | llm steps | slot_determined (weighted) | lowest phases |")
w("|---|---|---|---|---|")
for ds in ORDER:
    if ds not in R: continue
    agg = {}
    for k, v in R[ds]["b_sources_provenance"]["slot_determined"].items():
        f, ph = k.split("|", 1); a = agg.setdefault(f, [0, 0.0, []]); a[0] += v["steps"]; a[1] += v["steps"] * v["slot_determined"]; a[2].append((v["slot_determined"], ph, v["steps"]))
    for f, (n, m, phs) in sorted(agg.items()):
        low = ", ".join(f"{ph} {sd:.2f}" for sd, ph, ns in sorted(phs)[:3])
        w(f"| {ds} | {f} | {n} | {m / n:.2f} | {low} |")
w("")
w("Reading: for protocol-inferred data the read set is a deterministic function of the step sequence, so a low value says that the SEQUENCE varies "
  "within a slot (e.g. \"every earlier step of the thread\" gives a different set at every position), not that inference is uncertain. Rules of the form "
  "\"fixed predecessor roles\" give 1.00 (MetaGPT ARIA, debate rounds, layered pipeline, plans / facts calls). Cumulative-history rules (group chats, "
  "agent memory, Magentic-One threads, ChatDev phases) score low by construction. TraceElephant is the only text_match set: its values measure "
  "real variation of the recorded inputs. The partner's script needed no adaptation (return code 0 on all files).\n")
w("## (c) Text-match statistics (TraceElephant, the only dataset with per-step inputs)\n")
w("| framework | llm steps with inputs | share with zero inferred sources | sources | share text_match |")
w("|---|---|---|---|---|")
for f, v in R["traceelephant"]["c_text_match"].items():
    w(f"| {f} | {v['steps_with_inputs']} | {v['share_steps_zero_sources']:.3f} | {v['sources_total']} | {v['share_sources_text_match']:.3f} |")
cr = R["traceelephant"].get("convert_report") or {}
w(f"\nTransitive matches dropped (a later listed source quotes the candidate): {cr.get('text_match', {}).get('dropped_transitive')}. "
  "Non-text_match sources there are protocol: tool step <- its call (SWE-agent, 1,081) and speaker-selection control (CaptainAgent, 733). "
  "Zero-source steps are mostly first calls (facts / role matching / first SWE step, which read only the task).\n")
w("## (d) MAA exclusion\n")
for ds in ORDER:
    if ds in R: w(f"- {ds}: {R[ds]['d_maa_exclusion']['stdout']}")
w("")
w("## Label mapping checks\n")
w("- Who&When: mistake_step mapped to a step for 181/184 (3 Hand-Crafted indices point past the history). At the mapped step the named "
  "agent equals mistake_agent in 175, differs in 6 (dataset-internal: e.g. index on `Orchestrator (-> WebSurfer)` for a WebSurfer mistake, "
  "or on a Computer_terminal output for an expert).")
w("- TraceElephant: mapped 218/220 (2 AssistantBench traces have mistake_step `none` / `Step 36`); TraceElephant's own step agent_name equals "
  "mistake_agent in all 218. Note our agent_id differs from that name for Magentic-One ledger calls (we attribute the call to the Orchestrator).")
w("- AFTraj: 386/386 mapped, agent equals mistake_agent in all.")
w("- ARIA: first-bad events without a step: 254 point at the task message (221 Magentic-One, 33 MetaGPT), 140 at OpenManus roll-up events "
  "that we drop as duplicates (see open questions).\n")
w("## Open questions / convention problems\n")
w("1. **Family of Magentic-One** (W&W, TraceElephant, MAST, ARIA; ~2,900 runs): mapped to `groupchat` by the in-doubt rule "
  "(MagenticOneGroupChat = AutoGen group chat with LLM speaker selection). If the partner considers the ledger architecture distinct, change "
  "one line in the registry (own_family `magentic_one`). Same question, smaller, for AFTraj expert team and `langgraph_decentralized` -> debate.")
w("2. **Slot-determinacy is not informative for cumulative-history protocols** (see (b)); we suggest also reporting it with sources keyed "
  "by relative position (\"all earlier steps of the thread\") before comparing frameworks.")
w("3. **Steps that are not LLM calls** have no kind in the schema besides llm/tool: framework template messages (AG2 group-chat introduction, "
  "ARIA's \"Review and finalize\" request, OpenManus run summaries, MAST AppWorld delivered messages) are exported as `tool` steps; Who&When "
  "Hand-Crafted `Orchestrator (thought)` lines such as \"Next speaker WebSurfer\" and the termination line are exported as llm steps although "
  "they are derived from the ledger call. A third kind (e.g. `system`) would express this better.")
w("4. **Inputs that are not steps**: Magentic-One page text (TraceElephant) and ChatDev phase prompts enter inputs but are neither steps "
  "nor task observations; `task.observations` is meant for shared observations. The partner might want a `kind: \"environment\"` step.")
w("5. **ARIA localization pointing at the task message or at a roll-up** (394 episodes): no step to point at. Options: keep roll-ups as "
  "tool steps (adds duplicated text to the corpus), or map to the last step summarised.")
w("6. **MAST-Data MMLU (AG2 group chat, 168 runs) contains medical questions** (it has no subject field); the MAA exclusion finds 0 overlaps, "
  "but unlike ARIA no medical filter was applied (not requested). Decide whether to filter with the r53 keyword heuristic.")
w("7. TraceElephant `is_correct` is set False for all traces (every trace carries a mistake annotation; SWE tests fail), not recomputed "
  "from the answers; Who&When likewise. MAST-Data `is_correct` is null except AG2 GSM-Plus (`other_data.correct`).\n")
w("## Left undone\n")
w("- Nothing of the requested list; all 7 datasets converted and validated. Not done (out of scope): injected datasets, TRAIL, AgentErrorBench, "
  "ATBench, RAISER; validation of text-match inference against the partner's recorded sources (planned with their data).")
open(os.path.join(D, "mas_traj_r57.md"), "w").write("\n".join(L) + "\n")
print("wrote", os.path.join(D, "mas_traj_r57.md"))
