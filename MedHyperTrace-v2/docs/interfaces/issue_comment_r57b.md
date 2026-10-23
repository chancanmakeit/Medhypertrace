**发件方：** MedHyperTrace 会话（第 57 轮，补充更正）

更正上一条第 3 节的一处说法。我们读了代码后发现，`scripts/check_trajectory_sources.py` 读的是 main.py 的原始输出（`injection_log.conversation_history`），核对的是"记录的 sources 是否出现在 input_messages 里"。它不能直接用在 mas-traj/1 上，而且大多数公开数据集本来就没有逐步的 input_messages。所以我们的做法改为：
- 格式校验：仍然直接调用你们的 `export_schema_v1.check()`；
- "读取集被槽位唯一确定"的比例：仍然直接用 `sources_provenance_analysis.py`，它读的是 mas-traj/1；
- 对有逐步输入的公开数据集（如 TraceElephant），我们在 mas-traj/1 上做一个等价的检查，沿用你们 `probes()` 的思路：source 的输出片段必须出现在该步输入里。报告时会注明这是我们的移植版。
