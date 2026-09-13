# 抽取质量报告 — ada-kdigo-consensus-report-diabetes-ckd-diabetes-care-2022

- 源文件：`ontology/knowledges/pdfs/ADA-KDIGO-Consensus-Report-Diabetes-CKD-Diabetes-Care-2022.pdf`（sha256 `e63a1f405f3d…`）
- 目标图：`urn:dmo:extract:ada-kdigo-consensus-report-diabetes-ckd-diabetes-care-2022`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：18

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **36.4%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 98.4% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 52.0% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.14 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 503 |
| 通过校验 | 183 |
| 丢弃 | 320 |
| 消解后实体 | 161 |
| 关系边 | 36 |
| 悬空关系 | 39 |
| 合并冲突 | 70 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 295 |
| `quote_too_short` | 25 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| medication | 43 |
| recommendation | 32 |
| drugClass | 14 |
| contraindication | 14 |
| complication | 9 |
| riskFactor | 7 |
| labTest | 7 |
| monitoringSchedule | 6 |
| lifestyleIntervention | 6 |
| adverseEffect | 6 |
| symptom | 6 |
| diabetesType | 4 |
| complicationStage | 4 |
| device | 3 |

## 合并冲突样例

- diabetesType/t1d: name: 'T1D' vs 'Type 1 Diabetes'
- diabetesType/t2d: name: 'T2D' vs 'Type 2 Diabetes'
- labTest/urine-albumin-to-creatinine-ratio: name: 'Urine Albumin-to-Creatinine Ratio' vs 'urine albumin-to-creatinine ratio'
- labTest/urine-albumin-to-creatinine-ratio: loincCode: '2951-2' vs '29515-2'
- labTest/urine-albumin-to-creatinine-ratio: unitOfMeasure: 'mg/g' vs 'mg-per-g'
- labTest/urine-albumin-to-creatinine-ratio: definition: 'Persistent urine ACR ≥30 mg/g defines CKD diagnosis.' vs 'urine albumin-to-creatinine ratio'
- labTest/estimated-glomerular-filtration-rate: loincCode: '30954-2' vs '21600-0'
- labTest/estimated-glomerular-filtration-rate: unitOfMeasure: 'mL/min/1.73 m2' vs 'mL-per-min-per-1.73-m2'
- labTest/estimated-glomerular-filtration-rate: definition: 'Persistent eGFR <60 mL/min/1.73 m2 defines CKD diagnosis.' vs 'A measure of kidney function based on serum creatinine, age, sex, and race, used to stage chronic kidney disease.'
- complication/chronic-kidney-disease: mondoCode: 'MONDO:0005146' vs 'MONDO:0005148'
- complication/chronic-kidney-disease: definition: 'Persistent abnormalities in either urine ACR or eGFR (or both) diagnose CKD and should lead to immediate initiation of evidence-based treatments.' vs 'CKD is a condition characterized by reduced kidney function or structural damage, often associated with diabetes and contributing to increased risk of cardiovascular events and mortality.'
- complication/chronic-kidney-disease: mondoCode: 'MONDO:0005146' vs 'MONDO:0005737'
- complication/chronic-kidney-disease: definition: 'Persistent abnormalities in either urine ACR or eGFR (or both) diagnose CKD and should lead to immediate initiation of evidence-based treatments.' vs 'Chronic kidney disease (CKD) is a condition characterized by reduced kidney function over a period of time, often defined by an estimated glomerular filtration rate (eGFR) <60 mL/min/1.73 m² for at least 3 months.'
- riskFactor/smoking: name: 'Smoking' vs 'smoking'
- medication/sglt2i: name: 'SGLT2i' vs 'SGLT2 inhibitor'
- medication/glp-1-ra: name: 'GLP-1 RA' vs 'GLP-1 receptor agonist'
- medication/nonsteroidal-mra: name: 'Nonsteroidal MRA' vs 'nonsteroidal mineralocorticoid receptor antagonist'
- medication/dihydropyridine-ccb: name: 'Dihydropyridine CCB' vs 'dihydropyridine calcium channel blocker'
- medication/antiplatelet-agent: name: 'Antiplatelet agent' vs 'antiplatelet agent'
- medication/steroidal-mra: name: 'Steroidal MRA' vs 'steroidal mineralocorticoid receptor antagonist'

## 悬空关系样例

- `urine-albumin-to-creatinine-ratio` --hasThreshold--> `ACR ≥30 mg/g`（未找到）
- `estimated-glomerular-filtration-rate` --hasThreshold--> `eGFR <60 mL/min/1.73 m2`（未找到）
- `urine-albumin-to-creatinine-ratio` --schedulesTest--> `Chronic Kidney Disease`（未找到）
- `estimated-glomerular-filtration-rate` --schedulesTest--> `Chronic Kidney Disease`（未找到）
- `diagnose-ckd-based-on-persistent-abnormalities` --appliesToType--> `Screening for CKD in People with Diabetes`（未找到）
- `initiate-evidence-based-treatments-after-ckd-diagnosis` --appliesToType--> `Diagnose CKD Based on Persistent Abnormalities`（未找到）
- `include-lifestyle-interventions-in-overall-care-plan` --appliesToType--> `Use Multidisciplinary Team Care for Diabetes and CKD Management`（未找到）
- `smoking` --increasesRiskOf--> `Cardiovascular Disease`（未找到）
- `smoking` --increasesRiskOf--> `Chronic Kidney Disease`（未找到）
- `an-acei-or-arb-is-recommended-for-patients-with-t1d-or-t2d-who-have-hypertension-and-albuminuria-titrated-to-the-maximum-antihypertensive-or-highest-tolerated-dose` --targetsComplication--> `Hypertension`（未找到）
- `an-acei-or-arb-is-recommended-for-patients-with-t1d-or-t2d-who-have-hypertension-and-albuminuria-titrated-to-the-maximum-antihypertensive-or-highest-tolerated-dose` --recommendsDrugClass--> `ACE inhibitor`（未找到）
- `an-acei-or-arb-is-recommended-for-patients-with-t1d-or-t2d-who-have-hypertension-and-albuminuria-titrated-to-the-maximum-antihypertensive-or-highest-tolerated-dose` --recommendsDrugClass--> `ARB`（未找到）
- `acute-kidney-injury` --increasesRiskOf--> `Metformin-Associated Lactic Acidosis`（未找到）
- `sglt2-inhibitors` --hasContraindication--> `Diabetic ketoacidosis`（未找到）
- `sglt2-inhibitors` --hasContraindication--> `Volume depletion`（未找到）
- `sglt2-inhibitors` --hasContraindication--> `Genital mycotic infections`（未找到）
- `glp-1-receptor-agonists` --hasContraindication--> `Nausea/vomiting/diarrhea`（未找到）
- `glp-1-receptor-agonists` --hasContraindication--> `Hypoglycemia`（未找到）
- `metformin` --hasContraindication--> `B12 malabsorption`（未找到）
- `use-of-an-sglt2i-or-glp-1-receptor-agonist-in-patients-with-t2d-who-have-established-ascvd-or-established-kidney-disease` --citesSource--> `ADA Living Standards of Care Guideline Update Process`（未找到）
