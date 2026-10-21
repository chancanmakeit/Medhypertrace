# S− 档:可插拔事实核查 provider

**定位**:S− 档(模型固有失败,轨迹内无结构信号,只能靠外部世界知识检测)。
我们**不发明新的幻觉检测器**,而是定义一个统一接口,把近两年的开源 SOTA 检测器
作为一个节点特征插入。超图仍是**归因器**,检测器是**特征提供者**。贡献边界诚实:
我们把外部事实核查**整合进结构化归因**,证明结构信号与外部核查如何互补。

## 接口(`common/factuality_provider.py`)

```python
provider.score_steps(steps, context) -> np.ndarray[n] in [0,1]
# 每个 acting step 一个"事实可疑度"分(1=很可能是幻觉)
```

分数作为一维节点特征追加到 7 维结构先验之后(`structural_features_with_factuality`),
再由超图沿 agg/ctx/role/phase 超边传播——所以"这个幻觉有没有被下游采信"由**同一套
传播机制**回答,不是外挂。

用法:`train_hgnn.py --factuality {null|heuristic|nli|medical}`
- `null`(默认):无外部信号,7 维不变,数值与现在**逐位相同**(纯结构档)。
- `heuristic`:CPU 占位符(数值医学声明密度),**仅供管线/消融测试,不可当真实检测器报告**。
- `nli` / `medical`:需接入真实检测器(见下)。

## ⚠️ 关键约束:静态轨迹 vs 需重采样

我们的轨迹是**已跑完的静态数据**,拿不到"对同一 agent 同一问题重新采样"的能力。
这直接决定哪些检测器能用:

| 类别 | 代表方法 | 需重采样? | 能否直接用 |
|---|---|---|---|
| 一致性/采样 | SelfCheckGPT, Semantic Entropy(Nature'24) | **是** | ❌ 除非能重跑 agent |
| NLI/分解entailment | RefChecker, Decomposed-Entailment, FactSelfCheck | 否 | ✅ 静态文本可用 |
| LLM-judge / 医学 | MedHallu(EMNLP'25), KnowHalu, MIT medical_hallucination | 否 | ✅ 需一个 judge/KB |

**优先接 NLI 类和医学类**(静态文本友好),不要接 SelfCheckGPT/Semantic Entropy
(它们要重采样)——除非你能重跑原 MAS 的那个 agent。

## 候选开源检测器(近两年)

**通用黑盒(静态可用)**
- **RefChecker**(Amazon,2024,开源):把回答分解成原子声明,基于参考做细粒度核查。
  最贴合 `NLIFactualityProvider`:`claim_splitter` + `nli_model` 两个 callable 接进来。
- **FactSelfCheck**(2025,开源):fact-level,建知识图谱算 fact 级一致性,输出可当每步分。
- **Decomposed Entailment**(2025):encoder-based NLI,把事实核查当约束分类,高效可复现。

**医学专用(你的领域,优先看)**
- **MedHallu**(EMNLP 2025,medhallu.github.io,开源):最大开源医学幻觉检测基准+方法。
- **MIT medical_hallucination**(2025,github.com/mitmedialab/medical_hallucination):
  医学幻觉标注框架(NEJM case reports),其类型学可与我们的 FC0/F1.1.1 对齐。
- **KnowHalu**(2024,开源):multi-form 知识核查,适合需外部医学 KB 的场景。

**综述/清单**(找更多)
- EdinburghNLP/awesome-hallucination-detection
- mala-lab/Awesome-LLM-LVLM-Hallucination-Detection-and-Mitigation

## 接一个真实 provider 的最小改动

```python
# NLI 类(RefChecker 风格)
from common.factuality_provider import NLIFactualityProvider
prov = NLIFactualityProvider(
    nli_model=my_nli,          # callable(premise, hypothesis) -> P(entail)
    claim_splitter=my_split)   # callable(text) -> [atomic claims]

# 医学 judge 类(MedHallu 风格)
from common.factuality_provider import MedFactualityProvider
prov = MedFactualityProvider(judge=my_med_judge)  # callable(step_text, ctx) -> [0,1]
```
然后在 `train_hgnn` 里让 `_make_fact_provider` 返回它(或加一个 `--factuality_ckpt`
路径参数指向你的检测器权重)。

## 三段式消融(论文用)

провайдер 一换就是一档,直接产出"结构方法能力边界"那张图:
1. `--factuality null` → 纯结构(覆盖 S+)
2. `--factuality null` + 传播一致性损失(`--prop`)→ +传播足迹(覆盖 S~)
3. `--factuality nli|medical` → +外部事实核查(触及 S−)

对比三档在"幻觉主导的失败(FC0/F1.1.1)"上的归因提升,量化每一档各救回多少。
若第 3 档明显涨 → 外部核查必要;若不涨 → 证明结构信号已足够、外部核查冗余。
两个方向都是可发表的结论。

---

## 已接好的真实检测器:NLI(RefChecker 风格)

`common/factuality_nli.py` 是一个**可运行的真实检测器**(不是占位符),实现 RefChecker 的
NLI-checker 分支:规则分解声明 + 小型开源 NLI 模型核查,**全程离线、无需 LLM/API**。

```bash
# 三段式消融一键跑(需 GPU+torch):
python ours/ablation_tiers.py --frameworks clinical_agent mdagents \
    --features emb --emb_model mxbai --epochs 30 --out ablation.json
# 沙箱无 torch 时,它会打印三档的确切命令供复制到服务器跑。

# 或手动单档:
python ours/hgnn_unified_eval.py clinical_agent --features emb --emb_model mxbai --epochs 30 \
    --struct 1 --prop 0.1 --factuality nli \
    --factuality_model cross-encoder/nli-deberta-v3-small --factuality_ref prior-steps \
    --json_out ours_nli.json --report_gran role
```

**三档对应 S+/S~/S−**:
- t1 `--prop 0 --factuality null` → 纯结构(S+)
- t2 `--prop 0.1 --factuality null` → +传播一致性(S~)
- t3 `--prop 0.1 --factuality nli` → +外部事实核查(S−)

**NLI 模型**(`--factuality_model`,都小、开源、CPU 可载):
- `cross-encoder/nli-deberta-v3-small`(默认,~140MB)
- `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`
- `roberta-large-mnli`(RefChecker 的 RoBERTa-NLI 基线)

**参考源**(`--factuality_ref`,即每个声明核查的对象):
- `prior-steps`(默认):同轨迹更早的步 → 检测"缺乏对话内支撑"的声明
- `gold-answer`:轨迹已知正确答案 → 最接近"事实错误"
- `none`:用外部传入的 context(接你自己的检索/KB)

**默认 null 逐位不变**:不加 `--factuality` 时走原 7 维路径,现有数字完全不受影响。

**升级到医学专用**:把 `--factuality_model` 换成医学 NLI/judge,或实现 `MedFactualityProvider`
的 `judge` callable(接 MedHallu/KnowHalu),接口不变。
