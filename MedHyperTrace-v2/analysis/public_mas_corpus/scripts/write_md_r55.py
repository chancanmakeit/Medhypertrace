# r55: merge measure/overlap/download outputs into stats_r55.json and render stats_r55.md
import json
P = "/home/claude/public_mas"
D = "/home/claude/medhypertrace/MedHyperTrace-v2/analysis/public_mas_corpus"
S = json.load(open(f"{P}/stats_r55_measure.json"))
OV = json.load(open(f"{P}/overlap_r55.json"))
DL = json.load(open(f"{P}/download_log_r55.json"))
ok = [r for r in DL if not r.get("failed")]
S["overlap_vs_MAA"] = OV
S["download_log_summary"] = dict(files_ok=len(ok), mb=round(sum(r["mb"] for r in ok), 1), failed=[r for r in DL if r.get("failed")],
                                 per_repo={rp: dict(files=sum(r["repo"] == rp for r in ok), mb=round(sum(r["mb"] for r in ok if r["repo"] == rp), 1)) for rp in sorted({r["repo"] for r in DL})})
S["licenses"] = {"microsoft/AgentRx": "cc-by-4.0 (card + README); gated=auto",
                 "PatronusAI/TRAIL": "mit (card); gated=auto with extra terms: do not reshare outside a gated or private HF repo; card 'Out-of-Scope Use': must not be used for training systems intended to automate human evaluation, evaluation/benchmarking only"}
json.dump(S, open(f"{D}/stats_r55.json", "w"), indent=1, ensure_ascii=False)

def M(x): return f"{x/1e6:.2f}M" if x is not None else "not measured"
L = []
L.append("# Public MAS failure-attribution datasets, round 55: AgentRx and TRAIL (gated) trajectory-text token stats\n")
L.append("Tokenizer: Qwen/Qwen3-8B (add_special_tokens=False). Same protocol as stats.md / stats_r53.md: only natural-language trajectory content is counted (task question, message/step contents, final output, tool-call argument values, tool results); JSON keys, labels, annotations, injection metadata, repairs/counterfactuals excluded. Generated 2026-10-22 in the local sandbox after the user was granted access to both gated repos; raw data under /home/claude/public_mas/raw/ (not in the repo), scripts `scripts/*_r55.py` (helpers imported verbatim from `measure_r53.py` / `overlap_r53.py`).\n")
L.append("## Summary\n")
L.append("| Dataset | Trajectories | Steps (total / p50) | Total tokens | Global exact-dedup tokens | p50 / p90 / p99 / max per traj | >8K / >32K | Top benchmarks (token share) |")
L.append("|---|---|---|---|---|---|---|---|")
def row(name, key, bench="by_benchmark"):
    o = S[key]["overall"]; tot = o["tokens_total"]; b = S[key][bench]
    tb = ", ".join(f"{k} {v['tokens_total']/tot*100:.0f}%" for k, v in list(b.items())[:4]) if tot else ""
    st = f"{o['steps_total']} / {o['steps_p50']}" if o["steps_total"] is not None else "not measured"
    L.append(f"| {name} | {o['n']} | {st} | {M(tot)} | {M(o['tokens_global_exact_dedup'])} | {o['p50']} / {o['p90']} / {o['p99']} / {o['max']} | {o['n_gt_8k']} / {o['n_gt_32k']} | {tb} |")
row("microsoft/AgentRx (all; natural failures)", "AgentRx")
row("- AgentRx magentic (Magentic-One, MAS)", "AgentRx/magentic")
row("- AgentRx tau_retail (single agent)", "AgentRx/tau_retail")
row("PatronusAI/TRAIL (all; natural runs)", "TRAIL")
row("- TRAIL GAIA (manager + search_agent)", "TRAIL/gaia")
row("- TRAIL SWE-bench Lite (single CodeAgent)", "TRAIL/swe_bench")
L.append("")
tr = S["TRAIL"]["overall"]
L.append(f"Total tokens = sum over trajectories, except TRAIL: every LLM span re-sends the full agent memory, and step/tool outputs are re-wrapped into later inputs, so TRAIL's per-trajectory figure is within-trace unique segments (raw as stored, incl. the repeated context: {M(tr['tokens_raw_as_stored'])}; GAIA {M(S['TRAIL/gaia']['overall']['tokens_raw_as_stored'])}, SWE-bench {M(S['TRAIL/swe_bench']['overall']['tokens_raw_as_stored'])}). Steps: AgentRx = rows of `steps` (one substep each); TRAIL = `Step N` CHAIN spans of all agents (TRAIL also has {S['TRAIL']['labels']['llm_calls_total']} LLM spans). Global exact-dedup = unique segment texts across the dataset (segment = message/substep for AgentRx; LLM input message / output / tool-call argument value / tool output / step output for TRAIL).\n")

g = S["grand_total_new"]
L.append("## Grand total of new, non-medical, non-duplicated tokens\n")
L.append(g["rule"] + ".\n")
L.append("Deduped against (segment hashes rebuilt from re-downloaded raw data with the r53 segmentation code, " + f"{g['prior_hashes']:,} distinct segments): " + ", ".join(g["prior_sets_deduped_against"]) + ".\n")
L.append("| scope | (a) natural / clean | (b) injected | total | removed as already in prior sets |\n|---|---|---|---|---|")
lab = {"all": "AgentRx + TRAIL, all", "mas_only": "MAS only (AgentRx magentic + TRAIL GAIA)", "mas_only_strict": "MAS only, strict (TRAIL GAIA restricted to the 47 traces where search_agent actually ran)"}
for k in ["all", "mas_only", "mas_only_strict"]:
    x = g[k]; L.append(f"| {lab[k]} | {M(x['natural_or_clean'])} | {M(x['injected'])} | {M(x['total'])} | {M(x['excluded_as_prior_dup'])} |")
L.append("\nPer-dataset contribution (after cross-set dedup, in order of crediting):\n")
L.append("| dataset | natural/clean | injected | removed as prior dup | medical trajectories removed (n / tokens) |\n|---|---|---|---|---|")
for k in ["AgentRx/magentic", "AgentRx/tau_retail", "TRAIL/gaia", "TRAIL/swe_bench"]:
    v = g["all"]["per_dataset"].get(k, dict(natural_or_clean=0, injected=0)); me = g["medical_excluded_trajectories"].get(k, {})
    pr = S[k]["overall"]["dedup_tokens_also_in_prior_sets"]
    L.append(f"| {k} | {M(v['natural_or_clean'])} | {M(v['injected'])} | {M(pr)} | {me.get('n',0)} / {M(me.get('tokens',0))} |")
L.append("\nRemoved-as-duplicate tokens by first matching prior set (all scope): " + ", ".join(f"{k} {v:,}" for k, v in sorted(g["all"]["excluded_by_prior_set_first_match"].items(), key=lambda kv: -kv[1])) + ".\n")
L.append("Both datasets contain **no injected trajectories**, so column (b) is 0. Combined with round 53 (77.88M all / 70.46M MAS-only new tokens over the old 5), the r55 sets add " + f"{M(g['all']['total'])} (all) / {M(g['mas_only']['total'])} (MAS only)" + " on top; the r55 dedup was run against the r53 sets as well, so the figures are additive.\n")

def table(title, d, cols=("n", "tokens_total", "tokens_global_exact_dedup", "p50", "p90", "n_gt_8k", "n_gt_32k")):
    L.append(f"#### {title}\n"); L.append("| group | " + " | ".join(cols) + " | share |"); L.append("|---|" + "---|" * (len(cols) + 1))
    tot = sum(v["tokens_total"] for v in d.values()) or 1
    for k, v in d.items(): L.append(f"| {k} | " + " | ".join(str(v[c]) for c in cols) + f" | {v['tokens_total']/tot*100:.1f}% |")
    L.append("")
def xo(name):
    c = S["cross_dataset_question_overlap"]["per_dataset"][name]
    items = list(c["overlaps"].items())
    return f"Cross-dataset question overlap ({c['n_questions']} distinct questions): " + (", ".join(f"{k} exact {v['exact']} / first-60 {v['first60']}" for k, v in items[:7]) if items else "none") + "."

L.append("## Per-dataset notes\n")
ax = S["AgentRx"]; o = OV["per_dataset"]
L.append("### 1. microsoft/AgentRx\n")
L.append(f"- License CC-BY-4.0 (card and README); gated=auto. Downloaded with the user's read token: {S['download_log_summary']['per_repo']['microsoft/AgentRx']['files']} files, {S['download_log_summary']['per_repo']['microsoft/AgentRx']['mb']} MB, no 403. Paper: Barke et al. 2026, arXiv 2602.02475.")
L.append(f"- Config `trajectories`: magentic_dataset.jsonl ({ax['labels']['magentic_traj']} trajectories) and tau_retail_dataset.jsonl ({ax['labels']['tau_traj']}); config `default` = label files magentic_one.jsonl ({ax['labels']['magentic_with_label']} labelled trajectories) and tau_retail.jsonl ({ax['labels']['tau_with_label']}). {ax['labels']['failures_total']} annotated failures. Labels: per-failure step_number + failure_category + failed_agent + free-text reasons, plus a designated root-cause failure (agent + step + category). **Only 44 of the 58 magentic trajectories have labels**; all 29 tau trajectories do.")
mv = ax["magentic_vs_WhoWhen_HandCrafted"]
L.append(f"- **Natural failures** (all trajectories are failed runs; no injection, no clean subset).")
L.append(f"- **The magentic split is Who&When Hand-Crafted re-packaged**: {mv['agentrx_magentic']} trajectories vs {mv['ww_hc_rows']} W&W Hand-Crafted rows; {mv['substeps_exact_in_ww_hc_messages']} / {mv['substeps']} substep texts occur verbatim among W&W Hand-Crafted message contents, {mv['trajectories_fully_contained']} / {mv['agentrx_magentic']} trajectories fully contained; {mv['instruction_exact_in_ww_hc']} instructions match a W&W Hand-Crafted question exactly. Consequently it contributes 0 new tokens (its 1.01M dedup tokens are all already in Who&When). Its new value is only the re-annotation (multiple failures per trace with categories, root cause) on top of W&W's single mistake_agent/mistake_step.")
L.append("- tau_retail: **single agent** (role assistant with tool calls) talking to an LLM-simulated user (role user) under a retail policy (role system, identical in all 29 traces, so global dedup removes 28 copies); assistant tool calls are JSON lists, only argument values are counted; tool results are JSON product/order records. Multi-agent only in the sense of agent + user simulator.")
L.append(f"- Agents seen (trajectories containing the role): magentic {ax['agents_per_split']['magentic']}; tau_retail {ax['agents_per_split']['tau_retail']}.")
L.append(f"- Medical-flagged trajectories: {ax['medical']['n']} ({M(ax['medical']['tokens'])}).")
L.append(f"- MAA overlap: {o['AgentRx']['exact_question_matches']} exact normalized question matches ({o['AgentRx']['rows_questions_checked']} questions); first-60-char probes: {o['AgentRx']['probe_hits']} / {o['AgentRx']['probes']} hits over {o['AgentRx']['chars_searched']/1e6:.0f}M normalized chars; planted control found = {o['AgentRx']['planted_control_found']}.")
L.append("- " + xo("AgentRx/magentic") + " (AgentRx/tau_retail: none.)\n")
table("AgentRx by split", ax["by_split"])
table("AgentRx magentic by token part", {k: dict(n="-", tokens_total=v, tokens_global_exact_dedup="-", p50="-", p90="-", n_gt_8k="-", n_gt_32k="-") for k, v in S["AgentRx/magentic"]["overall"]["tokens_by_part"].items()})
table("AgentRx tau_retail by token part", {k: dict(n="-", tokens_total=v, tokens_global_exact_dedup="-", p50="-", p90="-", n_gt_8k="-", n_gt_32k="-") for k, v in S["AgentRx/tau_retail"]["overall"]["tokens_by_part"].items()})

t = S["TRAIL"]; lb = t["labels"]
L.append("### 2. PatronusAI/TRAIL\n")
L.append(f"- License MIT (card); gated=auto with extra terms: do not reshare outside a gated or private HF repository. **The card's 'Out-of-Scope Use' says it must not be used for training systems intended to automate human evaluation; evaluation and benchmarking only.** This restricts TRAIL to evaluation in MedHyperTrace. Downloaded {S['download_log_summary']['per_repo']['PatronusAI/TRAIL']['files']} files, {S['download_log_summary']['per_repo']['PatronusAI/TRAIL']['mb']} MB, no 403.")
L.append("- Files: data/gaia-*.parquet (117 rows) + data/swe_bench-*.parquet (31 rows), columns `trace` (OpenTelemetry/OpenInference span tree as JSON string) and `labels`; the per-trace JSON files under GAIA/ and SWE Bench/ are byte-for-byte the same traces (all 148 parsed objects identical), processed_annotations_* = labels. One labels string has a trailing comma (parsed after removing it). The card says 118 GAIA / 30 SWE-bench traces; the files hold 117 / 31.")
L.append(f"- Labels: {lb['errors_total']} span-level errors (span id + category + evidence + description + impact {lb['impacts']}) in {lb['traces_with_errors']} of 148 traces, plus trace-level scores (reliability, security, instruction adherence, plan optimality). No responsible-agent field: the agent is only implied by the span. Top categories: {', '.join(f'{k} {v}' for k, v in list(lb['top_categories'].items())[:8])}. The 4 traces without any annotated error are classed `no_annotated_error` (credited to natural/clean).")
L.append("- **Natural runs** (no injection; for SWE-bench the card says 'added instructional constraints to organically introduce errors', i.e. prompted, not injected into the trace). GAIA: HF OpenDeepResearch (smolagents CodeAgent manager with a managed ToolCallingAgent `search_agent`), o3-mini. SWE-bench Lite: single smolagents CodeAgent, claude-3-7-sonnet.")
L.append(f"- **Single- vs multi-agent**: SWE-bench traces are single-agent. GAIA traces are configured as manager + search_agent, but the search_agent actually ran in only {lb['gaia_traces_where_search_agent_ran']} of 117 traces; the others are effectively single-agent. Hence the 'strict' MAS-only row above.")
L.append("- Extraction: every LLM input message (system / user / assistant / tool-response; tool-call messages reduced to their argument values) + LLM output content and tool-call argument values + TOOL span argument values and outputs + CHAIN step outputs + AGENT task and output + exception messages. Output-side segments whose text already occurs inside an input message of the same trace are dropped (" + f"{t['parse_stats']['output_segments_contained_in_inputs']:,} dropped, {t['parse_stats']['output_segments_kept']:,} kept" + "), then within-trace unique. Excluded: span metadata, tool JSON schemas/descriptions, invocation parameters, OTel `logs` (function arguments/outputs of main/get_examples_to_answer, which include the GAIA gold answer and annotator metadata), stack traces, labels and scores. The system prompts (CodeAgent instructions, ~1.6M GAIA + 0.9M SWE-bench tokens raw) are part of the trajectory and counted. SWE-bench has a single distinct system prompt (431 occurrences), which the within-trace and global dedup collapse to one copy; GAIA has 293 distinct system messages over 1,154 occurrences (many embed the task or the agent memory, e.g. the final 'Earlier you were asked ...' call), so dedup removes only part of them (GAIA global dedup 2.54M -> 2.45M). processed_annotations_* files equal the `labels` column for 148/148 traces.")
L.append("- Cross-check: a simpler rule (unique LLM input/output message strings per trace, tool-call messages kept as raw text) gives 3.64M vs 3.40M here.")
L.append(f"- Unique questions: GAIA {S['TRAIL/gaia']['unique_questions']} for 117 traces; SWE-bench {S['TRAIL/swe_bench']['unique_questions']} issues for 31 traces (1 trace has no AGENT span; its task is still counted via the LLM input messages). SWE-bench repos: sqlfluff 13, astroid 5, pydicom 5, pvlib 4, marshmallow 2, pyvista 1.")
L.append(f"- Medical-flagged trajectories: {t['medical']['n']} ({M(t['medical']['tokens'])}).")
L.append(f"- MAA overlap: {o['TRAIL']['exact_question_matches']} exact normalized question matches ({o['TRAIL']['rows_questions_checked']} questions); first-60-char probes: {o['TRAIL']['probe_hits']} / {o['TRAIL']['probes']} hits over {o['TRAIL']['chars_searched']/1e6:.0f}M normalized chars (full raw trace + labels); planted control found = {o['TRAIL']['planted_control_found']}.")
L.append("- " + xo("TRAIL/gaia") + " Same GAIA questions as the prior sets, but different runs (OpenDeepResearch / o3-mini): only " + f"{S['TRAIL/gaia']['overall']['dedup_tokens_also_in_prior_sets']}" + " of its dedup tokens are exact segments of a prior set. TRAIL/swe_bench: no question overlap.\n")
table("TRAIL by split", t["by_split"])
table("TRAIL by class", t["by_class"])
table("TRAIL GAIA by token part (raw, before within-trace dedup)", {k: dict(n="-", tokens_total=v, tokens_global_exact_dedup="-", p50="-", p90="-", n_gt_8k="-", n_gt_32k="-") for k, v in S["TRAIL/gaia"]["overall"]["tokens_by_part"].items()})
table("TRAIL SWE-bench by token part (raw, before within-trace dedup)", {k: dict(n="-", tokens_total=v, tokens_global_exact_dedup="-", p50="-", p90="-", n_gt_8k="-", n_gt_32k="-") for k, v in S["TRAIL/swe_bench"]["overall"]["tokens_by_part"].items()})

L.append("## Overlap with the MAA medical corpus\n")
L.append(f"MAA: {OV['maa_unique_queries']} unique normalized queries; {OV['probes']} first-60-char probes (queries >= 40 chars). MAA rebuilt from the public repo GuihaiChen1998/nature-sub-record (anonymous clone, GIT_LFS_SKIP_SMUDGE=1; 'MedAgentAudit-datasets_and_logs-9.2 - 1.zip.00{{1,2,3}}' cat-merged, unzipped twice, converted with data_tools.maa_to_mas_traj: 14,370 rows, same as r51/r53). Searched text = every string value of every row (JSON-in-string parsed), normalized.\n")
L.append("| dataset | questions checked | exact matches | probe hits | chars searched | planted control |\n|---|---|---|---|---|---|")
for k, v in o.items(): L.append(f"| {k} | {v['rows_questions_checked']} | {v['exact_question_matches']} | {v['probe_hits']} | {v['chars_searched']/1e6:.0f}M | {v['planted_control_found']} |")
L.append("")
L.append("## Downloads\n")
dl = S["download_log_summary"]
L.append(f"Local sandbox, HF direct, read token from file (never printed or stored): {dl['files_ok']} files OK ({dl['mb']} MB), {len(dl['failed'])} failed. microsoft/AgentRx {dl['per_repo']['microsoft/AgentRx']}, PatronusAI/TRAIL {dl['per_repo']['PatronusAI/TRAIL']}. Prior sets re-downloaded unauthenticated with download.py (old 5, incl. the 3.5 GB tmpxv7 tarball, extracted with extract_wwp.py) and download_r53.py (r53 sets) because the sandbox had been reset.\n")
open(f"{D}/stats_r55.md", "w").write("\n".join(L))
print("wrote", f"{D}/stats_r55.md", f"{D}/stats_r55.json")
