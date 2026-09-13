# 抽取质量报告 — niddk-gestational-diabetes

- 源文件：`ontology/knowledges/niddk-gestational-diabetes.txt`（sha256 `d06560c0e6bf…`）
- 目标图：`urn:dmo:extract:niddk-gestational-diabetes`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：1

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **100.0%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 51.6% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 13.6% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.0 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 20 |
| 通过校验 | 20 |
| 丢弃 | 0 |
| 消解后实体 | 20 |
| 关系边 | 19 |
| 悬空关系 | 3 |
| 合并冲突 | 11 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| lifestyleIntervention | 5 |
| riskFactor | 4 |
| recommendation | 4 |
| labTest | 2 |
| symptom | 2 |
| diabetesType | 1 |
| medication | 1 |
| monitoringSchedule | 1 |

## 合并冲突样例

- symptom/thirstiness: name: 'Thirstiness' vs 'thirstier than normal'
- symptom/frequent-urination: name: 'Frequent Urination' vs 'having to urinate more often'
- riskFactor/extra-weight: name: 'Extra Weight' vs 'extra weight'
- riskFactor/being-physically-active-before-and-during-pregnancy: name: 'Being Physically Active Before and During Pregnancy' vs 'Being physically active before and during pregnancy'
- riskFactor/losing-extra-weight-before-pregnancy: name: 'Losing Extra Weight Before Pregnancy' vs 'Losing extra weight before pregnancy'
- medication/insulin: name: 'Insulin' vs 'insulin'
- lifestyleIntervention/healthy-eating-plan: name: 'Healthy Eating Plan' vs 'Healthy eating plan'
- lifestyleIntervention/being-physically-active: name: 'Being Physically Active' vs 'Being physically active'
- lifestyleIntervention/losing-extra-weight-before-pregnancy: name: 'Losing Extra Weight Before Pregnancy' vs 'Losing extra weight before pregnancy'
- lifestyleIntervention/making-healthy-food-choices: name: 'Making Healthy Food Choices' vs 'Making healthy food choices'
- lifestyleIntervention/being-physically-active-after-pregnancy: name: 'Being Physically Active After Pregnancy' vs 'Being physically active'

## 悬空关系样例

- `gestational-diabetes` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `glucose-challenge-test` --hasThreshold--> `Oral Glucose Tolerance Test`（未找到）
- `oral-glucose-tolerance-test` --hasThreshold--> `Glucose Challenge Test`（未找到）
