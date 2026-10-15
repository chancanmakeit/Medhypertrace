# MedHyperTrace 会话交接文档

**最后更新:** 2026-10-09(第 2 个会话,Claude Code 云端沙箱) · **原始版本:** 2026-10-08
**项目:** 医学多智能体系统故障归因 → 本仓库是其中的「故障归因方法」子项目(另一个子项目「人机协同自动化标注」提供人类标注,接口见 `docs/annotation_interface_v1.md`)
**用户:** Alvin Chan(清华,ML/NLP researcher;偏好直接的 peer-level 技术交流、要诚实批评而非附和、要求实证核对而非臆断)

> **新会话开场顺序:** ① 本文 §0(当前状态)→ ② 最新的 `RUN_v0.<N>.md`(讨论记录,文件名带版本号,N=轮次)的最后两轮 → ③ 按需读 `RUN_EXPERIMENTS.md`(完整实验命令)和 `docs/`。
> **仓库:** https://github.com/chancanmakeit/Medhypertrace (**私有仓库**,2026-10-09 起)。§一 以下是 2026-10-08 旧会话的内容,§0 中与之冲突的以 §0 为准。

---

## 0、当前状态(每轮更新,以此为准)

### 0.1 环境(2026-10-09 实测)
| 项 | 状态 |
|---|---|
| 工作目录 | `/home/claude/medhypertrace`(本仓库的 git clone,推送走会话 git 代理,**不需要 token**) |
| torch | **可用**:沙箱现有 30G 磁盘,CPU 版 torch 2.14.1 已装上。HGNN 训练 + `hgnn_unified_eval.py` 在 CPU 上已跑通(clinical_agent 2 epoch 约 10 秒)。旧会话"沙箱装不了 torch"的限制已不存在。仍无 GPU,LLM 基线(Who&When/med-SFT)仍需用户服务器 |
| 机器 | 2 核 CPU / 7G 内存 |
| 数据集 | **在仓库里**:`data/AEGIS-custom-dataset-8-13.7z`(11.5M);嵌入缓存 `data/emb_cache/mxbai/`(只有 clinical_agent、mdagents)和 `baselines/aegis_sft_ood/eval_samples/` 也已入库。新会话恢复:clone 仓库后跑 `bash scripts/restore_env.sh`(无参数即用仓库内的 .7z,解压到 `/home/claude/aegis_813`,装依赖含 CPU torch,跑 validate),再 `export MHT_DATA_DIR=/home/claude/aegis_813/AEGIS-custom-dataset`。**不需要用户再上传** |
| 被 .gitignore 排除 | 解压后的 `data/AEGIS-custom-dataset/`、`*.env`(API 密钥) |
| API 端点 | 用户 2026-10-09 提供,完整内容(含密钥)存在 **Project doc `claude/api端点`**(用 Projects 工具 `project_read` 读取)。新会话需要时读它,写到仓库外的 `/home/claude/.mht_api.env`(权限 600)。**密钥绝不进 git**(即使仓库私有)。提供方:aiberm(claude-opus-5)、aihubmix(gpt-5.6-sol-disc,有 logprobs)、deepseek(deepseek-flash)、阿里云(qwen3.8-flash;chat 和 responses 两个 base_url 不同)、智谱(glm-5.3-flash)、小米 MiMo(mimo-v2.6-flash/pro;不返回 logprobs,推理开关用 `extra_body={"thinking":{"type":...}}`)。**调用前先小规模试跑估算成本,停下来问用户** |

### 0.2 本会话已核对的事实
- 两个代码包(`medhypertrace.zip` 和 FULL 包里的 `medhypertrace/`)逐文件一致。
- 接口文档 §6.1 的 `answer==ground_truth` 问题:在本项目的 5 个 AEGIS 合成文件上同样成立(5231/5231 条 `answer == ground_truth.correct_answer`,全部 `is_correct=False`)。**本项目代码不受影响**:`common/data.py` 把它当正确答案(`correct_answer`)用,没有任何地方把它当系统答案;NLI 的 `--factuality_ref gold-answer` 用的也是正确答案,语义正确。
- 接入人类标注时:只能用 `anchors.jsonl`(`status=done`、present/absent);`reviewer.kind=llm` 的 human-like 标签**绝不能**当真值;MAST 包的框架固有码(MDAgents 的 FM-1.1/1.2、ClinicalAgent 的 FM-1.2)不能当「故障→答错」监督信号。轨迹 ID 必须用整串做键。

### 0.25 MAFA 联合评估(2026-10-09 第 5 轮)
- MAFA 仓库 `chancanmakeit/MAFA-human-ai-annotation` 在本会话**只读**,克隆在 `/home/claude/mafa-human-ai-annotation`,锁定 `ce6f8f7`(第 5 轮评估时为 `908bc74`);AEGIS 原始记录需在其根目录跑 `bash scripts/fetch_data.sh`(约 1.9G,很快)。新会话需重新 add_repo(只读)+ 克隆 + checkout。
- 评估代码在 `eval_mafa/`,产物在 `eval_mafa/out/`,详见 `eval_mafa/out/error_analysis_notes.md`。结论:可行性成立,**方法在 human-like-v1 上四项指标都没超过「猜第一步」基线**,智能体排序 AUROC 0.41。
- MedHyperTrace 没有保存权重;评估时按默认超参在合成训练集上现训(每框架 ~1–2 分钟 CPU)。
- **发现:** 合成测试集上 step head 对「猜第一步」在 mdagents 只高 1 个点(0.693 对 0.680),主表 Step-Acc 需加此对照。

### 0.26 合成标签的语义与伪迹(第 6 轮,`analysis/injection_propagation.py`)
- MAFA 人类版将分「缺陷层 / 责任层」。AEGIS 合成标签 = 被注入集合,两层都不是:答案级代理显示有作答的被注入智能体中 34%–70% 的最终表态 ≠ 最终错误答案(按框架;mdagents 59%)。
- **注入伪迹:** 被注入步骤答案为 A 的比例远高于未注入步骤(mdagents 51% 对 18%,dylan 55% 对 11%);训练表层特征的方法会学到这个捷径。改进方法前先处理(例如在合成集上做去伪迹的消融)。
- llm_debate 17% 轨迹有计划注入却未应用的智能体,仍被标为故障(标签噪声)。

### 0.27 MAFA 人类版标签 = 接口 v3(第 7 轮,待对方提交号)
- 两层:缺陷层(码,依赖体系)+ 责任层(每个存在码标「促成答错:是/否/不确定」,必选至少一个下游被采用步骤)。另有「无对应码的缺陷」行;答错且追溯不到须勾「找不到可追溯的缺陷」→ 两种逃逸可分开统计(体系覆盖不到 / 完全追溯不到),正是 Nature 故事的逃逸率。
- 评测主目标:智能体层 = 责任层 agent_auroc(缺陷层辅助);步骤层 = 最早责任步(最早缺陷步辅助)。
- 本方提出的未决问题:31% 的存在码挂多个智能体,责任若挂在整码上会过度归因 → 建议挂在(码, 智能体, 步骤)实例上。
- MAFA `data/simulated/` 与本项目合成数据是同一份(无 llm_debate)。注入伪迹的比例两边抽取器结果不一致(dylan 差异大),引用前需统一抽取器。

### 0.28 MAFA 接口 v3 已落地(第 8 轮,MAFA `cc1606f` / 0.7.49)
- 本地 MAFA 副本已切到 `cc1606f`(只读)。人类版到位后:`import_review_labels.py` 产出 `attribution.jsonl` → `eval_attribution.py --layer responsibility|responsibility_any`(主)/ `defect`(辅)。我们的 `medhypertrace_pred.jsonl` 格式不变。
- 已向 MAFA 提交 `apply_layer` 修正(`eval_mafa/mafa_patches/apply_layer_unsure.py`):贡献「不确定」的智能体和 coded 层里只经无码缺陷负责的智能体不应作 AUROC 负例。正式评测前确认对方是否采纳,否则用本地补丁版评分并注明。
- MAFA 新增缺陷层视角 `--view code|excl_const`;excl_const 下「猜第一步」只有 6/18,MedHyperTrace 5/18,两者持平。
- 待办(双方):引用注入伪迹比例前统一抽取器 + 人工抽查。

### 0.29 注入模板(第 9 轮,`analysis/artifact_audit.py`)【第 10 轮更正:模板句就是 RC 注入的故障本身,「删模板后」的结论撤回,以 §0.30 为准】
- 合成数据里有一批只出现在被注入步骤的尾部模板句(如 "On re-reading the question more generically, the answer is A.")。被注入步骤覆盖率:mdagents 21.6%、dylan 41.2%、clinical_agent 4.8%;未注入步骤 ≈0。
- 删模板后 MHT 步骤 top-1:dylan 0.694→0.599(猜第一步 0.513),mdagents 0.693→0.667(猜第一步 0.680),clinical_agent 0.686→0.676(0.600)。**现有合成集主表数字被抬高,尤其 dylan;mdagents 上方法不超过位置先验。**
- 计划(待用户确认):先改数据和评测协议(去模板重跑本方法 + 全部基线;主表加猜第一步、模板检测器两条平凡基线),结构改进等人类 dev 集;与 MAFA 预注册 dev/test 划分。

### 0.30 按注入策略分开评估(第 10 轮,`analysis/strategy_split_eval.json`)
- response_corruption(RC)的故障 = 固定模板句;prompt_injection(PI)由模型在改写的提示下生成,较接近真实故障,但 PI 步骤常为空(llm_debate 33.8%、ca5 11.8%)。
- PI 子集上 MHT 比最强平凡基线(猜第一步 / 结构先验 / 模板 / 空输出)高:dylan +13、llm_debate +11(非空步骤)、clinical_agent +10(边缘);mdagents 无增益;ca5 不可信(整体上单靠模板检测器就有 0.90)。
- 主表改为按策略分开 + 4 条平凡基线。MAFA 建议:花钱重新生成注入数据前,先在 PI 子集上重跑全部基线(Who&When/med-SFT 需 GPU/API)。

### 0.31 预注册 dev/test 划分(第 11 轮,MAFA `3d80c11`)— 硬约束
- `review_packages/eval_split_v1.json`:dev 120 / test 240(按轨迹,框架 × 答对/答错分层)。成员哈希 `916fee301529…`(文件本身 sha256 不同,是正常的)。**只在 dev 上开发、调参;test 只在最后评一次。** 评分加 `--subset dev`。
- v2 演练集 `results/human_like_eval_v2/`(19 条,全在 dev)已跑通三层评分,产物在 `eval_mafa/out_v2/`。
- **泄漏(第 13 轮定稿,判定=题干相同,影像题加图片):** 答对轨迹 180/180 题目在合成数据里(129 条在同框架训练集),部分步骤完全相同;答错轨迹 dev 3/60(`5badfa1f` 仅在合成测试集)、test 1/120(`40d2f70f`)。结果按 `eval_mafa/out_v2/leakage_package.json` 的逐条标记分开报告。
- 目标(与 MAFA 对齐,接口 §6.7):答对轨迹上做**缺陷层**(有哪些缺陷,没有就输出「无」;答对 ≠ 无缺陷);责任层只在答错轨迹。方法缺口:目前无法输出「无」。
- **人类标签回来前不在 dev 的 LLM 标签上调参**,只搭框架、跑通流程。

### 0.32 评测框架(第 13 轮)— 人类标签到了就用这个
- **评分:** `python eval_mafa/evaluate.py --labels <MAFA 导入产物 attribution.jsonl 的路径> --pred mht=eval_mafa/out_pkg/medhypertrace_pred.jsonl [--subset dev] --out r.json --md r.md`。默认只收 `source=human`、只评 dev;评 test 必须 `--final`,自动记入 `eval_mafa/test_runs.jsonl`(test 只评一次)。大模型标签 dry run 用 `--source llm`。
- **预测:** `python eval_mafa/predict.py --traces review_packages/mast_v1.json --out_dir eval_mafa/out_pkg`(全部 360 条;需先在 MAFA 根目录 `bash scripts/fetch_data.sh`)。输出 `defect_score`,低于 0.5 输出 `pred_step="none"`(阈值固定,未调;只能在人类 dev 上校准)。
- **泄漏标记:** `eval_mafa/out_v2/leakage_package.json`,按题干(不区分大小写,影像题加图片)比对,与 MAFA §6.6(v3.2)一致:答错 dev 3/60、test 1/120;答对 180/180。
- MAFA 本地副本锁定 `ce6f8f7`。**test 人类标签由 MAFA 保管**,平时只收 `attribution_dev.jsonl`;最终评测时 MAFA 交出 test 标签并记录时间、提交号。
- **当前在等:** 试标 19 条(全在 dev)的 `attribution_dev.jsonl`。

### 0.3 下一步
见 §七;另加:接入标注数据(接口 v1)时先写一个 loader,把 `anchors.jsonl` 对齐到本项目的轨迹对象,并在失效边界上实测(ID 重复、框架固有码)。

---

## 〇、一句话定位

把失败归因(failure attribution)从通用 MAS 扩展到**医学多智能体系统**,做一个 Nature 子刊论文 + CS 姊妹论文。核心系统 **MedHyperTrace**:异构超图(step/agent/phase 节点 + agg/ctx/role/phase 超边)+ 关系感知超图卷积 + 三级解码头(agent/FM/step)。**方法已够用,真正的瓶颈是真实临床标注的规模和质量(κ)——反复确认过。**

---

## 一、沙箱环境与恢复

| 限制 | 说明 |
|---|---|
| 无 GPU/torch | 沙箱磁盘满,装不了 torch;HGNN 训练只能在用户服务器跑。沙箱只能验证非-torch 链路(数据加载/超图/特征/解析/填表) |
| 会话间文件重置 | 每次新会话要重新解压数据集 |

**恢复命令:**
```bash
pip install py7zr matplotlib --break-system-packages -q
python3 -c "import py7zr; py7zr.SevenZipFile('/mnt/user-data/uploads/AEGIS-custom-dataset-8-13.7z').extractall('/home/claude/aegis_813')"
export MHT_DATA_DIR=/home/claude/aegis_813/AEGIS-custom-dataset
# 代码包:解压 /mnt/user-data/outputs/medhypertrace.zip 到 /home/claude/pkg/
```
**坑:** 沙箱 shell 不稳定,`rm -rf` 偶尔 I/O error,重试即可。数据集目录名是 `AEGIS-custom-dataset`(7z 解压后)。

---

## 二、五个数据集框架(最新 AEGIS-custom-dataset-8-13.7z)

| 框架 | 全量 | train | test | 模态 | 步数 | 多故障% | 责任agent均 |
|---|--:|--:|--:|---|--:|--:|--:|
| mdagents | 1003 | 703 | 300 | **多模态(医学影像)** | 7 | 91.2% | 3.96 |
| dylan | 1062 | 725 | 337 | 纯文本 | 9.1 | 100% | 2.00 |
| llm_debate | 1712 | 1127 | 585 | 纯文本 | 7 | 100% | 2.01 |
| clinical_agent | 402 | 297 | 105 | 纯文本 | 6 | 100% | 2.00 |
| clinical_agent5 | 1052 | 738 | 314 | 纯文本 | 5 | 100% | 2.35 |
| **合计** | **5231** | **3590** | **1641** | | | | |

- split 按 **task 划分**(防同一 task 的注入变体泄漏),定义在 `common/splits.json`,所有方法共享同一份。
- 权威标签在 `injection_log.multi_injection_info`:字段 `injected_role` / `injected_role_index` / `fm_error_type`(注意 `agent_name` 字段为 None 是坑)。
- FM 空间 = **MAST-14**(AEGIS 按 MAST 注入);14 类全覆盖、分布均衡(5.3%–9.9%)。
- **MDAgents 的图像**:数据里 `images: ['MM-1-a.png',...]` 只有**文件名引用,无像素**。用户有 MedXpertQA-MM 原始图像文件(某目录);视觉描述混在步骤文本里。

### ⚠️ 两个重要的数据处理决定(本会话做的)

**(1) mdagents 专家名细化**(`common/data.py` 的 `_AGENT_REFINERS`):
mdagents 的 5 个专家 `agent_name` 全叫 `Expert`,真实身份(Breast Radiologist 等)藏在 `phase='expert_answer/<专家名>'`。本会话改成从 phase 取专家名作为 agent 身份,贯穿 parser→gold(用 `orig_agent_name` 精确对齐)→render(LLM 看到的轨迹)→匹配。**效果:同名专家多 instance 的轨迹从 85.3% 降到 1.3%,role≈instance。** 是个**显式的每框架注册表**(不是伪通用检测),新框架需显式加条目,见 `RUN_EXPERIMENTS.md §6b`。
**→ 后果:mdagents 的所有旧结果作废需重跑(set_metrics/med-SFT/ours 的 mdagents 部分);其他四框架旧结果有效。**

**(2) 粒度统一为 role**:所有方法两张表统一 role 粒度。因为 Who&When 只能预测 role 名(LLM 猜不到 instance index);mdagents 细化后 role≈instance。**med-SFT 的粒度在 preprocess 时烘焙进训练目标,所以 preprocess + eval 都要 `--agent_key role`,必须一致。** med-SFT 之前用 instance 训的 → 需重新 preprocess+训+评。

**已知遗留问题(未修,本会话发现)**:dylan 有 20/1062 条 gold 对齐失败(gold 有 `Medical_Researcher` 但步骤里没有),是 injection 记录与步骤 role 名不一致,与专家名细化无关。未动,避免范围蔓延。

---

## 三、代码库结构(`common/` `ours/` `baselines/` `analysis/` `docs/`)

### common/(核心)
- `paths.py` — **唯一 FILES 定义(single source of truth)**,五框架全注册。本会话修了 5 处硬编码 FILES 的 anti-pattern(preprocess_med_sft/validate/bridge/baseline_pointwise 的 shadowing/baseline_whowhen 的 __main__)
- `data.py` — 统一 parser + 超图构造 + 三级标签。`FM_TYPES`=14 类 MAST。`load_jsonl` 用 realpath 反查 FILES 得权威框架名(修了 clinical_agent5 误标为 clinical_agent 的 bug)。`_AGENT_REFINERS` 专家名细化(见上)。`get_framework(rec, override)` 支持权威 override
- `aegis_metrics.py` — vendored `compute_metrics`,返回 Agent/Error/Pair × Micro/Macro-F1,**0-100 标度**。`_norm_agent` 做 strip().lower()
- `embed_cache.py` — 多模型嵌入缓存(`--model mxbai|nomic`,device auto)。mxbai(384维,比 nomic 快 12 倍)。**包内附带 mxbai 的 clinical_agent/mdagents 缓存;其余三框架需本地补跑**
- `structural_features.py` — 7 维结构先验(N_STRUCT=7);新增 `structural_features_with_factuality()`(7+1 维,N_STRUCT_FACT=8)
- `factuality_provider.py` — **可插拔事实核查接口**(S− 档)。`score_steps(steps,context)->[0,1]`。providers:null(默认,全0,逐位不变)/heuristic(CPU 占位符)/nli(真实)/medical(stub)。`get_provider(name,**kwargs)`
- `factuality_nli.py` — **真实 NLI 检测器**(RefChecker 的 NLI-checker 分支)。规则分解声明 + 小型开源 NLI 模型(cross-encoder/nli-deberta-v3-small 等)。静态文本友好无需重采样。`build_nli_provider(model,reference,device)`,reference∈{prior-steps,gold-answer,none}
- `splits.py` / `splits.json` — 固定 train/test split

### ours/(我们的方法)
- `hypergraph_model.py` — HGNN 模型
- `train_hgnn.py` — 训练。`build_sample(traj,fz,use_struct,fact_provider)`。参数:`--features tfidf|emb`、`--emb_model`、`--struct`、`--prop`(传播一致性损失权重)、`--factuality null|heuristic|nli|medical`、`--factuality_model`、`--factuality_ref`、`--frameworks`(子集)、`--holdout`(OOD)。**`get_args` 用 `parse_known_args`**(忽略 unified_eval 传入的 eval-only 参数,否则报 unrecognized arguments)
- `hgnn_unified_eval.py` — 统一评测。用法:`<framework|all>`,支持 `--frameworks` 子集、`--report_gran role|instance`、`--json_out`(per-framework,key 'ours')、`--pooled_out`(合并池)
- `ablation_tiers.py` — 三段式消融(t1 纯结构 S+ / t2 +传播 S~ / t3 +NLI 事实核查 S−),无 torch 时打印命令

### baselines/
- `whowhen/baseline_whowhen.py` — 三协议(all_at_once/step_by_step/binary_search 单预测,accuracy,附录用)+ **SET_METHODS(all_at_once_set/step_by_step_set/sdbl_set 集合预测)**。openai/hf/ct2/mock 后端 + workers 并发
- `whowhen/eval_set_unified.py` — 集合方法统一评测(Agent/Error/Pair-Micro-F1 + Step-Acc)。`--out`(per-framework)+ `--pooled_out`(正确池化:拼接 pred/gt 后 compute_metrics)
- `whowhen/run_whowhen_table.py` — 三协议单预测表(附录)+ `--controls` 平凡基线
- `whowhen/fill_agnostic_table.py` — 填框架无关表(单预测口径,旧)
- `pointwise/pointwise_unified_eval.py` — pointwise 基线(`--json_out`,key 'pointwise')
- `aegis_med_sft/preprocess_med_sft.py` — 生成 SFT 训练数据(`--variant no_step|with_step`、`--agent_key role|instance`)
- `aegis_med_sft/aegis_med.py` — build_prompt/parse_prediction(**已加固**:剥离 `<think>`、容忍 trailing comma/单引号、兼容 key 变体、抓 prose 中 JSON、**空预测 `[]` 算合法不算失败**)/build_target_json/`_agent_surface`
- `aegis_med_sft/eval_med_sft.py` — med-SFT 评测(`--agent_key role`、`--json_out`、`--pooled_out`、`--out raw.jsonl`、记录 parse_ok)
- `make_main_table.py` — **框架相关主表**(表头细分五框架)。合并多个 json;NAME_MAP/METHOD_ORDER 定义行序;每列最优加粗;ours 行自动前置 \midrule + 加粗
- `make_agnostic_table.py` — **框架无关主表**(合并池)。消费 `{"pooled":{method:{metrics}}}`
- `reconstruct_pooled.py` — 从 set_metrics.json + 数据集精确反解池化(gold 对数确定性可复原 TP/FP/FN)
- 其他:graphtracer/agenttrace/famas/echo 基线

### analysis/(本会话新增,数据集分析)
- `dataset_analysis.py` — 6 张表(规模/结构/FM分布/角色画像/模态/故障位置)+ **逃逸率骨架(第7节)**。`--frameworks` 子集、`--annotations`(真实标注算逃逸率)、`--out`
- `dataset_viz.py` — 5 张图(长度分布/FM条形/故障位置密度/多故障分布/框架×FM热力图)。`--frameworks`、`--outdir`。B类(签名2×3、逃逸率图)和C类(性能图)未实现,需标注/实验

### docs/
- `annotation_protocol.md` — 标注协议,四层(定位/归因 A-B/线索 S+~-/责任结构)。**§3.5 关键:表现型(FM)与归因(A/B)是独立字段,A/B 不从 FM 标签派生,逐轨迹判 V(τ)**
- `attribution_vs_phenotype.md` — 方法学备忘(回应 GPT 的"根因二分"质疑,见第五节)
- `factuality_providers.md` — S− 档可插拔检测器清单 + 约束(SelfCheckGPT 等需重采样,不适用)
- `dataset_stats.md` — 数据集分析报告(已生成)
- `table_main.tex` / `table_agnostic_main.tex` — 两张主表
- `figs/` — 5 张数据集图

---

## 四、指标体系(两张表通用)

每条轨迹 → (agent, FM) 对集合,预测 P / 真值 G,投影到 agent/error/pair 三层次:
- TP=|P_L∩G_L|, FP=|P_L\G_L|, FN=|G_L\P_L|
- **Micro-F1**(先跨轨迹累加计数再算一次):P=ΣTP/Σ(TP+FP), R=ΣTP/Σ(TP+FN), F1=2PR/(P+R)
- **Macro-F1**:每类(agent名/FM码/对)单独累计算 F1 再无权平均
- **Step-Acc**(单点不套 F1):(1/N)Σ 1[最早预测步==最早真值步];池化=Σ命中/Σn

**两张表唯一区别 = 累加范围**:框架相关表单框架,框架无关表合并池 1641 条。
**⚠️ 池化 Micro-F1 必须累加 TP/FP/FN,不能平均各框架 F1**(实测 all_at_once 五框架 Agent-F1 简单平均 51.15 / n加权 53.18 / 正确池化 52.79,三者都不同)。

**统一口径收敛史**:binary_search 移出集合表(二分本质单点);step_by_step 原版(停第一个 yes)留附录,集合变体(收集所有 yes)进主表;Step 维度统一用 accuracy(真值 when 是单个最早步)。

---

## 五、方法论核心决定(最重要,反复讨论收敛的)

### 5.1 二元本体(顶层,稳定)+ 固定 MAST-14(底层,error-level 细粒度)

- **顶层 = 二元责任本体**:A(架构-协作,违反规范)vs B(模型固有,逃逸规范)。判据是 **V(τ):是否存在一条明确的预定义规范被违反**(操作性,**不问根因**)。
- **底层 = 固定 MAST-14 细粒度分类**(error-level,**完整保留,不退化成二分**)。
- **放弃"自适应底层"**(AdaMAST 式):用户两个疑问确诊不可行——(1)专家自由标注新类型→类型体系不一致、长尾爆炸、κ 崩;(2)AEGIS 合成数据只按 MAST-14 注入,新类型无训练标签,真实标注量小不够训。AdaMAST 降为讨论/未来工作引用。
- **A 类**:合成+真实都有,细粒度(MAST-14)+ 结构归因,训练充分。**B 类**:只在真实数据(专家撞出的 MAST 装不下的),**不细分**(开放集,列不完),只检测 + 可插拔外部检测器。

### 5.2 回应 GPT 的"根因二分"质疑(见 `MAST_分类维度分析.md` 和 `docs/attribution_vs_phenotype.md`)

GPT 说:MAST 标签是表现型,根因(模型 vs 架构)是另一条轴,同一标签可来自不同根因,不该硬二分。
**我们的回应**:采纳"表现型与归因是独立字段"(A/B 不从 FM 标签派生,逐轨迹判),但**用"规范违反(V(τ))"而非"根因"作判据**——根因认识论上不确定,而"有没有违反一条明确规范"是可判定的二元问题,绕开了 GPT 指出的根因不确定性。**不采纳** GPT 的连续根因贡献度(会软化"逃逸"这个二元核心发现)。

### 5.3 一个已更正的错误

早先说"A/B 头可从 MAST 标签确定性派生、现在就能训"——**这是错的**(与 V(τ) 逐轨迹判定矛盾)。**A/B 监督只能来自真实标注**,合成数据只有表现型标签。这再次强化:**瓶颈是真实标注。**

### 5.4 S− 档:模态分派 + 可插拔检测器(用户认同)

模型固有类**本体不细分**,但**检测手段按模态分派**:文本事实幻觉→NLI provider(已接 RefChecker 风格真实检测器);视觉感知幻觉→VLM provider(用户有 MedXpertQA-MM 图像,候选 CLIPScore/MedHallTune,**未实现**);重复输出→repetition 检测;覆盖不到→诚实标注"无法核查"(abstain)。三 taxonomy 模型固有占比差异大(MedAgentAudit 2-3/10、Who&When Pro 7/18、MAST 0/14)证明模型固有是开放集。

### 5.5 Nature 可行性(诚实评估)

方法已过门槛但**不是决定因素**。决定因素:真实标注规模 + κ + **逃逸率实证**(X% 真实失败无法归入 MAST-14;<5% 分量不够,15-30% 故事成立)。和 MedAgentAudit 区别清晰(它做 population-level 审计,你做 instance-level 责任归因 + 逃逸性 + 结构签名)。**建议:方法停在当前自洽版,80% 精力转推标注,尽早算初步逃逸率。** 警告勿用方法复杂度对冲数据不确定性。

### 5.6 结构签名 2×3 表(论文核心图,待标注)

归因维度 A/B × 签名维度 S+(强结构信号)/S~(弱/传播足迹)/S−(无信号需外部知识),正交非一根轴。三段式消融(纯结构→+传播→+LLM核查)对应 S+→S~→S−。需真实标注才能填。

---

## 六、已出的真实结果(role 粒度前,mdagents 需重跑)

### Who&When 集合指标(`set_metrics.json`,用户 GPU 跑,**instance 粒度,mdagents 未细化,需重跑**)
Agent-mi 尚可(43-64)但 Pair-mi 极低(<10),因 Error-mi 低(FM 分类是瓶颈)。sdbl≈all_at_once>step_by_step。

### 框架无关表(`ww_pooled.json` + `medsft_pooled.json`,已填 `docs/table_agnostic_main.tex`,n=1641)
| 方法 | Agent-mi | Error-mi | Pair-mi | Step-Acc |
|---|--:|--:|--:|--:|
| Who&When all-at-once | 52.8 | 16.9 | 4.4 | 34.0 |
| Who&When step-by-step | 22.9 | 7.0 | 1.7 | 7.6 |
| SDBL | 50.5 | 15.6 | 4.5 | 36.6 |
| AEGIS-med-SFT | 35.3 | 11.3 | 2.7 | 38.6 |

### AEGIS-med-SFT(`medsft_pooled.json`,parse_ok=0.993 干净)
**重要诊断**:llm_debate 的 Agent-mi 只有 7.0,确诊是**模型退化成常数输出**(对每条都预测 `Agent 3/FM-3.1`),50 步欠拟合所致,不是评估 bug。clinical_agent5 最好(53.3)。合并池 med-SFT(35.3)反低于零样本(因 llm_debate 退化拉低)。**这版是 instance + mdagents 未细化,需按 role 重跑。**

### parse_ok 排查史(重要经验)
med-SFT 初次 parse_ok 低(clinical_agent 0.43)。排查确认**不是输入/输出截断**(prompt 最长 12k<16384,目标 JSON 最长 90tok<512),是模型输出格式漂移。加固 parser 后回升。又发现**空预测 bug**:`{"faulty_agents":[]}` 是合法空预测被误判成解析失败(`[] or ...` 跌穿成 None)。修后真实 parse_ok 全部 0.98-1.00。

---

## 七、下一步(按优先级)

### 立即能做(不依赖标注)
1. **重跑 mdagents 相关结果**(专家名细化 + role 粒度):Who&When(`eval_set_unified.py --pooled_out`)、med-SFT(preprocess+训+评全走 `--agent_key role`)、ours(`hgnn_unified_eval.py all --report_gran role --frameworks ... --json_out --pooled_out`)
2. **跑我们的方法填两张表**:`ours/hgnn_unified_eval.py` 见 `RUN_EXPERIMENTS.md §2.2, §5d, §5e`。先确保嵌入缓存
3. **C 类性能可视化**(未实现):性能对比条形图、FM 混淆矩阵、归因难度 vs 轨迹长度散点。依赖实验 json,可现在做好等实验

### 依赖真实标注(真正的瓶颈)
4. **推进真实标注**(当前只到 clinical_agent + MDAgents 一部分,进度慢)。标注协议已就绪(`docs/annotation_protocol.md`),含 V(τ)/A-B 字段
5. **算初步逃逸率**:`dataset_analysis.py --annotations <真实标注jsonl>`(骨架已就绪)。这个数字决定 Nature 故事成不成立
6. **加 A/B 双头**(标注够了之后):细粒度头(MAST-14,合成数据训)+ A/B 头(真实标注的 V(τ) 训)
7. **视觉 provider**(用户有 MedXpertQA-MM 图像):接 CLIPScore/MedHallTune 类,完成 S− 档模态分派

### 论文
8. CS 姊妹论文(方法+全基线+SOTA,AEGIS 合成数据,ICLR/NeurIPS/ACL)+ Nature 子刊(findings-heavy,真实标注,方法当仪器)

---

## 八、端点(见 project doc `api端点`,不在代码包内)

用户在 project 里存了多个第三方 API 端点(claude-opus-5 via aiberm、gpt via aihubmix、deepseek、qwen、glm、mimo 等)。需要调模型时读 project doc `api端点`。

---

## 九、关键参考文献(用户已提供分析)

- **MAST**(arXiv:2503.13657):14 类故障,主动排除模型固有类。AEGIS 按它注入
- **MedAgentAudit**(arXiv:2510.10185v3):10 类医学 MAS 审计 taxonomy,population-level。正交非竞争
- **Who&When**(ICLR'26/arXiv:2505.00212):失败归因开山,127 系统,best agent-acc 53.5%/step 14.2%
- **Who&When Pro**(arXiv:2607.09996):18 类,3 模态,12326 轨迹,κ=0.73。数据分析范式参考
- **AdaMAST / Fantastic Adaptive Taxonomies**(arXiv:2607.16387):MAST 原班人马,自适应归纳分类法。降为引用/未来工作
- **AEGIS**(用户自己的,ICLR 2026):合成数据底料

---

## 十、与用户协作的注意事项

- **诚实优先**:用户明确要诚实批评、实证核对。本会话多次因此纠正自己(A/B 派生错误、离线重算数字不可信、伪通用检测过度泛化)。**不要臆断数字,不要过度设计,不要用方法复杂度对冲数据问题。**
- **每轮更新讨论记录 `RUN_v0.<N>.md`(文件名带版本号,每轮 `git mv` 到新轮次)和本交接文档**(project 规则)。Project doc `claude/api端点` 存 API 密钥
- 用户英文/中文混用,技术讨论用中文居多
- **反复出现的错误模式**:"便宜的代理量替代真实量,从没在失效边界上检查过"。做状态判断前先确认指标量的到底是什么
