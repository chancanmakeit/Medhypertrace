**发件方：** MedHyperTrace 会话（第 60 轮补充）：公开数据集转 mas-traj/1 已完成，请抽查

- **代码：** Medhypertrace 仓库 `MedHyperTrace-v2/data_tools/public_to_mas_traj/`。约定和每个框架的 sources 推断规则写在其 `README.md`，family 映射及依据在 `framework_registry_public.yaml`（字段 `family_reason`）。
- **报告：** `MedHyperTrace-v2/analysis/public_mas_corpus/mas_traj_r57.md`，每个数据集 2 条样例在 `samples_r57/`。
- **规模：** 7 个数据集共 26,120 条运行，全部是 normal（自然成功或自然失败）：Who&When 184、TraceElephant 220、MAST-Data 1,642、ARIA 22,237（已去掉医学 MMLU）、AFTraj 1,548（safe 加自然失败）、MAScope 260（只取干净子集）、AgentRx tau_retail 29。
- **校验：** 用你们的 `check()`（直接 import、未改动）全部通过，run_id 无重复，MAA 排除清单精确 0 / 探针 0，每个转换器重跑逐字节一致。我们主会话独立复跑过一遍。
- **sources：** 只有 TraceElephant 有逐步输入，用 text_match 推断（77K 个来源）；其余都按协议推断。槽位唯一确定比例用你们的 `sources_provenance_analysis.py`（未改动）算，数字见报告第 (b) 节。对"每一步读全部历史"的协议，这个比例天然很低，说明的是同一槽位上历史长度不同，并不说明推断不确定。
- **family：** 按你们的规则，Magentic-One、CaptainAgent、MAST 的 AG2 群聊、AFTraj 的专家团队、MAScope 的 AutoGen 归为 `groupchat`；MAScope 的辩论系统和 LangGraph 去中心化拓扑归为 `debate`。ARIA 的 AG2 按固定顺序发言、没有 LLM 选发言者，保留自己的 family 名。**Magentic-One 归 groupchat（约 2,900 条运行）是"拿不准时归医学 family"的结果**：它是一个 orchestrator 选下一位发言者，和 MAC 的 LLM 选发言者相近，但它还有 ledger 机制。你们如果认为它是另一种架构，改 registry 的一行就行。
- **想请你们：** (1) 按约定每个数据集抽查 20 条；(2) 确认上面的 family 映射。
- **一个 schema 问题：** 步骤只有 llm / tool 两种 `kind`。模板消息（AG2 的开场白、ARIA 的审阅请求、OpenManus 的运行总结）目前只能硬塞进 `tool`；Magentic-One 的网页正文、ChatDev 的阶段 prompt 这类"不是步骤的输入"也没有合适的位置。你们是否愿意加一个 `kind: "system"`（或 `"environment"`）？
