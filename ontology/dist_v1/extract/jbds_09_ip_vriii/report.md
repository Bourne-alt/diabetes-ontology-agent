# 抽取质量报告 — jbds_09_ip_vriii

- 源文件：`ontology/knowledges/pdfs/JBDS_09_IP_VRIII.pdf`（sha256 `f27306f506a9…`）
- 目标图：`urn:dmo:extract:jbds_09_ip_vriii`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：23

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **82.2%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 90.3% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 72.4% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.15 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 511 |
| 通过校验 | 420 |
| 丢弃 | 91 |
| 消解后实体 | 365 |
| 关系边 | 32 |
| 悬空关系 | 84 |
| 合并冲突 | 155 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 85 |
| `quote_too_short` | 6 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 187 |
| contraindication | 38 |
| medication | 29 |
| drugClass | 23 |
| labTest | 21 |
| riskFactor | 21 |
| monitoringSchedule | 16 |
| adverseEffect | 11 |
| complication | 7 |
| device | 7 |
| diabetesType | 2 |
| complicationStage | 2 |
| lifestyleIntervention | 1 |

## 合并冲突样例

- diabetesType/type-2-diabetes: name: 'Type 2 diabetes' vs 'Type 2 Diabetes'
- diabetesType/type-2-diabetes: definition: 'This guideline is designed for acutely unwell patients, including those with a pre-existing diagnosis of diabetes and those who present with hyperglycaemia for the first time.' vs 'Patients with type 2 diabetes may also be prone to ketone production if unwell. We recommend ketone testing in this group of patients when presenting with acute illness. We do not recommend the routine use of capillary blood ketone testing in hyperglycaemic patients with Type 2 diabetes who are not acutely unwell.'
- diabetesType/type-2-diabetes: name: 'Type 2 diabetes' vs 'Type 2 Diabetes'
- diabetesType/type-2-diabetes: mondoCode: 'MONDO:0005148' vs 'MONDO:0005147'
- diabetesType/type-2-diabetes: definition: 'This guideline is designed for acutely unwell patients, including those with a pre-existing diagnosis of diabetes and those who present with hyperglycaemia for the first time.' vs 'Most patients will be taking additional OHG treatments, which should be restarted when a meal is due'
- diabetesType/type-2-diabetes: name: 'Type 2 diabetes' vs 'Type 2 Diabetes'
- diabetesType/type-2-diabetes: mondoCode: 'MONDO:0005148' vs 'MONDO:0005147'
- diabetesType/type-2-diabetes: definition: 'This guideline is designed for acutely unwell patients, including those with a pre-existing diagnosis of diabetes and those who present with hyperglycaemia for the first time.' vs 'Restarting insulin for patients previously on subcutaneous insulin'
- diabetesType/type-2-diabetes: definition: 'This guideline is designed for acutely unwell patients, including those with a pre-existing diagnosis of diabetes and those who present with hyperglycaemia for the first time.' vs 'Type 2 diabetes: give 0.1 units/kg of subcutaneous rapid acting analogue Insulin *, and recheck blood glucose 1 hour later to ensure it is falling.'
- diabetesType/type-2-diabetes: definition: 'This guideline is designed for acutely unwell patients, including those with a pre-existing diagnosis of diabetes and those who present with hyperglycaemia for the first time.' vs 'Type 1 or 2 diabetes and severe illness with need to achieve good glycaemic control e.g. sepsis'
- diabetesType/type-2-diabetes: name: 'Type 2 diabetes' vs 'Type 2 Diabetes'
- diabetesType/type-2-diabetes: mondoCode: 'MONDO:0005148' vs 'MONDO:0005147'
- diabetesType/type-2-diabetes: definition: 'This guideline is designed for acutely unwell patients, including those with a pre-existing diagnosis of diabetes and those who present with hyperglycaemia for the first time.' vs 'Type 2 Diabetes'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005042' vs 'MONDO:0005040'
- complication/hypoglycaemia: affectedOrgan: 'Brain' vs 'Systemic'
- complication/hypoglycaemia: definition: 'hypoglycaemia' vs 'Defined as CBG less than 4 mmol/L'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005042' vs 'MONDO:0005147'
- complication/hypoglycaemia: definition: 'hypoglycaemia' vs 'If the TPN is stopped for any reason this will put the patient at risk of hypoglycaemia.'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005042' vs 'MONDO:0005005'
- complication/hypoglycaemia: affectedOrgan: 'Brain' vs 'Systemic'

## 悬空关系样例

- `variable-rate-intravenous-insulin-infusion` --hasContraindication--> `DKA`（未找到）
- `variable-rate-intravenous-insulin-infusion` --causesAdverseEffect--> `excess length of stay`（未找到）
- `safe-use-of-variable-rate-intravenous-insulin-infusion` --definesTarget--> `Target blood glucose levels`（未找到）
- `safe-use-of-variable-rate-intravenous-insulin-infusion` --definesSchedule--> `Short duration of use`（未找到）
- `safe-use-of-variable-rate-intravenous-insulin-infusion` --recommendsLifestyle--> `Referral to local diabetes teams`（未找到）
- `safe-use-of-variable-rate-intravenous-insulin-infusion` --citesSource--> `NHS Diabetes e-learning module 'Safe use of Intravenous insulin infusion'`（未找到）
- `referral-to-local-diabetes-teams` --appliesToType--> `Variable Rate Intravenous Insulin Infusion (VRIII)`（未找到）
- `completion-of-e-learning-module-on-intravenous-insulin-infusion` --citesSource--> `NHS Diabetes e-learning module 'Safe use of Intravenous insulin infusion'`（未找到）
- `hyperglycaemia` --increasesRiskOf--> `Poor clinical outcomes`（未找到）
- `glucose-variability` --increasesRiskOf--> `Mortality`（未找到）
- `admission-glucose` --increasesRiskOf--> `Mortality`（未找到）
- `uncontrolled-hyperglycaemia` --increasesRiskOf--> `Poor outcomes in ACS`（未找到）
- `nice-recommends-the-use-of-a-dose-adjusted-intravenous-insulin-to-prevent-uncontrolled-hyperglycaemia-bg-11-0-mmol-l-in-patients-with-acute-coronary-syndrome-acs` --definesTarget--> `moderate glycaemic control target BG <11 mmol/L`（未找到）
- `nice-recommends-the-use-of-a-dose-adjusted-intravenous-insulin-to-prevent-uncontrolled-hyperglycaemia-bg-11-0-mmol-l-in-patients-with-acute-coronary-syndrome-acs` --citesSource--> `NICE`（未找到）
- `moderate-glycaemic-control-target-bg-11-mmol-l` --definesTarget--> `moderate glycaemic control target BG <11 mmol/L`（未找到）
- `moderate-glycaemic-control-target-bg-11-mmol-l` --appliesToType--> `Treatment`（未找到）
- `insulin` --hasContraindication--> `Hypoglycaemia`（未找到）
- `insulin` --hasContraindication--> `unstable blood glucose`（未找到）
- `insulin` --hasContraindication--> `HbA1c > 59 mmol/mol`（未找到）
- `insulin` --hasContraindication--> `Frail elderly patients`（未找到）
