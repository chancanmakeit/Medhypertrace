# RUN_v0.7 — 每轮讨论记录

**命名规则(2026-10-09 起,按 Project 要求带版本号):** 文件名 `RUN_v0.<轮次>.md`,每轮结束时用 `git mv` 改名到新的版本号,历史在 git 里连续。**当前最新版本号 = 最后一轮的轮次。**

本文件每轮对话结束时追加一节,记录:用户要求、做了什么、结论/数字、产物、未决问题。
**数字只记实测过的**;冒烟测试的数字标明「冒烟,无意义」。
交接用的当前状态汇总见 `HANDOFF.md §0`;旧会话(2026-10-08 及以前)的记录不在本文件,见 `HANDOFF.md §一–十`。

---

## 第 1 轮 · 2026-10-09 02:08 · 仓库写权限测试

**要求:** 推一个空文件到 GitHub 仓库,验证写权限。
**做了:** 用用户给的 token 推送被会话 git 代理拦截(仓库不在会话授权列表)→ 把仓库以写权限加入会话 → 推送 `.write_test`(commit `92fdc32`)成功。
**结论:** 写权限正常。推送由会话代理认证,**不需要 token**;用户的临时 token 可撤销。

## 第 2 轮 · 2026-10-09 02:24 · 恢复旧会话环境

**要求:** 读标注接口说明(来自「人机协同标注」子项目)、旧会话交接文档和两个资源包,看能否恢复旧会话环境。
**做了:**
- 两份交接 md 完全一致(md5 相同);`medhypertrace.zip` 与 FULL 包里的 `medhypertrace/` 逐文件一致。
- 解压 AEGIS 数据集到 `/home/claude/aegis_813/AEGIS-custom-dataset`;装依赖。
- **torch 现在能装**(磁盘 30G 空闲),CPU torch 2.14.1。
- 冒烟测试:`validate.py`(专家名细化、超图构造正常);`train_hgnn.py clinical_agent --epochs 2`(约 10 秒);`hgnn_unified_eval.py clinical_agent --epochs 2 --report_gran role --json_out` 写出 JSON 正常。冒烟数字(Agent-mi 57.8,召回 ~97%、精确率 ~41%,过预测)**无意义,只证明链路通**。
- 核对接口文档 §6.1 的 `answer==ground_truth` 问题:本项目 5 个合成文件 5231/5231 条 `answer == ground_truth.correct_answer`,全部 `is_correct=False`。本项目代码只把它当正确答案用 → **不受影响**。
- 代码、文档、参考资料(`refs/`)、接口文档(`docs/annotation_interface_v1.md`)入库;新增 `scripts/restore_env.sh`、`.gitignore`;`HANDOFF.md` 加 §0「当前状态」。

**未决(需用户决定):**
1. 仓库是**公开**的。数据集 `.7z` 和派生文件(嵌入缓存 7.7M、`eval_samples` 13M)暂未推。是否推,或把仓库改为私有后再推?
2. 当前 Project 里没有 `api端点` doc,需要调 API 时要用户提供。
3. `.write_test` 是否删除。

## 第 3 轮 · 2026-10-09 02:57 · 私有仓库权限、API 端点、删测试文件

**问答:** 改成私有仓库后能否继续读写?会话的写权限来自 GitHub 连接对这个仓库的授权,与仓库是否公开无关,原则上不变。改完后需实测一次(`git ls-remote` + 推送)。
**做了:**
- 用户提供 6 个 API 端点 → 存到仓库外 `/home/claude/.mht_api.env`(600 权限),`.gitignore` 加 `*.env`。密钥不入库。未发起任何 API 调用。
- 删除 `.write_test`。
- `HANDOFF.md §0.1` 的 API 一行更新为端点清单(不含密钥)。

**未决:** 用户改私有后实测读写;若确认私有,再决定是否推数据集和派生文件。

## 第 4 轮 · 2026-10-09 03:07 · 仓库改私有,端点存 Project doc,数据入库

**做了:**
- 确认仓库私有(`gh api` 读到 `private: true`),会话读写正常。
- **更正第 2 轮的判断**:当时用「未认证请求返回 200」推断仓库公开,但沙箱的请求会被会话代理自动加认证,200 不能说明公开。改私有前的真实状态未验证;现在已确认私有。
- API 端点(含密钥)存为 Project doc `claude/api端点`;密钥仍不进 git。
- 数据集 `.7z`、嵌入缓存、`eval_samples` 入库;`.gitignore` 只排除解压目录和 `*.env`。
- `scripts/restore_env.sh` 改为无参数即用仓库内 `.7z`;修了 `validate.py | head` 在 `pipefail` 下 BrokenPipe 导致脚本中断的 bug。实测脚本从头跑通。
- `HANDOFF.md §0.1` 同步更新(私有、数据在库、端点在 Project doc)。

**结论:** 新会话续接只需 clone 仓库 + `bash scripts/restore_env.sh` + 读 Project doc `api端点`,不需要用户再上传任何文件。

## 第 5 轮 · 2026-10-09 03:21 · MedHyperTrace 在 MAFA human-like-v1 上的可行性验证

**要求:** 把私有仓库 `chancanmakeit/MAFA-human-ai-annotation` 只读加入会话,锁定 `908bc74`,按其 `docs/MedHyperTrace评估执行文档.md` 评估;只推理不训练不调参;先做 §2 sha1 自检和 §3 泄漏检查。
**做了:**
- 仓库只读加入,克隆并 `checkout --detach 908bc74`。跑 `scripts/fetch_data.sh` 取 AEGIS 原始记录(需要原始格式建图)。
- **偏离说明:** MedHyperTrace 没有保存的权重,无法纯推理。改为每个框架用 `train_hgnn.py` **默认超参**在合成注入训练集上训一个模型,MAFA 标签不参与训练/选择/阈值。决策规则跑分前写死(主口径 step-owner,副口径 agent-head)。
- §2 对齐 **17/17**;§3 泄漏 文件+行号 0/17、整轨迹 0/17,1 条与 dylan/llm_debate **测试集**共享 2 步文本和题目;同框架训练集同题 0/17。
- 结果(种子 0,主口径):who_earliest **9/20** [0.26,0.66]、who_any 12/20、when_exact **8/20** [0.22,0.61]、when_pm1 14/20、agent AUROC **0.414**、MAST code F1 0.349(全判存在 0.478)。**四项都没超过「永远猜第一步」(14/14/11/15)**。种子 1、2 结论相同。
- 错误分析:不偏后而偏早;智能体头反向(AUROC<0.5);dylan 合成注入 100% 在 s01–s03 而真实故障在 s05/s06/s09;clinical_agent 真实主导故障 ClinicalAgent@s02 在合成集只占 9%;mdagents 被拉向专家步骤;步骤分数极度过度自信。
- **超出本轮的发现:** 合成测试集上 step head top-1 对「猜第一步」:mdagents 0.693 对 0.680(几乎无增益)、clinical_agent 0.686 对 0.600、dylan 0.694 对 0.513。主表 Step-Acc 需要加这个对照。
- 产物在 `eval_mafa/out/`(`medhypertrace_pred.jsonl`、`medhypertrace_report.json`、`error_analysis_notes.md`);评估代码提交 `9ad8ca0`;复现 `bash eval_mafa/run_eval.sh`。

**未决:** 回传 MAFA 由用户转交(MAFA 仓库在本会话只读);是否把「猜第一步」对照补进主表。

## 第 6 轮 · 2026-10-09 05:21 · 回应 MAFA 的「缺陷层/责任层」提案

**MAFA 提案:** 人类版标签分两层——缺陷层(哪些智能体输出有缺陷)+ 责任层(只在答错轨迹上标:哪些缺陷沿传播链进入了最终答案);最早故障步改由码推出,另给最早责任步。问我们三件事:(a) 步骤标签怎么来的;(b) 合成集里「被注入但没传到最终答案」的比例;(c) 主目标用哪一层。
**做了(`analysis/injection_propagation.py`,结果 `analysis/injection_propagation.json`):**
- (a) 步骤标签 = conversation_history 中 `injection_applied=True` 的最小 `step`;智能体标签 = `multi_injection_info` ∪ 已应用步骤。计划注入却从未应用:llm_debate 294/1712(17%)、dylan 20/1062,其余 0。不核对传播。
- (b) 答案级代理(被注入智能体最后表态 vs 最终错误答案),排除最终答案产出者(mdagents/llm_debate 的 Aggregator、clinical_agent 的 Reasoner),只保留最终答案与 `regex_extracted` 一致且≠金标准的轨迹。有作答的被注入智能体中,最后表态 ≠ 最终错误答案:mdagents 59%(其中仍答对 19%)、dylan 34%(23%)、llm_debate 70%(33%)、clinical_agent 37%(37%,但只有 166/571 个被注入智能体给出概率)。对照(未注入)与最终答案一致率:46%/17%/16%/40%。mdagents 被注入者一致率(41%)甚至低于未注入者(46%)。clinical_agent5 智能体基本不出概率,代理量无信息。mdagents 抽取器与 regex_extracted 945/950 一致、抽查正确;dylan/llm_debate 抽取较粗(一致率 77%/88%,覆盖低),只作粗估。
- **新发现(影响本方法):** 注入伪迹——被注入步骤答案为 A 的比例 51%/55%/30%(mdagents/dylan/llm_debate),未注入步骤 18%/11%/12%;响应篡改常追加模板句「Therefore the final answer is A.」。这是表层捷径,可能是向真实故障迁移失败的原因之一。
- 核对 MAFA 第 3 点:合成 mdagents 中**未被注入**的招募者 66% 也给出答案(越权),其中 51% 是正确答案——即「有缺陷、无责任」在合成标签里被标为无故障。
- (c) 建议:智能体层主指标用责任层 agent_auroc,缺陷层辅助;步骤层主报最早责任步(对应 Who&When 的 decisive error),最早缺陷步辅助。另提出责任层的操作细则建议(见给 MAFA 的回复)。

**含义:** 合成训练标签在语义上是「被注入集合」,既不是缺陷层也不是责任层;责任层监督只能来自真实标注(与交接文档 §5.3 一致)。

## 第 7 轮 · 2026-10-09 05:46 · MAFA 接受方案并改为接口 v3;讨论记录改为带版本号命名

**MAFA 回复:** 自查注入伪迹方向一致(最后表态为 A:mdagents 44% 对 22%,dylan 90% 对 43%;金标准为 A 约 12%);人类版数据包无合成数据,模板句 0 次。对 (c):①同意;②责任改挂在**每个判为存在的码**上(促成:是/否/不确定),有责任的智能体由码推出,最早责任步 = 促成码里最早的步骤;③促成时必选至少一个下游被采用步骤(直接责任选「最终答案」),完整链可选;④⑤码层仍依赖体系,另加「无对应码的缺陷」行(也标促成);体系无关责任集合 = 有码促成 ∪ 无码促成,双体系轨迹另给交集;答错但追溯不到须勾「找不到可追溯的缺陷」,从而区分「体系覆盖不到」与「完全追溯不到」两种逃逸;⑥责任层单独算 κ,盲审含责任层。导出将升到接口 v3,提交号稍后发来。
**核对:**
- MAFA 的 `data/simulated/` 与本项目 AEGIS-custom-dataset-8-13 是**同一份数据**(mdagents 1003/1003、dylan 1062/1062 条轨迹逐条一致;MAFA 不含 llm_debate)。按「最后表态」口径本项目算得 mdagents 51% 对 18%、dylan 50% 对 10%(金标准为 A:13%、19%)。方向一致,但 dylan 差很多(90/43 对 50/10)→ 差异来自抽取器/口径,至少一方在 dylan 上不可靠;论文引用前需共用一个抽取器并人工抽查。
- **对 ② 的问题:** human-like-v1 中 61 个「存在」码有 19 个(31%)挂多个智能体但只记一个步骤。责任挂在整个码上会 (i) 把没促成的智能体也算有责任,(ii) 让最早责任步取码记录的那一步,而非真正被采用的那一处。建议责任挂在(码, 智能体, 步骤)实例上,或标「是」时勾选该码中实际促成的智能体/步骤。
**做了:** `RUN.md` 改名为 `RUN_v0.7.md`(带版本号);`HANDOFF.md` 同步。
**未决:** 等 MAFA 接口 v3 提交号;届时把 `analysis/dataset_analysis.py --annotations` 的逃逸率骨架改成读 v3(两种逃逸分开)。
