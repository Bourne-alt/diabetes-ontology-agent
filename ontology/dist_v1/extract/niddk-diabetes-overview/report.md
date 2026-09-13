# 抽取质量报告 — niddk-diabetes-overview

- 源文件：`ontology/knowledges/niddk-diabetes-overview.txt`（sha256 `f399dbc57da1…`）
- 目标图：`urn:dmo:extract:niddk-diabetes-overview`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：2

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **95.0%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 37.1% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 10.7% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.0 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 20 |
| 通过校验 | 19 |
| 丢弃 | 1 |
| 消解后实体 | 19 |
| 关系边 | 25 |
| 悬空关系 | 3 |
| 合并冲突 | 4 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 1 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| complication | 6 |
| diabetesType | 5 |
| riskFactor | 4 |
| recommendation | 3 |
| lifestyleIntervention | 1 |

## 合并冲突样例

- riskFactor/overweight-or-obesity: name: 'Overweight or Obesity' vs 'overweight or obesity'
- riskFactor/family-history-of-type-2-diabetes: name: 'Family History of Type 2 Diabetes' vs 'family history of the disease'
- riskFactor/gestational-diabetes-history: name: 'Gestational Diabetes History' vs 'GDM history'
- riskFactor/prediabetes: name: 'Prediabetes' vs 'prediabetes'

## 悬空关系样例

- `prediabetes` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `managing-diabetes` --appliesToType--> `Diabetes`（未找到）
- `preventing-diabetes-health-problems` --appliesToType--> `Diabetes`（未找到）
