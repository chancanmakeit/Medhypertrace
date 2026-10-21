# MAFA evaluation · subset=dev · source=llm · rows=19
labels `results/human_like_eval_v2/labels_v2.jsonl` sha256 e10dc633b405 · split 916fee301529

Every number is computed within ONE taxonomy: MAST and MedAgentAudit labels are different label definitions (and the same trace can appear under both), so rows are never pooled across them. MedHyperTrace is trained on MAST-coded synthetic data only and has no MedAgentAudit code head.

# MAST (rows=10)

## MAST · defect · all (rows=10)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/8 | 3/8 | 3/10 | 3/7 | 0.480 (8) | 0.167 |
| first_step | 2/8 | 2/8 | 2/10 | 2/8 | - | - |
| last_step | 1/8 | 5/8 | 1/10 | 1/8 | - | - |
| always_none | - | - | 2/10 | - | - | - |
| structure_prior | 3/8 | 3/8 | 3/10 | 3/8 | 0.445 (8) | - |
| mafa_primary | 6/8 | 6/8 | 8/10 | 6/7 | 0.833 (8) | 0.88 |
| mafa_secondary | 5/8 | 5/8 | 6/10 | 4/4 | 0.688 (8) | 0.455 |

## MAST · defect · no_leak (rows=7)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/6 | 3/6 | 2/7 | 2/5 | 0.515 (6) | 0.062 |
| first_step | 1/6 | 1/6 | 1/7 | 1/6 | - | - |
| last_step | 1/6 | 3/6 | 1/7 | 1/6 | - | - |
| always_none | - | - | 1/7 | - | - | - |
| structure_prior | 2/6 | 2/6 | 2/7 | 2/6 | 0.518 (6) | - |
| mafa_primary | 4/6 | 4/6 | 5/7 | 4/5 | 0.819 (6) | 0.8 |
| mafa_secondary | 3/6 | 3/6 | 3/7 | 2/2 | 0.667 (6) | 0.167 |

## MAST · defect · fw=clinical_agent (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/3 | 1/3 | 0/3 | 0/2 | 0.496 (3) | 0.0 |
| first_step | 0/3 | 0/3 | 0/3 | 0/3 | - | - |
| last_step | 0/3 | 1/3 | 0/3 | 0/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 0/3 | 0/3 | 0/3 | 0/3 | 0.419 (3) | - |
| mafa_primary | 3/3 | 3/3 | 3/3 | 3/3 | 0.944 (3) | 0.857 |
| mafa_secondary | 2/3 | 2/3 | 2/3 | 2/2 | 0.833 (3) | 0.286 |

## MAST · defect · fw=clinical_agent5 (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/1 | 1/1 | 2/3 | 1/1 | 1.000 (1) | 0.0 |
| first_step | 0/1 | 0/1 | 0/3 | 0/1 | - | - |
| last_step | 0/1 | 1/1 | 0/3 | 0/1 | - | - |
| always_none | - | - | 2/3 | - | - | - |
| structure_prior | 1/1 | 1/1 | 1/3 | 1/1 | 1.000 (1) | - |
| mafa_primary | 0/1 | 0/1 | 2/3 | - | 0.500 (1) | 0.0 |
| mafa_secondary | 0/1 | 0/1 | 2/3 | - | 0.500 (1) | 0.0 |

## MAST · defect · fw=dylan (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/2 | 0/2 | 0/2 | 0/2 | 0.375 (2) | 0.0 |
| first_step | 0/2 | 0/2 | 0/2 | 0/2 | - | - |
| last_step | 1/2 | 2/2 | 1/2 | 1/2 | - | - |
| always_none | - | - | 0/2 | - | - | - |
| structure_prior | 0/2 | 0/2 | 0/2 | 0/2 | 0.125 (2) | - |
| mafa_primary | 1/2 | 1/2 | 1/2 | 1/2 | 0.792 (2) | 1.0 |
| mafa_secondary | 1/2 | 1/2 | 1/2 | 1/1 | 0.500 (2) | 0.667 |

## MAST · defect · fw=mdagents (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/2 | 1/2 | 1/2 | 2/2 | 0.300 (2) | 0.421 |
| first_step | 2/2 | 2/2 | 2/2 | 2/2 | - | - |
| last_step | 0/2 | 1/2 | 0/2 | 0/2 | - | - |
| always_none | - | - | 0/2 | - | - | - |
| structure_prior | 2/2 | 2/2 | 2/2 | 2/2 | 0.529 (2) | - |
| mafa_primary | 2/2 | 2/2 | 2/2 | 2/2 | 0.875 (2) | 1.0 |
| mafa_secondary | 2/2 | 2/2 | 1/2 | 1/1 | 0.750 (2) | 0.6 |

## MAST · defect · split=clean (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/3 | 0/3 | 1/5 | 1/3 | 0.200 (3) | 0.25 |
| first_step | 1/3 | 1/3 | 1/5 | 1/3 | - | - |
| last_step | 1/3 | 2/3 | 1/5 | 1/3 | - | - |
| always_none | - | - | 2/5 | - | - | - |
| structure_prior | 1/3 | 1/3 | 1/5 | 1/3 | 0.136 (3) | - |
| mafa_primary | 2/3 | 2/3 | 4/5 | 2/3 | 0.944 (3) | 1.0 |
| mafa_secondary | 1/3 | 1/3 | 3/5 | 1/1 | 0.667 (3) | 0.6 |

## MAST · defect · split=faulty (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/5 | 3/5 | 2/5 | 2/4 | 0.648 (5) | 0.083 |
| first_step | 1/5 | 1/5 | 1/5 | 1/5 | - | - |
| last_step | 0/5 | 3/5 | 0/5 | 0/5 | - | - |
| always_none | - | - | 0/5 | - | - | - |
| structure_prior | 2/5 | 2/5 | 2/5 | 2/5 | 0.631 (5) | - |
| mafa_primary | 4/5 | 4/5 | 4/5 | 4/4 | 0.767 (5) | 0.769 |
| mafa_secondary | 4/5 | 4/5 | 3/5 | 3/3 | 0.700 (5) | 0.333 |

## MAST · defect_any · all (rows=10)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/8 | 3/8 | 3/10 | 4/7 | 0.480 (8) | 0.167 |
| first_step | 2/8 | 2/8 | 2/10 | 3/8 | - | - |
| last_step | 2/8 | 5/8 | 1/10 | 1/8 | - | - |
| always_none | - | - | 2/10 | - | - | - |
| structure_prior | 3/8 | 3/8 | 3/10 | 4/8 | 0.445 (8) | - |
| mafa_primary | 5/8 | 6/8 | 7/10 | 6/7 | 0.833 (8) | 0.88 |
| mafa_secondary | 4/8 | 5/8 | 5/10 | 4/4 | 0.688 (8) | 0.455 |

## MAST · defect_any · no_leak (rows=7)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/6 | 3/6 | 2/7 | 2/5 | 0.515 (6) | 0.062 |
| first_step | 1/6 | 1/6 | 1/7 | 1/6 | - | - |
| last_step | 1/6 | 3/6 | 1/7 | 1/6 | - | - |
| always_none | - | - | 1/7 | - | - | - |
| structure_prior | 2/6 | 2/6 | 2/7 | 2/6 | 0.518 (6) | - |
| mafa_primary | 4/6 | 4/6 | 5/7 | 4/5 | 0.819 (6) | 0.8 |
| mafa_secondary | 3/6 | 3/6 | 3/7 | 2/2 | 0.667 (6) | 0.167 |

## MAST · defect_any · fw=clinical_agent (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/3 | 1/3 | 0/3 | 0/2 | 0.496 (3) | 0.0 |
| first_step | 0/3 | 0/3 | 0/3 | 0/3 | - | - |
| last_step | 0/3 | 1/3 | 0/3 | 0/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 0/3 | 0/3 | 0/3 | 0/3 | 0.419 (3) | - |
| mafa_primary | 3/3 | 3/3 | 3/3 | 3/3 | 0.944 (3) | 0.857 |
| mafa_secondary | 2/3 | 2/3 | 2/3 | 2/2 | 0.833 (3) | 0.286 |

## MAST · defect_any · fw=clinical_agent5 (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/1 | 1/1 | 2/3 | 1/1 | 1.000 (1) | 0.0 |
| first_step | 0/1 | 0/1 | 0/3 | 0/1 | - | - |
| last_step | 0/1 | 1/1 | 0/3 | 0/1 | - | - |
| always_none | - | - | 2/3 | - | - | - |
| structure_prior | 1/1 | 1/1 | 1/3 | 1/1 | 1.000 (1) | - |
| mafa_primary | 0/1 | 0/1 | 2/3 | - | 0.500 (1) | 0.0 |
| mafa_secondary | 0/1 | 0/1 | 2/3 | - | 0.500 (1) | 0.0 |

## MAST · defect_any · fw=dylan (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/2 | 0/2 | 0/2 | 1/2 | 0.375 (2) | 0.0 |
| first_step | 0/2 | 0/2 | 0/2 | 1/2 | - | - |
| last_step | 2/2 | 2/2 | 1/2 | 1/2 | - | - |
| always_none | - | - | 0/2 | - | - | - |
| structure_prior | 0/2 | 0/2 | 0/2 | 1/2 | 0.125 (2) | - |
| mafa_primary | 0/2 | 1/2 | 0/2 | 1/2 | 0.792 (2) | 1.0 |
| mafa_secondary | 0/2 | 1/2 | 0/2 | 1/1 | 0.500 (2) | 0.667 |

## MAST · defect_any · fw=mdagents (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/2 | 1/2 | 1/2 | 2/2 | 0.300 (2) | 0.421 |
| first_step | 2/2 | 2/2 | 2/2 | 2/2 | - | - |
| last_step | 0/2 | 1/2 | 0/2 | 0/2 | - | - |
| always_none | - | - | 0/2 | - | - | - |
| structure_prior | 2/2 | 2/2 | 2/2 | 2/2 | 0.529 (2) | - |
| mafa_primary | 2/2 | 2/2 | 2/2 | 2/2 | 0.875 (2) | 1.0 |
| mafa_secondary | 2/2 | 2/2 | 1/2 | 1/1 | 0.750 (2) | 0.6 |

## MAST · defect_any · split=clean (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/3 | 0/3 | 1/5 | 1/3 | 0.200 (3) | 0.25 |
| first_step | 1/3 | 1/3 | 1/5 | 1/3 | - | - |
| last_step | 1/3 | 2/3 | 1/5 | 1/3 | - | - |
| always_none | - | - | 2/5 | - | - | - |
| structure_prior | 1/3 | 1/3 | 1/5 | 1/3 | 0.136 (3) | - |
| mafa_primary | 2/3 | 2/3 | 4/5 | 2/3 | 0.944 (3) | 1.0 |
| mafa_secondary | 1/3 | 1/3 | 3/5 | 1/1 | 0.667 (3) | 0.6 |

## MAST · defect_any · split=faulty (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/5 | 3/5 | 2/5 | 3/4 | 0.648 (5) | 0.083 |
| first_step | 1/5 | 1/5 | 1/5 | 2/5 | - | - |
| last_step | 1/5 | 3/5 | 0/5 | 0/5 | - | - |
| always_none | - | - | 0/5 | - | - | - |
| structure_prior | 2/5 | 2/5 | 2/5 | 3/5 | 0.631 (5) | - |
| mafa_primary | 3/5 | 4/5 | 3/5 | 4/4 | 0.767 (5) | 0.769 |
| mafa_secondary | 3/5 | 4/5 | 2/5 | 3/3 | 0.700 (5) | 0.333 |

## MAST · responsibility · all (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/3 | 2/3 | 1/3 | 1/2 | 0.708 (3) | - |
| first_step | 0/3 | 0/3 | 0/3 | 0/3 | - | - |
| last_step | 0/3 | 2/3 | 0/3 | 0/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 1/3 | 1/3 | 1/3 | 1/3 | 0.708 (3) | - |
| mafa_primary | 2/3 | 2/3 | 2/3 | 2/2 | 0.708 (3) | - |
| mafa_secondary | 2/3 | 2/3 | 2/3 | 2/2 | 0.792 (3) | - |

## MAST · responsibility · no_leak (rows=4)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/3 | 2/3 | 1/3 | 1/2 | 0.708 (3) | - |
| first_step | 0/3 | 0/3 | 0/3 | 0/3 | - | - |
| last_step | 0/3 | 2/3 | 0/3 | 0/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 1/3 | 1/3 | 1/3 | 1/3 | 0.708 (3) | - |
| mafa_primary | 2/3 | 2/3 | 2/3 | 2/2 | 0.708 (3) | - |
| mafa_secondary | 2/3 | 2/3 | 2/3 | 2/2 | 0.792 (3) | - |

## MAST · responsibility · fw=clinical_agent (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/2 | 1/2 | 0/2 | 0/1 | 0.562 (2) | - |
| first_step | 0/2 | 0/2 | 0/2 | 0/2 | - | - |
| last_step | 0/2 | 1/2 | 0/2 | 0/2 | - | - |
| always_none | - | - | 0/2 | - | - | - |
| structure_prior | 0/2 | 0/2 | 0/2 | 0/2 | 0.562 (2) | - |
| mafa_primary | 2/2 | 2/2 | 2/2 | 2/2 | 0.812 (2) | - |
| mafa_secondary | 2/2 | 2/2 | 2/2 | 2/2 | 0.938 (2) | - |

## MAST · responsibility · fw=clinical_agent5 (rows=1)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | - |
| first_step | 0/1 | 0/1 | 0/1 | 0/1 | - | - |
| last_step | 0/1 | 1/1 | 0/1 | 0/1 | - | - |
| always_none | - | - | 0/1 | - | - | - |
| structure_prior | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | - |
| mafa_primary | 0/1 | 0/1 | 0/1 | - | 0.500 (1) | - |
| mafa_secondary | 0/1 | 0/1 | 0/1 | - | 0.500 (1) | - |

## MAST · responsibility · fw=dylan (rows=1)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | - | - | - | - | - | - |
| first_step | - | - | - | - | - | - |
| last_step | - | - | - | - | - | - |
| always_none | - | - | - | - | - | - |
| structure_prior | - | - | - | - | - | - |
| mafa_primary | - | - | - | - | - | - |
| mafa_secondary | - | - | - | - | - | - |

## MAST · responsibility · fw=mdagents (rows=1)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | - | - | - | - | - | - |
| first_step | - | - | - | - | - | - |
| last_step | - | - | - | - | - | - |
| always_none | - | - | - | - | - | - |
| structure_prior | - | - | - | - | - | - |
| mafa_primary | - | - | - | - | - | - |
| mafa_secondary | - | - | - | - | - | - |

## MAST · responsibility_any · all (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/4 | 2/4 | 1/4 | 2/3 | 0.573 (4) | - |
| first_step | 0/4 | 0/4 | 0/4 | 1/4 | - | - |
| last_step | 0/4 | 2/4 | 0/4 | 0/4 | - | - |
| always_none | - | - | 0/4 | - | - | - |
| structure_prior | 1/4 | 1/4 | 1/4 | 2/4 | 0.781 (4) | - |
| mafa_primary | 2/4 | 2/4 | 2/4 | 3/3 | 0.635 (4) | - |
| mafa_secondary | 2/4 | 2/4 | 2/4 | 2/2 | 0.719 (4) | - |

## MAST · responsibility_any · no_leak (rows=4)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/4 | 2/4 | 1/4 | 2/3 | 0.573 (4) | - |
| first_step | 0/4 | 0/4 | 0/4 | 1/4 | - | - |
| last_step | 0/4 | 2/4 | 0/4 | 0/4 | - | - |
| always_none | - | - | 0/4 | - | - | - |
| structure_prior | 1/4 | 1/4 | 1/4 | 2/4 | 0.781 (4) | - |
| mafa_primary | 2/4 | 2/4 | 2/4 | 3/3 | 0.635 (4) | - |
| mafa_secondary | 2/4 | 2/4 | 2/4 | 2/2 | 0.719 (4) | - |

## MAST · responsibility_any · fw=clinical_agent (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/2 | 1/2 | 0/2 | 0/1 | 0.562 (2) | - |
| first_step | 0/2 | 0/2 | 0/2 | 0/2 | - | - |
| last_step | 0/2 | 1/2 | 0/2 | 0/2 | - | - |
| always_none | - | - | 0/2 | - | - | - |
| structure_prior | 0/2 | 0/2 | 0/2 | 0/2 | 0.562 (2) | - |
| mafa_primary | 2/2 | 2/2 | 2/2 | 2/2 | 0.812 (2) | - |
| mafa_secondary | 2/2 | 2/2 | 2/2 | 2/2 | 0.938 (2) | - |

## MAST · responsibility_any · fw=clinical_agent5 (rows=1)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | - |
| first_step | 0/1 | 0/1 | 0/1 | 0/1 | - | - |
| last_step | 0/1 | 1/1 | 0/1 | 0/1 | - | - |
| always_none | - | - | 0/1 | - | - | - |
| structure_prior | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | - |
| mafa_primary | 0/1 | 0/1 | 0/1 | - | 0.500 (1) | - |
| mafa_secondary | 0/1 | 0/1 | 0/1 | - | 0.500 (1) | - |

## MAST · responsibility_any · fw=dylan (rows=1)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | - | - | - | - | - | - |
| first_step | - | - | - | - | - | - |
| last_step | - | - | - | - | - | - |
| always_none | - | - | - | - | - | - |
| structure_prior | - | - | - | - | - | - |
| mafa_primary | - | - | - | - | - | - |
| mafa_secondary | - | - | - | - | - | - |

## MAST · responsibility_any · fw=mdagents (rows=1)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/1 | 0/1 | 0/1 | 1/1 | 0.167 (1) | - |
| first_step | 0/1 | 0/1 | 0/1 | 1/1 | - | - |
| last_step | 0/1 | 0/1 | 0/1 | 0/1 | - | - |
| always_none | - | - | 0/1 | - | - | - |
| structure_prior | 0/1 | 0/1 | 0/1 | 1/1 | 1.000 (1) | - |
| mafa_primary | 0/1 | 0/1 | 0/1 | 1/1 | 0.417 (1) | - |
| mafa_secondary | 0/1 | 0/1 | 0/1 | - | 0.500 (1) | - |

# MedAgentAudit (rows=9)

## MedAgentAudit · defect · all (rows=9)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/6 | 4/7 | 4/9 | 5/6 | 0.651 (6) | - |
| first_step | 4/6 | 4/7 | 3/9 | 4/6 | - | - |
| last_step | 0/6 | 5/7 | 0/9 | 1/6 | - | - |
| always_none | - | - | 3/9 | - | - | - |
| structure_prior | 4/6 | 5/7 | 3/9 | 4/6 | 0.525 (6) | - |
| mafa_primary | 6/6 | 7/7 | 7/9 | 5/5 | 0.858 (6) | 0.706 |
| mafa_secondary | 3/6 | 4/7 | 5/9 | 2/3 | 0.625 (6) | 0.154 |

## MedAgentAudit · defect · no_leak (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/4 | 3/5 | 3/5 | 3/4 | 0.656 (4) | - |
| first_step | 3/4 | 3/5 | 2/5 | 2/4 | - | - |
| last_step | 0/4 | 5/5 | 0/5 | 1/4 | - | - |
| always_none | - | - | 1/5 | - | - | - |
| structure_prior | 3/4 | 3/5 | 2/5 | 2/4 | 0.575 (4) | - |
| mafa_primary | 4/4 | 5/5 | 4/5 | 4/4 | 0.975 (4) | 0.714 |
| mafa_secondary | 2/4 | 3/5 | 3/5 | 2/3 | 0.688 (4) | 0.182 |

## MedAgentAudit · defect · fw=clinical_agent (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/1 | 0/2 | 1/2 | 1/1 | 0.738 (2) | - |
| first_step | 0/1 | 0/2 | 0/2 | 0/1 | - | - |
| last_step | 0/1 | 2/2 | 0/2 | 0/1 | - | - |
| always_none | - | - | 1/2 | - | - | - |
| structure_prior | 0/1 | 0/2 | 0/2 | 0/1 | 0.775 (2) | - |
| mafa_primary | 1/1 | 2/2 | 1/2 | 1/1 | 1.000 (2) | 1.0 |
| mafa_secondary | 0/1 | 0/2 | 1/2 | - | 0.500 (2) | 0.0 |

## MedAgentAudit · defect · fw=clinical_agent5 (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/1 | 1/1 | 0/2 | 1/1 | 0.833 (1) | - |
| first_step | 0/1 | 0/1 | 0/2 | 1/1 | - | - |
| last_step | 0/1 | 0/1 | 0/2 | 0/1 | - | - |
| always_none | - | - | 1/2 | - | - | - |
| structure_prior | 0/1 | 1/1 | 0/2 | 1/1 | 0.500 (1) | - |
| mafa_primary | 1/1 | 1/1 | 2/2 | 1/1 | 0.750 (1) | 1.0 |
| mafa_secondary | 0/1 | 0/1 | 1/2 | - | 0.500 (1) | 0.0 |

## MedAgentAudit · defect · fw=dylan (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/1 | 1/1 | 1/2 | 0/1 | 0.750 (1) | - |
| first_step | 1/1 | 1/1 | 0/2 | 0/1 | - | - |
| last_step | 0/1 | 1/1 | 0/2 | 1/1 | - | - |
| always_none | - | - | 1/2 | - | - | - |
| structure_prior | 1/1 | 1/1 | 0/2 | 0/1 | 0.500 (1) | - |
| mafa_primary | 1/1 | 1/1 | 2/2 | 1/1 | 1.000 (1) | 1.0 |
| mafa_secondary | 1/1 | 1/1 | 2/2 | 1/1 | 1.000 (1) | 0.0 |

## MedAgentAudit · defect · fw=mdagents (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/3 | 2/3 | 2/3 | 3/3 | 0.425 (2) | - |
| first_step | 3/3 | 3/3 | 3/3 | 3/3 | - | - |
| last_step | 0/3 | 2/3 | 0/3 | 0/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 3/3 | 3/3 | 3/3 | 3/3 | 0.300 (2) | - |
| mafa_primary | 3/3 | 3/3 | 2/3 | 2/2 | 0.700 (2) | 0.444 |
| mafa_secondary | 2/3 | 3/3 | 1/3 | 1/2 | 0.625 (2) | 0.25 |

## MedAgentAudit · defect · split=clean (rows=4)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/3 | 1/3 | 1/4 | 3/3 | 0.719 (3) | - |
| first_step | 1/3 | 1/3 | 1/4 | 2/3 | - | - |
| last_step | 0/3 | 1/3 | 0/4 | 0/3 | - | - |
| always_none | - | - | 1/4 | - | - | - |
| structure_prior | 1/3 | 2/3 | 1/4 | 2/3 | 0.533 (3) | - |
| mafa_primary | 3/3 | 3/3 | 3/4 | 2/2 | 0.750 (3) | 0.857 |
| mafa_secondary | 1/3 | 1/3 | 1/4 | - | 0.500 (3) | 0.0 |

## MedAgentAudit · defect · split=faulty (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/3 | 3/4 | 3/5 | 2/3 | 0.583 (3) | - |
| first_step | 3/3 | 3/4 | 2/5 | 2/3 | - | - |
| last_step | 0/3 | 4/4 | 0/5 | 1/3 | - | - |
| always_none | - | - | 2/5 | - | - | - |
| structure_prior | 3/3 | 3/4 | 2/5 | 2/3 | 0.517 (3) | - |
| mafa_primary | 3/3 | 4/4 | 4/5 | 3/3 | 0.967 (3) | 0.6 |
| mafa_secondary | 2/3 | 3/4 | 4/5 | 2/3 | 0.750 (3) | 0.222 |

## MedAgentAudit · defect_any · all (rows=9)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/7 | 4/7 | 3/9 | 5/6 | 0.651 (6) | - |
| first_step | 4/7 | 4/7 | 3/9 | 4/7 | - | - |
| last_step | 1/7 | 5/7 | 1/9 | 2/7 | - | - |
| always_none | - | - | 2/9 | - | - | - |
| structure_prior | 4/7 | 5/7 | 3/9 | 4/7 | 0.525 (6) | - |
| mafa_primary | 7/7 | 7/7 | 8/9 | 6/6 | 0.858 (6) | 0.706 |
| mafa_secondary | 3/7 | 4/7 | 4/9 | 2/3 | 0.625 (6) | 0.154 |

## MedAgentAudit · defect_any · no_leak (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/5 | 3/5 | 2/5 | 3/4 | 0.656 (4) | - |
| first_step | 3/5 | 3/5 | 2/5 | 2/5 | - | - |
| last_step | 1/5 | 5/5 | 1/5 | 2/5 | - | - |
| always_none | - | - | 0/5 | - | - | - |
| structure_prior | 3/5 | 3/5 | 2/5 | 2/5 | 0.575 (4) | - |
| mafa_primary | 5/5 | 5/5 | 5/5 | 5/5 | 0.975 (4) | 0.714 |
| mafa_secondary | 2/5 | 3/5 | 2/5 | 2/3 | 0.688 (4) | 0.182 |

## MedAgentAudit · defect_any · fw=clinical_agent (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/2 | 0/2 | 0/2 | 1/1 | 0.738 (2) | - |
| first_step | 0/2 | 0/2 | 0/2 | 0/2 | - | - |
| last_step | 1/2 | 2/2 | 1/2 | 1/2 | - | - |
| always_none | - | - | 0/2 | - | - | - |
| structure_prior | 0/2 | 0/2 | 0/2 | 0/2 | 0.775 (2) | - |
| mafa_primary | 2/2 | 2/2 | 2/2 | 2/2 | 1.000 (2) | 1.0 |
| mafa_secondary | 0/2 | 0/2 | 0/2 | - | 0.500 (2) | 0.0 |

## MedAgentAudit · defect_any · fw=clinical_agent5 (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/1 | 1/1 | 0/2 | 1/1 | 0.833 (1) | - |
| first_step | 0/1 | 0/1 | 0/2 | 1/1 | - | - |
| last_step | 0/1 | 0/1 | 0/2 | 0/1 | - | - |
| always_none | - | - | 1/2 | - | - | - |
| structure_prior | 0/1 | 1/1 | 0/2 | 1/1 | 0.500 (1) | - |
| mafa_primary | 1/1 | 1/1 | 2/2 | 1/1 | 0.750 (1) | 1.0 |
| mafa_secondary | 0/1 | 0/1 | 1/2 | - | 0.500 (1) | 0.0 |

## MedAgentAudit · defect_any · fw=dylan (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/1 | 1/1 | 1/2 | 0/1 | 0.750 (1) | - |
| first_step | 1/1 | 1/1 | 0/2 | 0/1 | - | - |
| last_step | 0/1 | 1/1 | 0/2 | 1/1 | - | - |
| always_none | - | - | 1/2 | - | - | - |
| structure_prior | 1/1 | 1/1 | 0/2 | 0/1 | 0.500 (1) | - |
| mafa_primary | 1/1 | 1/1 | 2/2 | 1/1 | 1.000 (1) | 1.0 |
| mafa_secondary | 1/1 | 1/1 | 2/2 | 1/1 | 1.000 (1) | 0.0 |

## MedAgentAudit · defect_any · fw=mdagents (rows=3)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 2/3 | 2/3 | 2/3 | 3/3 | 0.425 (2) | - |
| first_step | 3/3 | 3/3 | 3/3 | 3/3 | - | - |
| last_step | 0/3 | 2/3 | 0/3 | 0/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 3/3 | 3/3 | 3/3 | 3/3 | 0.300 (2) | - |
| mafa_primary | 3/3 | 3/3 | 2/3 | 2/2 | 0.700 (2) | 0.444 |
| mafa_secondary | 2/3 | 3/3 | 1/3 | 1/2 | 0.625 (2) | 0.25 |

## MedAgentAudit · defect_any · split=clean (rows=4)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/3 | 1/3 | 1/4 | 3/3 | 0.719 (3) | - |
| first_step | 1/3 | 1/3 | 1/4 | 2/3 | - | - |
| last_step | 0/3 | 1/3 | 0/4 | 0/3 | - | - |
| always_none | - | - | 1/4 | - | - | - |
| structure_prior | 1/3 | 2/3 | 1/4 | 2/3 | 0.533 (3) | - |
| mafa_primary | 3/3 | 3/3 | 3/4 | 2/2 | 0.750 (3) | 0.857 |
| mafa_secondary | 1/3 | 1/3 | 1/4 | - | 0.500 (3) | 0.0 |

## MedAgentAudit · defect_any · split=faulty (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 3/4 | 3/4 | 2/5 | 2/3 | 0.583 (3) | - |
| first_step | 3/4 | 3/4 | 2/5 | 2/4 | - | - |
| last_step | 1/4 | 4/4 | 1/5 | 2/4 | - | - |
| always_none | - | - | 1/5 | - | - | - |
| structure_prior | 3/4 | 3/4 | 2/5 | 2/4 | 0.517 (3) | - |
| mafa_primary | 4/4 | 4/4 | 5/5 | 4/4 | 0.967 (3) | 0.6 |
| mafa_secondary | 2/4 | 3/4 | 3/5 | 2/3 | 0.750 (3) | 0.222 |

## MedAgentAudit · responsibility · all (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/3 | 1/3 | 0/3 | 0/3 | 0.350 (3) | - |
| first_step | 1/3 | 1/3 | 0/3 | 0/3 | - | - |
| last_step | 1/3 | 3/3 | 1/3 | 2/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 1/3 | 1/3 | 0/3 | 0/3 | 0.200 (3) | - |
| mafa_primary | 1/3 | 1/3 | 1/3 | 1/3 | 0.761 (3) | - |
| mafa_secondary | 2/3 | 2/3 | 2/3 | 2/3 | 0.750 (3) | - |

## MedAgentAudit · responsibility · no_leak (rows=4)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/3 | 1/3 | 0/3 | 0/3 | 0.350 (3) | - |
| first_step | 1/3 | 1/3 | 0/3 | 0/3 | - | - |
| last_step | 1/3 | 3/3 | 1/3 | 2/3 | - | - |
| always_none | - | - | 0/3 | - | - | - |
| structure_prior | 1/3 | 1/3 | 0/3 | 0/3 | 0.200 (3) | - |
| mafa_primary | 1/3 | 1/3 | 1/3 | 1/3 | 0.761 (3) | - |
| mafa_secondary | 2/3 | 2/3 | 2/3 | 2/3 | 0.750 (3) | - |

## MedAgentAudit · responsibility · fw=clinical_agent (rows=1)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | - | - | - | - | - | - |
| first_step | - | - | - | - | - | - |
| last_step | - | - | - | - | - | - |
| always_none | - | - | - | - | - | - |
| structure_prior | - | - | - | - | - | - |
| mafa_primary | - | - | - | - | - | - |
| mafa_secondary | - | - | - | - | - | - |

## MedAgentAudit · responsibility · fw=clinical_agent5 (rows=1)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | - | - | - | - | - | - |
| first_step | - | - | - | - | - | - |
| last_step | - | - | - | - | - | - |
| always_none | - | - | - | - | - | - |
| structure_prior | - | - | - | - | - | - |
| mafa_primary | - | - | - | - | - | - |
| mafa_secondary | - | - | - | - | - | - |

## MedAgentAudit · responsibility · fw=dylan (rows=1)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/1 | 1/1 | 0/1 | 0/1 | 0.750 (1) | - |
| first_step | 1/1 | 1/1 | 0/1 | 0/1 | - | - |
| last_step | 0/1 | 1/1 | 0/1 | 1/1 | - | - |
| always_none | - | - | 0/1 | - | - | - |
| structure_prior | 1/1 | 1/1 | 0/1 | 0/1 | 0.500 (1) | - |
| mafa_primary | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | - |
| mafa_secondary | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | - |

## MedAgentAudit · responsibility · fw=mdagents (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/2 | 0/2 | 0/2 | 0/2 | 0.150 (2) | - |
| first_step | 0/2 | 0/2 | 0/2 | 0/2 | - | - |
| last_step | 1/2 | 2/2 | 1/2 | 1/2 | - | - |
| always_none | - | - | 0/2 | - | - | - |
| structure_prior | 0/2 | 0/2 | 0/2 | 0/2 | 0.050 (2) | - |
| mafa_primary | 0/2 | 0/2 | 0/2 | 0/2 | 0.642 (2) | - |
| mafa_secondary | 1/2 | 1/2 | 1/2 | 1/2 | 0.625 (2) | - |

## MedAgentAudit · responsibility_any · all (rows=5)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/4 | 1/4 | 0/4 | 0/3 | 0.412 (4) | - |
| first_step | 1/4 | 1/4 | 0/4 | 0/4 | - | - |
| last_step | 2/4 | 4/4 | 2/4 | 3/4 | - | - |
| always_none | - | - | 0/4 | - | - | - |
| structure_prior | 1/4 | 1/4 | 0/4 | 0/4 | 0.350 (4) | - |
| mafa_primary | 2/4 | 2/4 | 2/4 | 2/4 | 0.821 (4) | - |
| mafa_secondary | 2/4 | 2/4 | 2/4 | 2/3 | 0.688 (4) | - |

## MedAgentAudit · responsibility_any · no_leak (rows=4)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/4 | 1/4 | 0/4 | 0/3 | 0.412 (4) | - |
| first_step | 1/4 | 1/4 | 0/4 | 0/4 | - | - |
| last_step | 2/4 | 4/4 | 2/4 | 3/4 | - | - |
| always_none | - | - | 0/4 | - | - | - |
| structure_prior | 1/4 | 1/4 | 0/4 | 0/4 | 0.350 (4) | - |
| mafa_primary | 2/4 | 2/4 | 2/4 | 2/4 | 0.821 (4) | - |
| mafa_secondary | 2/4 | 2/4 | 2/4 | 2/3 | 0.688 (4) | - |

## MedAgentAudit · responsibility_any · fw=clinical_agent (rows=1)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/1 | 0/1 | 0/1 | - | 0.600 (1) | - |
| first_step | 0/1 | 0/1 | 0/1 | 0/1 | - | - |
| last_step | 1/1 | 1/1 | 1/1 | 1/1 | - | - |
| always_none | - | - | 0/1 | - | - | - |
| structure_prior | 0/1 | 0/1 | 0/1 | 0/1 | 0.800 (1) | - |
| mafa_primary | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | - |
| mafa_secondary | 0/1 | 0/1 | 0/1 | - | 0.500 (1) | - |

## MedAgentAudit · responsibility_any · fw=clinical_agent5 (rows=1)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | - | - | - | - | - | - |
| first_step | - | - | - | - | - | - |
| last_step | - | - | - | - | - | - |
| always_none | - | - | - | - | - | - |
| structure_prior | - | - | - | - | - | - |
| mafa_primary | - | - | - | - | - | - |
| mafa_secondary | - | - | - | - | - | - |

## MedAgentAudit · responsibility_any · fw=dylan (rows=1)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 1/1 | 1/1 | 0/1 | 0/1 | 0.750 (1) | - |
| first_step | 1/1 | 1/1 | 0/1 | 0/1 | - | - |
| last_step | 0/1 | 1/1 | 0/1 | 1/1 | - | - |
| always_none | - | - | 0/1 | - | - | - |
| structure_prior | 1/1 | 1/1 | 0/1 | 0/1 | 0.500 (1) | - |
| mafa_primary | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | - |
| mafa_secondary | 1/1 | 1/1 | 1/1 | 1/1 | 1.000 (1) | - |

## MedAgentAudit · responsibility_any · fw=mdagents (rows=2)

| method | who_earliest | who_any | when_exact | when_pm1 | agent_auroc (n) | code_micro_f1 |
|---|---|---|---|---|---|---|
| mht | 0/2 | 0/2 | 0/2 | 0/2 | 0.150 (2) | - |
| first_step | 0/2 | 0/2 | 0/2 | 0/2 | - | - |
| last_step | 1/2 | 2/2 | 1/2 | 1/2 | - | - |
| always_none | - | - | 0/2 | - | - | - |
| structure_prior | 0/2 | 0/2 | 0/2 | 0/2 | 0.050 (2) | - |
| mafa_primary | 0/2 | 0/2 | 0/2 | 0/2 | 0.642 (2) | - |
| mafa_secondary | 1/2 | 1/2 | 1/2 | 1/2 | 0.625 (2) | - |
