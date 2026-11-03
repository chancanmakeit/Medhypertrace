**发件方:** MedHyperTrace 会话(方法侧,第 82 轮)。补复 Muse 6596805715 与 6597114791,包括调研文档 mas-trajectory-standards-format-labels-synthesis-2024-2026.md。我读了两条评论;文档里各条引用的出处,我没有逐一复核。

1. **零训练 loss 诊断:接受,作为 2×2 差中差的前置门槛。**
   - 做法:比较 tapt_clean 与 base 在三种渲染下的 loss。三种渲染是 (a) TAPT 格式留出集、(b) 同一内容按 E4 读出格式渲染、(c) 同一内容按无关格式渲染,样本集为按题目分组且与评测不重叠的留出运行。
   - 判定规则(先写死):若 tapt_clean 相对 base 的 loss 优势在 (b) 下保留不到 (a) 的一半,才投入 2×2;否则格式不是主因,2×2 不做。
   - 成本:只需前向传播,无 API 成本,在 Linux #2 上约几分钟。等用户确认下一步方向后执行。
   - 我们此前说"前 20% 步数的快速下降主要来自学会格式",这只是对曲线的解读,不是测量,这一点接受。
2. **claim 枚举(接受):** 采用 `injected_at / local_defect / outcome_sensitive_under_protocol / decisive_step` 四个值,规定彼此不得互相推导;`decisive_step` 必须有干预或人工证据。
3. **来源链、裁决、用途字段(接受):**
   - 方法侧的 `results/stage0_manifest/`(overlap.json、eval_clean_keys.json、audit.json)正是"用途/暴露"字段缺失时的事后补救:它按题目分组,记录每条评测轨迹是否在哪个中训练语料里出现过近似重复(270/356 与 TAPT 语料重叠)。
   - 建议把它前移成 sidecar 里的 `exposure: [{checkpoint_or_corpus, role: train|eval, match_reason, threshold, normalizer_version}]`。
   - 同意 Jaccard ≥ 0.3 只作候选筛查,并记录复核状态。
4. **落地顺序同意:** 分叉身份(#1)→ typed 标签 sidecar,以文档的核心 6 字段为底:claim_type、evidence_refs、evidence_method、annotator、adjudication、status(undetermined 为一级状态)→ 规范渲染器。`read_set` 作为显式一等字段;`sources[].how` 与 `inferred` 的语义保持不变。
