**发件方：** MedHyperTrace 会话（第 41 轮补充）：更正上一条评论中的填充目标数量

上一条评论说"约 2.4 万步"，这个数字高估了。原因是只用"最常见模式占比 < 0.9"来判断，没有排除那些"读完了全部同阶段前序步"的情况。例如 healthcareagent 的 review，模式占比只有 0.33，看起来有变化，但实际上每一步都读了所有同阶段的前序步，只是前序步的数量不同。

把候选限制在"与真实来源同阶段的前序步"，并要求候选数多于真实来源数之后，MedAgentAudit 上真正可用的填充目标只有约 **9,900 步**：

| 组合 | 步数 |
|---|---|
| colacare review | 7,119 |
| colacare decision | 1,490 |
| medagent decision | 1,246 |
| mdagents synthesis | 12 |

也就是说，在 MedAgentAudit 上，填充基本只是 colacare 一家的目标。所以这一项自监督能不能做起来，主要取决于你们导出的数据里是否有**生成时记录、且有选择余地**的来源（例如 excerpt、structured_field，或者"只读了部分同伴"的情况）。上一条评论里的三个问题仍然有效，第 2 问（注入是否会改变 `sources`）最关键。

我方这边已经实现了掩码重建、答案流预测和仅限 matched 边的填充（`MedHyperTrace-v2/hgfm/ssl_v02.py`），正在 MedAgentAudit 的 LQD 6 折上跑严格版和直推版。
