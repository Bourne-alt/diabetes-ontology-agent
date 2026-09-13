# 抽取质量报告 — fda-diabetes-drug-classes

- 源文件：`ontology/knowledges/fda-diabetes-drug-classes.txt`（sha256 `38f4accfbefe…`）
- 目标图：`urn:dmo:extract:fda-diabetes-drug-classes`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：3

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **51.3%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 56.5% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 10.9% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.07 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 154 |
| 通过校验 | 79 |
| 丢弃 | 75 |
| 消解后实体 | 74 |
| 关系边 | 49 |
| 悬空关系 | 6 |
| 合并冲突 | 15 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_too_short` | 45 |
| `quote_not_found` | 30 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 20 |
| symptom | 10 |
| drugClass | 10 |
| adverseEffect | 9 |
| riskFactor | 8 |
| contraindication | 7 |
| medication | 7 |
| diabetesType | 2 |
| complication | 1 |

## 合并冲突样例

- symptom/hypoglycemia: name: 'Hypoglycemia' vs 'Hypoglycemia (blood sugar that is too low)'
- symptom/hypoglycemia: name: 'Hypoglycemia' vs 'hypoglycemia'
- riskFactor/liver-problems: name: 'Liver Problems' vs 'Liver problems'
- riskFactor/kidney-problems: name: 'Kidney Problems' vs 'Kidney problems'
- riskFactor/heart-failure: name: 'Heart Failure' vs 'Heart failure'
- riskFactor/heart-failure: evidenceNote: '文档中提到Thiazolidinediones类药物可能引起心力衰竭，且使用前需告知医生是否有心衰。' vs "Document states 'Heart Failure (heart cannot pump blood well)' as a condition associated with certain medications, implying it is a pre-existing condition that may affect drug use."
- adverseEffect/hypoglycemia: name: 'Hypoglycemia' vs 'Hypoglycemia (blood sugar that is too low)'
- symptom/severe-stomach-pain: name: 'Severe Stomach Pain' vs 'severe stomach pain'
- symptom/nausea: name: 'Nausea' vs 'nausea'
- symptom/vomiting: name: 'Vomiting' vs 'vomiting'
- symptom/dyspepsia: name: 'Dyspepsia' vs 'dyspepsia'
- symptom/vaginal-yeast-infections: name: 'Vaginal Yeast Infections' vs 'vaginal yeast infections'
- symptom/urinary-tract-infections: name: 'Urinary Tract Infections' vs 'urinary tract infections'
- adverseEffect/nausea: name: 'Nausea' vs 'nauseous'
- adverseEffect/nausea: severity: 'Unknown' vs 'Mild'

## 悬空关系样例

- `meglitinides` --hasContraindication--> `Liver or kidney problems`（未找到）
- `alpha-glucosidase-inhibitors` --hasContraindication--> `Heart problems`（未找到）
- `alpha-glucosidase-inhibitors` --causesAdverseEffect--> `Gas`（未找到）
- `alpha-glucosidase-inhibitors` --causesAdverseEffect--> `Abnormal Liver Tests`（未找到）
- `pioglitazone` --belongsToDrugClass--> `Thiazolidinediones`（未找到）
- `rosiglitazone` --belongsToDrugClass--> `Thiazolidinediones`（未找到）
