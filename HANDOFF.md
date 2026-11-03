# MedHyperTrace 会话交接文档

**最后更新:** 2026-11-03 05:45 UTC(第 80 轮;阶段 0 附录 A1 收尾中) · **原始版本:** 2026-10-08
**项目:** 医学多智能体系统故障归因 → 本仓库是其中的「故障归因方法」子项目(另一个子项目「人机协同自动化标注」提供人类标注,接口见 `docs/annotation_interface_v1.md`)
**用户:** Alvin Chan(清华,ML/NLP researcher;偏好直接的 peer-level 技术交流、要诚实批评而非附和、要求实证核对而非臆断)

> **新会话开场顺序:** ① 本文 §0(当前状态)→ ② 最新的 `RUN_v0.<N>.md`(讨论记录,文件名带版本号,N=轮次)的最后两轮 → ③ 按需读 `RUN_EXPERIMENTS.md`(完整实验命令)和 `docs/`。
> **仓库:** https://github.com/chancanmakeit/Medhypertrace (**私有仓库**,2026-10-09 起)。§一 以下是 2026-10-08 旧会话的内容,§0 中与之冲突的以 §0 为准。

> **⚠️ 第 34 轮(2026-10-21)起目录重组(用户要求):** 原方法 = **MedHyperTrace-v1**,全部代码 / 数据 / 结果移入 `MedHyperTrace-v1/`;新的超图基础模型 = **MedHyperTrace-v2**,代码在 `MedHyperTrace-v2/`。根目录只留 `README.md`、`HANDOFF.md`、`RUN_v0.<N>.md`。**本文 §0.3x 及以前出现的路径,v1 的一律加前缀 `MedHyperTrace-v1/`**(例如 `scripts/restore_env.sh` → `MedHyperTrace-v1/scripts/restore_env.sh`、`eval_mafa/` → `MedHyperTrace-v1/eval_mafa/`);**v2 的对照表:** `ours/hgfm/*` → `MedHyperTrace-v2/hgfm/*`(包名 `hgfm`,在 `MedHyperTrace-v2/` 下 `python -m hgfm.<模块>`);`data_tools/*`、`common/clean_inputs.py`、`common/old_data_filters.py` → `MedHyperTrace-v2/data_tools/`;`analysis/{read_hyperedge_stats,pilot_20261020}.py` → `MedHyperTrace-v2/analysis/`;`docs/{design,lit,interfaces}` → `MedHyperTrace-v2/docs/`;`scripts/issue_inbox.sh` → `MedHyperTrace-v2/scripts/issue_inbox.sh`。v1 用 `validate.py` 和 `ours/train_hgnn.py --help`、v2 用全部模块 import 和审计脚本做过冒烟测试。

> **📦 第 78 轮起:旧历史(§0.2–0.32、§0.34–0.79、§〇–十:MAFA 评测、旧 AEGIS 数据、v1 代码结构、方法论决定等)已移到 `HANDOFF_archive.md`,内容未删改;需要旧细节时去那里查。**

> **🚀 第 6 个会话快速恢复(第 76 轮末写,以此为准;下面第 38 轮的旧清单仍适用于 MAA / 公开数据恢复细节):**
> 1. `add_repo`(push)添加 `chancanmakeit/Medhypertrace`、`chancanmakeit/medical-aegis`,clone 到 `/home/claude/medhypertrace`、`/home/claude/medical-aegis`;推送走会话 git 代理,**不用 Project 指令里的明文 GitHub token**(已建议用户吊销)。commit 结尾加会话给的署名行。
> 2. 读 §0.91 → §0.90 → §0.89 → §0.88 → §0.87 → §0.86 → §0.80–0.85 → `RUN_v0.80.md` 第 63–80 轮。核心结果文件:`MedHyperTrace-v2/results/e1e3/README.md`、`results/e4/README.md`、`results/tracertraj_audit/README.md`、`results/figures/README.md`、`results/samt_v1/README.md`、`results/midtrain_pilot/README.md`;设计:`docs/design/{HGFM_design_v0.2,SAMT_design_v1,E1-E3_prereg_v1,E4_prereg_v1}.md`;论文:`docs/paper/method_overview_and_figure_prompt.md`。
> 3. issue:`bash MedHyperTrace-v2/scripts/issue_inbox.sh`(medical-aegis 全部 issue;我方最近:第 75 轮 issue #2 评论 `docs/interfaces/issue2_comment_r75.md`;第 78 轮新开 **issue #3**(中训练动机 + 是否请 medical-aegis 生成语料,正文 `docs/interfaces/issue3_r78.md`);第 80 轮新开 **issue #4**(ADP 对 mas-traj schema 的借鉴,正文 `docs/interfaces/issue4_r80.md`))。与其他智能体只通过 issue 交流,不 @ 任何人。
> 4. **Linux #2(4×A6000,无 NVLink)**:经 claude.ai 连接器 `Claude-connect-inqi_top` 的 `jupyter-mcp-2_linux2_*` 工具访问(**会话结束时该连接器掉线,需用户在连接器设置里重新授权**)。上次 kernel `ffd58261-5022-427d-86d3-035e82bd2358`(可能已不在,先 `list_kernels`;新 kernel 要重新定义 helper:`r()` 跑 shell、`rep()` 原地替换字符串)。路径:代码 `C=/data1/ekyang/cgh/CODE/Medhypertrace/MedHyperTrace-v2`(服务器上的仓库副本,改动后需同步)、工作区 `W=/data1/ekyang/cgh/CODE/mht_work`(`e1e3/`、`e4/`、`midtrain/`、`tracertraj/agentracer-data-v1.0.0`、`wheels/`)。环境:MS-Swift 4.6、flash-attn 2.7.4.post1、liger-kernel 0.7.0、peft 0.17.1;长单元格容易 520 / 超时,单元格要短、长任务用 nohup 后台 + 状态文件。沙箱访问不了服务器文件,数据传输靠 kernel 打印(zlib + base64 + md5 核对)。
> 5. 密钥:HF token 从 Project doc `UUUooUUU-huggingface-access-token` 读,写 600 文件,不上命令行;API 端点从 Project doc `claude/api端点` 读,写 `/home/claude/.mht_api.env`,绝不进 git;**任何付费 API 调用前先试跑估算成本,问用户**。
> 6. 规则:每轮 `git mv RUN_v0.<N>.md` 到新轮次并追加;更新本文 §0;commit + push;同步 Project doc `claude/HANDOFF_MedHyperTrace.md`;sleep ≤ 约 60 秒;MAST 与 MedAgentAudit 数据 / 结果分开;责任层评测必须报告长度 / 位置基线和长度控制结果;外部数据按"题干归一化 + Jaccard ≥ 0.3,按题目分组"去重;主线 = 文本属性超图上的超图基础模型,**基础模型必须经中训练 / 续训预训练获得**;用户要直接、同行式的批评和实证核对,用中文交流。
> 7. **第 79 轮起阶段 0 运行中(见 §0.91),用户已批准:** ① 标签效率曲线(TracerTraj 100 / 300 / 1000 / 全量);② 负对照中训练(shuf / irr,与 R 同 token 量);③ 剂量 24.5M → 34.4M(full);④ 按题目分组的 manifest + 基准审计表。预注册 v2(替换步检测)等阶段 0 结果后再议。阶段 1(medical-aegis 付费生成)等 issue #3 报价 + 阶段 0 结果。用户已开始写论文(Method 图提示词已给)。

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

### 0.92 第 80 轮:ADP 论文 → issue #4(2026-11-03 05:45 UTC)
- 用户让读 Agent Data Protocol(ICLR 2026)并提到 issue #4。已发(`docs/interfaces/issue4_r80.md`):mas-traj/1 已覆盖并超出 ADP 的轨迹层,不改主格式;提案是规范渲染器(**中训练语料格式 ≠ OAT / E4 读出格式**,建议做零 API 的格式一致性检验)、typed 标签子 schema、`task_group_id` / `split` 必填、数据卡。分工待用户确认、待各方回复。
- 论文 PDF 在 private-documents(本会话稀疏克隆于 `/home/claude/private-documents`)。

### 0.91 第 79 轮:阶段 0 运行中(2026-11-02 16:45 UTC)
- 预注册 `MedHyperTrace-v2/docs/design/Stage0_prereg_v1.md`(30a4862;修订 9df9dc0)。所有判定按它执行;读结果前先读它。
- **Linux #2 `mht_work/stage0/`:** `status` 是进度;驱动 `scripts/linux2_run_stage0.sh`(setsid,可重跑续接;各步有输出就跳过;重跑前要把 status 里的 FAIL 行处理掉,车道 D 见到 "FAIL feats <n>" / "FAIL train" 会停)。产物:
  - `nc_shuf/`、`nc_irr/`、`full/`(各含 `Qwen3-8B-<name>` 合并模型);
  - E1 在 `mht_work/e1e3/oat_{shuf,irr,full}/`,日志 `stage0/e1_*.log`;
  - 特征 `stage0/feats_{shuf,irr,full}.pt`;
  - 标签效率 `stage0/le/le_{linear,mlp}_<proxy>.json` + `meta.json`;
  - A 阶段全量 `stage0/stageA/`;
  - BEFT `stage0/beft_{base,tapt}_n{100,300}/`。
  - 子集 `stage0/subsets.json`。
- **全部完成(主驱动 ALL DONE 约 03:00 UTC;A1 ALL DONE 约 06:15 UTC,11-03)后要做:**
  1. 写 `scripts/stage0_analyze.py`(复用 `hgfm/e4/e4_eval.py` 的 per_traj / residualise,`analysis/e4_overlap_matched.py` 的 matched;OAT 分数按该文件的读法);
  2. 按预注册算 Q1 / Q2 / Q3(原始、控制后、匹配配对,以及敏感性子集 `results/stage0_manifest/eval_clean_keys.json`);
  3. 写 `results/stage0/README.md`;发 issue #3;更新本文。
- **manifest:** 由后台子 agent 产出 `results/stage0_manifest/`(若会话中断:检查该目录是否齐全,不齐就按预注册 Q4 重做,脚本 `data_tools/build_manifest.py`)。
- **manifest 已完成(17:30 UTC,`results/stage0_manifest/`):** 356 条评测轨迹中 270 条与 tapt 语料重题(R 205、S 118、full 0、TT_train 90);干净子集 `eval_clean_keys.json` 的 `clean_direct` 85 条(用直接重叠,不用连通分量——0.3 时一个分量 14k 项)。分析时把 tapt 重叠 / 不重叠分开报告。TracerTraj 测试集 621 / 768 与训练重题。
- **附录 A1(用户批准,17:48 UTC 启动):** tapt_clean(TAPT 规则去掉 379 条评测重题运行,24.38M)。驱动 `scripts/linux2_run_stage0_a1.sh`(status 行带 "A1" 前缀;末行 "A1 ALL DONE",约 06:15 UTC)。产物 `stage0/tapt_clean/`、`e1e3/oat_tapt_clean/`、`stage0/feats_tapt_clean.pt`、`stage0/stageA_clean/`、`stage0/le/le_*_tapt_clean.json`;BEFT n100 也由它最后跑(主驱动车道 A 靠占位文件跳过;占位文件含 "placeholder" 字样,分析时若还在就说明 A1 没跑完)。判定见预注册附录 A1(Q1′ / Q3′ 与 Q1 / Q3 不一致时以 Q1′ / Q3′ 为准)。
- **03:20 UTC(检查 3):** 主驱动 ALL DONE。e4_probe 回归 bug(非标签效率模式 dev 未定义)已修(md5 c780bb7f),shuf / irr / full 的全量 A 阶段 03:23 在 GPU 0 重跑(status 会出现 "DONE stageA new (rerun after e4_probe fix)")。中间结果(RUN_v0.79 续 5):Q1 无效(tapt − base 面积 +0.014 [−0.006, +0.034]),Q2 未定(R − irr +0.031 [−0.002, +0.065]),Q3 无效。**Q1′ / Q3′ 待 A1**(tapt_clean 的标签效率),以它们为准。分析命令:`cd $C && python scripts/stage0_analyze.py --w $W --clean $W/stage0/hf/stage0/an/eval_clean_keys.json --out $W/stage0/analysis_final.json`。全部完成后写 `results/stage0/README.md`、发 issue #3。
- **更正:** 可用干净语料是 34.42M(不是 75M);TAPT / S / R 语料可能含 WW / TEgc 题目近似重复(full 已去除)。issue #3 评论 6582634345。

### 0.90 第 78 轮:中训练动机再审视;新开 medical-aegis issue #3
- 用户写下中训练动机:① 弥合 MAS 轨迹与通用文本的域差异;② 成功轨迹有规律,中训练灌入"成功轨迹先验";并问是否请 medical-aegis 跑不同框架凑 0.1B–1B 语料。
- **新核查**(零 API,`MedHyperTrace-v2/analysis/success_regularity_check.py` / `.out`,锚点 normal 1,200 条):同题内,成功对成功比成功对失败更近 +0.032 [+0.024, +0.042];选同一错项的两条失败运行同样更近 +0.043 [+0.027, +0.062];选不同错项的 −0.009(n.s.)→ "成功的规律"≈"结论一致"。注意:锚点导出的 `answer` 字段是金标准,系统答案用 `verification.regex_extracted`。
- **我方立场(issue #3):** 动机 1 对,但应以标签效率检验,医学域差异未测;动机 2 的边际版本有弱阴性证据(E2),建议改为条件版本(同题成败对比 / 分叉);语料量不是当前瓶颈(75M 干净语料只用了 24.5M,无剂量效应)。分阶段:阶段 0 我方零 API(标签效率、负对照、24.5M→75M 剂量检验、manifest)→ 阶段 1 medical-aegis 约 $5–15、10–20M token 医学自然运行(难度筛题、K ≥ 4、≥ 6 族、带 sources)→ 阶段 2 有正斜率才扩到 0.1B+(按第 66 轮单价估 0.1B ≈ $50–75)。
- 等:用户决定阶段 0 是否开始;issue #3 各方回复(medical-aegis 单价 / 题库 / 有对有错比例 / sources)。

### 0.89 第 77 轮:第 6 个会话已恢复(2026-11-02 15:45 UTC)
- 两仓库已 clone(Medhypertrace 2e34e8d、medical-aegis ebb77a3);issue 无新评论(#2 最后为我方 04:15:22Z)。Linux #2 连接正常,kernel `ffd58261-…` 仍在(helper 已重定义),GPU 1–3 空闲,`mht_work/` 完好;**/data1 用了 92%(剩 1.3 TB)**。密钥文件在 `/home/claude/.mht_secrets/`、`/home/claude/.mht_api.env`(600)。讨论记录当时为 `RUN_v0.77.md`。
- 没有在跑的任务;等用户在 §0.87 的四个零 API 下一步中决定。

### 0.88 第 76 轮:训练过程图 + Method 概览图提示词(写论文用)
- 图与讲解:`MedHyperTrace-v2/results/figures/`(README、4 张图 PNG + PDF、数据、脚本 `scripts/plot_training_curves.py`)。
- 方法框架与 GPT 绘图提示词:`MedHyperTrace-v2/docs/paper/method_overview_and_figure_prompt.md`。图按模块化画,不写性能主张;C9 未实现;C5 无增益,只放消融。
- 待用户决定的下一步(零 API)同 §0.87。

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
