# MedHyperTrace-v2：多智能体轨迹的超图基础模型（HGFM）

> 状态（2026-10-21，第 34 轮）：**数据与建图已完成，编码器 v0 第一阶段训练进行中**。下文"已实现 / 设计中"分开写，请勿把设计中的部分当作已有结果引用。
> 设计草案：`docs/design/HGFM_design_v0.1.md`；文献依据：`docs/lit/`。

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

**诚实的说明：** 目前已实现的编码器 v0 在网络结构上和 v1 很接近（按关系类型做均值消息传递）。v2 现阶段的差别主要在**数据、建图方式、训练目标和评测口径**；"基础模型"所依赖的几块（自监督预训练、关系文本条件化、LLM 耦合）还在设计中。

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
2. **编码器 v0**（`hgfm/model_v0.py`）
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

编号对应 `docs/lit/graph_llm_118/`（图大模型 118 篇解读）；MAS 归因文献在文献仓库 `chancanmakeit/graph-based-mas-fault-attribution-papers`。

**直接借用的核心技术（已实现）**
- **超图消息传递的基本形式**：HGNN（Feng et al., AAAI 2019）/ HGNN+（Gao et al., TPAMI 2022）的"节点 → 超边 → 节点"两阶段传播，以及按关系类型分参数（R-GCN，Schlichtkrull et al., 2018）。这部分与 v1 同源。
- **查询条件化、一次前向给所有节点打分**：GFM-RAG（#108）和 ULTRA（#3）的思路。用任务（失败的问题）作为查询，对每个 step 节点同时输出归因分数。v0 采用的是简化形式：把任务向量拼接到每个节点上，还不是 labeling trick。
- **信息依赖图 / 读取集**：GraphTracer（AAMAS 2026）的 Information Dependency Graph、AgentTrace（ICLR 2026 workshop）的 data-dependency 边、CHIEF（arXiv 2602.23701）的因果图。v2 把这些"二元依赖边"推广为**一次调用读多个前序步的有向超边**，并要求在生成时记录，而不是事后靠 LLM 抽取。
- **边的证据等级、度数匹配的伪造对照**：GRADE（arXiv 2606.22741）。对应 v2 的 `how` 字段（verbatim / excerpt / structured_field / matched / protocol / control）和计划中的消融。
- **控制依赖**：受 MAC（pyautogen 群聊选人）和 KAMAC（运行中招募）的启发，单独建 `control` 超边。

**设计中、准备结合的技术**
- **跨 schema 零样本**：ULTRA（#3）、HYPER（#54）的关系图加位置交互（对关系改名保持不变，HYPER 本身就处理 k 元超边）；REEF（#50）用关系文本经超网络生成参数；HiGPT（#61）用自然语言描述类型。对应 v2 计划用 `framework_description` 和关系文本条件化编码器。
- **超图自监督**：HypeBoy（#52）的超边填充，用于读取超边填充预训练；HyperBERT（#99）。
- **图与 LLM 耦合**：TEA-GLM（#98）把 GNN 表示和 LLM token 空间做特征级对齐、零样本；GraphGPT（#55）、LLaGA（#56）冻结 LLM、只训投影器；GOFA（#6）交错的 GNN 层；HyperG（#93）把超边表示作为软 token 输入 LLM；G-Retriever（#58）证明图 token 与文本化互补。
- **约束解码**：PromptGFM（#51）的前缀树约束、RAR（#71）的路径幻觉问题，用于把 LLM 输出限制在真实存在的 (agent, step) 上。
- **成对运行分歧伪标签**：HPFA（COLM 2026）用成功与失败轨迹对比定位根因。v2 改为定义在 `structured.answer` 等语义字段上。

**必须正面对比的直接竞争工作**
- **AFANet**（arXiv 2608.18575）：轮次图加 GCN，在 AEGIS-Bench 上训练、迁移到 Who&When。与 v2 最接近，而且它的消融显示结构增益很小。
- **CHIEF / Adaptive Influence Graphs / DCFA / EDGE / EMFA**：LLM 建图、LLM 推理，免训练。
- **GraphTracer / AgenTracer**：图或 RL 加微调 LLM。
- **MedAgentAudit**（arXiv 2510.10185）：故障体系、数据和审计员。它做的是群体层面的审计，v2 做的是单条轨迹层面的定位和责任归因。

**新颖性的边界（据文献检索，详见 `docs/lit/graph_mas_attribution_positioning.md`）**
- "用超图做故障归因"本身已被 HPFA 占用，但 HPFA 是单智能体推理轨迹，超图也未被编码。
- "把编码后的 MAS 轨迹超图和 LLM 推理结合"、"跨 MAS 框架零样本的超图基础模型"目前没有先例。

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
