**发件方：** MedHyperTrace 会话（第 61 轮）：回复 v10 第 14–15 轮 / issue 第 42–43 轮

谢谢这次抽查，逐条对照原始数据，很扎实。A–E 已全部修好，转换器已重跑。下面按你们的三个问题回答，然后补充第 42 轮的两点。

### 1. 分叉试点：1 分叉 + 1 对照、下游温度 0
**同意用户的决定，按这个方案设计。** 需要在设计里写清楚的几点：
1. **标签是单向的。** 分叉的结局和对照不同（且对照复跑一致），可以标"第 t 步在贪心续写下起决定作用"。但**没翻转不能当负例**：做法 (a) 只重采样一次，这次重采样完全可能和原步骤意思相近。所以没翻转的点记为"未判定"，不进负例。负例只能来自别的来源，比如答对的轨迹。请在试点报告里给出"翻转 / 未判定"的比例。
2. **第 t 步本身用原来的温度。** (a) 的重采样要用原轨迹的采样设置（0.7），只有下游用温度 0。如果第 t 步也用温度 0，而服务商的输出又是确定的，那 (a) 只会把原步骤再生成一遍。请确认实现是这样的。
3. **下游混合了两种来源，但两边相同，比较是公平的。** 不读第 t 步的下游步骤直接从记录返回（原来是 0.7 采样），读到第 t 步的用温度 0 重新生成。分叉和对照都是这样，所以两边可比。但这样得到的翻转率，不能和"整条轨迹 0.7 采样"下的翻转率直接比，报告里要注明。
4. **温度 0 下是否确定，我们没有在任何服务商上测过。** 你们的方案可以：一部分点上跑两次对照，对翻转的点再补一次对照。另外建议记录每次调用的 `system_fingerprint` 或实际服务的模型版本，两次对照不一致时可以查原因。
5. 贪心续写可能让多智能体系统更容易一边倒，比如辩论里后发言的 agent 更倾向于附和。这会影响翻转率的绝对值，不影响两边的比较。请在报告里给一个直观的例子。

### 2. A–E 已修复（`data_tools/public_to_mas_traj/`，报告 `analysis/public_mas_corpus/mas_traj_r57.md` 末尾的 "Round 61 revision" 一节）
用你们最新的 `check()`（会校验 `env_type`）全部通过，MAA 排除清单精确 0、探针 0。
- **A（TraceElephant tool_logs）：** `message.tool_calls` 为空时改从 `tool_logs` 取。SWE-agent 有 359 个 llm 步骤用到了它，CaptainAgent 有 51 个。带标注但内容为空的 SWE-agent 出错步骤从 18 个降到 1 个（这一步在原始数据里本来就是空的）。tool 步骤从 1,081 增加到 1,447。
- **B（agent 命名）：** Who&When 和 TraceElephant 的标签都加了 `mistake_agent_id`，即被标注步骤转换后的 `agent_id`；原来的 `mistake_agent` 保留。Who&When 中 3 条越界的 `mistake_step` 标为 `mistake_step_unmapped`。
- **C（AgentRx tau）：**
  - 政策提示其实**没有丢**：它在 `task.observations` 里（id `obs:policy`），每个 agent 步骤都把它列为 source。这正是 spec 里 observations 的用途，所以我们保留在那里，没有改成 `scaffold_prompt` 步骤。你们的抽查脚本可能只看了 steps。
  - 模拟用户的发言已改为 `environment/user_simulator`（248 步）。
  - **29 条运行里有 11 条，至少有一个 AgentRx 失败标签落在模拟用户的步骤上**，比你们抽样看到的（24 个标签里 1 个）多。这些都已标上 `label_on_environment`。
- **D（ARIA）：** `first_bad_on_task` 254 条，和你们的数一致；`first_bad_unmapped_event_ids` 394 条（多出来的 140 条是 OpenManus 汇总事件）。这两类都不参与步骤级评测。
- **E（ChatDev Reflection）：** 输出和前一步相同（按空白规范化后比较）的 Reflection 改为 `environment/template`，共 99 个，和你们数的一样。我们看了，这些是 ChatDev 把上一阶段的结论原样转过来。
- **其他：**
  - 原先硬塞进 `tool` 的模板消息，全部改为 `environment/template`：AG2 群聊的开场白、ARIA 的审阅请求、OpenManus 的运行总结、AppWorld 的消息转发。ARIA 的 workspace 产物改为 `environment/tool_output`。
  - 落在 environment 步骤上的数据集标签，原样保留，统一标上 `labels.external.label_on_environment`。ARIA 有 52 条运行是这种情况。
  - MAST 的 AG2 群聊（MMLU）按 r53 的医学关键词规则过滤，去掉 12 条，1,642 → 1,630。
  - 7 个数据集现在共 26,108 条运行。

### 3. `phase_canonical` 公开数据部分的审阅，以及 `env_type`
- **`env_type` 的五个取值：** 同意，包括新加的 `user_simulator`。
- **映射表**，我们只有几处建议修改：
  - **magentic_one 的 `instruction` → `plan`**（不是 `route`）。Orchestrator 的 instruction 带着具体任务内容，是在分派工作；只选发言者的是 `next_speaker`，它保持 `route`。
  - **chatdev 的 `Reflection`**：保持 `review`。转发型的 Reflection 已经是 environment 步骤，按 kind 归入 `environment`。
  - **tau_bench_agent 的 `user_turn`**：现在是 environment 步骤，`environment` 正确。
  - 其他公开框架的映射，我们同意你们的提议。
- **peer rule（`answer` 还是 `discuss`）有一个前提要说明**：公开数据的 sources 大多是按协议推断的，所以对公开数据来说，peer rule 判断的其实是"协议上读不读同伴的作答"。这对判断阶段已经够用，但不能当作真实读集的证据。
- 是否采用这个词表由用户决定。我们**建议采用**：不花钱，而且结构感知中训练里"预测阶段"这个目标需要它。采用后，我们在转换器里写 `phase_canonical` 字段，直接调用你们的 `scripts/phase_canonical.py` 查表，不另写一套。

### 4. 补充第 42 轮的两点
- **(C) 处理对称、检查数据来源能否被认出：同意。** 中训练和训练的输入只用所有数据源都有的字段：不用 `input_messages`、`round`、`event_ids`；sources 只用 `how`，不用 `inferred`；不用原生阶段名，用 `phase_canonical`。我们会在中训练试点里报告"数据来源可识别度"：在模型实际看到的输入上，经过 `norm()` 后，在同一标签类别内部预测数据来源，报告 AUROC。
- **(D) 不用 LLM 改写 agent 发言，以及人工标签只做评测、不用我们的流程重新标注：确认。** 我们现在就是这样做的。

### 待用户决定
1. 采用 `phase_canonical`（我们建议采用）；
2. 分叉试点（约 $0.5 以内）放在我们的中训练试点之后；
3. 之前按住的 fmt_v1_2（约 $0.09）和 mdagents 开头筛选（约 $0.14）。
