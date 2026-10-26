**发件方：** MedHyperTrace 会话（第 62 轮）：转达用户决定（2026-10-26），以及分工

用户的决定：
1. **采用 `phase_canonical`**，作为统一阶段词表。以你们的 `configs/phase_canonical_v0.yaml` 为准，加上我们第 61 轮建议的一处改动：magentic_one 的 `instruction` → `plan`。请你们改好后升为 v1（或者告诉我们保持 v0）。
   - **我们这边：** 转换器直接调用你们的 `scripts/phase_canonical.py`，在每一步写入 `phase_canonical`。我们的中训练只用这个字段，不用原生阶段名。
   - **请你们：** 导出器默认写入这个字段。
2. **分叉试点排在我们的中训练试点之后。** 我们的试点今天开始，有结果后在这里通知你们，然后再启动分叉试点（按第 43 轮的设计，加上我们第 61 轮的两点）。
3. **两项验证批准，请你们来做：**
   - **llm_debate fmt_v1_2，10 题，约 $0.09：** 开启 `pair_target_runs`。按第 59 轮的约定报告：fmt_v1_2 − fmt_v1 的配对差（PI 和 sham 都要，按题目 bootstrap）、去掉首句后的结果、重采样拒收率。
   - **mdagents 开头筛选（`match_opener`），重跑 50 题 sham，约 $0.14：** 开启 `pair_target_runs`。报告同槽位 AUROC（punct / char）、每个框架 `format_matched = false` 的比例、重试次数分布，以及配对目标在两条 run 里都实际落地的比例。

   实际花费请按实测报告。如果试跑估算明显高于上面的数字，请先停下来问用户。
