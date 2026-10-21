# MedHyperTrace：医学多智能体系统故障归因

本仓库包含两代方法，代码完全分开：

| 目录 | 方法 | 状态 |
|---|---|---|
| [`MedHyperTrace-v1/`](MedHyperTrace-v1/README.md) | 原方法：针对 AEGIS 合成数据的任务特定异构超图神经网络（agent / FM / step 三级归因），配套基线、MAFA 联合评测 | 冻结；在 human-like 标注上未超过平凡基线（见 `HANDOFF.md` §0.25–0.30） |
| [`MedHyperTrace-v2/`](MedHyperTrace-v2/README.md) | 新方法：多智能体轨迹的超图基础模型（HGFM），跨框架零样本，后续耦合冻结 LLM | 开发中 |

根目录只放项目级文档：
- `HANDOFF.md`：交接文档，新会话先读 §0。
- `RUN_v0.<N>.md`：每轮讨论记录。
- `README.md`：本文件。

两个版本各自从自己的目录运行（`cd MedHyperTrace-v1` 或 `cd MedHyperTrace-v2`）。
