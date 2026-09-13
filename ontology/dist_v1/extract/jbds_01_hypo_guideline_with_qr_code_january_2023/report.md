# 抽取质量报告 — jbds_01_hypo_guideline_with_qr_code_january_2023

- 源文件：`ontology/knowledges/pdfs/JBDS_01_Hypo_Guideline_with_QR_code_January_2023.pdf`（sha256 `c92b2d6416bf…`）
- 目标图：`urn:dmo:extract:jbds_01_hypo_guideline_with_qr_code_january_2023`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：28

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **84.2%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 98.4% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 78.8% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.27 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 620 |
| 通过校验 | 522 |
| 丢弃 | 98 |
| 消解后实体 | 412 |
| 关系边 | 45 |
| 悬空关系 | 167 |
| 合并冲突 | 258 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 78 |
| `quote_too_short` | 14 |
| `unknown_relation_predicate` | 6 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 136 |
| riskFactor | 69 |
| contraindication | 40 |
| symptom | 38 |
| medication | 36 |
| adverseEffect | 25 |
| drugClass | 16 |
| device | 13 |
| labTest | 10 |
| complication | 9 |
| diabetesType | 9 |
| lifestyleIntervention | 5 |
| complicationStage | 4 |
| monitoringSchedule | 2 |

## 合并冲突样例

- complication/hypoglycaemia: mondoCode: 'MONDO:0005147' vs 'MONDO:0005148'
- complication/hypoglycaemia: definition: 'The hospital management of hypoglycaemia in adults with diabetes mellitus' vs 'Hypoglycaemia continues to be one of the most feared short-term complications of diabetes mellitus amongst people with diabetes, healthcare professionals and lay carers alike.'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005147' vs 'MONDO:0005148'
- complication/hypoglycaemia: definition: 'The hospital management of hypoglycaemia in adults with diabetes mellitus' vs 'Hypoglycaemia continues to be one of the most feared short-term complications of diabetes mellitus amongst people with diabetes, healthcare professionals and lay carers alike.'
- complication/hypoglycaemia: definition: 'The hospital management of hypoglycaemia in adults with diabetes mellitus' vs 'Hypoglycaemia is a serious condition and should be treated as an emergency regardless of level of conciousness. Hypoglycaemia is defined as blood sugar glucose of <4.0mmol/L (if not <4.0mmol/L but symptomatic give a small carbohydrate snack for symptom relief)'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005147' vs 'MONDO:0005148'
- complication/hypoglycaemia: definition: 'The hospital management of hypoglycaemia in adults with diabetes mellitus' vs 'A condition characterized by abnormally low blood glucose levels, requiring immediate treatment to prevent serious complications such as coma or death.'
- complication/hypoglycaemia: definition: 'The hospital management of hypoglycaemia in adults with diabetes mellitus' vs 'A condition characterized by abnormally low blood glucose levels, requiring immediate intervention to prevent serious complications such as unconsciousness or seizures.'
- complication/hypoglycaemia: definition: 'The hospital management of hypoglycaemia in adults with diabetes mellitus' vs 'A condition characterized by abnormally low blood glucose levels, which can lead to unconsciousness, seizures, or aggressive behavior, requiring immediate intervention.'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005147' vs 'MONDO:0005148'
- complication/hypoglycaemia: definition: 'The hospital management of hypoglycaemia in adults with diabetes mellitus' vs 'Hypoglycaemia is a condition in which blood glucose levels fall below 4.0 mmol/L, leading to symptoms such as confusion, sweating, tremors, and in severe cases, loss of consciousness or coma.'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005147' vs 'MONDO:0005000'
- complication/hypoglycaemia: definition: 'The hospital management of hypoglycaemia in adults with diabetes mellitus' vs 'A condition characterized by abnormally low blood glucose levels, requiring immediate treatment to prevent serious complications.'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005147' vs 'MONDO:0005148'
- complication/hypoglycaemia: definition: 'The hospital management of hypoglycaemia in adults with diabetes mellitus' vs 'Hypoglycaemia results from an imbalance between glucose supply, glucose utilisation and current insulin levels. Hypoglycaemia is the commonest side-effect of insulin or sulfonylurea therapy used to treat diabetes.'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005147' vs 'MONDO:0005148'
- complication/hypoglycaemia: definition: 'The hospital management of hypoglycaemia in adults with diabetes mellitus' vs 'Hypoglycaemia is a level of blood glucose below normal. Normal blood glucose levels in a person without diabetes are 3.5-7.0mmol/L. To avoid potential hypoglycaemia, Diabetes UK recommends a practical policy of “make four the floor”, i.e. 4.0mmol/L is the lowest acceptable blood glucose level in people with diabetes. In clinical practice, it can be defined as ”non-severe” if the episode is self-treated and “severe” if unable to self-treat and assistance by a third party is required (11).'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005147' vs 'MONDO:0005040'
- complication/hypoglycaemia: definition: 'The hospital management of hypoglycaemia in adults with diabetes mellitus' vs 'Hypoglycaemia with a glucose <3.0mmol/L recurred in in 39% and 45% of people with T2DM and T1DM respectively, in a study of over 17,000 hospital admissions (20).'
- complication/hypoglycaemia: mondoCode: 'MONDO:0005147' vs 'MONDO:0005005'

## 悬空关系样例

- `insulin` --hasContraindication--> `Hypoglycemia`（未找到）
- `insulin` --hasContraindication--> `Renal impairment`（未找到）
- `sulfonylurea` --hasContraindication--> `Hypoglycemia`（未找到）
- `sulfonylurea` --hasContraindication--> `Acute Kidney Injury`（未找到）
- `sulfonylurea` --hasContraindication--> `Renal Impairment`（未找到）
- `sulfonylurea` --hasContraindication--> `Renal impairment`（未找到）
- `blood-glucose` --hasThreshold--> `Hypoglycaemia`（未找到）
- `insulin-therapy` --increasesRiskOf--> `Hypoglycaemia`（未找到）
- `sulfonylurea-therapy` --increasesRiskOf--> `Hypoglycaemia`（未找到）
- `sulfonylurea-therapy` --increasesRiskOf--> `Hypoglycaemia`（未找到）
- `sulfonylurea-therapy` --increasesRiskOf--> `Nocturnal hypoglycaemia <3.9mmol/L`（未找到）
- `poorer-glycaemic-control` --increasesRiskOf--> `Hypoglycaemia`（未找到）
- `use-of-insulin-pumps` --increasesRiskOf--> `Hypoglycaemia`（未找到）
- `use-of-wearable-glucose-sensors` --increasesRiskOf--> `Hypoglycaemia`（未找到）
- `promotion-of-hypoglycaemia-rescue-treatment-prescription` --recommendsDrugClass--> `Intravenous Glucose`（未找到）
- `promotion-of-hypoglycaemia-rescue-treatment-prescription` --recommendsDrugClass--> `Intramuscular Glucagon`（未找到）
- `use-of-intravenous-glucose-for-fasting-patients` --recommendsDrugClass--> `Intravenous Glucose`（未找到）
- `long-acting-insulin` --hasContraindication--> `Acute Kidney Injury`（未找到）
- `long-acting-insulin` --hasContraindication--> `Renal Impairment`（未找到）
- `long-acting-insulin` --hasContraindication--> `Long-acting insulin`（未找到）
