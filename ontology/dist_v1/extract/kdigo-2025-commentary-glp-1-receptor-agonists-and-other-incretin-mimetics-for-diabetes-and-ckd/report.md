# 抽取质量报告 — kdigo-2025-commentary-glp-1-receptor-agonists-and-other-incretin-mimetics-for-diabetes-and-ckd

- 源文件：`ontology/knowledges/pdfs/KDIGO-2025-Commentary-GLP-1-Receptor-Agonists-and-Other-Incretin-Mimetics-for-Diabetes-and-CKD.pdf`（sha256 `f8f4e19fcb80…`）
- 目标图：`urn:dmo:extract:kdigo-2025-commentary-glp-1-receptor-agonists-and-other-incretin-mimetics-for-diabetes-and-ckd`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：4

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **23.7%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 41.9% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 50.0% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.08 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 59 |
| 通过校验 | 14 |
| 丢弃 | 45 |
| 消解后实体 | 13 |
| 关系边 | 2 |
| 悬空关系 | 2 |
| 合并冲突 | 4 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 41 |
| `quote_too_short` | 3 |
| `unknown_relation_predicate` | 1 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| medication | 5 |
| complication | 3 |
| labTest | 2 |
| diabetesType | 2 |
| riskFactor | 1 |

## 合并冲突样例

- riskFactor/albuminuria: name: 'Albuminuria' vs 'albuminuria'
- medication/semaglutide-1-mg-once-weekly: name: 'Semaglutide 1 mg once weekly' vs 'semaglutide'
- medication/semaglutide-2-4-mg-once-weekly: name: 'Semaglutide 2.4 mg once weekly' vs 'semaglutide'
- medication/tirzepatide-5-mg-10-mg-or-15-mg-once-weekly: name: 'Tirzepatide (5 mg, 10 mg, or 15 mg once weekly)' vs 'tirzepatide'

## 悬空关系样例

- `albuminuria` --increasesRiskOf--> `Chronic Kidney Disease Progression`（未找到）
- `albuminuria` --increasesRiskOf--> `Cardiovascular Events`（未找到）
