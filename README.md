# MedHyperTrace

面向医学多智能体系统（MAS）错误轨迹的三级失败归因（**agent / mode(FM) / step**）。
主方法是异构超图神经网络；配套一整套同口径基线与评测基础设施。

---

## 目录结构

```
medhypertrace/
├── common/                     # 共享基础设施（所有方法都依赖）
│   ├── data.py                 # 统一 parser（吃平 mdagents/dylan/llm_debate）+ 超图构造 + 三级标签
│   ├── aegis_metrics.py        # 你 AEGIS_Reproduce 的 compute_metrics（原样 vendor，保证口径一致）
│   ├── splits.py / paths.py    # 固定 task 划分加载器 + 数据/路径配置（读 MHT_DATA_DIR）
│   ├── splits.json             # 固定 train/test task-id 清单（防变体泄漏）
│   └── export_splits.py        # 重新生成 splits.json
│
├── ours/                       # ★ 我们的方法：MedHyperTrace HGNN
│   ├── hypergraph_model.py     # relation-aware 超图卷积（文献谱系见文件头注释：HGNN/AAAI19
│   │                           #   + HGNN+/TPAMI22 hyperedge groups + HyperGAT 注意力 + AllSet 框架）
│   │                           #   含 StandardHGNNPLayer（=DHG HGNNPConv 的原生等价实现，backbone 消融）
│   │                           #   pair 头：pair_logit = agent_logit + mode_logit（层次一致性内建）
│   ├── train_hgnn.py           # v2：--features tfidf|nomic --struct --backbone relation|standard
│   │                           #   --prop(传播一致性) --margin(step边际) joint/--holdout(跨框架OOD)
│   │                           #   val 上按类校准阈值；step 损失本就是 listwise softmax（+margin 项）
│   └── hgnn_unified_eval.py    # 走 compute_metrics 出 Agent/Error/Pair（实例+角色）+ step Top-k
│
├── baselines/
│   ├── pointwise/              # 无结构下界：TF-IDF + 逻辑回归
│   │   ├── baseline_pointwise.py
│   │   └── pointwise_unified_eval.py   # 统一口径版（推荐用这个出数）
│   ├── whowhen/                # Who&When (ICML'25) 三协议，需 LLM endpoint
│   │   └── baseline_whowhen.py
│   ├── echo/                   # ECHO (arXiv:2510.04886) 复现：分层上下文+6角色分析员
│   │   └── baseline_echo.py    #   panel+置信加权共识，需 LLM endpoint
│   ├── famas/                  # FAMAS (arXiv:2509.13782) 复现：谱分析（精确公式 Eq.2-8）
│   │   └── baseline_famas.py   #   variant/success/replay 三种谱群体模式，本地确定性可跑
│   ├── graphtracer/            # GraphTracer 结构核心复现（IDG+Impact分数，确定性）
│   │   └── baseline_graphtracer.py
│   ├── agenttrace/             # AgentTrace 复现（因果图+反向BFS+17特征加权，确定性）
│   │   └── baseline_agenttrace.py
│   ├── aegis_sft_ood/          # AEGIS-SFT（通用→医学，OOD 迁移），用你已有模型
│   │   ├── bridge_to_aegis_eval.py     # 把医学数据转成你 evaluate-v3.py 的输入
│   │   ├── eval_samples/*.jsonl        # 已转好的固定 test-set 样本
│   │   └── HOWTO.md
│   └── aegis_med_sft/          # AEGIS-med-SFT（医学 in-domain 重训），两版输出
│       ├── preprocess_med_sft.py       # 生成 verl SFT parquet（no_step / with_step，实例粒度）
│       ├── aegis_med.py                # 医学 prompt/target/解析 + step 评分
│       └── HOWTO.md
│
├── docs/overview_figure_prompt.md      # 生成 overview 图的 prompt（GPT-Image/Nano Banana）
├── data/                       # 放数据集（见 data/README.md），或用 MHT_DATA_DIR
├── common/embed_cache.py       # 嵌入缓存（多模型：--model mxbai|nomic|<HF-id>；分块断点续传；
│                               #   device 默认 auto = 有CUDA用CUDA否则CPU）
├── validate.py                 # 数据/超图健全性检查
└── requirements.txt
```

---

## 方法 / 基线状态一览

| 名称 | 类型 | 训练域 | 粒度 | step | 状态 | 运行环境 |
|---|---|---|---|---|---|---|
| **MedHyperTrace HGNN** | 主方法 | 医学 | 实例+角色 | ✓ | ✅ 本地跑通、出数 | CPU |
| HGNN 去超边 | 消融 | 医学 | 同上 | ✓ | ✅ 本地跑通 | CPU |
| Pointwise (TF-IDF) | 基线 | 医学 | 角色 | ✓ | ✅ 本地出数 | CPU |
| Who&When ×3 | 基线 | — (prompting) | 角色 | ✓ | 🔌 适配器就绪、mock 验证 | 需 LLM endpoint |
| ECHO | 基线 | — (prompting) | 角色 | ✓ | 🔌 忠实复现、mock 验证 | 需 LLM endpoint |
| FAMAS | 基线 | — (谱分析) | 角色 | ✓ | ✅ variant模式已出数(成功轨迹/重放待接入) | CPU |

### 数据集：四个框架（2026-07-24 更新）
新增 **clinical_agent**（trial_success-200，402条/133任务）：固定6步流水线
（Planner→ClinicalAgent→Safety/Efficacy/Enrollment→Reasoner），**100%轨迹恰好2个责任agent**，
13类FM，无 masked step。schema 与原三框架一致（`injection_log.conversation_history`），
parser/超图构造器零改动即可用。原三框架划分**重新生成后与旧版逐位相同**（seed=0确定性），
历史数字全部仍可比。新划分：clinical_agent train 94任务(297条) / test 39任务(105条)。
| GraphTracer(结构核心) | 基线 | — (确定性) | 角色 | ✓ | ✅ 本地出数(RL-8B部分需GPU自建) | CPU |
| AgentTrace | 基线 | — (确定性) | 角色 | ✓ | ✅ 本地出数 | CPU |
| AEGIS-SFT (OOD) | 基线 | 通用→医学 | 角色 | ✗ | 🔌 桥接+样本就绪 | 需你的 SFT 权重 + GPU |
| AEGIS-med-SFT | 基线 | 医学 in-domain | 实例 | no_step / with_step(最早错误步) | 🏗️ 训练数据就绪、待训 | 需 GPU 训练 |

> 真正在真实模型上出过数的只有前三行（本地 CPU）。后三行是"代码/适配器/数据就绪，
> 待你在 GPU 上跑真实推理/训练"——本环境无 GPU、无 LLM 权重、无 API。

**统一口径**：所有方法都归约成"每条轨迹的 `(agent, FM)` 对"，喂进同一个 `compute_metrics`，
在同一份 `splits.json` 固定 test-set 上，输出 Agent/Error/Pair × Micro/Macro-F1。
step 是单独子表（最早错误步 Top-1，所有方法同口径），AEGIS-SFT-no_step 不参与（结构上不预测 step）。

---

## 快速开始

```bash
pip install -r requirements.txt
# 放数据：把 AEGIS-custom-dataset 解到 data/ 下，或 export MHT_DATA_DIR=/path
python validate.py                                    # 健全性检查

# 本地可跑：
python baselines/pointwise/pointwise_unified_eval.py  # pointwise 统一口径
python ours/hgnn_unified_eval.py dylan                # HGNN 统一口径（单框架）
python ours/train_hgnn.py llm_debate                  # HGNN full vs 去超边

# 需 GPU/LLM（见各自 HOWTO.md）：
python baselines/aegis_med_sft/preprocess_med_sft.py --variant with_step --out data_med_withstep
python baselines/aegis_sft_ood/bridge_to_aegis_eval.py --out med_eval --test_only
```

## 说明
- 数据集路径统一由 `common/paths.py` 管理，改 `MHT_DATA_DIR` 环境变量即可。
- 固定划分由 `common/splits.json` 保证所有方法可比、防同题变体泄漏。
- v2 已并入改进 A–G（阈值校准/nomic特征通路/结构先验/传播一致性/joint+OOD/pair头/step margin）。
  CPU 短训验证（dylan，6ep）：**结构先验特征是 step 的主要增益来源**
  （Top-1 0.546→0.70+）；joint 训练 1ep 即在 llm_debate 达 0.66（v1 20ep 为 0.523）。
  标准 HGNN+ backbone 短训下与 relation-aware 相当（0.721 vs 0.697）——relation-aware
  的优势需在长训/pair 指标上复验。pair-F1 仍需 GPU 长训 + 真实 nomic 特征提升。
- dhg 库在 py3.12 wheel 构建失败；StandardHGNNPLayer 为其 HGNNPConv 的原生等价实现。
- 论文引用注意：不要写"我们使用 HGNN[Feng 2019]"，用 hypergraph_model.py 头注释里的
  精确表述（relation-aware conv 实例化 AllSet 两阶段框架 + HGNN 式归一化 + R-GCN 式
  关系参数 + HyperGAT 式超边内注意力）。Hyper-RAG 无任何超图神经网络（仅 Hypergraph-DB
  符号存储+向量检索），我们只借其"n 元关系需超边"的表示论证。
```
