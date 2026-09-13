# 抽取质量报告 — niddk-uacr-egfr

- 源文件：`ontology/knowledges/niddk-uacr-egfr.txt`（sha256 `196ec62270a6…`）
- 目标图：`urn:dmo:extract:niddk-uacr-egfr`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：1

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **82.3%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 41.9% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 15.8% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.0 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 17 |
| 通过校验 | 14 |
| 丢弃 | 3 |
| 消解后实体 | 14 |
| 关系边 | 16 |
| 悬空关系 | 3 |
| 合并冲突 | 0 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `unknown_relation_predicate` | 2 |
| `quote_not_found` | 1 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 4 |
| complication | 3 |
| diabetesType | 2 |
| labTest | 2 |
| monitoringSchedule | 2 |
| complicationStage | 1 |

## 悬空关系样例

- `urine-albumin-to-creatinine-ratio` --hasThreshold--> `Albuminuria`（未找到）
- `chronic-kidney-disease` --presentsWith--> `Urine Albumin-to-Creatinine Ratio`（未找到）
- `chronic-kidney-disease` --presentsWith--> `Estimated Glomerular Filtration Rate`（未找到）
