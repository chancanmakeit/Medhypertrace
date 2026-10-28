# E1–E3 预注册 v1(第 67 轮,2026-10-28,写于任何 E1 / E2 结果产生之前)

**目的:** 检验中训练能否为**责任层**归因(哪一步导致失败)提供可迁移信号。用的是 OAT 式无监督读出,在严格留出的外部轨迹上评测。
MAA 缺陷层的既有结果照常报告,不因本实验替换。本文件提交后不再修改判定规则;实施细节如有变化,另起"偏离记录"一节,写明原因。

## E3 留出评测集(先固定)
- **WW**:Who&When 184 条失败轨迹(Hand-Crafted 58 + Algorithm-Generated 126,用 OAT 仓库自带的副本),标签是最早决定性错误步(`mistake_step`)。
- **TEgc**:TraceElephant 的 groupchat 部分 176 条(Magentic-One / CaptainAgent),从我方 mas-traj/1 转换成 Who&When 格式,标签是 `mistake_step_id`。TraceElephant 的 44 条 swe_agent 进过 TAPT / SAMT 语料,**不纳入**。
- 两者都是 groupchat family,TAPT / SAMT 中训练语料都排除了 groupchat,所以是架构层面的零样本。从本轮起,所有中训练语料入训前都要对这 360 条做排除检查(按 run_id 和规范化题干)。
- **医学分叉点**(medical-aegis 分叉试点,去掉 aggregator 后 79 点、12 个翻转):**只做描述性报告**,检验力不足,不参与判定。

## 指标(候选步骤 = 模型步,即 OAT 的 `model_steps_only`)
- **主指标:** Acc@1(得分最高的步骤 = 标注错误步)、Hit@3、**轨迹内 rank-AUROC**(错误步在本轨迹模型步中的排名,1 − (rank−1)/(n−1))。三个都是轨迹内指标,不受不同运行之间分数尺度的影响。
- 次要(为与 OAT 论文可比):OAT 的池化 step AUROC / AUPRC、top-3 F1。
- 区间:按轨迹做配对 bootstrap(1000 次);WW 与 TEgc 分开报告,并报告两者合并(n = 360)。

## 平凡基线(必报)
随机步(期望值)、第一个模型步、最后一个模型步、按位置的先验(用另一个数据集的错误步相对位置分布打分)。Who&When 类数据没有同伴支持度的定义,不报。

## E1:中训练检查点作为 OAT 的代理 LLM
- 完全沿用 OAT 的代码与超参(PCA 64、Neural CDE、门控控制路径、5 个种子、CORAL 对齐),在 MCP-Atlas 成功轨迹上训练。
- 代理 LLM 有两个:**base** = Qwen3-8B;**tapt** = `Qwen3-8B-tapt_pilot_v1`(第 62 轮的合并检查点)。唯一的变量是代理 LLM。
- 步骤表示 = 末层隐状态在步骤 token 上取均值(OAT 默认)。超过 32,768 token 的轨迹(WW 有 11 条)对两个代理都用 YaRN ×4;另报去掉这 11 条的敏感性结果。
- **判定(E1 成立):** 在合并的 360 条上,tapt − base 的 rank-AUROC 差 95% CI 下界 > 0,且 Acc@1 差的点估计 ≥ 0。只在 WW 或只在 TEgc 上成立,记为"部分"。
- 参照(不作判定):OAT 论文用 Qwen3.5-27B 代理时,MCP-Atlas → Who&When 的池化 AUROC 0.758、Hit@3 0.451。

## E2:似然比读出(无 CDE)
- 从 Qwen3-8B 出发,用同一 TAPT 配方训练两个 LoRA:**S** = 只用成功运行;**R** = 全部结局的运行。两者 token 数相同,并在**每个数据集内**匹配 token 占比(差别只在结局构成)。语料规则同 TAPT:公开数据 + 锚点 normal,无 MAA,排除 groupchat,过 MAA 排除清单。成功标签来源:ARIA `source_success`、AFTraj `safe`、MAST-Data `any_failure = False`、锚点"最终答案 = 金标准"。AgentRx、MAScope、TraceElephant 没有成功标签,两个语料都不用。
- **步骤分数** = NLL_S(步骤 token | 前缀) − NLL_R(步骤 token | 前缀),取该步 token 的均值;越高越"不像成功"。文本用 OAT 的序列化。
- 对照分数:原始 NLL_base(意外度)、NLL_tapt − NLL_base(域适应差)。
- **判定(E2 成立):** 合并 360 条上,ΔNLL 的 rank-AUROC 比最好的平凡基线和原始 NLL_base 都高,两个配对差的 95% CI 下界都 > 0。
- E2 与 E1 的 OAT(base)也做配对比较(描述性)。

## 无论结果如何都会报告
所有设定的所有指标,包括阴性结果;GPU 时长;没有用到的数据。若 E1 或 E2 成立,下一步才考虑把 OAT / 似然比阶段并入课程(TAPT → SAMT v2 → 成功流)。

## 补充 E1b(第 68 轮,2026-10-28 ~09:00 UTC;写于 E1 / E2 结果之后、E1b 结果之前)
E1 成立后的追加问题:增益是否随中训练语料变化。**这是追加实验,上面 E1 / E2 的判定不变。**
- 代理 LLM 换成 E2 的两个检查点:**S**(只用成功运行,6.06M token)和 **R**(全部结局,6.09M token)。两者都与 TAPT 同配方,但语料约为 TAPT(24.5M)的四分之一,数据集构成也不同。其余与 E1 完全相同(同一份打过补丁的 OAT,SDPA 注意力,5 个种子)。
- **主比较:** S − base、R − base、S − R;合并 356 条上的 rank-AUROC 与 Acc@1,配对 bootstrap 1000 次。
- **预期(写在结果之前):** S − base 与 R − base 的 rank-AUROC 都为正,且都小于 tapt − base 的 +0.027;S − R 的 CI 包含 0。
- **判定:** "中训练增益可复现" = S − base 和 R − base 中至少一个的 rank-AUROC CI 下界 > 0。两者都不满足,则记为"E1 的增益在四分之一语料量下复现不出",并在 E1 的结论里注明。S / R 与 TAPT 的语料不只是量不同,所以这里**不做**剂量—效应的结论。
