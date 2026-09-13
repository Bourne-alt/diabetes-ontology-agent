# 抽取质量报告 — jbds_02_nursing_management_for_dka_v1_20122022

- 源文件：`ontology/knowledges/pdfs/JBDS_02_Nursing_Management_for_DKA_v1_20122022.pdf`（sha256 `446ccba661df…`）
- 目标图：`urn:dmo:extract:jbds_02_nursing_management_for_dka_v1_20122022`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：8

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **93.1%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 64.5% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 34.0% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.21 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 217 |
| 通过校验 | 202 |
| 丢弃 | 15 |
| 消解后实体 | 167 |
| 关系边 | 31 |
| 悬空关系 | 16 |
| 合并冲突 | 100 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 15 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 56 |
| medication | 39 |
| labTest | 25 |
| device | 10 |
| drugClass | 10 |
| symptom | 8 |
| monitoringSchedule | 8 |
| contraindication | 7 |
| complication | 2 |
| adverseEffect | 2 |

## 合并冲突样例

- labTest/capillary-or-blood-ketone-concentration: definition: 'a capillary or blood ketone concentration of > 3.0mmol/L or significant ketonuria (more than 2+ on standard urine sticks)' vs 'A measure of ketone levels in capillary or blood samples, used to diagnose ketonaemia in DKA.'
- labTest/venous-ph: definition: 'venous pH <7.3' vs 'Venous/arterial pH below 7.0 may indicate severe DKA.'
- labTest/venous-ph: definition: 'venous pH <7.3' vs 'A measure of the acidity or alkalinity of venous blood, used to assess acidosis in DKA.'
- labTest/urine-ketone: definition: 'significant ketonuria (more than 2+ on standard urine sticks)' vs 'A measure of ketones in urine, used to assess ketonuria in DKA.'
- complication/diabetic-ketoacidosis: mondoCode: 'MONDO:0005147' vs 'MONDO:0005040'
- complication/diabetic-ketoacidosis: definition: "The 'D' is for Diabetes- a blood glucose concentration of >11.0mmol/L or known to have diabetes mellitus The 'K' is for Ketonaemia or ketonuria - a capillary or blood ketone concentration of > 3.0mmol/L or significant ketonuria (more than 2+ on standard urine sticks) The 'A' is for Acidaemia/acidosis– a bicarbonate concentration of ≤15.0mmol/L and/or venous pH <7.3" vs 'Diabetic Ketoacidosis (DKA) is a serious complication of diabetes characterized by hyperglycemia, ketonemia, and metabolic acidosis.'
- complication/diabetic-ketoacidosis: mondoCode: 'MONDO:0005147' vs 'MONDO:0005070'
- complication/diabetic-ketoacidosis: definition: "The 'D' is for Diabetes- a blood glucose concentration of >11.0mmol/L or known to have diabetes mellitus The 'K' is for Ketonaemia or ketonuria - a capillary or blood ketone concentration of > 3.0mmol/L or significant ketonuria (more than 2+ on standard urine sticks) The 'A' is for Acidaemia/acidosis– a bicarbonate concentration of ≤15.0mmol/L and/or venous pH <7.3" vs 'Diabetic Ketoacidosis (DKA) is a serious complication of diabetes characterized by high blood glucose, ketone production, and metabolic acidosis.'
- complication/diabetic-ketoacidosis: mondoCode: 'MONDO:0005147' vs 'MONDO:0005148'
- complication/diabetic-ketoacidosis: definition: "The 'D' is for Diabetes- a blood glucose concentration of >11.0mmol/L or known to have diabetes mellitus The 'K' is for Ketonaemia or ketonuria - a capillary or blood ketone concentration of > 3.0mmol/L or significant ketonuria (more than 2+ on standard urine sticks) The 'A' is for Acidaemia/acidosis– a bicarbonate concentration of ≤15.0mmol/L and/or venous pH <7.3" vs 'Diabetic Ketoacidosis (DKA) is a serious complication of diabetes characterized by hyperglycemia, ketonemia, and metabolic acidosis, often requiring urgent medical intervention.'
- complication/diabetic-ketoacidosis: definition: "The 'D' is for Diabetes- a blood glucose concentration of >11.0mmol/L or known to have diabetes mellitus The 'K' is for Ketonaemia or ketonuria - a capillary or blood ketone concentration of > 3.0mmol/L or significant ketonuria (more than 2+ on standard urine sticks) The 'A' is for Acidaemia/acidosis– a bicarbonate concentration of ≤15.0mmol/L and/or venous pH <7.3" vs 'The ‘D’ is for Diabetes- a blood glucose concentration of >11.0mmol/L or known to have diabetes mellitus The ‘K’ is for Ketonaemia or ketonuria - a capillary or blood ketone concentration of > 3.0mmol/L or significant ketonuria (more than 2+ on standard urine sticks) The ‘A’ is for Acidaemia/acidosis– a bicarbonate concentration of ≤15.0mmol/L and/or venous pH <7.3'
- complication/diabetic-ketoacidosis: definition: "The 'D' is for Diabetes- a blood glucose concentration of >11.0mmol/L or known to have diabetes mellitus The 'K' is for Ketonaemia or ketonuria - a capillary or blood ketone concentration of > 3.0mmol/L or significant ketonuria (more than 2+ on standard urine sticks) The 'A' is for Acidaemia/acidosis– a bicarbonate concentration of ≤15.0mmol/L and/or venous pH <7.3" vs 'Diabetic Ketoacidosis (DKA) is a serious complication of diabetes characterized by hyperglycemia, ketonemia, and metabolic acidosis, requiring urgent medical intervention.'
- labTest/blood-ketones: name: 'Blood ketones' vs 'Blood Ketones'
- labTest/blood-ketones: definition: 'Blood ketones over 6.0mmol/L may indicate severe DKA.' vs 'Monitor blood ketones hourly using Trust approved meter until <0.6 mmol/L'
- symptom/blood-ketones-over-6-0mmol-l: name: 'Blood Ketones over 6.0mmol/L' vs 'Blood ketones over 6.0mmol/L'
- medication/human-soluble-insulin: name: 'Human Soluble Insulin' vs 'human soluble insulin'
- medication/human-soluble-insulin: name: 'Human Soluble Insulin' vs 'human soluble insulin'
- device/continuous-subcutaneous-insulin-infusion-pump: name: 'Continuous Subcutaneous Insulin Infusion Pump' vs 'continuous subcutaneous insulin infusion pump'
- labTest/capillary-blood-glucose: definition: 'Capillary blood glucose is monitored hourly using Trust approved meter. If meter reads “over POCT QA range ie >27.8mmol/L" or “Hi", venous blood should be sent to the laboratory hourly or measured using venous blood in a blood gas analyser.' vs 'A measure of blood glucose concentration from capillary blood, used to monitor glucose levels in DKA management.'
- labTest/venous-bicarbonate: definition: 'Assess the resolution of ketoacidosis: If blood ketone measurement is available and blood ketones are not falling by at least 0.5mmol/L/hr call a prescribing clinician to increase the insulin infusion rate by 1.0 unit/hr increments hourly until the ketones are falling at target rates (also check infusion**)' vs 'A measure of bicarbonate concentration in venous blood, used to assess acidosis in DKA.'

## 悬空关系样例

- `review-by-consultant-physician-for-severe-dka-signs` --appliesToType--> `Assess for Severe DKA Indicators`（未找到）
- `consider-alternative-causes-for-deterioration-in-dka` --appliesToType--> `Review by Consultant Physician for Severe DKA Signs`（未找到）
- `urgent-senior-multidisciplinary-discussion-for-surgical-needs` --appliesToType--> `Consider Alternative Causes for Deterioration in DKA`（未找到）
- `remove-csii-and-replace-with-subcutaneous-basal-insulin-if-no-local-policy` --appliesToType--> `Manage CSII in DKA Patients`（未找到）
- `consider-level-2-hdu-admission-for-high-risk-dka-patients` --appliesToType--> `Administer Fluids in Stages for DKA`（未找到）
- `guide-fluid-replacement-by-central-venous-pressure-in-high-risk-cases` --appliesToType--> `Consider Level 2/HDU Admission for High-Risk DKA Patients`（未找到）
- `prepare-insulin-infusion-with-human-soluble-insulin-in-0-9-sodium-chloride` --appliesToType--> `Start Continuous Fixed Rate Intravenous Insulin Infusion (FRIII)`（未找到）
- `basal-insulin` --hasContraindication--> `Basal Insulin`（未找到）
- `basal-insulin` --causesAdverseEffect--> `Hypoglycemia`（未找到）
- `restarting-short-acting-insulin-after-basal-insulin` --appliesToType--> `Diabetic Ketoacidosis`（未找到）
- `overlap-between-insulin-infusion-and-rapid-acting-insulin` --appliesToType--> `Diabetic Ketoacidosis`（未找到）
- `reintroducing-subcutaneous-insulin-after-fixed-mix-insulin` --appliesToType--> `Diabetic Ketoacidosis`（未找到）
- `stopping-additional-basal-insulin-after-mixed-insulin-reintroduction` --appliesToType--> `Diabetic Ketoacidosis`（未找到）
- `transitioning-from-iv-insulin-infusion-to-csii` --appliesToType--> `Diabetic Ketoacidosis`（未找到）
- `fixed-rate-intravenous-insulin-infusion` --hasContraindication--> `Fixed Rate Intravenous Insulin Infusion`（未找到）
- `fixed-rate-intravenous-insulin-infusion` --causesAdverseEffect--> `Hypoglycemia`（未找到）
