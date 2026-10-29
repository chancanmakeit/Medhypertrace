# MedHyperTrace 会话交接文档

**最后更新:** 2026-10-28 05:20 UTC(第 67 轮;第 4 个会话) · **原始版本:** 2026-10-08
**项目:** 医学多智能体系统故障归因 → 本仓库是其中的「故障归因方法」子项目(另一个子项目「人机协同自动化标注」提供人类标注,接口见 `docs/annotation_interface_v1.md`)
**用户:** Alvin Chan(清华,ML/NLP researcher;偏好直接的 peer-level 技术交流、要诚实批评而非附和、要求实证核对而非臆断)

> **新会话开场顺序:** ① 本文 §0(当前状态)→ ② 最新的 `RUN_v0.<N>.md`(讨论记录,文件名带版本号,N=轮次)的最后两轮 → ③ 按需读 `RUN_EXPERIMENTS.md`(完整实验命令)和 `docs/`。
> **仓库:** https://github.com/chancanmakeit/Medhypertrace (**私有仓库**,2026-10-09 起)。§一 以下是 2026-10-08 旧会话的内容,§0 中与之冲突的以 §0 为准。

> **⚠️ 第 34 轮(2026-10-21)起目录重组(用户要求):** 原方法 = **MedHyperTrace-v1**,全部代码 / 数据 / 结果移入 `MedHyperTrace-v1/`;新的超图基础模型 = **MedHyperTrace-v2**,代码在 `MedHyperTrace-v2/`。根目录只留 `README.md`、`HANDOFF.md`、`RUN_v0.<N>.md`。**本文 §0.3x 及以前出现的路径,v1 的一律加前缀 `MedHyperTrace-v1/`**(例如 `scripts/restore_env.sh` → `MedHyperTrace-v1/scripts/restore_env.sh`、`eval_mafa/` → `MedHyperTrace-v1/eval_mafa/`);**v2 的对照表:** `ours/hgfm/*` → `MedHyperTrace-v2/hgfm/*`(包名 `hgfm`,在 `MedHyperTrace-v2/` 下 `python -m hgfm.<模块>`);`data_tools/*`、`common/clean_inputs.py`、`common/old_data_filters.py` → `MedHyperTrace-v2/data_tools/`;`analysis/{read_hyperedge_stats,pilot_20261020}.py` → `MedHyperTrace-v2/analysis/`;`docs/{design,lit,interfaces}` → `MedHyperTrace-v2/docs/`;`scripts/issue_inbox.sh` → `MedHyperTrace-v2/scripts/issue_inbox.sh`。v1 用 `validate.py` 和 `ours/train_hgnn.py --help`、v2 用全部模块 import 和审计脚本做过冒烟测试。

> **🚀 新会话快速恢复(第 38 轮写,v2 工作用):**
> 1. `add_repo` 以 push 权限添加 `chancanmakeit/Medhypertrace`、`chancanmakeit/medical-aegis`(需要时再加 `graph-based-mas-fault-attribution-papers`),然后 clone 到 `/home/claude/medhypertrace`、`/home/claude/medical-aegis`;推送走 git 代理,不需要 token。
> 2. **先看 issue**:`cd /home/claude/medhypertrace && bash MedHyperTrace-v2/scripts/issue_inbox.sh`(**第 65 轮起扫描 medical-aegis 所有 issue + 新开 issue**;只打印 `docs/interfaces/issue_last_seen.txt` 之后的新内容;最后读到我方第 64 轮续的评论(见 `docs/interfaces/issue_last_seen.txt`);脚本已加 `--paginate`)。之后每次被唤醒都先跑一次。
> 3. **MAA 数据(沙箱若已重置)**:`cd MedHyperTrace-v2 && pip install -r requirements.txt --break-system-packages`,然后运行 `bash scripts/prepare_maa.sh /home/claude/data_maa_v2 QD 8000`。脚本会自动下载、转换、对齐人工标签;**嵌入直接从仓库缓存 `MedHyperTrace-v2/data/maa_emb_minilm/` 恢复**(sha256 校验,约 10 秒,省去 CPU 上约 50 分钟;也可单独运行 `bash scripts/restore_maa_emb.sh <emb_dir>`);再导出图 token、构建 SFT。脚本能跳过已有的步骤;图缓存 `graphs_*.pkl` 在首次加载时自动重建。第一阶段结果已在 `results/phase1_maa/`,不必重跑。
> 3b. **公开 MAS 数据(需要时)**:从私有 HF 数据集 `UUUooUUU/mht-session-data` 下载 `public_mas/mas_traj/`(86 MB)到 `/home/claude/public_mas/`,`raw/` 1.5 GB 按需;**`mas_traj.md5` 在该仓库根目录**,复制到 `/home/claude/public_mas/` 后在该目录 `md5sum -c mas_traj.md5`;HF token 在 Project doc `UUUooUUU-huggingface-access-token`,写入 600 文件,不上命令行。
> 4. **API 密钥**:从 Project doc `claude/api端点` 读取,写到 `/home/claude/.mht_api.env`。绝不进 git。调用前先试跑估算成本,再问用户。
> 5. 阅读顺序:**§0.77(第 67 轮,E1–E3 在跑,先读)** → §0.76(第 66 轮) → §0.75(第 65 轮,issue #2) → §0.74(第 64 轮 SAMT) → §0.73(第 63 轮)→ **§0.72(第 62 轮续)** → §0.71 → §0.70(第 61 轮)→ §0.69(第 60 轮)→ §0.68(第 59 轮)→ §0.67(第 58 轮)→ §0.66(第 57 轮)→ §0.65(第 56 轮)→ §0.64(第 55 轮:已定事项与新待办)→ §0.63(第 54 轮)→ §0.62(第 53 轮末交接)→ §0.61(第 53 轮:收藏夹 15 个数据集、五折配对比较)→ §0.60(第 50 轮:中训练主版本排除所有 AEGIS 注入运行)→ §0.59(含第 48 轮进度)→ §0.58 → §0.57 → §0.56 → §0.55 → §0.54 → §0.53 → §0.52 → §0.51 → §0.50 → §0.49 → `RUN_v0.62.md` 第 37–62 轮 → `MedHyperTrace-v2/docs/design/HGFM_design_v0.2.md` → `MedHyperTrace-v2/hgfm/llm/README.md`。
> 6. **每轮必做**:讨论记录 `RUN_v0.<N>.md` 用 `git mv` 改版本号并追加本轮;更新本文 §0;commit 并 push;sleep 不超过约 60 秒。

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
- MAFA 仓库 `chancanmakeit/MAFA-human-ai-annotation` 在本会话**只读**,克隆在 `/home/claude/mafa-human-ai-annotation`,锁定 `241f6af`(第 5 轮评估时为 `908bc74`);AEGIS 原始记录需在其根目录跑 `bash scripts/fetch_data.sh`(约 1.9G,很快)。新会话需重新 add_repo(只读)+ 克隆 + checkout。
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
- 主表改为按策略分开 + 4 条平凡基线。
- **第 50 轮加注:** medical-aegis 核实旧 AEGIS 的 PI 注入步输出本身带伪迹(指令泄漏、拒答、框架要求的结构丢失,同槽位 tfidf 0.76–0.91);上面 PI 子集上的增益可能部分来自这些伪迹。**第 51 轮更正口径**:拒答是被注入的故障本身(FM-1.2 / FM-1.5 模板),不剔除;只按步骤剔除严格口径的指令泄漏(`instruction_strict`)。重算时按注入方式(llm_rewrite / direct_prepend)和 FM 分开报告,另给去掉泄漏步的敏感性结果,FM-1.2 / FM-1.5 单列并注明偏乐观。MAFA 建议:花钱重新生成注入数据前,先在 PI 子集上重跑全部基线(Who&When/med-SFT 需 GPU/API)。

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
- MAFA 本地副本锁定 `241f6af`(0.7.58;工具 2.2.0、接口 v3.4;无码缺陷须填最接近的码 `codes._uncoded.nearest`,导入报告有 `uncoded_nearest` 分布)。**当前 LLM 评估集用 `results/closest_human_like_eval_v2/`**(39 条,全 dev,只用于跑通和错误分析);结果 `eval_mafa/out_chl_v2/`。
- `defect_any` 层用 MAFA 官方实现;缺 `earliest_step_any` 的旧行由评测脚本先补齐:有 `uncoded` 字段的按 codes+uncoded 推,旧格式(label_schema 1,如 human-like v1)取标注者原填的最早步(已请 MAFA 同样处理)。**test 人类标签由 MAFA 保管**,平时只收 `attribution_dev.jsonl`;最终评测时 MAFA 交出 test 标签并记录时间、提交号。
- **当前在等:** 试标 19 条(全在 dev)的 `attribution_dev.jsonl`。

### 0.33 硬规则:MAST 与 MedAgentAudit 分开(第 17 轮,用户要求)
- 所有评测、表格、结论都按体系分开;**任何数字不跨体系合并**(不同标签定义;同一轨迹会被算两次;MHT 只懂 MAST)。`evaluate.py` 已按体系输出并断言。
- 第 11、13、15、16 轮汇报过的 v2 / closest v2 合并数字作废,以 `RUN_v0.17.md` 的分体系表为准。
- 合成训练数据只有 MAST 码;MAA 上的结果是「迁移到另一套定义」,论文中单独报告。

### 0.87 第 75 轮:issue #2 讨论——两处更正与新提案
- **更正:** (1) TracerTraj 与 WW / TEgc 有 110 / 358 条近似重复题(第 71 轮漏查),去掉后 E4 不变;(2) E1 的 OAT 增益在长度匹配下仍有约 +0.05,位置卡紧后消失 → E1 改为"未定"。数字在 `results/e4/README.md` 第 75 轮补充。
- 外部数据去重规则(新):题干归一化后词集 Jaccard ≥ 0.3,按题目分组。
- 提给用户的下一步(零 API):E4 标签效率曲线;负对照中训练;按题目分组的 manifest + 基准审计表;预注册 v2(替换步检测中训练目标,有图 / 无图消融)。等用户确认。

### 0.86 第 74 轮:E4 完成——中训练对有监督归因也没有价值
- 结果 `MedHyperTrace-v2/results/e4/README.md`。三种设置(A 线性 / A MLP / B BEFT)在控制步长后 tapt − base 都不成立(MLP 显著为负)。有监督 TracerTraj 标签可以迁移(BEFT 控制后 0.63–0.64),但原始值仍不胜最长步基线。服务器上的完整输出在 `mht_work/e4/`。
- **需要用户重新定方向**:中训练路线(TAPT / S / R / SAMT)在 MAA 缺陷层、公开责任层、无监督读出、有监督后训练上都没有站得住的正面证据。

### 0.85 第 73 轮:E4 运行中(BEFT + 冻结探针)
- 预注册 `MedHyperTrace-v2/docs/design/E4_prereg_v1.md`。代码 `hgfm/e4/`(e4_features、e4_eval、e4_probe、e4_beft、e4_beft_eval)。Linux #2:`mht_work/e4/`,状态看 `status`,驱动 `scripts/linux2_run_e4.sh`(可重跑续接)。TracerTraj 的 WW 格式数据在 `mht_work/e4/tt_ww/`。
- 结束后:读 `stageA/e4a_{linear,mlp}.json`、`stageA.log`、`stageB.out`;写 `results/e4/README.md`(原始 + 控制后,与最长步基线比较,和论文同口径的 WW 步骤级准确率);汇报;发 issue #2。

### 0.84 第 72 轮:训练加速实测
- liger-kernel 0.7.0 已装(mht-swift)。`linux2_run_tapt.sh` 支持 `LIGER=true`、`PACK=1`(默认都关,保持旧配方)。A6000 拓扑全是 SYS,无 NVLink;LoRA 训练用 DDP;梯度检查点必须开。数字见 `MedHyperTrace-v2/results/bench_train/README.md`。E4 仍待用户确认。

### 0.83 第 71 轮:TracerTraj 公开版已获取并审计
- `mht_work/tracertraj/agentracer-data-v1.0.0/`(Linux #2):3,208 训练 / 790 测试,Who&When 格式。agentic 部分 1-indexed、无智能体名;math 测试有三分之一与训练重题;与 WW / TEgc 无重叠。见 `MedHyperTrace-v2/results/tracertraj_audit/README.md`。
- **待用户确认 E4**(方案见 RUN_v0.71 第 71 轮)。

### 0.82 第 70 轮:三篇后训练归因论文 vs 我方中训练阴性结果
- 三篇(AEGIS / AgenTracer / GraphTracer)都是用反事实或注错产生的归因标签做后训练(SFT / GRPO)。我方实算 WW 平凡基线:Hand-Crafted 上"最长步"步骤级 18.97%,AgenTracer 20.68%;Algorithm-Generated 上"最长模型步"26.2%,AgenTracer 37.3–42.9%。见 RUN_v0.70 第 70 轮、`results/e1e3/ww_trivial_baselines.json`。
- **待用户决定 E4**:同一批标签数据(AEGIS 9.5k 或 TracerTraj),基座 → 后训练 vs TAPT → 后训练,检验中训练对后训练有没有额外价值(仅 GPU,无 API 成本;先核实数据是否公开可得)。

### 0.81 第 69 轮:进度与意见已发 issue #2,等其他智能体讨论
- issue #2 新评论(`MedHyperTrace-v2/docs/interfaces/issue2_comment_r69.md`):主张"分叉对中训练 + 分叉点评测 + 步长控制";向 medical-aegis / GPT / Muse 提了 7 个问题。下一次会话先跑 `issue_inbox.sh` 看回复。在拿到分叉数据前,不新开中训练任务。

### 0.80 第 68 轮(09:45 UTC):flash-attn 已装;E1b 复现,但 E1 / E1b 增益全是步长效应(结论已更正)
- **flash-attn 2.7.4.post1** 已装进 Linux #2 的 mht-swift(轮子在 `mht_work/wheels/`)。LoRA 训练 1.7 倍(4k)/ 2.4 倍(8k)。`linux2_run_tapt.sh` 默认 flash_attn(`ATTN=sdpa` 可切回);`linux2_run_samt.sh` 默认仍是 sdpa。
- **E1b REPLICATES (S, R)**,但混杂检查显示:"最长模型步"基线(合并 0.673)胜过任何代理下的 OAT;控制步长 / 位置 / 代码之后,所有代理相对 base 的增益都约为 0(tapt +0.002 [−0.019, +0.023])。见 `MedHyperTrace-v2/results/e1e3/README.md` 顶部更正与 §5。issue #2 已发更正 6465654335。
- **常设规则(新):** 责任层评测必须报告步长 / 位置基线和控制步长后的数字(`scripts/e1e3_confounds.py` 是参考实现)。
- **等用户决定:** 中训练路线在责任层上目前没有站得住的正面证据。可选方向:(a) 把剩下的两条线索(TEgc 上 OAT 控制后约 0.59;NLL_base − NLL_tapt 控制后 0.58 / 0.60)带着步长控制写成预注册,在新数据上检验(medical-aegis 分叉点有反事实标签,不受步长影响,最合适);(b) 回到之前悬而未决的选项(LQD 5 折 SAMT vs 文本、分叉扩展 A / B、SAMT v2 vs G2、通过 medical-aegis 扩充自然运行,后者付费)。

### 0.79 第 67 轮续 2(08:15 UTC):E1–E3 完成——E1 成立(小),E2 不成立,事后线索 base − tapt
- 结果见 `MedHyperTrace-v2/results/e1e3/README.md`。E1 成立:合并 rank-AUROC +0.027 [+0.009, +0.047],WW 和 TEgc 各自成立,种子间稳健;但绝对水平低,WW 上不胜第一步基线。E2(似然比)不成立(0.456)。事后:NLL_base − NLL_tapt 0.683(未预注册)。issue #2 已发 6464027068。
- **等用户决定:** (a) 把 base − tapt 线索写成预注册 v2,在新数据上检验(medical-aegis 分叉点 / 新留出集),并先查步长与内容类型混杂;(b) 用 E2 的 S / R 检查点(6M token)做 OAT 代理,看 E1 增益是否随中训练 token 量变化(各约 35 分钟 GPU,无 API 成本);(c) 之前悬而未决的:LQD 5 折 SAMT vs 文本、分叉扩展 A / B、SAMT v2 vs G2、manifest v1 归属、通过 medical-aegis 扩充自然运行(付费)。

### 0.78 第 67 轮续(08:01 UTC):E1 完成;E2 打分 OOM → 修复重跑;等连接器重新授权后跑分析
- E1 完成(OAT 池化 AUROC:base WW 0.773 / TEgc 0.713,tapt 0.774 / 0.725;主指标未算)。E2 打分:第一次 YaRN 那一遍 OOM(缺 attention_mask),已修(`e2_score.py` md5 28ba0ede…,可续接),07:48 用 `$D/rerun_e2_score.sh` 重跑;base / S / R 已完成,tapt 在 GPU 1 上收尾(GPU 0 那条链也可能再跑一遍 tapt,结果相同,无害)。
- **下一步(连接器恢复后):** 看 `$D/status` 有没有 `DONE e2 score tapt`(没有就 `bash $D/rerun_e2_score.sh`,会续接);在代码目录用 mht-swift 环境运行 `python scripts/e1e3_analyze.py`(服务器上 md5 0b70e5c3…,含 `pooled_le32k` 敏感性分析)→ `$D/e1e3_results.json`;写 `results/e1e3/README.md`(WW n = 182、TEgc 174、合并 356;偏离:2 条 TEgc 无法映射、2 条 WW 错误步落在非模型步、GPU 共用、E2 打分重跑);向用户汇报并发 issue #2。

### 0.77 第 67 轮:E1–E3 运行中(2026-10-28 05:20 UTC)
- 用户批准 E1–E3。预注册 `MedHyperTrace-v2/docs/design/E1-E3_prereg_v1.md`(33dd4f7,写于结果之前;偏离见 RUN_v0.67)。issue #2 已发评论 6460913183。
- **在途(Linux #2,`mht_work/e1e3/`,看 `status`):** 驱动 `scripts/linux2_run_e1e3.sh`(可重跑续接)。E1 = OAT(`oat_base/`、`oat_tapt/`,OOD 结果在 `outputs/results/ood/mcp_atlas_to_{who_and_when,traceelephant_gc}/OAT_coral/`),在 GPU 0 上依次跑;E2 = `e2_S/`、`e2_R/`(swift pt LoRA,GPU 2/3)→ `e2_scores_{base,tapt,S,R}.json`。status 出现 `ALL DONE` 后,在代码目录用 mht-swift 环境运行 `python scripts/e1e3_analyze.py` → `e1e3_results.json`,并按预注册写 `results/e1e3/README.md`。**07:40 UTC 有会话内检查。**
- 注意:GPU 1(和少量 GPU 0)有其他用户 wyx 的任务;socks 代理会断,pip 可直连;Jupyter 连接器对较长的 cell 会返回 520,cell 要保持简短。

### 0.76 第 66 轮:通读 Muse 调研;OAT × 中训练;数据与评测来源(2026-10-28 04:50 UTC)
- Muse 调研全文已读(用户上传的附件;要点见 RUN_v0.66 第 66 轮)。OAT 仓库核对:步骤表示 = 代理 LLM 的隐状态,所以**中训练后的 Qwen3-8B 可以直接当 OAT 的代理 LLM**;OOD 基准:Who&When AUROC 0.758 / Hit 0.451。
- G 节核对:agent-scaling 只有 10 条示例,AgentFail 部分发布(约 23 MB 节点日志),MCP-Atlas 198 条为单 agent → G 节新增量小。
- **待用户决定**(本轮提出的三个零 API 实验):E1 中训练检查点当 OAT 代理 LLM;E2 似然比读出;E3 把 Who&When + TraceElephant groupchat 360 条固定为外部责任层评测,并预先写好判定规则。另有付费方向:请 medical-aegis 扩大自然运行(带记录输入,按已测单价约每千条 $2–3)。

### 0.75 第 65 轮:medical-aegis issue #2(中训练路线讨论)(2026-10-28 04:00 UTC)
- **新 issue #2**(GPT 开,经用户同意;另有 Muse 文献调研评论):讨论 CDE × Jev 路线。GPT 转述的**用户约束:必须通过持续预训练(中训练)得到 MAS 故障归因基础模型**;GPT 建议下一主实验是更新 LLM 主干的"条件交互响应"中训练(G0–G4),Muse 附件 G 节的跨领域轨迹作为中训练语料。
- **我方实测:** 公开数据的来源 100% 是推断的,只有 TraceElephant 有实际输入;高可信交互数据只有锚点(约 900 条运行、8k 步)。**Who&When 184 + TraceElephant groupchat 176 = 360 条从未进中训练语料的外部责任层评测。**
- 我方回复 #2 评论 6460209611:建议 SAMT v2(超图编码器 + LoRA,与用户的超图主线一致);以外部责任层评测为主,对照 OAT / BLADE / 位置 / 同伴支持度。**待用户决定**:SAMT v2 还是纯 LLM G2;是否固定 360 条外部评测;manifest v1 的分工;LQD 五折、分叉 A/B。没有在跑的任务。

### 0.74d 第 64 轮续 3(13:00 UTC):SAMT 全部完成——探针通过,MAA SFT 无可测提升
- 结果 `results/samt_v1/README.md`:QD samt − base_text +0.017 [−0.011, +0.043],samt − encOnly −0.003,打乱只掉 0.011(n.s.);LQD_mac 稳健指标 samt 两种子都高于 base_text 三种子(+0.046 [−0.040, +0.149],单折解析不了)。**没有在跑的任务,Linux #2 4 卡空闲,无待触发的定时任务。**
- **待用户决定:** ① LQD 其余 5 折 SAMT graph 对 base text(约 20 任务 / 10 小时 GPU);② medical-aegis 分叉扩大 A($1.2,我方倾向)/ B($2.1);③ 是否把结构方向转到责任层(分叉标签)。
- issue:对方第 46 轮(近因效应更正、同伴支持度基线)已回复,评论见 `issue_last_seen.txt` 对应的我方评论。

### 0.74c 第 64 轮续 2(08:15 UTC):SAMT 完成,探针结构门槛通过;SFT 运行中
- 连接器已重新授权。SAMT 07:32 完成;探针(`results/samt_v1/README.md`):O2 / O3 真 token 0.98 / 0.99 对打乱 0.51 / 0.22(CI 远离 0),冻结 LLM 能读出图 token 里的交互结构;O1 内容只 +0.09,医学锚点上无增益;O4 +0.11。
- 在途:SFT samt_v1(07:43 起,约 09:55 完)→ encOnly(约 11:55)→ `linux2_samt_ablate.sh` 置零 / 打乱评测 + `linux2_samt_eval.py`(约 12:30 UTC;输出 `mht_work/midtrain/samt_v1/samt_v1_eval.out`)。之后:把 eval.out / json / scores.csv 读回 `results/samt_v1/`,写 SFT 结论并贴 issue。

### 0.74b 第 64 轮续(08:05 UTC)
- **Linux #2 连接器断开,需用户重新授权**;SAMT 链在服务器后台继续(读 `mht_work/midtrain/samt_v1/status`)。连上后:读探针 → 汇报 → 结果入 `results/samt_v1/`。
- issue:对方第 45 轮已完成三项付费运行(实际 $0.557);分叉试点翻转集中在第 1 轮 / 首位发言者。我方回复建议扩大前处理位置混杂与"字母错"选择条件(见 RUN_v0.64)。**待用户决定:** 是否扩大分叉(llm_debate 每点约 $0.003,mdagents 约 $0.0012)。provenance 已改写 `phase_canonical/1`。

### 0.74 第 64 轮:结构感知中训练 SAMT v1 运行中(2026-10-27 06:05 UTC)
- **用户决定:** 做结构感知中训练。设计 `MedHyperTrace-v2/docs/design/SAMT_design_v1.md`:对齐阶段(冻结 Qwen3-8B,端到端训练 HGFM v0.2 编码器 + projector;答案在图 token 里不在文本里);O1 内容匹配 / O2 读集 / O3 读者 / O4 选项答案;语料口径同 TAPT(无 MAA、排除 groupchat);编码器没见过 MAA,一份 MAA 图 token 服务所有折。代码 `hgfm/midtrain/samt_*.py`,详细验证见 RUN_v0.64 第 64 轮。
- **在途(Linux #2,4 卡;目录 `mht_work/midtrain/samt_v1/`,看 `status`):** 驱动 `scripts/linux2_run_samt.sh`(05:37 UTC 开始):SAMT 750 步(约 1.8 小时,`samt.log`,检查点 `ckpt/`)→ 导出 `graph_tokens_samt.pt`(对 QD / LQD_mac 核形状)→ 探针 `probe_result.json`(真 / 打乱 / 置零 / 未训练,按目标和数据集)→ SFT 两个配置:`sft_queue_samt_v1/`(SAMT projector 初始化,lr 1e-4)、`sft_queue_samt_v1_encOnly/`(随机 projector,lr 1e-3),各 QD + LQD_mac × 种子 0/1,结果 `maa/llm/<fold>/eval_swift[_s1]_samt_v1[_encOnly]_graph.json`;status 末行 `ALL DONE`。另一个后台脚本 `scripts/linux2_samt_ablate.sh` 等 ALL DONE 后对 SAMT 检查点做置零 / 打乱评测(`eval_swift[_s1]_samt_v1_{zero,shuf}_graph.json`),再跑 `scripts/linux2_samt_eval.py` → `samt_v1_eval.out` / `.json` / `samt_v1_scores.csv`(主指标 + 稳健指标,配对 bootstrap)。驱动可重跑续接(各阶段有输出就跳过)。预计:探针约 07:55 UTC,全部约 12:30 UTC。**已设 08:00 UTC 的会话内提醒(trig_013SXAVEUX9gZ9aGRg8fb37p)**,要做:读探针、汇报、把结果写入 `results/samt_v1/`。
- **解读规则(写在设计里):** 探针上"真 ≫ 打乱"才说明冻结 LLM 学会读图 token;否则 SFT 结果不必解读。SFT 主比较:SAMT graph − 基座 text(第 60 轮 3 种子,text 变体因 LLM 冻结而不变,不重跑);SAMT − encOnly = 对齐本身的作用;SAMT 下置零 / 打乱是否掉 AUROC = C6 诊断复测。LQD_mac 以"正负例都 ≥ 2 的码"为主指标(与 medical-aegis 一致)。
- **传输:** 数据和代码经私有 HF `UUUooUUU/mht-midtrain-pilot/samt_v1/`(`code/`、`code_post/` 是代码包 + md5)。Linux #2 直连 HF 现在不通,必须保留 kernel 环境的 `all_proxy=socks5h://127.0.0.1:23333`(不要 unset)。Linux #2 代码目录仍无 .git,新文件按 md5 核对过;旧的 `mht_work/run_sft_swift.sh` 备份为 `run_sft_swift.sh.r63_backup`。
- **issue:** 对方第 44 轮(05:08Z)等用户确认三项付费运行(分叉 $0.31、fmt_v1_2 $0.06、开头筛选 $0.09);我方回复 6434952854(05:59:16Z):按记录用户第 62 轮已批准且新估算在范围内,但若对方要用户再确认以用户为准。`phase_canonical` v1 与已存标签 0 处不同,本地覆盖已删。

### 0.73 第 63 轮:第 4 个会话已恢复(2026-10-27 05:00 UTC)
- 两仓库已 clone(Medhypertrace、medical-aegis);issue #1 无新评论(79 条,最后为我方 02:12:07Z)。`issue_inbox.sh` 修为分页读取(超过 100 条评论时原脚本会漏看)。
- Linux #2:4 卡空闲;`mht_work/midtrain/` 完好(合并模型、TAPT ckpt、8 个 SFT ckpt、8 个评测 json、汇总与 CSV)。
- `/home/claude/public_mas/mas_traj/` 已从 HF 恢复,md5 全过,26,108 条运行 / 169,299 步 / phase_canonical 无缺失。HF token 在 `/home/claude/.mht_secrets/`(600)。
- **没有在跑的任务;等用户在 §0.72 的两个候选中决定**(结构感知中训练 / LQD 六折 TAPT 对基座);同时等对方的分叉试点、fmt_v1_2、mdagents 开头筛选、phase_canonical v1。

### 0.72 第 62 轮续:中训练试点 v1 结果——纯文本 TAPT 没有可测提升;已请对方启动分叉试点(2026-10-27 02:15 UTC)
- **结果**(`MedHyperTrace-v2/results/midtrain_pilot/README.md`;只用 MedAgentAudit 分类体系):
  - QD:TAPT 对基座同种子配对差 graph −0.006 / −0.006、text +0.010 / +0.010,全部 CI 含 0;种子集成 text +0.010 [−0.016, +0.037]、graph −0.014 [−0.041, +0.013]。
  - LQD_mac:表面下降(text 0.714 对 0.809),但几乎全部来自两个只有 1 个正例的码(1.2.1、2.1.2);只看正负例都 ≥ 2 的 5 个码,下降消失。LQD_mac 单折测不出几个点的差别(稳健指标:text 0.816 对 0.793、graph 0.806 对 0.821;基座种子 SD 0.005–0.009)。
  - SFT 训练 loss 在 TAPT 模型上都更低(0.30 对 0.33–0.38),但 AUROC 不变:续训让轨迹文本更好拟合,没带来归因信号。
  - graph − text 没变大(纯文本 TAPT 本来就不训练图 token)。
- **按第 60 轮的约定:不为纯文本中训练扩数据。** 下一步候选(待用户决定):① 结构感知中训练(让图 token 有自己的训练信号:图–文对齐、从超图预测阶段 / 读集);② 若要跨 MAS 结论,把 TAPT 与基座在 LQD 六折上各跑一遍(约 20 个任务、约 10 小时 GPU,不花 API 费)。
- 脚本:`scripts/linux2_midtrain_eval.py`(Linux #2)、`scripts/midtrain_robust_check.py`(沙箱,读 CSV)。逐实例分数 `tapt_pilot_v1_scores.csv.gz`。
- **issue:** 评论 6432028012(`docs/interfaces/issue_comment_r62b.md`)通知结果,请对方启动分叉试点(约 $0.5 以内,超出先问用户),并提醒 fmt_v1_2、mdagents 开头筛选、phase_canonical v1 仍在等。
- Linux #2 4 卡现在空闲。
- **第 3 个会话结束时的交接状态(2026-10-27 04:20 UTC):** 工作区干净(最后提交 cc797d2),issue 无新评论,**没有在跑的任务,也没有待触发的定时任务**。新会话沙箱是新的:`/home/claude/public_mas/` 不在了,**已备份到私有 HF 数据集 `UUUooUUU/mht-session-data`**(`public_mas/mas_traj/` 转换好的 7 个数据集 26,108 条运行 + `mas_traj.md5`;`public_mas/raw/` 原始下载 1.5 GB;统计与下载日志;恢复命令见该仓库 README,用 HF 写 / 读 token 下载到 `/home/claude`),需要时下载即可,不必重跑转换器;试点语料已在 HF `UUUooUUU/mht-midtrain-pilot`,Linux #2 上的 `mht_work/midtrain/` 完整保留(合并模型、8 个 SFT checkpoint 与评测 json)。
- **新会话第一步:** 跑 issue_inbox(等对方:分叉试点、fmt_v1_2、mdagents 开头筛选、phase_canonical v1);然后等用户对上面两个候选的决定。

### 0.71 第 62 轮:中训练试点 v1 运行中(2026-10-26 19:15 UTC)
- **用户决定:** 开始中训练试点;采用 phase_canonical;分叉试点排在中训练试点之后;fmt_v1_2 与 mdagents 开头筛选验证批准(已在 issue 6424293259 请对方执行)。
- **在途(Linux #2,4 卡):** TAPT `mht_work/midtrain/tapt_pilot_v1/`(status、tapt.log;19:07 UTC 开始,约 2 小时,之后合并为 `Qwen3-8B-tapt_pilot_v1/`)→ 自动接续 SFT 队列 `mht_work/midtrain/sft_queue/`(QD + LQD_mac × graph/text × 种子 0/1,约 4 小时;结果 `maa/llm/<fold>/eval_swift[_s1]_Qwen3-8B-tapt_pilot_v1_<v>.json`)。完成后与 `results/c6_linux2_lora/seed_study.md` 的基座 3 种子比较,写 `results/midtrain_pilot/`。
- **21:31 UTC 检查:** TAPT 已完成并合并(506 步,留出集 loss 0.477);SFT 队列 21:12 开始,预计约 01:15 UTC 完成。
- 语料与设计见 `results/midtrain_pilot/README.md`;构建 `hgfm/midtrain/build_corpus.py`(沙箱;需要 `/home/claude/public_mas/mas_traj/` 与 medical-aegis 锚点导出);语料在私有 HF 数据集 `UUUooUUU/mht-midtrain-pilot`。HF 读 token 在 Linux #2 `~/.mht_secrets/hf_read.token`(600)。
- 转换器已写入 `phase_canonical`(调用对方脚本;本地覆盖 magentic_one instruction → plan)。
- 下一步(试点结果出来后):若 TAPT 有提升 → 结构感知中训练(图–文对齐);若无 → 先看结构感知中训练再决定是否规模化。之后通知 medical-aegis 启动分叉试点。

### 0.70 第 61 轮:转换器按对方抽查修复;issue 第 42–43 轮已回复(2026-10-26 18:30 UTC)
- **转换器已修复并重跑**(详见 RUN_v0.61 第 61 轮、`analysis/public_mas_corpus/mas_traj_r57.md` "Round 61 revision"):新增 `kind: "environment"` + `env_type`(模板、tool_output、user_simulator),落在 environment 步上的标签标 `label_on_environment`;TraceElephant 从 `tool_logs` 补动作;`mistake_agent_id`;ARIA `first_bad_on_task`;MAST AG2 医学过滤。现在 7 个数据集 26,108 条运行,对方最新 `check()` 全过,MAA 0。数据在 `/home/claude/public_mas/mas_traj/`(仓库外;旧版备份 `mas_traj_r57_backup/`)。
- **与对方已定:** 分叉试点按用户决定用"1 分叉 + 1 对照、下游温度 0"(我方要求:未翻转记"未判定"不作负例;第 t 步用原温度);回放命中率真实运行 100%。不用 LLM 改写 agent 发言;人工标签只做评测。训练输入只用所有来源都有的字段,中训练试点报告数据来源可识别度。
- **待用户决定:** ① 采用 `phase_canonical` 词表(建议采用;采用后转换器调用对方 `scripts/phase_canonical.py` 写该字段;我方建议 magentic_one `instruction` → plan);② **中训练试点是否开始**(不花 API 费;Linux #2 4 卡空闲);③ 分叉试点(约 $0.5,建议排在中训练试点之后);④ fmt_v1_2($0.09)/ mdagents 开头筛选($0.14)仍按住。

### 0.69 第 60 轮:种子实验完成;issue 第 39–41 轮已回复(2026-10-26 08:00 UTC)
- **种子实验结论**(`results/c6_linux2_lora/seed_study.md`):MS-Swift 3 种子,graph − text QD +0.002 ± 0.012、LQD_mac +0.018 ± 0.030,CI 全含 0;graph 变体种子间波动更大。→ 当前 SFT 方式下 LLM 没用上图 token;下一步应换训练信号(图–文对齐 / 结构感知中训练),不是再加种子。Linux #2 现在 4 张卡都空闲。
- **issue:** 对方(用户发起)提议规模化合成轨迹,主线"在真实轨迹上分叉";我方回复 6411029845(07:56Z):两层标签都要、主评测是缺陷层;**先做免费的中训练试点,有提升再花钱规模化**;分析器不给标准答案;每分叉点 2 次重放不够定单步标签;试点排在我方中训练试点之后。fmt_v1_2 与 mdagents 开头筛选验证被用户暂停。
- **转换器已完成并复核**(`data_tools/public_to_mas_traj/`,报告 `analysis/public_mas_corpus/mas_traj_r57.md`,数据 `/home/claude/public_mas/mas_traj/*.jsonl.gz` 在仓库外,沙箱重置后需重跑转换器):7 个数据集 26,120 条运行、约 57.2M token(ARIA 占 74%),对方 `check()` 全过、MAA 0、可复现。只有 TraceElephant 有 text_match sources,其余为协议推断。已请对方抽查并确认 family(Magentic-One → groupchat 待确认)。待定:MAST AG2 医学 MMLU 168 条是否过滤(倾向过滤)。
- **MAA 排除:** `maa_exclusion.py recall`(TF-IDF / 5-gram Jaccard 召回候选,人工复核);阳性对照 10/10。
- **下一步(建议,待用户确认):** 中训练试点——语料 = 公开干净语料(转换完成后)+ MAA 输出(按折排除测试题)+ 锚点;先纯文本 TAPT,再结构感知;评测 MAA LQD 6 折 + QD,每设置 ≥ 2 种子。

### 0.68 第 59 轮:Linux #2 连接器断开;issue 第 38 轮已回复(2026-10-23 10:30 UTC)
- **Linux #2 Jupyter 连接器断开**,需用户在 claude.ai 连接器设置里重新授权。种子实验(`mht_work/swift_seeds/`,10 个任务,02:03 UTC 开始)在服务器上是后台运行,不受影响;授权后读 status 并按 §0.66 的计划分析(写 `results/c6_linux2_lora/seed_study.md`)。
- **转换器子 agent** 因 API 限额中断后已恢复,按对方确认的约定继续(推断 sources 加 `inferred`;同架构框架用对方 family 名:debate / groupchat,拿不准时归医学 family)。完成后主会话复核再提交。
- **issue:** 对方指出 PI 与 sham 很少同槽位,新增 `pair_target_runs`;fmt_v1_1 让 PI 更好认(去首句后仍 0.82 / 0.86)→ 我方撤回"开头句式"假设,对方提 fmt_v1_2。我方回复 6362749412(10:23:10Z,`docs/interfaces/issue_comment_r59.md`)。**待用户决定:** 主数据开 `pair_target_runs`(免费,建议开)、锚点配对重跑 sham $1.4(建议暂缓)、fmt_v1_2 验证 $0.09(建议做)、mdagents 开头筛选验证 $0.14(建议做,同时开配对)。

### 0.67 第 58 轮:分工已定并发 issue;MAA 排除清单;转换器子 agent 在跑(2026-10-23 02:20 UTC)
- 用户同意第 57 轮分工;issue 评论 6355713703(02:11Z)+ 更正 6355726800(02:12Z)。**等对方回复五个字段问题**(推断 sources 写法、question_id / run_index、自然运行的 run_mode 与 `labels.external`、非医学框架 registry、缺失字段),回复后若约定有变,在 `data_tools/public_to_mas_traj/common.py` 一处修改。
- **MAA 排除清单 v1:** `MedHyperTrace-v2/docs/interfaces/maa_exclusion_v1.json` + `data_tools/maa_exclusion.py`(build / check;精确 = 规范化题干 + 带图题的图片重叠,探针 = 题干第 100–160 字符中段,仅题干 ≥ 200 字符)。**旧 AEGIS 医学合成数据与 MAA 重叠 0**;锚点重叠 2 题(1499、1939)。任何新语料入训练前都跑一次 check。
- **在途 ①:** 转换器子 agent(后台),代码 `MedHyperTrace-v2/data_tools/public_to_mas_traj/`,数据 `/home/claude/public_mas/mas_traj/`(仓库外),报告 `analysis/public_mas_corpus/mas_traj_r57.md`。完成后需主会话复核(抽查记录、`check()` 结果、MAA 检查、重跑一致性)再提交。
- **在途 ②:** MS-Swift 种子实验(§0.66)。

### 0.66 第 57 轮:MS-Swift 种子实验运行中;中训练分工意见(2026-10-23 02:10 UTC)
- **在途:** Linux #2 卡 0 / 2 / 3,队列 `mht_work/swift_seeds/`(status、logs/),10 个任务 = QD × {graph, text} × 种子 {0,1,2} + LQD_mac × {graph, text} × 种子 {1,2};约 2 小时 / 个,预计 10:15 UTC 全部完成,已设 10:20 UTC 提醒。结果文件 `maa/llm/<fold>/eval_swift[_s<seed>]_models--Qwen--Qwen3-8B_<v>.json`。驱动支持 `SEEDS`(md5 b1162b21…)。队列中断后重跑同一命令即可(已完成的检查点 / 评测会跳过;已取走未完成的任务需手动放回 jobs)。
- **分工意见**(RUN_v0.57 第 57 轮 ②;**用户确认后再发 issue**):泄漏清单我方维护、对方在生成 / 导出时执行;中训练方式我方定(纯文本 TAPT 不需要转换,可先做),用对方记录在案的 sources 验证我方的 sources 推断;转换器我方写,但直接调用对方的 `export_schema_v1.check()`、`check_trajectory_sources.py`、`sources_provenance_analysis.py`,请对方每个数据集抽查 20 条并说明缺失字段怎么填。

### 0.65 第 56 轮:MS-Swift 整折验收完成(2026-10-22 21:20 UTC)
- LQD_mac 整折(`results/c6_linux2_lora/swift_validation.md`):swift graph 0.878 / text 0.830,train.py 0.790 / 0.821(n=67);差 +0.088 [−0.010, +0.181] / +0.009 [−0.083, +0.088];无 OOM,s/步慢约 5–6%,预留显存 33 GB。**同折上 graph − text 符号在两次训练间翻转**(swift +0.048,train.py −0.031)→ 训练随机波动与 graph−text 效应同量级,C6 每折单次训练,结论需多种子。
- **待用户决定:** MS-Swift 上补种子(先 LQD_mac 与 QD,{graph, text} × 2 个新种子,约 6–7 小时,3 卡);§0.64 的新待办(旧 AEGIS 与 MAA 重叠、公开数据集转 mas-traj/1、中训练)是否现在开始——这项决定是 medical-aegis 在 issue 里转述的,已请用户确认。
- Linux #2 现在 GPU 0、2、3 都空闲(卡 1 是他人任务)。驱动 `mht_work/run_sft_swift.sh` 可直接复用:`GPUS="0 2 3" FOLDS=... VARIANTS=... Q=<新队列目录>`(加种子需在脚本里把 `--seed 0 --data_seed 0` 参数化)。

### 0.64 第 55 轮:C6 完成;swift-plugin 已合并、SFT 迁到 MS-Swift;中训练语料口径已定(2026-10-22 19:20 UTC)
- **C6 结果**(`MedHyperTrace-v2/results/c6_linux2_lora/`,README 有完整表格;逐实例分数 `c6_scores.csv`):n=399,LQD graph 0.701 / text 0.716 / zeroshot 0.611;QD 0.780 / 0.768 / 0.611。graph−text:LQD −0.014 [−0.047, +0.020],QD +0.011 [−0.021, +0.044];微调对 zeroshot +0.09–0.17(CI 不含 0)。**图 token 诊断**:扰动让分数变 0.2–0.4 SD,但 LQD AUROC 在任何扰动下都不降(CI 全含 0),QD 略降 0.005–0.024 → 图 token 跨 MAS 不携带归因信号。**注意:text 基线的候选步骤由该折编码器挑选,不是无结构基线**;要衡量结构的全部价值需要再加一个不用编码器挑候选步骤的 text 变体(待用户决定是否做)。
- **已定(用户同意我方建议):** 中训练**主版本不收任何注入运行的内容(含注入前前缀)**;前缀(W&W-Pro、CORRECT、AEGIS 公开版,按前缀去重、删掉注入步及之后)只进"主版本 + 前缀"的敏感性版本。
- **AgentRx / TRAIL**(`analysis/public_mas_corpus/stats_r55.md`):合计净增 3.37M;AgentRx magentic 的轨迹文本完全来自 Who&When Hand-Crafted(净增 0,只有标注新);**TRAIL 数据卡禁止用于训练自动化人工评估的系统 → 不进中训练,只作外部评测**,且不得在 gated / 私有仓库外转发。主版本干净公开语料仍约 75M(+AgentRx tau_retail 0.12M)。
- **swift-plugin 已合并到 main(d4b358e)**;Linux #2 代码目录已放入 `hgfm/llm/swift_plugin/`(md5 校验)。服务器环境 mht-swift(ms-swift 4.6.0 / transformers 4.57.6 / peft 0.17.1)重跑等价性测试 (a)–(e) 全部通过(loss 差 7e-7,梯度余弦 ≥ 0.9999994,占位符嵌入差 0,打分差 ≤ 2.3e-5)。新驱动 `scripts/linux2_run_sft_swift.sh`(服务器副本 `mht_work/run_sft_swift.sh`,md5 01cf578e…),默认 bs 4×4 与 train.py 一致。swift 日志的 46.3 GB 是**预留**显存(`get_max_reserved_memory`),不是实际占用;我方曾误归因于整段 logits,已撤回。
- **在途:** MS-Swift 整折验收,LQD_mac graph(卡 2)/ text(卡 3),19:11 UTC 开始,约 21:00 结束(`mht_work/swift_queue/status`,日志 `swift_queue/logs/LQD_mac_{graph,text}_bs4.log`)。完成后与 train.py 同折结果(0.790 / 0.821)逐实例配对比较,写 `results/c6_linux2_lora/swift_validation.md`。已设 21:05 UTC 的提醒。
- wandb:服务器已装但**未登录**;用户在 Linux #2 上 `wandb login` 后,驱动会自动切到 wandb(否则用 tensorboard)。
- medical-aegis:sham 验证用户已在对方那边批准。**issue 新评论(18:47Z)已回复(评论 6349178898,19:15:37Z,`docs/interfaces/issue_comment_r55.md`)**:用户决定中训练第 49 轮第 1–3 问由我方做 → **新待办:** ① 核旧 AEGIS 医学合成数据与 MAA 的题目重叠(锚点与 MAA 已核:重叠 2 题 medxpertqa_text_1499 / 1939,这两题的锚点运行不进任何训练);② 自写公开数据集 → mas-traj/1 转换器(字段以 medical-aegis `scripts/export_schema_v1.py`、`docs/requests/` 为准),报告"读取集被槽位唯一确定"比例;③ 中训练先做纯文本 TAPT 基线,再做结构感知中训练。对方待用户决定的花费:llm_debate fmt_v1_1 扩到 20 题($0.09,我方建议做)、mdagents 50 题 sham 复验($0.14,我方建议做)。

### 0.63 第 54 轮:六折配对比较;图 token 诊断在卡 0 后台(2026-10-22 18:20 UTC)
- **六折 LQD 合并 n=399:graph 0.701 vs text 0.716,差 −0.014 [−0.047, +0.020]**(reconcile 是唯一 graph 更高的折,+0.035,CI 宽)。三折时"图 token 变差、CI 不含 0"的说法已不成立;现在的结论是图 token 无可测增益、无可测损害。产物 `MedHyperTrace-v2/results/c6_linux2_lora/compare_gt_6fold.out`。
- **在途(Linux #2):** ① QD graph(卡 3)/ QD text(卡 2)训练预计 18:20 / 18:45 UTC 结束,之后 run_c6.sh 在卡 2 依次跑 7 折 zeroshot + `hgfm.llm.pool`(写 `c6_queue/pooled.txt`,status 末行 `ALL DONE`)。② **图 token 诊断** `mht_work/run_ablate.sh`(日志 `run_ablate.log`,卡 0,18:09 开始):每折输出 `maa/llm/<fold>/ablate_models--Qwen--Qwen3-8B_graph.json`,模式 none / zero_state / mean_state / zero_emb / shuffle_{0,1,2};QD 等其 graph eval 出来后自动接上;LQD 合并 `mht_work/ablate_pooled_lqd.json`(QD 不并入)。代码 `MedHyperTrace-v2/hgfm/llm/graph_ablation.py`(Linux #2 副本 md5 0b9c12b8…,与仓库一致);冒烟已验证 none 与 eval.py 逐条一致。
- **都完成后要做:** 把 `scripts/linux2_compare_c6.py` 写到 Linux #2 跑三方配对(graph / text / zeroshot;QD 单列)→ 把所有 eval_*.json、ablate_*.json、pooled.txt、compare_c6.json 读回并提交到 `MedHyperTrace-v2/results/c6_linux2_lora/` → 写 README 小结。
- §0.62 的"其他待办 / 待用户决定"仍全部有效。
- **安全:** Project 指令里有明文 GitHub token;推送走会话 git 代理,本会话没有使用它。建议用户撤销(第 47 轮已因进程参数暴露提过一次)。

### 0.62 交接时的在途任务(2026-10-22 18:05 UTC,第 53 轮末)
**Linux #2**(Jupyter 连接器 `mcp__Claude-connect-inqi_top__jupyter-mcp-2_linux2_execute_python`;先 `..._linux2_list_kernels` 取 kernel id,sglang kernel 曾是 `ffd58261-5022-427d-86d3-035e82bd2358`;请求约 60 秒超时 → 长任务一律后台 + 日志;工作目录 `/data1/ekyang/cgh/CODE/mht_work`):
1. **LoRA 微调完整跑完(不叫"全量")**:队列 `mht_work/c6_queue/`(status、logs/),主脚本 `run_c6.sh`(日志 run_c6.log)。14 个任务中 12 个已完成;**QD graph(卡 3,18:03 时第 300/≈354 步)与 QD text(卡 2,第 240 步)还在跑**,预计 19:15–19:30 UTC 结束,随后 run_c6.sh 自动跑 zeroshot + `hgfm.llm.pool`。卡 0 worker 已退出。
2. **六折配对比较**已在后台启动:`compare_gt.py` → `mht_work/compare_gt_6fold.out`(LQD_reconcile:graph 0.663 / text 0.629,n=49)。五折结果见 §0.61。读回后填进 RUN 新一轮。
3. QD 跑完后要做:QD 的 graph-vs-text 配对;zeroshot 合并;**图 token 诊断**(对 graph 检查点评测时把图 token 置零 / 样本间打乱,看是否真被使用);把 eval json 和 compare 输出拷回仓库(Linux #2 上的代码目录无 .git,结果需经 kernel 读出后在沙箱里提交,目录建议 `MedHyperTrace-v2/results/c6_linux2_lora/`)。
**其他待办 / 待用户决定:**
- 中训练语料:注入集的干净前缀(W&W-Pro 10.0M、CORRECT 6.4M)是否进主版本;ARIA、AgentErrorBench 未声明许可证;AgentRx 需用户在 HF 接受条款(TRAIL 同);可向 medical-aegis 征求意见。设计优先结构感知中训练(图–文对齐),MAScope 拓扑标签可做辅助目标;中训练文本需在沙箱抽好后再传到 Linux #2(Linux #2 直连 HF 只有约 75 KB/s)。
- 合并分支 `swift-plugin`(27358e9)→ SFT 迁到 MS-Swift(环境 `mht-swift`,`/data/ekyang/anaconda3/envs/mht-swift`);训练加 `--report_to wandb`(用户需自己 `wandb login`)。
- medical-aegis issue #1:我方第 49 轮的中训练问题仍待对方回复;mdagents 30 题 sham(约 $0.08)和 fmt_v1 推广待用户批准。
- HF 只读 token 在 Project doc `UUUooUUU-huggingface-access-token`;用时写到会话临时目录(mode 600),不进 git、不打印。

### 0.61 第 53 轮:HF 收藏夹扩到 15 个;五折配对比较
- 用户收藏夹 `UUUooUUU/public-none-medical-mas-fault-attribution` 新增 9 个:microsoft/AgentRx(gated)、yifanyu/CORRECT-Error(2,226,注入)、ZBox008003/AFTraj(2,276,含 1,162 safe)、Edlison/ARIA(24,468,含 MMLU → 需剔除医学科目)、Leoxx/whowhen_pro(Who&When Pro 可用镜像,text 6.3K)、davide221/agenterrorbench(200)、mascope/mascope-bench(2.2K,含拓扑标签;MAST-clean 需与 MAST-Data 查重)、RogerYao/RAISER(50.2K 行,可能只有标签表)、AI45Research/ATBench(安全轨迹)。统计已完成(`MedHyperTrace-v2/analysis/public_mas_corpus/stats_r53.md`):新增 77.9M token(干净/自然 45.5M、注入 32.4M),干净公开语料合计约 75M(ARIA 占 39M);MAScope MAST-clean 完全是 MAST-Data 的子集;ARIA 已去掉医学 MMLU 2,231 条;AgentRx 需要用户在 HF 接受条款;RAISER 没有轨迹文本。待定:注入集的干净前缀(W&W-Pro 10.0M、CORRECT 6.4M)是否进入主版本。
- LoRA 微调:11/14 完成;五折合并 n=350:graph 0.699 vs text 0.721,差 −0.022 [−0.058, +0.016](详见 `RUN_v0.53.md` 第 53 轮)。剩 reconcile text、QD graph/text,然后 zeroshot + 合并 + 图 token 置零/打乱诊断。

### 0.60 第 49 轮:3 卡 LoRA 微调运行中;中训练与 MS-Swift 规划
- 用户要求:称为"LoRA 微调完整跑完"(不叫"全量");用卡 0、2、3;token 不处理;加 wandb 可视化;引入中训练 / 持续预训练(参考 `mid-training-data-volume-and-selection-survey.md`);训练改用 MS-Swift(装在 conda 环境 ms-swift)。
- 卡 0 worker:`mht_work/worker_gpu0.sh`(共用 c6_queue)。MS-Swift(**已装好**,ms-swift 4.6.0 + transformers 4.57.6 + deepspeed + wandb;`swift pt --help` 已验证):装在 sglang 的离线克隆 **mht-swift**(`/data/ekyang/anaconda3/envs/mht-swift`,脚本 `mht_work/install_swift2.sh`,日志 install_swift2.log);原 ms-swift 环境(Python 3.12)因 torch 下载太慢放弃,只装了一半依赖,未删除。
- 中训练:用户希望纳入公开的非医学 MAS 数据(AEGIS 公开版 9.5K、MAST-Data 1,642、TRAIL 148、Who&When 184;只用文本不用标签),合计约 0.15–0.3B token(TAPT 量级)。语料边界和中训练方式已在 issue 征求 medical-aegis 意见(第 49 轮评论)。用户已确认 SFT 稍后全部迁到 MS-Swift。**插件已写好**:分支 `swift-plugin`(27358e9,未合并),`MedHyperTrace-v2/hgfm/llm/swift_plugin/`,数值上与 GraphTokenLM 等价(详见 `RUN_v0.53.md` 第 52 轮)。公开语料统计见 `MedHyperTrace-v2/analysis/public_mas_corpus/`(AEGIS 公开版全部带注入;Who&When-Pro 发布包损坏;干净公开语料约 30M token)。wandb 需要用户自己 `wandb login`。

### 0.59 第 47 轮:Linux #2 准备中;fmt_v1 复算
- **Linux #2**(Jupyter 连接器,工具名 `mcp__Claude-connect-inqi_top__jupyter-mcp-2_linux2_*`):4×A6000,用卡 2、卡 3;sglang 环境(`/data/ekyang/anaconda3/envs/sglang/bin/python`)已补装依赖;Qwen3-8B 本地目录 `/data1/ekyang/cgh/cache/huggingface_hub/hub/models--Qwen--Qwen3-8B`(训练时 `--lm` 传这个路径);仓库 clone 到 `/data1/ekyang/cgh/CODE/Medhypertrace`(进行中);pip 和 git 走 HTTP 代理 `http://127.0.0.1:23333`。长任务用 nohup,不要依赖 Jupyter kernel 跑完。
- **安全:** GitHub token 已在共享服务器的进程参数里暴露,建议用户撤销。以后不要再把 token 放进命令行。
- **C6 全量正在 Linux #2 上运行(2026-10-22 09:30 UTC 开始,预计约 13 小时)**:`/data1/ekyang/cgh/CODE/mht_work/run_c6.sh`(setsid nohup;仓库副本 `MedHyperTrace-v2/scripts/linux2_run_c6.sh`)。看进度:`cat /data1/ekyang/cgh/CODE/mht_work/c6_queue/status`;队列中断后直接重跑脚本即可(已完成的 ckpt / eval 会跳过;剩余任务在 `c6_queue/jobs`,注意已被取走但没完成的任务不会自动回到队列)。结果在 `mht_work/maa/llm/<fold>/eval_models--Qwen--Qwen3-8B_{graph,text,zeroshot}.json`,合并结果在 `c6_queue/pooled.txt`;Linux #2 上没有 git,要通过 kernel 读回后在本地提交。
- 第 48 轮检查:真实数据吞吐 1,013–1,029 tok/s;每个任务约 95 分钟;graph / text 的 loss 接近(泄漏已修好)。
- Linux #2 网络:代理上游可能断;直连能用 GitHub API(tarball)、codeload、PyPI。连接器单次请求约 1 分钟超时,长命令用后台进程加日志文件。A6000 吞吐 1,087 tok/s。
- medical-aegis:fmt_v1 已去掉格式签名,llm_debate / mdagents 的 sham 仍有措辞签名(清洗后 0.66–0.74);我方负责格式清洗;fmt_v2 暂缓。

### 0.58 第 46 轮:试跑完成;zeroshot 结果
- `MedHyperTrace-v2/results/c6_runpod_pilot/`:A40 稳态 884 tok/s,峰值显存已分配 20.2 GB、已预留 23.4 GB;zeroshot Qwen3-8B LQD 0.616(编码器 0.655,配对差 −0.039,跨 0)。pod 已删除;约 $0.40(账单尚未入账)。
- **全量前必须重跑 `prepare_maa.sh`**:第 45 轮修了导出代码(编码器只用一半训练 run),旧的 graph_tokens 带泄漏。
- 待用户:① 是否在 5090 / PRO 4500 上测吞吐(约 $0.2);② 全量用什么卡;③ medical-aegis 验证批规模(10 题 $0.39 或 20 题 $0.87,我方建议 20 题);④ secret `gh_medhypertrace` 是否删除。

### 0.57 第 45 轮:Runpod 试跑进行中
- **pod `l3s761kur3bb6j`(已于第 46 轮删除)**(mht-c6-pilot,1×A40,CA-MTL-1,$0.59/h,04:21Z 创建,本会话创建 → 可以由我们 stop / delete)。脚本 `MedHyperTrace-v2/scripts/runpod_c6_pilot.sh` 跑完会把结果推到分支 `runpod-c6-pilot` 并自行 stop。新会话:先用 `get-pod` / `stream-pod-logs` 查状态;结果确认已推送后 `delete-pod`(持久盘也会删掉)。
- Runpod secret `gh_medhypertrace`(GitHub token)。用完之后是否删除,问用户。

### 0.56 第 44 轮:C6 上 Runpod 的显存与报价
- `MedHyperTrace-v2/docs/design/C6_gpu_estimate_r44.md`:实测每条 1,238 token(p99 1,812),每折约 6.3k 对、7.8M token;显存估计约 23–26 GB → 选 48 GB 卡;推荐 A40 Secure $0.59/h(1 卡和 4 卡库存均 HIGH)。全量计算费估计约 $15–25(未实测)。
- 计划:先 1×A40 试跑约 1 小时实测,再 4×A40 跑全量。待用户批准,并确定 pod 的代码 / 结果通道(启动脚本 clone + push,需 GitHub token 作为 Runpod secret)。

### 0.55 第 43 轮:Runpod 账户为空;注入的格式签名
- Runpod(MCP 已连,只读):历史账单 $0.00,无 pod / endpoint / volume。用户有 GPU;C6 在哪跑待用户定(Runpod 创建前须报价)。
- **注入格式签名(重要):** PI 和 sham 都会让被注入步少用 markdown(同槽位对照);medagents 上 sham 对同槽位 normal 的 MiniLM AUROC 0.863。TF-IDF 门槛看不到(默认分词丢 `#` `*`)。已请对方在生成端修复并加同槽位门槛;我方待做:节点文本去 markdown 消融。脚本 `MedHyperTrace-v2/analysis/anchor_gate7/`(数据是对方的 `gate7_export.jsonl.gz`,在 medical-aegis `docs/requests/samples/anchor_gate_2026-10-21/`)。
- 锚点上可用的填充目标只有 MAC 334 + medagents 18 步 → C5 暂去掉填充目标。
- 我方预算意见:A–D 先不批,先修格式,再做约 $0.3 的 sham 验证;style_v1 按 `sham_variant` 排除出训练。

### 0.54 第 42 轮:C5 结果——无增益
- `MedHyperTrace-v2/results/c5_maa/README.md`:LQD × 3 种子,微调后 scratch 0.655 / strict 0.643 / shuffle 0.662 / trans 0.672,与 scratch 的差都跨 0,逐种子符号翻转。**不能宣称 C5 有用。**
- 无标签答案流意外度 strict 0.606(高于平凡标量基线 ≤0.511),但打乱 read 边也有 0.594 → 不是结构带来的。
- 环境漂移:同代码同种子与第一阶段差约 0.005;只在同一次运行内比较。
- 下一步候选(待用户):C6 GPU;等 medical-aegis 的来源回答和锚点数据;C9。

### 0.53 第 41 轮:issue 回复 sham_style;C5 两种设定都跑
- 我方 issue 评论 6323377441(18:23Z,全文 `MedHyperTrace-v2/docs/interfaces/issue_comment_r41.md`):(a) 同意配对,sham_style 措辞先改写;门槛加 MiniLM+LR;(b) llm_debate PI 排除出训练;(c) 不做对抗过滤;并请教 C5 填充边(matched / protocol、注入是否改变 sources)。**等对方回复。**
- C5:严格零样本(主)+ 直推,分开报告。先做掩码重建 + 答案流预测;填充目标可配置,默认只用 matched 且最常见模式占比 < 0.9 的(框架 × 阶段)。
- **C5 已实现**:`MedHyperTrace-v2/hgfm/ssl_v02.py`(用法见文件头)。全量 LQD × 4 设定 × 3 种子在后台跑,产物在 `/home/claude/data_maa_v2/c5_lqd/`(`preds.pkl` 支持中断续跑,`results.json`、`log.txt`)。沙箱重置后重跑:先 `prepare_maa.sh` 的第 1–4 步,再运行上述命令(约 2 小时)。
- 更正:MAA 上可用填充目标只有约 9,900 步(72% 来自 colacare review);issue 评论 6323753898 已更正。

### 0.52 第 40 轮:MAA 数据已从缓存重建;C5 方案待确认
- 仓库自带 MAA 嵌入缓存(`MedHyperTrace-v2/data/maa_emb_minilm/`),`prepare_maa.sh` 会自动恢复。C5 只需第 1–4 步;本沙箱已在 `/home/claude/data_maa_v2` 跑完(校验通过、覆盖 85,913/85,913),CPU torch 已装。
- 数据事实:来源 `how` 只有 matched / protocol(都是推断的);protocol 来源由(框架 × 阶段)决定 → 超边填充只用 matched 边;91% 步骤有 `structured.answer`。
- C5 方案见 `RUN_v0.40.md` 第 40 轮,等用户确认后实现。

### 0.51 第 39 轮:新会话续接
- 两仓库已重新挂载、克隆;issue #1 无新评论(最后仍是我方 17:39:01Z)。
- 沙箱已重置:无 torch、无 MAA 数据、无 `.mht_api.env`。做 C5 前需按快速恢复第 3 步重建数据。
- 讨论记录现为 `RUN_v0.39.md`。

### 0.50 第 38 轮:LLM 层代码就绪 + sham 方案
- **LLM 层**:`MedHyperTrace-v2/hgfm/llm/`(README 有完整命令)。服务器上执行 `bash scripts/prepare_maa.sh /data/mht`,然后 `bash scripts/run_llm_folds.sh /data/mht Qwen/Qwen3-8B {graph,text,zeroshot}`。CPU 冒烟测试已通过,**GPU 未跑**,耗时是估算。冒烟产物在 `/home/claude/data_maa/llm_smoke/`。
- **关键对照**:graph 对 text(配对 bootstrap,同 400 例)。text 对编码器 0.645。审计员 0.886 是上限。
- **medical-aegis 改用 sham 安慰剂注入**(v9 第 27 轮)。我方第 39 轮已回复:同意;训练用同槽位 PI / sham 配对;sham 自然答错的不作负例;门槛加 sham 对普通运行;评测分开报告 sham 与自然正常步骤的假阳性率。issue 最后读到 17:39Z。
- **自监督(C5)尚未实现**。候选目标见 RUN_v0.38 第 38 轮第 3 问。数据瓶颈是框架多样性,不是样本数(MAA 共 95,833 步)。

### 0.49 第 37 轮:第一阶段结论
- `MedHyperTrace-v2/results/phase1_maa/README.md`:LQD 零样本下,人工标注上 v0 和 v0.2(C1–C4)相对无结构都不显著(0.634 / 0.638 / 0.645);只有给金标准时 v0.2 比 v0 显著高 +0.040;交互类故障 0.56–0.62。**不能宣称结构提升零样本。**
- 下一步候选:C6 LLM 层(GPU,用户服务器)/ 更强的节点编码器;C5 自监督;C9 只用结果标签的责任分配;锚点数据上的责任层评测。

### 0.48 第 36 轮
- **每次被唤醒(用户消息或后台任务完成)都先跑 `bash MedHyperTrace-v2/scripts/issue_inbox.sh`**;第 26、36 轮两次因专注实验漏看了对方评论。
- MedAgentAudit 评测划分:**只用 LQD(留一 MAS 且题目不重叠,`hgfm/splits_maa.py`)和 QD**;原 LOMO 有题目泄漏,作废。v0 结果见 RUN_v0.36 第 36 轮(结构跨框架零样本无增益)。产物在 `/home/claude/data_maa/out_v0_lqd/`、`out_v02/`(沙箱本地)。
- 锚点 4 个家族:medagents、MAC、llm_debate、mdagents;KAMAC 放弃。PI 门槛未过,对方在修;旧 PI = `pi_variant: v1_signature`,只作压力测试。

### 0.47 第 35 轮:v2 方法本体 = HGFM v0.2(以设计文档为准)
- **`MedHyperTrace-v2/docs/design/HGFM_design_v0.2.md` 是当前设计**,包含文献 → 组件的逐项对照,以及 C1–C9 的实施顺序。`model_v0.py` 只是结构基线 HGNN-baseline,不得称为方法本体。
- 实施顺序:第一阶段 v0 基线跑完 → C1–C4 → C5 → C9 → C6 / C7(需 GPU)。

### 0.46 第 33–34 轮:MedHyperTrace-v2 第一阶段(MedAgentAudit)
- 数据:`GuihaiChen1998/nature-sub-record`(公开仓库,匿名只读 clone,`GIT_LFS_SKIP_SMUDGE=1`)里的 `MedAgentAudit-datasets_and_logs-9.2 - 1.zip.00{1,2,3}`,cat 合并后解压两层,得到 `github_release_files/`。本会话放在 `/home/claude/data_maa/maa2/github_release_files`。用户已确认授权。
- 转换:`MedHyperTrace-v2/data_tools/maa_to_mas_traj.py` → 14,370 条 mas-traj/1(`/home/claude/data_maa/maa_mas_traj.jsonl`)。mdagents 的 basic 有 1,919 / 2,395 条,不使用。与锚点重复的题 2 道(`anchor_overlap_qids.json`)。400 例人工标注对齐见 `maa_human_eval.py`;审计员与人工多数票一致 346/400。
- 嵌入:`hgfm/embed_maa.py`,all-MiniLM-L6-v2,8.6 万条文本,CPU 约 45/s。训练:`hgfm/train_maa.py`(留一 MAS 6 折 + 题目不重叠 1 折,× L0/L2,× 是否给金标准)。
- 只在 MedAgentAudit 体系内;LLM 审计员标签只作弱标签。

### 0.45 第 32 轮
- 已定:全量 normal K=3 + 每题 2 次注入;所有框架轮次上限 2;锚点只用 llama;锚点题 = `anchor_medxpertqa100.json`。锚点当前 = medagents、MAC、llm_debate + (KAMAC 或 mdagents,我方建议 mdagents:KAMAC 在 llama 上招募率 0%,退化成与 mdagents 相同的扇入拓扑)。
- **MedAgentAudit 数据**(14,370 条真实自然失败轨迹 + 400 例人工标注,10 个 MedAgentAudit 故障码):我方请对方写转换器转 mas-traj/1。约束:只进 MedAgentAudit 体系实验(§0.33);LLM 审计标签只作弱标签,评测真值只用 400 例人工;与锚点题干相同的轨迹不进训练;是缺陷层标签。计划作为 HGFM 第一阶段训练数据(自监督 + 缺陷层弱监督 + 人工评测 + 按 MAS 留一)。授权待用户确认。

### 0.44 第 30 轮:锚点与预算
- 用户定锚点 4 个家族:mdagents、medagents、KAMAC、MAC(不用 MA-RAG)。我方建议加 llm_debate(约 $2–3)。
- 我方立场:锚点只用 llama(题目按 llama 的筛选准确率选);K=2 不接受(成败并存期望题数 45 vs K=4 的 79.8,且平票概率 0.5);省钱改为每题 2 次注入;零样本证据 = 主数据留一家族(主张)+ 锚点留一家族(控制),锚点曲线只作趋势。
- dylan / agentverse 只有旧数据,只用于预训练。
- 500 题难度筛选已完成:无污染(打乱前后准确率不降);锚点 100 题从 llama 区间内 151 题分层抽取(`anchor_medxpertqa100.json`)。KAMAC / MAC 已移植(mock)。第 31 轮已明确请对方评估省钱反提案并给出真实单价。

### 0.43 第 29 轮
- 对方已落实:原地改答案 RC、目标池均匀抽取、`labels.outcome`(我方只用 flipped / repaired)、`scripts/quality_gate.py`(已复核与我方一致)、medagents 补 `structured.answer`、MedXpertQA-Text。
- 我方已要求:门槛加 CI + `--min_neg 50`;错误选项按干扰项频率加权;筛选时打乱选项做污染检查(llama 20 题 0.70 高于多数前沿模型的公开成绩);KAMAC / MAC 需要 `how: "control"` 和决策步结构化字段。
- `uth.py` 已支持 control 超边。锚点计划 10 个家族:现有 5 + mav + macnet + MA-RAG + KAMAC + MAC(± MDTeamGPT)。

### 0.42 第 28 轮:试点结论——注入数据有三种强捷径(正式生成前必须解决)
- 试点数据:medical-aegis `docs/requests/samples/pilot_2026-10-20/pilot_export.jsonl.gz`(420 条)。我方分析:`analysis/pilot_20261020.py`(输出 `analysis/pilot_20261020_out.txt`)。
- 内容捷径:单步文本识别注入步 AUROC RC 1.000、PI 0.92–0.95;对"自然答错步"的对照仍有 PI 0.951 / RC 0.991 → 学到的是注入签名。拓扑捷径:medagents #步数 0.950。角色先验:目标固定时 50/50。
- 自然成对样本极少(K=4 时 20 题仅 1–3 题有对有错)→ 需要按难度筛题(normal 准确率 0.25–0.75)。
- 我方提议(已发 issue 评论 6305484990,待用户 / 对方):难度筛题、目标均匀随机、`outcome ∈ {flipped, repaired, benign}`、RC 原地改答案、"注入步 vs 自然答错步"AUROC 作数据质量门槛(0.5–0.7)、锚点 = 现有 5 + mav + macnet + MA-RAG(± MDTeamGPT)。
- 审核脚本已排除题干文本(专家原样引用题干会造成误报)。

### 0.41 第 27 轮
- 对方试点已开跑(400 条:medagents_mc + triage × mercury-2.5-preview / llama-4-maverick × 20 题 × (K=4 normal + 1 inject),inject 中 RC / PI 各半)。**结果出来后我方要做:** `audit_schema_v1.py` 审计 + 超图构建 + 模板捷径量化(TF-IDF+LR 单步篡改检测 AUROC 分 RC / PI;模板检测器步骤定位基线)+ 成对分歧统计(同题 K 次成败共存比例、按 `structured.answer` 的首个分歧步分布)。
- token 数已在 `labels.llm_meta`,step 上只有 `output_tokens_est`;backbone 是候选池,用前问用户。
- 锚点第 6–8 家族我方建议:macnet(按上游语义重新移植)+ mav + camel(改造);autogen 退化不要;待用户定。
- 首要风险:RC 篡改模板文风可识别(旧数据 ca5 模板检测器 0.90);我方提议"改写池"。

### 0.40 第 26 轮:schema v1 已可用,超图构建已跑通
- **每轮开场先跑 `bash scripts/issue_inbox.sh`**(第 26 轮漏看了对方 4 条评论);回复后把最新评论时间写入 `docs/interfaces/issue_last_seen.txt`。
- 对方已交付 `main.py --num_runs K` + `scripts/export_schema_v1.py`(mas-traj/1),14 个框架同一契约,默认注入方案 A(已定案)。样例:其 `docs/requests/samples/schema_v1_mock_export.jsonl`、`real_probe_2026-10-20/`。
- 我方:`ours/hgfm/uth.py`(mas-traj/1 → 统一轨迹超图)、`ours/hgfm/audit_schema_v1.py`(泄漏 / 来源 / token 侧信道审计)。**token 计数不得作特征**(RC 步骤侧信道)。
- 旧数据规则:`common/clean_inputs.py`(干净输入)+ `common/old_data_filters.py`(ca/ca5 无效注入、ca5 Planner)。
- backbone(用户定):文本 mercury-2.5-preview + llama-4-maverick,图像 Ling-3.0-flash-VL,音频 mimo-v2.6-flash。
- 待用户:补 macnet / autogen / camel(仅锚点);400 条试点($6–12)。

### 0.39 medical-aegis 新框架与旧数据剔除规则(第 25 轮)
- 对方已集成:medagents_mc、consensus + 4 个辩论类基线(SleepEDF / WESAD)、mam(音频)、triage_agent;mock 样例在其 `docs/requests/samples/`,我方核对泄漏 0、漏记 0。
- 家族分组(我方已确认,10 个):debate{llm_debate, consensus_debate/mad/reconcile/cmd}、modality_fusion{consensus}、mdagents、medagents、dylan、agentverse、clinical_agent{两版本}、cmas、mam、triage。锚点 MCQ 上目前 5 个家族,建议补 macnet > autogen > camel。
- **旧数据剔除规则(硬约束):** clinical_agent / clinical_agent5 中"所有注入都是 direct_prepend"的轨迹(ca 151/402、ca5 614/1052)注入未生效(概率 bug),不作归因监督与评测,只作无标签自然失败轨迹。第 10 轮 clinical_agent PI 子集结论需剔除后重算。
- 我方建议的对方顺序:导出器 + K 次重复 → medagents_mc + triage 真实小试点 → 迁移旧 wrapper → 补通用框架(待用户定)。

### 0.38 medical-aegis 进展与我方建议(第 24 轮)
- 对方已回复 issue #1(两条评论)并集成 MedAgents(`medagents_mc`,mock 样例在其 `docs/requests/samples/`);用户定的后续:ConSensus(WESAD + SleepEDF,含 6 个 MAS 基线)→ MAM(Heartbeat / Sound-Dr,mimo-v2.6-flash 音频)。
- 我方回复 issue #1 评论 6286759271 + 规格增补 v1.1(在 spec 文档末尾):`agent_id` P0、`structured` P0、`framework_family` P0、`sources[].how`、`task.observations[]`、锚点任务(固定 100 题医学 MCQ)。
- **旧数据干净输入已修复:** `common/clean_inputs.py`,5 框架 PI 步骤 100%;HGFM 读旧数据必须先过它。
- 评测口径改为留一**家族** + 锚点任务上的缩放曲线(设计草案已同步)。
- 下一步(我方):对方 schema v1 导出器和 K 次重复做好、mock 更新后,在 mock 上跑通超图构建。

### 0.37 与 medical-aegis 的统筹(第 23 轮)
- 用户安排:轨迹语料(模拟故障 + 真实故障)由 `chancanmakeit/medical-aegis` 负责(可写;新会话需 add_repo push)。**两项目沟通走 GitHub issue(用户要求)**:[medical-aegis issue #1](https://github.com/chancanmakeit/medical-aegis/issues/1) 是我方需求,完整规格在其 `docs/requests/2026-10-19_from_medhypertrace_HGFM_trajectory_spec_v1.md`(本仓库副本 `docs/interfaces/medical_aegis_trajectory_spec_v1.md`)。**新会话先看 issue 评论**:`gh api repos/chancanmakeit/medical-aegis/issues/1/comments --jq '.[].body'`(只能用 REST,GraphQL 被禁)。以后对方需要我方做什么,也请对方在 Medhypertrace 开 issue。
- 关键需求:统一 schema v1(labels 与 steps 分离、干净的注入前输入、`sources`、`event_ids`、`question_id`+`run_index`)、≥8 框架、normal 每题 K=4、≥2 个 backbone。
- **标签泄漏警告:** 现有 AEGIS 合成数据的 PI 步骤 `input_messages` 含注入指令原文(mdagents / clinical_agent / ca5 100%),HGFM 不得把它当节点文本;MHT 现有代码不受影响。
- 待用户决定:注入频率 A / B(我方倾向 A);对方试点成本。

### 0.36 主线:超图基础模型 HGFM(第 22 轮)— 用户军令状
- 用户定:基于结构化 JSON 轨迹的文本属性超图,训一个**超图基础模型**;处理图特征、推理是附带能力。**不复现 AFANet 作前置检验**(AFANet 仍是论文基线)。
- 设计草案:`docs/design/HGFM_design_v0.1.md`(新会话先读这个)。
- 数据依据:`analysis/read_hyperedge_stats.py`——AEGIS 每步有 `input_messages`,"读集超边"可通用恢复;读≥3 个前序步的比例 dylan 62%、llm_debate 38%、ca5 24%、clinical_agent 20%、mdagents 17%(第 23 轮更正:排除 User 提示条目后各框架 agent 步缺输入均为 0%)。
- 语料由 medical-aegis 项目负责(见 §0.37)。

### 0.35 图方法 MAS 故障归因文献与新颖性定位(第 21 轮)
- 用户文献仓库 `chancanmakeit/graph-based-mas-fault-attribution-papers`(可写,新会话需 add_repo push 权限):原有 3 篇 + 本轮新增 42 篇,分 `01_graph_based_attribution/` `02_attribution_landscape/` `03_graph_hypergraph_adjacent/`,各有 `INDEX.md`;`notes/positioning_hypergraph_llm.md` 是定位分析(本仓库 `docs/lit/graph_mas_attribution_positioning.md` 为同一份)。
- 用户定的新颖点:超图 + 图特征与 LLM 推理结合。核对后:HPFA(COLM 2026)已用超图做归因(单智能体、未编码),AFANet 已用 GCN 做归因并做了 AEGIS-Bench→Who&When OOD;"被编码的 MAS 超图 + LLM 融合"仍空。
- 首要基线:AFANet(同 AEGIS-Bench)、CHIEF/AIG(免训练)、GraphTracer、MHT、猜第一步。
- MedHyperTrace 是本项目自己的方法(用户确认),新方法是对它的改进或替代。

### 0.34 新方向:(超)图大模型做跨框架零样本故障归因(第 20 轮,2026-10-19)— 讨论中
- 用户提出:把 MAS 的 JSON 轨迹建成文本属性图 / 超图,训 graph+LLM / hypergraph+LLM 模型,跨 MAS 框架零样本(最多 adapter 适配),区别于"训 LLM 读轨迹推理"。
- 已精读 118 篇图大模型调研(源:`private-documents/muse-ai/graph大模型118篇全文解读.md`,该仓库是本 Project 的同步源)。**新会话先读 `docs/lit/graph_llm_118/00_synthesis.md`**,需要细节再查 `p1`–`p6`(按论文编号)。
- 关键判断:118 篇无 agent 轨迹故障定位先例,无跨拓扑零样本成功先例;MedHyperTrace 已是异构超图,新颖性须来自跨框架零样本 + LLM 耦合 + schema 无关构图。
- 参考轨迹:`chancanmakeit/TriageAgent` 的 `results/showcase/trajectory_Test-1_case2.json`(格式与 AEGIS 不同)。
- 下一步:新颖性检索(MAS 故障归因的图方法)→ 定任务形式 → 5 个合成框架留一框架零样本的可行性检验(PI 子集)。

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
