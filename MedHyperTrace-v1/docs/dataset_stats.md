# 数据集分析

## 1. 数据集规模(task-level split)

| framework | total | train | test | test% |
|---|--:|--:|--:|--:|
| mdagents | 1003 | 703 | 300 | 29.9% |
| dylan | 1062 | 725 | 337 | 31.7% |
| llm_debate | 1712 | 1127 | 585 | 34.2% |
| clinical_agent | 402 | 297 | 105 | 26.1% |
| clinical_agent5 | 1052 | 738 | 314 | 29.8% |
| **合计** | **5231** | **3590** | **1641** | **31.4%** |

## 2. 轨迹结构

| framework | 步数均/中/max | agent均 | 多故障% | 责任agent均 |
|---|--:|--:|--:|--:|
| mdagents | 7.0/7/7 | 7.0 | 91.2% | 3.96 |
| dylan | 9.1/10/10 | 4.0 | 100.0% | 2.00 |
| llm_debate | 7.0/7/7 | 4.0 | 100.0% | 2.01 |
| clinical_agent | 6.0/6/6 | 6.0 | 100.0% | 2.00 |
| clinical_agent5 | 5.0/5/5 | 5.0 | 100.0% | 2.35 |

## 3. 故障模式(MAST-14)分布

总注入 12857 次,覆盖 14/14 类。

| FM | count | share |
|---|--:|--:|
| FM-1.1 | 1271 | 9.9% |
| FM-1.2 | 931 | 7.2% |
| FM-1.3 | 929 | 7.2% |
| FM-1.4 | 1074 | 8.4% |
| FM-1.5 | 875 | 6.8% |
| FM-2.1 | 735 | 5.7% |
| FM-2.2 | 743 | 5.8% |
| FM-2.3 | 1208 | 9.4% |
| FM-2.4 | 917 | 7.1% |
| FM-2.5 | 684 | 5.3% |
| FM-2.6 | 939 | 7.3% |
| FM-3.1 | 767 | 6.0% |
| FM-3.2 | 1086 | 8.4% |
| FM-3.3 | 698 | 5.4% |

## 4. Agent 角色画像

| framework | 不同角色数 | 最常出错角色(次数) |
|---|--:|---|
| mdagents | 553 | Recruiter(680), Clinical Pharmacologist(383), Attending Physician(261) |
| dylan | 4 | Medical_Researcher(611), Pharmacologist(573), Physician(531) |
| llm_debate | 4 | Aggregator(1562), Agent 2(812), Agent 3(692) |
| clinical_agent | 6 | Planner(242), Reasoner(224), SafetyAgent(141) |
| clinical_agent5 | 5 | Reasoner(772), EfficacyAgent(629), EnrollmentAgent(482) |

## 5. 模态

| framework | 带图像轨迹数 | 模态 |
|---|--:|---|
| mdagents | 1003 | 多模态(含医学影像) |
| dylan | 0 | 纯文本 |
| llm_debate | 0 | 纯文本 |
| clinical_agent | 0 | 纯文本 |
| clinical_agent5 | 0 | 纯文本 |

## 6. 故障位置(最早注入错误步的归一化位置,0=开头 1=结尾)

| framework | 位置均值 | 位置中位 |
|---|--:|--:|
| mdagents | 0.08 | 0.00 |
| dylan | 0.09 | 0.06 |
| llm_debate | 0.54 | 0.33 |
| clinical_agent | 0.14 | 0.00 |
| clinical_agent5 | 0.35 | 0.25 |
