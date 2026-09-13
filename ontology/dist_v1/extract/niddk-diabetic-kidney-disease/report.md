# 抽取质量报告 — niddk-diabetic-kidney-disease

- 源文件：`ontology/knowledges/niddk-diabetic-kidney-disease.txt`（sha256 `4ae81fcb0528…`）
- 目标图：`urn:dmo:extract:niddk-diabetic-kidney-disease`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：2

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **64.1%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 51.6% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 14.9% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.03 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 53 |
| 通过校验 | 34 |
| 丢弃 | 19 |
| 消解后实体 | 33 |
| 关系边 | 63 |
| 悬空关系 | 11 |
| 合并冲突 | 10 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 16 |
| `quote_too_short` | 3 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 10 |
| riskFactor | 9 |
| lifestyleIntervention | 8 |
| labTest | 2 |
| diabetesType | 1 |
| complication | 1 |
| contraindication | 1 |
| monitoringSchedule | 1 |

## 合并冲突样例

- riskFactor/having-diabetes-for-a-longer-time: name: 'Having Diabetes for a Longer Time' vs 'Having diabetes for a longer time'
- riskFactor/high-blood-glucose: name: 'High Blood Glucose' vs 'high blood glucose'
- riskFactor/high-blood-pressure: name: 'High Blood Pressure' vs 'high blood pressure'
- riskFactor/race-and-ethnicity-african-americans-american-indians-and-hispanics-latinos: name: 'Race and Ethnicity: African Americans, American Indians, and Hispanics/Latinos' vs 'African Americans, American Indians, and Hispanics/Latinos'
- contraindication/ace-inhibitors-and-arbs: rationale: 'ACE inhibitors and ARBs are not safe for women who are pregnant.' vs 'ACE inhibitors and ARBs are not safe for women who are pregnant'
- riskFactor/high-salt-and-sodium-intake: name: 'High Salt and Sodium Intake' vs 'high salt and sodium intake'
- riskFactor/physical-inactivity: name: 'Physical Inactivity' vs 'physical inactivity'
- riskFactor/obesity-or-overweight: name: 'Obesity or Overweight' vs 'obesity or overweight'
- riskFactor/poor-sleep: name: 'Poor Sleep' vs 'poor sleep'
- riskFactor/chronic-stress: name: 'Chronic Stress' vs 'chronic stress'

## 悬空关系样例

- `a1c` --hasThreshold--> `A1C Goal`（未找到）
- `urine-albumin-to-creatinine-ratio` --hasThreshold--> `UACR Threshold`（未找到）
- `having-diabetes-for-a-longer-time` --increasesRiskOf--> `Diabetic Kidney Disease`（未找到）
- `high-blood-glucose` --increasesRiskOf--> `Diabetic Kidney Disease`（未找到）
- `high-blood-pressure` --increasesRiskOf--> `Diabetic Kidney Disease`（未找到）
- `race-and-ethnicity-african-americans-american-indians-and-hispanics-latinos` --increasesRiskOf--> `Diabetic Kidney Disease`（未找到）
- `high-salt-and-sodium-intake` --increasesRiskOf--> `Diabetic Kidney Disease`（未找到）
- `physical-inactivity` --increasesRiskOf--> `Diabetic Kidney Disease`（未找到）
- `obesity-or-overweight` --increasesRiskOf--> `Diabetic Kidney Disease`（未找到）
- `poor-sleep` --increasesRiskOf--> `Diabetic Kidney Disease`（未找到）
- `chronic-stress` --increasesRiskOf--> `Diabetic Kidney Disease`（未找到）
