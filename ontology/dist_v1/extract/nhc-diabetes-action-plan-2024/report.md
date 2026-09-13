# 抽取质量报告 — nhc-diabetes-action-plan-2024

- 源文件：`ontology/knowledges/nhc-diabetes-action-plan-2024.txt`（sha256 `0be4e2c4ac6e…`）
- 目标图：`urn:dmo:extract:nhc-diabetes-action-plan-2024`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：2

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **97.2%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 45.2% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 12.3% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.0 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 72 |
| 通过校验 | 70 |
| 丢弃 | 2 |
| 消解后实体 | 70 |
| 关系边 | 64 |
| 悬空关系 | 9 |
| 合并冲突 | 13 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_too_short` | 2 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| lifestyleIntervention | 23 |
| recommendation | 23 |
| riskFactor | 9 |
| monitoringSchedule | 7 |
| labTest | 3 |
| complication | 3 |
| diabetesType | 2 |

## 合并冲突样例

- diabetesType/diabetes前期: name: 'Diabetes前期' vs '糖尿病前期'
- complication/diabetic-kidney-disease: name: 'Diabetic Kidney Disease' vs '糖尿病肾脏病'
- complication/diabetic-retinopathy: name: 'Diabetic Retinopathy' vs '糖尿病视网膜病变'
- complication/diabetic-foot-disease: name: 'Diabetic Foot Disease' vs '糖尿病足病'
- riskFactor/obesity: name: 'Obesity' vs '肥胖'
- riskFactor/overweight: name: 'Overweight' vs '超重'
- riskFactor/physical-inactivity: name: 'Physical Inactivity' vs '久坐'
- riskFactor/unhealthy-diet: name: 'Unhealthy Diet' vs '不合理膳食'
- riskFactor/smoking: name: 'Smoking' vs '吸烟'
- riskFactor/excessive-alcohol-consumption: name: 'Excessive Alcohol Consumption' vs '饮酒过量'
- riskFactor/family-history-of-diabetes: name: 'Family History of Diabetes' vs '一级亲属糖尿病史'
- riskFactor/gestational-diabetes-mellitus: name: 'Gestational Diabetes Mellitus' vs '妊娠期糖尿病史'
- riskFactor/polycystic-ovary-syndrome: name: 'Polycystic Ovary Syndrome' vs '多囊卵巢综合征'

## 悬空关系样例

- `obesity` --increasesRiskOf--> `Type 2 Diabetes`（未找到）
- `overweight` --increasesRiskOf--> `Type 2 Diabetes`（未找到）
- `physical-inactivity` --increasesRiskOf--> `Type 2 Diabetes`（未找到）
- `unhealthy-diet` --increasesRiskOf--> `Type 2 Diabetes`（未找到）
- `smoking` --increasesRiskOf--> `Type 2 Diabetes`（未找到）
- `excessive-alcohol-consumption` --increasesRiskOf--> `Type 2 Diabetes`（未找到）
- `family-history-of-diabetes` --increasesRiskOf--> `Type 2 Diabetes`（未找到）
- `gestational-diabetes-mellitus` --increasesRiskOf--> `Type 2 Diabetes`（未找到）
- `polycystic-ovary-syndrome` --increasesRiskOf--> `Type 2 Diabetes`（未找到）
