# MAFA evaluation · subset=dev · source=llm · rows=20
labels `results/human_like_eval/labels_v1.jsonl` sha256 f0ccf787c569 · split 916fee301529

Every number is computed within ONE taxonomy: MAST and MedAgentAudit labels are different label definitions (and the same trace can appear under both), so rows are never pooled across them. MedHyperTrace is trained on MAST-coded synthetic data only and has no MedAgentAudit code head.

# MAST (rows=13)

## MAST · defect · all (rows=13)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 6/13 | 7/13 | 5/13 | 9/12 | 0.371 (10) | 0.349 |
| first_step | 8/13 | 8/13 | 6/13 | 9/13 | - | - |
| last_step | 0/13 | 13/13 | 0/13 | 0/13 | - | - |
| always_none | - | - | 0/13 | - | - | - |
| structure_prior | 8/13 | 8/13 | 6/13 | 9/13 | 0.360 (10) | - |
| mafa_primary | 11/13 | 13/13 | 11/13 | 11/13 | 0.911 (10) | 0.814 |
| mafa_secondary | 10/13 | 12/13 | 7/13 | 7/9 | 0.712 (10) | 0.361 |

## MAST · defect · no_leak (rows=13)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 6/13 | 7/13 | 5/13 | 9/12 | 0.371 (10) | 0.349 |
| first_step | 8/13 | 8/13 | 6/13 | 9/13 | - | - |
| last_step | 0/13 | 13/13 | 0/13 | 0/13 | - | - |
| always_none | - | - | 0/13 | - | - | - |
| structure_prior | 8/13 | 8/13 | 6/13 | 9/13 | 0.360 (10) | - |
| mafa_primary | 11/13 | 13/13 | 11/13 | 11/13 | 0.911 (10) | 0.814 |
| mafa_secondary | 10/13 | 12/13 | 7/13 | 7/9 | 0.712 (10) | 0.361 |

## MAST · defect · fw=clinical_agent (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/5 | 2/5 | 2/5 | 4/4 | 0.343 (5) | 0.114 |
| first_step | 1/5 | 1/5 | 1/5 | 4/5 | - | - |
| last_step | 0/5 | 5/5 | 0/5 | 0/5 | - | - |
| always_none | - | - | 0/5 | - | - | - |
| structure_prior | 1/5 | 1/5 | 1/5 | 4/5 | 0.386 (5) | - |
| mafa_primary | 5/5 | 5/5 | 5/5 | 5/5 | 0.922 (5) | 0.706 |
| mafa_secondary | 4/5 | 5/5 | 4/5 | 4/5 | 0.790 (5) | 0.452 |

## MAST · defect · fw=dylan (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/5 | 3/5 | 1/5 | 2/5 | 0.417 (4) | 0.432 |
| first_step | 4/5 | 4/5 | 2/5 | 2/5 | - | - |
| last_step | 0/5 | 5/5 | 0/5 | 0/5 | - | - |
| always_none | - | - | 0/5 | - | - | - |
| structure_prior | 4/5 | 4/5 | 2/5 | 2/5 | 0.333 (4) | - |
| mafa_primary | 3/5 | 5/5 | 3/5 | 3/5 | 0.917 (4) | 0.909 |
| mafa_secondary | 4/5 | 4/5 | 1/5 | 1/1 | 0.583 (4) | 0.0 |

## MAST · defect · fw=mdagents (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/3 | 2/3 | 2/3 | 3/3 | 0.333 (1) | 0.486 |
| first_step | 3/3 | 3/3 | 3/3 | 3/3 | - | - |
| last_step | 0/3 | 3/3 | 0/3 | 0/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 3/3 | 3/3 | 3/3 | 3/3 | 0.333 (1) | - |
| mafa_primary | 3/3 | 3/3 | 3/3 | 3/3 | 0.833 (1) | 0.867 |
| mafa_secondary | 2/3 | 3/3 | 2/3 | 2/3 | 0.833 (1) | 0.444 |

## MAST · defect · split=faulty (rows=13)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 6/13 | 7/13 | 5/13 | 9/12 | 0.371 (10) | 0.349 |
| first_step | 8/13 | 8/13 | 6/13 | 9/13 | - | - |
| last_step | 0/13 | 13/13 | 0/13 | 0/13 | - | - |
| always_none | - | - | 0/13 | - | - | - |
| structure_prior | 8/13 | 8/13 | 6/13 | 9/13 | 0.360 (10) | - |
| mafa_primary | 11/13 | 13/13 | 11/13 | 11/13 | 0.911 (10) | 0.814 |
| mafa_secondary | 10/13 | 12/13 | 7/13 | 7/9 | 0.712 (10) | 0.361 |

## MAST · defect_any · all (rows=13)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 6/13 | 7/13 | 5/13 | 9/12 | 0.371 (10) | 0.349 |
| first_step | 8/13 | 8/13 | 6/13 | 9/13 | - | - |
| last_step | 0/13 | 13/13 | 0/13 | 0/13 | - | - |
| always_none | - | - | 0/13 | - | - | - |
| structure_prior | 8/13 | 8/13 | 6/13 | 9/13 | 0.360 (10) | - |
| mafa_primary | 11/13 | 13/13 | 11/13 | 11/13 | 0.911 (10) | 0.814 |
| mafa_secondary | 10/13 | 12/13 | 7/13 | 7/9 | 0.712 (10) | 0.361 |

## MAST · defect_any · no_leak (rows=13)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 6/13 | 7/13 | 5/13 | 9/12 | 0.371 (10) | 0.349 |
| first_step | 8/13 | 8/13 | 6/13 | 9/13 | - | - |
| last_step | 0/13 | 13/13 | 0/13 | 0/13 | - | - |
| always_none | - | - | 0/13 | - | - | - |
| structure_prior | 8/13 | 8/13 | 6/13 | 9/13 | 0.360 (10) | - |
| mafa_primary | 11/13 | 13/13 | 11/13 | 11/13 | 0.911 (10) | 0.814 |
| mafa_secondary | 10/13 | 12/13 | 7/13 | 7/9 | 0.712 (10) | 0.361 |

## MAST · defect_any · fw=clinical_agent (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/5 | 2/5 | 2/5 | 4/4 | 0.343 (5) | 0.114 |
| first_step | 1/5 | 1/5 | 1/5 | 4/5 | - | - |
| last_step | 0/5 | 5/5 | 0/5 | 0/5 | - | - |
| always_none | - | - | 0/5 | - | - | - |
| structure_prior | 1/5 | 1/5 | 1/5 | 4/5 | 0.386 (5) | - |
| mafa_primary | 5/5 | 5/5 | 5/5 | 5/5 | 0.922 (5) | 0.706 |
| mafa_secondary | 4/5 | 5/5 | 4/5 | 4/5 | 0.790 (5) | 0.452 |

## MAST · defect_any · fw=dylan (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/5 | 3/5 | 1/5 | 2/5 | 0.417 (4) | 0.432 |
| first_step | 4/5 | 4/5 | 2/5 | 2/5 | - | - |
| last_step | 0/5 | 5/5 | 0/5 | 0/5 | - | - |
| always_none | - | - | 0/5 | - | - | - |
| structure_prior | 4/5 | 4/5 | 2/5 | 2/5 | 0.333 (4) | - |
| mafa_primary | 3/5 | 5/5 | 3/5 | 3/5 | 0.917 (4) | 0.909 |
| mafa_secondary | 4/5 | 4/5 | 1/5 | 1/1 | 0.583 (4) | 0.0 |

## MAST · defect_any · fw=mdagents (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/3 | 2/3 | 2/3 | 3/3 | 0.333 (1) | 0.486 |
| first_step | 3/3 | 3/3 | 3/3 | 3/3 | - | - |
| last_step | 0/3 | 3/3 | 0/3 | 0/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 3/3 | 3/3 | 3/3 | 3/3 | 0.333 (1) | - |
| mafa_primary | 3/3 | 3/3 | 3/3 | 3/3 | 0.833 (1) | 0.867 |
| mafa_secondary | 2/3 | 3/3 | 2/3 | 2/3 | 0.833 (1) | 0.444 |

## MAST · defect_any · split=faulty (rows=13)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 6/13 | 7/13 | 5/13 | 9/12 | 0.371 (10) | 0.349 |
| first_step | 8/13 | 8/13 | 6/13 | 9/13 | - | - |
| last_step | 0/13 | 13/13 | 0/13 | 0/13 | - | - |
| always_none | - | - | 0/13 | - | - | - |
| structure_prior | 8/13 | 8/13 | 6/13 | 9/13 | 0.360 (10) | - |
| mafa_primary | 11/13 | 13/13 | 11/13 | 11/13 | 0.911 (10) | 0.814 |
| mafa_secondary | 10/13 | 12/13 | 7/13 | 7/9 | 0.712 (10) | 0.361 |

# MedAgentAudit (rows=7)

## MedAgentAudit · defect · all (rows=7)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/7 | 5/7 | 3/7 | 5/7 | 0.500 (5) | - |
| first_step | 6/7 | 6/7 | 5/7 | 6/7 | - | - |
| last_step | 0/7 | 5/7 | 0/7 | 1/7 | - | - |
| always_none | - | - | 0/7 | - | - | - |
| structure_prior | 6/7 | 6/7 | 5/7 | 6/7 | 0.465 (5) | - |
| mafa_primary | 7/7 | 7/7 | 6/7 | 6/7 | 0.713 (5) | 0.545 |
| mafa_secondary | 5/7 | 7/7 | 5/7 | 6/7 | 0.758 (5) | 0.182 |

## MedAgentAudit · defect · no_leak (rows=7)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/7 | 5/7 | 3/7 | 5/7 | 0.500 (5) | - |
| first_step | 6/7 | 6/7 | 5/7 | 6/7 | - | - |
| last_step | 0/7 | 5/7 | 0/7 | 1/7 | - | - |
| always_none | - | - | 0/7 | - | - | - |
| structure_prior | 6/7 | 6/7 | 5/7 | 6/7 | 0.465 (5) | - |
| mafa_primary | 7/7 | 7/7 | 6/7 | 6/7 | 0.713 (5) | 0.545 |
| mafa_secondary | 5/7 | 7/7 | 5/7 | 6/7 | 0.758 (5) | 0.182 |

## MedAgentAudit · defect · fw=clinical_agent (rows=1)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/1 | 0/1 | 0/1 | 1/1 | 0.500 (1) | - |
| first_step | 0/1 | 0/1 | 0/1 | 1/1 | - | - |
| last_step | 0/1 | 1/1 | 0/1 | 0/1 | - | - |
| always_none | - | - | 0/1 | - | - | - |
| structure_prior | 0/1 | 0/1 | 0/1 | 1/1 | 0.375 (1) | - |
| mafa_primary | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | 1.0 |
| mafa_secondary | 1/1 | 1/1 | 1/1 | 1/1 | 0.875 (1) | 0.0 |

## MedAgentAudit · defect · fw=dylan (rows=1)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/1 | 0/1 | 0/1 | 0/1 | 0.333 (1) | - |
| first_step | 1/1 | 1/1 | 0/1 | 0/1 | - | - |
| last_step | 0/1 | 0/1 | 0/1 | 1/1 | - | - |
| always_none | - | - | 0/1 | - | - | - |
| structure_prior | 1/1 | 1/1 | 0/1 | 0/1 | 0.333 (1) | - |
| mafa_primary | 1/1 | 1/1 | 0/1 | 0/1 | 0.667 (1) | 1.0 |
| mafa_secondary | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | 0.0 |

## MedAgentAudit · defect · fw=mdagents (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/5 | 5/5 | 3/5 | 4/5 | 0.556 (3) | - |
| first_step | 5/5 | 5/5 | 5/5 | 5/5 | - | - |
| last_step | 0/5 | 4/5 | 0/5 | 0/5 | - | - |
| always_none | - | - | 0/5 | - | - | - |
| structure_prior | 5/5 | 5/5 | 5/5 | 5/5 | 0.539 (3) | - |
| mafa_primary | 5/5 | 5/5 | 5/5 | 5/5 | 0.633 (3) | 0.375 |
| mafa_secondary | 3/5 | 5/5 | 3/5 | 4/5 | 0.639 (3) | 0.235 |

## MedAgentAudit · defect · split=faulty (rows=7)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/7 | 5/7 | 3/7 | 5/7 | 0.500 (5) | - |
| first_step | 6/7 | 6/7 | 5/7 | 6/7 | - | - |
| last_step | 0/7 | 5/7 | 0/7 | 1/7 | - | - |
| always_none | - | - | 0/7 | - | - | - |
| structure_prior | 6/7 | 6/7 | 5/7 | 6/7 | 0.465 (5) | - |
| mafa_primary | 7/7 | 7/7 | 6/7 | 6/7 | 0.713 (5) | 0.545 |
| mafa_secondary | 5/7 | 7/7 | 5/7 | 6/7 | 0.758 (5) | 0.182 |

## MedAgentAudit · defect_any · all (rows=7)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/7 | 5/7 | 3/7 | 5/7 | 0.500 (5) | - |
| first_step | 6/7 | 6/7 | 5/7 | 6/7 | - | - |
| last_step | 0/7 | 5/7 | 0/7 | 1/7 | - | - |
| always_none | - | - | 0/7 | - | - | - |
| structure_prior | 6/7 | 6/7 | 5/7 | 6/7 | 0.465 (5) | - |
| mafa_primary | 7/7 | 7/7 | 6/7 | 6/7 | 0.713 (5) | 0.545 |
| mafa_secondary | 5/7 | 7/7 | 5/7 | 6/7 | 0.758 (5) | 0.182 |

## MedAgentAudit · defect_any · no_leak (rows=7)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/7 | 5/7 | 3/7 | 5/7 | 0.500 (5) | - |
| first_step | 6/7 | 6/7 | 5/7 | 6/7 | - | - |
| last_step | 0/7 | 5/7 | 0/7 | 1/7 | - | - |
| always_none | - | - | 0/7 | - | - | - |
| structure_prior | 6/7 | 6/7 | 5/7 | 6/7 | 0.465 (5) | - |
| mafa_primary | 7/7 | 7/7 | 6/7 | 6/7 | 0.713 (5) | 0.545 |
| mafa_secondary | 5/7 | 7/7 | 5/7 | 6/7 | 0.758 (5) | 0.182 |

## MedAgentAudit · defect_any · fw=clinical_agent (rows=1)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/1 | 0/1 | 0/1 | 1/1 | 0.500 (1) | - |
| first_step | 0/1 | 0/1 | 0/1 | 1/1 | - | - |
| last_step | 0/1 | 1/1 | 0/1 | 0/1 | - | - |
| always_none | - | - | 0/1 | - | - | - |
| structure_prior | 0/1 | 0/1 | 0/1 | 1/1 | 0.375 (1) | - |
| mafa_primary | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | 1.0 |
| mafa_secondary | 1/1 | 1/1 | 1/1 | 1/1 | 0.875 (1) | 0.0 |

## MedAgentAudit · defect_any · fw=dylan (rows=1)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/1 | 0/1 | 0/1 | 0/1 | 0.333 (1) | - |
| first_step | 1/1 | 1/1 | 0/1 | 0/1 | - | - |
| last_step | 0/1 | 0/1 | 0/1 | 1/1 | - | - |
| always_none | - | - | 0/1 | - | - | - |
| structure_prior | 1/1 | 1/1 | 0/1 | 0/1 | 0.333 (1) | - |
| mafa_primary | 1/1 | 1/1 | 0/1 | 0/1 | 0.667 (1) | 1.0 |
| mafa_secondary | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | 0.0 |

## MedAgentAudit · defect_any · fw=mdagents (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/5 | 5/5 | 3/5 | 4/5 | 0.556 (3) | - |
| first_step | 5/5 | 5/5 | 5/5 | 5/5 | - | - |
| last_step | 0/5 | 4/5 | 0/5 | 0/5 | - | - |
| always_none | - | - | 0/5 | - | - | - |
| structure_prior | 5/5 | 5/5 | 5/5 | 5/5 | 0.539 (3) | - |
| mafa_primary | 5/5 | 5/5 | 5/5 | 5/5 | 0.633 (3) | 0.375 |
| mafa_secondary | 3/5 | 5/5 | 3/5 | 4/5 | 0.639 (3) | 0.235 |

## MedAgentAudit · defect_any · split=faulty (rows=7)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/7 | 5/7 | 3/7 | 5/7 | 0.500 (5) | - |
| first_step | 6/7 | 6/7 | 5/7 | 6/7 | - | - |
| last_step | 0/7 | 5/7 | 0/7 | 1/7 | - | - |
| always_none | - | - | 0/7 | - | - | - |
| structure_prior | 6/7 | 6/7 | 5/7 | 6/7 | 0.465 (5) | - |
| mafa_primary | 7/7 | 7/7 | 6/7 | 6/7 | 0.713 (5) | 0.545 |
| mafa_secondary | 5/7 | 7/7 | 5/7 | 6/7 | 0.758 (5) | 0.182 |
