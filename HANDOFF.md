# MedHyperTrace 会话交接文档

**最后更新:** 2026-11-08 12:45 UTC(第 101 轮续;第 7 个会话) · **原始版本:** 2026-10-08
**项目:** 医学多智能体系统故障归因 → 本仓库是其中的「故障归因方法」子项目(另一个子项目「人机协同自动化标注」提供人类标注,接口见 `docs/annotation_interface_v1.md`)
**用户:** Alvin Chan(清华,ML/NLP researcher;偏好直接的 peer-level 技术交流、要诚实批评而非附和、要求实证核对而非臆断)

> **新会话开场顺序:** ① 本文 §0(当前状态)→ ② 最新的 `RUN_v0.<N>.md`(讨论记录,文件名带版本号,N=轮次)的最后两轮 → ③ 按需读 `RUN_EXPERIMENTS.md`(完整实验命令)和 `docs/`。
> **仓库:** https://github.com/chancanmakeit/Medhypertrace (**私有仓库**,2026-10-09 起)。§一 以下是 2026-10-08 旧会话的内容,§0 中与之冲突的以 §0 为准。

> **⚠️ 第 34 轮(2026-10-21)起目录重组(用户要求):** 原方法 = **MedHyperTrace-v1**,全部代码 / 数据 / 结果移入 `MedHyperTrace-v1/`;新的超图基础模型 = **MedHyperTrace-v2**,代码在 `MedHyperTrace-v2/`。根目录只留 `README.md`、`HANDOFF.md`、`RUN_v0.<N>.md`。**本文 §0.3x 及以前出现的路径,v1 的一律加前缀 `MedHyperTrace-v1/`**(例如 `scripts/restore_env.sh` → `MedHyperTrace-v1/scripts/restore_env.sh`、`eval_mafa/` → `MedHyperTrace-v1/eval_mafa/`);**v2 的对照表:** `ours/hgfm/*` → `MedHyperTrace-v2/hgfm/*`(包名 `hgfm`,在 `MedHyperTrace-v2/` 下 `python -m hgfm.<模块>`);`data_tools/*`、`common/clean_inputs.py`、`common/old_data_filters.py` → `MedHyperTrace-v2/data_tools/`;`analysis/{read_hyperedge_stats,pilot_20261020}.py` → `MedHyperTrace-v2/analysis/`;`docs/{design,lit,interfaces}` → `MedHyperTrace-v2/docs/`;`scripts/issue_inbox.sh` → `MedHyperTrace-v2/scripts/issue_inbox.sh`。v1 用 `validate.py` 和 `ours/train_hgnn.py --help`、v2 用全部模块 import 和审计脚本做过冒烟测试。

> **📦 第 78 轮起:旧历史(§0.2–0.32、§0.34–0.79、§〇–十:MAFA 评测、旧 AEGIS 数据、v1 代码结构、方法论决定等)已移到 `HANDOFF_archive.md`,内容未删改;需要旧细节时去那里查。**

> **🚀 第 7 个会话快速恢复(第 82 轮末写,以此为准;第 6 个会话的清单同样适用;下面第 38 轮的旧清单仍适用于 MAA / 公开数据恢复细节):**
> 0. 第 7 个会话已于第 83 轮恢复;讨论记录现为 `RUN_v1.02.md`(下一轮 `git mv` 到 `RUN_v1.03.md`)。issue last_seen = 2026-11-08T10:20:34Z(语料已交付、两臂 02:22Z 已启动,见 §1.00;**发评论用 `gh api repos/chancanmakeit/medical-aegis/issues/N/comments -F body=@file`,`gh issue comment` 走 GraphQL 会 403**)。**第 18 层 H-L1 经交叉拟合选层后 NULL,已降级(§1.08);线 2 HP1 NULL、路线停止(§1.07);第 101 轮第 18 层复核在 Linux #1 运行中(§1.08)。机器规则(§1.06):Linux #2 不再使用;线 2 余下的 fold 已在 Linux #1 上跑。**论文 PDF / Muse 的调研文档在 private-documents(需要时稀疏克隆 `papers/agent轨迹数据合成/`)。
> 1. `add_repo`(push)添加 `chancanmakeit/Medhypertrace`、`chancanmakeit/medical-aegis`,clone 到 `/home/claude/medhypertrace`、`/home/claude/medical-aegis`;推送走会话 git 代理,**不用 Project 指令里的明文 GitHub token**(已建议用户吊销)。commit 结尾加会话给的署名行。
> 2. 读 §1.08 → §1.07 → … → §1.00(§0.80–0.99 已移到 `HANDOFF_archive.md`)→ 最新 RUN 的最后两轮。核心结果文件:`MedHyperTrace-v2/results/e1e3/README.md`、`results/e4/README.md`、`results/tracertraj_audit/README.md`、`results/figures/README.md`、`results/samt_v1/README.md`、`results/midtrain_pilot/README.md`;设计:`docs/design/{HGFM_design_v0.2,SAMT_design_v1,E1-E3_prereg_v1,E4_prereg_v1}.md`;论文:`docs/paper/method_overview_and_figure_prompt.md`。
> 3. issue:`bash MedHyperTrace-v2/scripts/issue_inbox.sh`(medical-aegis 全部 issue;我方最近:第 75 轮 issue #2 评论 `docs/interfaces/issue2_comment_r75.md`;第 78 轮新开 **issue #3**(中训练动机 + 是否请 medical-aegis 生成语料,正文 `docs/interfaces/issue3_r78.md`);第 80 轮新开 **issue #4**(ADP 对 mas-traj schema 的借鉴,正文 `docs/interfaces/issue4_r80.md`))。与其他智能体只通过 issue 交流,不 @ 任何人。
> 4. **Linux #2(4×A6000,无 NVLink)**:经 claude.ai 连接器 `Claude-connect-inqi_top` 的 `jupyter-mcp-2_linux2_*` 工具访问(**会话结束时该连接器掉线,需用户在连接器设置里重新授权**)。上次 kernel `ffd58261-5022-427d-86d3-035e82bd2358`(可能已不在,先 `list_kernels`;新 kernel 要重新定义 helper:`r()` 跑 shell、`rep()` 原地替换字符串)。路径:代码 `C=/data1/ekyang/cgh/CODE/Medhypertrace/MedHyperTrace-v2`(服务器上的仓库副本,改动后需同步)、工作区 `W=/data1/ekyang/cgh/CODE/mht_work`(`e1e3/`、`e4/`、`midtrain/`、`tracertraj/agentracer-data-v1.0.0`、`wheels/`)。环境:MS-Swift 4.6、flash-attn 2.7.4.post1、liger-kernel 0.7.0、peft 0.17.1;长单元格容易 520 / 超时,单元格要短、长任务用 nohup 后台 + 状态文件。沙箱访问不了服务器文件,数据传输靠 kernel 打印(zlib + base64 + md5 核对)。
> 5. 密钥:HF token 从 Project doc `UUUooUUU-huggingface-access-token` 读,写 600 文件,不上命令行;API 端点从 Project doc `claude/api端点` 读,写 `/home/claude/.mht_api.env`,绝不进 git;**任何付费 API 调用前先试跑估算成本,问用户**。
> 6. 规则:每轮 `git mv RUN_v0.<N>.md` 到新轮次并追加;更新本文 §0;commit + push;同步 Project doc `claude/HANDOFF_MedHyperTrace.md`;sleep ≤ 约 60 秒;MAST 与 MedAgentAudit 数据 / 结果分开;责任层评测必须报告长度 / 位置基线和长度控制结果;外部数据按"题干归一化 + Jaccard ≥ 0.3,按题目分组"去重;主线 = 文本属性超图上的超图基础模型,**基础模型必须经中训练 / 续训预训练获得**;用户要直接、同行式的批评和实证核对,用中文交流。
> 7. **阶段 0 已完成(§0.93、§0.94),纯语言建模中训练配方停掉;等用户定下一步中训练目标**(候选:GPT 的关系类混合目标 / 零训练 loss 诊断 → 格式 2×2 / 三种步骤表示比较 / 阶段 1 付费生成按约 $8.78 每千条重估;loss 诊断免费可并行)。 阶段 0 内容回顾: ① 标签效率曲线(TracerTraj 100 / 300 / 1000 / 全量);② 负对照中训练(shuf / irr,与 R 同 token 量);③ 剂量 24.5M → 34.4M(full);④ 按题目分组的 manifest + 基准审计表。预注册 v2(替换步检测)等阶段 0 结果后再议。阶段 1(medical-aegis 付费生成)等 issue #3 报价 + 阶段 0 结果。用户已开始写论文(Method 图提示词已给)。

> **🚀 旧版快速恢复(第 38 轮写,恢复 MAA / 公开数据时参考):**
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

### 0.31 预注册 dev/test 划分(第 11 轮,MAFA `3d80c11`)— 硬约束
- `review_packages/eval_split_v1.json`:dev 120 / test 240(按轨迹,框架 × 答对/答错分层)。成员哈希 `916fee301529…`(文件本身 sha256 不同,是正常的)。**只在 dev 上开发、调参;test 只在最后评一次。** 评分加 `--subset dev`。
- v2 演练集 `results/human_like_eval_v2/`(19 条,全在 dev)已跑通三层评分,产物在 `eval_mafa/out_v2/`。
- **泄漏(第 13 轮定稿,判定=题干相同,影像题加图片):** 答对轨迹 180/180 题目在合成数据里(129 条在同框架训练集),部分步骤完全相同;答错轨迹 dev 3/60(`5badfa1f` 仅在合成测试集)、test 1/120(`40d2f70f`)。结果按 `eval_mafa/out_v2/leakage_package.json` 的逐条标记分开报告。
- 目标(与 MAFA 对齐,接口 §6.7):答对轨迹上做**缺陷层**(有哪些缺陷,没有就输出「无」;答对 ≠ 无缺陷);责任层只在答错轨迹。方法缺口:目前无法输出「无」。
- **人类标签回来前不在 dev 的 LLM 标签上调参**,只搭框架、跑通流程。

### 0.33 硬规则:MAST 与 MedAgentAudit 分开(第 17 轮,用户要求)
- 所有评测、表格、结论都按体系分开;**任何数字不跨体系合并**(不同标签定义;同一轨迹会被算两次;MHT 只懂 MAST)。`evaluate.py` 已按体系输出并断言。
- 第 11、13、15、16 轮汇报过的 v2 / closest v2 合并数字作废,以 `RUN_v0.17.md` 的分体系表为准。
- 合成训练数据只有 MAST 码;MAA 上的结果是「迁移到另一套定义」,论文中单独报告。

### 1.08 第 101 轮:第 18 层复核预注册 + Linux #1 运行中;R1b 已请报价(2026-11-08 10:25 UTC)
- **用户(第 101 轮):**
  - 问 Q0–Q3(已答:所有臂都从后训练版出发,Base 从未训练;LM-CPT 有冻结读出和接后训练两种读法;ICPT 是并行臂;串行 LM-CPT → ICPT → 后训练没试过);
  - 4 "H-L1 按你推荐来";5 "检查之前的阴性结论";6 "P-TT 可以记录,后续也可以考虑作为附录拓展"。
- **串行臂 Q3 的处理:** 不直接开。触发条件:R2.5 在 L18 上 icpt − lm 显示优势(哪怕只过未校正门槛)→ 写修正案,开"串行臂 + LM-CPT 2 倍剂量对照";仍 NULL → 不做。
- **预注册** `MedHyperTrace-v2/docs/design/Layer18_recheck_prereg_v1.md`:
  - e4d8048(10:04 UTC);C1 澄清 6fad6ea(约 10:17,驱动 10:15 启动,当时尚无任何特征或结果)。
  - **R1a:** 交叉拟合选层,8 层 {9,12,15,18,21,24,27,36},按 question_id 用种子 0 分两半,只看 it 选层,在另一半上测 lm − it,§4.3 规则。
  - **R1b:** 在新数据上真复现,固定 L18 + agg。issue #1 评论 6720288063 请 medical-aegis 报价(约 250 个父运行,备选 150 个)。**报价回来先给用户,批准前不生成。**
  - **R2:** 固定在 L18 复核 E4 stage A、阶段 0 Q1 / Q2 / Q3、ICPT H1–H4。
    - Holm family 共 12 个比较。只有判 HOLDS 且 Holm 校正后仍 < 0.05,才写"在 L18 被推翻";HOLDS 但没过 Holm 的写"需复现"。
    - E1 OAT 不在 L18 重跑。Q2 规则用 LE 面积代替 E1;Q3 只能判"部分 NULL"。
  - C1 还写明:base = it(后训练版);ICPT 主接口是前缀特征(`e4_features`)+ agg;`feat_query` 是次要接口。
- **代码:**
  - `hgfm/icpt/feat_query.py` 新增 `--layer`;
  - `scripts/linux1_run_layer18_recheck.sh`:单队列 4 卡,先医学后公开,再 CPU 打分,最后探针和分析;
  - `scripts/l18rc_analyze.py`:med / pub 两个子命令,已在合成数据上测通。
  - Linux #1 上的副本 md5 一致。
- **Linux #1 运行:**
  - 输出目录 `/data1/cgh/code/mht/runs/l18rc/`(`status`、`feats/`、`w/`);10:15 UTC 启动,可重跑续接。
  - 7 个模型(tapt / S / R / full / irr / shuf / tapt_clean)经局域网从 Linux #2 拷到 `models/<name>/`:脚本 `xfer/r101_copy.sh`,日志 `xfer/r101_copy.log`(以 ALLDONE 结尾),按大小核对。
    - Linux #2 上的 http.server 端口 18101(pid 1694917),拷完要关。
    - `eval_clean_keys.json` 也已拷到 Linux #1 仓库,md5 一致。
  - **预计耗时:** 医学特征约 1.5 小时出 R1a / R2.5 / R2.6(`runs/l18rc/med_results.out`);公开集 8 个模型每个约 2.8 GPU 小时,4 卡并行约 7 小时后出 R2.1–R2.4 和 Holm(`pub_results.out`、`stage0_L18.out`、`icpt_le_L18.out`)。
  - base / lm 的公开 L18 特征复用 `xfer/pub_it_L18.pt` 和 `runs/layer18/pub_lm_L18.pt`。
- **P-TT** 已作为附录候选 A1 写进 `MedHyperTrace-v2/docs/paper/appendix_candidates.md`。
- **医学部分结果(12:38 UTC,`MedHyperTrace-v2/results/layer18_recheck/README.md`):**
  - **R1a NULL:** 两半都选 L21;lm − it +0.0002 [−0.015, +0.015]。**H-L1 降级为"未复现(选层敏感)"。**
  - **R2.5 主接口:** H1 icpt − lm −0.008,NULL → 串行臂未触发。次要的查询接口 icpt − lm +0.049,只来自没见过的框架,绝对值 0.606 没超过最好的冻结基线 → 报告给用户。
  - **R2.6:** tapt +0.017、irr +0.009 → L18 上的差值看起来是 CPT 的一般扰动。
  - Linux #2 http.server 已关。
- **还在跑:** 公开部分(探针 + stage0_analyze + l18rc_analyze pub),约 19:00 UTC;看 `runs/l18rc/status` 里的 "DONE pub analysis" 和 `pub_results.out`。
- **待用户决定:** R1b 是否还值得付费;是否追查查询接口的信号。

### 1.07 第 100 轮:线 2 结果——HP1 NULL(显著为负),路线停止;HP2 公开集成立(2026-11-08 07:05 UTC)
- **结果:** `MedHyperTrace-v2/results/posttrain/README.md`;原始输出在 Linux #1 `/data1/cgh/code/mht/work/posttrain/`。
- **HP1:** P-MED − F-LOFO = −0.064 [−0.115, −0.017](去掉 mdagents 后 −0.078)。P-MED 控制后 0.505、原始 0.696,学到的是捷径。**按预注册停掉这条路线,不扩付费标签**;issue #1 6718517591 已撤回报价请求。
- **HP2:** P-TT − F-TT 公开集 +0.068 [+0.032, +0.104] → HOLDS;零样本迁移到医学 −0.007。**HP3:** +0.084 HOLDS,但 P-MED/TT 只回到冻结基线水平(+0.021)。
- **bridge(08:59 UTC 完成):** pmedlm − pmed +0.054 [+0.021, +0.088] HOLDS;pmedicpt − pmed 未定;pmedicpt − pmedlm −0.028 显著为负。pmedlm 控制后 0.559,仍低于冻结探针 0.569 和 TT 初始化 0.589。**线 2 全部完成,Linux #1 上没有在跑的任务。**
- **待用户决定(第 101 轮已决定,见 §1.08):** H-L1 复现按我方建议;复核之前的阴性结论;P-TT 记为附录候选。

### 1.06 用户决定:机器使用(2026-11-08 03:06 UTC)
- **用户:** "等 Linux #2 上目前的实验做完之后,就先不用 Linux #2,我们这边的实验都在 Linux #1 上做。"
- **执行:**
  - Linux #2 上只让正在跑的线 2 驱动(`scripts/linux2_run_posttrain.sh`:P-TT → P-MED ×7 → P-MED/TT ×7 → 评测 → bridge)继续,**不再往 Linux #2 派任何新任务**,包括特征抽取、stageA、med_eval、拷数据以外的计算。
  - 新实验一律放 Linux #1:代码 `/data1/cgh/code/mht/MedHyperTrace-v2`,数据 `work/`,模型 `models/{lm,it}`,Base 在 `/data1/cgh/cache/huggingface/models/Qwen3-8B-Base`;GPU 与他人共用,每卡约 26 GB 空余,训练用 ZeRO-3。
  - Linux #2 上需要的旧产物(G0 特征 / 打分等)按需经局域网拷到 Linux #1。
  - **用户 04:32 UTC 决定:剩下的 fold 挪到 Linux #1。已执行:**
    - P-TT 和 pmed_mdagents 在 Linux #2 完成,已拷到 Linux #1 的 `work/posttrain/`;Linux #2 上已没有本项目任务。
    - Linux #1 驱动 `MedHyperTrace-v2/scripts/linux1_run_posttrain.sh` 04:40 启动(4 卡 × accum 8;PostTrain 修正案 A1),状态文件 `/data1/cgh/code/mht/work/posttrain/status`,可重跑续接。
    - 产物:pmed_* / pmedtt_* / pmedlm_* / pmedicpt_* 目录,以及 eval_{med,pub,bridge}.{json,out}。
    - 读结果按 PostTrain 预注册 HP1 / HP2 / HP3 判定,并另报不含 mdagents 的 HP1 敏感性结果。

### 1.05 第 99 轮:第 18 层 H-L1 成立(同机确认);闸门 G UNCLEAR;issue #3 已通报(2026-11-08 01:10 UTC)
- **H-L1(lm(18) − base(18),医学 agg,控制后):** 同机重算 +0.0169 [+0.0034, +0.0316],网格 6/6 → **HOLDS**;linear 未定。两台机器的特征逐位相同。详见 `MedHyperTrace-v2/results/outcome/README.md` 第 18 层一节。
- **闸门 G(it18):** probe 有效(末步 AUROC 最小 0.628);drop 判 UNCLEAR → 不训练 ocpt。
- **issue #3 6715423327** 已通报;last_seen = 2026-11-08T01:07:13Z。
- **公开集次要比较(02:55 UTC 完成):** agg 控制后 lm − base +0.020 [+0.0001, +0.041],linear +0.012(不显著);原始值 linear 为 −0.022。方向和医学集一致,但很勉强。打分结果在 Linux #2 `mht_work/outcome/g0/l18/`。
- **还在跑:** 线 2 P-TT(Linux #2 GPU 0,1),约 05:30 UTC 结束,然后是 7 个 P-MED fold。
- **待用户决定:** H-L1 怎么复现(新数据,或按题目切半、事先登记);是否预注册在第 18 层回头检查之前的阴性结论;线 2 是否改用第 18 层(要先修改预注册)。

### 1.04 第 98 轮:G0 → it18(case L);Linux #1 抽第 18 层特征;线 2 已恢复(2026-11-07 22:55 UTC)
- **G0 结论:** switch_to = it18(与 b18 打平)。Base 与后训练版同层比较为 NULL,起作用的是层;证据强度一般(网格 1/6,公开集 agg 为负)。详见 `MedHyperTrace-v2/results/outcome/README.md`。
- **A2 case L 正在执行(Linux #1):**
  - 状态 `/data1/cgh/code/mht/runs/layer18/status`;驱动 `MedHyperTrace-v2/scripts/linux1_run_layer_feats.sh`(LAYER=18,可重跑)。
  - 输出:`med_lm_L18.pt`、`pub_lm_L18.pt`、`corpus_it_L18.pt`、`med_lm.json`、`hl1.{json,out}`(H-L1 判定)、`gate_it_L18.{json,out}`(闸门 G 重跑)。
  - 模型在 `/data1/cgh/code/mht/models/{lm,it}`。
- **结果出来后:**
  1. H-L1 按 interaction-CPT §4.3 规则判定;
  2. 闸门 G 在 it18 上按 §1 规则判定,GO 才训练 ocpt 臂;
  3. 公开集 stageA(次要):把 pub_lm_L18.pt 经局域网拷回 Linux #2,用 e4_probe 跑 base=pub_it_L18 vs lm=pub_lm_L18。
- **线 2:** 22:33 在 Linux #2 GPU 0,1 自动恢复(`mht_work/posttrain/status`)。

### 1.03 第 97 轮:G0(后训练版 vs Base × 层)运行中;闸门 G 判 UNINFORMATIVE;Linux #1 准备 Base 实验(2026-11-07 16:55 UTC)
- **用户要求:**
  - 先做冻结检查 G0,看 Base 和中间层是否更好(修正案 A1,4ec524a);
  - 下载 Qwen3-8B-Base;Base 上的续训实验放在 Linux #1(代码放 `/data1/cgh/code/`,HF 缓存放 `/data1/cgh/cache/huggingface`,conda 环境 `ms-swift`;四张卡每卡剩约 26 GB,小 batch / ZeRO-3 / 张量并行)。
- **闸门 G(参考配置):**
  - probe 留出末步 AUROC 最小值 0.592 < 0.60 → **UNINFORMATIVE**;
  - drop 控制后 0.500 [0.458, 0.541];
  - 不启动 ocpt 臂。结果写在 `MedHyperTrace-v2/results/outcome/README.md`。
- **G0(Linux #2,`scripts/linux2_run_g0.sh`):**
  - 状态文件 `mht_work/outcome/g0/status`,最终结果写入 `g0/g0.out`(含 DECISION 行);
  - GPU 0 跑后训练版,GPU 1 跑 Base(检测到 `mht_work/dl_base.log` 出现 `^done` 后才开始);
  - 结束后自动重启线 2 驱动(线 2 目前暂停)。
- **Base 模型下载(`scripts/pdl.py`,走 ModelScope 直连,用 `qwen3_8b_base_meta.json` 校验 sha256):**
  - Linux #1 → `/data1/cgh/cache/huggingface/models/Qwen3-8B-Base`,log `/data1/cgh/code/mht/pdl_base.log`;
  - Linux #2 → `/data1/ekyang/cgh/models/Qwen3-8B-Base`,log `mht_work/dl_base.log`。
- **网络要点:**
  - 两台机器都能直连 ModelScope 和清华 PyPI;
  - Linux #2 的 HTTP 代理 23333 总带宽只有约 1.4 MB/s;
  - Linux #1 的 SOCKS 11111 很慢,而且 SSL 会断。
- **Linux #1 连接器:** `jupyter-mcp_*`,kernel `17b8b4c1-4eb4-45ce-8509-1bdf4b8088a8`,其中已定义 `mht_r`。
- **Linux #1 环境已就绪(17:58 UTC 核实 ENV OK):** conda `ms-swift`(Python 3.12),torch 2.6.0+cu124、transformers 4.57.6、swift 4.6.0、peft 0.17.1、deepspeed 0.19.8、flash-attn 2.7.4.post1;安装脚本 `/data1/cgh/code/mht/install_env.sh`(清华源)。两台机器的 Base 都已下载并通过 sha256 校验。
- **G0 进度:** 预计约 19:15 UTC 抽完特征,然后 stageA、med_eval、g0_compare。**用户要求 Linux #2 的 GPU 2,3 留空**(上面现在跑的是用户另一个项目的 lewm 训练)。
- **用户授权(18:26 UTC):** G0 有胜出配置时,写好修正案后直接开训,不用再问。**修正案 A2 已写好(ce75abb,早于 G0 读出)**,规定 Base 胜出(case B)、中间层胜出(case L)、没有胜出三种情况怎么做。
- **Linux #1 已就绪:** 代码 `/data1/cgh/code/mht/MedHyperTrace-v2`;语料 `xfer/lm.jsonl`;评测数据 `work/`(结构与 Linux #2 的 mht_work 相同)。
  - Base 胜出时的启动命令:`cd /data1/cgh/code/mht && LAYER=<l> setsid nohup bash MedHyperTrace-v2/scripts/linux1_run_base_lm.sh > runs/base_lm_driver.log 2>&1 < /dev/null &`
  - 用 ZeRO-3,约 76 s/步,约 16.5 h;状态文件 `runs/base_lm/driver_status`。
  - 两台机器同在 10.171.26.x 局域网:在发送端 `python -m http.server <port> --bind <ip>`,接收端不走代理 curl,约 117 MB/s;传完关掉服务。
  - /data1 是机械盘,加载模型前先 cat 一遍权重做预热。
- **待办:**
  1. 读 G0 结果,按 A1 规则判定,再按 A2 执行(case B → 在 Linux #1 启动上面的驱动;case L → 在 Linux #2 重抽 lm 臂第 l 层特征);
  2. Base-lm 训练完成后,把特征传回 Linux #2,对照 G0 的 b_l 特征跑 med_eval / stageA(H-B1 / H-B2);
  3. 闸门 G 在胜出配置上重跑;
  4. 线 2 自动恢复后监控;
  5. issue #1 等报价。

### 1.02 第 96 轮:线 2 和线 3 启动(2026-11-07 15:40 UTC)
- **用户决定:** 做线 2(用反事实标签做后训练)和线 3(继续中训练,但先说明凭什么这次会不一样)。训练用 GPU 0,1(即使有他人占用)。
- **预注册:** `docs/design/PostTrain_prereg_v1.md`(线 2;主假设 HP1 = P-MED − F-LOFO,医学集控制后);`docs/design/OutcomeCPT_prereg_v1.md`(线 3;先跑零训练闸门 G,GO 之后才训练 ocpt 臂,对照 lm 臂)。
- **服务器:**
  - 线 3 闸门:`mht_work/outcome/`(status、featscorpus_base.pt、gate_base.{out,json});
  - 线 2:`mht_work/posttrain/`(status;驱动 `scripts/linux2_run_posttrain.sh`,可重跑,有 scores.json 的步骤会跳过;评测脚本 `hgfm.posttrain.posttrain_eval`)。
- **待办:** 读闸门结果;GO 的话 ocpt 需要先改 build_icpt 加 `[OUTCOME]` 渲染,并问用户 GPU 怎么安排;issue #1 6709060723 在等报价;付费生成需要用户批准。

### 1.01 第 95 轮:交互式续训实验完成,H1 NULL(2026-11-07 15:20 UTC)
- **结果:** `MedHyperTrace-v2/results/icpt/README.md`;原始输出在服务器 `mht_work/icpt/`。
- **H1(icpt − lm,前缀 + agg,控制后):** +0.002 [−0.010, +0.014],网格 0/6 同号 → **NULL**。换读出头、分层都不改变结论。**按预注册停掉这一交互目标配方,不扩语料。**
- **次要比较:** 两个 CPT 臂只在见过框架上有约 +0.02,两臂相同。公开数据上 icpt 比 lm 略差;query 接口两个 CPT 臂都比 base 差。控制后三臂都在约 0.57。
- **issue #3 6708829225** 已通报。待补 A1 敏感性分析。
- **待用户决定:** 中训练路线下一步(主线规则"基础模型必须经中训练获得"与目前的证据相冲突)。
- **Linux #2:** kernel `0ee2176b-…`,helper `mht_r`;没有在跑的任务。

### 1.00 第 88 轮:语料构建完成,两个训练臂已启动(2026-11-05 02:30 UTC)
- **M-new 已交付**(medical-aegis `data_runs/corpus_v1_2026-11-04/mastraj/`,5ee6c44):4 个框架,不含 DyLAN,duckcoding 端点。
- **语料:** 沙箱 `/home/claude/icpt_corpus`(会话重置会丢,HF `icpt/corpus/` 有备份)。LM 40.00M / icpt 40.33M(比值 1.008);回放与 LM 公开 chunk 逐字相同;有效目标 token LM 约 40M、icpt 约 24M。
- **两臂启动(02:22:33Z):** lm 在 GPU 0,1,icpt 在 GPU 2,3;日志 `mht_work/icpt/{lm,icpt}/tapt.log`,状态 `mht_work/icpt/status`。完成后 driver 自动抽特征 → final(e4_probe 默认头已含 agg;medscore lm / icpt;compare)。
- **接口诊断:** 选中 (c) 前缀 + 聚合器(tt_val 0.887);WW 上 c 最差(0.526),报告时要写。loss_diag 修好 import,训练后重跑:`cd $C && GPU=<g> bash scripts/linux2_run_icpt_diag.sh`(跳过已完成步骤)。
- base 医学 med_eval 带 agg 头已完成(第 89 轮,数字见 RUN_v0.89)。
- **final 已因 lm 的 FAIL 自行退出(03:02)。** lm 臂重跑完后要手动单独跑 final:先处理 status 里 lm 的 FAIL 行。
- 03:02 UTC 用户要求终止 lm 臂(GPU 0,1;步 55,没有检查点)。
- **第 91 轮用户决定:lm 臂改在 GPU 2,3 上跑(等交互臂完成之后)。** 驱动 `scripts/linux2_run_icpt_lm2.sh`(每 100 步存检查点,可续接;做完接 final,FG=2)。启动:`cd $C && setsid nohup bash scripts/linux2_run_icpt_lm2.sh > $W/icpt/driver_lm2.log 2>&1 < /dev/null &`。代码在 HF `icpt/code.tgz`,md5 4c0de726…。
- **第 92 轮(14:45 UTC):** 交互臂已全部完成(训练 08:18、特征 10:45);lm2 驱动 14:38 启动,lm 臂在 GPU 2,3 上训练,约 20:40 UTC 结束,之后抽特征、跑 final;loss_diag 在 GPU 1 上重跑。
- **Jupyter 重启过,旧 kernel 已不在。** 现用 ms-swift kernel `0ee2176b-5b1d-4fd8-9674-9d9b18fee69f`,helper 为 `mht_r(cmd, t)`(subprocess,bash -lc)。后台任务用 `subprocess.Popen(..., start_new_session=True)` 启动。
- **第 93 轮(17:45 UTC):** lm 臂 390 / 791 步(约 20:25 UTC 训练结束)。loss_diag 已完成(数字和 recv 列的问题见 RUN_v0.93):tapt_clean 在 OAT 格式下目标变好(+0.19),在自己的格式下没有变好(−0.08,含 0);recv 列被格式边界尖峰主导,不可比,稳健版本等用户决定。
- **第 94 轮(20:51 UTC):连接器又要求重新登录,lm 臂的 merge / 抽特征 / final 状态未核实;等用户授权后再查(检查 6 的步骤见 RUN_v0.94)。**
- issue #3 6647953304 已回复。下一次定时检查见最新的 RUN。

### 0.80–0.99(第 68–86 轮)
- 第 101 轮起已移到 `HANDOFF_archive.md` 末尾「第 101 轮移入」一节,内容未删改。
