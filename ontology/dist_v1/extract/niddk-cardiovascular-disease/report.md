# 抽取质量报告 — niddk-cardiovascular-disease

- 源文件：`ontology/knowledges/niddk-cardiovascular-disease.txt`（sha256 `ec34f8889d2d…`）
- 目标图：`urn:dmo:extract:niddk-cardiovascular-disease`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：4

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **82.9%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 61.3% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 75.8% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.01 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 111 |
| 通过校验 | 92 |
| 丢弃 | 19 |
| 消解后实体 | 91 |
| 关系边 | 31 |
| 悬空关系 | 97 |
| 合并冲突 | 39 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 12 |
| `quote_too_short` | 6 |
| `unknown_relation_predicate` | 1 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 37 |
| symptom | 19 |
| riskFactor | 11 |
| complication | 10 |
| lifestyleIntervention | 8 |
| labTest | 2 |
| medication | 2 |
| contraindication | 1 |
| monitoringSchedule | 1 |

## 合并冲突样例

- riskFactor/smoking: name: 'Smoking' vs 'smoking'
- riskFactor/smoking: evidenceNote: 'Smoking raises your risk of developing heart disease. If you have diabetes, it is important to stop smoking, because both smoking and diabetes narrow blood vessels.' vs 'Smoking is a risk factor for heart disease in people with diabetes, and quitting can lower the risk of heart attack, stroke, and other complications.'
- riskFactor/abnormal-cholesterol-levels: name: 'Abnormal Cholesterol Levels' vs 'Abnormal cholesterol levels'
- riskFactor/obesity-and-belly-fat: name: 'Obesity and Belly Fat' vs 'Obesity and belly fat'
- riskFactor/family-history-of-heart-disease: name: 'Family History of Heart Disease' vs 'Family history of heart disease'
- riskFactor/male-sex: name: 'Male Sex' vs 'Male'
- riskFactor/chronic-kidney-disease: name: 'Chronic Kidney Disease' vs 'Chronic kidney disease'
- complication/heart-attack: name: 'Heart Attack' vs 'Heart attack'
- complication/kidney-disease: name: 'Kidney Disease' vs 'Kidney disease'
- complication/eye-disease: name: 'Eye Disease' vs 'Eye disease'
- complication/high-blood-pressure: name: 'High Blood Pressure' vs 'High blood pressure'
- complication/high-cholesterol: name: 'High Cholesterol' vs 'High cholesterol'
- complication/high-blood-glucose: name: 'High Blood Glucose' vs 'High blood glucose'
- riskFactor/high-blood-glucose: name: 'High Blood Glucose' vs 'high blood glucose'
- riskFactor/high-blood-pressure: name: 'High Blood Pressure' vs 'high blood pressure'
- riskFactor/high-cholesterol: name: 'High Cholesterol' vs 'high cholesterol'
- riskFactor/physical-inactivity: name: 'Physical Inactivity' vs 'physical inactivity'
- riskFactor/chronic-stress: name: 'Chronic Stress' vs 'chronic stress'
- medication/statin: name: 'Statin' vs 'statin'
- medication/aspirin: name: 'Aspirin' vs 'aspirin'

## 悬空关系样例

- `heart-disease` --presentsWith--> `High Blood Pressure`（未找到）
- `heart-disease` --presentsWith--> `Abnormal Cholesterol Levels`（未找到）
- `heart-disease` --presentsWith--> `Obesity and Belly Fat`（未找到）
- `heart-disease` --presentsWith--> `Chronic Kidney Disease`（未找到）
- `heart-disease` --presentsWith--> `Smoking`（未找到）
- `chronic-kidney-disease` --presentsWith--> `Heart Disease`（未找到）
- `chronic-kidney-disease` --presentsWith--> `Stroke`（未找到）
- `chronic-kidney-disease` --presentsWith--> `High Blood Pressure`（未找到）
- `smoking` --presentsWith--> `Heart Disease`（未找到）
- `smoking` --presentsWith--> `Stroke`（未找到）
- `smoking` --increasesRiskOf--> `Heart Disease`（未找到）
- `smoking` --increasesRiskOf--> `Stroke`（未找到）
- `smoking` --increasesRiskOf--> `Heart Attack`（未找到）
- `smoking` --increasesRiskOf--> `Stroke`（未找到）
- `smoking` --increasesRiskOf--> `Nerve Disease`（未找到）
- `smoking` --increasesRiskOf--> `Kidney Disease`（未找到）
- `smoking` --increasesRiskOf--> `Eye Disease`（未找到）
- `smoking` --increasesRiskOf--> `Amputation`（未找到）
- `abnormal-cholesterol-levels` --increasesRiskOf--> `Heart Disease`（未找到）
- `abnormal-cholesterol-levels` --increasesRiskOf--> `Stroke`（未找到）
