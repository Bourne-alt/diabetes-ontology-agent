# 抽取质量报告 — cdc-hypoglycemia

- 源文件：`ontology/knowledges/cdc-hypoglycemia.txt`（sha256 `78367648b510…`）
- 目标图：`urn:dmo:extract:cdc-hypoglycemia`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：1

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **64.3%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 50.0% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 53.6% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.0 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 42 |
| 通过校验 | 27 |
| 丢弃 | 15 |
| 消解后实体 | 27 |
| 关系边 | 13 |
| 悬空关系 | 15 |
| 合并冲突 | 8 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 11 |
| `quote_too_short` | 3 |
| `unknown_relation_predicate` | 1 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| riskFactor | 8 |
| lifestyleIntervention | 5 |
| recommendation | 5 |
| complication | 3 |
| symptom | 3 |
| diabetesType | 1 |
| complicationStage | 1 |
| device | 1 |

## 合并冲突样例

- riskFactor/having-diabetes-for-more-than-5-10-years: name: 'Having Diabetes for More Than 5–10 Years' vs 'Having diabetes for more than 5–10 years'
- riskFactor/taking-too-much-insulin: name: 'Taking Too Much Insulin' vs 'Taking too much insulin'
- riskFactor/not-eating-enough-carbohydrates-for-how-much-insulin-you-take: name: 'Not Eating Enough Carbohydrates for How Much Insulin You Take' vs 'Not eating enough carbohydrates for how much insulin you take'
- riskFactor/timing-of-when-you-take-your-insulin: name: 'Timing of When You Take Your Insulin' vs 'Timing of when you take your insulin'
- riskFactor/the-amount-and-timing-of-physical-activity: name: 'The Amount and Timing of Physical Activity' vs 'The amount and timing of physical activity'
- riskFactor/unexpected-changes-in-your-schedule: name: 'Unexpected Changes in Your Schedule' vs 'Unexpected changes in your schedule'
- riskFactor/spending-time-at-a-high-altitude: name: 'Spending Time at a High Altitude' vs 'Spending time at a high altitude'
- riskFactor/having-your-period-menstruation: name: 'Having Your Period (Menstruation)' vs 'Having your period (menstruation)'

## 悬空关系样例

- `hypoglycemia-unawareness` --presentsWith--> `Low Blood Sugar`（未找到）
- `having-diabetes-for-more-than-5-10-years` --increasesRiskOf--> `Hypoglycemia Unawareness`（未找到）
- `taking-too-much-insulin` --increasesRiskOf--> `Low Blood Sugar`（未找到）
- `not-eating-enough-carbohydrates-for-how-much-insulin-you-take` --increasesRiskOf--> `Low Blood Sugar`（未找到）
- `timing-of-when-you-take-your-insulin` --increasesRiskOf--> `Low Blood Sugar`（未找到）
- `the-amount-and-timing-of-physical-activity` --increasesRiskOf--> `Low Blood Sugar`（未找到）
- `unexpected-changes-in-your-schedule` --increasesRiskOf--> `Low Blood Sugar`（未找到）
- `spending-time-at-a-high-altitude` --increasesRiskOf--> `Low Blood Sugar`（未找到）
- `having-your-period-menstruation` --increasesRiskOf--> `Low Blood Sugar`（未找到）
- `check-blood-sugar-more-often` --appliesToType--> `Hypoglycemia Unawareness`（未找到）
- `check-blood-sugar-more-often` --definesTarget--> `Blood Sugar Level Below 70 mg/dL`（未找到）
- `have-a-snack-before-bed` --appliesToType--> `Nighttime Low Blood Sugar`（未找到）
- `use-continuous-glucose-monitor-cgm` --appliesToType--> `Nighttime Low Blood Sugar`（未找到）
- `eat-when-drinking-alcohol` --appliesToType--> `Nighttime Low Blood Sugar`（未找到）
- `eat-regular-meals` --appliesToType--> `Nighttime Low Blood Sugar`（未找到）
