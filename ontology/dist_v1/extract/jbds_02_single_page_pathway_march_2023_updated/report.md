# 抽取质量报告 — jbds_02_single_page_pathway_march_2023_updated

- 源文件：`ontology/knowledges/pdfs/JBDS_02_Single_page_pathway_March_2023_updated.pdf`（sha256 `2acc1fa0241f…`）
- 目标图：`urn:dmo:extract:jbds_02_single_page_pathway_march_2023_updated`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：2

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **86.4%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 43.5% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 7.7% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.0 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 44 |
| 通过校验 | 38 |
| 丢弃 | 6 |
| 消解后实体 | 38 |
| 关系边 | 24 |
| 悬空关系 | 2 |
| 合并冲突 | 1 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_too_short` | 6 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 25 |
| labTest | 9 |
| complication | 1 |
| drugClass | 1 |
| medication | 1 |
| contraindication | 1 |

## 合并冲突样例

- medication/human-soluble-insulin: name: 'Human Soluble Insulin' vs 'human soluble insulin'

## 悬空关系样例

- `review-fluid-and-insulin-infusion-if-dka-not-resolved` --appliesToType--> `Diabetic Ketoacidosis`（未找到）
- `convert-to-subcutaneous-insulin-when-biochemically-stable-and-patient-is-ready-to-eat` --definesTarget--> `Diabetic Ketoacidosis`（未找到）
