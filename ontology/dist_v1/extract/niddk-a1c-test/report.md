# 抽取质量报告 — niddk-a1c-test

- 源文件：`ontology/knowledges/niddk-a1c-test.txt`（sha256 `25ea9d16380f…`）
- 目标图：`urn:dmo:extract:niddk-a1c-test`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：3

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **87.7%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 61.3% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 10.3% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.06 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 65 |
| 通过校验 | 57 |
| 丢弃 | 8 |
| 消解后实体 | 54 |
| 关系边 | 52 |
| 悬空关系 | 6 |
| 合并冲突 | 15 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 8 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 19 |
| contraindication | 10 |
| labTest | 9 |
| complication | 5 |
| monitoringSchedule | 4 |
| riskFactor | 3 |
| diabetesType | 2 |
| lifestyleIntervention | 1 |
| adverseEffect | 1 |

## 合并冲突样例

- diabetesType/type-2-diabetes: definition: 'The A1C test can be used to diagnose type 2 diabetes and prediabetes.' vs 'to diagnose type 2 diabetes and prediabetes.'
- diabetesType/prediabetes: prevalenceShare: 0.05 vs 0.3
- diabetesType/prediabetes: definition: 'Having prediabetes is a risk factor for developing type 2 diabetes.' vs 'to diagnose type 2 diabetes and prediabetes.'
- riskFactor/prediabetes: name: 'Prediabetes' vs 'prediabetes'
- riskFactor/risk-factors-for-prediabetes-or-diabetes: name: 'Risk Factors for Prediabetes or Diabetes' vs 'risk factors for prediabetes or diabetes'
- monitoringSchedule/a1c-test: name: 'A1C Test' vs 'A1C test'
- monitoringSchedule/a1c-test: frequencyMonths: 3 vs 6
- monitoringSchedule/a1c-test: appliesTo: 'after diagnosis of diabetes' vs 'people with diabetes'
- complication/chronic-kidney-disease: name: 'Chronic Kidney Disease' vs 'chronic kidney disease'
- complication/nerve-problems: name: 'Nerve Problems' vs 'nerve problems'
- complication/cardiovascular-disease: name: 'Cardiovascular Disease' vs 'cardiovascular disease'
- complication/severe-hypoglycemia: name: 'Severe Hypoglycemia' vs 'severe hypoglycemia'
- complication/hypoglycemia-unawareness: name: 'Hypoglycemia Unawareness' vs 'hypoglycemia unawareness'
- riskFactor/limited-life-expectancy: name: 'Limited Life Expectancy' vs 'limited life expectancy'
- adverseEffect/hypoglycemia: name: 'Hypoglycemia' vs 'hypoglycemia'

## 悬空关系样例

- `diabetes-screening-for-women-with-prior-gestational-diabetes` --schedulesTest--> `Postpartum Diabetes Screening`（未找到）
- `a1c` --hasThreshold--> `Diabetes Diagnosis Threshold`（未找到）
- `fpg` --hasThreshold--> `Diabetes Diagnosis Threshold`（未找到）
- `ogtt-2h` --hasThreshold--> `Diabetes Diagnosis Threshold`（未找到）
- `random-plasma-glucose` --hasThreshold--> `Diabetes Diagnosis Threshold`（未找到）
- `estimated-average-glucose` --hasThreshold--> `7 percent`（未找到）
