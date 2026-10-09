# MedHyperTrace Overview 图 — 生图 Prompt（GPT-Image / Nano Banana）

> ⚠️ 现实提醒：扩散类生图模型**画不准精确文字标签**（会糊/拼错）。建议：用下面的
> Prompt 生成**整体布局 + 配色 + 视觉风格**，把文字当占位；最终的字、公式、箭头标签
> 在 Illustrator / draw.io / PPT / Excalidraw 里矢量补齐。这样才是投稿级质量。

---

## ✅ 版本 A：主 Prompt（英文，直接粘给 GPT-Image / Nano Banana）

```
A clean, modern scientific overview figure for a machine-learning research paper,
horizontal left-to-right pipeline layout, 16:9, on a white background with a soft
academic color palette (muted teal, slate blue, warm coral accent, light gray panels).
Flat vector illustration style, thin rounded-rectangle panels with subtle drop shadows,
clear directional arrows between stages, generous whitespace, no photorealism,
no clutter. Four labeled stages arranged in a row:

STAGE 1 (left) — "Medical multi-agent trajectory": a vertical stack of chat-bubble
rows representing a failed medical consultation among AI agents. Small circular agent
avatars in different colors labeled like Recruiter, Expert, Aggregator. A few bubbles
are highlighted in coral to indicate injected errors. A tiny medical cross icon and a
small X-ray/thumbnail icon hint at the medical domain.

STAGE 2 — "Heterogeneous hypergraph construction": the central visual highlight.
Show three distinct node types drawn as different shapes and colors: small circles =
step nodes, larger rounded squares = agent nodes, diamonds = phase/subtask nodes.
Critically, draw HYPEREDGES as translucent colored blobs/enclosures that each wrap
AROUND MULTIPLE nodes at once (an n-ary relation, NOT simple pairwise lines): one
teal blob enclosing several step nodes plus one aggregator node (a "consensus /
aggregation" hyperedge), one blue blob enclosing an agent node with all its step
nodes (a "role" hyperedge), one coral blob enclosing steps that share consumed
context (a "context-inheritance" hyperedge), one gray blob enclosing a subtask group
(a "phase" hyperedge). Make the enclosing blobs the eye-catching element that
distinguishes this from an ordinary node-and-line graph.

STAGE 3 — "Hypergraph neural network": a compact stack of 2–3 rounded layer bands
labeled as message-passing layers, with small bidirectional arrows suggesting
node -> hyperedge -> node propagation and a subtle attention-weight glow on one
hyperedge. Keep it schematic and tidy.

STAGE 4 (right) — "Three-level attribution output": three stacked small result cards,
one above another, each with a distinct icon: (a) "Agent" card highlighting which
agent avatar is faulty, (b) "Error mode" card showing a small tag/label chip, (c)
"Step" card showing a timeline with one step marked. Use the same coral accent to
mark the culprit consistently across the three cards.

Consistent color language across the whole figure: coral = error/culprit, teal =
aggregation hyperedge, blue = agent/role, gray = phase. Balanced composition,
publication-quality, minimalist, ICLR/NeurIPS poster aesthetic. Leave clear empty
label areas above each stage for text to be added later.
```

---

## ✅ 版本 B：更"控制感"的结构化 Prompt（若模型支持长指令 / 你想分块生成）

逐模块描述，适合让模型更听话，或你照此在矢量工具里精修：

```
Scientific paper overview diagram, vector flat style, white background, 4 stages in a
horizontal pipeline separated by rightward arrows. Muted academic palette.

[Panel 1 | Input] Title area reads "Failed medical MAS trajectory". Below: 6–8
stacked message bubbles, each prefixed by a small colored agent avatar. Two bubbles
tinted coral-red = injected errors. Domain hint: a small caduceus icon and a tiny
medical-image thumbnail in the corner.

[Panel 2 | Hypergraph — MAKE THIS THE LARGEST, CENTERPIECE] Title "Heterogeneous
hypergraph". Draw a graph where nodes have THREE shapes:
  - small circles = step nodes (light blue)
  - rounded squares = agent nodes (blue)
  - diamonds = phase nodes (gray)
Then overlay FOUR semi-transparent rounded enclosures, each surrounding a DIFFERENT
GROUP OF MULTIPLE NODES (these are hyperedges — the key novelty; they must visibly
enclose 3+ nodes, not connect just two):
  - teal enclosure over several step-circles + one agent-square  → label slot "E_agg"
  - blue enclosure over one agent-square + its step-circles      → label slot "E_role"
  - coral enclosure over a chain of step-circles                 → label slot "E_ctx"
  - gray enclosure over a subtask cluster                        → label slot "E_phase"
Add a small magnifier/attention glow on the teal enclosure.

[Panel 3 | Model] Title "Hypergraph neural network (HGNN)". Three stacked rounded
horizontal bands (layers). Between them, small paired arrows curving out to a little
hyperedge glyph and back, illustrating node→edge→node message passing.

[Panel 4 | Output] Title "Three-level failure attribution". Three small stacked cards:
  - "Agent-level" : a row of agent avatars, one circled in coral
  - "Mode-level"  : a label chip (e.g., a colored tag) 
  - "Step-level"  : a horizontal timeline of dots, one dot marked coral
All coral marks refer to the same culprit for visual consistency.

Style: minimalist, thin strokes, rounded corners, soft shadows, lots of whitespace,
NeurIPS/ICLR figure aesthetic, 16:9, high resolution, no photorealism.
```

---

## 关键视觉要点（无论用哪版，都要盯住这几点，否则图会退化成"普通图"）

1. **超边一定要画成"包住多个节点的半透明色块/圈"**，而不是节点间的连线。这是我们
   和 CHIEF/GraphTracer(二元图) 的核心区别，也是 HyperRAG "n 元关系"启发的落点。
   一旦模型把它画成两两连线，视觉卖点就没了——这是最容易出错、最需要盯的地方。
2. **三类节点用三种形状**（圆=step、方=agent、菱=phase），别只靠颜色区分。
3. **红/珊瑚色 = 错误/责任方**，从输入(被注入的 bubble) → 超图(可疑节点) →
   输出(三张卡片里被标记的 agent/mode/step) **一路保持同一个红**，形成"错误如何
   被追踪"的视觉叙事线。
4. **第 2 块(超图)要最大、居中**，是全图的视觉重心。
5. **医学暗示**用小图标点到即止（听诊器/医疗十字/影像缩略图），别喧宾夺主。

## 建议的文字标签（生图后你自己矢量补上）

- 四阶段标题：`Failed medical MAS trajectory` → `Heterogeneous hypergraph` →
  `Hypergraph neural network` → `Three-level attribution`
- 四类超边：`E_agg (consensus)`、`E_role`、`E_ctx (context inheritance)`、`E_phase`
- 输出三级：`Agent-level (who)`、`Mode-level (which MAST error)`、`Step-level (when)`
- 可选点睛副标题：`n-ary relations that binary graphs cannot express`

## 负向提示词（Negative prompt，若工具支持）

```
photorealistic, 3D render, cluttered, busy background, dark background, neon,
hand-drawn sketch, low-res, watermark, distorted tiny text, pairwise-only edges,
tangled lines, overlapping unreadable labels
```
```
```
