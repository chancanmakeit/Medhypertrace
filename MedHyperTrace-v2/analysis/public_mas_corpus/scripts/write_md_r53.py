# r53: merge measure/overlap/RAISER/peek outputs into stats_r53.json and render stats_r53.md
import json, os
P = "/home/claude/public_mas"
D = "/home/claude/medhypertrace/MedHyperTrace-v2/analysis/public_mas_corpus"
S = json.load(open(f"{P}/stats_r53_measure.json"))
OV = json.load(open(f"{P}/overlap_r53.json"))
RA = json.load(open(f"{P}/raiser_check_r53.json"))
PK = json.load(open(f"{P}/wwp_image_peek_r53.json"))
DL = json.load(open(f"{P}/download_log_r53.json"))
S["overlap_vs_MAA"] = OV; S["RAISER_file_check"] = RA; S["WWP_image_split_peek"] = PK; S["download_log"] = DL
S["AgentRx"] = dict(status="gated (gated=auto): 403 GatedRepoError with the provided read token on all 4 data files (README readable). User must accept terms on HF.",
                    license="cc-by-4.0", files=["magentic_dataset.jsonl 4.2MB", "magentic_one.jsonl 0.15MB", "tau_retail.jsonl 0.04MB", "tau_retail_dataset.jsonl 0.83MB"],
                    readme_summary="failed trajectories (tau-retail, Magentic-One) with step-level failure categories, failed_agent per failure, and a designated root-cause failure")
json.dump(S, open(f"{D}/stats_r53.json", "w"), indent=1, ensure_ascii=False)

def M(x): return f"{x/1e6:.2f}M" if x is not None else "not measured"
def K(x): return f"{x:,}"
L = []
L.append("# Public MAS failure-attribution datasets, round 53: trajectory-text token stats\n")
L.append("Tokenizer: Qwen/Qwen3-8B (add_special_tokens=False). Same protocol as stats.md: only natural-language trajectory content is counted (task question, message/step contents, final output, tool-call argument values, tool results); JSON keys, labels, annotations, injection metadata, repairs/counterfactuals excluded. Generated 2026-10-22 in the local sandbox; raw data under /home/claude/public_mas/raw/, scripts `scripts/*_r53.py`.\n")
L.append("## Summary\n")
L.append("| Dataset | Trajectories | Steps (total / p50) | Total tokens | Global exact-dedup tokens | p50 / p90 / p99 / max per traj | >8K / >32K | Top benchmarks (token share) |")
L.append("|---|---|---|---|---|---|---|---|")
def row(name, key, bench="by_benchmark"):
    o = S[key]["overall"]; tot = o["tokens_total"]; b = S[key][bench]
    tb = ", ".join(f"{k} {v['tokens_total']/tot*100:.0f}%" for k, v in list(b.items())[:4]) if tot else ""
    st = f"{o['steps_total']} / {o['steps_p50']}" if o["steps_total"] is not None else "not measured"
    L.append(f"| {name} | {o['n']} | {st} | {M(tot)} | {M(o['tokens_global_exact_dedup'])} | {o['p50']} / {o['p90']} / {o['p99']} / {o['max']} | {o['n_gt_8k']} / {o['n_gt_32k']} | {tb} |")
L.append("| microsoft/AgentRx | gated - not downloaded | not measured | not measured | not measured | not measured | not measured | gated, user must accept terms |")
row("CORRECT-Error (all injected)", "CORRECT-Error")
row("AFTraj (safe+unsafe)", "AFTraj")
row("ARIA (all; incl. medical MMLU)", "ARIA")
row("Who&When-Pro mirror, text", "WhoWhenPro-mirror (text)", "by_benchmark_framework")
row("Who&When-Pro mirror, video (text-in-JSON only)", "WhoWhenPro-mirror (video)", "by_benchmark_framework")
row("AgentErrorBench (single-agent)", "AgentErrorBench")
row("MAScope MAST-clean (MAST subset)", "MAScope/MAST-clean")
row("MAScope LG-Ctrl", "MAScope/LG-Ctrl")
row("MAScope Inject-Mix", "MAScope/Inject-Mix")
L.append("| RogerYao/RAISER | 0 (labels only) | - | 0 | 0 | - | - | references AEGIS/CORRECT/MAST/TE/TRAIL/W&W traces |")
row("ATBench (1,000; single-agent)", "ATBench/ATBench")
row("ATBench500 (single-agent)", "ATBench/ATBench500")
L.append("")
L.append("Total tokens = sum over trajectories as stored, except AgentErrorBench, whose user prompts re-embed earlier observations: there it is within-trace unique lines (raw as stored: %s). ARIA excludes OpenManus `agent_run_completed` roll-ups that re-concatenate the step outputs. Global exact-dedup = unique segment texts across the dataset (segment = message/turn/event; MAScope = blank-line paragraph as for MAST; AgentErrorBench = line).\n" % M(S["AgentErrorBench"]["overall"]["tokens_raw_as_stored"]))

g = S["grand_total_new"]
L.append("## Grand total of new, non-medical, non-duplicated tokens\n")
L.append(g["rule"] + ".\n")
L.append("| scope | (a) natural / clean | (b) injected | total | removed as already in old 5 sets |\n|---|---|---|---|---|")
for k in ["all", "mas_only"]:
    x = g[k]; L.append(f"| {'all r53 text sets' if k=='all' else 'MAS only (drops AgentErrorBench, ATBench, ATBench500)'} | {M(x['natural_or_clean'])} | {M(x['injected'])} | {M(x['total'])} | {M(x['excluded_as_old_dup'])} |")
L.append("\nPer-dataset contribution (after cross-set dedup, in order of crediting):\n")
L.append("| dataset | natural/clean | injected | medical trajectories removed (n / tokens) |\n|---|---|---|---|")
for k, v in g["all"]["per_dataset"].items():
    me = g["medical_excluded_trajectories"].get(k, {})
    L.append(f"| {k} | {M(v['natural_or_clean'])} | {M(v['injected'])} | {me.get('n',0)} / {M(me.get('tokens',0))} |")
L.append("")

def table(title, d, cols=("n", "tokens_total", "tokens_global_exact_dedup", "p50", "p90", "n_gt_8k", "n_gt_32k")):
    L.append(f"#### {title}\n"); L.append("| group | " + " | ".join(cols) + " | share |"); L.append("|---|" + "---|" * (len(cols) + 1))
    tot = sum(v["tokens_total"] for v in d.values()) or 1
    for k, v in d.items(): L.append(f"| {k} | " + " | ".join(str(v[c]) for c in cols) + f" | {v['tokens_total']/tot*100:.1f}% |")
    L.append("")
def ov(name):
    x = OV["per_dataset"][name]
    return f"MAA overlap: {x['exact_question_matches']} exact normalized question matches ({x['rows_questions_checked']} questions); first-60-char probes: {x['probe_hits']} / {x['probes']} hits over {x['chars_searched']/1e6:.0f}M normalized chars; planted control found = {x['planted_control_found']}."
def xdup(name, top=6):
    o = S["cross_dataset_question_overlap"]["per_dataset"][name]
    items = sorted(o["overlaps"].items(), key=lambda kv: -kv[1]["first60"])[:top]
    return f"Cross-dataset question overlap ({o['n_questions']} distinct questions): " + (", ".join(f"{k} exact {v['exact']} / first-60 {v['first60']}" for k, v in items) if items else "none") + "."
def parts(key):
    p = S[key].get("injected_parts")
    if not p: return ""
    return ("Injected trajectories, token parts: " + ", ".join(f"{k} {K(v)}" for k, v in p.items() if k != "prefix_dedup_by_task_exact_segment")
            + f"; prefix+task deduplicated by (task, exact segment) = {K(p['prefix_dedup_by_task_exact_segment'])}.")
def cls(key): return ", ".join(f"{k} {v['n']} ({M(v['tokens_total'])})" for k, v in S[key]["by_class"].items())
def med(key):
    m = S[key]["medical"]; return f"Medical-flagged trajectories: {m['n']} ({M(m['tokens'])}; {m['sources']})."

L.append("## Per-dataset notes\n")
L.append("### 1. microsoft/AgentRx\n")
L.append("- **Gated (gated=auto): all 4 data files return 403 GatedRepoError with the provided read token; the user must accept the terms on HF.** README is public: license CC-BY-4.0; failed trajectories from tau-retail and Magentic-One with step-level failure categories, failed_agent per failure and a designated root-cause failure (agent + step + category). Files: magentic_dataset.jsonl 4.2 MB, tau_retail_dataset.jsonl 0.83 MB, plus label files. Natural failures (no injection mentioned). Not measured.\n")

L.append("### 2. yifanyu/CORRECT-Error\n")
c = S["CORRECT-Error"]
L.append(f"- License Apache-2.0. 2,226 trajectories, **all error-injected** (Magentic-One runs, then contextual error injection; no clean subset). Labels: mistake_agent + mistake_step (decisive error) + free-text reason (often empty). Generators: gpt-4o-mini / gpt-5-nano.")
L.append(f"- {parts('CORRECT-Error')}")
L.append(f"- Unique questions {c['unique_questions']} (task reuse across generators/injections). {med('CORRECT-Error')}")
L.append(f"- {ov('CORRECT-Error')}"); L.append(f"- {xdup('CORRECT-Error')}\n")
table("CORRECT-Error by benchmark", c["by_benchmark"]); table("CORRECT-Error by generator", c["by_model"])

L.append("### 3. ZBox008003/AFTraj (AFTraj-2K)\n")
a = S["AFTraj"]
L.append(f"- License CC-BY-4.0. Classes: {cls('AFTraj')}. Safe = verified-successful (clean) runs; unsafe = 728 injected into verified-safe runs + 386 naturally failed runs labelled by a multi-judge propose-verify pipeline ('diagnosed'). Labels: mistake_step (k*) + mistake_agent (a*) + optional reason. Injected traces share their prefix with the safe originals (removed by exact dedup).")
L.append(f"- {parts('AFTraj')}")
L.append(f"- {med('AFTraj')}"); L.append(f"- {ov('AFTraj')}"); L.append(f"- {xdup('AFTraj')}\n")
table("AFTraj by domain/class", a["by_domain_class"]); table("AFTraj by benchmark", a["by_benchmark"])

L.append("### 4. Edlison/ARIA\n")
r = S["ARIA"]; mm = r["mmlu"]
L.append(f"- License: none declared on the card (no license field). 24,468 episodes (train 14,683 / validation 4,895 / test 4,890). Frameworks AG2, OpenManus, MetaGPT, Magentic-One; benchmarks GAIA, GSM-Plus, HumanEval, MMLU, OlympiadBench, SWE-bench-Lite. **Natural runs (no injection)**: {cls('ARIA')} (clean = source_success True). Labels are model-generated: first-bad event ids (step), primary/secondary error codes (category), responsible agents. Repairs/replacement events and counterfactuals excluded.")
p = r["overall"]["tokens_by_part"]
L.append(f"- Token parts: " + ", ".join(f"{k} {M(v)}" for k, v in sorted(p.items(), key=lambda kv: -kv[1])) + f". tool_result tokens are counted once (after_act content equals the tool result in {r['rollup_classification']} roll-up check: rollup_dup excluded).")
L.append(f"- **MMLU = {mm['n']} episodes ({M(mm['tokens'])}), subject read from the 'Subject:' line ({mm['n_subject_detected']} detected), {mm['unique_mmlu_questions']} distinct questions. Medical subjects ({', '.join(mm['medical_core_subjects'])}): {mm['medical_core']['n']} episodes, {M(mm['medical_core']['tokens'])} tokens ({M(mm['medical_core']['dedup_tokens'])} dedup).** Borderline ({', '.join(mm['borderline_subjects'])}): {mm['borderline']['n']} episodes, {M(mm['borderline']['tokens'])} (kept).")
L.append("- Medical subjects: " + ", ".join(f"{k} {v['n']} ({M(v['tokens'])})" for k, v in mm["per_subject"].items() if k in mm["medical_core_subjects"]) + ".")
L.append(f"- {med('ARIA')}"); L.append(f"- {ov('ARIA')}"); L.append(f"- {xdup('ARIA')}\n")
table("ARIA by framework", r["by_framework"]); table("ARIA by benchmark", r["by_benchmark"]); table("ARIA by class", r["by_class"]); table("ARIA by host model", r["by_model"])

L.append("### 5. Leoxx/whowhen_pro (Who&When Pro mirror)\n")
w = S["WhoWhenPro-mirror (text)"]; vv = w["vs_tmpxv7_real_files"]
L.append(f"- License CC-BY-4.0. **The mirror gives readable text traces: {vv['mirror_text_traces']} text rows (all 6,257 listed in the broken tmpxv7 release, incl. the 5,946 that were dangling symlinks there) + {vv['mirror_video_traces']} video rows.** All injected (one injected error per trace; no clean subset). Labels: agent + step (or round/position/stage) + error mode (17 modes / 6 categories).")
L.append(f"- vs tmpxv7: real tmpxv7 files {vv['tmpxv7_real']}; mirror traces whose query matches a tmpxv7 real file: {vv['mirror_traces_with_query_in_tmpxv7']}; mirror traces with >=95% of tokens in tmpxv7 segments: {vv['mirror_traces_with_ge95pct_tokens_in_tmpxv7_segments']}.")
L.append(f"- Injection located (prefix/injected/post split possible): {w['injection_located']}. {parts('WhoWhenPro-mirror (text)')}")
L.append(f"- Single- vs multi-agent: alfagent and smolagents are single-agent (3,587 of 6,257 text traces); magentic-one, macnet, metagpt, debate, dylan, mathchat are multi-agent.")
L.append(f"- image / image_gui splits (6.8 GB / 11.2 GB, images embedded) not downloaded; 32 KB range peek shows the same row schema {PK['data/image.jsonl']['first_keys']} (first rows: {PK['data/image.jsonl']['framework_benchmark']}, {PK['data/image_gui.jsonl']['framework_benchmark']}).")
L.append(f"- {med('WhoWhenPro-mirror (text)')}"); L.append(f"- {ov('WhoWhenPro-mirror')}"); L.append(f"- {xdup('WhoWhenPro-mirror (text)')}\n")
table("Who&When-Pro mirror text by benchmark/framework", w["by_benchmark_framework"])
vd = S["WhoWhenPro-mirror (video)"]
L.append(f"Video (text-in-JSON only, not in grand total): {vd['overall']['n']} traces, {M(vd['overall']['tokens_total'])}. {parts('WhoWhenPro-mirror (video)')}\n")

L.append("### 6. davide221/agenterrorbench\n")
e = S["AgentErrorBench"]
L.append(f"- License: none declared on the card. 200 trajectories (train 139 / validation 31 / test 30) - this is AgentDebug's AgentErrorBench: **single-agent** (ALFWorld 100, GAIA 50, WebShop 50; GPT-4o, Llama3.3-70B, Qwen3-8B). **Natural failures** (all failed; no clean subset, no injection). Labels: critical_failure_step + module (memory/reflection/planning/action/system) + failure type, plus per-step annotations.")
L.append(f"- Each user turn re-embeds recent observations (GAIA pages are re-pasted every step): raw as stored {M(e['overall']['tokens_raw_as_stored'])} vs within-trace unique lines {M(e['overall']['tokens_total'])}.")
L.append(f"- {med('AgentErrorBench')}"); L.append(f"- {ov('AgentErrorBench')}"); L.append(f"- {xdup('AgentErrorBench')}\n")
table("AgentErrorBench by benchmark", e["by_benchmark"]); table("AgentErrorBench by model", e["by_model"])

L.append("### 7. mascope/mascope-bench\n")
mc = S["MAScope/MAST-clean"]; o = mc["overlap_with_MAST_Data"]
L.append("- License CC-BY-4.0 (MAST-clean retains MAST upstream terms). Labels: trace-level MAST-14 multi-label failure categories + communication-topology label; no agent/step labels.")
L.append(f"- **MAST-clean ({o['n']} traces) vs mcemri/MAST-Data: {o['counts']}. Duplicates (exact or paragraph-Jaccard >= 0.9): {o['duplicates_exact_or_near']} / {o['n']}.** Framework counts MAST-clean {o['framework_counts_MAST_clean']} vs MAST-Data {o['framework_counts_MAST_Data']}. Dedup tokens {M(o['dedup_tokens'])}, of which not already MAST paragraphs: {M(o['dedup_tokens_not_in_MAST_paragraphs'])}. Natural failures (MAST runs); traces with no MAST label: {mc['n_with_any_mast_label']} labelled of {mc['overall']['n']}.")
for k in ["MAScope/LG-Ctrl", "MAScope/Inject-Mix"]:
    x = S[k]
    L.append(f"- {k.split('/')[1]}: {cls(k)}. Anomaly-injection-derived synthetic runs (LangGraph / AutoGen-based debate etc.) on planning/RAG tasks; anomaly 'None' rows are the uninjected controls (clean). No step marker for the injection inside the raw string. Labels with any MAST code: {x['n_with_any_mast_label']}.")
L.append(f"- {med('MAScope/MAST-clean')} {med('MAScope/LG-Ctrl')} {med('MAScope/Inject-Mix')}")
L.append(f"- {ov('MAScope')}"); L.append(f"- {xdup('MAScope/MAST-clean')}\n")
table("MAST-clean by framework", mc["by_framework"]); table("LG-Ctrl by anomaly", S["MAScope/LG-Ctrl"]["by_anomaly"]); table("Inject-Mix by anomaly", S["MAScope/Inject-Mix"]["by_anomaly"]); table("Inject-Mix by framework", S["MAScope/Inject-Mix"]["by_framework"])

L.append("### 8. RogerYao/RAISER\n")
L.append("- License `other`, deliberately: LICENSE_DATA.md says the package does not redistribute third-party trace content and grants no rights to it; source identifiers stay subject to each upstream repo's license/access terms (AEGIS MIT, CORRECT-Error Apache-2.0, MAST-Data and TraceElephant CC-BY-4.0, Who&When unspecified, TRAIL MIT + gated, evaluation only, never reshared outside an approved gated/private repo); maintainers may later add a license for the original annotations only.")
L.append("- **No trajectory text.** All 7 data files hold IDs, hashes, binary role labels, confidences and outcomes; the longest string in any column is 92 chars (trace_id). 3,121 traces referenced (model_benchmark: 484 gold + 2,637 silver) from AEGIS, CORRECT-Error, MAST-Data, TraceElephant, TRAIL, Who&When - all already covered or gated. Labels: event-level (step) six binary roles (source, propagator, missed_verifier, contract_violation, symptom, repair_leverage); human_gold 1,600 candidate-role pairs. Trajectory tokens: 0.")
L.append(f"- {ov('RAISER')}\n")

L.append("### 9. AI45Research/ATBench\n")
for k in ["ATBench/ATBench", "ATBench/ATBench500"]:
    L.append(f"- {k.split('/')[1]}: {cls(k)}. {med(k)}")
L.append("- License Apache-2.0. **Single-agent** tool-use trajectories (roles user / agent / environment only). **Fully synthetic**: planner-generated blueprint, risk injection, simulated tool calls and tool responses; unsafe = risk injected by construction, safe = no risk. Labels: trajectory-level safe/unsafe + risk_source / failure_mode / real_world_harm categories (+ reason in ATBench); no step or agent labels. Root `test.json` is byte-identical to ATBench500/test.json (not counted twice).")
L.append(f"- {ov('ATBench')}"); L.append(f"- {xdup('ATBench/ATBench')}\n")
table("ATBench by class", S["ATBench/ATBench"]["by_class"]); table("ATBench500 by class", S["ATBench/ATBench500"]["by_class"])

L.append("## Overlap with the MAA medical corpus\n")
L.append(f"MAA: {OV['maa_unique_queries']} unique normalized queries; {OV['probes']} first-60-char probes (queries >= 40 chars). Searched text = every string value of every row (JSON-in-string parsed), normalized.\n")
L.append("| dataset | questions checked | exact matches | probe hits | chars searched | planted control |\n|---|---|---|---|---|---|")
for k, x in OV["per_dataset"].items():
    L.append(f"| {k} | {x['rows_questions_checked']} | {x['exact_question_matches']} | {x['probe_hits']} | {x['chars_searched']/1e6:.0f}M | {x['planted_control_found']} |")
L.append("")
L.append("## Downloads\n")
ok = [d for d in DL if not d.get("failed")]
L.append(f"Local sandbox, HF direct: {len(ok)} files OK ({sum(d['mb'] for d in ok):.0f} MB), all first attempt. AgentRx: 4 data files 403 (gated). Leoxx/whowhen_pro image/image_gui (18 GB) and video frames (3.6 GB) not downloaded.\n")
open(f"{D}/stats_r53.md", "w").write("\n".join(L))
print("written", len(L), "lines")
