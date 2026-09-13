# 抽取质量报告 — kdigo-2022-clinical-practice-guideline-for-diabetes-management-in-ckd

- 源文件：`ontology/knowledges/pdfs/KDIGO-2022-Clinical-Practice-Guideline-for-Diabetes-Management-in-CKD.pdf`（sha256 `d2889a8b699e…`）
- 目标图：`urn:dmo:extract:kdigo-2022-clinical-practice-guideline-for-diabetes-management-in-ckd`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：123

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **49.0%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 98.4% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 77.9% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.59 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 1839 |
| 通过校验 | 902 |
| 丢弃 | 937 |
| 消解后实体 | 568 |
| 关系边 | 96 |
| 悬空关系 | 338 |
| 合并冲突 | 639 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 840 |
| `quote_too_short` | 74 |
| `unknown_relation_predicate` | 23 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 118 |
| lifestyleIntervention | 85 |
| medication | 80 |
| riskFactor | 70 |
| contraindication | 44 |
| labTest | 39 |
| complication | 34 |
| adverseEffect | 23 |
| drugClass | 21 |
| monitoringSchedule | 21 |
| device | 12 |
| complicationStage | 10 |
| diabetesType | 8 |
| symptom | 3 |

## 合并冲突样例

- drugClass/glp-1-ra: mechanism: 'Glucagon-like peptide-1 receptor agonist' vs 'Activates glucagon-like peptide-1 receptors, enhancing glucose-dependent insulin secretion and suppressing glucagon secretion'
- drugClass/glp-1-ra: mechanism: 'Glucagon-like peptide-1 receptor agonist' vs 'Activates glucagon-like peptide-1 receptors, enhancing glucose-dependent insulin secretion and suppressing glucagon secretion'
- drugClass/glp-1-ra: mechanism: 'Glucagon-like peptide-1 receptor agonist' vs 'Enhance glucose-dependent insulin secretion, suppress inappropriately high glucagon secretion, slow gastric emptying, and promote satiety.'
- drugClass/sglt2i: mechanism: 'Sodium-glucose co-transporter 2 inhibitor' vs 'Inhibits sodium-glucose cotransporter-2 in the proximal tubule, promoting urinary glucose excretion'
- drugClass/sglt2i: mechanism: 'Sodium-glucose co-transporter 2 inhibitor' vs 'Inhibits sodium-glucose cotransporter-2 in the proximal tubule, promoting urinary glucose excretion'
- drugClass/sglt2i: mechanism: 'Sodium-glucose co-transporter 2 inhibitor' vs 'Inhibits sodium-glucose co-transporter 2 in the proximal tubule of the kidney, promoting urinary glucose excretion and lowering blood glucose levels.'
- drugClass/sglt2i: mechanism: 'Sodium-glucose co-transporter 2 inhibitor' vs 'inhibits sodium-glucose co-transporter 2 in the proximal tubule, leading to increased urinary glucose excretion'
- drugClass/sglt2i: weightEffect: 'Loss' vs 'Neutral'
- drugClass/sglt2i: mechanism: 'Sodium-glucose co-transporter 2 inhibitor' vs 'Sodium-glucose co-transporter 2 inhibitors'
- drugClass/insulin: mechanism: 'Insulin replacement therapy' vs 'Exogenous insulin replacement to lower blood glucose levels.'
- drugClass/insulin: mechanism: 'Insulin replacement therapy' vs 'Directly replaces endogenous insulin, promoting glucose uptake in muscle and adipose tissue and suppressing hepatic glucose production.'
- drugClass/insulin: name: 'Insulin' vs 'insulin'
- drugClass/insulin: mechanism: 'Insulin replacement therapy' vs 'Insulin lowers blood glucose by promoting glucose uptake in muscle and fat and inhibiting hepatic glucose production.'
- drugClass/insulin: atcCode: 'A10A' vs 'A10AA01'
- drugClass/insulin: mechanism: 'Insulin replacement therapy' vs 'Directly lowers blood glucose by promoting glucose uptake in muscle and fat and inhibiting hepatic glucose production.'
- medication/insulin-degludec: name: 'Insulin degludec' vs 'insulin degludec'
- medication/insulin-glargine: name: 'Insulin glargine' vs 'insulin glargine'
- medication/insulin-glargine: name: 'Insulin glargine' vs 'insulin glargine'
- medication/insulin-glargine: name: 'Insulin glargine' vs 'insulin glargine'
- medication/thiazolidinedione: name: 'Thiazolidinedione' vs 'thiazolidinedione'

## 悬空关系样例

- `sglt2i` --hasContraindication--> `volume depletion`（未找到）
- `sglt2i` --hasContraindication--> `genital infections`（未找到）
- `sglt2i` --hasContraindication--> `lower-limb amputation due to foot ulcerations`（未找到）
- `sglt2i` --hasContraindication--> `urinary tract infections`（未找到）
- `sglt2i` --hasContraindication--> `kidney transplant recipients`（未找到）
- `sglt2i` --hasContraindication--> `hyperkalemia`（未找到）
- `continuous-glucose-monitoring` --deviceMeasuresTest--> `glucose`（未找到）
- `albumin-to-creatinine-ratio` --hasThreshold--> `A1`（未找到）
- `albumin-to-creatinine-ratio` --hasThreshold--> `A2`（未找到）
- `albumin-to-creatinine-ratio` --hasThreshold--> `A3`（未找到）
- `glycated-hemoglobin` --hasThreshold--> `DCCT (%)`（未找到）
- `albuminuria` --hasThreshold--> `Moderately increased albuminuria`（未找到）
- `albuminuria` --hasThreshold--> `Severely increased albuminuria`（未找到）
- `cardiovascular-disease` --presentsWith--> `Albuminuria`（未找到）
- `albuminuria` --presentsWith--> `Chronic Kidney Disease`（未找到）
- `smoking` --increasesRiskOf--> `Cardiovascular Disease`（未找到）
- `smoking` --increasesRiskOf--> `Kidney Disease Progression`（未找到）
- `smoking` --increasesRiskOf--> `Atherosclerotic Cardiovascular Disease`（未找到）
- `smoking` --increasesRiskOf--> `Cardiovascular Complications`（未找到）
- `smoking` --increasesRiskOf--> `Chronic Kidney Disease`（未找到）
