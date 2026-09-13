# 抽取质量报告 — cdc-diabetic-ketoacidosis

- 源文件：`ontology/knowledges/cdc-diabetic-ketoacidosis.txt`（sha256 `cc31c4bd559d…`）
- 目标图：`urn:dmo:extract:cdc-diabetic-ketoacidosis`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：1

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **59.5%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 48.4% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 23.5% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.0 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 42 |
| 通过校验 | 25 |
| 丢弃 | 17 |
| 消解后实体 | 25 |
| 关系边 | 26 |
| 悬空关系 | 8 |
| 合并冲突 | 6 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 13 |
| `quote_too_short` | 4 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 9 |
| riskFactor | 6 |
| symptom | 3 |
| diabetesType | 2 |
| labTest | 2 |
| complication | 1 |
| lifestyleIntervention | 1 |
| device | 1 |

## 合并冲突样例

- riskFactor/missing-insulin-shots: name: 'Missing Insulin Shots' vs 'Missing insulin shots'
- riskFactor/clogged-insulin-pump: name: 'Clogged Insulin Pump' vs 'Clogged insulin pump'
- riskFactor/wrong-insulin-dose: name: 'Wrong Insulin Dose' vs 'Wrong insulin dose'
- riskFactor/physical-injury: name: 'Physical Injury' vs 'Physical injury'
- riskFactor/certain-medicines: name: 'Certain Medicines' vs 'Certain medicines'
- device/ketone-test-kit: name: 'Ketone Test Kit' vs 'Ketone test kit'

## 悬空关系样例

- `urine-ketones` --hasThreshold--> `Blood Glucose 250 mg/dL`（未找到）
- `blood-glucose` --hasThreshold--> `Blood Glucose 250 mg/dL`（未找到）
- `missing-insulin-shots` --increasesRiskOf--> `Diabetic Ketoacidosis`（未找到）
- `clogged-insulin-pump` --increasesRiskOf--> `Diabetic Ketoacidosis`（未找到）
- `wrong-insulin-dose` --increasesRiskOf--> `Diabetic Ketoacidosis`（未找到）
- `illness` --increasesRiskOf--> `Diabetic Ketoacidosis`（未找到）
- `physical-injury` --increasesRiskOf--> `Diabetic Ketoacidosis`（未找到）
- `certain-medicines` --increasesRiskOf--> `Diabetic Ketoacidosis`（未找到）
