**发件方:** MedHyperTrace 会话(方法侧,第 80 轮)。用户读到 Agent Data Protocol(ADP,ICLR 2026),认为它"用 schema 统一 agent 轨迹数据集"的思路可能对我们的多智能体轨迹有借鉴意义(中训练、后训练都算),请我们先给出看法,再请各方建言。
下面是我方读完全文后的看法。凡涉及我方数据和代码的,都对照实际文件核对过。

## 一、ADP 做了什么(我方转述)
- **schema:** 用 Pydantic 定义轻量 schema。`Trajectory` 由三部分组成:`id`;`content`(动作与观察交替的序列);`details`(自由元数据)。
  - 动作 3 类:API(函数名 + 参数 + 可选说明)、Code(语言 + 代码 + 可选说明)、Message(自然语言)。
  - 观察 2 类:Text(来源分 user / environment)、Web(html、axtree、url、视口、截图)。
- **流程分三段:** 原始数据 → ADP(每个数据集写一次转换器);ADP → SFT(每个 agent 框架写一次转换器);再加自动质检,包括工具调用格式、"思考"覆盖率、对话是否正常结束等。
- **工程论点:** 数据集到框架的转换工作量从 O(D×A) 降到 O(D+A)。论文给出 13 个数据集的转换器合计约 4.9k 行,3 个框架的转换器平均约 77 行。
- **规模与结果:** 13 个数据集,共 1.3M 条轨迹。用 Qwen2.5-Coder 做 SFT 后,SWE-Bench、WebArena、AgentBench OS、GAIA 平均比基座高约 20%。跨任务的混合训练优于只用单一数据集;附录 E.1 用"上采样到同样本数"的单数据集做了对照。
- **未来方向**(作者自述):多模态;把同样的"协议"思路用到评测和环境上;更强的自动校验。

## 二、我方已有的对应物:mas-traj/1,比 ADP 多出的是多智能体结构
medical-aegis 的 `scripts/export_schema_v1.py` 定义了 mas-traj/1,我方的公开数据转换器(`data_tools/public_to_mas_traj/`,7 个数据集,26,108 条运行)也输出这个格式。逐项对照:

| ADP | mas-traj/1 | 说明 |
|---|---|---|
| `Trajectory.id` | `run_id`,另有 `question_id`、`run_index`、`run_mode` | 我方能表达"同一题的第 k 次运行",以及 normal / 注入 |
| `content`:动作 / 观察交替 | `steps[]`,`kind` ∈ {llm, environment},外加 `env_type`(模板 / 工具输出 / 用户模拟器) | 大体对应 |
| 动作类型 API / Code / Message | llm 步的 `output` + `tool_calls` + `structured`(如选项答案) | **我方缺**:代码动作和自然语言消息没有显式类型 |
| 动作的 `description`(思考) | `provenance.reasoning_exported`(公开数据大多为 False) | **我方缺**:思考与动作没有分开 |
| — | `agent_id` / `agent_role` / `agent_label` / `phase` / `phase_canonical` / `round` | **ADP 没有**:单智能体,没有"谁在说话" |
| — | `sources[]`(读集:这一步读了哪些前序步;`how` = matched / protocol / control;`inferred` 标记) | **ADP 没有**,这是超图的基础。实测公开数据的来源 100% 是推断的,只有锚点是运行时记录的 |
| — | `framework` / `framework_family` / `framework_description` | 按框架族做留一评测要用 |
| `details`(自由字典) | `provenance{}` + `labels{}`(与 steps 分开:gold、is_correct、injection、outcome、external …) | 我方标签与轨迹分层更彻底 |
| Web 观察 | `task.images`、`task.observations` | 医学多模态(影像、音频)ADP 列为未来工作 |
| 自动质检 | `export_schema_v1.check()`、`check_trajectory_sources.py`、MAA 排除清单、外部评测去重 | 双方都有,侧重不同 |

**结论:** 单智能体轨迹可以无损地放进 mas-traj/1(1 个 agent + environment);反过来,把 mas-traj/1 转成 ADP 会丢掉 agent 身份和读集——也就是超图主线需要的全部结构。所以**不建议改用 ADP 作为我方的主格式**。值得借鉴的是它的工程分层和"协议化"做法,具体见下。

## 三、值得借鉴的四点(按我方判断的优先级)
### 1. "ADP → SFT"这一侧:我方现在有多种序列化方式,而且中训练和评测用的格式不一样
- 同一份 mas-traj 数据,我方实际至少有三种渲染:
  - TAPT / S / R / 阶段 0 的中训练语料(`build_corpus.py`):`Task (<数据集>, framework <f>):\n<题干>` + `[s<k>] <角色> | <phase>\n<输出>`;
  - OAT 读出和 E4 特征(OAT 的 `_build_input_text`):`Question: … Trajectory: [STEP t] [ROLE: r] [AGENT: a]\n…`;
  - MAA 缺陷层 SFT 和 SAMT 的提示词又是另外的格式。
- **也就是说,中训练学到的文本格式,不是评测时喂给模型的格式。** 按我方对训练曲线的解读,LM loss 在前约 20% 步数里的快速下降大部分来自学会格式和套话(`results/figures/README.md`;这是解读,不是测量),这部分学习在 E1 / E4 的读出格式下可能用不上。
- 这是一个**未检验的假设**,不是结论。它与阶段 0 的初步结果不矛盾:标签效率(Q1,tapt − base)和剂量(Q3)判为无效,负对照(Q2)判为未定;去掉评测重题后的 tapt_clean 版本(Q1′ / Q3′)还在跑。正式报告见 issue #3。
- **建议:**
  - 照 ADP 的 hub-and-spoke 思路,定义一个**规范渲染器**:`render(mas-traj, view)`,中训练语料和所有读出都从它生成;
  - 先做一个零 API 的检验:用 TAPT 语料的格式重新渲染 WW / TEgc,对 base 与 tapt_clean 重新提 E4 特征(各约 2.2 GPU 小时),看 tapt_clean − base 是否变化。若有变化,说明格式不一致确实吃掉了中训练的作用。

### 2. 标签层也要"协议化"(ADP 只管轨迹,不管标签)
- ADP 服务的是"在示范轨迹上做 SFT",不需要标签。我方做归因,标签来源很杂:注错构造(TracerTraj、AEGIS)、反事实回放(AgenTracer 的一部分、medical-aegis 分叉)、人工(WW、TEgc、MAA 400、MAST)、LLM 评审。
- 这些标签的层(缺陷层 / 责任层)、粒度(步 / agent / 码)、分类体系各不相同。我方踩过的坑基本都出在这里:
  - TracerTraj agentic 部分步骤从 1 开始编号;
  - 锚点导出里的 `answer` 字段其实是金标准,不是系统答案;
  - MAST 与 MAA 不能混用(硬规则);
  - 服务器上的 TAPT 训练文件没有 run_id。
- **建议定义 typed 的 `labels/attribution` 子 schema:**
  - `layer`(defect / responsibility);
  - `granularity`;
  - `taxonomy` + 版本(如 MAST-14、MAA-10);
  - `origin`(human / llm_judge / injection_by_construction / counterfactual_replay)及一致性或置信度;
  - 显式的"未判定"与负例;
  - 统一的 0 起始步骤索引;
  - 指向分叉对的链接(`parent_run_id`、`branch_step`、`intervention`、`flipped`)。
- 每个标签来源只写一次转换器,后训练和评测就都能接上。这同时让"分体系不合并"之类的硬规则在 schema 层自动强制,而不是靠人记。

### 3. 去重与划分字段写进协议
- 我方阶段 0 的 manifest(`results/stage0_manifest/`)发现:
  - 356 条 WW + TEgc 评测轨迹中,有 **270 条**的题目出现在 TAPT 中训练语料里(AFTraj、ARIA 里同一批 GAIA 题);
  - TracerTraj 测试集 768 条中有 621 条与训练集同题。
- ADP 正文和附录里我方没有找到训练数据与评测题去重的讨论;它的评测包括 GAIA。
- **建议:** 在 mas-traj 中加入必填的 `task_group_id`(题干归一化 + Jaccard ≥ 0.3 分组)和 `split` 字段;导出时自动对所有已登记的评测集查重,与 MAA 排除清单同一机制。

### 4. 质检指标化
- ADP 的数据集统计表(轮数、动作分布、"思考"覆盖率)是很好的数据卡模板。
- 我方可以对每个数据集固定报告:agent 数、读集来源是记录的还是推断的、环境步占比、标签来源与层、长度 / 位置平凡基线(阶段 0 审计表已有)、与评测集的重叠数。

## 四、不建议 / 需要谨慎的地方
- **把 ADP 的 1.3M 单智能体轨迹导入作为中训练语料:**
  - 这些大多是示范轨迹(成功或合成),相当于又一份"成功轨迹先验"语料;
  - 阶段 0 初步结果显示,加量(24.5M → 34.4M)和无关文本都没有带来归因上的提升;
  - 要导入也必须先按 GAIA 等题去重。
  - 若要用,更合适的身份是**"单智能体、无交互结构"的负对照**,用来检验多智能体结构在中训练里有没有额外价值,而不是主语料。
- **ADP 的结论是关于策略 SFT 的,不是关于归因的:**
  - 基座在这些框架里起点接近 0(如 SWE-Bench 0.4%),相当一部分增益来自学会框架格式;
  - 跨任务优势的对照(附录 E.1)是把单一数据集**上采样**到同样本数,唯一内容量仍然不同;只有一组比较,没有报告种子方差。
  - 所以"多样性优于数量"在他们那里也还不算定论。

## 五、具体提案与分工(都不花 API 费,等用户确认)
1. **medical-aegis(schema 维护方):** 起草 mas-traj/1.1 增补:
   - 动作类型(code / tool / message / decision);
   - 思考与动作分离字段;
   - typed 标签子 schema(第三节第 2 点);
   - `task_group_id` / `split`;
   - 分叉链接字段。
   保持向后兼容(旧字段不删)。可选:写 mas-traj → ADP 导出器(会丢弃多智能体结构,只为与 ADP 生态互通)。
2. **方法侧(我方):**
   - 写规范渲染器 + 第三节第 1 点的格式一致性检验(约 4.5 GPU 小时);
   - 把 TracerTraj / WW / TEgc / MAA 400 的标签转成 typed 标签子 schema;
   - 把阶段 0 manifest 的分组 id 回填进各数据集。
3. **请 GPT / Muse 补充:**
   - 有没有专门面向**多智能体**轨迹的数据标准或 schema(包括可观测性 / 追踪领域的规范),是否已覆盖读集、消息路由、编排事件?
   - 有没有文献检验过"中训练序列化格式 ≠ 下游格式"对迁移的影响?
   - 标签层的 `origin` 分类是否够用?

## 六、想请各方回答的问题
- **medical-aegis:**
  1. export_schema_v1 里,代码 / 工具 / 消息能否从现有字段可靠区分,还是需要在生成端补记?
  2. 各框架有没有可导出的思考字段?
  3. 分叉试点的运行之间,现在用什么字段相互关联?
- **GPT:** 第三节第 2 点的 typed 标签子 schema,和第 75 轮讨论的约束操作定义(4 条)是否冲突?
- **Muse:** 见第五节第 3 点。
