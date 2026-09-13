# 抽取质量报告 — nhc-diabetes-day-2025

- 源文件：`ontology/knowledges/nhc-diabetes-day-2025.txt`（sha256 `aa943eba2bc3…`）
- 目标图：`urn:dmo:extract:nhc-diabetes-day-2025`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：1

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **91.2%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 51.6% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 62.0% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.0 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 80 |
| 通过校验 | 73 |
| 丢弃 | 7 |
| 消解后实体 | 73 |
| 关系边 | 27 |
| 悬空关系 | 44 |
| 合并冲突 | 7 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_too_short` | 6 |
| `quote_not_found` | 1 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 33 |
| lifestyleIntervention | 15 |
| complication | 7 |
| symptom | 7 |
| riskFactor | 7 |
| labTest | 2 |
| diabetesType | 1 |
| monitoringSchedule | 1 |

## 合并冲突样例

- complication/diabetic-ketoacidosis: name: 'Diabetic Ketoacidosis' vs '糖尿病酮症酸中毒'
- complication/hyperosmolar-hyperglycemic-state: name: 'Hyperosmolar Hyperglycemic State' vs '高渗性高血糖状态'
- complication/diabetic-retinopathy: name: 'Diabetic Retinopathy' vs '糖尿病视网膜病变'
- complication/diabetic-nephropathy: name: 'Diabetic Nephropathy' vs '糖尿病肾脏病'
- complication/diabetic-neuropathy: name: 'Diabetic Neuropathy' vs '糖尿病神经病变'
- complication/diabetic-foot-ulcer: name: 'Diabetic Foot Ulcer' vs '糖尿病足溃疡'
- complication/cardiovascular-disease: name: 'Cardiovascular Disease' vs '动脉粥样硬化性心血管疾病'

## 悬空关系样例

- `餐后2小时血糖` --hasThreshold--> `餐后2小时血糖`（未找到）
- `超重与肥胖` --increasesRiskOf--> `Diabetes`（未找到）
- `吸烟` --increasesRiskOf--> `Chronic Obstructive Pulmonary Disease`（未找到）
- `室内外空气污染` --increasesRiskOf--> `Chronic Obstructive Pulmonary Disease`（未找到）
- `职业暴露` --increasesRiskOf--> `Chronic Obstructive Pulmonary Disease`（未找到）
- `遗传因素` --increasesRiskOf--> `Chronic Obstructive Pulmonary Disease`（未找到）
- `幼年时期的呼吸道感染` --increasesRiskOf--> `Chronic Obstructive Pulmonary Disease`（未找到）
- `有巨大儿-出生体重-4kg-分娩史或妊娠糖尿病史` --increasesRiskOf--> `Diabetes`（未找到）
- `每年进行慢性并发症筛查` --schedulesTest--> `Urine Albumin-to-Creatinine Ratio`（未找到）
- `每年进行慢性并发症筛查` --schedulesTest--> `eGFR`（未找到）
- `每年进行慢性并发症筛查` --schedulesTest--> `Dilated Eye Examination`（未找到）
- `每年检测1次空腹血糖` --appliesToType--> `Diabetes`（未找到）
- `每半年检测1次空腹血糖或餐后2小时血糖` --appliesToType--> `Diabetes`（未找到）
- `每年检查1次肺功能` --appliesToType--> `Chronic Obstructive Pulmonary Disease`（未找到）
- `戒烟` --appliesToType--> `Chronic Obstructive Pulmonary Disease`（未找到）
- `避免二手烟暴露` --appliesToType--> `Chronic Obstructive Pulmonary Disease`（未找到）
- `减少室内外空气污染` --appliesToType--> `Chronic Obstructive Pulmonary Disease`（未找到）
- `改善厨房通风条件` --appliesToType--> `Chronic Obstructive Pulmonary Disease`（未找到）
- `在职业环境中做好防护-减少职业暴露` --appliesToType--> `Chronic Obstructive Pulmonary Disease`（未找到）
- `及时接种流感疫苗和肺炎球菌疫苗` --appliesToType--> `Chronic Obstructive Pulmonary Disease`（未找到）
