# MedHyperTrace 方法总框架讲解 + Method 概览图绘图提示词(第 76 轮,2026-10-28)

依据:
- `docs/design/HGFM_design_v0.2.md`(C1–C9)、`docs/design/SAMT_design_v1.md`;
- `hgfm/uth.py`、`hgfm/model_v02.py`、`hgfm/llm/README.md`、`hgfm/midtrain/*`、`hgfm/e4/*`;
- 各轮结果 README。

文中凡写到"已实现 / 有证据 / 没有证据"的地方,都对应到具体结果文件。

---

## 0. 先说清楚:这张图应该画什么

Method 图画的是**方法设计**,不是结论。但按目前的证据,下面几项**都没有**得到支持:
- 中训练能改善归因(E1 未定,E4 不成立);
- C5 自监督;
- SFT 阶段的图 token 增益。

**有正面证据的只有一项:** SAMT 让冻结的 LLM 学会了从图 token 读出交互结构(探针门槛)。

因此我的建议是:
1. **图按模块化画。** 每个训练阶段一个独立方框,这样以后如果某个阶段在论文里被删掉或降级为消融,只需删一个方框,不用重画整张图。
2. **不在图上写任何性能主张。** 不要出现 "improves"、"+x%" 之类的字样。
3. **C9(只用结果标签的反事实责任分配)尚未实现**,在图里用虚线框表示,或者先不画。下面的提示词给了 A、B 两个版本。
4. **方法名的选择。** 用户约束是"基础模型通过中训练获得",所以图的主干叙事是:
   > 轨迹超图化 → 超图编码器 + 图 token 接入 LLM → 两阶段中训练(文本 TAPT + 结构 SAMT)→ 下游归因微调
   >
   名字建议用 **MedHyperTrace**,基础模型部分叫 **HGFM**(Hypergraph Foundation Model)。

---

## 1. 方法总流程(一句话版)

把医疗多智能体系统的执行日志转成**统一轨迹超图(UTH)**,再用**超图基础模型编码器 HGFM** 编码成**图软 token**,经 projector 注入 LLM(Qwen3-8B)。整个模型通过**两阶段中训练**获得轨迹先验:
- **TAPT:** 在无标注轨迹文本上续训预训练;
- **SAMT:** 冻结 LLM,训练编码器和 projector,让 LLM 能"读"图 token 中的交互结构。

然后用少量参数的微调(SFT-LoRA / BEFT)做两层归因,输出受约束解码限制在真实存在的 agent、步骤和故障码上:
- **缺陷层:** 步骤 × 故障码,MedAgentAudit 体系;
- **责任层:** 哪一步是决定性错误,Who&When 口径。

---

## 2. 各模块细节

### 模块 A:输入,医疗 MAS 执行日志
- 统一 schema `mas-traj/1`(与 medical-aegis 共同定义)。只读取 `task`、`steps`、`final`、`framework_description`。
- 标签和元数据在物理上分开存放,建图时从不读取,防止标签泄漏。
- 每个 step 是一次 LLM 调用或工具调用,字段包括 agent_id / role、phase、round、event_ids、`sources`(读了哪些前序步骤,以及读取方式 `how`)和 output。
- 覆盖的框架有 llm_debate、mdagents、medagents_mc、MAC 等医疗 MAS,以及公开数据(ARIA、MAST-Data、AFTraj、MAScope、TraceElephant、AgentRx、Who&When)。

### 模块 B:统一轨迹超图 UTH(`hgfm/uth.py`,已实现)
节点都带文本属性,分 5 类:

| 节点 | 含义 |
|---|---|
| `task` | 题目 / 查询 |
| `obs` | 共享观察 |
| `step` | 一次调用,文本 = 输出 |
| `agent` | 跨阶段稳定的 agent 身份 |
| `final` | 系统最终答案 |

有向超边分 6 类(tail → head):

| 超边 | 成员 | 说明 |
|---|---|---|
| `read` | 某步骤读到的全部来源 → 该步骤 | k 元,每步一条 |
| `read_new` | 只含该 agent 之前没见过的来源 | |
| `control` | 选择 / 路由 / 招募关系 | 与内容读取分开 |
| `event` | 同一投票轮 / 讨论轮的步骤 | 无向 |
| `agent` | 同一 agent 的全部步骤 | 无向 |
| `final` | 最终答案的来源步骤 → final | |

每个成员带角色槽:head,或 tail 的 `how` ∈ {verbatim, excerpt, structured_field, protocol}。

**为什么用超边而不是普通图边:** 一次调用往往同时读多个前序步骤(例如主持人读三份专家意见),这是 k 元关系。拆成二元边会丢失"一起被读"的信息,也就区分不了"读了原文"和"只读了票数"。

### 模块 C:超图基础模型编码器 HGFM v0.2(`hgfm/model_v02.py`,C1–C4 已实现)
输入特征:
- 节点:MiniLM(输出前 2,000 字符) | MiniLM(phase | role) | 9 个标量;
- query:MiniLM(题目) + 0.5 · MiniLM(框架描述)。

四个组件:
- **C1 位置感知的 k 元超边消息(来自 HYPER):** 成员的角色槽用位置编码 + MLP 表示,参与消息计算。
- **C2 关系图(来自 HYPER / ULTRA):**
  - 关系类型定义为 (超边类型 × 角色槽 × 头步骤的 phase),每种关系作为一个节点;
  - 两种关系在某个槽位共享步骤时连边;
  - 在关系图上做以 query 为条件的 2 层消息传递,得到关系表示 r。初值为关系文本的嵌入。
  - 作用:对框架内的阶段名、角色名改名不变,支持跨框架零样本。
- **C3 超边文本指令(来自 IHP):**
  - 每条超边由模板生成一句自然语言指令,例如 "In review round 1, the internist read the summary and three initial opinions";
  - 超边表示 = 成员聚合 + γ · W · MiniLM(指令),再被关系表示 r 调制。
- **C4 查询感知的 edge→node 注意力(来自 HyperG):** node→edge 用多头注意力;edge→node 以 query(题目 + 系统最终答案)为条件,把与"这次失败"相关的超边信息传回步骤节点。

输出:每个步骤节点和每条超边一个 192 维向量。

(**C5** 是 HypeBoy 式自监督:掩码特征重构 + read 超边填充,代码在 `hgfm/ssl_v02.py`。**已做过,没有增益**。建议论文里只放在消融中,不放进主图。)

### 模块 D:图 token 接入 LLM(C6,`hgfm/llm/`、`hgfm/midtrain/samt_*`,已实现)
- projector:Linear(194 → 4096) → ReLU → Linear(4096 → 4096)。
- 提示词中每个候选步骤一行 `[sid] agent | phase | round r <graph>` + 400 字符节选;每条关键超边一行 `<graph> 指令`。每个 `<graph>` 占位符的嵌入替换成对应的图向量。
- LLM:Qwen3-8B。
- 分工:超图负责结构定位("谁读了谁、谁选了谁"),LLM 负责内容判断("这条医学推理错了")。这样设计的依据是 C8 / LLM4Hypergraph:直接把超图写成文本交给 LLM,结构能力有限,并且随图规模变大而退化。

### 模块 E:两阶段中训练,获得基础模型(本文核心叙事)
**Stage I:文本中训练 TAPT(`hgfm/midtrain/build_corpus.py`,`scripts/linux2_run_tapt.sh`)**
- 语料:24.5M token 的无标注轨迹,来自公开 7 个数据集 + 锚点 normal 运行。不含 MAA;排除 groupchat 家族,以保证留出评测零样本。
- 训练:续训预训练(next-token CE),LoRA r64 全 linear 层,1 个 epoch;之后把 LoRA 合并进权重。
- 学到的东西:轨迹语言,包括格式、角色话语和工具输出(图 1)。

**Stage II:结构感知中训练 SAMT(`hgfm/midtrain/samt_*`)**
- 冻结 LLM,从零端到端训练 HGFM 编码器 + projector,共 19.1M 参数。
- 训练数据是 4 类图问答。答案编码在图 token 里,可见文本中拿不到:

| 目标 | 内容 |
|---|---|
| O1 | 内容匹配 |
| O2 | 读集:目标步骤读了谁 |
| O3 | 读者:谁读了目标步骤 |
| O4 | 选项答案 |

- 相当于 GraphGPT / LLaVA 第一阶段的对齐。
- 证据:留出运行上,真 token 与打乱 token 相比,O2 为 0.98 vs 0.51,O3 为 0.99 vs 0.22(图 2)。

**(规划中的 Stage II′,预注册 v2 候选):** 替换步检测(类似 ELECTRA 的 RTD)。把轨迹中某一步换成同题另一次运行里同位置、长度相近的步骤,让模型找出被替换的那一步。
- 零 API,标签按构造得到,长度按构造匹配。
- 与超图读集结构直接相关:被换掉的步骤会破坏"谁读了谁"的一致性。
- 如果它进入论文,在图中作为 Stage II 的第二个目标框。

### 模块 F:下游归因微调与输出
- **缺陷层(MedAgentAudit 体系):** 对每个"步骤 × 故障码",问 LLM "Target step … present? yes/no"。分数 = logit(yes) − logit(no)。训练 LoRA(q/k/v,r = 8)+ projector。只用 MAA 的审计员弱标签训练,用 400 条人工标注评测。
- **责任层(Who&When 口径):** 每个候选步骤取 LLM 末层在该步 token 上隐状态的均值,经打分头得到分数,在候选步骤上做 softmax 交叉熵。
  - 参数高效版本是 **BEFT**:只训练每层 v_proj 的 bias,加一个打分头,约 49k 参数;
  - 也可以把冻结特征 + 探针头作为对照。
- **C7 约束解码:** 输出只允许轨迹中真实存在的 (agent_id, step_id) 和体系内的故障码。目前实现的是最简形式:yes / no 二选一,加上候选集限定。
- **C9 反事实责任(未实现,设计中):** 只用结果标签(是否答错)。对每个步骤或超边做掩码,用失败概率的下降量 ΔScore 作为该步的责任分,不需要步骤级标签。

### 模块 G:评测协议(建议画成图下方的一条窄带,或者干脆不放进 Method 图)
- 任务按题目分组,外部集用"题干归一化 + Jaccard ≥ 0.3"去重;
- 报告步长 / 位置基线,以及长度控制后的结果:轨迹固定效应残差化,另做匹配配对;
- 配对 bootstrap;
- MAST、MedAgentAudit 的结果分开报告。

---

## 3. 推荐的图版式

- 横向 16:9,从左到右三列,底部一条横带。
  - 左列:输入日志 → UTH。
  - 中列:HGFM 编码器 → projector → 图 token 与文本交错进入 LLM。
  - 右列:两类输出(缺陷层、责任层)。
- 底部横带:训练课程 Stage I → Stage II → Stage III。用细箭头向上指到各自更新的模块,并在模块上标出"训练 / 冻结"的图标(火焰 / 雪花)。
- 配色(与训练曲线图一致):
  - 结构 / 超图用蓝 `#2a78d6`;
  - LLM / 文本用橙 `#eb6834`;
  - 训练信号用绿 `#1baf7a`;
  - 其余用灰色。

---

## 4. 给 GPT 的绘图提示词

### 版本 A:完整版,含 C9 虚线框

```
Draw a clean, publication-quality METHOD OVERVIEW figure for an ML paper (NeurIPS/ICLR style), landscape 16:9, flat vector style, white background, thin dark-gray outlines, rounded rectangles, sans-serif font, no 3D, no gradients, no clip-art people, no logos. Use only this palette: structure/hypergraph = blue #2A78D6, LLM/text = orange #EB6834, training signals = green #1BAF7A, everything else gray (#52514E text, #E4E3DF fills). All text in English and spelled exactly as given in quotes. Keep text short; do not add any numbers, scores or claims that are not listed here.

Title at top-left: "MedHyperTrace: failure attribution in medical multi-agent systems with a mid-trained hypergraph foundation model".

LAYOUT: three columns left-to-right connected by bold arrows, plus a horizontal band along the bottom.

COLUMN 1 — "(a) Trajectory → Unified Trajectory Hypergraph (UTH)".
Top: a small stack of log cards labelled "Medical MAS execution log" showing 4 short rows: "s1 GP | diagnose", "s2 Cardiologist | opinion", "s3 Neurologist | opinion", "s4 Moderator | aggregate → final answer". Small caption under it: "schema mas-traj/1 · labels never read".
Arrow down to a hypergraph drawing: round nodes of five kinds with a tiny legend — "task" (gray square), "step" (blue circle), "agent" (blue-outlined diamond), "obs" (gray hexagon), "final" (dark star). Draw hyperedges as translucent blue blobs enclosing several nodes, with a small arrowhead pointing to the head node. Show one large k-ary hyperedge where s2, s3 and the task jointly point to s4, labelled "read (k-ary)". Show also smaller labelled hyperedges: "control", "event", "agent", "final". On the k-ary read hyperedge, mark member role slots with tiny tags "head", "verbatim", "excerpt". Attach to one hyperedge a small speech-bubble labelled "edge instruction: 'In round 1 the moderator read three specialist opinions'".

COLUMN 2 — "(b) HGFM encoder + graph tokens → LLM".
Upper box (blue) titled "HGFM hypergraph encoder" containing four stacked mini-blocks:
  "C2 relation graph (query-conditioned) → relation vectors r",
  "C1 position-aware k-ary messages (role slots)",
  "C3 hyperedge text instructions (+γ·instruction embedding)",
  "C4 query-aware edge→node attention".
Left of the box a small input "query = question + final answer" feeding into C2 and C4. Inside the box show a small loop arrow "× L layers". Output arrow labelled "step & hyperedge embeddings (d=192)".
Then a narrow blue-to-orange trapezoid labelled "projector (MLP 194→4096)".
Then an orange box titled "LLM (Qwen3-8B)". Its input is a horizontal token strip interleaving gray text tokens and blue square tokens: "[s2] Cardiologist | opinion", blue square "<graph>", "excerpt…", "[s4] Moderator | aggregate", blue square "<graph>", "Question: …". Caption under the strip: "graph soft tokens replace <graph> placeholders; text excerpts kept".

COLUMN 3 — "(c) Attribution outputs".
Two stacked output cards:
  Card 1 (orange border) "Defect layer: step × fault code" with a mini table of 3 rows of yes/no bars, caption "score = logit(yes) − logit(no)".
  Card 2 (orange border) "Responsibility layer: decisive mistake step" with a small bar chart over steps s1–s4 where s3 is highlighted, caption "softmax over candidate steps".
Under both cards a thin gray box "C7 constrained decoding: only existing (agent, step) and valid fault codes".
Below it a DASHED-outline box (to indicate future work) "C9 outcome-only responsibility: counterfactual masking ΔScore".

BOTTOM BAND — "(d) Training curriculum (foundation model via mid-training)", a horizontal sequence of three green-bordered stage boxes connected by arrows:
  "Stage I · Text mid-training (TAPT): continued pre-training on unlabeled trajectories, next-token loss, LoRA" — draw a thin green arrow up to the LLM box; put a small flame icon on the LLM for this stage.
  "Stage II · Structure-aware mid-training (SAMT): LLM frozen; encoder + projector learn graph-grounded QA — O1 content match, O2 read set, O3 readers, O4 answer" — thin green arrows up to the encoder and the projector; flame icons on encoder and projector, snowflake icon on the LLM.
  "Stage III · Attribution fine-tuning: SFT (LoRA q/k/v + projector) or BEFT (value-projection biases + scoring head)" — thin green arrows up to the output cards.
At the far left of the band a small gray note: "corpora: public MAS traces + medical anchor runs (no evaluation data)".

Make the three columns visually balanced, align boxes on a grid, keep generous whitespace, and make every label legible at single-column print size.
```

### 版本 B:保守版,只画已实现且已跑过的部分

在版本 A 的基础上,把下面这句加到提示词末尾即可:

```
Remove the dashed C9 box entirely. In Stage III keep only "Attribution fine-tuning: SFT (LoRA q/k/v + projector) or BEFT". Do not draw any future-work elements.
```

### 迭代时常用的追加指令
- 文字出错时:`Re-render with exactly the same layout; fix the spelling of the labels to match the quoted strings verbatim.`
- 太拥挤时:`Reduce text inside the encoder box to the four component names only ("C1 position-aware messages", "C2 relation graph", "C3 edge instructions", "C4 query-aware attention") and move the details to a caption.`
- 需要可编辑的版本时:先让 GPT 出 SVG(`Output as a single SVG with text as <text> elements`),再在 Inkscape / draw.io 中细修。生图模型的小字常常出错,最终版建议在矢量软件里重排文字。

---

## 5. 对应的 Method 章节结构(写作时可参照)
1. **3.1 问题设定。** 两层归因:缺陷层与责任层;输入只有日志,不读标签。
2. **3.2 统一轨迹超图 UTH。** 模块 B,配图 (a)。
3. **3.3 超图基础模型编码器 HGFM。** C1–C4,公式按 `model_v02.py` 写。
4. **3.4 图 token 接口。** C6,projector 与占位符替换。
5. **3.5 中训练。** TAPT 与 SAMT,包括语料构成、去重和留出规则;如果预注册 v2 的替换步检测有了结果,在这里加入。
6. **3.6 归因微调与推理。** SFT / BEFT,C7;C9 写成扩展或放到附录。
7. **3.7 评测协议。** 长度 / 位置控制与匹配配对。这一节建议放进实验章节的开头。
