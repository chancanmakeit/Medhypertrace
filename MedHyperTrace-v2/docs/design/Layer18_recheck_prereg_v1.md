# 第 18 层复核预注册 v1(第 101 轮,2026-11-08 10:20 UTC)

写在任何下列计算之前。唯一已经看过的第 18 层结果:
- H-L1:lm − base,医学集;
- 闸门 G:it18;
- 公开集 stage A:lm18 − it18。

见 `results/outcome/README.md`。

**用户决定(第 101 轮):**
- H-L1 的复现按我方建议;
- 检查之前的阴性结论;
- P-TT 记录下来,作为附录候选。

**计算:** 只用 Linux #1。Linux #2 上的合并模型只拷贝、不在那里计算。

## R1 · H-L1 的复现

### R1a 交叉拟合选层(零成本,立即做)

这一步检验的是"第 18 层是在同一数据上挑的"这一选择偏差。**它不是独立复现:这批数据在 L18 上已经看过。**

- **层网格:** {9, 12, 15, 18, 21, 24, 27, 36},覆盖后训练版(it)和 LM-CPT 臂(lm)。
- **打分:** 每个配置用 `med_eval score`(LOFO,agg 头)给每个父运行打分,和 G0 完全相同。
- **划分:** 237 个父运行按 question_id 用种子 0 分成两半 A、B。
- **选层与检验:**
  - 在 A 上,只看 base 的控制后平均 AUROC,选最高的层 l_A(和 G0 的规则一样,不看 lm);
  - 在 B 上,计算 lm(l_A) − base(l_A);
  - 再把 A、B 对调。
  - 每个父运行只在另一半选出的层上计一次差值,合并后按 question_id 聚类 bootstrap。
- **判定:** interaction-CPT §4.3 规则。HOLDS = CI 下界 > 0 且匹配网格 ≥ 4/6 同号;NULL = CI 上界 < +0.04。
- **同时报告:**
  - l_A、l_B 各是哪一层;
  - lm − base 在全部 8 层上的曲线(只作描述)。

### R1b 新数据上的真复现(付费,要先报价,再由用户批准)

- 向 medical-aegis 询问一批**新**评测父运行的报价:
  - 协议 v3,题目与已有题池和我方所有语料不重叠;
  - 框架上优先选步长 / 位置与阳性解耦的,例如 mdagents。
- 假设固定为 H-L1:L18,agg 头,控制后,§4.3 规则。不再挑层、不换读出头。
- 报价回来后先报给用户,批准前不生成。

## R2 · 在第 18 层复核之前的阴性结论

- **层固定为 18**(G0 按 base 选出),R2 不考虑任何其他层。
- **特征和分析代码与原实验相同,只把特征换成第 18 层:**
  - step-mean 接口:`e4_features --layers 18`;
  - 前缀接口:`feat_query --layer 18`,本轮新增参数,默认行为不变。
- **判定规则沿用各原预注册。**

| 编号 | 原结论 | 第 18 层复核的比较 | 数据 | 原规则 |
|---|---|---|---|---|
| R2.1 | E4 stage A(第 74 轮):tapt / S / R 相对 base 控制后不成立 | tapt − base、S − base、R − base;linear、MLP 为主,agg 为辅 | 公开 WW + TEgc,jac0.7 聚类 | E4_prereg_v1 |
| R2.2 | 阶段 0 Q1 / Q1′(标签效率):NULL | tapt − base、tapt_clean − base,标签效率曲线面积(n = 100 / 300 / 1000 / 全量;linear、MLP) | 公开 | Stage0_prereg_v1 |
| R2.3 | 阶段 0 Q2(负对照):未定 | R − irr、R − shuf | 公开 | Stage0_prereg_v1 |
| R2.4 | 阶段 0 Q3 / Q3′(剂量):NULL | full − tapt、full − tapt_clean | 公开 | Stage0_prereg_v1 |
| R2.5 | ICPT H1(第 95 轮):NULL | icpt − lm,前缀接口 + agg,医学集控制后;H2 / H3 按原定义 | 医学 | InteractionCPT_prereg_v1 |
| R2.6(探索) | 无 | 各臂第 18 层 − base 第 18 层(med_eval agg / linear) | 医学 | 只描述,不判定 |

- **多重比较:**
  - R2.1–R2.5 共 12 个比较(R2.1 有 3 个臂 × 主读出头),全部报告。
  - 某个阴性结论只有在第 18 层判 HOLDS,**并且**按 Holm 校正后仍显著(family = 这 12 个比较),才写成"在第 18 层被推翻";
  - 只过了未校正门槛的,写成"需复现"。
- **对照:** 每一项都和原第 36 层的数字并列报告。

## P-TT(用户:记录,作附录候选)

- 线 2 的 HP2:公开集上 P-TT − F-TT = +0.068 [+0.032, +0.104]。
- 写进 `docs/paper/appendix_candidates.md`。本轮不追加计算。

## 计算与产物

- **Linux #1**(`/data1/cgh/code/mht`):`models/` 放 it、lm、icpt,以及从 Linux #2 拷来的 tapt、S、R、full、nc_irr、nc_shuf、tapt_clean。
- **驱动:** `scripts/linux1_run_layer18_recheck.sh`。
  - 先抽特征:R1a 的医学多层特征;R2 的公开 / 医学第 18 层特征;
  - 再跑读出:stage A、标签效率、med_eval;
  - 最后分析。
- **结果:** `results/layer18_recheck/README.md`。
