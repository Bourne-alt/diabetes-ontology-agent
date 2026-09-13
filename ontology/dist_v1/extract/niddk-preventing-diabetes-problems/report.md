# 抽取质量报告 — niddk-preventing-diabetes-problems

- 源文件：`ontology/knowledges/niddk-preventing-diabetes-problems.txt`（sha256 `48dc8bd409f8…`）
- 目标图：`urn:dmo:extract:niddk-preventing-diabetes-problems`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：1

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **76.9%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 32.3% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 77.1% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.14 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 65 |
| 通过校验 | 50 |
| 丢弃 | 15 |
| 消解后实体 | 44 |
| 关系边 | 11 |
| 悬空关系 | 37 |
| 合并冲突 | 2 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `unknown_relation_predicate` | 12 |
| `quote_not_found` | 3 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| lifestyleIntervention | 15 |
| recommendation | 12 |
| complication | 11 |
| riskFactor | 4 |
| adverseEffect | 1 |
| monitoringSchedule | 1 |

## 合并冲突样例

- riskFactor/high-blood-pressure: name: 'High Blood Pressure' vs 'High blood pressure'
- riskFactor/high-cholesterol: name: 'High Cholesterol' vs 'High cholesterol'

## 悬空关系样例

- `diabetes` --increasesRiskOf--> `Heart Disease & Stroke`（未找到）
- `diabetes` --increasesRiskOf--> `Low Blood Glucose (Hypoglycemia)`（未找到）
- `diabetes` --increasesRiskOf--> `Diabetic Neuropathy`（未找到）
- `diabetes` --increasesRiskOf--> `Diabetic Kidney Disease`（未找到）
- `diabetes` --increasesRiskOf--> `Diabetes & Foot Problems`（未找到）
- `diabetes` --increasesRiskOf--> `Diabetic Eye Disease`（未找到）
- `diabetes` --increasesRiskOf--> `Diabetes, Gum Disease, & Other Dental Problems`（未找到）
- `diabetes` --increasesRiskOf--> `Diabetes, Sexual, & Bladder Problems`（未找到）
- `diabetes` --increasesRiskOf--> `Depression & Diabetes`（未找到）
- `diabetes` --increasesRiskOf--> `Cancer & Diabetes`（未找到）
- `diabetes` --increasesRiskOf--> `Dementia & Diabetes`（未找到）
- `diabetes` --increasesRiskOf--> `Sleep Apnea & Diabetes`（未找到）
- `high-blood-pressure` --increasesRiskOf--> `Heart Disease & Stroke`（未找到）
- `high-blood-pressure` --increasesRiskOf--> `Diabetic Kidney Disease`（未找到）
- `high-cholesterol` --increasesRiskOf--> `Heart Disease & Stroke`（未找到）
- `smoking` --increasesRiskOf--> `Heart Disease & Stroke`（未找到）
- `smoking` --increasesRiskOf--> `Diabetic Eye Disease`（未找到）
- `smoking` --increasesRiskOf--> `Diabetes, Gum Disease, & Other Dental Problems`（未找到）
- `managing-blood-glucose-blood-pressure-and-cholesterol-levels` --appliesToType--> `Diabetes`（未找到）
- `managing-blood-glucose-blood-pressure-and-cholesterol-levels` --targetsComplication--> `Diabetes, Heart Disease, & Stroke`（未找到）
