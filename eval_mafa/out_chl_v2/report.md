# MAFA evaluation · subset=dev · source=llm · rows=39
labels `results/closest_human_like_eval_v2/labels_v2.jsonl` sha256 67aaee8b41d7 · split 916fee301529

Every number is computed within ONE taxonomy: MAST and MedAgentAudit labels are different label definitions (and the same trace can appear under both), so rows are never pooled across them. MedHyperTrace is trained on MAST-coded synthetic data only and has no MedAgentAudit code head.

# MAST (rows=20)

## MAST · defect · all (rows=20)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/13 | 7/13 | 3/20 | 4/11 | 0.474 (9) | 0.157 |
| first_step | 6/13 | 8/13 | 5/20 | 5/13 | - | - |
| last_step | 1/13 | 8/13 | 1/20 | 1/13 | - | - |
| always_none | - | - | 7/20 | - | - | - |
| structure_prior | 6/13 | 8/13 | 5/20 | 5/13 | 0.332 (9) | - |
| mafa_primary | 12/13 | 13/13 | 17/20 | 12/12 | 0.852 (9) | 0.766 |
| mafa_secondary | 10/13 | 11/13 | 14/20 | 7/7 | 0.759 (9) | 0.474 |

## MAST · defect · no_leak (rows=13)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/9 | 6/9 | 1/13 | 2/7 | 0.399 (6) | 0.14 |
| first_step | 4/9 | 5/9 | 3/13 | 3/9 | - | - |
| last_step | 1/9 | 7/9 | 1/13 | 1/9 | - | - |
| always_none | - | - | 4/13 | - | - | - |
| structure_prior | 4/9 | 5/9 | 3/13 | 3/9 | 0.290 (6) | - |
| mafa_primary | 8/9 | 9/9 | 11/13 | 8/8 | 0.868 (6) | 0.71 |
| mafa_secondary | 7/9 | 8/9 | 8/13 | 4/4 | 0.771 (6) | 0.4 |

## MAST · defect · fw=clinical_agent (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/5 | 1/5 | 0/5 | 0/4 | 0.420 (5) | 0.0 |
| first_step | 0/5 | 0/5 | 0/5 | 0/5 | - | - |
| last_step | 0/5 | 2/5 | 0/5 | 0/5 | - | - |
| always_none | - | - | 0/5 | - | - | - |
| structure_prior | 0/5 | 0/5 | 0/5 | 0/5 | 0.340 (5) | - |
| mafa_primary | 5/5 | 5/5 | 5/5 | 5/5 | 0.875 (5) | 0.667 |
| mafa_secondary | 3/5 | 3/5 | 3/5 | 3/3 | 0.725 (5) | 0.5 |

## MAST · defect · fw=clinical_agent5 (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | - | - | 1/5 | - | - | 0.0 |
| first_step | - | - | 0/5 | - | - | - |
| last_step | - | - | 0/5 | - | - | - |
| always_none | - | - | 5/5 | - | - | - |
| structure_prior | - | - | 0/5 | - | - | - |
| mafa_primary | - | - | 4/5 | - | - | 0.0 |
| mafa_secondary | - | - | 5/5 | - | - | - |

## MAST · defect · fw=dylan (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/3 | 3/3 | 1/5 | 0/2 | 0.333 (1) | 0.0 |
| first_step | 1/3 | 3/3 | 0/5 | 0/3 | - | - |
| last_step | 1/3 | 3/3 | 1/5 | 1/3 | - | - |
| always_none | - | - | 2/5 | - | - | - |
| structure_prior | 1/3 | 3/3 | 0/5 | 0/3 | 0.000 (1) | - |
| mafa_primary | 2/3 | 3/3 | 3/5 | 2/2 | 1.000 (1) | 0.571 |
| mafa_secondary | 2/3 | 3/3 | 4/5 | 2/2 | 1.000 (1) | 0.667 |

## MAST · defect · fw=mdagents (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/5 | 3/5 | 1/5 | 4/5 | 0.611 (3) | 0.326 |
| first_step | 5/5 | 5/5 | 5/5 | 5/5 | - | - |
| last_step | 0/5 | 3/5 | 0/5 | 0/5 | - | - |
| always_none | - | - | 0/5 | - | - | - |
| structure_prior | 5/5 | 5/5 | 5/5 | 5/5 | 0.431 (3) | - |
| mafa_primary | 5/5 | 5/5 | 5/5 | 5/5 | 0.764 (3) | 0.917 |
| mafa_secondary | 5/5 | 5/5 | 2/5 | 2/2 | 0.736 (3) | 0.353 |

## MAST · defect · split=clean (rows=9)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/4 | 0/4 | 2/9 | 2/4 | 0.619 (4) | 0.154 |
| first_step | 2/4 | 2/4 | 2/9 | 2/4 | - | - |
| last_step | 0/4 | 0/4 | 0/9 | 0/4 | - | - |
| always_none | - | - | 5/9 | - | - | - |
| structure_prior | 2/4 | 2/4 | 2/9 | 2/4 | 0.363 (4) | - |
| mafa_primary | 4/4 | 4/4 | 7/9 | 4/4 | 0.865 (4) | 0.824 |
| mafa_secondary | 2/4 | 2/4 | 7/9 | 2/2 | 0.677 (4) | 0.5 |

## MAST · defect · split=faulty (rows=11)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/9 | 7/9 | 1/11 | 2/7 | 0.358 (5) | 0.16 |
| first_step | 4/9 | 6/9 | 3/11 | 3/9 | - | - |
| last_step | 1/9 | 8/9 | 1/11 | 1/9 | - | - |
| always_none | - | - | 2/11 | - | - | - |
| structure_prior | 4/9 | 6/9 | 3/11 | 3/9 | 0.308 (5) | - |
| mafa_primary | 8/9 | 9/9 | 10/11 | 8/8 | 0.842 (5) | 0.733 |
| mafa_secondary | 8/9 | 9/9 | 7/11 | 5/5 | 0.825 (5) | 0.462 |

## MAST · defect_any · all (rows=20)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 4/13 | 7/13 | 5/20 | 6/11 | 0.474 (9) | 0.157 |
| first_step | 8/13 | 8/13 | 7/20 | 8/13 | - | - |
| last_step | 0/13 | 8/13 | 0/20 | 0/13 | - | - |
| always_none | - | - | 7/20 | - | - | - |
| structure_prior | 8/13 | 8/13 | 7/20 | 8/13 | 0.332 (9) | - |
| mafa_primary | 11/13 | 13/13 | 15/20 | 11/12 | 0.852 (9) | 0.766 |
| mafa_secondary | 9/13 | 11/13 | 12/20 | 6/7 | 0.759 (9) | 0.474 |

## MAST · defect_any · no_leak (rows=13)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/9 | 6/9 | 2/13 | 3/7 | 0.399 (6) | 0.14 |
| first_step | 5/9 | 5/9 | 4/13 | 5/9 | - | - |
| last_step | 0/9 | 7/9 | 0/13 | 0/9 | - | - |
| always_none | - | - | 4/13 | - | - | - |
| structure_prior | 5/9 | 5/9 | 4/13 | 5/9 | 0.290 (6) | - |
| mafa_primary | 8/9 | 9/9 | 10/13 | 8/8 | 0.868 (6) | 0.71 |
| mafa_secondary | 7/9 | 8/9 | 7/13 | 4/4 | 0.771 (6) | 0.4 |

## MAST · defect_any · fw=clinical_agent (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/5 | 1/5 | 0/5 | 0/4 | 0.420 (5) | 0.0 |
| first_step | 0/5 | 0/5 | 0/5 | 1/5 | - | - |
| last_step | 0/5 | 2/5 | 0/5 | 0/5 | - | - |
| always_none | - | - | 0/5 | - | - | - |
| structure_prior | 0/5 | 0/5 | 0/5 | 1/5 | 0.340 (5) | - |
| mafa_primary | 4/5 | 5/5 | 4/5 | 5/5 | 0.875 (5) | 0.667 |
| mafa_secondary | 2/5 | 3/5 | 2/5 | 3/3 | 0.725 (5) | 0.5 |

## MAST · defect_any · fw=clinical_agent5 (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | - | - | 1/5 | - | - | 0.0 |
| first_step | - | - | 0/5 | - | - | - |
| last_step | - | - | 0/5 | - | - | - |
| always_none | - | - | 5/5 | - | - | - |
| structure_prior | - | - | 0/5 | - | - | - |
| mafa_primary | - | - | 4/5 | - | - | 0.0 |
| mafa_secondary | - | - | 5/5 | - | - | - |

## MAST · defect_any · fw=dylan (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/3 | 3/3 | 3/5 | 2/2 | 0.333 (1) | 0.0 |
| first_step | 3/3 | 3/3 | 2/5 | 2/3 | - | - |
| last_step | 0/3 | 3/3 | 0/5 | 0/3 | - | - |
| always_none | - | - | 2/5 | - | - | - |
| structure_prior | 3/3 | 3/3 | 2/5 | 2/3 | 0.000 (1) | - |
| mafa_primary | 2/3 | 3/3 | 2/5 | 1/2 | 1.000 (1) | 0.571 |
| mafa_secondary | 2/3 | 3/3 | 3/5 | 1/2 | 1.000 (1) | 0.667 |

## MAST · defect_any · fw=mdagents (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/5 | 3/5 | 1/5 | 4/5 | 0.611 (3) | 0.326 |
| first_step | 5/5 | 5/5 | 5/5 | 5/5 | - | - |
| last_step | 0/5 | 3/5 | 0/5 | 0/5 | - | - |
| always_none | - | - | 0/5 | - | - | - |
| structure_prior | 5/5 | 5/5 | 5/5 | 5/5 | 0.431 (3) | - |
| mafa_primary | 5/5 | 5/5 | 5/5 | 5/5 | 0.764 (3) | 0.917 |
| mafa_secondary | 5/5 | 5/5 | 2/5 | 2/2 | 0.736 (3) | 0.353 |

## MAST · defect_any · split=clean (rows=9)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/4 | 0/4 | 2/9 | 2/4 | 0.619 (4) | 0.154 |
| first_step | 2/4 | 2/4 | 2/9 | 2/4 | - | - |
| last_step | 0/4 | 0/4 | 0/9 | 0/4 | - | - |
| always_none | - | - | 5/9 | - | - | - |
| structure_prior | 2/4 | 2/4 | 2/9 | 2/4 | 0.363 (4) | - |
| mafa_primary | 4/4 | 4/4 | 7/9 | 4/4 | 0.865 (4) | 0.824 |
| mafa_secondary | 2/4 | 2/4 | 7/9 | 2/2 | 0.677 (4) | 0.5 |

## MAST · defect_any · split=faulty (rows=11)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 4/9 | 7/9 | 3/11 | 4/7 | 0.358 (5) | 0.16 |
| first_step | 6/9 | 6/9 | 5/11 | 6/9 | - | - |
| last_step | 0/9 | 8/9 | 0/11 | 0/9 | - | - |
| always_none | - | - | 2/11 | - | - | - |
| structure_prior | 6/9 | 6/9 | 5/11 | 6/9 | 0.308 (5) | - |
| mafa_primary | 7/9 | 9/9 | 8/11 | 7/8 | 0.842 (5) | 0.733 |
| mafa_secondary | 7/9 | 9/9 | 5/11 | 4/5 | 0.825 (5) | 0.462 |

## MAST · responsibility · all (rows=11)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/6 | 2/6 | 0/6 | 0/4 | 0.392 (5) | - |
| first_step | 1/6 | 1/6 | 0/6 | 0/6 | - | - |
| last_step | 2/6 | 5/6 | 2/6 | 2/6 | - | - |
| always_none | - | - | 0/6 | - | - | - |
| structure_prior | 1/6 | 1/6 | 0/6 | 0/6 | 0.325 (5) | - |
| mafa_primary | 4/6 | 4/6 | 4/6 | 4/5 | 0.775 (5) | - |
| mafa_secondary | 4/6 | 4/6 | 4/6 | 4/4 | 0.842 (5) | - |

## MAST · responsibility · no_leak (rows=10)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/6 | 2/6 | 0/6 | 0/4 | 0.392 (5) | - |
| first_step | 1/6 | 1/6 | 0/6 | 0/6 | - | - |
| last_step | 2/6 | 5/6 | 2/6 | 2/6 | - | - |
| always_none | - | - | 0/6 | - | - | - |
| structure_prior | 1/6 | 1/6 | 0/6 | 0/6 | 0.325 (5) | - |
| mafa_primary | 4/6 | 4/6 | 4/6 | 4/5 | 0.775 (5) | - |
| mafa_secondary | 4/6 | 4/6 | 4/6 | 4/4 | 0.842 (5) | - |

## MAST · responsibility · fw=clinical_agent (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/3 | 1/3 | 0/3 | 0/2 | 0.542 (3) | - |
| first_step | 0/3 | 0/3 | 0/3 | 0/3 | - | - |
| last_step | 0/3 | 2/3 | 0/3 | 0/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 0/3 | 0/3 | 0/3 | 0/3 | 0.542 (3) | - |
| mafa_primary | 3/3 | 3/3 | 3/3 | 3/3 | 0.875 (3) | - |
| mafa_secondary | 3/3 | 3/3 | 3/3 | 3/3 | 0.903 (3) | - |

## MAST · responsibility · fw=clinical_agent5 (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | - | - | - | - | - | - |
| first_step | - | - | - | - | - | - |
| last_step | - | - | - | - | - | - |
| always_none | - | - | - | - | - | - |
| structure_prior | - | - | - | - | - | - |
| mafa_primary | - | - | - | - | - | - |
| mafa_secondary | - | - | - | - | - | - |

## MAST · responsibility · fw=dylan (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/2 | 1/2 | 0/2 | 0/1 | 0.333 (1) | - |
| first_step | 1/2 | 1/2 | 0/2 | 0/2 | - | - |
| last_step | 1/2 | 2/2 | 1/2 | 1/2 | - | - |
| always_none | - | - | 0/2 | - | - | - |
| structure_prior | 1/2 | 1/2 | 0/2 | 0/2 | 0.000 (1) | - |
| mafa_primary | 1/2 | 1/2 | 1/2 | 1/1 | 1.000 (1) | - |
| mafa_secondary | 1/2 | 1/2 | 1/2 | 1/1 | 1.000 (1) | - |

## MAST · responsibility · fw=mdagents (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/1 | 0/1 | 0/1 | 0/1 | 0.000 (1) | - |
| first_step | 0/1 | 0/1 | 0/1 | 0/1 | - | - |
| last_step | 1/1 | 1/1 | 1/1 | 1/1 | - | - |
| always_none | - | - | 0/1 | - | - | - |
| structure_prior | 0/1 | 0/1 | 0/1 | 0/1 | 0.000 (1) | - |
| mafa_primary | 0/1 | 0/1 | 0/1 | 0/1 | 0.250 (1) | - |
| mafa_secondary | 0/1 | 0/1 | 0/1 | - | 0.500 (1) | - |

## MAST · responsibility_any · all (rows=11)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 4/9 | 6/9 | 2/9 | 4/7 | 0.485 (7) | - |
| first_step | 2/9 | 3/9 | 1/9 | 4/9 | - | - |
| last_step | 0/9 | 8/9 | 0/9 | 0/9 | - | - |
| always_none | - | - | 0/9 | - | - | - |
| structure_prior | 2/9 | 3/9 | 1/9 | 4/9 | 0.408 (7) | - |
| mafa_primary | 5/9 | 6/9 | 4/9 | 8/8 | 0.536 (7) | - |
| mafa_secondary | 5/9 | 6/9 | 4/9 | 5/5 | 0.732 (7) | - |

## MAST · responsibility_any · no_leak (rows=10)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 4/8 | 5/8 | 2/8 | 4/6 | 0.485 (7) | - |
| first_step | 2/8 | 2/8 | 1/8 | 4/8 | - | - |
| last_step | 0/8 | 7/8 | 0/8 | 0/8 | - | - |
| always_none | - | - | 0/8 | - | - | - |
| structure_prior | 2/8 | 2/8 | 1/8 | 4/8 | 0.408 (7) | - |
| mafa_primary | 5/8 | 5/8 | 4/8 | 7/7 | 0.536 (7) | - |
| mafa_secondary | 5/8 | 5/8 | 4/8 | 4/4 | 0.732 (7) | - |

## MAST · responsibility_any · fw=clinical_agent (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/3 | 1/3 | 0/3 | 0/2 | 0.542 (3) | - |
| first_step | 0/3 | 0/3 | 0/3 | 0/3 | - | - |
| last_step | 0/3 | 2/3 | 0/3 | 0/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 0/3 | 0/3 | 0/3 | 0/3 | 0.542 (3) | - |
| mafa_primary | 3/3 | 3/3 | 3/3 | 3/3 | 0.833 (3) | - |
| mafa_secondary | 3/3 | 3/3 | 3/3 | 3/3 | 0.875 (3) | - |

## MAST · responsibility_any · fw=clinical_agent5 (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | - | - | - | - | - | - |
| first_step | - | - | - | - | - | - |
| last_step | - | - | - | - | - | - |
| always_none | - | - | - | - | - | - |
| structure_prior | - | - | - | - | - | - |
| mafa_primary | - | - | - | - | - | - |
| mafa_secondary | - | - | - | - | - | - |

## MAST · responsibility_any · fw=dylan (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/3 | 3/3 | 1/3 | 1/2 | 0.333 (1) | - |
| first_step | 2/3 | 3/3 | 1/3 | 1/3 | - | - |
| last_step | 0/3 | 3/3 | 0/3 | 0/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 2/3 | 3/3 | 1/3 | 1/3 | 0.000 (1) | - |
| mafa_primary | 2/3 | 3/3 | 1/3 | 2/2 | 1.000 (1) | - |
| mafa_secondary | 2/3 | 3/3 | 1/3 | 2/2 | 1.000 (1) | - |

## MAST · responsibility_any · fw=mdagents (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/3 | 2/3 | 1/3 | 3/3 | 0.478 (3) | - |
| first_step | 0/3 | 0/3 | 0/3 | 3/3 | - | - |
| last_step | 0/3 | 3/3 | 0/3 | 0/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 0/3 | 0/3 | 0/3 | 3/3 | 0.411 (3) | - |
| mafa_primary | 0/3 | 0/3 | 0/3 | 3/3 | 0.083 (3) | - |
| mafa_secondary | 0/3 | 0/3 | 0/3 | - | 0.500 (3) | - |

# MedAgentAudit (rows=19)

## MedAgentAudit · defect · all (rows=19)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/8 | 9/16 | 7/19 | 4/7 | 0.482 (11) | - |
| first_step | 3/8 | 10/16 | 1/19 | 4/8 | - | - |
| last_step | 1/8 | 10/16 | 1/19 | 2/8 | - | - |
| always_none | - | - | 11/19 | - | - | - |
| structure_prior | 3/8 | 10/16 | 1/19 | 4/8 | 0.362 (11) | - |
| mafa_primary | 5/8 | 16/16 | 6/19 | 4/7 | 0.780 (11) | 0.667 |
| mafa_secondary | 6/8 | 14/16 | 11/19 | 4/5 | 0.636 (11) | 0.211 |

## MedAgentAudit · defect · no_leak (rows=11)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/4 | 6/9 | 5/11 | 1/4 | 0.465 (4) | - |
| first_step | 1/4 | 6/9 | 0/11 | 1/4 | - | - |
| last_step | 1/4 | 8/9 | 1/11 | 1/4 | - | - |
| always_none | - | - | 7/11 | - | - | - |
| structure_prior | 1/4 | 6/9 | 0/11 | 1/4 | 0.486 (4) | - |
| mafa_primary | 1/4 | 9/9 | 1/11 | 1/4 | 0.708 (4) | 0.625 |
| mafa_secondary | 3/4 | 8/9 | 7/11 | 3/4 | 0.625 (4) | 0.308 |

## MedAgentAudit · defect · fw=clinical_agent (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | - | 0/4 | 2/5 | - | 0.390 (4) | - |
| first_step | - | 0/4 | 0/5 | - | - | - |
| last_step | - | 3/4 | 0/5 | - | - | - |
| always_none | - | - | 5/5 | - | - | - |
| structure_prior | - | 0/4 | 0/5 | - | 0.553 (4) | - |
| mafa_primary | - | 4/4 | 0/5 | - | 0.771 (4) | 0.0 |
| mafa_secondary | - | 3/4 | 2/5 | - | 0.750 (4) | 0.0 |

## MedAgentAudit · defect · fw=clinical_agent5 (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/2 | 2/3 | 3/5 | 2/2 | 0.583 (3) | - |
| first_step | 0/2 | 1/3 | 0/5 | 2/2 | - | - |
| last_step | 0/2 | 0/3 | 0/5 | 0/2 | - | - |
| always_none | - | - | 3/5 | - | - | - |
| structure_prior | 0/2 | 1/3 | 0/5 | 2/2 | 0.278 (3) | - |
| mafa_primary | 2/2 | 3/3 | 3/5 | 2/2 | 0.917 (3) | 1.0 |
| mafa_secondary | 1/2 | 2/3 | 4/5 | 1/1 | 0.667 (3) | 0.0 |

## MedAgentAudit · defect · fw=dylan (rows=4)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/2 | 4/4 | 2/4 | 0/1 | 0.688 (2) | - |
| first_step | 2/2 | 4/4 | 0/4 | 0/2 | - | - |
| last_step | 0/2 | 4/4 | 0/4 | 1/2 | - | - |
| always_none | - | - | 2/4 | - | - | - |
| structure_prior | 2/2 | 4/4 | 0/4 | 0/2 | 0.000 (2) | - |
| mafa_primary | 2/2 | 4/4 | 3/4 | 1/2 | 0.625 (2) | 1.0 |
| mafa_secondary | 2/2 | 4/4 | 2/4 | 0/1 | 0.500 (2) | 0.0 |

## MedAgentAudit · defect · fw=mdagents (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/4 | 3/5 | 0/5 | 2/4 | 0.308 (2) | - |
| first_step | 1/4 | 5/5 | 1/5 | 2/4 | - | - |
| last_step | 1/4 | 3/5 | 1/5 | 1/4 | - | - |
| always_none | - | - | 1/5 | - | - | - |
| structure_prior | 1/4 | 5/5 | 1/5 | 2/4 | 0.467 (2) | - |
| mafa_primary | 1/4 | 5/5 | 0/5 | 1/3 | 0.750 (2) | 0.615 |
| mafa_secondary | 3/4 | 5/5 | 3/5 | 3/3 | 0.500 (2) | 0.364 |

## MedAgentAudit · defect · split=clean (rows=8)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/4 | 3/7 | 2/8 | 3/3 | 0.492 (7) | - |
| first_step | 2/4 | 4/7 | 1/8 | 3/4 | - | - |
| last_step | 0/4 | 2/7 | 0/8 | 1/4 | - | - |
| always_none | - | - | 4/8 | - | - | - |
| structure_prior | 2/4 | 4/7 | 1/8 | 3/4 | 0.290 (7) | - |
| mafa_primary | 4/4 | 7/7 | 4/8 | 3/3 | 0.821 (7) | 0.6 |
| mafa_secondary | 3/4 | 6/7 | 4/8 | 1/1 | 0.643 (7) | 0.0 |

## MedAgentAudit · defect · split=faulty (rows=11)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/4 | 6/9 | 5/11 | 1/4 | 0.465 (4) | - |
| first_step | 1/4 | 6/9 | 0/11 | 1/4 | - | - |
| last_step | 1/4 | 8/9 | 1/11 | 1/4 | - | - |
| always_none | - | - | 7/11 | - | - | - |
| structure_prior | 1/4 | 6/9 | 0/11 | 1/4 | 0.486 (4) | - |
| mafa_primary | 1/4 | 9/9 | 2/11 | 1/4 | 0.708 (4) | 0.714 |
| mafa_secondary | 3/4 | 8/9 | 7/11 | 3/4 | 0.625 (4) | 0.308 |

## MedAgentAudit · defect_any · all (rows=19)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 7/16 | 9/16 | 6/19 | 8/10 | 0.482 (11) | - |
| first_step | 8/16 | 10/16 | 8/19 | 10/16 | - | - |
| last_step | 2/16 | 10/16 | 0/19 | 0/16 | - | - |
| always_none | - | - | 3/19 | - | - | - |
| structure_prior | 7/16 | 10/16 | 7/19 | 9/16 | 0.362 (11) | - |
| mafa_primary | 12/16 | 16/16 | 10/19 | 9/13 | 0.780 (11) | 0.667 |
| mafa_secondary | 9/16 | 14/16 | 7/19 | 4/8 | 0.636 (11) | 0.211 |

## MedAgentAudit · defect_any · no_leak (rows=11)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 6/9 | 6/9 | 5/11 | 4/5 | 0.465 (4) | - |
| first_step | 6/9 | 6/9 | 6/11 | 6/9 | - | - |
| last_step | 0/9 | 8/9 | 0/11 | 0/9 | - | - |
| always_none | - | - | 2/11 | - | - | - |
| structure_prior | 5/9 | 6/9 | 5/11 | 5/9 | 0.486 (4) | - |
| mafa_primary | 7/9 | 9/9 | 5/11 | 5/8 | 0.708 (4) | 0.625 |
| mafa_secondary | 5/9 | 8/9 | 4/11 | 2/6 | 0.625 (4) | 0.308 |

## MedAgentAudit · defect_any · fw=clinical_agent (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/4 | 0/4 | 0/5 | 0/2 | 0.390 (4) | - |
| first_step | 0/4 | 0/4 | 0/5 | 0/4 | - | - |
| last_step | 0/4 | 3/4 | 0/5 | 0/4 | - | - |
| always_none | - | - | 1/5 | - | - | - |
| structure_prior | 0/4 | 0/4 | 0/5 | 0/4 | 0.553 (4) | - |
| mafa_primary | 2/4 | 4/4 | 2/5 | 2/4 | 0.771 (4) | 0.0 |
| mafa_secondary | 2/4 | 3/4 | 3/5 | 2/3 | 0.750 (4) | 0.0 |

## MedAgentAudit · defect_any · fw=clinical_agent5 (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/3 | 2/3 | 2/5 | 2/2 | 0.583 (3) | - |
| first_step | 1/3 | 1/3 | 1/5 | 3/3 | - | - |
| last_step | 0/3 | 0/3 | 0/5 | 0/3 | - | - |
| always_none | - | - | 2/5 | - | - | - |
| structure_prior | 0/3 | 1/3 | 0/5 | 2/3 | 0.278 (3) | - |
| mafa_primary | 3/3 | 3/3 | 4/5 | 3/3 | 0.917 (3) | 1.0 |
| mafa_secondary | 2/3 | 2/3 | 3/5 | 1/1 | 0.667 (3) | 0.0 |

## MedAgentAudit · defect_any · fw=dylan (rows=4)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/4 | 4/4 | 1/4 | 1/1 | 0.688 (2) | - |
| first_step | 2/4 | 4/4 | 2/4 | 2/4 | - | - |
| last_step | 2/4 | 4/4 | 0/4 | 0/4 | - | - |
| always_none | - | - | 0/4 | - | - | - |
| structure_prior | 2/4 | 4/4 | 2/4 | 2/4 | 0.000 (2) | - |
| mafa_primary | 2/4 | 4/4 | 0/4 | 0/2 | 0.625 (2) | 1.0 |
| mafa_secondary | 2/4 | 4/4 | 0/4 | 0/1 | 0.500 (2) | 0.0 |

## MedAgentAudit · defect_any · fw=mdagents (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/5 | 3/5 | 3/5 | 5/5 | 0.308 (2) | - |
| first_step | 5/5 | 5/5 | 5/5 | 5/5 | - | - |
| last_step | 0/5 | 3/5 | 0/5 | 0/5 | - | - |
| always_none | - | - | 0/5 | - | - | - |
| structure_prior | 5/5 | 5/5 | 5/5 | 5/5 | 0.467 (2) | - |
| mafa_primary | 5/5 | 5/5 | 4/5 | 4/4 | 0.750 (2) | 0.615 |
| mafa_secondary | 3/5 | 5/5 | 1/5 | 1/3 | 0.500 (2) | 0.364 |

## MedAgentAudit · defect_any · split=clean (rows=8)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/7 | 3/7 | 1/8 | 4/5 | 0.492 (7) | - |
| first_step | 2/7 | 4/7 | 2/8 | 4/7 | - | - |
| last_step | 2/7 | 2/7 | 0/8 | 0/7 | - | - |
| always_none | - | - | 1/8 | - | - | - |
| structure_prior | 2/7 | 4/7 | 2/8 | 4/7 | 0.290 (7) | - |
| mafa_primary | 5/7 | 7/7 | 4/8 | 4/5 | 0.821 (7) | 0.6 |
| mafa_secondary | 4/7 | 6/7 | 3/8 | 2/2 | 0.643 (7) | 0.0 |

## MedAgentAudit · defect_any · split=faulty (rows=11)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 6/9 | 6/9 | 5/11 | 4/5 | 0.465 (4) | - |
| first_step | 6/9 | 6/9 | 6/11 | 6/9 | - | - |
| last_step | 0/9 | 8/9 | 0/11 | 0/9 | - | - |
| always_none | - | - | 2/11 | - | - | - |
| structure_prior | 5/9 | 6/9 | 5/11 | 5/9 | 0.486 (4) | - |
| mafa_primary | 7/9 | 9/9 | 6/11 | 5/8 | 0.708 (4) | 0.714 |
| mafa_secondary | 5/9 | 8/9 | 4/11 | 2/6 | 0.625 (4) | 0.308 |

## MedAgentAudit · responsibility · all (rows=11)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/3 | 1/3 | 0/3 | 0/3 | 0.125 (2) | - |
| first_step | 1/3 | 1/3 | 0/3 | 0/3 | - | - |
| last_step | 1/3 | 3/3 | 1/3 | 1/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 1/3 | 1/3 | 0/3 | 0/3 | 0.167 (2) | - |
| mafa_primary | 1/3 | 1/3 | 0/3 | 0/3 | 0.542 (2) | - |
| mafa_secondary | 2/3 | 2/3 | 1/3 | 1/3 | 0.667 (2) | - |

## MedAgentAudit · responsibility · no_leak (rows=10)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/3 | 1/3 | 0/3 | 0/3 | 0.125 (2) | - |
| first_step | 1/3 | 1/3 | 0/3 | 0/3 | - | - |
| last_step | 1/3 | 3/3 | 1/3 | 1/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 1/3 | 1/3 | 0/3 | 0/3 | 0.167 (2) | - |
| mafa_primary | 1/3 | 1/3 | 0/3 | 0/3 | 0.542 (2) | - |
| mafa_secondary | 2/3 | 2/3 | 1/3 | 1/3 | 0.667 (2) | - |

## MedAgentAudit · responsibility · fw=clinical_agent (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | - | - | - | - | - | - |
| first_step | - | - | - | - | - | - |
| last_step | - | - | - | - | - | - |
| always_none | - | - | - | - | - | - |
| structure_prior | - | - | - | - | - | - |
| mafa_primary | - | - | - | - | - | - |
| mafa_secondary | - | - | - | - | - | - |

## MedAgentAudit · responsibility · fw=clinical_agent5 (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | - | - | - | - | - | - |
| first_step | - | - | - | - | - | - |
| last_step | - | - | - | - | - | - |
| always_none | - | - | - | - | - | - |
| structure_prior | - | - | - | - | - | - |
| mafa_primary | - | - | - | - | - | - |
| mafa_secondary | - | - | - | - | - | - |

## MedAgentAudit · responsibility · fw=dylan (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/1 | 1/1 | 0/1 | 0/1 | - | - |
| first_step | 1/1 | 1/1 | 0/1 | 0/1 | - | - |
| last_step | 0/1 | 1/1 | 0/1 | 0/1 | - | - |
| always_none | - | - | 0/1 | - | - | - |
| structure_prior | 1/1 | 1/1 | 0/1 | 0/1 | - | - |
| mafa_primary | 1/1 | 1/1 | 0/1 | 0/1 | - | - |
| mafa_secondary | 1/1 | 1/1 | 0/1 | 0/1 | - | - |

## MedAgentAudit · responsibility · fw=mdagents (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/2 | 0/2 | 0/2 | 0/2 | 0.125 (2) | - |
| first_step | 0/2 | 0/2 | 0/2 | 0/2 | - | - |
| last_step | 1/2 | 2/2 | 1/2 | 1/2 | - | - |
| always_none | - | - | 0/2 | - | - | - |
| structure_prior | 0/2 | 0/2 | 0/2 | 0/2 | 0.167 (2) | - |
| mafa_primary | 0/2 | 0/2 | 0/2 | 0/2 | 0.542 (2) | - |
| mafa_secondary | 1/2 | 1/2 | 1/2 | 1/2 | 0.667 (2) | - |

## MedAgentAudit · responsibility_any · all (rows=11)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/9 | 2/9 | 1/9 | 2/5 | 0.447 (7) | - |
| first_step | 2/9 | 2/9 | 2/9 | 3/9 | - | - |
| last_step | 0/9 | 8/9 | 0/9 | 0/9 | - | - |
| always_none | - | - | 0/9 | - | - | - |
| structure_prior | 3/9 | 3/9 | 3/9 | 4/9 | 0.466 (7) | - |
| mafa_primary | 3/9 | 5/9 | 1/9 | 2/8 | 0.530 (7) | - |
| mafa_secondary | 4/9 | 6/9 | 2/9 | 2/6 | 0.631 (7) | - |

## MedAgentAudit · responsibility_any · no_leak (rows=10)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/9 | 2/9 | 1/9 | 2/5 | 0.447 (7) | - |
| first_step | 2/9 | 2/9 | 2/9 | 3/9 | - | - |
| last_step | 0/9 | 8/9 | 0/9 | 0/9 | - | - |
| always_none | - | - | 0/9 | - | - | - |
| structure_prior | 3/9 | 3/9 | 3/9 | 4/9 | 0.466 (7) | - |
| mafa_primary | 3/9 | 5/9 | 1/9 | 2/8 | 0.530 (7) | - |
| mafa_secondary | 4/9 | 6/9 | 2/9 | 2/6 | 0.631 (7) | - |

## MedAgentAudit · responsibility_any · fw=clinical_agent (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/3 | 0/3 | 0/3 | 0/1 | 0.454 (3) | - |
| first_step | 0/3 | 0/3 | 0/3 | 0/3 | - | - |
| last_step | 0/3 | 3/3 | 0/3 | 0/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 0/3 | 0/3 | 0/3 | 0/3 | 0.537 (3) | - |
| mafa_primary | 1/3 | 3/3 | 1/3 | 1/3 | 0.694 (3) | - |
| mafa_secondary | 1/3 | 2/3 | 1/3 | 1/2 | 0.667 (3) | - |

## MedAgentAudit · responsibility_any · fw=clinical_agent5 (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/1 | 0/1 | 0/1 | - | 0.750 (1) | - |
| first_step | 0/1 | 0/1 | 0/1 | 0/1 | - | - |
| last_step | 0/1 | 0/1 | 0/1 | 0/1 | - | - |
| always_none | - | - | 0/1 | - | - | - |
| structure_prior | 1/1 | 1/1 | 1/1 | 1/1 | 0.750 (1) | - |
| mafa_primary | 0/1 | 0/1 | 0/1 | 0/1 | 0.375 (1) | - |
| mafa_secondary | 0/1 | 0/1 | 0/1 | - | 0.500 (1) | - |

## MedAgentAudit · responsibility_any · fw=dylan (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/2 | 2/2 | 1/2 | 1/1 | - | - |
| first_step | 2/2 | 2/2 | 2/2 | 2/2 | - | - |
| last_step | 0/2 | 2/2 | 0/2 | 0/2 | - | - |
| always_none | - | - | 0/2 | - | - | - |
| structure_prior | 2/2 | 2/2 | 2/2 | 2/2 | - | - |
| mafa_primary | 2/2 | 2/2 | 0/2 | 0/1 | - | - |
| mafa_secondary | 2/2 | 2/2 | 0/2 | 0/1 | - | - |

## MedAgentAudit · responsibility_any · fw=mdagents (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/3 | 0/3 | 0/3 | 1/3 | 0.339 (3) | - |
| first_step | 0/3 | 0/3 | 0/3 | 1/3 | - | - |
| last_step | 0/3 | 3/3 | 0/3 | 0/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 0/3 | 0/3 | 0/3 | 1/3 | 0.300 (3) | - |
| mafa_primary | 0/3 | 0/3 | 0/3 | 1/3 | 0.417 (3) | - |
| mafa_secondary | 1/3 | 2/3 | 1/3 | 1/3 | 0.639 (3) | - |
