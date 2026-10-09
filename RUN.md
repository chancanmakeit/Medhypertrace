# RUN.md — 每轮讨论记录

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
