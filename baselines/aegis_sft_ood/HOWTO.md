# AEGIS-SFT 基线 — 运行说明（在你的 GPU 机器上）

## 已确认的事实（来自你的仓库 aegis_common.py + train.parquet）
- **训练用直接 JSON，不是 CoT**。SFT target 100% 是单行
  `{"faulty_agents":[{"agent_name","error_type"}]}`（7146/7146 条）。
  → 评测**不要**加 `--use_cot`。
- 任务是**多标签 (agent,error) 对**，**不预测 step**。所以此基线只在
  Agent / Error / Pair 三级 Micro/Macro-F1 上比，step-level 不适用（设计如此）。
- 你的模型在 `outputs/global_step_110/huggingface_merged`。

## 关键区别（务必知道）
你的 SFT 是在**通用 AEGIS 数据**上训的，现在测**医学数据** = OOD 迁移基线。
这正是我们要的对照：一个通用失败归因模型迁移到医学 MAS 上表现如何。

## 步骤
1. 用桥接脚本把我们的医学数据转成你 evaluate-v3.py 的输入格式（已在本目录附上
   转好的样本 `aegis_sft_eval_samples/med_*.jsonl`，是**固定 test-set**版本）：
   ```
   # 若要自己重跑： python bridge_to_aegis_eval.py --out /tmp/med_eval --test_only --agent_key role
   ```
2. 在 AEGIS_Reproduce/ 里，用你训好的模型评测（不加 --use_cot）：
   ```
   python evaluate-v3.py \
       --model_path outputs/global_step_110/huggingface_merged \
       --bench_jsonl  aegis_sft_eval_samples/med_mdagents.jsonl \
       --whowhen_jsonl aegis_sft_eval_samples/med_llm_debate.jsonl \
       --output_dir outputs/med_eval_results --max_new_tokens 256
   ```
   evaluate-v3 一次吃两个 jsonl；三个框架可跑两次覆盖，或改脚本循环。
   它会用 aegis_common.compute_metrics 输出 Pair/Agent/Error 的 Micro/Macro-F1。
3. 把 outputs/med_eval_results 发我，我帮你和 HGNN 主方法整合成一张表。

## agent_key 选择
- 默认 `role`：责任 agent = 裸角色名（Expert/Aggregator...），与 SFT 在通用数据上
  训练时的命名习惯一致，最公平。
- `instance`：把复制角色区分成 "Expert 0/1/2"。仅当你想按实例评时用（会更难，
  因为 SFT 没见过这种命名）。

## 注意
- evaluate-v3 里 `sys.path.insert(0, ".../src")` 假设 aegis_common 在 src/ 下；
  你的仓库是平铺的，跑之前确认 import 路径能找到 aegis_common.py（必要时把
  evaluate-v3.py 顶部那句 sys.path 改成当前目录）。
