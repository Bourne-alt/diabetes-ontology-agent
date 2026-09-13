# 抽取质量报告 — nhc-adult-diabetes-dietary-guide-2023

- 源文件：`ontology/knowledges/pdfs/nhc-adult-diabetes-dietary-guide-2023.pdf`（sha256 `2e03cd9e06b1…`）
- 目标图：`urn:dmo:extract:nhc-adult-diabetes-dietary-guide-2023`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：9

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **12.8%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 25.8% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 100.0% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.0 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 156 |
| 通过校验 | 20 |
| 丢弃 | 136 |
| 消解后实体 | 20 |
| 关系边 | 0 |
| 悬空关系 | 1 |
| 合并冲突 | 1 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 110 |
| `quote_too_short` | 26 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| lifestyleIntervention | 11 |
| recommendation | 7 |
| riskFactor | 1 |
| labTest | 1 |

## 合并冲突样例

- riskFactor/sedentary-lifestyle: name: 'Sedentary Lifestyle' vs '久坐'

## 悬空关系样例

- `ogtt-2h` --hasThreshold--> `Diabetes`（未找到）
