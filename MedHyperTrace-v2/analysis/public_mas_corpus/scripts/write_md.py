import json
S=json.load(open("stats.json"))
S["download_linux2_speed_sample"]=dict(proxy="http://127.0.0.1:23333",method="hf_hub_download, refs/convert/parquet",
  samples=[dict(file="Who_and_When Algorithm-Generated parquet",mb=0.63,sec=23,kbps=28),dict(file="Who_and_When Hand-Crafted parquet",mb=1.27,sec=28,kbps=46),
           dict(file="AEGIS test parquet",mb=4.69,sec=59,kbps=80),dict(file="AEGIS validation parquet",mb=13.24,sec=176,kbps=75)],
  note="AEGIS train (52.5MB) download started then deliberately killed per scope change; partial files removed. Files left on Linux #2: /data1/ekyang/cgh/CODE/mht_work/public_mas/raw (W&W x2, AEGIS test+validation parquet, 20MB)")
S["TRAIL"]=dict(status="gated (gated=auto) - requires user to accept terms on HF; not downloaded, not measured")
S["overlap_vs_MAA"]["bruteforce_crosscheck"]="first 60 normalized chars of each of 554 MAA queries (>=40 chars) substring-searched in full normalized text of every dataset (incl. raw JSON): 0 hits in all 5; planted positive control found"
json.dump(S,open("stats.json","w"),indent=1,ensure_ascii=False)
def M(x): return f"{x/1e6:.2f}M" if x is not None else "not measured"
L=[]
L.append("# Public MAS failure-attribution datasets: trajectory-text token stats\n")
L.append("Tokenizer: Qwen/Qwen3-8B (add_special_tokens=False). Only natural-language trajectory content is counted (task question, message/step contents, final output, tool-call argument *values*); JSON keys, labels, annotations, injection metadata excluded. Generated 2026-10-22 in the local sandbox (/home/claude/public_mas).\n")
L.append("## Summary\n")
L.append("| Dataset | Trajectories | Steps (total / p50) | Total tokens | Global exact-dedup tokens | p50 / p90 / p99 / max per traj | >8K / >32K | Top benchmarks (token share) |")
L.append("|---|---|---|---|---|---|---|---|")
def row(name,o,bench):
    tot=o["tokens_total"]; tb=", ".join(f"{k} {v['tokens_total']/tot*100:.0f}%" for k,v in list(bench.items())[:4])
    st=f"{o['steps_total']} / {o['steps_p50']}" if o["steps_total"] is not None else "not measured"
    L.append(f"| {name} | {o['n']} | {st} | {M(tot)} | {M(o['tokens_global_exact_dedup'])} | {o['p50']} / {o['p90']} / {o['p99']} / {o['max']} | {o['n_gt_8k']} / {o['n_gt_32k']} | {tb} |")
row("AEGIS (all injected)",S["AEGIS"]["overall"],S["AEGIS"]["by_benchmark"])
row("MAST-Data",S["MAST"]["overall"],S["MAST"]["by_benchmark"])
row("Who&When",S["Who&When"]["overall"],S["Who&When"]["by_benchmark"])
row("TraceElephant",S["TraceElephant"]["overall"],S["TraceElephant"]["by_benchmark"])
w=S["Who&When-Pro"]
row("Who&When-Pro (text, real files only)",w["text_modality"],w["text_by_benchmark_framework"])
L.append("| PatronusAI/TRAIL | gated - not downloaded | not measured | not measured | not measured | not measured | not measured | needs user to accept HF terms |\n")
L.append("Total tokens = sum over trajectories as stored, except TraceElephant, where per-step inputs repeat the cumulative context: there it is the unique message texts within each trace (raw as stored: %s). Global exact-dedup = unique segment texts across the whole dataset (segment = turn/message; MAST = blank-line paragraph of the raw log).\n" % M(S["TraceElephant"]["overall"]["tokens_raw_as_stored"]))
def table(title,d,cols=("n","tokens_total","p50","p90","n_gt_8k","n_gt_32k")):
    L.append(f"### {title}\n"); L.append("| group | "+" | ".join(cols)+" | share |"); L.append("|---|"+"---|"*(len(cols)+1))
    tot=sum(v["tokens_total"] for v in d.values())
    for k,v in d.items(): L.append(f"| {k} | "+" | ".join(str(v[c]) for c in cols)+f" | {v['tokens_total']/tot*100:.1f}% |")
    L.append("")
L.append("## AEGIS (Fancylalala/AEGIS, parquet export)\n")
a=S["AEGIS"]; o=a["overall"]
L.append(f"- Clean (no injection) runs: **0**. Injected runs: **{o['n']}** (every row has num_injected_agents>=1, injected_agents non-empty, is_injection_successful=True). There is no clean subset to separate.")
L.append(f"- Token parts: task {M(o['tokens_by_part']['task'])}, normal turns {M(o['tokens_by_part']['turn'])}, turns flagged is_injected {M(o['tokens_by_part']['injected_turn'])}, final_output {M(o['tokens_by_part']['final'])}. Note: response_corruption injections also alter un-flagged downstream turns; only explicitly flagged turns can be separated.")
L.append(f"- Unique task queries: {a['unique_queries']} across {o['n']} rows (heavy question reuse). Models per metadata: gpt-4o-mini 9,260, unknown-model 273 (magentic_one).\n")
table("AEGIS by split",a["by_split"]); table("AEGIS by framework",a["by_framework"]); table("AEGIS by benchmark",a["by_benchmark"]); table("AEGIS by domain",a["by_domain"])
L.append("## MAST-Data (mcemri/MAST-Data, parquet export)\n")
m=S["MAST"]
L.append(f"- Each trace is a raw framework log string (timestamps, config paths, pip/docker output included). Steps are not uniformly parseable: **not measured**. Paragraph-level exact dedup cuts {M(m['overall']['tokens_total'])} to {M(m['overall']['tokens_global_exact_dedup'])} (ChatDev logs repeat prompts heavily).")
L.append(f"- ChatDev alone is {m['by_framework']['ChatDev']['tokens_total']/m['overall']['tokens_total']*100:.0f}% of tokens. Question extracted (for exact overlap) for {m['question_extracted']}/{m['overall']['n']} traces; full-text containment check covers all.\n")
table("MAST by framework",m["by_framework"]); table("MAST by benchmark",m["by_benchmark"]); table("MAST by domain",m["by_domain"])
L.append("## Who&When (Kevin355/Who_and_When)\n")
L.append("- Benchmark inferred from question_ID format (UUID = GAIA, 64-hex = AssistantBench). Hand-Crafted = Magentic-One logs; Algorithm-Generated = CaptainAgent.\n")
table("Who&When by config",S["Who&When"]["by_config"]); table("Who&When by benchmark",S["Who&When"]["by_benchmark"])
L.append("## TraceElephant (TraceElephant/TraceElephant, data.zip 596.6 MB)\n")
t=S["TraceElephant"]
L.append("- Archive: 2,827 entries = 2,070 PNG (578.7 MB, screenshots under magentic-runs-*/<run>/images/) + 440 JSON (252.2 MB) + 317 dirs. 220 traces, each = step_records.json + trace_metadata.json.")
L.append("- What it is: a failure-attribution set with *full LLM-call records* per step (input messages, output, tool calls, token usage) and per-trace labels mistake_agent / mistake_step / mistake_reason (+ SWE-bench test status). Subsets: captain-agent on GAIA (73) / AssistantBench (12), Magentic-One on GAIA (74) / AssistantBench (17), SWE-agent on SWE-bench (44); model gpt-4o. 135 of its 176 GAIA/AssistantBench traces contain a Who&When question (first 80 normalized chars), so it is largely a full-context re-run of Who&When tasks (same question pool; do not count both as independent tasks).")
L.append(f"- Images inside input messages: {t['images_in_inputs']} (not tokenized). Raw-as-stored tokens {M(t['overall']['tokens_raw_as_stored'])} vs within-trace unique {M(t['overall']['tokens_total'])}.\n")
table("TraceElephant by framework",t["by_framework"]); table("TraceElephant by benchmark",t["by_benchmark"])
L.append("## Who&When-Pro (tmpxv7/who-when-pro, data_release.tar.gz 3.50 GB, sha256 verified)\n")
L.append(f"- **The release is largely broken**: of {w['n_traces_listed']} trace JSON entries, {w['archive_inventory'].get('text/symlink',0)+w['archive_inventory'].get('image/symlink',0)} are relative symlinks pointing outside the archive (../../../../mmagent/..., ../../../../PixelCraft/...) - dangling, no content. All 3,899 image-modality traces and 5,946 of 6,257 text traces are dangling. Real files: 311 text traces (alfworld/alfagent only) + 916 video traces (lvbench: dvd 168, eva 748) + 21,851 video frames (10,991 jpg / 655 MB, 10,860 png / 2.95 GB; counted while streaming, never extracted to disk). Repo history has no other data copy (earlier commit only has eval code).")
L.append("- Dangling text traces by benchmark/framework: " + ", ".join(f"{k.split('/',1)[1]}={v}" for k,v in w["dangling_by_modality_benchmark_framework"].items() if k.startswith("text/")))
L.append("- Dangling image traces: " + ", ".join(f"{k.split('/',1)[1]}={v}" for k,v in w["dangling_by_modality_benchmark_framework"].items() if k.startswith("image/")) + "\n")
p=w["text_prefix_injected_post"]
L.append("### Text modality (311 real alfworld/alfagent traces, 135 distinct task+split keys)\n")
L.append(f"| part | tokens |\n|---|---|\n| pre-injection prefix (turns with step < gt.step, incl. task prompt) | {p['prefix']:,} |\n| injected step (step == gt.step) | {p['injected_step']:,} |\n| post-injection turns | {p['post']:,} |\n| total | {p['prefix']+p['injected_step']+p['post']:,} |\n| **prefix deduplicated by (task, exact turn text)** | **{p['prefix_dedup_by_task_exact_turn']:,}** |\n| all turns deduplicated by (task, exact turn text) | {p['all_turns_dedup_by_task_exact_turn']:,} |\n")
v=w["video_prefix_injected_post"]
L.append(f"Video (counts requested; text tokens reported only as extra): 916 traces, text-in-JSON {M(w['video_json_extra_text_tokens']['tokens_total'])} (prefix {v['prefix']:,} / injected {v['injected_step']:,} / post {v['post']:,}; prefix dedup {v['prefix_dedup_by_task_exact_turn']:,}). Image modality: 3,899 listed, 0 readable.\n")
L.append("## Overlap with MAA medical corpus\n")
ov=S["overlap_vs_MAA"]
L.append(f"MAA: {ov['maa_rows']} rows, {ov['maa_unique_queries']} unique normalized task.query ({ov['maa_queries_ge12_words']} with >=12 words). Local copy /home/claude/data_maa_v2/maa_mas_traj.jsonl (same 14,370 lines as Linux #2 file).\n")
L.append("| dataset | questions checked | exact matches | MAA queries contained in any segment | trajectories containing one |\n|---|---|---|---|---|")
for k,x in ov["per_dataset"].items(): L.append(f"| {k} | {x['questions_checked']} | {x['exact_question_matches']} | {x['maa_queries_contained_in_any_segment']} | {x['trajectories_containing_a_maa_query']} |")
L.append(f"\nCross-check: {ov['bruteforce_crosscheck']}.\n")
L.append("## Downloads\n")
L.append("Local sandbox (HF direct): all files OK first attempt - parquets 0.3-150 MB/s, TraceElephant data.zip 596.6 MB in 7.2 s (83 MB/s), who-when-pro tar.gz 3.50 GB in 12.3 s (284 MB/s).\n")
L.append("Linux #2 via proxy 127.0.0.1:23333 (speed sample only): W&W parquets 28 / 46 KB/s, AEGIS test 4.7 MB in 59 s (80 KB/s), AEGIS validation 13.2 MB in 176 s (75 KB/s). At ~75 KB/s: all parquets (~263 MB) ~1 h, TraceElephant zip ~2.2 h, who-when-pro tar.gz ~13 h (and ~85% of it is video frames). Recommendation: transfer extracted text (JSONL, tens of MB) from the sandbox instead.\n")
L.append("TRAIL (PatronusAI/TRAIL): gated=auto, requires accepting terms on HF with the user's account; not attempted.\n")
open("stats.md","w").write("\n".join(L))
