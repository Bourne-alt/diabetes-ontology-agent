# 抽取质量报告 — jbds_08_hyperglycaemia_and_steroid_therapy_january_2023

- 源文件：`ontology/knowledges/pdfs/JBDS_08_Hyperglycaemia_and_Steroid_Therapy_January_2023.pdf`（sha256 `a83d17dfbe86…`）
- 目标图：`urn:dmo:extract:jbds_08_hyperglycaemia_and_steroid_therapy_january_2023`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：14

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **84.2%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 90.3% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 57.9% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.14 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 399 |
| 通过校验 | 336 |
| 丢弃 | 63 |
| 消解后实体 | 295 |
| 关系边 | 83 |
| 悬空关系 | 114 |
| 合并冲突 | 128 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 48 |
| `quote_too_short` | 10 |
| `unknown_relation_predicate` | 5 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 127 |
| medication | 32 |
| riskFactor | 31 |
| drugClass | 22 |
| symptom | 17 |
| monitoringSchedule | 15 |
| labTest | 12 |
| lifestyleIntervention | 10 |
| device | 7 |
| contraindication | 7 |
| complication | 6 |
| adverseEffect | 5 |
| diabetesType | 4 |

## 合并冲突样例

- drugClass/sulphonylureas-and-meglitinides: mechanism: 'Stimulate insulin secretion from pancreatic beta cells' vs 'promote insulin release from the pancreatic beta cell'
- medication/twice-daily-gliclazide-or-isophane-insulin: name: 'Twice daily gliclazide or isophane insulin' vs 'gliclazide'
- medication/twice-daily-gliclazide-or-isophane-insulin: name: 'Twice daily gliclazide or isophane insulin' vs 'isophane insulin'
- medication/twice-daily-gliclazide-or-isophane-insulin: isInsulin: False vs True
- medication/twice-daily-gliclazide-or-isophane-insulin: insulinAction: 'NotApplicable' vs 'Intermediate'
- symptom/acute-hyperglycaemia: name: 'Acute hyperglycaemia' vs 'acute hyperglycaemia'
- symptom/fatigue: name: 'Fatigue' vs 'fatigue'
- symptom/polyuria: name: 'Polyuria' vs 'polyuria'
- symptom/polydipsia: name: 'Polydipsia' vs 'polydipsia'
- riskFactor/steroid-therapy: name: 'Steroid Therapy' vs 'Steroid therapy'
- riskFactor/duration-of-steroid-use: name: 'Duration of Steroid Use' vs 'Duration of steroid use'
- riskFactor/dose-of-glucocorticoids: name: 'Dose of Glucocorticoids' vs 'Dose of glucocorticoids'
- riskFactor/potency-of-glucocorticoid: name: 'Potency of Glucocorticoid' vs 'Potency of glucocorticoid'
- riskFactor/pre-existing-diabetes: name: 'Pre-existing Diabetes' vs 'Pre-existing diabetes'
- medication/dexamethasone: name: 'Dexamethasone' vs 'dexamethasone'
- medication/dexamethasone: name: 'Dexamethasone' vs 'dexamethasone'
- medication/dexamethasone: durationHours: 0 vs 36
- medication/dexamethasone: name: 'Dexamethasone' vs 'dexamethasone'
- diabetesType/type-1-diabetes: name: 'Type 1 diabetes' vs 'Type 1 Diabetes'
- diabetesType/type-1-diabetes: definition: 'In Type 1 diabetes also check daily for ketones if CBG >12mmol/L.' vs 'These individuals will still need to follow the algorithm on page 10.'

## 悬空关系样例

- `steroid-therapy` --increasesRiskOf--> `Glucocorticoid Induced Hyperglycaemia`（未找到）
- `duration-of-steroid-use` --increasesRiskOf--> `Glucocorticoid Induced Hyperglycaemia`（未找到）
- `dose-of-glucocorticoids` --increasesRiskOf--> `Glucocorticoid Induced Hyperglycaemia`（未找到）
- `potency-of-glucocorticoid` --increasesRiskOf--> `Glucocorticoid Induced Hyperglycaemia`（未找到）
- `pre-existing-diabetes` --increasesRiskOf--> `Steroid Induced Hyperglycaemia`（未找到）
- `sulphonylureas` --hasContraindication--> `Steroid therapy`（未找到）
- `sulphonylureas` --hasContraindication--> `Steroid Therapy`（未找到）
- `sulphonylureas` --hasContraindication--> `Hyperglycaemia in COVID-19`（未找到）
- `insulin` --hasContraindication--> `Steroid therapy`（未找到）
- `insulin` --hasContraindication--> `Steroid Therapy`（未找到）
- `insulin` --hasContraindication--> `Steroid therapy`（未找到）
- `insulin` --hasContraindication--> `Pregnancy`（未找到）
- `obesity` --increasesRiskOf--> `People at increased risk of diabetes`（未找到）
- `family-history-of-diabetes` --increasesRiskOf--> `People at increased risk of diabetes`（未找到）
- `previous-gestational-diabetes` --increasesRiskOf--> `People at increased risk of diabetes`（未找到）
- `ethnic-minorities` --increasesRiskOf--> `People at increased risk of diabetes`（未找到）
- `polycystic-ovarian-syndrome` --increasesRiskOf--> `People at increased risk of diabetes`（未找到）
- `use-of-diabetes-risk-calculator` --increasesRiskOf--> `People at increased risk of diabetes`（未找到）
- `basal-bolus-insulin-adjustment-for-hyperglycaemia-in-steroid-therapy` --definesTarget--> `Capillary blood glucose (CBG) targets`（未找到）
- `glycaemic-targets-for-hospital-inpatients-on-steroid-therapy` --definesTarget--> `Capillary blood glucose (CBG) targets`（未找到）
