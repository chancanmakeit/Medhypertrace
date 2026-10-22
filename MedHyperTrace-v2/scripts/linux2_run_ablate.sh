#!/usr/bin/env bash
# round 54: graph-token ablation on GPU 0 for every fold whose graph ckpt + eval exist; QD waits for its eval json.
# Copy of /data1/ekyang/cgh/CODE/mht_work/run_ablate.sh on Linux #2 (run with setsid nohup; `smoke` = 6 prompts of LQD_mac).
export PATH=/data/ekyang/anaconda3/envs/sglang/bin:$PATH HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false
unset all_proxy ALL_PROXY http_proxy https_proxy
LM=/data1/ekyang/cgh/cache/huggingface_hub/hub/models--Qwen--Qwen3-8B; L=/data1/ekyang/cgh/CODE/mht_work/maa/llm; T=models--Qwen--Qwen3-8B
cd /data1/ekyang/cgh/CODE/Medhypertrace/MedHyperTrace-v2
if [ "$1" = smoke ]; then d=$L/LQD_mac
  CUDA_VISIBLE_DEVICES=0 python -m hgfm.llm.graph_ablation --lm $LM --ckpt $d/ckpt_${T}_graph --data $d/sft_graph/eval_human.jsonl --tokens $d/graph_tokens.pt --ref $d/eval_${T}_graph.json --out /data1/ekyang/cgh/CODE/mht_work/ablate_smoke.json --limit 6; exit; fi
for f in LQD_mac LQD_colacare LQD_healthcareagent LQD_medagent LQD_reconcile LQD_mdagents QD; do d=$L/$f
  while [ ! -s $d/eval_${T}_graph.json ]; do sleep 60; done
  [ -s $d/ablate_${T}_graph.json ] && continue
  echo "[$(date -u +%T)] START $f"
  CUDA_VISIBLE_DEVICES=0 python -m hgfm.llm.graph_ablation --lm $LM --ckpt $d/ckpt_${T}_graph --data $d/sft_graph/eval_human.jsonl --tokens $d/graph_tokens.pt --ref $d/eval_${T}_graph.json --out $d/ablate_${T}_graph.json
  echo "[$(date -u +%T)] DONE $f rc=$?"
done
python -m hgfm.llm.graph_ablation --pool $L --tag $T --out /data1/ekyang/cgh/CODE/mht_work/ablate_pooled_lqd.json
echo "[$(date -u +%T)] ALL DONE"
