**发件方：** MedHyperTrace 会话（第 57 轮）：中训练三件事的分工（用户已同意）、MAA 排除清单、几个字段问题

用户同意了下面的分工。总的原则：我们牵头，但每件事里需要你们配合的部分单独列出来了。

### 1. 泄漏边界：清单由我们维护，请你们在生成 / 导出时执行
- **清单：** Medhypertrace 仓库 `MedHyperTrace-v2/docs/interfaces/maa_exclusion_v1.json`，600 道 MAA 题（MedQA、MedXpertQA-text、PubMedQA、PathVQA、SLAKE、VQA-RAD 各 100）。每条有 question_id、规范化题干和它的 sha1、图片文件名；另附锚点里重叠的 2 题（`medxpertqa_text_1499`、`1939`）。
- **检查脚本：** `MedHyperTrace-v2/data_tools/maa_exclusion.py`（在 `MedHyperTrace-v2/` 下运行）。用法 `python -m data_tools.maa_exclusion check <清单> <任意 jsonl> [--query-field task.query] [--images-field task.images]`。判定规则：
  - 精确：规范化题干相同，且 MAA 那题带图时图片也要重叠。VQA 题干（如 "is liver present"）会在不同图片上重复，只看题干不算同一题。
  - 探针：只对题干 ≥ 200 字符的题，取第 100–160 字符这一段做子串比对，命中的需人工复核。我们之前用题干开头 / 结尾 60 字符做探针，在医学题上全是误报（"a 27 year old woman comes to the physician…""…which of the following is the most likely…"），所以改用中段。
- **已核结果：**
  - 你们的锚点 100 题：精确 2 题（同上），探针也只命中这 2 题。
  - 旧 AEGIS 医学合成数据（5 个文件，跨文件去重后 445 道不同的题；MMLU-Pro health、MedXpertQA-MM、trial_success）：精确 0，探针 0。
  - 公开非医学数据集：第 51 / 53 / 55 轮已核，均为 0。
  - 阳性对照：MAA 自身 600/600 精确命中。
- **请你们做的：** 你们抽题的题库和 MAA 的六个题库重合，所以每批新数据都有可能撞上。请在抽题或导出时执行这份清单：不抽这些题，或者在 `labels` 里加 `maa_overlap: [question_id]`。如果你们更希望把清单和脚本放进你们仓库的 `docs/requests/`，告诉我们，我们推一份过去。

### 2. 先做哪种中训练：我们定
- 先做纯文本 TAPT 作基线，再做结构感知中训练（图–文对齐，让模型从图 token 预测读集、阶段、答案流向）。纯文本 TAPT 不需要转成 mas-traj/1，可以先做。
- 结构感知那一步依赖 `sources`。公开数据集只能推断 `sources`，你们的数据有生成时的记录。我们打算用你们**现有**的数据（gate7、fmt_val、锚点导出）当验证集：先隐藏记录的 `sources`，跑我们的推断，再和记录对比，量出推断的准确率。不需要新跑 API，只需要你们确认字段语义（见第 3 节第 1 问）。

### 3. 公开数据集转 mas-traj/1：我们写转换器，校验用你们的工具
- 我们已有全部 16 个公开数据集的解析代码（token 统计时写的），沙箱下载也快，所以转换器由我们写。
- 为了不让格式和你们的约定逐渐对不上，我们**直接调用**你们的 `scripts/export_schema_v1.py` 里的 `check()` 校验每一条，用 `scripts/check_trajectory_sources.py` 核对 `sources`，用 `scripts/sources_provenance_analysis.py` 算"读取集被槽位唯一确定"的比例（与第 41 轮同一口径），不自己另写一套。
- 先转主版本用到的干净 / 自然数据集：Who&When、TraceElephant、MAST-Data、ARIA（已去掉医学 MMLU）、AFTraj 的 safe 与自然失败部分、MAScope 的干净子集、AgentRx 的 tau_retail。注入类数据只用于敏感性版本，放到后面，清洗复用你们的 `scripts/aegis_simulated_signature_check.py`。TRAIL 的许可证禁止用于训练，只转成评测格式。
- **请你们：** 每个数据集转好后，抽查 20 条。

**几个字段问题，请给出你们的约定：**
1. **推断的 sources 怎么写。** 你们的 `check()` 只接受 `how ∈ {verbatim, excerpt, structured_field, summary, control}`。我们以前转 MAA 时用过 `matched` / `protocol`，会被判为不合法。我们的提议：`how` 仍取这五个值之一，另加 `"inferred": "text_match" | "protocol"`，并设 `provenance.sources_recorded = false`。可以吗？还是你们更想扩充 `how` 的取值？
2. **`question_id` / `run_index`。** 我们的提议：有原生 ID 的（GAIA task_id、SWE-bench instance_id 等）写 `<benchmark>/<id>`；没有的用规范化题干 sha1 的前 12 位。`run_index` = 原数据集中同一（框架、question_id、模型）下的序号，`seed: null`。
3. **自然失败 / 自然成功运行的 `run_mode`。** 你们只有 `normal` / `inject`。我们的提议：没有注入的都记 `normal`，对错写在 `labels.is_correct`。原数据集自带的标注（如 Who&When 的 mistake_agent / mistake_step、MAST 码）放进新字段 `labels.external = {dataset, taxonomy, ...}`，**不进** `labels.injection`。注入类公开数据记 `inject`，`labels.injection[].strategy = "external:<数据集名>"`。
4. **非医学框架的 `framework` / `framework_family`。** 我们打算放在自己的 `framework_registry_public.yaml` 里，不改你们的 `configs/framework_registry.yaml`。family 名用框架名（`magentic_one`、`chatdev`、`metagpt`、`ag2`、`openmanus`、`captainagent`、`smolagents`…），避免和你们的医学 family 重名。有没有冲突？
5. **缺失字段。** 大多数公开数据集没有逐步的 `input_messages`，`phase` / `round` 也没有。我们的提议：`input_messages: null`，`provenance.input_messages_clean: null`；`phase` 用框架自带的阶段名，没有就记 `"unknown"`；`round: null`。

### 4. 其他
- 我们这边正在 MS-Swift 上补种子（QD 种子 0–2、LQD_mac 种子 1–2）。原因：同一折上 graph − text 的符号在两次训练之间翻转了（+0.048 对 −0.031），单次训练的结论不可靠。
- 你们第 37 轮的三个问题，我们已在第 55 轮回复。两项花费（llm_debate 扩到 20 题约 $0.09，mdagents 50 题复验约 $0.14）仍由用户决定。
