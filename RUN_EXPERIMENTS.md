# RUN_EXPERIMENTS — 完整实验运行文档

覆盖论文所需的全部实验:本地 CPU 可跑的、以及必须在你 GPU 机器上跑的。
所有实验共享同一份固定划分(`common/splits.json`)与同一套指标
(`common/aegis_metrics.py` = 你 AEGIS_Reproduce 的 compute_metrics 原样 vendor)。

> 标注约定:🖥️=CPU 即可;🚀=需要 GPU;🌐=需要 LLM API/endpoint。
> 时间估计以单卡 A6000/A800 级别为参考。

---

## 0. 环境与数据(一次性)

```bash
# 0.1 解压代码包,安装依赖
unzip medhypertrace.zip && cd medhypertrace
pip install -r requirements.txt          # torch/sklearn/pandas/pyarrow/py7zr 等
pip install sentence-transformers einops # 嵌入编码需要(mxbai 直接从 HF 拉取)

# 0.2 放数据集(二选一)
py7zr x AEGIS-custom-dataset.7z -o data/            # 方式A:解到 data/ 下
export MHT_DATA_DIR=/abs/path/AEGIS-custom-dataset  # 方式B:环境变量指向
# Windows PowerShell: $env:MHT_DATA_DIR="F:\path\AEGIS-custom-dataset"

# 0.3 (可选)nomic 嵌入模型 —— 仅当你要用 --model nomic 时;默认推荐 mxbai(无需手动放置)
# 解压 models--nomic-ai--nomic-embed-text-v1.5 到任意目录,并确保目录里有
# modeling_hf_nomic_bert.py / configuration_hf_nomic_bert.py 且 config.json 的
# auto_map 已本地化(我给你的版本已处理好;若用原始 HF 下载则无需处理)。
export NOMIC_PATH=/abs/path/models--nomic-ai--nomic-embed-text-v1.5

# 0.4 健全性检查(必跑,~1min)🖥️
python validate.py
# 期望:五框架均 step-loss masked = 0(clinical_agent5 单故障除外亦为0);超边统计正常
```

固定划分已随包提供(`common/splits.json`)。**不要重新生成**,否则与已出数字不可比;
若确需重生成:`python common/export_splits.py`(seed=0)。

---

## 1. 本地基线(CPU,共 ~15 min)🖥️

```bash
# 1.1 Pointwise(无结构下界,统一口径 6 列)
python baselines/pointwise/pointwise_unified_eval.py
# → 每框架一行:Agent/Error/Pair × mi/ma(角色粒度)

# 1.2 GraphTracer 结构核心复现(确定性,step 排序)
python baselines/graphtracer/baseline_graphtracer.py
# 1.3 AgentTrace 复现(确定性,因果图 RCA)
python baselines/agenttrace/baseline_agenttrace.py
# → 每框架:step Top-1/Top-3 + agent-hit@1
# 注:GraphTracer 的 RL-8B tracer 部分论文未开源,不在此复现范围(如需要须自建管线)
```

---

## 2. 我们的方法 MedHyperTrace(主实验)

### 2.1 嵌入缓存(一次性;device 默认 auto,有 CUDA 自动用 CUDA)🚀

```bash
# 推荐 mxbai(384维,CPU ~22 texts/s,比 nomic 快 12 倍);五框架全量约 31k 步
python common/embed_cache.py all --model mxbai
# 也可 --model nomic(768维)或任意 HF id / 本地路径;--device auto|cuda|cpu(默认 auto)
# 产出 data/emb_cache/<model_tag>/{mdagents,dylan,llm_debate,clinical_agent,clinical_agent5}.npz
# 中断可直接重跑续传(EMB_CHUNK 控制分块;已存在的框架自动跳过)
# 本包已附带 mxbai 的 clinical_agent / mdagents 缓存;其余三框架需你本地补跑
```

### 2.2 主结果:五框架 × 两种特征(GPU ~30-60 min)🚀

```bash
# tfidf 特征(不依赖 2.1)
python ours/hgnn_unified_eval.py all --epochs 30
# 嵌入特征(依赖 2.1;论文主配置)
python ours/hgnn_unified_eval.py all --features emb --emb_model mxbai --epochs 30
#   --features nomic 仍可用(等价于 --features emb --emb_model nomic)
#   --device auto|cuda|cpu(默认 auto),也可用环境变量 MHT_DEVICE
# → 每框架输出:Agent/Error/Pair×mi/ma(实例+角色两套粒度)+ step Top-1/Top-3
# "all" = mdagents/dylan/llm_debate/clinical_agent/clinical_agent5 五个框架
```

### 2.3 消融(每个 = 主配置改一个开关;建议 emb 特征下做)🚀

```bash
B=" --features emb --emb_model mxbai --epochs 30"
python ours/train_hgnn.py all $B --backbone standard   # 标准HGNN+ vs relation-aware
python ours/train_hgnn.py all $B --struct 0            # 去结构先验特征(改进C)
python ours/train_hgnn.py all $B --prop 0              # 去传播一致性损失(改进D)
python ours/train_hgnn.py all $B --margin 0            # 去step margin项(改进G)
python ours/train_hgnn.py all $B --no_hyperedges       # 去全部超边(核心消融)
# Pair/Agent 指标的消融用 hgnn_unified_eval.py 加同样开关跑
```

### 2.4 联合训练 + 跨框架 OOD(改进E)🚀

```bash
python ours/train_hgnn.py joint $B                     # 五框架联合训练
python ours/train_hgnn.py x $B --holdout mdagents      # 训dylan+debate,测mdagents
python ours/train_hgnn.py x $B --holdout dylan
python ours/train_hgnn.py x $B --holdout llm_debate
```

---

## 3. AEGIS-med-SFT(in-domain 强基线)🚀

> **⚠️ 粒度统一(全流程 role):** 所有方法的两张表**统一用 role 粒度**。原因:Who\&When
> 零样本方法只能预测 role 名(LLM 猜不到 instance index),所以 gold 也降到 role;而
> mdagents 专家名细化后(§6b),role 与 instance 已几乎等价。**med-SFT 的粒度在
> preprocess 时就烘焙进训练目标了,所以 preprocess 和 eval 都要 `--agent_key role`,两者
> 必须一致**,否则训练目标和评测口径对不上。

```bash
# 3.1 生成训练数据(CPU 即可,~2 min;两版都生成)—— role 粒度
python baselines/aegis_med_sft/preprocess_med_sft.py --variant no_step   --agent_key role --out data_med_nostep
python baselines/aegis_med_sft/preprocess_med_sft.py --variant with_step --agent_key role --out data_med_withstep

# 3.2 训练(在你的 AEGIS_Reproduce 目录,用你现成的 train_sft-v2.sh;每版 ~数小时)
DATA_DIR=/path/medhypertrace/data_med_nostep   bash train_sft-v2.sh /path/data_med_nostep   ./outputs/aegis-med-sft-nostep
DATA_DIR=/path/medhypertrace/data_med_withstep bash train_sft-v2.sh /path/data_med_withstep ./outputs/aegis-med-sft-withstep
# 训完合并权重到 huggingface_merged(按你原有流程)

# 3.3 评测(回到 medhypertrace 目录;prompt 与训练字节一致;不要用 evaluate-v3.py 评 med-SFT)
# vLLM 服务(评测端):
#   python -m vllm.entrypoints.openai.api_server --model <.../global_step_50/huggingface_merged/> \
#       --served-model-name aegis-med-sft-withstep_Qwen2.5-7B-Instruct \
#       --data-parallel-size 4 --max-model-len 16384 --enable-prefix-caching
python baselines/aegis_med_sft/eval_med_sft.py --variant with_step --backend vllm \
    --base_url http://localhost:8000/v1 --model aegis-med-sft-withstep_Qwen2.5-7B-Instruct \
    --workers 32 --agent_key role --json_out medsft_fw.json --pooled_out medsft_pooled.json --out raw.jsonl
# --agent_key role : 必须与 3.1 preprocess 的粒度一致
# --json_out    : per-framework 指标(方法 key 'aegis_med_sft')-> 喂 make_main_table.py
# --pooled_out  : 五框架合并池指标(正确池化)-> 喂 make_agnostic_table.py
# --out raw.jsonl : dump 每条原始输出(排查 parse_ok 用)
# --backend hf --model <.../huggingface_merged> 也可(不起服务,但慢)
# → 每框架打印 parse_ok + Agent/Error/Pair×mi/ma + with_step 版 step Top-1
```

**parse_ok 排查经验(踩过的坑)**:
- `parse_ok` = 输出能被解析成结构化预测的比例。低了先 `--out raw.jsonl` 看原始输出,别猜。
- 已加固 `parse_prediction`:剥离 `<think>` 段、容忍 trailing comma/单引号、兼容 key 变体
  (agent/name、error_type/failure_mode 等)、抓 prose 中嵌入的 JSON。
- **空预测不是解析失败**:`{"faulty_agents": [], ...}` 是合法的"预测无责任 agent",
  必须按 key 是否存在判断(不能用 `x or ...`,空列表是 falsy 会误判)。这个 bug 已修。
- 若 parse_ok 已高但某框架 F1 异常低,可能是**模型退化成常数输出**(训练步数太少)。
  用 `--out` dump 后并排看 PRED vs GOLD 确认——若每条 PRED 都一样,就是欠拟合,需多训几轮,
  不是评估 bug。

---

## 4. AEGIS-SFT(OOD 迁移基线,你已有的通用模型)🚀

```bash
# 4.1 生成评测输入(CPU;固定test-set;角色粒度以公平对待OOD模型)
python baselines/aegis_sft_ood/bridge_to_aegis_eval.py --out med_eval --test_only --agent_key role

# 4.2 在你的 AEGIS_Reproduce 目录用 evaluate-v3.py 评(不要加 --use_cot!)
#    注意:evaluate-v3.py 顶部 sys.path.insert 指向 src/,你的仓库是平铺的,先改成当前目录
python evaluate-v3.py \
    --model_path outputs/global_step_110/huggingface_merged \
    --bench_jsonl  /path/med_eval/med_mdagents.jsonl \
    --whowhen_jsonl /path/med_eval/med_llm_debate.jsonl \
    --output_dir outputs/med_eval_ood --max_new_tokens 256
# evaluate-v3 一次吃两个文件;med_dylan.jsonl 再跑一次即可
# → Agent/Error/Pair×mi/ma(角色粒度);step 一栏 = N/A(该模型不预测step)
```

---

## 5. Who&When 协议基线🌐

**两种口径,分别对应论文的两张表:**

### 5a. 统一集合指标(主表:与 ours/pointwise/med-SFT 同一套 Micro-F1)📐

零样本协议改成**集合预测**变体,和我们的方法用同一个 `compute_metrics`,报
**Agent-Micro-F1 / Error-Micro-F1 / Pair-Micro-F1 + Step-Accuracy**。

```bash
# 先起 vLLM(服务端并行:tensor/data-parallel;客户端 --workers 喂满 continuous batching)
vllm serve Qwen/Qwen2.5-7B-Instruct --tensor-parallel-size 2 --data-parallel-size 2 --port 8000

python baselines/whowhen/eval_set_unified.py --backend openai \
    --model Qwen/Qwen2.5-7B-Instruct --base_url http://localhost:8000/v1 \
    --workers 32 --out set_metrics.json
# 方法:all_at_once_set / step_by_step_set(收集所有yes再逐个问FM)/ sdbl_set(先划scope再定位)
# 五框架 × 上述三方法;数值与 ours/pointwise/med-SFT 直接可比
```
- **binary_search 已从集合指标表移除**(二分本质单点定位,无法输出集合而不变成另一算法)。
- 沙箱验证:`--backend mock --limit N`(数值无意义,仅验证管线)。

### 5b. 单预测 accuracy(附录对照)🌐

原版协议(单预测),用 accuracy 报,作附录对照。含框架无关的合并池填表。

```bash
# 三协议 × 五框架 × (agent-hit@1 / step Top-1 / step±1 / FM-acc),含平凡基线对照
python baselines/whowhen/run_whowhen_table.py --backend openai \
    --model Qwen/Qwen2.5-7B-Instruct --base_url http://localhost:8000/v1 \
    --workers 32 --controls --out ww.json
# WW_STEP_CHARS 控制每步内容截断(默认600;设0=官方不截断)
# --limit N 按固定种子随机子采样(不是取前N条)

# 自动生成"框架无关"LaTeX 表(合并池,Σ命中/Σn)
python baselines/whowhen/fill_agnostic_table.py --backend openai \
    --model Qwen/Qwen2.5-7B-Instruct --base_url http://localhost:8000/v1 --workers 32 \
    --aegis_ood_json ood_pooled.json \
    --out_tex docs/table_agnostic_baselines.filled.tex
# AEGIS-SFT-OOD 行是集合预测,其合并池指标写成小json由 --aegis_ood_json 传入;不传则该行留 "--"
```

### 5c. ECHO(prompting 基线,每轨迹6次调用)🌐

```bash
python baselines/echo/baseline_echo.py --backend openai --model Qwen/Qwen2.5-7B-Instruct \
    --base_url http://localhost:8000/v1 --workers 32
# 按 trajectory-id 确定性播种,workers>1 与 =1 结果逐位相同
```

**并行语义保证**(适用 5a–5c 及 §3 的 med-SFT eval):`--workers` 只做跨轨迹并发,
不改任何单轨迹内部逻辑;已验证 **workers>1 与 =1 结果逐位相同**——纯加速不改数值。

**指标公式**(写论文用)——每条轨迹预测对集合 P、真值对集合 G,投影到层次 L∈{agent,error,pair}:
- TP=|P_L∩G_L|, FP=|P_L\G_L|, FN=|G_L\P_L|
- Micro-F1:先跨轨迹累加计数再算一次 → P=ΣTP/Σ(TP+FP), R=ΣTP/Σ(TP+FN), F1=2PR/(P+R)
- Macro-F1:每个类(agent名/FM码/对)单独累计算F1再无权平均
- Step-Acc:(1/N)Σ 1[最早预测错误步==最早真值错误步](单点,不套F1)

---

### 5d. 生成框架相关主表(表头细分框架,LaTeX)📄

`make_main_table.py` 把一个或多个结果 json 合并成框架相关主表(五框架 × 各方法 ×
Agent/Error/Pair-Micro-F1 + Step-Acc),每列最优自动加粗。

```bash
# 各方法先各自 dump 同格式 json({framework:{method:{metrics}}})。全部 role 粒度:
python baselines/whowhen/eval_set_unified.py --backend openai ... \
    --out set_metrics.json --pooled_out ww_pooled.json          # Who&When 固定 role
python baselines/pointwise/pointwise_unified_eval.py --json_out pointwise.json
python ours/hgnn_unified_eval.py all --features emb --emb_model mxbai --epochs 30 \
    --report_gran role --json_out ours_fw.json --pooled_out ours_pooled.json
# 只跑部分框架(排除某个,如不用 llm_debate)——加 --frameworks:
#   python ours/hgnn_unified_eval.py all --features emb --emb_model mxbai --epochs 30 \
#       --report_gran role --frameworks mdagents dylan clinical_agent clinical_agent5 \
#       --json_out ours_fw.json --pooled_out ours_pooled.json
#   (联合训练同理:python ours/train_hgnn.py joint --frameworks dylan mdagents ...)
# med-SFT:见 §3.3(--agent_key role --json_out medsft_fw.json --pooled_out medsft_pooled.json)
#   AEGIS-SFT-OOD:走 evaluate-v3.py(--agent_key role)后手工转同格式

# 合并成框架相关主表(后面的文件在键冲突时覆盖前面的):
python baselines/make_main_table.py --in set_metrics.json pointwise.json medsft_fw.json ours_fw.json \
    --out_tex docs/table_main.tex
# --metric macro 可切换为 Macro-F1
```
- **粒度**:全部 role(见 §3 的粒度统一说明)。ours 用 `--report_gran role`、med-SFT 用
  `--agent_key role`、Who&When 固定 role,三者同口径可比。
- 行顺序/显示名在 `make_main_table.py` 的 `NAME_MAP`/`METHOD_ORDER` 里定义;
  ours 行会自动前置一条 \midrule 与基线分隔、并加粗方法名。
- Step 列:集合方法用其 step_acc;pointwise 无 step 预测 → 显示 "--"。

### 5e. 生成框架无关主表(表头不分框架=合并池,LaTeX)📄

不细分框架:五框架 test 合并成一个池(n=1641),每方法一行、四指标各一个总数。

```bash
# 方式1(推荐,评测时直接输出正确池化):eval_set_unified.py 加 --pooled_out
python baselines/whowhen/eval_set_unified.py --backend openai ... \
    --out set_metrics.json --pooled_out ww_pooled.json
# 方式2(从已有 set_metrics.json 精确重构池化——gold计数确定性可复原TP/FP/FN):
#   见 baselines/reconstruct_pooled.py(读 set_metrics.json + 数据集 -> ww_pooled.json)

# 生成框架无关表(合并所有方法的 pooled json,全部 role 粒度)
python baselines/make_agnostic_table.py \
    --in ww_pooled.json medsft_pooled.json ours_pooled.json \
    --out_tex docs/table_agnostic_main.tex
```
**关键:池化 Micro-F1 必须由累加 TP/FP/FN 算,不能平均各框架 F1**(否则小框架被过度加权、
数值错误)。`--pooled_out` 内部拼接所有框架的预测/真值集合后一次性 compute_metrics,保证正确;
reconstruct 脚本利用"gold 对数可从数据集确定性复原"精确反解,与直接池化等价。

### 5f. 指标计算公式(两张表通用)📐

所有指标的基本单元:每条轨迹归约成一组 (agent, FM) 对的集合,预测集 P_i、真值集 G_i。
**两张表指标定义完全相同,唯一区别是累加 TP/FP/FN 的范围**:框架相关表=单框架,
框架无关表=五框架合并池(n=1641)。

**投影到三层次**(以 agent 层为例,error 层只留 FM 码、pair 层留完整对):
  TP_i = |P_i^ag ∩ G_i^ag|,  FP_i = |P_i^ag \ G_i^ag|,  FN_i = |G_i^ag \ P_i^ag|
  (比较 agent 名前做 strip().lower() 归一化)

**Micro-F1**(先跨轨迹累加计数,再算一次):
  P_micro = ΣTP_i / Σ(TP_i+FP_i),  R_micro = ΣTP_i / Σ(TP_i+FN_i)
  F1_micro = 2·P_micro·R_micro / (P_micro+R_micro)
  - 框架相关表:Σ 只在该框架轨迹上;框架无关表:Σ 在全池 1641 条上。

**Macro-F1**(每个类=一个 agent名/FM码/对,单独累计算 F1 再无权平均):
  F1_macro = mean_c [ 2·TP_c / (2·TP_c + FP_c + FN_c) ]

**Step-Acc**(单点,不套 F1,因真值 when 是单个最早注入步):
  Step-Acc = (1/N) Σ 1[最早预测错误步 == 最早真值错误步];池化时 = Σ命中 / Σn。

**实例(单轨迹,来自 llm_debate 诊断)**:
  PRED: [(Agent 3, FM-3.1)]   GOLD: [(Agent 1 0, FM-2.1), (Aggregator 0, FM-3.2)]
  agent 层:TP=0(Agent 3 不在 gold),FP=1,FN=2 -> 该条贡献 0 命中、拉低 F1。
  模型对 llm_debate 每条都输出 Agent 3/FM-3.1(常数退化)-> ΣTP≈0 -> F1_micro≈7.0。

**实例(池化,来自 medsft_pooled.json)**:
  Agent: P_micro=60.084%, R_micro=25.019%
  F1 = 2·0.60084·0.25019 / (0.60084+0.25019) = 35.33 -> 表里 AEGIS-med-SFT 的 35.3。

**⚠️ 池化 ≠ 平均 F1**(用 all-at-once 五框架 Agent-F1 [59.2,64.4,50.1,34.8,47.2] 实测):
  简单平均=51.15,n加权平均F1=53.18,**正确池化(累加计数)=52.79** —— 三者都不同。
  F1 非线性,任何在 F1 层的平均都错;必须回到 TP/FP/FN 累加。这就是为什么框架无关表
  必须用 --pooled_out(或从 P/R+gold计数精确重构),不能拿框架相关表的 F1 去合并。

---

## 6. 结果汇总(论文表格与口径)

**主表(统一口径,角色粒度,固定 test-set)** — 列:Agent/Error/Pair × mi/ma:
| 方法 | 来源命令 |
|---|---|
| Pointwise | §1.1 |
| GraphTracer(结构核心) / AgentTrace | §1.2/1.3(仅 agent-hit,pair 列 N/A)|
| Who&When ×3 | §5(agent-acc;pair 列 N/A)|
| ECHO | §5b(agent-acc + step Top-1;pair 列 N/A)|
| FAMAS | §5c(agent-hit + step Top-1/3;pair 列 N/A)|

### 已出数汇总（固定 test 集，五框架）
Pointwise 统一口径（Agent-mi/ma, Error-mi/ma, Pair-mi/ma）：
| 框架 | Agent-mi | Agent-ma | Error-mi | Error-ma | Pair-mi | Pair-ma | n |
|---|---|---|---|---|---|---|---|
| mdagents | 84.6 | 52.8 | 52.9 | 52.0 | 49.6 | 39.2 | 300 |
| dylan | 76.6 | 76.1 | 56.8 | 59.0 | 44.5 | 40.3 | 337 |
| llm_debate | 72.3 | 67.5 | 33.5 | 32.8 | 20.8 | 16.6 | 585 |
| clinical_agent | 74.5 | 64.0 | 60.4 | 51.4 | 58.0 | 41.6 | 105 |

确定性基线（agent-hit@1 / step Top-1 / step Top-3）：
| 方法 | mdagents | dylan | llm_debate | clinical_agent |
|---|---|---|---|---|
| GraphTracer(结构核心) | .983/.147/.293 | .457/.083/.338 | .282/.060/.320 | .248/.019/.362 |
| AgentTrace | .680/.680/.930 | .409/.270/.875 | .309/.150/.839 | .600/.600/1.000 |
| FAMAS(variant谱) | .685/.084/.500 | .395/.104/.365 | .212/.053/.388 | .312/.198/.250 |

**平凡基线对照（无模型，必看）** clinical_agent 上：
「永远猜第一步」= agent .600 / step .600；「永远猜最后一步」= agent .657 / step .000。
→ **AgentTrace 的 .600/.600 与前者完全重合**，说明它在该框架上等价于位置先验；
我们的方法（agent .829 / step .676）是唯一显著超越平凡基线的。建议在论文中保留此对照行。
| AEGIS-SFT (OOD) | §4 |
| AEGIS-med-SFT (in-domain) | §3.3 |
| **MedHyperTrace (ours)** | §2.2(取 role 行)|

**粒度统一**:两张主表全部 role 粒度(见 §3 说明)。mdagents 专家名细化后(§6b),
role 与 instance 已几乎等价,不再单列实例粒度副表;若确需实例级,仅 ours 与 med-SFT
结构上支持(其余方法结构上只能 role),但当前论文口径统一 role。

**step 子表(最早错误步 Top-1/Top-3)**:ours、pointwise、GraphTracer、AgentTrace、
Who&When、med-SFT-with_step(仅 Top-1);AEGIS-SFT-no_step = N/A。
**注意**:所有 step 数字口径相同(earliest_error_turn),可直接同列比较。

**消融表**:§2.3 五行 + §2.4 joint/OOD。

## 6b. Agent 身份细化(mdagents 专属,可扩展)🔧

**问题**:mdagents 的 5 个专家在数据里 `agent_name` 全叫 `Expert`,真实身份(Breast
Radiologist 等)藏在 `phase='expert_answer/<专家名>'` 里。不处理的话,所有方法在 mdagents
上都无法区分 5 个专家,归因、render 给 LLM 看的轨迹、gold 标签全被压成一个 `Expert`。

**处理**:`common/data.py` 有一个**每框架显式注册表** `_AGENT_REFINERS`:
- 目前只有 mdagents 一个 refiner(从 phase 取 `/` 后的专家名);
- 其他四框架**无条目 → 不细化**(agent_name 本就是真实身份);
- gold 标签通过 `orig_agent_name`(细化前的原名)精确对齐,不会错位。

**接入新框架时**:不要假设新框架和 mdagents 同款(phase 带 `/`)——身份藏在哪是**每个
框架自己的数据约定**,没有可靠的通用检测。做法:先**实际检查该框架数据**确认身份在哪个字段,
再在 `_AGENT_REFINERS` 里加一条 `"新框架名": refiner_fn`,`refiner_fn(raw_step, base_name)`
返回细化后的名字。没加条目的框架默认不动,安全。

**注意**:mdagents 的 agent 身份已变(专家名),所以 **mdagents 的旧结果(set_metrics/
med-SFT/ours)全部作废需重跑**;其他四框架旧结果仍有效。

## 7. 已知坑
- **不要**加 `--use_cot` 评你的 SFT(训练目标是直接 JSON)。
- evaluate-v3.py 的 `sys.path` 指向 src/,平铺仓库需改。
- Windows:路径用 `$env:MHT_DATA_DIR`;代码内部全用 os.path,无 posix 硬编码。
- dhg 库 wheel 在 py3.12 构建失败;`--backbone standard` 即为其 HGNNPConv 等价实现。
- llm_debate 有 ~17% 轨迹存在 planned-but-not-applied 标签坑,已在数据层处理
  (agent/mode 以 multi_injection_info 为准),无需手工干预。
- CPU 短训参考数(dylan@6ep):v2 全开 step Top-1≈0.70;去结构特征≈0.55;
  GPU 长训数字应显著更好,以 GPU 结果为准。
