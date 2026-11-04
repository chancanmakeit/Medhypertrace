# 交互式续训预注册 v1(项目内称"预注册 v2";第 86 轮,2026-11-04,写于任何本实验结果之前)

**背景:**
- 阶段 0 停掉了纯语言建模续训配方(`results/stage0/README.md`;按题目聚类重算后结论不变)。
- GPT 在 medical-aegis #3 给出最小方案(6599948902):同一份清洁语料、同一主干,比较三臂——base / LM-CPT / interaction-CPT。
- 用户第 86 轮批准:按此方案写预注册并执行。
- 评测新增 medical-aegis 协议 v3 医学分叉集(`data_runs/eval_v3_2026-11-04/`;审计见 `analysis/branch_v3_audit/`)。

**时间顺序:** 本文提交时,没有任何 CPT 臂被训练,也没有提取任何新特征。随后才做:接口诊断(只用 base)、语料构建、训练、评测。

**常设规则(沿用):**
- 责任层评测报告原始值、控制后的值、匹配配对的值:
  - 控制后 = 对 log 步长、相对位置(公开数据另加是否含代码)做带轨迹固定效应的 OLS,不用标签,取残差;
- 区间按题目聚类 bootstrap(1,000 次);
- 无效界:控制后差值 95% CI 上界 < +0.04;
- MAST 与 MedAgentAudit 不合并(本实验不用 MAA)。

## 1. 假设与比较
| 编号 | 比较 | 评测 | 地位 |
|---|---|---|---|
| **H1** | interaction-CPT − LM-CPT | 医学分叉集,留一框架读出,控制后 AUROC | **主假设** |
| H2 | interaction-CPT − base | 同上 | 次要 |
| H3 | LM-CPT − base | 同上(阶段 0 在医学数据上的复现) | 次要 |
| H4 | 三个比较 | 公开 WW + TEgc,阶段 0 的标签效率面积(线性头,控制后) | 次要 |

主张的检验对象:在**同一批运行、同等处理 token** 下,显式学习"接收者看到什么 → 回什么""回答依据了哪些消息",是否比在同样文本上做普通 next-token 续训,带来更好的可迁移归因表示。

## 2. 语料(两个 CPT 臂共用同一批运行)
### 2.1 运行来源
| 来源 | 读集 | 用法 |
|---|---|---|
| **M-new:** medical-aegis 在语料题池(`pools_v1/corpus.json`,1,449 题;与 eval 800 题按题组分开)上的新自然运行;gemini-2.5-flash-lite;框架 = llm_debate、mdagents、medagents_mc、MAC 群聊、DyLAN;K = 1 | 运行时(`collection: runtime`)| 交互目标 + LM 文本 |
| **M-anchor:** 锚点 normal 运行,1,200 条;gemma-4-31B;4 个框架 | 运行时 | 交互目标 + LM 文本 |
| **P:** 公开 mas-traj(阶段 0 full 规则:排除 MAA、groupchat 族,并按 Jaccard ≥ 0.3 去掉与 WW / TEgc 近似重复的运行) | 协议推断(没有运行时读集) | **只作 LM 文本**(两臂相同) |

- **留出:** AgentVerse、triage_agent、MAM **不进任何语料**,是"未见框架"评测层。DyLAN 的读集不完整(`provenance.sources_complete = false`),**只作 LM 文本**,不生成交互目标。
- **题目隔离:** 语料题池与 eval 题池按 `task_group_id` 分开(medical-aegis 构造)。语料构建时再对 eval 800 题 + 多模态 eval 子集 + triage / MAM 评测题做题干 Jaccard ≥ 0.3 检查,命中就删,并记入 manifest。
- **M-new 需付费生成**:按 medical-aegis 试跑单价粗估约 ¥10 以内。先请对方报价,用户批准后生成。生成前训练臂不启动;接口诊断和 loss 诊断不受影响。

### 2.2 两臂的样本
- **LM-CPT:** 全部运行(M-new + M-anchor + P)按 `build_corpus.py` 的规则渲染成文本,`swift pt` 训练,做 next-token loss,与阶段 0 配方相同。
- **interaction-CPT:** 用 `swift sft`,loss 只算回答部分:
  1. **接收者条件响应**(M-new / M-anchor 中读集完整的每个 LLM 步 t):
     - system = 接收者身份(框架、角色、phase、round);
     - user = 任务 + `sources(t)` 中各步按原顺序渲染的消息(环境 / 工具输出按 `build_corpus` 的截断规则);
     - assistant = 步 t 的真实输出。
     - `sources(t)` 为空时,user 只有任务。未来轨迹不进入输入。
  2. **证据对应**(同上范围内,`sources(t)` 非空,且至少有一个同运行的更早步不在读集里,或可找到同题其他运行的匹配干扰项):
     - user = 步 t 的输出 + 打乱顺序的候选消息(真读集成员 + 不在读集里的同运行更早步;不够时补同题、同框架、同角色、同轮的其他运行步作检索负例,最多 6 个候选);
     - assistant = 被读取的候选编号。
     - 读集成员只代表"可见",不标成"有影响";干扰项不是故障负例。
  3. **LM 回放:** P 部分与 LM-CPT **完全相同的文本 chunk**,用 sft 格式,全部 token 计 loss。
- **配额(按处理 token 计):**
  - 两臂总处理 token 相等,允许 ±5%;
  - P 部分两臂逐 chunk 相同;
  - 医学部分:LM-CPT = M-new + M-anchor 的渲染文本;interaction-CPT = 交互样本,按步随机抽样到与 LM-CPT 医学部分同等的处理 token(条件响应 : 证据对应约 3 : 1 按 token);
  - 每臂报告:处理 token、有效目标 token(计 loss 的 token)、优化步数、GPU 小时。
- **总预算:** 每臂约 40M 处理 token,以 M-new 实际生成量为准,P 部分补足。超过就按数据集等比例截 P。

### 2.3 训练
- Qwen3-8B,LoRA r64 / α128 all-linear,lr 1e-4 cosine,warmup 3%,1 epoch,有效 batch 32 条,≤ 4,096 token,flash-attn,seed 0,结束后合并。
- 两臂都从 Qwen3-8B 原模型开始(不从 tapt 系列续)。各一个训练种子(算力限制,写明)。

## 3. 读出接口(先定接口,再提取各臂特征)
候选接口:
- (a) **前缀**:阶段 0 / E4 的方式,步内 token 末层均值,因果注意,只看前缀;
- (b) **全轨迹后置查询**:整条轨迹之后追加每个候选步的查询串 `\n[QUERY s<k>]`,取查询末 token 的末层隐状态,能看到完整轨迹;
- (c) **双向聚合器**:(a) 的步向量上加 2 层 Transformer 读出头(d = 256),与线性头同预算训练。

**选择规则:** 只用 base,在公开 TracerTraj 验证集(319 条)上,用 TracerTraj 训练的线性头比较控制后 rank-AUROC,取最高者为主接口,其余作次要报告。选定发生在任何 CPT 臂特征提取之前。医学评测集不参与选择。

## 4. 评测
### 4.1 医学分叉集(主)
- **单元:** 每条父运行(mas-traj 导出 `parents_mastraj/`)在主接口下得到每个 LLM 步的表示。
  - 阳性 = `judgment == positive`,不含"只反映末次调用"(`dt_empty` 且非 `downstream_regenerated`)的点——这类点从该父运行中整体剔除;
  - 其余点都作"其他点"。
  - 只评有 ≥ 1 个阳性、≥ 1 个其他点的父运行。
- **读出:** 留一框架交叉拟合。对每个框架 f,在其余框架的父运行上训练读出头,在 f 上打分:
  - 读出头:线性为主,MLP 为次;
  - 损失:每条父运行内的 listwise softmax,多阳性取对数似然之和;
  - 训练中"其他点"按 0 处理,这只是训练用,评测不把它们当负例;
  - AdamW,lr 1e-3,wd 1e-2,≤ 30 epoch,早停用训练框架内按题目 10% 留出;种子 0 / 1 / 2。
  - 框架集合:mdagents、llm_debate、MedAgents、MAC(见过的框架),AgentVerse、triage、MAM heartbeat_a / heartbeat_b(未见框架);多模态 mdagents 合入 mdagents。
- **指标:** 每条父运行的 AUROC(阳性 vs 其他点),先在种子上平均。
  - 控制后:对 log 步长、相对位置做带父运行固定效应的 OLS,按框架拟合,不用标签,取残差后算 AUROC;
  - 匹配配对:同父运行内步长比 ≤ 1.5、相对位置差 ≤ 0.25,另报 6 档网格,同阶段 0。
- **主统计量:** H1 差值(控制后,线性头),合并所有框架的父运行,按 `question_id` 聚类 bootstrap。另按"见过 / 未见框架"两层和每个框架报告(次要)。
- **平凡基线**(必须同表报告):最长步、最早步、随机。

### 4.2 公开数据(次要)
沿用阶段 0:冻结特征(主接口),TracerTraj n ∈ {100, 300, 1000} 标签效率,5 次抽取;WW + TEgc 合并,控制后面积;按题目聚类(jac0.7)。

### 4.3 判定
- **HOLDS:** 控制后 CI 下界 > 0,且匹配网格 6 档中 ≥ 4 档同号(同时报网格中位值与极差);
- **NULL:** 控制后 CI 上界 < +0.04;
- 否则 **UNDETERMINED**。
- H1 NULL → 停掉这一交互目标配方,不为它扩语料。H1 HOLDS → 再议扩语料(阶段 1)。
- 其余比较只报告,不改变决定。

## 5. 功效(粗估,写明假设)
- 主评测可用父运行(有非末次阳性):见过框架约 115 条(mdagents 62、llm_debate 35、MedAgents 10、MAC 8),未见框架约 154 条(AgentVerse 86、triage 31、MAM 37),合计约 269 条。
- 由阶段 0 公开数据的配对差 CI 反推每条轨迹的差值标准差约 0.20–0.29。由此 H1 的 80% 功效最小可检出效应约 0.035–0.05;要判 NULL,点估计需约 ≤ 0.00–0.005。
- 题内相关会再降低有效样本(triage 每题 4 次,MAM 每题 2 次)。
- **追加量:** 若要把最小可检出效应压到 0.035 以下,需约 +150 条含阳性的父运行。优先 mdagents(步长最干净;eval 池 K = 2,约 1,000 条新父运行,产出约 150 条含阳性)。是否追加由用户决定,不阻塞本实验。

## 6. 免费诊断(与语料生成并行)
1. **零训练 loss 诊断**(issue #4,GPT 的估计对象):
   - base vs tapt_clean;
   - 同一目标响应在三种渲染下的条件 NLL:(a) TAPT 语料格式,(b) OAT / E4 读出格式,(c) 接收者条件格式(本文 §2.2.1);
   - 报 Δ_f 和 D = Δ_a − Δ_b,按题目聚类;模板 token 单列;
   - 留出样本:锚点 normal 运行中按题目分组的 20%,只作诊断用。
2. **接口诊断**(§3):只用 base。

## 7. 已知偏离与风险
- 每臂一个训练种子,训练随机性与臂间差异混在一起。用两个读出头 × 三个读出种子部分缓解,不能消除。
- interaction-CPT 和 LM-CPT 的医学部分处理 token 相等,但覆盖的运行比例不同(交互样本按步抽样)。
- 医学分叉集的阳性有约 11–17% 与噪声相容(置换 FDR);读出训练把"其他点"当 0,会被未判定的真阳性稀释。两臂受同样影响。
- M-new 与评测父运行用同一 backbone(gemini),M-anchor 是 gemma。"见过框架"层是"同框架、新题",不是框架级零样本。

## 8. 产物
- 代码:`hgfm/icpt/`(语料构建、渲染、医学评测);驱动 `scripts/linux2_run_icpt.sh`。
- 结果:`results/icpt/README.md`。

## 修订记录
- **A1(第 86 轮,2026-11-04,在任何特征提取与评测之前):** §4.1 的阳性改为对两臂对称的合并参照规则——stage 2 且 `statistics.p_value_pooled` < 0.05。
  - 原因:第一批标签的 `judgment` 用 control 众数参照(有偏,置换 FDR 约 0.14),扩充批用合并参照,两批口径不一。
  - 合并参照下共 303 个阳性(原 `judgment` 为 379 个)。`judgment` 口径作敏感性分析报告。
