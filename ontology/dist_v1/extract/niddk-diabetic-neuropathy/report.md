# 抽取质量报告 — niddk-diabetic-neuropathy

- 源文件：`ontology/knowledges/niddk-diabetic-neuropathy.txt`（sha256 `a0957384924b…`）
- 目标图：`urn:dmo:extract:niddk-diabetic-neuropathy`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：2

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **63.2%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 29.0% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 67.6% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.03 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 57 |
| 通过校验 | 36 |
| 丢弃 | 21 |
| 消解后实体 | 35 |
| 关系边 | 12 |
| 悬空关系 | 25 |
| 合并冲突 | 11 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 15 |
| `unknown_relation_predicate` | 6 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 14 |
| riskFactor | 9 |
| complication | 7 |
| lifestyleIntervention | 3 |
| monitoringSchedule | 2 |

## 合并冲突样例

- complication/peripheral-neuropathy: mondoCode: 'MONDO:0005147' vs 'MONDO:0005148'
- complication/peripheral-neuropathy: definition: 'Peripheral neuropathy is nerve damage that typically affects the feet and legs and sometimes affects the hands and arms.' vs 'Foot care is very important for all people with diabetes, and it’s even more important if you have peripheral neuropathy.'
- riskFactor/older-age: name: 'Older Age' vs 'older age'
- riskFactor/longer-duration-of-diabetes: name: 'Longer Duration of Diabetes' vs 'longer duration of diabetes'
- riskFactor/overweight: name: 'Overweight' vs 'overweight'
- riskFactor/genetic-predisposition: name: 'Genetic Predisposition' vs 'certain genes may make people more likely to develop diabetic neuropathy'
- riskFactor/smoking: name: 'Smoking' vs 'smoking'
- riskFactor/poor-glycemic-control: name: 'Poor Glycemic Control' vs 'poor blood glucose control'
- riskFactor/high-blood-pressure: name: 'High Blood Pressure' vs 'high blood pressure'
- riskFactor/high-cholesterol-levels: name: 'High Cholesterol Levels' vs 'high cholesterol levels'
- riskFactor/obesity: name: 'Obesity' vs 'obesity'

## 悬空关系样例

- `peripheral-neuropathy` --hasStage--> `Diabetic Neuropathy`（未找到）
- `foot-complications` --presentsWith--> `Peripheral Neuropathy`（未找到）
- `balance-and-coordination-problems` --presentsWith--> `Peripheral Neuropathy`（未找到）
- `older-age` --increasesRiskOf--> `Diabetic Neuropathy`（未找到）
- `longer-duration-of-diabetes` --increasesRiskOf--> `Diabetic Neuropathy`（未找到）
- `overweight` --increasesRiskOf--> `Diabetic Neuropathy`（未找到）
- `genetic-predisposition` --increasesRiskOf--> `Diabetic Neuropathy`（未找到）
- `manage-blood-glucose-levels` --appliesToType--> `Diabetic Neuropathy`（未找到）
- `manage-blood-pressure-levels` --appliesToType--> `Diabetic Neuropathy`（未找到）
- `manage-cholesterol-levels` --appliesToType--> `Diabetic Neuropathy`（未找到）
- `be-physically-active` --appliesToType--> `Diabetic Neuropathy`（未找到）
- `limit-alcoholic-drinks` --appliesToType--> `Diabetic Neuropathy`（未找到）
- `take-prescribed-diabetes-medicines` --appliesToType--> `Diabetic Neuropathy`（未找到）
- `manage-blood-glucose-levels-to-prevent-worsening` --appliesToType--> `Diabetic Neuropathy`（未找到）
- `manage-blood-pressure-levels-to-prevent-worsening` --appliesToType--> `Diabetic Neuropathy`（未找到）
- `manage-cholesterol-levels-to-prevent-worsening` --appliesToType--> `Diabetic Neuropathy`（未找到）
- `manage-weight-to-prevent-worsening` --appliesToType--> `Diabetic Neuropathy`（未找到）
- `smoking` --increasesRiskOf--> `Diabetic Neuropathy`（未找到）
- `poor-glycemic-control` --increasesRiskOf--> `Diabetic Neuropathy`（未找到）
- `high-blood-pressure` --increasesRiskOf--> `Diabetic Neuropathy`（未找到）
