# 抽取质量报告 — cdc-prediabetes-prevention

- 源文件：`ontology/knowledges/cdc-prediabetes-prevention.txt`（sha256 `8536e3864367…`）
- 目标图：`urn:dmo:extract:cdc-prediabetes-prevention`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：1

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **79.0%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 21.0% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 40.0% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.0 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 19 |
| 通过校验 | 15 |
| 丢弃 | 4 |
| 消解后实体 | 15 |
| 关系边 | 18 |
| 悬空关系 | 12 |
| 合并冲突 | 6 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_too_short` | 2 |
| `quote_not_found` | 2 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| riskFactor | 6 |
| recommendation | 6 |
| diabetesType | 2 |
| labTest | 1 |

## 合并冲突样例

- riskFactor/family-history-of-type-2-diabetes: name: 'Family History of Type 2 Diabetes' vs '一级亲属糖尿病史'
- riskFactor/physical-inactivity-less-than-3-times-a-week: name: 'Physical Inactivity Less Than 3 Times a Week' vs '每周体力活动少于3次'
- riskFactor/gestational-diabetes: name: 'Gestational Diabetes' vs '妊娠期糖尿病史'
- riskFactor/history-of-giving-birth-to-a-baby-weighing-more-than-9-pounds: name: 'History of Giving Birth to a Baby Weighing More Than 9 Pounds' vs '曾生育体重超过9磅的婴儿'
- riskFactor/polycystic-ovary-syndrome: name: 'Polycystic Ovary Syndrome' vs '多囊卵巢综合征'
- riskFactor/race-and-ethnicity: name: 'Race and Ethnicity' vs '种族和民族'

## 悬空关系样例

- `prediabetes` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `type-2-diabetes` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `lifestyle-changes-to-prevent-type-2-diabetes-in-prediabetes` --recommendsLifestyle--> `Weight loss and physical activity`（未找到）
- `lifestyle-changes-to-prevent-type-2-diabetes-in-prediabetes` --definesTarget--> `5% to 7% body weight loss`（未找到）
- `lifestyle-changes-to-prevent-type-2-diabetes-in-prediabetes` --definesSchedule--> `150 minutes per week of brisk walking`（未找到）
- `lifestyle-changes-to-prevent-type-2-diabetes-in-prediabetes` --citesSource--> `CDC-led National Diabetes Prevention Program`（未找到）
- `weight-loss-for-prediabetes` --definesTarget--> `5% to 7% body weight loss`（未找到）
- `physical-activity-for-prediabetes` --definesSchedule--> `150 minutes per week of brisk walking`（未找到）
- `cdc-led-national-diabetes-prevention-program` --recommendsLifestyle--> `Weight loss and physical activity`（未找到）
- `cdc-led-national-diabetes-prevention-program` --citesSource--> `CDC-led National Diabetes Prevention Program`（未找到）
- `5-to-7-body-weight-loss` --definesTarget--> `5% to 7% body weight loss`（未找到）
- `150-minutes-per-week-of-brisk-walking` --definesSchedule--> `150 minutes per week of brisk walking`（未找到）
