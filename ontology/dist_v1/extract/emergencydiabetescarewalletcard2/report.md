# 抽取质量报告 — emergencydiabetescarewalletcard2

- 源文件：`ontology/knowledges/pdfs/EmergencyDiabetesCareWalletCard2.pdf`（sha256 `1ad39dfd324e…`）
- 目标图：`urn:dmo:extract:emergencydiabetescarewalletcard2`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：1

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **50.0%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 35.5% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 0.0% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.0 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 42 |
| 通过校验 | 21 |
| 丢弃 | 21 |
| 消解后实体 | 21 |
| 关系边 | 13 |
| 悬空关系 | 0 |
| 合并冲突 | 3 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_too_short` | 19 |
| `quote_not_found` | 2 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| labTest | 6 |
| recommendation | 6 |
| monitoringSchedule | 4 |
| symptom | 3 |
| complication | 1 |
| lifestyleIntervention | 1 |

## 合并冲突样例

- symptom/acting-strangely: name: 'Acting Strangely' vs 'acting strangely'
- symptom/cannot-be-awakened: name: 'Cannot Be Awakened' vs 'cannot be awakened'
- symptom/cannot-swallow: name: 'Cannot Swallow' vs 'cannot swallow'
