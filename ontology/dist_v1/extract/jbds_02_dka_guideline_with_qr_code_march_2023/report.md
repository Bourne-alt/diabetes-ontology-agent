# 抽取质量报告 — jbds_02_dka_guideline_with_qr_code_march_2023

- 源文件：`ontology/knowledges/pdfs/JBDS_02_DKA_Guideline_with_QR_code_March_2023.pdf`（sha256 `568323c1bb8b…`）
- 目标图：`urn:dmo:extract:jbds_02_dka_guideline_with_qr_code_march_2023`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：30

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **83.0%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 96.8% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 58.3% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.22 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 764 |
| 通过校验 | 634 |
| 丢弃 | 130 |
| 消解后实体 | 518 |
| 关系边 | 103 |
| 悬空关系 | 144 |
| 合并冲突 | 248 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 76 |
| `quote_too_short` | 31 |
| `unknown_relation_predicate` | 23 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 246 |
| labTest | 47 |
| medication | 33 |
| device | 30 |
| monitoringSchedule | 29 |
| symptom | 27 |
| contraindication | 26 |
| lifestyleIntervention | 21 |
| riskFactor | 20 |
| complication | 19 |
| drugClass | 11 |
| diabetesType | 5 |
| adverseEffect | 3 |
| complicationStage | 1 |

## 合并冲突样例

- complication/diabetic-ketoacidosis: name: 'Diabetic Ketoacidosis' vs 'Diabetic ketoacidosis'
- complication/diabetic-ketoacidosis: definition: 'The management of diabetic ketoacidosis in adults' vs 'Diabetic ketoacidosis (DKA) is a frequent and potentially life-threatening complication of type 1 diabetes.'
- complication/diabetic-ketoacidosis: definition: 'The management of diabetic ketoacidosis in adults' vs 'A life threatening complication of diabetes characterized by hyperglycaemia, ketonaemia, and metabolic acidosis.'
- complication/diabetic-ketoacidosis: mondoCode: 'MONDO:0005147' vs 'MONDO:0005040'
- complication/diabetic-ketoacidosis: definition: 'The management of diabetic ketoacidosis in adults' vs 'A serious complication of diabetes characterized by hyperglycemia, ketonemia, and metabolic acidosis, requiring urgent medical intervention.'
- complication/diabetic-ketoacidosis: mondoCode: 'MONDO:0005147' vs 'MONDO:0005075'
- complication/diabetic-ketoacidosis: definition: 'The management of diabetic ketoacidosis in adults' vs 'Diabetic ketoacidosis (DKA) is a serious complication of diabetes that occurs when the body produces high levels of blood acids called ketones. It is characterized by hyperglycemia, ketonemia, and metabolic acidosis, and requires urgent medical treatment.'
- complication/diabetic-ketoacidosis: mondoCode: 'MONDO:0005147' vs 'MONDO:0005143'
- complication/diabetic-ketoacidosis: definition: 'The management of diabetic ketoacidosis in adults' vs 'Diabetic ketoacidosis (DKA) is a life-threatening complication of diabetes characterized by hyperglycaemia, ketonaemia, and metabolic acidosis.'
- complication/diabetic-ketoacidosis: mondoCode: 'MONDO:0005147' vs 'MONDO:0005040'
- complication/diabetic-ketoacidosis: definition: 'The management of diabetic ketoacidosis in adults' vs 'Diabetic ketoacidosis is a medical emergency requiring prompt treatment, and is different to a ketosis of pregnancy.'
- complication/diabetic-ketoacidosis: definition: 'The management of diabetic ketoacidosis in adults' vs 'A serious complication of diabetes characterized by hyperglycemia, ketonemia, and metabolic acidosis, often requiring urgent medical intervention.'
- complication/diabetic-ketoacidosis: definition: 'The management of diabetic ketoacidosis in adults' vs 'Diabetic ketoacidosis (DKA) is a serious complication of diabetes characterized by hyperglycemia, ketonemia, and metabolic acidosis, often requiring urgent medical intervention.'
- complication/diabetic-ketoacidosis: mondoCode: 'MONDO:0005147' vs 'MONDO:0005040'
- complication/diabetic-ketoacidosis: definition: 'The management of diabetic ketoacidosis in adults' vs 'Resolution of DKA is defined as ketones less than 0.6 mmol/L and venous pH over 7.3'
- complication/diabetic-ketoacidosis: name: 'Diabetic Ketoacidosis' vs 'Diabetic ketoacidosis'
- complication/diabetic-ketoacidosis: definition: 'The management of diabetic ketoacidosis in adults' vs 'Diabetic ketoacidosis (DKA) is a complex disordered metabolic state characterised by hyperglycaemia, ketonaemia, and acidosis.'
- complication/diabetic-ketoacidosis: name: 'Diabetic Ketoacidosis' vs 'Diabetic ketoacidosis'
- complication/diabetic-ketoacidosis: mondoCode: 'MONDO:0005147' vs 'MONDO:0005075'
- complication/diabetic-ketoacidosis: definition: 'The management of diabetic ketoacidosis in adults' vs 'Diabetic ketoacidosis is a common medical emergency and must be treated appropriately.'

## 悬空关系样例

- `diabetic-ketoacidosis` --hasStage--> `Diabetic Ketoacidosis`（未找到）
- `reduce-the-rate-of-insulin-infusion-to-0-05-units-kg-hr-when-glucose-drops-to-14-0-mmol-l` --citesSource--> `A national survey of DKA management following earlier version of this guideline found that the rates of hypoglycaemia (<4.0 mmol/L) and hypokalaemia (<4.0 mmol/L) were 27.6% and 67% respectively. Whilst it may have been that these occurred due to 10% dextrose not being added in a timely manner, or that potassium containing fluids were not given correctly, the main driver for both of these biochemical abnormalities is the use of insulin. Thus, when glucose drops below 14 mmol/L, consider reducing the rate of intravenous insulin infusion to 0.05 units/kg/hr. This is already an option in the adult guidelines elsewhere (25), and several paediatric studies have suggested that the rate of resolution of DKA is not longer compared to 0.1 units/kg/hr (30-32). It is thus also included in the UK paediatric guidelines (33).`（未找到）
- `use-of-guidance-based-on-admitting-ward` --citesSource--> `2021 guidance`（未找到）
- `capillary-ketones` --hasThreshold--> `Ketones Less Than 0.6 mmol/L`（未找到）
- `urine-ketones` --hasThreshold--> `Urine ketones`（未找到）
- `venous-ph` --hasThreshold--> `Venous pH`（未找到）
- `venous-ph` --hasThreshold--> `Venous pH`（未找到）
- `venous-ph` --hasThreshold--> `7.3`（未找到）
- `venous-bicarbonate` --hasThreshold--> `Venous Bicarbonate Over 18 mmol/L`（未找到）
- `hourly-capillary-blood-glucose` --schedulesTest--> `Diabetic Ketoacidosis`（未找到）
- `hourly-capillary-ketone-measurement` --schedulesTest--> `Diabetic Ketoacidosis`（未找到）
- `venous-bicarbonate-and-potassium-at-60-minutes-2-hours-and-2-hourly-thereafter` --schedulesTest--> `Diabetic Ketoacidosis`（未找到）
- `4-hourly-plasma-electrolytes` --schedulesTest--> `Diabetic Ketoacidosis`（未找到）
- `continuous-cardiac-monitoring-if-required` --schedulesTest--> `Diabetic Ketoacidosis`（未找到）
- `continuous-pulse-oximetry-if-required` --schedulesTest--> `Diabetic Ketoacidosis`（未找到）
- `plasma-glucose` --hasThreshold--> `Glucose Less Than 14 mmol/L`（未找到）
- `capillary-ketone-concentration` --hasThreshold--> `Capillary Ketone Concentration`（未找到）
- `bicarbonate-concentration` --hasThreshold--> `Bicarbonate Concentration`（未找到）
- `blood-glucose-concentration` --hasThreshold--> `Blood Glucose Concentration`（未找到）
- `ketonuria` --hasThreshold--> `Ketonuria`（未找到）
