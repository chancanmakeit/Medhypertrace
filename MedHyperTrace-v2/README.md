# MedHyperTrace-v2：多智能体轨迹的超图基础模型（HGFM）

> 状态（2026-10-21，第 34 轮）：**数据与建图已完成，编码器 v0 第一阶段训练进行中**。下文"已实现 / 设计中"分开写，请勿把设计中的部分当作已有结果引用。
> **当前设计：`docs/design/HGFM_design_v0.2.md`**（文献 → 组件逐项对照）；旧草案 v0.1 只保留作历史记录。文献依据：`docs/lit/`。

## 1. 一句话

把任意医学多智能体系统（MAS）的运行轨迹，转成**同一种格式的文本属性有向超图**，用一个**跨框架共享**的超图编码器（后续再接冻结 LLM）判断"哪一步、哪个 agent 出了什么错，是否导致答错"；目标是对**没见过的 MAS 框架零样本**，最多只做轻量适配。

## 2. 和 v1 的区别

| | MedHyperTrace-v1 | MedHyperTrace-v2（HGFM） |
|---|---|---|
| 定位 | 针对 AEGIS 合成数据的**任务特定**归因模型 | 面向多框架的**超图基础模型**，零样本迁移是首要目标 |
| 输入 | 每个框架的原始日志由专门的解析器读入（`common/data.py`） | 统一轨迹格式 `mas-traj/1`（与 medical-aegis 共同制定）：标签与轨迹物理分离、干净输入、显式读取集 |
| 超边从哪来 | 规则：agg / ctx（输入中出现前序输出前缀）/ role / phase，**无向** | 生成时记录的**有向读取集**（谁读了谁，带 `how`），另有控制依赖（选人、招募）、事件（投票轮、讨论组、并行组）、agent、final；记录缺失时才回退为文本匹配或按协议推断，并标注证据等级 |
| 关系类型 | 4 种固定类型，每种一个投影矩阵 | 通用关系集合（read / read_rev / control / event / agent），不依赖框架词表；计划改为由关系文本生成参数（见 §4） |
| 训练数据 | AEGIS 合成注入数据，含模板伪迹，只有失败轨迹 | ① MedAgentAudit 的 14,370 条**真实自然失败**轨迹（6 个 MAS × 4 个 LLM）；② medical-aegis 新生成的 14 个框架数据（normal 每题 K 次 + 注入），注入数据先过"签名门槛"（文本 AUROC ≤ 0.7） |
| 学习目标 | 最早注入步（listwise）+ agent×FM 配对头 | 已实现：逐步故障码（多标签）+ 运行级结果（是否答错）；设计中：自监督预训练（掩码重建、读取超边填充、成对运行分歧定位）、责任层微调 |
| 是否用 LLM | 否 | 设计中：超图编码器打分 → top-k 候选以图 token 送入冻结 LLM，约束解码到真实存在的 (agent, step) |
| 评测 | 合成测试集 + MAFA human-like；平凡基线对照 | 留一家族零样本、锚点任务（固定 100 道医学选择题）、真实人工标注（MedAgentAudit 400 例、MAFA），每项都和"去掉结构"及参考标注者对照 |
| 已知问题 | 在 human-like v1 上没超过"猜第一步"；合成数据存在模板捷径 | 结构的增益尚未证实（AFANet、GRADE 的证据都偏负面），这是第一阶段要回答的问题 |

**诚实的说明（第 35 轮更正）：** 已实现的 `hgfm/model_v0.py` 本质上是按关系类型分参数的均值消息传递（HGNN+ / R-GCN），任务向量只是拼接，**不含任何超图基础模型特有的机制**，与 v1 同源。它现在只作为**结构基线（HGNN-baseline）**。v2 的方法本体是 HGFM v0.2（见设计文档），其中以下组件尚未实现：
- C1 HYPER 式位置感知 k 元消息；
- C2 HYPER / ULTRA 关系图；
- C3 IHP 超边文本指令；
- C4 HyperG 查询感知 edge→node；
- C5 HypeBoy 超边填充自监督；
- C6 HyperG / TEA-GLM 软 token 进冻结 LLM；
- C7 约束解码；
- C9 只用结果标签的责任分配（SOAP 思路）。

## 3. 方法（当前版本）

1. **统一轨迹超图**（`hgfm/uth.py`）
   - 节点：task、observation、step（每次 LLM 或工具调用，文本 = 输出）、agent、final。
   - 有向超边：
     - `read`：本步输入里放进了哪些前序步；
     - `read_new`：该 agent 第一次读到的部分；
     - `control`：被谁选中或招募。
   - 无向超边：
     - `event`：同一投票轮、讨论组或并行组；
     - `agent`：同一 agent 的全部步骤。
   - 整个构建过程**不写任何框架专用代码**，14 个 medical-aegis 框架和 6 个 MedAgentAudit MAS 都走同一路径。
2. **编码器 v0 = 结构基线 HGNN-baseline**（`hgfm/model_v0.py`；方法本体 HGFM v0.2 见设计文档）
   - 节点初值 = MLP(输出文本嵌入、角色/阶段嵌入、少量结构标量（是否给出答案、与最终答案或本轮多数是否一致、轮次、读者数等），任务向量)；
   - 2 层"节点 → 超边 → 节点"消息传递，每种关系类型一套参数，`read` 正反两向都传；
   - 两个输出头：逐步的故障码 logits 和运行级 logits（是否答错、角色分配故障）。`layers=0` 即"去掉结构"的消融，输入特征完全相同。
3. **数据与审计**
   - `data_tools/maa_to_mas_traj.py`：MedAgentAudit 转 mas-traj/1；
   - `data_tools/maa_human_eval.py`：把 400 例人工标注对齐到具体步骤；
   - `hgfm/audit_schema_v1.py`：泄漏、来源和 token 侧信道审计；
   - `data_tools/clean_inputs.py`、`old_data_filters.py`：旧 AEGIS 数据的干净输入恢复和标签有效性过滤；
   - `analysis/pilot_20261020.py`：注入捷径量化，即签名门槛。
4. **第一阶段实验**（`hgfm/train_maa.py`）：只在 MedAgentAudit 体系内进行（与 MAST 体系严格分开）。弱监督用 LLM 审计员的标签，评测真值只用 400 例人工标注；做留一 MAS 和题目不重叠两种划分，比较"有结构 vs 无结构"、"不给金标准 vs 给金标准"。

## 4. 参考和借用了哪些文献

**逐项对照（每篇对应哪个组件、原文机制、在 MAS 上怎么改）见 `docs/design/HGFM_design_v0.2.md` §1–§2。** 摘要如下：

- **超图基础模型（方法本体）**
  - HYPER（#54）：位置感知 k 元消息、关系图零样本，即 C1、C2；
  - IHP（#53）：超边文本指令和冻结提示的 adapter，即 C3；
  - HyperG（#93）：查询感知传播和超边软 token 进 LLM，即 C4、C6；
  - HypeBoy（#52）：超边填充自监督，即 C5；
  - Beyond Graphs / LLM4Hypergraph（#92）：文本化超图基线，也是"编码而不是文本化"的依据，即 C8；
  - 辅助：ULTRA（#3）、REEF（#50）、GFM-RAG（#108）、TEA-GLM（#98）、GraphGPT（#55）、G-Retriever（#58）、G-reasoner（#85）、PromptGFM（#51）、COSMOS（#38）。
- **基于图的 MAS 故障归因**
  - 读取超边由二元依赖边推广而来：GraphTracer、AgentTrace、CHIEF、DCFA、EMFA；
  - 边的证据等级与伪造对照：GRADE；
  - 只用结果标签的责任分配：SOAP、Node Contribution Backpropagation；
  - 只用正常运行的自监督与异常检测：AgentTether、BlindGuard；
  - 节点异常分数基线：G-Safeguard、XG-Guard；
  - 故障码传播先验：EDGE；
  - 反事实验证责任标签：CausalFlow、Causal Agent Replay；
  - 免训练对照：Adaptive Influence Graphs、FALAT、STRACE、CDC-MAS；
  - 新颖性边界：HPFA、HyperAgent、MAGE；
  - 最接近的竞品：AFANet；
  - 数据与故障体系：MedAgentAudit。
- **底层**：HGNN / HGNN+、R-GCN，即 v0 结构基线所用，与 v1 同源。

**新颖性的边界：**
- "用超图做故障归因"已有 HPFA，但它是单智能体推理轨迹，超图也没有被编码；
- "超图建模 MAS"已有 HyperAgent 和 MAGE，但它们做的是拓扑优化和记忆，不做归因；
- 目前没有先例的是：MAS 轨迹的**编码后**超图与 LLM 推理结合，以及跨 MAS 框架零样本的超图基础模型。

## 5. 运行（在本目录下）
```bash
pip install -r requirements.txt
python data_tools/maa_to_mas_traj.py <MedAgentAudit release dir> maa_mas_traj.jsonl
python data_tools/maa_human_eval.py  <MedAgentAudit release dir> maa_human400.jsonl
python -m hgfm.embed_maa  maa_mas_traj.jsonl emb/
python -m hgfm.train_maa  maa_mas_traj.jsonl emb/ maa_human400.jsonl anchor_overlap_qids.json out/
python -m hgfm.audit_schema_v1 <mas-traj/1 export>          # 审计 medical-aegis 导出
bash scripts/issue_inbox.sh                                  # 查看 medical-aegis issue #1 新评论
```
