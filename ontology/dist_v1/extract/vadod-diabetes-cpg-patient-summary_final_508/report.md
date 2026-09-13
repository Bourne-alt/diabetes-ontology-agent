# 抽取质量报告 — vadod-diabetes-cpg-patient-summary_final_508

- 源文件：`ontology/knowledges/pdfs/VADOD-Diabetes-CPG-Patient-Summary_final_508.pdf`（sha256 `d81bc580c61f…`）
- 目标图：`urn:dmo:extract:vadod-diabetes-cpg-patient-summary_final_508`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：2

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **87.5%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 69.3% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 13.7% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.02 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 72 |
| 通过校验 | 63 |
| 丢弃 | 9 |
| 消解后实体 | 62 |
| 关系边 | 44 |
| 悬空关系 | 7 |
| 合并冲突 | 13 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 6 |
| `quote_too_short` | 3 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 14 |
| riskFactor | 13 |
| monitoringSchedule | 9 |
| lifestyleIntervention | 8 |
| labTest | 7 |
| diabetesType | 4 |
| complication | 4 |
| complicationStage | 1 |
| symptom | 1 |
| device | 1 |

## 合并冲突样例

- labTest/hba1c: definition: 'A measure of average blood glucose over the past 2-3 months, used to diagnose diabetes and monitor long-term glucose control.' vs 'A measure of average blood glucose over the past 2-3 months.'
- riskFactor/overweight-or-obesity: name: 'Overweight or Obesity' vs 'Overweight or obesity'
- riskFactor/history-of-prediabetes: name: 'History of Prediabetes' vs 'History of prediabetes'
- riskFactor/first-degree-relative-with-type-2-diabetes-mellitus: name: 'First-Degree Relative with Type 2 Diabetes Mellitus' vs 'First-degree relative with T2DM'
- riskFactor/high-prevalence-population: name: 'High Prevalence Population' vs 'High prevalence population'
- riskFactor/high-blood-pressure: name: 'High Blood Pressure' vs 'High blood pressure'
- riskFactor/high-density-lipoprotein-cholesterol-level-35-mg-dl-and-or-triglyceride-level-250-mg-dl: name: 'High-Density Lipoprotein Cholesterol Level <35 mg/dL and/or Triglyceride Level >250 mg/dL' vs 'Lipids'
- riskFactor/gestational-diabetes-or-history-of-delivering-a-baby-weighing-9-pounds: name: 'Gestational Diabetes or History of Delivering a Baby Weighing >9 Pounds' vs 'Gestational diabetes or a history of delivering a baby weighing >9 pounds'
- riskFactor/history-of-cardiovascular-disease: name: 'History of Cardiovascular Disease' vs 'History of cardiovascular disease'
- riskFactor/polycystic-ovary-syndrome: name: 'Polycystic Ovary Syndrome' vs 'Polycystic ovary syndrome'
- riskFactor/physical-inactivity-or-a-sedentary-lifestyle: name: 'Physical Inactivity or a Sedentary Lifestyle' vs 'Physical inactivity or a sedentary lifestyle'
- riskFactor/patients-using-certain-medications-for-human-immunodeficiency-virus: name: 'Patients Using Certain Medications for Human Immunodeficiency Virus' vs 'Patients using certain medications for human immunodeficiency virus'
- riskFactor/patients-using-antipsychotic-or-statin-medications: name: 'Patients Using Antipsychotic or Statin Medications' vs 'Patients using antipsychotic or statin medications'

## 悬空关系样例

- `prediabetes` --predisposesTo--> `Type 2 Diabetes Mellitus`（未找到）
- `hba1c` --hasThreshold--> `HbA1c ≥ 6.5%`（未找到）
- `fasting-blood-sugar` --hasThreshold--> `Fasting Blood Sugar 100–125 mg/dL`（未找到）
- `blood-pressure` --hasThreshold--> `Blood Pressure >140/90 mmHg`（未找到）
- `high-density-lipoprotein-cholesterol` --hasThreshold--> `HDL Cholesterol <35 mg/dL`（未找到）
- `triglycerides` --hasThreshold--> `Triglycerides >250 mg/dL`（未找到）
- `use-the-rule-of-15` --definesTarget--> `Blood sugar less than 70mg/dl`（未找到）
