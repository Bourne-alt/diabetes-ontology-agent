# 抽取质量报告 — jbds-21-metabolic-bariatric-surgery-march-2026

- 源文件：`ontology/knowledges/pdfs/JBDS-21-Metabolic-bariatric-surgery-March-2026.pdf`（sha256 `48a1291adc84…`）
- 目标图：`urn:dmo:extract:jbds-21-metabolic-bariatric-surgery-march-2026`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：10

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **70.3%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 82.3% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 31.5% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.54 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 461 |
| 通过校验 | 324 |
| 丢弃 | 137 |
| 消解后实体 | 211 |
| 关系边 | 76 |
| 悬空关系 | 35 |
| 合并冲突 | 225 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 120 |
| `quote_too_short` | 12 |
| `unknown_relation_predicate` | 5 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 94 |
| medication | 52 |
| contraindication | 29 |
| drugClass | 14 |
| device | 8 |
| labTest | 4 |
| monitoringSchedule | 3 |
| diabetesType | 2 |
| complication | 2 |
| adverseEffect | 2 |
| riskFactor | 1 |

## 合并冲突样例

- diabetesType/type-2-diabetes: definition: 'The role of metabolic-bariatric surgery as effective interventions for obesity and type 2 diabetes is well recognised, particularly in achieving type 2 diabetes remission or improvement in glycaemic control, treatment impact and improvements in associated complications' vs 'Type 2 Diabetes'
- diabetesType/type-2-diabetes: name: 'Type 2 Diabetes' vs 'Type 2 diabetes'
- diabetesType/type-2-diabetes: definition: 'The role of metabolic-bariatric surgery as effective interventions for obesity and type 2 diabetes is well recognised, particularly in achieving type 2 diabetes remission or improvement in glycaemic control, treatment impact and improvements in associated complications' vs 'Type 2 diabetes - Insulin-based therapy agents during the liver reduction diet (LRD)'
- diabetesType/type-2-diabetes: definition: 'The role of metabolic-bariatric surgery as effective interventions for obesity and type 2 diabetes is well recognised, particularly in achieving type 2 diabetes remission or improvement in glycaemic control, treatment impact and improvements in associated complications' vs 'Individuals on insulin therapy should be discussed with and/or reviewed by the Diabetes-Bariatric Physician/Nurse. There is no set rule for insulin needs following metabolic-bariatric surgery(4).'
- diabetesType/type-2-diabetes: mondoCode: 'MONDO:0005147' vs 'MONDO:0005148'
- diabetesType/type-2-diabetes: definition: 'The role of metabolic-bariatric surgery as effective interventions for obesity and type 2 diabetes is well recognised, particularly in achieving type 2 diabetes remission or improvement in glycaemic control, treatment impact and improvements in associated complications' vs 'If type 2 diabetes remission is achieved following surgery, a recommendation should be made for an annual HbA1c and routine microvascular/macrovascular screening as this group is at high-risk of type 2 diabetes relapse and complications.'
- diabetesType/type-1-diabetes: definition: 'Hypoglycaemia is defined as blood glucose <4 mmol/L. Prevention and management of hypoglycaemia must be considered when planning and during the perioperative and postoperative phases of surgery in all those at risk (on insulin and insulin secretagogues)' vs 'Type 1 Diabetes'
- diabetesType/type-1-diabetes: mondoCode: 'MONDO:0005148' vs 'MONDO:0005147'
- diabetesType/type-1-diabetes: prevalenceShare: 0.1 vs 0.05
- diabetesType/type-1-diabetes: definition: 'Hypoglycaemia is defined as blood glucose <4 mmol/L. Prevention and management of hypoglycaemia must be considered when planning and during the perioperative and postoperative phases of surgery in all those at risk (on insulin and insulin secretagogues)' vs 'Individuals with type 1 diabetes require review by the Diabetes-Bariatric Physician. There is no set rule for individual insulin requirements following metabolic-bariatric surgery. The usual diabetes care providers must be contacted early to allow careful insulin management.'
- diabetesType/type-1-diabetes: mondoCode: 'MONDO:0005148' vs 'MONDO:0005147'
- diabetesType/type-1-diabetes: prevalenceShare: 0.1 vs 0.05
- diabetesType/type-1-diabetes: definition: 'Hypoglycaemia is defined as blood glucose <4 mmol/L. Prevention and management of hypoglycaemia must be considered when planning and during the perioperative and postoperative phases of surgery in all those at risk (on insulin and insulin secretagogues)' vs 'Individuals with type 1 diabetes could liaise with diabetes teams to adjust further to achieve/maintain optimal diabetes control'
- diabetesType/type-1-diabetes: mondoCode: 'MONDO:0005148' vs 'MONDO:0005147'
- diabetesType/type-1-diabetes: prevalenceShare: 0.1 vs 0.05
- diabetesType/type-1-diabetes: definition: 'Hypoglycaemia is defined as blood glucose <4 mmol/L. Prevention and management of hypoglycaemia must be considered when planning and during the perioperative and postoperative phases of surgery in all those at risk (on insulin and insulin secretagogues)' vs 'insulin must never be stopped as this expose them to the risk of DKA'
- labTest/hba1c: definition: 'A measure of average blood glucose levels over the past 2-3 months, used to assess long-term glycaemic control.' vs 'A measure of average blood glucose levels over the past 2-3 months, used to assess long-term glycaemic control in diabetes.'
- labTest/hba1c: definition: 'A measure of average blood glucose levels over the past 2-3 months, used to assess long-term glycaemic control.' vs 'A measure of average blood glucose levels over the past 2-3 months, used to assess long-term glycaemic control in people with diabetes.'
- labTest/hba1c: definition: 'A measure of average blood glucose levels over the past 2-3 months, used to assess long-term glycaemic control.' vs 'A measure of average blood glucose levels over the past 2-3 months, used to assess long-term glycaemic control in diabetes.'
- labTest/blood-ketones: name: 'Blood ketones' vs 'Blood Ketones'

## 悬空关系样例

- `glp-1-based-therapies` --causesAdverseEffect--> `Pulmonary aspiration`（未找到）
- `glp-1-based-therapies` --causesAdverseEffect--> `GLP-1 based therapies`（未找到）
- `sglt2-inhibitors` --hasContraindication--> `Diabetic ketoacidosis`（未找到）
- `sglt2-inhibitors` --hasContraindication--> `DKA`（未找到）
- `sglt2-inhibitors` --hasContraindication--> `Liver reduction diet`（未找到）
- `sglt2-inhibitors` --hasContraindication--> `Liver Reduction Diet`（未找到）
- `insulin` --hasContraindication--> `Diabetic ketoacidosis`（未找到）
- `insulin` --hasContraindication--> `DKA`（未找到）
- `insulin` --hasContraindication--> `Liver Reduction Diet`（未找到）
- `insulin` --hasContraindication--> `Type 1 Diabetes`（未找到）
- `insulin` --hasContraindication--> `Low-calorie diet`（未找到）
- `sulfonylureas` --hasContraindication--> `Liver reduction diet`（未找到）
- `sulfonylureas` --hasContraindication--> `Liver Reduction Diet`（未找到）
- `meglitinides` --hasContraindication--> `Liver reduction diet`（未找到）
- `meglitinides` --hasContraindication--> `Liver Reduction Diet`（未找到）
- `sulfonylureas` --triggeredByCondition--> `Liver Reduction Diet`（未找到）
- `meglitinides` --triggeredByCondition--> `Liver Reduction Diet`（未找到）
- `sglt2-inhibitors` --triggeredByCondition--> `Liver Reduction Diet`（未找到）
- `adjustment-of-diabetes-medication-doses-postoperatively` --citesSource--> `CPOC Guideline for Perioperative Care for People with Diabetes Mellitus Undergoing Elective and Emergency Surgery (updated October 2023)`（未找到）
- `modification-of-medication-formulation-postoperatively` --citesSource--> `CPOC Guideline for Perioperative Care for People with Diabetes Mellitus Undergoing Elective and Emergency Surgery (updated October 2023)`（未找到）
