# 图方法版图与"超图 + 大模型"的新颖性定位（2026-10-19，第 21 轮）

依据：本仓库 3 篇原有 PDF + 本轮新增 42 篇（三个检索方向）。所有 PDF 已按首页标题核对为真实论文。下列判断中，**AFANet、HPFA、GRADE、AIG、CHIEF、GraphTracer、AgentTrace** 由主会话读过原文摘要/方法/关键表；其余条目依据各目录 `INDEX.md`（子 agent 读 abs 页写成，未逐页通读，引用前需回看 PDF）。

## 1. 现有图方法分五类

| 类别 | 代表 | 图怎么建 | 学的是什么 | 跨框架 |
|---|---|---|---|---|
| A. LLM 建图 + LLM 推理（免训练） | CHIEF、Adaptive Influence Graphs、DCFA、EDGE、EMFA、FALAT、STRACE | LLM 抽取依赖/因果边，或 LLM 自适应选择节点粒度 | 不训练；图以文本形式喂回 LLM | 换 backbone，不换框架 |
| B. 图用于造数据 / 定义奖励，再微调 LLM | GraphTracer（IDG + RL，Qwen3-8B）、HPFA（**超图** + 成对对比 + SFT/GRPO，COLM 2026） | 依赖图 / 依赖超图 | LLM 读文本；图只在训练数据和奖励里 | 训练后迁移 |
| C. 规则建图 + 启发式 / 因果发现 | AgentTrace（反向 BFS + 手工特征，位置权重 0.70）、CDC-MAS（因果发现 + Shapley） | 规则解析日志 | 不训练或只调权重 | 无 |
| D. **训练图神经网络** | **AFANet**（轮次图，时序边 + 同 agent 边，TF-IDF + sentence-BERT 特征，2 层 GCN；AEGIS-Bench 训练 → Who&When OOD + 测试时适配）、AgentTether（异构图 Transformer 在正常遥测上自监督） | 规则建图 | GNN 直接输出归因 | AFANet 有 AEGIS→Who&When 迁移 |
| E. 表示与可信度批评 | GRADE | 执行层 + 分级依赖层 | — | 结论：依赖层相对"运行规模"基线的增益依赖学习器和任务采样；语料内与**度数匹配的伪造依赖层**不可区分 |

相邻：图安全（G-Safeguard、BlindGuard、XG-Guard、NetSafe、节点贡献反传）用 GNN 在通信拓扑上找恶意/出错 agent，属于运行时检测而非事后归因；超图在 MAS 里目前只用于拓扑优化（HyperAgent）和记忆（MAGE）。

## 2. 两个新颖点还剩多少

**"超图"：不能再说"首次把超图用于故障归因"。** HPFA（COLM 2026）已用依赖超图做故障归因。但它是单智能体推理轨迹（数学、代码），超图只用于成对比较缩小搜索空间和合成训练数据，最终模型是读文本的 LLM，超图从未被编码。仍空着的是：**多智能体轨迹上、作为可学习表示被编码的超图**。

**"图特征 + 大模型推理"：确实空着。** D 类只有 GNN（AFANet 明确主张"不需要 LLM"），A/B 类只有 LLM（图以文本或数据的形式进入）。118 篇图大模型里成熟的那套做法——GNN 表示对齐 LLM token 空间、图 token 进冻结 LLM、查询条件 GNN 打分 + LLM 读 top-k——在 MAS 归因里还没人做。

**"跨框架零样本 / adapter"：部分被占。** AFANet 已做 AEGIS-Bench→Who&When 的 OOD 加测试时适配，A 类全部免训练所以天然"零样本"。要成为卖点，必须做**系统的留一框架**评测，并在 OOD 上显著胜过 AFANet 和免训练的 A 类方法。

## 3. 最不利的证据（必须正面回应）

1. **结构增益很小。** AFANet 消融（表 4）：域内 AEGIS-Bench agent µF1 全边 74.16，**无边** 71.26，只用时序边 74.82（高于全边）；OOD 的 Who&When 上差距大一些（全边 37.93、无边 32.18、只用时序边 35.06）——结构的价值可能主要体现在分布外，这一点对我们有利，值得复核。GRADE：依赖层与度数匹配的伪造层在语料内不可区分。我们自己：MedHyperTrace 在 human-like v1 上未超过"猜第一步"，AgentTrace 的最大权重也是位置特征。四方证据指向同一结论——**现有基准上，图结构里多出来的东西还没被证明有用**。超图若只是更复杂的结构，大概率重蹈覆辙。
2. **LLM 一侧不弱。** CHIEF（免训练）在 Who&When algo 子集 step 准确率 52.00、agent 76.80（表 1，w/ G 设定），GraphTracer-8B 接近；"图 + LLM"必须同时超过 AFANet（便宜）和 CHIEF（免训练），否则两头不讨好。
3. **数据重叠。** AFANet 正是在 AEGIS-Bench 上训练的；我们的合成数据同源且有注入模板伪迹（HANDOFF §0.29–0.30）。在这些数据上赢，审稿人会问是否学到了伪迹。

## 4. 对 idea 的含义（待讨论）

- 卖点应从"用了超图"换成**超边承载的信息是二元图表达不了的**：例如一次投票/共识事件（多方同时贡献、少数意见被压制，对应项目里 FC4 共识动态故障）、一次多源检索被多人共用。必须设计"超边 vs 星形展开 vs 无边 vs 度数匹配伪造"的四方对照，并在**按故障类型分层**后证明增益集中在多方交互类故障上。
- LLM 的作用要有明确理由，而不是"加上更强"：AFANet 只做 agent + 错误类型，step 级和"为什么"仍弱；LLM 读 GNN 打分后的 top-k 候选并给出可验证的理由（约束解码到真实 (agent, step)），是 GNN 做不了的部分。
- 必须对比：AFANet（同 AEGIS-Bench，可直接复现）、CHIEF / AIG（免训练 LLM 建图）、GraphTracer（图 + RL）、MedHyperTrace、平凡基线（猜第一步、位置先验）。
