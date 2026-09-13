# 抽取质量报告 — jbds_15_frail_older_adult_with_diabetes_february_2023

- 源文件：`ontology/knowledges/pdfs/JBDS_15_Frail_Older_Adult_with_Diabetes_February_2023.pdf`（sha256 `71911fcff2ec…`）
- 目标图：`urn:dmo:extract:jbds_15_frail_older_adult_with_diabetes_february_2023`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：47

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **83.9%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 96.8% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 75.3% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.19 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 921 |
| 通过校验 | 773 |
| 丢弃 | 148 |
| 消解后实体 | 650 |
| 关系边 | 77 |
| 悬空关系 | 235 |
| 合并冲突 | 366 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 118 |
| `quote_too_short` | 16 |
| `unknown_relation_predicate` | 14 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 293 |
| riskFactor | 131 |
| medication | 49 |
| contraindication | 38 |
| complication | 24 |
| drugClass | 23 |
| symptom | 21 |
| labTest | 19 |
| lifestyleIntervention | 15 |
| device | 13 |
| monitoringSchedule | 13 |
| diabetesType | 5 |
| adverseEffect | 5 |
| complicationStage | 1 |

## 合并冲突样例

- diabetesType/type-2-diabetes: mondoCode: 'MONDO:0005147' vs 'MONDO:0005148'
- diabetesType/type-2-diabetes: definition: 'The structure of the Guideline is based on the template of the International Diabetes Federation (IDF) Global Guideline on Managing Older People with Type 2 Diabetes (2013)' vs 'Consider DPP4-I as a first choice for treatment if necessary'
- diabetesType/type-2-diabetes: mondoCode: 'MONDO:0005147' vs 'MONDO:0005148'
- diabetesType/type-2-diabetes: definition: 'The structure of the Guideline is based on the template of the International Diabetes Federation (IDF) Global Guideline on Managing Older People with Type 2 Diabetes (2013)' vs 'The International Diabetes Federation (IDF) Global Guidance on Managing Older People with type 2 Diabetes provided for the first time care recommendations for those with dependency including frailty, dementia and end of life care, and the recent publication of an International Position Statement on the Management of Frailty in Diabetes Mellitus has drawn significant attention to the area of frailty and diabetes and highlighted the importance of all hospital clinicians involved in the care of such patients to have a high degree of familiarity and clinical experience in managing the associated problems of frailty and functional impairment.'
- diabetesType/type-2-diabetes: prevalenceShare: 0.9 vs 0.925
- diabetesType/type-2-diabetes: definition: 'The structure of the Guideline is based on the template of the International Diabetes Federation (IDF) Global Guideline on Managing Older People with Type 2 Diabetes (2013)' vs 'Current evidence for dementia in diabetes is predominantly from patients with type 2 diabetes given their older nature hence the majority of recommendations centre around medication review especially of oral medications.'
- diabetesType/type-2-diabetes: definition: 'The structure of the Guideline is based on the template of the International Diabetes Federation (IDF) Global Guideline on Managing Older People with Type 2 Diabetes (2013)' vs 'Current evidence for dementia in diabetes is predominantly from patients with type 2 diabetes given their older nature hence the majority of recommendations centre around medication review especially of oral medications.'
- diabetesType/type-2-diabetes: definition: 'The structure of the Guideline is based on the template of the International Diabetes Federation (IDF) Global Guideline on Managing Older People with Type 2 Diabetes (2013)' vs 'Statin therapy is recommended in order to reduce cardiovascular risk unless specifically contraindicated: consider offering Atorvastatin 20mg for the primary prevention of CVD in those with type 2 diabetes if the person is aged 84 years and younger, are well functioning with mild evidence of frailty only, and their estimated 10-year risk of developing cardiovascular disease using the QRISK®23 assessment tool is 10% or more'
- diabetesType/type-2-diabetes: definition: 'The structure of the Guideline is based on the template of the International Diabetes Federation (IDF) Global Guideline on Managing Older People with Type 2 Diabetes (2013)' vs 'older inpatients with diabetes and frailty'
- diabetesType/type-2-diabetes: definition: 'The structure of the Guideline is based on the template of the International Diabetes Federation (IDF) Global Guideline on Managing Older People with Type 2 Diabetes (2013)' vs 'Insulin regimens in type 2 diabetes should be simplified; these individuals may only require a single injection of intermediate insulin e.g. Insuman Basal, Humulin I, Insulatard'
- complication/inpatient-hypoglycaemia: mondoCode: 'MONDO:0005147' vs 'MONDO:0019075'
- diabetesType/type-1-diabetes: prevalenceShare: 0.05 vs 0.1
- diabetesType/type-1-diabetes: definition: 'Do not deny insulin in T1D' vs 'The Writing Group also recognises that there is a paucity of specific studies on managing frailty in those with diabetes in any clinical setting, and emphasise the need for a minimum best clinical practice approach where such evidence is totally lacking.'
- diabetesType/type-1-diabetes: typicalOnset: 'Childhood' vs 'Adolescence'
- diabetesType/type-1-diabetes: definition: 'Do not deny insulin in T1D' vs 'Older patients with type 1 diabetes are especially vulnerable to hospital admission with DKA and HHS particularly when unwell'
- diabetesType/type-1-diabetes: name: 'Type 1 Diabetes' vs 'Type 1 diabetes'
- diabetesType/type-1-diabetes: definition: 'Do not deny insulin in T1D' vs 'Inpatients with type 1 diabetes should not have their insulin treatment withdrawn'
- diabetesType/type-1-diabetes: name: 'Type 1 Diabetes' vs 'Type 1 diabetes'
- diabetesType/type-1-diabetes: definition: 'Do not deny insulin in T1D' vs 'Patients with Type 1 diabetes have an absolute deficiency of insulin and there must always be insulin on board at all times.'
- labTest/hba1c: definition: 'Measure HbA1c and gauge control over previous 2 months' vs 'HbA1c is used to determine the need for immediate referral to the diabetes inpatient team (DIT) in pre-operative care.'

## 悬空关系样例

- `hba1c` --hasThreshold--> `HbA1c >69 mmol/mol`（未找到）
- `hba1c` --hasThreshold--> `HbA1c 7.5-8.5%`（未找到）
- `random-glucose` --hasThreshold--> `Mild F 7.5 - 10 mmol.l`（未找到）
- `random-glucose` --hasThreshold--> `ModF-SF 7.5-12 mmol/l`（未找到）
- `frailty` --increasesRiskOf--> `Functional Decline`（未找到）
- `frailty` --increasesRiskOf--> `Poor Clinical Outcomes`（未找到）
- `frailty` --increasesRiskOf--> `Disability`（未找到）
- `frailty` --increasesRiskOf--> `Hyperglycaemia`（未找到）
- `frailty` --increasesRiskOf--> `Hypoglycaemia`（未找到）
- `frailty` --increasesRiskOf--> `Falls`（未找到）
- `frailty` --increasesRiskOf--> `Sepsis`（未找到）
- `frailty` --increasesRiskOf--> `Cardiovascular Events`（未找到）
- `frailty` --increasesRiskOf--> `Increased Length of Stay`（未找到）
- `frailty` --increasesRiskOf--> `Readmissions`（未找到）
- `frailty` --increasesRiskOf--> `At-risk Foot`（未找到）
- `frailty` --increasesRiskOf--> `Hypoglycemia`（未找到）
- `frailty` --increasesRiskOf--> `Hospitalization`（未找到）
- `frailty` --increasesRiskOf--> `Cognitive Impairment`（未找到）
- `frailty` --increasesRiskOf--> `Delirium`（未找到）
- `frailty` --increasesRiskOf--> `Post-operative Delirium`（未找到）
