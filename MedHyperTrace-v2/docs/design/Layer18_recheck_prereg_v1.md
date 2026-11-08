# 第 18 层复核预注册 v1(第 101 轮,2026-11-08 10:04 UTC 提交,e4d8048)

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
  - 后置查询接口:`feat_query --layer 18`,本轮新增参数,默认行为不变(见 C1.2:前缀接口其实就是上面的 `e4_features`)。
- **判定规则沿用各原预注册。**

| 编号 | 原结论 | 第 18 层复核的比较 | 数据 | 原规则 |
|---|---|---|---|---|
| R2.1 | E4 stage A(第 74 轮):tapt / S / R 相对 base 控制后不成立 | tapt − base、S − base、R − base;linear、MLP 为主,agg 为辅 | 公开 WW + TEgc,jac0.7 聚类 | E4_prereg_v1 |
| R2.2 | 阶段 0 Q1 / Q1′(标签效率):NULL | tapt − base、tapt_clean − base,标签效率曲线面积(n = 100 / 300 / 1000 / 全量;linear、MLP) | 公开 | Stage0_prereg_v1 |
| R2.3 | 阶段 0 Q2(负对照):未定 | R − irr、R − shuf | 公开 | Stage0_prereg_v1 |
| R2.4 | 阶段 0 Q3 / Q3′(剂量):NULL | full − tapt、full − tapt_clean | 公开 | Stage0_prereg_v1 |
| R2.5 | ICPT H1(第 95 轮):NULL | icpt − lm,前缀接口(`e4_features`)+ agg,医学集控制后;H2 / H3 / H4 按原定义(见 C1.2) | 医学 + 公开 | InteractionCPT_prereg_v1 |
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

## C1 · 澄清与更正(第 101 轮,约 10:17 UTC 提交)

时间线:Linux #1 驱动 10:15 UTC 启动抽特征。提交本节时,还没有任何特征文件完成,也没有任何 R1/R2 结果。

翻原驱动脚本时发现上文有两处写错、两处没写清,在这里更正。

1. **"base" 的含义。** 本文的 base 一律指 CPT 起点,也就是后训练版 Qwen3-8B(`models/it`,和 E4 / 阶段 0 / ICPT 原驱动里的 `BASE=Qwen/Qwen3-8B` 是同一个模型),不是 Qwen3-8B-Base。R1a 里"只看 base 选层"即只看 it。

2. **ICPT 的接口(更正 R2.5 行)。**
   - 原 ICPT 预注册 §3 诊断选中的主接口是 (c):前缀特征(`e4_features`)加聚合器,医学集主读出头为 `med_eval agg`。
   - `feat_query` 是 (b) 后置查询接口,只作次要报告。
   - 所以 R2.5 的主比较是:icpt − lm,用 `e4_features --layers 18` 抽的医学特征,`med_eval agg`,控制后。linear 头和 `feat_query --layer 18` 作次要报告。
   - H2 = icpt − base,H3 = lm − base。注意 H3 在第 18 层就是 H-L1 本身,结果已经看过,这里只为完整列出。
   - H4 用公开集 LE 面积,在前缀接口上比较 base / lm / icpt 三者;主读出头按原 ICPT 修正案 A4 为 agg,linear 和 mlp 作次要报告。

3. **E1 OAT 不在第 18 层重跑。**
   - 原 Q2 判定规则和 Q3 的 NULL 条件用到了 E1 OAT 的匹配差。OAT 流水线固定只取末层(`OAT_LAST_LAYER_ONLY=1`),本复核不改它。
   - 第 18 层上的替代做法:
     - **Q2:** 照搬原 `q2_rule`,只是把每个比较的"primary"从 E1 匹配差换成 LE 面积(linear,控制后)。
     - **Q3:** 只看 LE 面积(linear,控制后)。HOLDS 规则不变;NULL 只要求 LE 面积 CI 上界 < +0.04。原规则另要求 E1 也满足,这一条在 L18 无法检查,标注为"部分 NULL"。
   - 这是和原规则的已知偏差,结果表里注明。

4. **特征来源。**
   - base 在公开集上的 L18 特征复用 `xfer/pub_it_L18.pt`:G0 时在 Linux #2 抽取,第 99 轮已验证两台机器的特征逐位一致。
   - lm 的公开 L18 特征复用 `runs/layer18/pub_lm_L18.pt`。
   - 其余全部在 Linux #1 重抽。

5. **Holm family:12 个比较,全部是控制后指标、主读出头。**

   | 来源 | 比较 | 读出 | 个数 |
   |---|---|---|---|
   | R2.1 | tapt / S / R − base | stage A linear | 3 |
   | R2.2 | tapt / tapt_clean − base | LE 面积 linear | 2 |
   | R2.3 | R − irr、R − shuf | LE 面积 linear | 2 |
   | R2.4 | full − tapt、full − tapt_clean | LE 面积 linear | 2 |
   | R2.5 | H1 icpt − lm | 医学 agg | 1 |
   | R2.5 | H2 icpt − base、H3 lm − base | 医学 agg | 2 |

   - p 值用双侧正态近似:se = (CI 上界 − CI 下界) / 3.92,z = 差值 / se。
   - MLP 头、raw、clean 子集都只作次要报告,不进 family。
