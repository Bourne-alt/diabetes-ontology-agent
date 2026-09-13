# 抽取质量报告 — jbds_10_discharge_planning_guideline_with_qr_code_march_2023

- 源文件：`ontology/knowledges/pdfs/JBDS_10_Discharge_Planning_Guideline_with_QR_code_March_2023.pdf`（sha256 `7622428406f2…`）
- 目标图：`urn:dmo:extract:jbds_10_discharge_planning_guideline_with_qr_code_march_2023`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：18

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **85.9%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 85.5% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 80.4% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.16 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 403 |
| 通过校验 | 346 |
| 丢弃 | 57 |
| 消解后实体 | 299 |
| 关系边 | 21 |
| 悬空关系 | 86 |
| 合并冲突 | 103 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 29 |
| `quote_too_short` | 28 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 166 |
| riskFactor | 32 |
| lifestyleIntervention | 22 |
| complication | 18 |
| device | 17 |
| medication | 12 |
| drugClass | 10 |
| diabetesType | 8 |
| labTest | 6 |
| adverseEffect | 3 |
| contraindication | 3 |
| symptom | 2 |

## 合并冲突样例

- complication/diabetic-ketoacidosis: name: 'Diabetic Ketoacidosis' vs 'Diabetic ketoacidosis'
- complication/diabetic-ketoacidosis: mondoCode: 'MONDO:0005147' vs 'MONDO:0005040'
- complication/diabetic-ketoacidosis: definition: 'Anyone admitted for reasons directly related to diabetes management/care e.g. DKA or hypoglycaemia, should have a clear description of the reason for admission with written plan for prevention of recurrence' vs 'Diabetic ketoacidosis / hyperosmolar hyperglycaemic state'
- complication/diabetic-ketoacidosis: definition: 'Anyone admitted for reasons directly related to diabetes management/care e.g. DKA or hypoglycaemia, should have a clear description of the reason for admission with written plan for prevention of recurrence' vs 'Cause severe insulin resistance and insulin deficiency precipitating DKA in people with type 1 diabetes and unusually also in those with type 2 diabetes'
- complication/diabetic-ketoacidosis: mondoCode: 'MONDO:0005147' vs 'MONDO:0005143'
- complication/diabetic-ketoacidosis: definition: 'Anyone admitted for reasons directly related to diabetes management/care e.g. DKA or hypoglycaemia, should have a clear description of the reason for admission with written plan for prevention of recurrence' vs 'all people with type 1 diabetes; people with type 2 diabetes and history of DKA'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005148' vs 'MONDO:0005152'
- complication/hypoglycaemia: definition: 'Anyone admitted for reasons directly related to diabetes management/care e.g. DKA or hypoglycaemia, should have a clear description of the reason for admission with written plan for prevention of recurrence' vs 'Minor, self-treated hypoglycaemia'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005148' vs 'MONDO:0005147'
- complication/hypoglycaemia: affectedOrgan: 'Brain' vs 'Systemic'
- complication/hypoglycaemia: definition: 'Anyone admitted for reasons directly related to diabetes management/care e.g. DKA or hypoglycaemia, should have a clear description of the reason for admission with written plan for prevention of recurrence' vs 'The risk of hypoglycaemia'
- complication/hypoglycaemia: definition: 'Anyone admitted for reasons directly related to diabetes management/care e.g. DKA or hypoglycaemia, should have a clear description of the reason for admission with written plan for prevention of recurrence' vs 'Precipitate new onset diabetes'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005148' vs 'MONDO:0005042'
- complication/hypoglycaemia: definition: 'Anyone admitted for reasons directly related to diabetes management/care e.g. DKA or hypoglycaemia, should have a clear description of the reason for admission with written plan for prevention of recurrence' vs 'potential hypoglycaemia due to tapering doses or cessation of steroid therapy'
- complication/hypoglycaemia: name: 'Hypoglycaemia' vs 'hypoglycaemia'
- diabetesType/type-1-diabetes: definition: 'People who have been living with type 1 diabetes for many years and are becoming increasingly frail, (particularly if admission is related to struggles with diabetes management at home).' vs "Type 1 Diabetes is a condition where the body's immune system attacks and destroys the insulin-producing beta cells in the pancreas, leading to a complete lack of insulin production. This type of diabetes typically develops in childhood or adolescence, though it can occur at any age."
- diabetesType/type-1-diabetes: definition: 'People who have been living with type 1 diabetes for many years and are becoming increasingly frail, (particularly if admission is related to struggles with diabetes management at home).' vs 'all people with type 1 diabetes'
- diabetesType/type-1-diabetes: definition: 'People who have been living with type 1 diabetes for many years and are becoming increasingly frail, (particularly if admission is related to struggles with diabetes management at home).' vs 'safe management of diabetes during intercurrent illness, insulin dose adjustment, monitoring, blood ketone testing for patients with type 1 diabetes or ketosis-prone type 2 diabetes'
- riskFactor/frequent-attendances-for-diabetes-emergencies: name: 'Frequent Attendances for Diabetes Emergencies' vs 'Frequent attendances for diabetes emergencies'
- riskFactor/moderate-to-severe-frailty: name: 'Moderate to Severe Frailty' vs 'Moderate to severe frailty'

## 悬空关系样例

- `stage-1-review-each-individual-daily-in-the-morning-and-identify-people-for-discharge-to-leave-that-day` --appliesToType--> `Discharge to assess model`（未找到）
- `planning-at-the-point-of-admission-including-collecting-details-of-usual-home-circumstances-and-referral-to-services-if-necessary` --appliesToType--> `Discharge to assess model`（未找到）
- `provide-patient-information-leaflet-to-ensure-people-are-involved-in-decision-making` --appliesToType--> `Discharge to assess model`（未找到）
- `stage-2-the-details-of-how-to-discharge-people` --appliesToType--> `Discharge to assess model`（未找到）
- `inform-the-individual-carers-and-relevant-ongoing-support-providers-provide-information-leaflets` --appliesToType--> `Discharge to assess model`（未找到）
- `ward-staff-to-arrange-discharge-for-those-on-pathway-0-for-all-others-provided-details-of-needs-to-single-point-of-assessment-coordinator-who-will-decide-which-pathway-is-appropriate` --appliesToType--> `Discharge to assess model`（未找到）
- `all-people-suitable-for-discharge-to-be-transferred-to-a-discharge-lounge-asap` --appliesToType--> `Discharge to assess model`（未找到）
- `for-people-with-diabetes-this-should-include-effective-communication-between-teams-about-care-needs-in-relation-to-mealtimes-diabetes-equipment-and-contact-for-diabetes-related-issues` --appliesToType--> `Discharge to assess model`（未找到）
- `it-will-be-the-case-managers-role-to-ensure-individuals-and-their-families-are-informed-of-arrangements-transport-is-organised-settle-in-support-is-provided-where-needed-and-covid-test-results-are-available-where-required` --appliesToType--> `Discharge to assess model`（未找到）
- `stage-3-assessment-and-care-planning-at-home` --appliesToType--> `Discharge to assess model`（未找到）
- `case-manager-to-liaise-with-all-agencies-to-ensure-staff-and-infrastructure-are-available-to-meet-care-needs` --appliesToType--> `Discharge to assess model`（未找到）
- `use-of-personal-budgets-to-be-discussed-with-the-individual-and-family-if-longer-term-care-will-be-required-6-weeks` --appliesToType--> `Discharge to assess model`（未找到）
- `case-manager-to-provide-frequent-review-and-adjustments-of-care-package-according-to-need` --appliesToType--> `Discharge to assess model`（未找到）
- `nice-recommends-discharge-planning-should-start-at-the-point-of-admission-for-medical-emergencies` --citesSource--> `Discharge planning should be built into the initial assessment process and should look beyond the inpatient episode of care`（未找到）
- `this-proactive-approach-is-aimed-at-ensuring-safety-for-the-individual-at-home-or-community-facilities-and-reducing-the-risk-of-admission` --citesSource--> `Discharge planning should be built into the initial assessment process and should look beyond the inpatient episode of care`（未找到）
- `assessment-provides-the-opportunity-for-information-gathering-and-anticipation-of-potential-problems-which-allows-for-early-resolution-of-potential-barriers-to-discharge` --citesSource--> `Discharge planning should be built into the initial assessment process and should look beyond the inpatient episode of care`（未找到）
- `clear-sensitive-communication-with-the-individual-and-their-family-is-essential-especially-for-people-who-experience-a-considerable-new-loss-of-function` --citesSource--> `Discharge planning should be built into the initial assessment process and should look beyond the inpatient episode of care`（未找到）
- `lack-of-knowledge-of-diabetes-and-discharge-instructions-is-a-significant-contributor-to-early-readmission-among-people-with-diabetes` --citesSource--> `Discharge planning should be built into the initial assessment process and should look beyond the inpatient episode of care`（未找到）
- `minor-self-treated-hypoglycaemia` --increasesRiskOf--> `Poor self-management skills`（未找到）
- `learning-barriers-language-cognition-dexterity-competence-related-to-diabetes-self-management` --increasesRiskOf--> `Poor self-management skills`（未找到）
