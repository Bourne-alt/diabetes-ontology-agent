# 抽取质量报告 — vadod-diabetes-cpg-provider-summary_final_508

- 源文件：`ontology/knowledges/pdfs/VADOD-Diabetes-CPG-Provider-Summary_final_508.pdf`（sha256 `43a6448d712f…`）
- 目标图：`urn:dmo:extract:vadod-diabetes-cpg-provider-summary_final_508`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：15

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **69.3%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 93.5% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 50.4% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.13 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 446 |
| 通过校验 | 309 |
| 丢弃 | 137 |
| 消解后实体 | 274 |
| 关系边 | 68 |
| 悬空关系 | 69 |
| 合并冲突 | 114 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 74 |
| `quote_too_short` | 60 |
| `unknown_relation_predicate` | 3 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 67 |
| riskFactor | 61 |
| complication | 34 |
| symptom | 20 |
| contraindication | 19 |
| adverseEffect | 18 |
| drugClass | 15 |
| labTest | 10 |
| medication | 9 |
| diabetesType | 6 |
| lifestyleIntervention | 6 |
| monitoringSchedule | 4 |
| complicationStage | 3 |
| device | 2 |

## 合并冲突样例

- diabetesType/type-2-diabetes-mellitus: mondoCode: 'MONDO:0001513' vs 'MONDO:0005147'
- diabetesType/type-2-diabetes-mellitus: definition: 'In contrast, Type 2 DM (T2DM) is due to progressive insulin deficiency on a background of insulin resistance.' vs 'Type 2 Diabetes Mellitus – Provider Summary'
- diabetesType/type-2-diabetes-mellitus: mondoCode: 'MONDO:0001513' vs 'MONDO:0005147'
- diabetesType/type-2-diabetes-mellitus: definition: 'In contrast, Type 2 DM (T2DM) is due to progressive insulin deficiency on a background of insulin resistance.' vs 'Type 2 diabetes mellitus (T2DM) is a chronic metabolic disorder characterized by insulin resistance and relative insulin deficiency, leading to hyperglycemia.'
- diabetesType/type-2-diabetes-mellitus: mondoCode: 'MONDO:0001513' vs 'MONDO:0005147'
- diabetesType/type-2-diabetes-mellitus: definition: 'In contrast, Type 2 DM (T2DM) is due to progressive insulin deficiency on a background of insulin resistance.' vs 'Type 2 diabetes mellitus'
- diabetesType/type-2-diabetes-mellitus: mondoCode: 'MONDO:0001513' vs 'MONDO:0005147'
- diabetesType/type-2-diabetes-mellitus: definition: 'In contrast, Type 2 DM (T2DM) is due to progressive insulin deficiency on a background of insulin resistance.' vs 'Type 2 Diabetes Mellitus'
- diabetesType/type-2-diabetes-mellitus: mondoCode: 'MONDO:0001513' vs 'MONDO:0005147'
- diabetesType/type-2-diabetes-mellitus: definition: 'In contrast, Type 2 DM (T2DM) is due to progressive insulin deficiency on a background of insulin resistance.' vs 'The VA/DoD Clinical Practice Guideline for the Management of Type 2 Diabetes Mellitus – Provider Summary'
- riskFactor/first-degree-relative-with-dm: name: 'First-Degree Relative with DM' vs 'First-degree relative with DM'
- riskFactor/hypertension: evidenceNote: 'The guideline recommends considering screening for diabetes or prediabetes in adults who are overweight or obese (body mass index [BMI] ≥ 25 kg/m2 or ≥ 23 kg/m2 in Asian Americans) and have additional risk factors, including: · Hypertension (blood pressure ≥ 140/90 mmHg or on therapy for hypertension)(2)' vs 'Hypertension (blood pressure ≥ 140/90 mmHg or on therapy for hypertension)'
- riskFactor/hypertension: name: 'Hypertension' vs 'hypertension'
- riskFactor/hypertension: evidenceNote: 'The guideline recommends considering screening for diabetes or prediabetes in adults who are overweight or obese (body mass index [BMI] ≥ 25 kg/m2 or ≥ 23 kg/m2 in Asian Americans) and have additional risk factors, including: · Hypertension (blood pressure ≥ 140/90 mmHg or on therapy for hypertension)(2)' vs 'Document recommends ACEi/ARB use in patients with HTN and moderately increased albuminuria, indicating hypertension is a modifiable risk factor.'
- riskFactor/history-of-cardiovascular-disease: name: 'History of Cardiovascular Disease' vs 'History of cardiovascular disease (CVD)'
- riskFactor/history-of-cardiovascular-disease: name: 'History of Cardiovascular Disease' vs 'History of cardiovascular disease'
- riskFactor/history-of-cardiovascular-disease: evidenceNote: 'The guideline recommends considering screening for diabetes or prediabetes in adults who are overweight or obese (body mass index [BMI] ≥ 25 kg/m2 or ≥ 23 kg/m2 in Asian Americans) and have additional risk factors, including: · History of cardiovascular disease (CVD)(2)' vs 'History of cardiovascular disease (CVD)'
- riskFactor/polycystic-ovary-syndrome: name: 'Polycystic Ovary Syndrome' vs 'Polycystic ovary syndrome (PCOS)'
- riskFactor/polycystic-ovary-syndrome: name: 'Polycystic Ovary Syndrome' vs 'Polycystic ovary syndrome'
- riskFactor/polycystic-ovary-syndrome: evidenceNote: 'The guideline recommends considering screening for diabetes or prediabetes in adults who are overweight or obese (body mass index [BMI] ≥ 25 kg/m2 or ≥ 23 kg/m2 in Asian Americans) and have additional risk factors, including: · Women with polycystic ovary syndrome (PCOS)(2)' vs 'Women with polycystic ovary syndrome (PCOS)'

## 悬空关系样例

- `hypertension` --increasesRiskOf--> `Diabetic Nephropathy`（未找到）
- `type-2-diabetes` --predisposesTo--> `Non-alcoholic Fatty Liver Disease`（未找到）
- `type-2-diabetes` --predisposesTo--> `Obstructive Sleep Apnea`（未找到）
- `type-2-diabetes` --predisposesTo--> `Hypertension`（未找到）
- `type-2-diabetes` --predisposesTo--> `Hyperlipidemia`（未找到）
- `type-2-diabetes` --predisposesTo--> `Obesity`（未找到）
- `type-2-diabetes` --predisposesTo--> `Mortality from COVID-19 Infection`（未找到）
- `retinopathy` --hasStage--> `Diabetic Retinopathy`（未找到）
- `nephropathy` --hasStage--> `Diabetic Kidney Disease`（未找到）
- `neuropathy` --hasStage--> `Diabetic Peripheral Neuropathy`（未找到）
- `atherosclerotic-cvd` --presentsWith--> `Ischemic Heart Disease`（未找到）
- `atherosclerotic-cvd` --presentsWith--> `Stroke`（未找到）
- `atherosclerotic-cvd` --presentsWith--> `Peripheral Vascular Disease`（未找到）
- `poor-glycemic-control` --increasesRiskOf--> `Mortality from COVID-19 Infection`（未找到）
- `management-of-comorbidities-in-type-2-diabetes-mellitus` --citesSource--> `VA/DoD Clinical Practice Guideline for the Management of Chronic Obstructive Pulmonary Disease (COPD)`（未找到）
- `management-of-comorbidities-in-type-2-diabetes-mellitus` --citesSource--> `VA/DoD Clinical Practice Guideline for the Management of Substance Use Disorders (SUD)`（未找到）
- `management-of-comorbidities-in-type-2-diabetes-mellitus` --citesSource--> `VA/DoD Clinical Practice Guideline for the Management of Adult Overweight and Obesity (OBE)`（未找到）
- `management-of-comorbidities-in-type-2-diabetes-mellitus` --citesSource--> `VA/DoD Clinical Practice Guideline for the Management of Major Depressive Disorder (MDD)`（未找到）
- `shared-decision-making` --definesTarget--> `Shared decision making`（未找到）
- `shared-decision-making` --citesSource--> `VA/DoD Clinical Practice Guideline for the Management of Type 2 Diabetes Mellitus – Provider Summary`（未找到）
