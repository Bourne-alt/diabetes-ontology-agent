# 抽取质量报告 — jbds_05_enteral_feeding_guideline_april_2024

- 源文件：`ontology/knowledges/pdfs/JBDS_05_Enteral_Feeding_Guideline_April_2024.pdf`（sha256 `1464e4a219f4…`）
- 目标图：`urn:dmo:extract:jbds_05_enteral_feeding_guideline_april_2024`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：23

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **92.1%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 93.5% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 53.0% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.25 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 617 |
| 通过校验 | 568 |
| 丢弃 | 49 |
| 消解后实体 | 454 |
| 关系边 | 118 |
| 悬空关系 | 133 |
| 合并冲突 | 257 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 35 |
| `quote_too_short` | 9 |
| `unknown_relation_predicate` | 5 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 233 |
| riskFactor | 47 |
| medication | 43 |
| contraindication | 32 |
| drugClass | 31 |
| device | 13 |
| symptom | 13 |
| labTest | 10 |
| monitoringSchedule | 9 |
| diabetesType | 8 |
| complication | 6 |
| complicationStage | 4 |
| adverseEffect | 3 |
| lifestyleIntervention | 2 |

## 合并冲突样例

- diabetesType/type-3c-secondary-diabetes: insulinRequired: True vs False
- diabetesType/type-3c-secondary-diabetes: definition: 'Type 3c/Secondary diabetes' vs 'Following pancreatitis or other pancreatic damage, insulin production can vary considerably between individuals. Some will be entirely insulin deficient (treat as type 1) whereas others may have significant insulin reserve (treat as type 2). It may not be clear at the time of feeding which applies. Pancreatic exocrine insufficiency may also be present. This may influence the rate of carbohydrate absorption of the feed and influence overall glucose control.'
- labTest/capillary-blood-glucose: definition: 'Capillary blood glucose (CBG) is used to monitor glycaemic control in people with diabetes receiving enteral feeding.' vs 'A measure of blood glucose concentration obtained from capillary blood, used to monitor glucose levels in real time.'
- labTest/capillary-blood-glucose: definition: 'Capillary blood glucose (CBG) is used to monitor glycaemic control in people with diabetes receiving enteral feeding.' vs 'A measure of blood glucose level taken from capillary blood, used to monitor glycaemic control in patients receiving enteral feeding.'
- labTest/capillary-blood-glucose: definition: 'Capillary blood glucose (CBG) is used to monitor glycaemic control in people with diabetes receiving enteral feeding.' vs 'Capillary blood glucose is used to monitor hyperglycaemia in patients receiving enteral feeding, particularly in the context of adjusting insulin regimens.'
- labTest/capillary-blood-glucose: definition: 'Capillary blood glucose (CBG) is used to monitor glycaemic control in people with diabetes receiving enteral feeding.' vs 'Capillary blood glucose persistently >12 mmol/L should be treated following the advice given in sections 4 choice of agent to achieve glycaemic control, section 5 non-insulin options and section 6, insulin options.'
- labTest/capillary-blood-glucose: definition: 'Capillary blood glucose (CBG) is used to monitor glycaemic control in people with diabetes receiving enteral feeding.' vs 'Bedside capillary blood glucose testing should be a clinical decision based on the stability of the patient.'
- labTest/capillary-blood-glucose: definition: 'Capillary blood glucose (CBG) is used to monitor glycaemic control in people with diabetes receiving enteral feeding.' vs 'A measure of blood glucose level taken from capillary blood, used to monitor glycaemic control in hospital settings.'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005147' vs 'MONDO:0005074'
- complication/hypoglycaemia: affectedOrgan: 'Systemic' vs 'Brain'
- complication/hypoglycaemia: definition: 'Variation in the inpatient management of hyperglycaemia and hypoglycaemia in people receiving enteral feeding may slow patient recovery and potentially result in further complications such as poor wound healing or super-added infection' vs 'A condition in which blood glucose levels fall below 4.0 mmol/L, leading to symptoms such as drowsiness, clamminess, and potentially life-threatening events.'
- complication/hypoglycaemia: definition: 'Variation in the inpatient management of hyperglycaemia and hypoglycaemia in people receiving enteral feeding may slow patient recovery and potentially result in further complications such as poor wound healing or super-added infection' vs 'A result of receiving feed specific insulin despite the feed being stopped.'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005147' vs 'MONDO:0005001'
- complication/hypoglycaemia: definition: 'Variation in the inpatient management of hyperglycaemia and hypoglycaemia in people receiving enteral feeding may slow patient recovery and potentially result in further complications such as poor wound healing or super-added infection' vs 'On a busy ward this is often overlooked or delayed resulting in hypoglycaemia.'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005147' vs 'MONDO:0005041'
- complication/hypoglycaemia: affectedOrgan: 'Systemic' vs 'Brain'
- complication/hypoglycaemia: definition: 'Variation in the inpatient management of hyperglycaemia and hypoglycaemia in people receiving enteral feeding may slow patient recovery and potentially result in further complications such as poor wound healing or super-added infection' vs 'to avoid hypoglycaemia'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005147' vs 'MONDO:0005148'
- complication/hypoglycaemia: definition: 'Variation in the inpatient management of hyperglycaemia and hypoglycaemia in people receiving enteral feeding may slow patient recovery and potentially result in further complications such as poor wound healing or super-added infection' vs 'Ward teams need to be aware of the risk of hypoglycaemia if the feed is stopped.'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005147' vs 'MONDO:0005041'

## 悬空关系样例

- `subcutaneous-basal-insulin` --hasContraindication--> `Type 1 Diabetes`（未找到）
- `subcutaneous-basal-insulin` --hasContraindication--> `Insulin Deficiency`（未找到）
- `subcutaneous-basal-insulin` --hasContraindication--> `Diabetic Ketoacidosis`（未找到）
- `insulin` --causesAdverseEffect--> `Hypoglycemia`（未找到）
- `insulin` --causesAdverseEffect--> `Ketosis`（未找到）
- `insulin` --hasContraindication--> `Insulin with basal requirements`（未找到）
- `insulin` --hasContraindication--> `Type 1 Diabetes`（未找到）
- `insulin` --hasContraindication--> `Type 1 Diabetes`（未找到）
- `metformin` --hasContraindication--> `Lactic Acidosis`（未找到）
- `metformin` --hasContraindication--> `Acute Kidney Injury`（未找到）
- `pancreatic-exocrine-insufficiency` --increasesRiskOf--> `Glycaemic Disturbance`（未找到）
- `pancreatic-exocrine-insufficiency` --increasesRiskOf--> `Suboptimal Glucose Control`（未找到）
- `careful-review-of-single-feed-regimen-at-36-48-hours` --appliesToType--> `Single feed regimen`（未找到）
- `delayed-enteral-feed` --increasesRiskOf--> `Hypoglycaemia`（未找到）
- `mismatched-timing-of-insulin-and-feed` --increasesRiskOf--> `Hyperglycaemia`（未找到）
- `mismatched-timing-of-insulin-and-feed` --increasesRiskOf--> `Hypoglycaemia`（未找到）
- `use-of-metformin-during-feed-breaks` --increasesRiskOf--> `Gastrointestinal Side Effects`（未找到）
- `subcutaneous-insulin` --hasContraindication--> `Hypoglycemia`（未找到）
- `subcutaneous-insulin` --hasContraindication--> `Ketonaemia`（未找到）
- `subcutaneous-insulin` --hasContraindication--> `Ketonuria`（未找到）
