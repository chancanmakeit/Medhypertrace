# 结构感知中训练 SAMT v1(第 64 轮)

**要检验的假设:** C6 的诊断是 SFT 没有学会读图 token(置零 / 打乱图 token,LQD AUROC 不降;graph − text ≈ 0)。
纯文本 TAPT 不训练图 token,所以没有回答这个问题(第 62 轮)。SAMT 先单独训练"把图 token 读出来"这件事,
再做和以前完全相同的 SFT,看图 token 是否开始有用。

**定位:** 这是 GraphGPT / LLaVA 第一阶段式的**对齐**,不是预测或自监督(C5 已做过编码器自监督,没有增益)。
每个中训练问题的答案都编码在图 token 里(编码器能看到完整的超图和节点内容),但不出现在可见文本里;
LLM 冻结,只训练超图编码器和 projector,所以 LLM 只能通过图 token 拿到答案。

## 1. 结构
- **编码器:** HGFM v0.2(C1–C4,`model_v02.HGFMv02`,去掉两个 head),d = 192,**从零开始、端到端**经冻结的
  Qwen3-8B 训练。与 SFT 现用的"每折有监督编码器"不同,它**从未见过 MAA 数据和任何标签**,所以一份图 token 服务所有折,
  对每个折都是严格零样本。
- **节点特征:** 与 MAA 完全相同(`data_maa.Featuriser` 的布局:MiniLM(output[:2000]) | MiniLM(phase | role) | 9 个标量;
  任务向量 = MiniLM(query) + 0.5·MiniLM(framework_description))。Linux #2 本地 MiniLM 与 MAA 嵌入缓存一致
  (123 条抽查,cos ≥ 0.99992)。没有结构化答案的来源,答案相关标量为 0。
- **projector:** 与 SFT 相同(Linear(194, 4096) → ReLU → Linear(4096, 4096)),`<graph>` 占位符替换方式相同。
- **LLM:** Qwen3-8B 冻结(不加 LoRA)。好处:text 变体和以前完全一样,基座 3 种子的 text 结果直接作对照,不用重跑。

## 2. 语料(不含 MAA;排除 groupchat family,同 TAPT,LQD_mac 在架构层面也零样本;MAA 排除清单)
公开 7 个数据集 + medical-aegis 锚点 normal 运行。提示格式与 SFT 一致:任务、最终答案、
≤ 10 个步骤行 `[sid] agent | phase | round r <graph>` + 400 字符节选、≤ 4 条事件行 `<graph> instr`、问题。
答案短,loss 只算答案。四类问题:

| 目标 | 问法 | 答案 | 文本里拿不到答案的保证 |
|---|---|---|---|
| O1 内容匹配 | 4 个步骤的节选被隐藏,给出 4 段节选(A–D),问目标步骤是哪段 | 字母 | 干扰项来自同一运行、优先同一 agent / 同 phase;选项步骤在列表里都不显示节选 |
| O2 读集 | 目标步骤读了列表里的哪些步骤 | 步骤 id 列表 | 只问"(数据集, 框架, phase) 的来源模式最常见占比 < 0.9"的步骤(C5 规则);干扰项 = 与真来源 phase 相同的更早步骤 |
| O3 读者 | 列表里哪些步骤读了目标步骤 | 步骤 id 列表 | 同上,方向相反 |
| O4 答案 | 目标步骤(节选隐藏)选了哪个选项 | 选项字母 | 只用锚点(只有锚点有结构化答案) |

## 3. 中训练检验(决定 SFT 结果能否解读)
留出 3% 的运行,每类目标分别比较:真图 token / 运行间打乱的图 token / 图 token 置零 下的答案准确率。
**真 ≫ 打乱** 才说明冻结 LLM 学会了读图 token;否则 SFT 结果不必解读。

## 4. SFT 评测(与第 60、62 轮相同:只用 MedAgentAudit 体系;QD + LQD_mac;种子 0、1)
| 配置 | 图 token 来源 | projector | 用途 |
|---|---|---|---|
| **SAMT** | SAMT 编码器 | SAMT 中训练后的权重,lr 1e-4 | 主结果 |
| 对照:只换编码器 | SAMT 编码器 | 随机初始化,lr 1e-3(原配方) | 区分"编码器换了"和"对齐过了" |
| 基座 graph / text | 每折有监督编码器 | 随机,lr 1e-3 | 已有 3 种子(第 60 轮) |

SFT 提示与基座完全相同(复用各折现有的 `sft_graph/*.jsonl`,候选步骤不变),只换图向量来源。
主要比较:SAMT graph − 基座 text(配对 bootstrap);SAMT 下图 token 置零 / 打乱是否降低 AUROC(C6 诊断复测)。
projector 学习率从 1e-3 降到 1e-4 是有意的偏离:已对齐的 projector 用大学习率会很快被冲掉(LLaVA 第二阶段同理)。

## 5. 不做 / 留到下一版
- 不训练 LLM(若 SAMT 显示 LLM 能读 token 但 SFT 仍无增益,v2 再考虑 LoRA 一起训);
- 不在中训练用 MAA 无标签运行(保持一份 token 服务所有折);
- 数据来源可识别度(第 61 轮承诺):用 O1–O3 的打乱对照按数据集分开报告。
- LQD 其余 5 折:若 QD / LQD_mac 有信号再做。
