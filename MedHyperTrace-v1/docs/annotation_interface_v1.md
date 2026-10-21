# 标注数据接口说明（人机协同标注 → 故障归因方法）

**版本：** v1 · 2026-10-08 · 对应 MAFA v0.7.44
**适用：** 大项目「医学多智能体系统故障归因」下的两个子项目。
- **人机协同自动化标注（本文的提供方）**：产出轨迹的人类标注。
- **多智能体系统故障归因方法（使用方）**：用这些标注做监督或评测。

两边只通过本文列出的文件交换数据。字段有任何改动，先改本文、升版本号，再改代码。

---

## 1. 数据包（审查对象）

| 文件 | package_id | 体系 | 体系签名 | 码数 |
|---|---|---|---|---|
| `review_packages/mast_v1.json` | `MAST-T0:321a19c96e-52013c8e` | MAST 种子 v1（全 14 码） | `T0:321a19c96e` | 14 |
| `review_packages/medagentaudit_v1.json` | `MedAgentAudit-T0:210546d507-52013c8e` | MedAgentAudit | `T0:210546d507` | 10 |

- 两个包都是 360 条轨迹：答错（`split=faulty`）180 条，答对（`split=clean`）180 条。四个框架 `mdagents`、`clinical_agent`、`clinical_agent5`、`dylan` 各 90 条。两个包的轨迹集合相同。
- `stage4_enabled = false`：体系是固定的，审查期间不会自进化。
- **标签只对它所属的 package_id 有效。** 体系签名或数据包变了，旧标签就不能直接沿用。导入脚本会拒绝把不同包的标签混在一起。

**MAST 码：** FM-1.1 违反任务规定 · FM-1.2 违反角色规定 · FM-1.3 步骤重复 · FM-1.4 丢失对话历史 · FM-1.5 不知终止条件 · FM-2.1 对话重置 · FM-2.2 未要求澄清（医学化定义为「没有指出信息缺口」） · FM-2.3 任务偏离 · FM-2.4 信息隐瞒 · FM-2.5 忽视其他智能体输入 · FM-2.6 推理与行动不一致 · FM-3.1 过早终止 · FM-3.2 缺少或不完整的验证 · FM-3.3 错误的验证

**MedAgentAudit 码：** 1.1.1 输入理解时的事实幻觉 · 1.2.1 忽视或误读模态信息 · 2.1.1 角色与临床任务不匹配 · 2.1.2 未调用专科知识 · 2.2.1 重复初始观点（回音室） · 2.2.2 协作中的冲突未解决 · 3.1.1 正确的少数意见被错误共识压制（**需对照正确答案**） · 3.1.2 权威偏见扭曲推理 · 3.1.3 忽视推理中的矛盾 · 3.2.1 跨轮自相矛盾

## 2. 轨迹 ID

格式：`<framework>::<源文件名(不含扩展名)>#<行号5位>#<原始记录id>`
例：`mdagents::mdagents_fm_clean_none_none-allfalse#00018#MM-51`

**原始记录 id 不唯一**：同一个 faulty 文件里有 10 个 id 重复，另有 3 个 id 同时出现在同框架的 faulty 和 clean 文件中。所以必须用整串 ID 做键，不能只用 `MM-51` 这一段。步骤 ID 是 `s01`、`s02`……，在同一条轨迹内按顺序编号；智能体 ID 形如 `Recruiter-0`、`Expert-2`、`Aggregator-0`。

## 3. 专家标签文件（工具导出，`format = "mafa-review-labels"`）

```
{format, format_version: 1, tool_version, package_id, taxonomy, taxonomy_signature,
 reviewer: {name, id, kind?}, storage, exported_at,
 labels: {<trace_id>: Label}}
```
Label 的字段：
- `status`：`done` / `in_progress` / `skipped`。**只有 `done` 的标签可以使用。**
- `codes[<code>]`：`{decision: present|absent|unsure, agents: [uid], step: sNN|null, note, prefilled}`。`prefilled=true` 表示这个判断是按两个模型一致的意见预填的。
- `agents[<uid>]`：`fault` / `ok` / `unsure`（智能体层）。
- `earliest_step`：`sNN`，或 `none` 表示没有故障。
- `novel["primary:0"]`：`{decision: real_new|is_existing|not_failure, code}`，是专家对模型提出的新模式的裁决。
- `blind`、`blind_first`：盲审条目在看到模型意见**之前**的初判，包括 codes、agents、earliest_step。**估计模型准确率时，只有这一部分是无偏的。**
- `outcome_viewed`：专家看过正确答案的位置（`global` 或某个码）。

## 4. 回收后的产物（`scripts/import_review_labels.py`）

- `anchors.jsonl`：`{trace_id, slot_key: "mode::<code>", label: 0|1, reviewer, source: "human"}`。只收录 `status=done` 且判断为 present 或 absent 的码；`unsure` 不收录。**这是方法项目可以当作人类真值使用的唯一文件。**
- `labels.jsonl`：每行对应一个（审查者、轨迹、码），含 `source`（human 或 llm）、`decision`、`blind_first`、`agents`、`step`、`prefilled`、`note`。
- `report.json`：模型与人工的一致性（全部 / 盲审子集），以及审查者之间的一致性（按 human-human 和 human-llm 分开统计）。

## 5. 两版标签

| 版本 | 来源 | `reviewer.kind` | 能否当真值 |
|---|---|---|---|
| human-version | 招募的人类专家，用审查工具标注 | 无此字段，或 `human` | 能（经 anchors.jsonl） |
| human-like-version | Claude 按专家协议扮演审查者（`scripts/llm_expert_review.py`） | `llm` | **不能**。只能用来和人类版对比，绝不能当训练或评测的真值，也不能和人类标签合并 |

human-like-version 目前**暂停**：只完成了 20 条，用户嫌贵叫停（详见 RUN.md §35）。

## 6. 已知的数据问题（使用前必读）

1. **`outcome.final_answer` 不是系统的答案，而是正确答案。** AEGIS 源数据里的 `answer` 字段存的是标准答案：1,552 条记录（答错 1,112 条，答对 440 条）全部满足 `answer == ground_truth`。所以在全部 180 条答错轨迹上，数据包里的 `final_answer` 都等于正确答案，同时 `is_correct = false`。**判断对错请只用 `is_correct`（即 `split`）。** 系统的实际答案需要从最后一步的输出中抽取。源数据的 `verification.regex_extracted` 也不可靠：答错的轨迹里有 264 条为空，另有 19 条等于标准答案。受影响的地方：审查工具里显示的「系统答案」；MedAgentAudit 3.1.1 的 Stage 1 标注（这个码需要看正确答案，标注模型在答错轨迹上收到的是自相矛盾的结局块，例如「正确答案 D / 系统答案 D / 系统答对 False」）。MAST 没有需要对照正确答案的码，Stage 1 不受影响。（2026-10-08 发现，尚未修复，见 RUN.md §36。）
2. **框架固有码**（`meta.framework_constant_codes`，只有 MAST 包有）：MDAgents 上的 FM-1.1、FM-1.2，ClinicalAgent 上的 FM-1.2，在答对和答错的会诊中出现得同样频繁，反映的是框架设计，不是导致答错的原因。拿它们当「故障 → 答错」的监督信号会学到框架身份。
3. **样本不是随机抽的**：答错和答对各 180 条，都是每个框架文件的前 45 条。正式轮次是否改用带固定种子的分层随机抽样，还没定。
