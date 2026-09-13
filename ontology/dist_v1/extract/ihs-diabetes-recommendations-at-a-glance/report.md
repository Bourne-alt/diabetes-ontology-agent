# 抽取质量报告 — ihs-diabetes-recommendations-at-a-glance

- 源文件：`ontology/knowledges/pdfs/ihs-diabetes-recommendations-at-a-glance.pdf`（sha256 `300c57433bf2…`）
- 目标图：`urn:dmo:extract:ihs-diabetes-recommendations-at-a-glance`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：1

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **81.8%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 54.8% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 13.9% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.0 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 66 |
| 通过校验 | 54 |
| 丢弃 | 12 |
| 消解后实体 | 54 |
| 关系边 | 31 |
| 悬空关系 | 5 |
| 合并冲突 | 8 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_too_short` | 6 |
| `quote_not_found` | 6 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 27 |
| symptom | 6 |
| riskFactor | 6 |
| labTest | 4 |
| lifestyleIntervention | 3 |
| diabetesType | 2 |
| medication | 2 |
| contraindication | 2 |
| device | 2 |

## 合并冲突样例

- symptom/resting-tachycardia: name: 'Resting Tachycardia' vs 'resting tachycardia'
- symptom/exercise-intolerance: name: 'Exercise Intolerance' vs 'exercise intolerance'
- symptom/orthostatic-hypotension: name: 'Orthostatic Hypotension' vs 'orthostatic hypotension'
- symptom/gastroparesis: name: 'Gastroparesis' vs 'gastroparesis'
- symptom/constipation: name: 'Constipation' vs 'constipation'
- symptom/diarrhea: name: 'Diarrhea' vs 'diarrhea'
- medication/aspirin-therapy-75-162-mg-day: name: 'Aspirin therapy 75-162 mg/day' vs 'aspirin'
- medication/ace-inhibitor-or-arb: name: 'ACE Inhibitor or ARB' vs 'ACE inhibitor'

## 悬空关系样例

- `aspirin-therapy-75-162-mg-day` --increasesRiskOf--> `ASCVD`（未找到）
- `tobacco-use` --increasesRiskOf--> `ASCVD`（未找到）
- `hypertension` --increasesRiskOf--> `CKD`（未找到）
- `chronic-kidney-disease` --increasesRiskOf--> `ASCVD`（未找到）
- `age-50-70-with-1-or-more-risk-factors-for-ascvd` --increasesRiskOf--> `ASCVD`（未找到）
