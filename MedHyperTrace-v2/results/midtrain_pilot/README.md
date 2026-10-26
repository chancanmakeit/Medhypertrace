# Mid-training pilot v1: text TAPT (round 62) — IN PROGRESS

**Question:** does continued pre-training (task-adaptive, LoRA) of Qwen3-8B on unlabelled multi-agent trajectories improve
MedAgentAudit (MAA) defect-layer attribution after the usual SFT? (Taxonomy: MedAgentAudit only for the evaluation.)

**Corpus** (`hgfm/midtrain/build_corpus.py`; stats `corpus_stats_tapt_pilot_v1.json`): 24.46M Qwen3 tokens, 16,271 chunks
(<= 4,096 tokens, split at step boundaries, task header repeated), 12,874 runs:
ARIA 10.0M (capped; 9,024 runs), MAST-Data 8.0M, medical-aegis anchor normal runs 3.7M (llm_debate, mdagents,
medagents_mc), AFTraj 1.1M, MAScope 0.8M, TraceElephant (SWE-agent) 0.7M, AgentRx tau 0.2M.
* **No MAA data**, so one mid-training run serves every MAA split; 18 anchor runs on the 2 MAA-overlapping questions removed
  (MAA exclusion list v1).
* **framework_family `groupchat` excluded** (Magentic-One, CaptainAgent, AG2 group chat, AFTraj expert team, MAScope AutoGen,
  anchor MAC): MAA's MAC is an AutoGen-GroupChat design, so LQD_mac stays zero-shot at the architecture level.
* Serialisation uses only fields every source has: task, `[s<k>] <agent_role> | <phase_canonical>` + output; environment /
  tool outputs truncated to 2,000 chars (head + tail) for every source; llm outputs never shortened.
* Transfer: private HF dataset `UUUooUUU/mht-midtrain-pilot` (file `tapt_pilot_v1_train.jsonl.gz`, md5 3a3ef54f…).

**TAPT** (`scripts/linux2_run_tapt.sh`): LoRA r 64 / α 128 on all linear layers, lr 1e-4 cosine (3% warm-up), 1 epoch,
4 GPUs × batch 1 × accum 8 (32 chunks / step, ~508 steps), max_length 4,096, sdpa (no packing: flash-attn not installed;
batch 1 means no padding), 0.5% held-out for eval loss. Smoke: 14.7 s/step, 31 GB. Then LoRA merged into the weights
(`Qwen3-8B-tapt_pilot_v1`).

**Evaluation** (`scripts/linux2_midtrain_chain_sft.sh`): the standard MS-Swift graph / text SFT on the merged model, QD and
LQD_mac, seeds 0 and 1; compared with the base-model MS-Swift seed study (`../c6_linux2_lora/seed_study.md`, 3 seeds).
