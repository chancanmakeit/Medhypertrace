# MAFA evaluation · subset=dev · source=llm · rows=20
labels `results/human_like_eval/labels_v1.jsonl` sha256 f0ccf787c569 · split 916fee301529

## defect · all (rows=20)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 9/20 | 12/20 | 8/20 | 14/19 | 0.414 (15) | 0.349 |
| first_step | 14/20 | 14/20 | 11/20 | 15/20 | - | - |
| last_step | 0/20 | 18/20 | 0/20 | 1/20 | - | - |
| always_none | - | - | 0/20 | - | - | - |
| structure_prior | 14/20 | 14/20 | 11/20 | 15/20 | 0.395 (15) | - |
| mafa_primary | 18/20 | 20/20 | 17/20 | 17/20 | 0.845 (15) | 0.759 |
| mafa_secondary | 15/20 | 19/20 | 12/20 | 13/16 | 0.727 (15) | 0.319 |

## defect · no_leak (rows=20)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 9/20 | 12/20 | 8/20 | 14/19 | 0.414 (15) | 0.349 |
| first_step | 14/20 | 14/20 | 11/20 | 15/20 | - | - |
| last_step | 0/20 | 18/20 | 0/20 | 1/20 | - | - |
| always_none | - | - | 0/20 | - | - | - |
| structure_prior | 14/20 | 14/20 | 11/20 | 15/20 | 0.395 (15) | - |
| mafa_primary | 18/20 | 20/20 | 17/20 | 17/20 | 0.845 (15) | 0.759 |
| mafa_secondary | 15/20 | 19/20 | 12/20 | 13/16 | 0.727 (15) | 0.319 |

## defect · fw=clinical_agent (rows=6)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/6 | 2/6 | 2/6 | 5/5 | 0.369 (6) | 0.114 |
| first_step | 1/6 | 1/6 | 1/6 | 5/6 | - | - |
| last_step | 0/6 | 6/6 | 0/6 | 0/6 | - | - |
| always_none | - | - | 0/6 | - | - | - |
| structure_prior | 1/6 | 1/6 | 1/6 | 5/6 | 0.384 (6) | - |
| mafa_primary | 6/6 | 6/6 | 6/6 | 6/6 | 0.935 (6) | 0.737 |
| mafa_secondary | 5/6 | 6/6 | 5/6 | 5/6 | 0.804 (6) | 0.412 |

## defect · fw=dylan (rows=6)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/6 | 3/6 | 1/6 | 2/6 | 0.400 (5) | 0.432 |
| first_step | 5/6 | 5/6 | 2/6 | 2/6 | - | - |
| last_step | 0/6 | 5/6 | 0/6 | 1/6 | - | - |
| always_none | - | - | 0/6 | - | - | - |
| structure_prior | 5/6 | 5/6 | 2/6 | 2/6 | 0.333 (5) | - |
| mafa_primary | 4/6 | 6/6 | 3/6 | 3/6 | 0.867 (5) | 0.917 |
| mafa_secondary | 5/6 | 5/6 | 2/6 | 2/2 | 0.667 (5) | 0.0 |

## defect · fw=mdagents (rows=8)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 5/8 | 7/8 | 5/8 | 7/8 | 0.500 (4) | 0.486 |
| first_step | 8/8 | 8/8 | 8/8 | 8/8 | - | - |
| last_step | 0/8 | 7/8 | 0/8 | 0/8 | - | - |
| always_none | - | - | 0/8 | - | - | - |
| structure_prior | 8/8 | 8/8 | 8/8 | 8/8 | 0.487 (4) | - |
| mafa_primary | 8/8 | 8/8 | 8/8 | 8/8 | 0.683 (4) | 0.696 |
| mafa_secondary | 5/8 | 8/8 | 5/8 | 6/8 | 0.688 (4) | 0.364 |

## defect · split=faulty (rows=20)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 9/20 | 12/20 | 8/20 | 14/19 | 0.414 (15) | 0.349 |
| first_step | 14/20 | 14/20 | 11/20 | 15/20 | - | - |
| last_step | 0/20 | 18/20 | 0/20 | 1/20 | - | - |
| always_none | - | - | 0/20 | - | - | - |
| structure_prior | 14/20 | 14/20 | 11/20 | 15/20 | 0.395 (15) | - |
| mafa_primary | 18/20 | 20/20 | 17/20 | 17/20 | 0.845 (15) | 0.759 |
| mafa_secondary | 15/20 | 19/20 | 12/20 | 13/16 | 0.727 (15) | 0.319 |
