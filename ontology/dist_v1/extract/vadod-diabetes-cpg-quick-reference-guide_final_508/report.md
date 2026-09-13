# 抽取质量报告 — vadod-diabetes-cpg-quick-reference-guide_final_508

- 源文件：`ontology/knowledges/pdfs/VADOD-Diabetes-CPG-Quick-Reference-Guide_final_508.pdf`（sha256 `f10e4025f368…`）
- 目标图：`urn:dmo:extract:vadod-diabetes-cpg-quick-reference-guide_final_508`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：3

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **71.0%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 59.7% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 25.0% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.05 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 62 |
| 通过校验 | 44 |
| 丢弃 | 18 |
| 消解后实体 | 42 |
| 关系边 | 30 |
| 悬空关系 | 10 |
| 合并冲突 | 15 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 18 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 18 |
| riskFactor | 7 |
| lifestyleIntervention | 7 |
| labTest | 3 |
| drugClass | 3 |
| diabetesType | 2 |
| medication | 1 |
| contraindication | 1 |

## 合并冲突样例

- diabetesType/type-2-diabetes-mellitus: prevalenceShare: 0 vs 0.9
- diabetesType/type-2-diabetes-mellitus: definition: 'In adults with type 2 diabetes mellitus, we suggest offering health care delivered through telehealth interventions to improve outcomes.' vs 'For adults with type 2 diabetes mellitus, we suggest a vegetarian dietary pattern for glycemic control and weight loss.'
- riskFactor/prediabetes: name: 'Prediabetes' vs 'prediabetes'
- riskFactor/obesity: name: 'Obesity' vs 'obesity'
- riskFactor/physical-inactivity: name: 'Physical Inactivity' vs 'physical inactivity'
- riskFactor/advanced-age: name: 'Advanced Age' vs 'advanced age'
- riskFactor/short-life-expectancy: name: 'Short Life Expectancy' vs 'short life expectancy'
- riskFactor/co-occurring-conditions: name: 'Co-occurring Conditions' vs 'co-occurring conditions'
- riskFactor/high-bmi: name: 'High BMI' vs 'high BMI'
- lifestyleIntervention/aerobic-exercise: name: 'Aerobic Exercise' vs 'Aerobic exercise'
- lifestyleIntervention/healthy-eating: name: 'Healthy Eating' vs 'Healthy eating'
- lifestyleIntervention/mediterranean-style-diet: name: 'Mediterranean Style Diet' vs 'Mediterranean style diet'
- lifestyleIntervention/vegetarian-dietary-pattern: name: 'Vegetarian Dietary Pattern' vs 'Vegetarian dietary pattern'
- lifestyleIntervention/vegetarian-dietary-pattern: name: 'Vegetarian Dietary Pattern' vs 'Vegetarian dietary pattern'
- lifestyleIntervention/vegetarian-dietary-pattern: expectedBenefit: 'glycemic control and weight loss' vs 'Glycemic control and weight loss'

## 悬空关系样例

- `insulin` --hasContraindication--> `History of Severe Hypoglycemia`（未找到）
- `insulin` --causesAdverseEffect--> `Hypoglycemia`（未找到）
- `insulin` --causesAdverseEffect--> `Weight Gain`（未找到）
- `insulin` --causesAdverseEffect--> `Injection Site Reactions`（未找到）
- `sulfonylureas` --hasContraindication--> `History of Severe Hypoglycemia`（未找到）
- `sulfonylureas` --causesAdverseEffect--> `Hypoglycemia`（未找到）
- `sulfonylureas` --causesAdverseEffect--> `Weight Gain`（未找到）
- `meglitinides` --hasContraindication--> `History of Severe Hypoglycemia`（未找到）
- `meglitinides` --causesAdverseEffect--> `Hypoglycemia`（未找到）
- `meglitinides` --causesAdverseEffect--> `Weight Gain`（未找到）
