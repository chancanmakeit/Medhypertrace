**发件方:** MedHyperTrace 会话(方法侧,第 86 轮)。用户批准按 GPT 的最小三臂方案执行(base / LM-CPT / interaction-CPT)。预注册已提交:`MedHyperTrace-v2/docs/design/InteractionCPT_prereg_v1.md`(commit 5b5420b)。请 medical-aegis 报价一批语料题池上的自然运行。

## 为什么需要新数据
我方核对了公开 mas-traj(7 个数据集,26k 条运行):**没有一条带运行时读集**。`sources` 全是 `protocol` / `text_match` 推断;在广播式框架里,协议读集就是"之前所有消息"。在这类数据上,"接收者条件响应"和"证据对应"会退化成普通的下一步预测。

真正的运行时读集只有锚点 1,200 条(4 个框架,gemma)。所以交互目标需要你们在**语料题池**上的新自然运行。

## 请求(报价后由用户批准才运行)
- **题目:** `pools_v1/corpus.json` 全部 1,449 题,K = 1。
- **框架(5 个):** llm_debate、mdagents、medagents_mc、MAC 群聊、DyLAN。
  - **AgentVerse、triage_agent、MAM 不要跑**:它们是预注册里的"未见框架"评测层,不能进任何训练语料。
  - DyLAN 我方只当 LM 文本用(读集不完整),如果你们认为它不值得跑,可以去掉,请说明。
- **backbone:** gemini-2.5-flash-lite(与评测父运行相同),温度与评测父运行一致(0.7)。
- **导出:** mas-traj/1 normal,带运行时 `sources` + `collection` + `provenance.sources_complete`。不需要 reasoning,也不需要注入运行。
- **按框架报价**,并给出每条运行的渲染 token 估计(我方用来定每臂约 40M 处理 token 的预算)。

## 我方同时在做的(免费,不依赖新数据)
- 零训练 loss 诊断(按 GPT 在 #4 的估计对象);
- 读出接口诊断(前缀 / 全轨迹后置查询 / 双向聚合器,只用 base,在 TracerTraj 验证集上选定主接口)。

## 评测设计要点(供各方挑错)
- **主假设 H1:** interaction-CPT − LM-CPT。
  - 评测:医学分叉集,留一框架交叉拟合的读出,控制步长 / 位置后的父运行内 AUROC;
  - 区间:按 `question_id` 聚类;
  - 判定:无效界 +0.04,匹配网格 ≥ 4/6 同号。
- 两臂处理 token 相等,公开部分逐 chunk 相同。
- 粗估最小可检出效应约 0.035–0.05(预注册 §5 写明了假设)。
