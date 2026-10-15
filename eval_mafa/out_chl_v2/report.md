# MAFA evaluation · subset=dev · source=llm · rows=39
labels `results/closest_human_like_eval_v2/labels_v2.jsonl` sha256 2fde4232a1ee · split 916fee301529

## defect · all (rows=39)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 6/21 | 16/29 | 10/39 | 8/18 | 0.478 (20) | 0.157 |
| first_step | 9/21 | 18/29 | 6/39 | 9/21 | - | - |
| last_step | 2/21 | 18/29 | 2/39 | 3/21 | - | - |
| always_none | - | - | 18/39 | - | - | - |
| structure_prior | 9/21 | 18/29 | 6/39 | 9/21 | 0.348 (20) | - |
| mafa_primary | 17/21 | 29/29 | 23/39 | 16/19 | 0.812 (20) | 0.732 |
| mafa_secondary | 16/21 | 25/29 | 25/39 | 11/12 | 0.692 (20) | 0.386 |

## defect · no_leak (rows=24)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 4/13 | 12/18 | 6/24 | 3/11 | 0.425 (10) | 0.14 |
| first_step | 5/13 | 11/18 | 3/24 | 4/13 | - | - |
| last_step | 2/13 | 15/18 | 2/24 | 2/13 | - | - |
| always_none | - | - | 11/24 | - | - | - |
| structure_prior | 5/13 | 11/18 | 3/24 | 4/13 | 0.369 (10) | - |
| mafa_primary | 9/13 | 18/18 | 12/24 | 9/12 | 0.804 (10) | 0.681 |
| mafa_secondary | 10/13 | 16/18 | 15/24 | 7/8 | 0.713 (10) | 0.368 |

## defect · fw=clinical_agent (rows=10)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/5 | 1/9 | 2/10 | 0/4 | 0.407 (9) | 0.0 |
| first_step | 0/5 | 0/9 | 0/10 | 0/5 | - | - |
| last_step | 0/5 | 5/9 | 0/10 | 0/5 | - | - |
| always_none | - | - | 5/10 | - | - | - |
| structure_prior | 0/5 | 0/9 | 0/10 | 0/5 | 0.435 (9) | - |
| mafa_primary | 5/5 | 9/9 | 5/10 | 5/5 | 0.829 (9) | 0.556 |
| mafa_secondary | 3/5 | 6/9 | 5/10 | 3/3 | 0.736 (9) | 0.429 |

## defect · fw=clinical_agent5 (rows=10)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/2 | 2/3 | 4/10 | 2/2 | 0.583 (3) | 0.0 |
| first_step | 0/2 | 1/3 | 0/10 | 2/2 | - | - |
| last_step | 0/2 | 0/3 | 0/10 | 0/2 | - | - |
| always_none | - | - | 8/10 | - | - | - |
| structure_prior | 0/2 | 1/3 | 0/10 | 2/2 | 0.278 (3) | - |
| mafa_primary | 2/2 | 3/3 | 7/10 | 2/2 | 0.917 (3) | 0.8 |
| mafa_secondary | 1/2 | 2/3 | 9/10 | 1/1 | 0.667 (3) | 0.0 |

## defect · fw=dylan (rows=9)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/5 | 7/7 | 3/9 | 0/3 | 0.569 (3) | 0.0 |
| first_step | 3/5 | 7/7 | 0/9 | 0/5 | - | - |
| last_step | 1/5 | 7/7 | 1/9 | 2/5 | - | - |
| always_none | - | - | 4/9 | - | - | - |
| structure_prior | 3/5 | 7/7 | 0/9 | 0/5 | 0.000 (3) | - |
| mafa_primary | 4/5 | 7/7 | 6/9 | 3/4 | 0.750 (3) | 0.727 |
| mafa_secondary | 4/5 | 7/7 | 6/9 | 2/3 | 0.667 (3) | 0.5 |

## defect · fw=mdagents (rows=10)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/9 | 6/10 | 1/10 | 6/9 | 0.490 (5) | 0.326 |
| first_step | 6/9 | 10/10 | 6/10 | 7/9 | - | - |
| last_step | 1/9 | 6/10 | 1/10 | 1/9 | - | - |
| always_none | - | - | 1/10 | - | - | - |
| structure_prior | 6/9 | 10/10 | 6/10 | 7/9 | 0.445 (5) | - |
| mafa_primary | 6/9 | 10/10 | 5/10 | 6/8 | 0.758 (5) | 0.811 |
| mafa_secondary | 8/9 | 10/10 | 5/10 | 5/5 | 0.642 (5) | 0.357 |

## defect · split=clean (rows=17)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/8 | 3/11 | 4/17 | 5/7 | 0.538 (11) | 0.154 |
| first_step | 4/8 | 6/11 | 3/17 | 5/8 | - | - |
| last_step | 0/8 | 2/11 | 0/17 | 1/8 | - | - |
| always_none | - | - | 9/17 | - | - | - |
| structure_prior | 4/8 | 6/11 | 3/17 | 5/8 | 0.317 (11) | - |
| mafa_primary | 8/8 | 11/11 | 11/17 | 7/7 | 0.837 (11) | 0.741 |
| mafa_secondary | 5/8 | 8/11 | 11/17 | 3/3 | 0.655 (11) | 0.333 |

## defect · split=faulty (rows=22)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 4/13 | 13/18 | 6/22 | 3/11 | 0.406 (9) | 0.16 |
| first_step | 5/13 | 12/18 | 3/22 | 4/13 | - | - |
| last_step | 2/13 | 16/18 | 2/22 | 2/13 | - | - |
| always_none | - | - | 9/22 | - | - | - |
| structure_prior | 5/13 | 12/18 | 3/22 | 4/13 | 0.387 (9) | - |
| mafa_primary | 9/13 | 18/18 | 12/22 | 9/12 | 0.782 (9) | 0.727 |
| mafa_secondary | 11/13 | 17/18 | 14/22 | 8/9 | 0.736 (9) | 0.41 |

## defect_any · all (rows=39)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 11/29 | 16/29 | 11/39 | 14/21 | 0.478 (20) | 0.157 |
| first_step | 16/29 | 18/29 | 15/39 | 18/29 | - | - |
| last_step | 2/29 | 18/29 | 0/39 | 0/29 | - | - |
| always_none | - | - | 10/39 | - | - | - |
| structure_prior | 15/29 | 18/29 | 14/39 | 17/29 | 0.348 (20) | - |
| mafa_primary | 23/29 | 29/29 | 25/39 | 20/25 | 0.812 (20) | 0.732 |
| mafa_secondary | 18/29 | 25/29 | 19/39 | 10/15 | 0.692 (20) | 0.386 |

## defect_any · no_leak (rows=24)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 9/18 | 12/18 | 7/24 | 7/12 | 0.425 (10) | 0.14 |
| first_step | 11/18 | 11/18 | 10/24 | 11/18 | - | - |
| last_step | 0/18 | 15/18 | 0/24 | 0/18 | - | - |
| always_none | - | - | 6/24 | - | - | - |
| structure_prior | 10/18 | 11/18 | 9/24 | 10/18 | 0.369 (10) | - |
| mafa_primary | 15/18 | 18/18 | 15/24 | 13/16 | 0.804 (10) | 0.681 |
| mafa_secondary | 12/18 | 16/18 | 11/24 | 6/10 | 0.713 (10) | 0.368 |

## defect_any · fw=clinical_agent (rows=10)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/9 | 1/9 | 0/10 | 0/6 | 0.407 (9) | 0.0 |
| first_step | 0/9 | 0/9 | 0/10 | 1/9 | - | - |
| last_step | 0/9 | 5/9 | 0/10 | 0/9 | - | - |
| always_none | - | - | 1/10 | - | - | - |
| structure_prior | 0/9 | 0/9 | 0/10 | 1/9 | 0.435 (9) | - |
| mafa_primary | 6/9 | 9/9 | 6/10 | 7/9 | 0.829 (9) | 0.556 |
| mafa_secondary | 4/9 | 6/9 | 5/10 | 5/6 | 0.736 (9) | 0.429 |

## defect_any · fw=clinical_agent5 (rows=10)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/3 | 2/3 | 3/10 | 2/2 | 0.583 (3) | 0.0 |
| first_step | 1/3 | 1/3 | 1/10 | 3/3 | - | - |
| last_step | 0/3 | 0/3 | 0/10 | 0/3 | - | - |
| always_none | - | - | 7/10 | - | - | - |
| structure_prior | 0/3 | 1/3 | 0/10 | 2/3 | 0.278 (3) | - |
| mafa_primary | 3/3 | 3/3 | 8/10 | 3/3 | 0.917 (3) | 0.8 |
| mafa_secondary | 2/3 | 2/3 | 8/10 | 1/1 | 0.667 (3) | 0.0 |

## defect_any · fw=dylan (rows=9)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 5/7 | 7/7 | 4/9 | 3/3 | 0.569 (3) | 0.0 |
| first_step | 5/7 | 7/7 | 4/9 | 4/7 | - | - |
| last_step | 2/7 | 7/7 | 0/9 | 0/7 | - | - |
| always_none | - | - | 2/9 | - | - | - |
| structure_prior | 5/7 | 7/7 | 4/9 | 4/7 | 0.000 (3) | - |
| mafa_primary | 4/7 | 7/7 | 2/9 | 1/4 | 0.750 (3) | 0.727 |
| mafa_secondary | 4/7 | 7/7 | 3/9 | 1/3 | 0.667 (3) | 0.5 |

## defect_any · fw=mdagents (rows=10)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 4/10 | 6/10 | 4/10 | 9/10 | 0.490 (5) | 0.326 |
| first_step | 10/10 | 10/10 | 10/10 | 10/10 | - | - |
| last_step | 0/10 | 6/10 | 0/10 | 0/10 | - | - |
| always_none | - | - | 0/10 | - | - | - |
| structure_prior | 10/10 | 10/10 | 10/10 | 10/10 | 0.445 (5) | - |
| mafa_primary | 10/10 | 10/10 | 9/10 | 9/9 | 0.758 (5) | 0.811 |
| mafa_secondary | 8/10 | 10/10 | 3/10 | 3/5 | 0.642 (5) | 0.357 |

## defect_any · split=clean (rows=17)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/11 | 3/11 | 3/17 | 6/9 | 0.538 (11) | 0.154 |
| first_step | 4/11 | 6/11 | 4/17 | 6/11 | - | - |
| last_step | 2/11 | 2/11 | 0/17 | 0/11 | - | - |
| always_none | - | - | 6/17 | - | - | - |
| structure_prior | 4/11 | 6/11 | 4/17 | 6/11 | 0.317 (11) | - |
| mafa_primary | 9/11 | 11/11 | 11/17 | 8/9 | 0.837 (11) | 0.741 |
| mafa_secondary | 6/11 | 8/11 | 10/17 | 4/4 | 0.655 (11) | 0.333 |

## defect_any · split=faulty (rows=22)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 10/18 | 13/18 | 8/22 | 8/12 | 0.406 (9) | 0.16 |
| first_step | 12/18 | 12/18 | 11/22 | 12/18 | - | - |
| last_step | 0/18 | 16/18 | 0/22 | 0/18 | - | - |
| always_none | - | - | 4/22 | - | - | - |
| structure_prior | 11/18 | 12/18 | 10/22 | 11/18 | 0.387 (9) | - |
| mafa_primary | 14/18 | 18/18 | 14/22 | 12/16 | 0.782 (9) | 0.727 |
| mafa_secondary | 12/18 | 17/18 | 9/22 | 6/11 | 0.736 (9) | 0.41 |

## responsibility · all (rows=22)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/9 | 3/9 | 0/9 | 0/7 | 0.315 (7) | - |
| first_step | 2/9 | 2/9 | 0/9 | 0/9 | - | - |
| last_step | 3/9 | 8/9 | 3/9 | 3/9 | - | - |
| always_none | - | - | 0/9 | - | - | - |
| structure_prior | 2/9 | 2/9 | 0/9 | 0/9 | 0.280 (7) | - |
| mafa_primary | 5/9 | 5/9 | 4/9 | 4/8 | 0.708 (7) | - |
| mafa_secondary | 6/9 | 6/9 | 5/9 | 5/7 | 0.792 (7) | - |

## responsibility · no_leak (rows=20)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/9 | 3/9 | 0/9 | 0/7 | 0.315 (7) | - |
| first_step | 2/9 | 2/9 | 0/9 | 0/9 | - | - |
| last_step | 3/9 | 8/9 | 3/9 | 3/9 | - | - |
| always_none | - | - | 0/9 | - | - | - |
| structure_prior | 2/9 | 2/9 | 0/9 | 0/9 | 0.280 (7) | - |
| mafa_primary | 5/9 | 5/9 | 4/9 | 4/8 | 0.708 (7) | - |
| mafa_secondary | 6/9 | 6/9 | 5/9 | 5/7 | 0.792 (7) | - |

## responsibility · fw=clinical_agent (rows=6)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/3 | 1/3 | 0/3 | 0/2 | 0.542 (3) | - |
| first_step | 0/3 | 0/3 | 0/3 | 0/3 | - | - |
| last_step | 0/3 | 2/3 | 0/3 | 0/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 0/3 | 0/3 | 0/3 | 0/3 | 0.542 (3) | - |
| mafa_primary | 3/3 | 3/3 | 3/3 | 3/3 | 0.875 (3) | - |
| mafa_secondary | 3/3 | 3/3 | 3/3 | 3/3 | 0.903 (3) | - |

## responsibility · fw=clinical_agent5 (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | - | - | - | - | - | - |
| first_step | - | - | - | - | - | - |
| last_step | - | - | - | - | - | - |
| always_none | - | - | - | - | - | - |
| structure_prior | - | - | - | - | - | - |
| mafa_primary | - | - | - | - | - | - |
| mafa_secondary | - | - | - | - | - | - |

## responsibility · fw=dylan (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/3 | 2/3 | 0/3 | 0/2 | 0.333 (1) | - |
| first_step | 2/3 | 2/3 | 0/3 | 0/3 | - | - |
| last_step | 1/3 | 3/3 | 1/3 | 1/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 2/3 | 2/3 | 0/3 | 0/3 | 0.000 (1) | - |
| mafa_primary | 2/3 | 2/3 | 1/3 | 1/2 | 1.000 (1) | - |
| mafa_secondary | 2/3 | 2/3 | 1/3 | 1/2 | 1.000 (1) | - |

## responsibility · fw=mdagents (rows=6)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/3 | 0/3 | 0/3 | 0/3 | 0.083 (3) | - |
| first_step | 0/3 | 0/3 | 0/3 | 0/3 | - | - |
| last_step | 2/3 | 3/3 | 2/3 | 2/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 0/3 | 0/3 | 0/3 | 0/3 | 0.111 (3) | - |
| mafa_primary | 0/3 | 0/3 | 0/3 | 0/3 | 0.444 (3) | - |
| mafa_secondary | 1/3 | 1/3 | 1/3 | 1/2 | 0.611 (3) | - |

## responsibility_any · all (rows=22)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 6/18 | 8/18 | 3/18 | 6/12 | 0.466 (14) | - |
| first_step | 4/18 | 5/18 | 3/18 | 7/18 | - | - |
| last_step | 0/18 | 16/18 | 0/18 | 0/18 | - | - |
| always_none | - | - | 0/18 | - | - | - |
| structure_prior | 5/18 | 6/18 | 4/18 | 8/18 | 0.437 (14) | - |
| mafa_primary | 8/18 | 11/18 | 5/18 | 10/16 | 0.533 (14) | - |
| mafa_secondary | 9/18 | 12/18 | 6/18 | 7/11 | 0.682 (14) | - |

## responsibility_any · no_leak (rows=20)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 6/17 | 7/17 | 3/17 | 6/11 | 0.466 (14) | - |
| first_step | 4/17 | 4/17 | 3/17 | 7/17 | - | - |
| last_step | 0/17 | 15/17 | 0/17 | 0/17 | - | - |
| always_none | - | - | 0/17 | - | - | - |
| structure_prior | 5/17 | 5/17 | 4/17 | 8/17 | 0.437 (14) | - |
| mafa_primary | 8/17 | 10/17 | 5/17 | 9/15 | 0.533 (14) | - |
| mafa_secondary | 9/17 | 11/17 | 6/17 | 6/10 | 0.682 (14) | - |

## responsibility_any · fw=clinical_agent (rows=6)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/6 | 1/6 | 0/6 | 0/3 | 0.498 (6) | - |
| first_step | 0/6 | 0/6 | 0/6 | 0/6 | - | - |
| last_step | 0/6 | 5/6 | 0/6 | 0/6 | - | - |
| always_none | - | - | 0/6 | - | - | - |
| structure_prior | 0/6 | 0/6 | 0/6 | 0/6 | 0.539 (6) | - |
| mafa_primary | 4/6 | 6/6 | 4/6 | 4/6 | 0.764 (6) | - |
| mafa_secondary | 4/6 | 5/6 | 4/6 | 4/5 | 0.771 (6) | - |

## responsibility_any · fw=clinical_agent5 (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/1 | 0/1 | 0/1 | - | 0.750 (1) | - |
| first_step | 0/1 | 0/1 | 0/1 | 0/1 | - | - |
| last_step | 0/1 | 0/1 | 0/1 | 0/1 | - | - |
| always_none | - | - | 0/1 | - | - | - |
| structure_prior | 1/1 | 1/1 | 1/1 | 1/1 | 0.750 (1) | - |
| mafa_primary | 0/1 | 0/1 | 0/1 | 0/1 | 0.375 (1) | - |
| mafa_secondary | 0/1 | 0/1 | 0/1 | - | 0.500 (1) | - |

## responsibility_any · fw=dylan (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 4/5 | 5/5 | 2/5 | 2/3 | 0.333 (1) | - |
| first_step | 4/5 | 5/5 | 3/5 | 3/5 | - | - |
| last_step | 0/5 | 5/5 | 0/5 | 0/5 | - | - |
| always_none | - | - | 0/5 | - | - | - |
| structure_prior | 4/5 | 5/5 | 3/5 | 3/5 | 0.000 (1) | - |
| mafa_primary | 4/5 | 5/5 | 1/5 | 2/3 | 1.000 (1) | - |
| mafa_secondary | 4/5 | 5/5 | 1/5 | 2/3 | 1.000 (1) | - |

## responsibility_any · fw=mdagents (rows=6)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/6 | 2/6 | 1/6 | 4/6 | 0.408 (6) | - |
| first_step | 0/6 | 0/6 | 0/6 | 4/6 | - | - |
| last_step | 0/6 | 6/6 | 0/6 | 0/6 | - | - |
| always_none | - | - | 0/6 | - | - | - |
| structure_prior | 0/6 | 0/6 | 0/6 | 4/6 | 0.356 (6) | - |
| mafa_primary | 0/6 | 0/6 | 0/6 | 4/6 | 0.250 (6) | - |
| mafa_secondary | 1/6 | 2/6 | 1/6 | 1/3 | 0.569 (6) | - |
