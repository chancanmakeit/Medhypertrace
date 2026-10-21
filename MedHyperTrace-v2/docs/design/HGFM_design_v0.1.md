# 超图基础模型（HGFM，暂名）设计草案 v0.1 — 第 22 轮，2026-10-19

**定位（用户定，军令状）：** 基于结构化 JSON 轨迹的文本属性超图，训一个**超图基础模型**；处理图特征、做推理是它附带的能力。不以复现 AFANet 作为前置检验。AFANet 等仍是论文里必须对比的基线。

---

## 0. 实测依据：通用"读集超边"可从调用输入中恢复

AEGIS 合成数据每一步都存了该次 LLM 调用的 `input_messages`，TriageAgent 有 `llm_call_log`。用分片子串匹配（每条前序输出取 ≤5 个 60 字符片段，过半出现在本步输入中即算"读过"），统计 LLM 调用步（不含 `is_input=True` 的 User 提示条目），首个调用步除外：

| 框架 | 中位步数 / agent 数 | 读了≥1 个前序步 | 读集大小 ≥3 | 缺 `input_messages` |
|---|---|---|---|---|
| dylan | 10 / 4 | 63% | 62% | 0% |
| llm_debate | 7 / 4 | 67% | 38% | 0% |
| clinical_agent | 6 / 6 | 38% | 20% | 0% |
| clinical_agent5 | 5 / 5 | 25% | 24% | 0% |
| mdagents | 7 / 3 | 17% | 17% | 0% |

（读集大小 = 读到的前序步数，不含写入步本身；脚本 `analysis/read_hyperedge_stats.py`。匹配是启发式的，改写过的引用会漏检。）

**含义：** "一次调用同时读了哪几条"是天然的多元关系，在聚合 / 讨论类步骤里很普遍，且可以不针对框架手写规则地恢复——这是超图建模的数据依据，也是"schema 无关"的落脚点。（第 23 轮更正：第 22 轮把 llm_debate 的 User 提示条目也算作步骤，误报"46% 缺输入"；agent 步实际缺失 0%。）

**第 23 轮发现的泄漏：** prompt_injection 步骤记录的 `input_messages` 含注入指令原文（mdagents、clinical_agent、clinical_agent5 100%，dylan 99%，llm_debate 64%），且前三个框架未存注入前输入。HGFM 节点文本**不得**直接使用这些框架的原始 `input_messages`。第 24 轮已实现 `data_tools/clean_inputs.py`：用 `raw_history.original_prompt`（mdagents / clinical_agent / ca5）和 `original_input_messages`（dylan / llm_debate）把 5 个框架的 PI 步骤 100% 恢复成干净输入、无模板残留；读入旧数据一律先过这一步。MedHyperTrace 现有代码只用 `input_messages` 建边、节点文本用 `content`，不受影响。

---

## 1. 统一轨迹超图（UTH）：模型的"分词器"

- **节点（均带文本属性）：** step（该步输出）、agent（角色描述）、task（问题）、outcome（最终答案）。
- **有向超边：**
  - 读集超边 R_i：尾 = 本步输入中出现的前序步集合，头 = 本步。从 `input_messages` / `llm_call_log` 的来源匹配得到，所有框架通用。
  - 事件超边：同一讨论轮 / 投票 / 共识的全部参与步（对应 FC4 共识动态故障）；同一 agent 的全部步；送入最终答案的步集合。
- **关系类型用自然语言描述**（如"该步读取了以下步骤的输出"），由冻结文本编码器编码，不设框架专属词表（借 ULTRA / HYPER 的关系图与位置交互、REEF 的关系文本→超网络）。超边内部用"角色"（读入 / 写出 / 投票成员 / 结果）而非有序槽位编码位置，因为投票成员无序。
- **缺 provenance 时的回退：** 按框架协议声明的可见性规则补边，并在边上标注证据等级（借 GRADE 的观测 / 声明 / 推断三级），评测时可分开统计。

## 2. 模型

1. **节点编码：** 冻结文本嵌入模型（如 Qwen3-Embedding）编码节点文本与关系描述。
2. **超图编码器：** 有向超图 Transformer，节点→超边→节点两段注意力，消息以关系文本嵌入为条件；**查询条件化**——用 labeling trick 把 task / outcome 节点初始化为查询向量（ULTRA、GFM-RAG），同一编码器回答"谁对这个结果负责"。
3. **输出头：** step 责任分、agent 责任分（对其 step 聚合）、超边责任分（哪一次交互事件出了问题）。
4. **LLM 耦合（推理能力）：** 投影器把 top-k 候选节点 / 超边表示映射为图 token，送入冻结 LLM（如 Qwen3-8B）；LLM 同时看到这些候选步的原文，生成故障类型与理由，**约束解码**只能输出轨迹里真实存在的 (agent, step)（借 GraphGPT / TEA-GLM 的投影器、PromptGFM / RAR 的约束解码）。

## 3. 预训练（自监督为主，不依赖人工标注）

| 目标 | 监督从哪来 | 学到什么 |
|---|---|---|
| 掩码步骤重建（特征级） | 自身 | 内容与上下文的一致性 |
| 读集超边填充（HypeBoy 式：给定头和部分尾，补缺失的尾） | provenance，免费 | 信息依赖结构 |
| 结果预测（这条轨迹答对还是答错） | 医学 QA 有标准答案，免费 | 全局失败信号 |
| 成对运行分歧定位（HPFA 式：同一问题多次运行，对齐成功与失败轨迹，找首个分歧步作伪标签；**分歧定义在 `structured`（答案/投票）语义层**，温度>0 时文本在 s1 就不同） | 多次采样，免费 | step 级弱监督 |
| 图-token 对齐（TEA-GLM 特征级对比 / GraphGPT 匹配指令） | 自身 | 让冻结 LLM 读懂图 token |

之后用有标签数据（AEGIS 合成注入、Who&When、AEGIS-Bench、GraphTraj 等）做归因微调；新框架只调投影器 LoRA + 框架描述 token（REEF 的数据集级偏置）。

## 4. 语料：基础模型成败的关键

- **现有：** 本项目 5 个合成框架（约 5.2k 条，全是注入后的失败轨迹，有模板伪迹）、Who&When、TRAIL、MAST 标注轨迹、AEGIS-Bench、GraphTraj-2.5K（若公开）、TriageAgent。
- **缺口：** 现有数据几乎全是失败轨迹且以注入为主；没有成功轨迹就做不了结果预测和成对分歧这两个最有价值的自监督目标。
- **由 medical-aegis 项目负责生成**（用户第 23 轮安排）。需求已写成 `docs/interfaces/medical_aegis_trajectory_spec_v1.md`（统一 schema v1：labels 与 steps 分离、干净输入、`sources`、`event_ids`、normal 每题 K 次采样、≥8 框架）。

## 5. 评测与必做实验

- **主评测：** 留一**家族**零样本（按 `framework_family` 留出，近似重复框架不得分处训练/测试；≥8 个家族），缩放曲线在**锚点任务**（固定 100 道医学 MCQ，所有框架都跑）上做，原生任务单独报"新框架 + 新任务"泛化+ MAFA 人类 dev/test（遵守预注册划分，MAST 与 MedAgentAudit 分开）。
- **基线：** AFANet、CHIEF / Adaptive Influence Graphs（免训练）、GraphTracer / AgenTracer（图 + RL / RL）、MedHyperTrace、猜第一步 / 位置先验。
- **论文必需的消融（不是前置门槛）：** 超边 vs 星形展开 vs 无边 vs 度数匹配伪造（GRADE）；按故障类型分层看增益是否集中在多方交互类；去掉 LLM / 去掉超图编码器；预训练目标逐项消融；**框架数量的缩放曲线**（"基础模型"的核心证据）。

## 6. 主要风险

1. 语料多样性不够，撑不起"基础模型"的说法 → 缩放曲线做不出来。
2. 注入数据的模板伪迹被编码器学成捷径 → 预训练以自然运行为主，注入数据只用于微调，并按注入策略分开报。
3. 部分框架缺 provenance → 回退规则 + 证据等级；已向 medical-aegis 申请生成时记录 `sources`（`docs/interfaces/medical_aegis_trajectory_spec_v1.md`）。
4. 计算：4×A6000，冻结 8B LLM + 小超图编码器 + LoRA 投影器可行；文本嵌入需离线缓存。
