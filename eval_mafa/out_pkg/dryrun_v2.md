# MAFA evaluation · subset=dev · source=llm · rows=19
labels `results/human_like_eval_v2/labels_v2.jsonl` sha256 2a098da62899 · split 916fee301529

## defect · all (rows=19)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 6/14 | 7/15 | 7/19 | 8/13 | 0.553 (14) | 0.167 |
| first_step | 6/14 | 6/15 | 5/19 | 6/14 | - | - |
| last_step | 1/14 | 10/15 | 1/19 | 2/14 | - | - |
| always_none | - | - | 5/19 | - | - | - |
| structure_prior | 7/14 | 8/15 | 6/19 | 7/14 | 0.480 (14) | - |
| mafa_primary | 12/14 | 13/15 | 15/19 | 11/12 | 0.844 (14) | 0.81 |
| mafa_secondary | 8/14 | 9/15 | 11/19 | 6/7 | 0.661 (14) | 0.343 |

## defect · no_leak (rows=12)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 6/10 | 6/11 | 5/12 | 5/9 | 0.571 (10) | 0.062 |
| first_step | 4/10 | 4/11 | 3/12 | 3/10 | - | - |
| last_step | 1/10 | 8/11 | 1/12 | 2/10 | - | - |
| always_none | - | - | 2/12 | - | - | - |
| structure_prior | 5/10 | 5/11 | 4/12 | 4/10 | 0.541 (10) | - |
| mafa_primary | 8/10 | 9/11 | 9/12 | 8/9 | 0.882 (10) | 0.759 |
| mafa_secondary | 5/10 | 6/11 | 6/12 | 4/5 | 0.675 (10) | 0.174 |

## defect · fw=clinical_agent (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/4 | 1/5 | 1/5 | 1/3 | 0.593 (5) | 0.0 |
| first_step | 0/4 | 0/5 | 0/5 | 0/4 | - | - |
| last_step | 0/4 | 3/5 | 0/5 | 0/4 | - | - |
| always_none | - | - | 1/5 | - | - | - |
| structure_prior | 0/4 | 0/5 | 0/5 | 0/4 | 0.561 (5) | - |
| mafa_primary | 4/4 | 5/5 | 4/5 | 4/4 | 0.967 (5) | 0.909 |
| mafa_secondary | 2/4 | 2/5 | 3/5 | 2/2 | 0.700 (5) | 0.222 |

## defect · fw=clinical_agent5 (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/2 | 2/2 | 2/5 | 2/2 | 0.917 (2) | 0.0 |
| first_step | 0/2 | 0/2 | 0/5 | 1/2 | - | - |
| last_step | 0/2 | 1/2 | 0/5 | 0/2 | - | - |
| always_none | - | - | 3/5 | - | - | - |
| structure_prior | 1/2 | 2/2 | 1/5 | 2/2 | 0.750 (2) | - |
| mafa_primary | 1/2 | 1/2 | 4/5 | 1/1 | 0.625 (2) | 0.5 |
| mafa_secondary | 0/2 | 0/2 | 3/5 | - | 0.500 (2) | 0.0 |

## defect · fw=dylan (rows=4)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/3 | 1/3 | 1/4 | 0/3 | 0.500 (3) | 0.0 |
| first_step | 1/3 | 1/3 | 0/4 | 0/3 | - | - |
| last_step | 1/3 | 3/3 | 1/4 | 2/3 | - | - |
| always_none | - | - | 1/4 | - | - | - |
| structure_prior | 1/3 | 1/3 | 0/4 | 0/3 | 0.250 (3) | - |
| mafa_primary | 2/3 | 2/3 | 3/4 | 2/3 | 0.861 (3) | 1.0 |
| mafa_secondary | 2/3 | 2/3 | 3/4 | 2/2 | 0.667 (3) | 0.4 |

## defect · fw=mdagents (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/5 | 3/5 | 3/5 | 5/5 | 0.362 (4) | 0.421 |
| first_step | 5/5 | 5/5 | 5/5 | 5/5 | - | - |
| last_step | 0/5 | 3/5 | 0/5 | 0/5 | - | - |
| always_none | - | - | 0/5 | - | - | - |
| structure_prior | 5/5 | 5/5 | 5/5 | 5/5 | 0.415 (4) | - |
| mafa_primary | 5/5 | 5/5 | 4/5 | 4/4 | 0.787 (4) | 0.762 |
| mafa_secondary | 4/5 | 5/5 | 2/5 | 2/3 | 0.688 (4) | 0.444 |

## defect · split=clean (rows=9)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/6 | 1/6 | 2/9 | 4/6 | 0.460 (6) | 0.25 |
| first_step | 2/6 | 2/6 | 2/9 | 3/6 | - | - |
| last_step | 1/6 | 3/6 | 1/9 | 1/6 | - | - |
| always_none | - | - | 3/9 | - | - | - |
| structure_prior | 2/6 | 3/6 | 2/9 | 3/6 | 0.335 (6) | - |
| mafa_primary | 5/6 | 5/6 | 7/9 | 4/5 | 0.847 (6) | 0.947 |
| mafa_secondary | 2/6 | 2/6 | 4/9 | 1/1 | 0.583 (6) | 0.429 |

## defect · split=faulty (rows=10)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 6/8 | 6/9 | 5/10 | 4/7 | 0.624 (8) | 0.083 |
| first_step | 4/8 | 4/9 | 3/10 | 3/8 | - | - |
| last_step | 0/8 | 7/9 | 0/10 | 1/8 | - | - |
| always_none | - | - | 2/10 | - | - | - |
| structure_prior | 5/8 | 5/9 | 4/10 | 4/8 | 0.588 (8) | - |
| mafa_primary | 7/8 | 8/9 | 8/10 | 7/7 | 0.842 (8) | 0.696 |
| mafa_secondary | 6/8 | 7/9 | 7/10 | 5/6 | 0.719 (8) | 0.286 |

## responsibility · all (rows=10)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/6 | 3/6 | 1/6 | 1/5 | 0.529 (6) | - |
| first_step | 1/6 | 1/6 | 0/6 | 0/6 | - | - |
| last_step | 1/6 | 5/6 | 1/6 | 2/6 | - | - |
| always_none | - | - | 0/6 | - | - | - |
| structure_prior | 2/6 | 2/6 | 1/6 | 1/6 | 0.454 (6) | - |
| mafa_primary | 3/6 | 3/6 | 3/6 | 3/5 | 0.735 (6) | - |
| mafa_secondary | 4/6 | 4/6 | 4/6 | 4/5 | 0.771 (6) | - |

## responsibility · no_leak (rows=8)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/6 | 3/6 | 1/6 | 1/5 | 0.529 (6) | - |
| first_step | 1/6 | 1/6 | 0/6 | 0/6 | - | - |
| last_step | 1/6 | 5/6 | 1/6 | 2/6 | - | - |
| always_none | - | - | 0/6 | - | - | - |
| structure_prior | 2/6 | 2/6 | 1/6 | 1/6 | 0.454 (6) | - |
| mafa_primary | 3/6 | 3/6 | 3/6 | 3/5 | 0.735 (6) | - |
| mafa_secondary | 4/6 | 4/6 | 4/6 | 4/5 | 0.771 (6) | - |

## responsibility · fw=clinical_agent (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/2 | 1/2 | 0/2 | 0/1 | 0.562 (2) | - |
| first_step | 0/2 | 0/2 | 0/2 | 0/2 | - | - |
| last_step | 0/2 | 1/2 | 0/2 | 0/2 | - | - |
| always_none | - | - | 0/2 | - | - | - |
| structure_prior | 0/2 | 0/2 | 0/2 | 0/2 | 0.562 (2) | - |
| mafa_primary | 2/2 | 2/2 | 2/2 | 2/2 | 0.812 (2) | - |
| mafa_secondary | 2/2 | 2/2 | 2/2 | 2/2 | 0.938 (2) | - |

## responsibility · fw=clinical_agent5 (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | - |
| first_step | 0/1 | 0/1 | 0/1 | 0/1 | - | - |
| last_step | 0/1 | 1/1 | 0/1 | 0/1 | - | - |
| always_none | - | - | 0/1 | - | - | - |
| structure_prior | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | - |
| mafa_primary | 0/1 | 0/1 | 0/1 | - | 0.500 (1) | - |
| mafa_secondary | 0/1 | 0/1 | 0/1 | - | 0.500 (1) | - |

## responsibility · fw=dylan (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/1 | 1/1 | 0/1 | 0/1 | 0.750 (1) | - |
| first_step | 1/1 | 1/1 | 0/1 | 0/1 | - | - |
| last_step | 0/1 | 1/1 | 0/1 | 1/1 | - | - |
| always_none | - | - | 0/1 | - | - | - |
| structure_prior | 1/1 | 1/1 | 0/1 | 0/1 | 0.500 (1) | - |
| mafa_primary | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | - |
| mafa_secondary | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | - |

## responsibility · fw=mdagents (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/2 | 0/2 | 0/2 | 0/2 | 0.150 (2) | - |
| first_step | 0/2 | 0/2 | 0/2 | 0/2 | - | - |
| last_step | 1/2 | 2/2 | 1/2 | 1/2 | - | - |
| always_none | - | - | 0/2 | - | - | - |
| structure_prior | 0/2 | 0/2 | 0/2 | 0/2 | 0.050 (2) | - |
| mafa_primary | 0/2 | 0/2 | 0/2 | 0/2 | 0.642 (2) | - |
| mafa_secondary | 1/2 | 1/2 | 1/2 | 1/2 | 0.625 (2) | - |

## responsibility_any · all (rows=10)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/8 | 3/8 | 1/8 | 2/6 | 0.493 (8) | - |
| first_step | 1/8 | 1/8 | 0/8 | 1/8 | - | - |
| last_step | 2/8 | 6/8 | 2/8 | 3/8 | - | - |
| always_none | - | - | 0/8 | - | - | - |
| structure_prior | 2/8 | 2/8 | 1/8 | 2/8 | 0.566 (8) | - |
| mafa_primary | 4/8 | 4/8 | 4/8 | 5/7 | 0.728 (8) | - |
| mafa_secondary | 4/8 | 4/8 | 4/8 | 4/5 | 0.703 (8) | - |

## responsibility_any · no_leak (rows=8)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/8 | 3/8 | 1/8 | 2/6 | 0.493 (8) | - |
| first_step | 1/8 | 1/8 | 0/8 | 1/8 | - | - |
| last_step | 2/8 | 6/8 | 2/8 | 3/8 | - | - |
| always_none | - | - | 0/8 | - | - | - |
| structure_prior | 2/8 | 2/8 | 1/8 | 2/8 | 0.566 (8) | - |
| mafa_primary | 4/8 | 4/8 | 4/8 | 5/7 | 0.728 (8) | - |
| mafa_secondary | 4/8 | 4/8 | 4/8 | 4/5 | 0.703 (8) | - |

## responsibility_any · fw=clinical_agent (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/3 | 1/3 | 0/3 | 0/1 | 0.575 (3) | - |
| first_step | 0/3 | 0/3 | 0/3 | 0/3 | - | - |
| last_step | 1/3 | 2/3 | 1/3 | 1/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 0/3 | 0/3 | 0/3 | 0/3 | 0.642 (3) | - |
| mafa_primary | 3/3 | 3/3 | 3/3 | 3/3 | 0.875 (3) | - |
| mafa_secondary | 2/3 | 2/3 | 2/3 | 2/2 | 0.792 (3) | - |

## responsibility_any · fw=clinical_agent5 (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | - |
| first_step | 0/1 | 0/1 | 0/1 | 0/1 | - | - |
| last_step | 0/1 | 1/1 | 0/1 | 0/1 | - | - |
| always_none | - | - | 0/1 | - | - | - |
| structure_prior | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | - |
| mafa_primary | 0/1 | 0/1 | 0/1 | - | 0.500 (1) | - |
| mafa_secondary | 0/1 | 0/1 | 0/1 | - | 0.500 (1) | - |

## responsibility_any · fw=dylan (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/1 | 1/1 | 0/1 | 0/1 | 0.750 (1) | - |
| first_step | 1/1 | 1/1 | 0/1 | 0/1 | - | - |
| last_step | 0/1 | 1/1 | 0/1 | 1/1 | - | - |
| always_none | - | - | 0/1 | - | - | - |
| structure_prior | 1/1 | 1/1 | 0/1 | 0/1 | 0.500 (1) | - |
| mafa_primary | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | - |
| mafa_secondary | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | - |

## responsibility_any · fw=mdagents (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/3 | 0/3 | 0/3 | 1/3 | 0.156 (3) | - |
| first_step | 0/3 | 0/3 | 0/3 | 1/3 | - | - |
| last_step | 1/3 | 2/3 | 1/3 | 1/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 0/3 | 0/3 | 0/3 | 1/3 | 0.367 (3) | - |
| mafa_primary | 0/3 | 0/3 | 0/3 | 1/3 | 0.567 (3) | - |
| mafa_secondary | 1/3 | 1/3 | 1/3 | 1/2 | 0.583 (3) | - |
