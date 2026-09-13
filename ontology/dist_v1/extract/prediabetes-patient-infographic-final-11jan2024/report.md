# 抽取质量报告 — prediabetes-patient-infographic-final-11jan2024

- 源文件：`ontology/knowledges/pdfs/Prediabetes-Patient-Infographic-final-11Jan2024.pdf`（sha256 `8756639a2b77…`）
- 目标图：`urn:dmo:extract:prediabetes-patient-infographic-final-11jan2024`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：1

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **92.9%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 33.9% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 3.9% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.0 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 70 |
| 通过校验 | 65 |
| 丢弃 | 5 |
| 消解后实体 | 65 |
| 关系边 | 49 |
| 悬空关系 | 2 |
| 合并冲突 | 6 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_too_short` | 5 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| lifestyleIntervention | 27 |
| recommendation | 27 |
| riskFactor | 6 |
| diabetesType | 2 |
| labTest | 2 |
| monitoringSchedule | 1 |

## 合并冲突样例

- riskFactor/family-history-of-diabetes: name: 'Family History of Diabetes' vs 'A family history (parent, brother, or sister) with diabetes.'
- riskFactor/ethnicity: name: 'Ethnicity' vs 'African American, American Indian, Asian American, Pacific Islander, or Hispanic American/Latino heritage.'
- riskFactor/prior-history-of-diabetes-during-pregnancy: name: 'Prior History of Diabetes During Pregnancy' vs 'Prior history of diabetes during pregnancy.'
- riskFactor/birth-of-at-least-one-baby-weighing-more-than-9-pounds: name: 'Birth of at Least One Baby Weighing More Than 9 Pounds' vs 'Birth of at least one baby weighing more than 9 pounds.'
- riskFactor/physical-inactivity: name: 'Physical Inactivity' vs 'Physical inactivity—exercising less than 3 times a week.'
- riskFactor/high-blood-pressure: name: 'High Blood Pressure' vs 'High blood pressure measuring 140/90 or higher.'

## 悬空关系样例

- `prediabetes` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `type-2-diabetes` --predisposesTo--> `Type 2 Diabetes`（未找到）
