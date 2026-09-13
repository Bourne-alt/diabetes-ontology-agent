# 抽取质量报告 — niddk-insulin-medicines-treatments

- 源文件：`ontology/knowledges/niddk-insulin-medicines-treatments.txt`（sha256 `9bc64702ec75…`）
- 目标图：`urn:dmo:extract:niddk-insulin-medicines-treatments`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：4

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **91.9%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 64.5% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 29.3% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.1 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 74 |
| 通过校验 | 68 |
| 丢弃 | 6 |
| 消解后实体 | 62 |
| 关系边 | 29 |
| 悬空关系 | 12 |
| 合并冲突 | 27 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 6 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 23 |
| drugClass | 9 |
| medication | 9 |
| lifestyleIntervention | 7 |
| device | 4 |
| diabetesType | 3 |
| symptom | 3 |
| adverseEffect | 3 |
| complication | 1 |

## 合并冲突样例

- diabetesType/type-1-diabetes: name: 'Type 1 diabetes' vs 'Type 1 Diabetes'
- diabetesType/type-1-diabetes: definition: 'If you have type 1 diabetes, you must take insulin because your pancreas does not make it.' vs 'An artificial pancreas is mainly used to help people with type 1 diabetes.'
- diabetesType/type-1-diabetes: prevalenceShare: 0.05 vs 0.1
- diabetesType/type-1-diabetes: definition: 'If you have type 1 diabetes, you must take insulin because your pancreas does not make it.' vs 'If you have type 1 diabetes, your doctor may recommend you take other medicines, in addition to insulin, to help control your blood glucose.'
- diabetesType/type-2-diabetes: name: 'Type 2 diabetes' vs 'Type 2 Diabetes'
- diabetesType/type-2-diabetes: definition: 'Some people with type 2 diabetes can control their blood glucose level by making lifestyle changes.' vs 'Inhaled insulin is only for adults with type 1 or type 2 diabetes.'
- diabetesType/type-2-diabetes: definition: 'Some people with type 2 diabetes can control their blood glucose level by making lifestyle changes.' vs 'Besides insulin, other types of injected medicines External link (PDF, 2.8 MB) are available that will keep your blood glucose level from rising too high after you eat or drink.'
- drugClass/insulin: mechanism: 'Helps the body use glucose from the blood for energy and stores excess glucose in the liver and muscles.' vs 'Insulin is a hormone that helps regulate blood glucose levels by allowing cells to take in glucose from the bloodstream.'
- medication/rapid-acting-inhaled-insulin: name: 'Rapid-Acting Inhaled Insulin' vs 'rapid-acting, inhaled'
- medication/regular-insulin: name: 'Regular Insulin' vs 'regular'
- medication/intermediate-acting-insulin: name: 'Intermediate-Acting Insulin' vs 'intermediate-acting'
- medication/long-acting-insulin: name: 'Long-Acting Insulin' vs 'long-acting'
- medication/ultra-long-acting-insulin: name: 'Ultra Long-Acting Insulin' vs 'ultra long-acting'
- medication/premixed-insulin: name: 'Premixed Insulin' vs 'premixed insulin'
- device/artificial-pancreas: name: 'Artificial Pancreas' vs 'artificial pancreas'
- medication/insulin: name: 'Insulin' vs 'insulin'
- medication/metformin: name: 'Metformin' vs 'metformin'
- device/continuous-glucose-monitor: name: 'Continuous Glucose Monitor' vs 'continuous glucose monitor (CGM)'
- device/insulin-infusion-pump: name: 'Insulin Infusion Pump' vs 'insulin infusion pump'
- symptom/hypoglycemia: name: 'Hypoglycemia' vs 'hypoglycemia'

## 悬空关系样例

- `rapid-acting-inhaled-insulin` --hasContraindication--> `Insulin`（未找到）
- `regular-also-called-short-acting-insulin` --hasContraindication--> `Insulin`（未找到）
- `intermediate-acting-insulin` --hasContraindication--> `Insulin`（未找到）
- `long-acting-insulin` --hasContraindication--> `Insulin`（未找到）
- `ultra-long-acting-insulin` --hasContraindication--> `Insulin`（未找到）
- `premixed-insulin` --hasContraindication--> `Insulin`（未找到）
- `artificial-pancreas` --deviceMeasuresTest--> `Blood Glucose Level`（未找到）
- `continuous-glucose-monitor` --deviceMeasuresTest--> `Blood Glucose Level`（未找到）
- `insulin-infusion-pump` --deviceMeasuresTest--> `Blood Glucose Level`（未找到）
- `glucagon-like-peptide-1-receptor-agonists` --hasContraindication--> `Insulin`（未找到）
- `weight-loss-surgery` --definesTarget--> `Weight-loss surgery`（未找到）
- `pancreatic-islet-transplantation` --definesTarget--> `Pancreatic islet transplantation`（未找到）
