# 抽取质量报告 — niddk-diabetes-prediabetes-tests

- 源文件：`ontology/knowledges/niddk-diabetes-prediabetes-tests.txt`（sha256 `9a3b9cdc52c8…`）
- 目标图：`urn:dmo:extract:niddk-diabetes-prediabetes-tests`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：2

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **75.0%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 38.7% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 31.2% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.57 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 44 |
| 通过校验 | 33 |
| 丢弃 | 11 |
| 消解后实体 | 21 |
| 关系边 | 11 |
| 悬空关系 | 5 |
| 合并冲突 | 24 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 9 |
| `quote_too_short` | 2 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 8 |
| labTest | 4 |
| symptom | 3 |
| contraindication | 3 |
| diabetesType | 2 |
| monitoringSchedule | 1 |

## 合并冲突样例

- diabetesType/type-2-diabetes: definition: 'Diagnosis of type 2 diabetes is definitively made by blood tests. Diagnosis requires two abnormal test results from the same sample or from two different samples.' vs 'Screening and diagnosis of type 2 diabetes1 6.5% or higher1 repeat for confirmation of diagnosis'
- diabetesType/prediabetes: definition: 'If the patient’s diabetes test results are close to—but not within—the diagnostic range of the test, the patient may have prediabetes.' vs 'Screening and diagnosis of prediabetes1 5.7–6.4%1'
- labTest/a1c-test: name: 'A1C Test' vs 'A1C test'
- labTest/a1c-test: definition: 'Screening and diagnosis of prediabetes; Screening and diagnosis of type 2 diabetes; Monitoring of diabetes' vs 'The A1C test is sometimes called the hemoglobin A1C, HbA1c, glycated hemoglobin, or glycohemoglobin test.'
- symptom/polyuria: name: 'Polyuria' vs 'polyuria'
- symptom/polydypsia: name: 'Polydypsia' vs 'polydypsia'
- symptom/unexplained-weight-loss: name: 'Unexplained Weight Loss' vs 'unexplained weight loss'
- recommendation/a1c-test: statement: 'The A1C test is sometimes called the hemoglobin A1C, HbA1c, glycated hemoglobin, or glycohemoglobin test.' vs 'Screening and diagnosis of prediabetes1'
- recommendation/a1c-test: statement: 'The A1C test is sometimes called the hemoglobin A1C, HbA1c, glycated hemoglobin, or glycohemoglobin test.' vs 'Screening and diagnosis of type 2 diabetes1'
- recommendation/a1c-test: recommendationType: 'Screening' vs 'Diagnosis'
- recommendation/a1c-test: statement: 'The A1C test is sometimes called the hemoglobin A1C, HbA1c, glycated hemoglobin, or glycohemoglobin test.' vs 'repeat for confirmation of diagnosis'
- recommendation/a1c-test: recommendationType: 'Screening' vs 'Diagnosis'
- recommendation/a1c-test: statement: 'The A1C test is sometimes called the hemoglobin A1C, HbA1c, glycated hemoglobin, or glycohemoglobin test.' vs 'Diagnosis requires a laboratory test certified by the NGSP and standardized to the DCCT assay.'
- recommendation/a1c-test: recommendationType: 'Screening' vs 'Diagnosis'
- recommendation/a1c-test: statement: 'The A1C test is sometimes called the hemoglobin A1C, HbA1c, glycated hemoglobin, or glycohemoglobin test.' vs 'Some point-of-care A1C assays may be certified by the NGSP or approved by the U.S. Food and Drug Administration for diagnosis; however, they should only be considered in laboratories that are certified to perform moderate-to-high complexity tests to ensure testing proficiency.'
- recommendation/a1c-test: recommendationType: 'Screening' vs 'Diagnosis'
- recommendation/a1c-test: statement: 'The A1C test is sometimes called the hemoglobin A1C, HbA1c, glycated hemoglobin, or glycohemoglobin test.' vs 'Not recommended for rapidly progressing diabetes, e.g., type 1 diabetes in children1'
- recommendation/a1c-test: recommendationType: 'Screening' vs 'Safety'
- recommendation/a1c-test: statement: 'The A1C test is sometimes called the hemoglobin A1C, HbA1c, glycated hemoglobin, or glycohemoglobin test.' vs 'Not recommended for screening cystic fibrosis NIH external link-related diabetes1'
- recommendation/a1c-test: recommendationType: 'Screening' vs 'Safety'

## 悬空关系样例

- `prediabetes` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `a1c-test` --hasThreshold--> `A1C test - Prediabetes threshold`（未找到）
- `a1c-test` --hasThreshold--> `A1C test - Type 2 diabetes threshold`（未找到）
- `repeating-test-when-results-conflict` --appliesToType--> `Confirming diagnosis of type 2 diabetes and prediabetes`（未找到）
- `random-plasma-glucose-rpg-test` --hasThreshold--> `Random plasma glucose (RPG) test - Diabetes threshold`（未找到）
