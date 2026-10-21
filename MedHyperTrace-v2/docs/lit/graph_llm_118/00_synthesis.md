# 图大模型 118 篇 × 多智能体故障归因：综合笔记（第 20 轮，2026-10-19）

**来源:** `private-documents/muse-ai/graph大模型118篇全文解读.md`(Meta Muse AI 调研文档,746KB,118 篇)。
**读法:** 6 个 Sonnet 子 agent 并行逐段精读,每篇写"机制 + 关键数字 + 对 MAS 故障归因的可借鉴点",分段摘要见同目录 `p1`–`p6`(共 118 节,无遗漏)。主 agent 抽查了若干关键数字(GOFA 7%–69%、ZeroG 全参微调 Cora −51.36%、HyperG +189M 参数、GraphArena 中 GraphWiz 0.2%–1.2%、TEA-GLM Cora 0.202、组织 GNN 打乱节点不显著)与源文档一致。
**注意:** 源文档本身是二手中文转述,数字未回溯原论文;摘要中标【推断】的是子 agent 的迁移判断,不是原文结论。

---

## 1. 一句话结论

118 篇里**没有一篇**做"在 agent 轨迹 / 对话图上定位故障责任步",也没有一篇在**拓扑、角色、步数差异很大的图之间**成功做过零样本迁移。这既是新颖性空间,也意味着关键假设(跨 MAS 框架零样本)没有任何直接先例支撑,必须自己证明。

## 2. 设计空间:可借的组件按模块归类

| 模块 | 代表论文(编号) | 可借的东西 |
|---|---|---|
| 任务统一(把"谁、哪步"变成图上的选择问题) | OFA #1、GIT #5、SCR #36、REEF #50、GFM-RAG #108、TEA-GLM #98 | NOI/prompt 节点 + 类节点;虚拟任务节点;把分类改写成 KG 补全查询;"子图对是否存在某关系"的二分类模板;**以失败答案为 query 的 query-dependent GNN 一次前向给所有节点打分**;指令里给候选集 |
| 跨 schema 的零样本机制(不同框架的角色/关系词表不重叠) | ULTRA #3、HYPER #54、REEF #50、HiGPT #61、SAMGPT #32、ALL-IN #12 | 关系图(关系作节点、关系间交互作边)+ 位置交互编码,对重命名不变;用关系文本经冻结编码器 → 超网络生成聚合器/分类器参数;用自然语言描述节点/边类型生成类型相关参数;每个框架一个结构 token,新框架只学混合系数 |
| 超图建模 | HYPER #54、HypeBoy #52、IHP #53、HyperBERT #99、HyperG #93、LLM4Hypergraph #92、HyperGraphRAG #110 | k 元超边 + Deep Sets 聚合;超边填充自监督(可用无标注真实轨迹);指令注入超边卷积;超边 embedding → MLP → 软 token 插进 prompt;超边二部图展开即可用普通 GNN |
| 图与 LLM 的耦合 | GraphGPT #55、LLaGA #56、TEA-GLM #98、GOFA #6、GraphTranslator #64、G-Retriever #58、GIMLET #96、MolCA #95 | 冻结 LLM + 只训投影器 + `<graph>` 占位符;GNN 输出与 LLM token 空间特征级对齐;冻结 LLM 中交错插 GNN 层(零初始化门控);图 token + 文本化子图并用(两者互补);最短路距离作注意力偏置;Q-Former 把变长图压成定长 |
| 输出约束与可解释性 | PromptGFM #51、RAR #71、G-Retriever #58、TxGNN #19、BioPathNet #75 | 前缀树约束解码,只能输出轨迹里真实存在的 (agent, step);GraphMask / 路径梯度解释 + 忠实性指标 |
| 合成数据与弱监督 | GraphPFN #10、OpenGraph #30、GTA-RAG #109、GraphRAG-R1 #105 | 设计合成先验预训练;**回放验证合成样本是否可执行**(对应"注入的故障是否真导致失败");过程 + 终点奖励(但见 §3 第 6 条) |
| 评测协议 | GLBench #83、TxGNN #19、Actions Speak #65、NLGraph #82、GraphArena #84 | 源/目标图与标签空间都不相交的零样本协议;整领域留出;删边 / 截断特征 / 打乱邻接的依赖性检验;对抗子集;正确/次优/幻觉/缺失四级评分 |

## 3. 反面证据(对这个 idea 最不利的)

1. **零样本绝对性能低,且只在同类图之间验证过。** OFA ogbn-arxiv 5-way 零样本 46.19%;GIT held-out 零样本 27.50;TEA-GLM Cora 0.202;HiGPT 零样本 Mi-F1 0.32–0.51;REEF 1-shot 约 0.48。迁移都发生在引文↔电商这种同为短文本 TAG 的图之间。
2. **换格式就崩。** GraphArena 中 GraphWiz 换题目格式后只剩 0.2%–1.2%;HiGPT 跳过阶段 1 对齐训 100 epoch 仍失败;GraphLLM 把图 Transformer 换成 GIN/GAT 掉到 24.2%/17.3%。
3. **多域合并会负迁移。** MDGFM 去掉源域反而提升;PromptGFM 跨域 co-training 掉点;FedGFM+ 显示多领域聚合后表示坍缩;UniGraph 单数据集版胜过跨域版。
4. **图结构未必带来收益。** 组织空间 GNN(#43)不显著优于多实例学习,**打乱节点标签后性能不变**;GraphRAG-Bench 显示简单任务上图不如朴素 RAG;Nicheformer 不用图也很好。我们的合成数据有模板伪迹,这正是 #43 那种"粗信号足够"的情形。
5. **"LLM 读结构化文本"是很强的廉价对手。** Graph-as-Code(#65)零样本在长文本图上接近或持平 GNN;LogicRAG 推理时动态建结构超过预建图;InstructGLM / InstructGraph 纯文本 + SFT 在有监督下很强;Position 论文说简单展平无提升,GOFA 说图感知更好——结论互相冲突,只能靠我们自己的消融定。
6. **过程监督不能直接搬。** GraphRAG-R1 的"过程约束"约束的是检索次数,不是逐步正确性;GTA-RAG 的过程奖励依赖已知目标证据,真实失败轨迹没有这类金标。
7. **语义相关 ≠ 因果责任。**(推断)GFM-RAG 一类打分器学的是"与 query 相关",故障归因要的是"导致了答错",两者在共识类框架里会分离(例如多数派都错时,最相关的发言者未必是源头)。

## 4. 与本项目已有工作的关系(诚实评估)

- **MedHyperTrace 本身就是异构超图 + 关系感知超图卷积**(step/agent/phase 节点,agg/ctx/role/phase 超边)。"把轨迹建成超图"不是新东西;新 idea 的新颖性只能来自三点:(i) 一个模型跨框架零样本 / 轻量适配(图基础模型),(ii) 与 LLM 的耦合,(iii) 不针对框架手写的图构造。少了 (i),它就是 MHT v2。
- **方法不是当前瓶颈的证据仍然成立**:MHT 在 human-like v1 上四项指标都没超过"猜第一步"(HANDOFF §0.25);合成数据有注入模板伪迹(§0.29–0.30)。换成图大模型不会自动解决这两点,反而更依赖大规模预训练数据。
- 样例轨迹格式(TriageAgent `trajectory_Test-1_case2.json`:`stages.doctor_a/b/c/summarizer`、`discussion_rounds[].updates[]`、`final_output.consensus_detail`、`llm_call_log`)与 AEGIS 合成数据的消息序列格式完全不同 → 图构造必须 schema 无关(例如从 `llm_call_log` 的调用 + 输入依赖统一抽取),否则"零样本"会被手写解析器吃掉。

## 5. 必须对比的基线与必须做的消融(汇总自六段)

- **LLM 读轨迹:** Who&When 式提示、AEGIS / med-SFT、InstructGLM / InstructGraph 式文本化 + LoRA(同骨干)、Graph-as-Code(免训练)、LLM + 结构序列化(LogicRAG / Hyper-COT 式)。
- **图 + LLM:** GraphGPT / LLaGA / TEA-GLM 式图 token + 冻结 LLM、GOFA、G-Retriever(图 token + 文本化)、G-reasoner / GFM-RAG 式 GNN 打分 + LLM 读 top-k。
- **纯图:** MedHyperTrace、HYPER / REEF 直接移植、ULTRA(reified 星形图)、GIN / R-GCN、免训练 Emb w/ NA、PPR 传播。
- **平凡基线(项目已定):** 猜第一步、结构先验、模板检测器、空输出。
- **消融:** 去结构(同数据)、打乱邻接 / 打乱节点、超边 vs 二元展开、删边 / 截断文本、按注入策略(RC / PI)分开报。

## 6. 下一步(待与用户讨论)

1. **新颖性核查必须出这份文档:** 118 篇全是图学习论文,不含 MAS 故障归因文献。需单独检索是否已有"图 / 依赖图 / 信息流图 + 故障归因"的 MAS 工作(2025–2026),否则无法判断这个方向是否已被占。
2. 定任务形式:推荐先考虑"失败答案作 query 的 query-conditioned 超图打分器 + 关系文本驱动的跨框架机制(ULTRA/HYPER/REEF 思路)",LLM 只读 top-k 候选或接收图 token;再与"图 token 进冻结 LLM 生成答案"对比。
3. 先做一个低成本可行性检验:在已有 5 个合成框架上做留一框架(leave-one-framework-out)零样本,用 PI 子集评测,看结构是否带来超过平凡基线和 LLM 文本化的增益。这一步不需要新数据。
