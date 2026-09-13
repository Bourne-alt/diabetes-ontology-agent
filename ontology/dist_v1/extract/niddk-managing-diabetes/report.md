# 抽取质量报告 — niddk-managing-diabetes

- 源文件：`ontology/knowledges/niddk-managing-diabetes.txt`（sha256 `b4c9ee184469…`）
- 目标图：`urn:dmo:extract:niddk-managing-diabetes`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：4

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **82.8%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 74.2% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 63.6% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.1 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 93 |
| 通过校验 | 77 |
| 丢弃 | 16 |
| 消解后实体 | 70 |
| 关系边 | 24 |
| 悬空关系 | 42 |
| 合并冲突 | 26 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 13 |
| `unknown_relation_predicate` | 3 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 27 |
| complication | 12 |
| symptom | 11 |
| lifestyleIntervention | 5 |
| device | 5 |
| labTest | 4 |
| diabetesType | 3 |
| medication | 1 |
| monitoringSchedule | 1 |
| drugClass | 1 |

## 合并冲突样例

- complication/kidney-disease: name: 'Kidney Disease' vs 'Kidney disease'
- complication/kidney-disease: mondoCode: 'MONDO:0005149' vs 'MONDO:0005147'
- complication/kidney-disease: definition: 'Kidney disease is a health problem from diabetes that can be prevented or delayed by managing your ABCs.' vs 'participants with type 1 diabetes who kept their blood glucose levels close to normal greatly lowered their chances of developing eye, kidney, and nerve disease'
- medication/statin: name: 'Statin' vs 'statin'
- diabetesType/type-1-diabetes: definition: 'If you have type 1 diabetes, your health care team may ask you to check your urine at home for substances called ketones.' vs 'Most often, ketoacidosis affects people with type 1 diabetes.'
- diabetesType/type-1-diabetes: prevalenceShare: 0.1 vs 0.05
- diabetesType/type-1-diabetes: definition: 'If you have type 1 diabetes, your health care team may ask you to check your urine at home for substances called ketones.' vs 'participants with type 1 diabetes who kept their blood glucose levels close to normal greatly lowered their chances of developing eye, kidney, and nerve disease'
- labTest/urine-ketones: definition: 'Substances in the urine that indicate the body is breaking down fat for energy, which can happen when there is not enough insulin.' vs 'Checking urine for ketones is recommended if you have symptoms of diabetic ketoacidosis.'
- complication/diabetic-ketoacidosis: name: 'Diabetic Ketoacidosis' vs 'Diabetic ketoacidosis'
- complication/diabetic-ketoacidosis: mondoCode: 'MONDO:0005075' vs 'MONDO:0005148'
- complication/diabetic-ketoacidosis: definition: 'A dangerous condition that may develop if high levels of ketones are left untreated.' vs 'Diabetic ketoacidosis is a medical emergency that needs to be treated right away.'
- diabetesType/type-2-diabetes: definition: 'However, some people with type 2 diabetes can develop ketoacidosis if they do not produce enough insulin.' vs 'people with type 2 diabetes. The study found that people with less effective diabetes management during the first year after being diagnosed with diabetes had a higher risk of diabetes complications and death.'
- symptom/feeling-shaky-or-jittery: name: 'Feeling Shaky or Jittery' vs 'feeling shaky or jittery'
- symptom/headache: name: 'Headache' vs 'headache'
- symptom/cold-sweat: name: 'Cold Sweat' vs 'cold sweat'
- symptom/feeling-tired: name: 'Feeling Tired' vs 'feeling tired'
- symptom/feeling-thirsty: name: 'Feeling Thirsty' vs 'feeling thirsty'
- symptom/having-blurry-vision: name: 'Having Blurry Vision' vs 'having blurry vision'
- symptom/urinating-too-often: name: 'Urinating Too Often' vs 'urinating too often'
- symptom/feeling-very-tired: name: 'Feeling Very Tired' vs 'feeling very tired'

## 悬空关系样例

- `heart-attack` --presentsWith--> `Diabetes`（未找到）
- `stroke` --presentsWith--> `Diabetes`（未找到）
- `kidney-disease` --presentsWith--> `Diabetes`（未找到）
- `blindness` --presentsWith--> `Diabetes`（未找到）
- `foot-or-leg-amputation` --presentsWith--> `Diabetes`（未找到）
- `a1c-blood-glucose-test` --definesTarget--> `A1C level below 7%`（未找到）
- `blood-pressure-goal-below-130-80-mm-hg` --definesTarget--> `Blood pressure goal below 130/80 mm Hg`（未找到）
- `cholesterol-test` --definesTarget--> `Cholesterol level`（未找到）
- `stop-smoking` --appliesToType--> `Diabetes`（未找到）
- `create-a-healthy-meal-plan` --appliesToType--> `Diabetes`（未找到）
- `get-physical-activity` --appliesToType--> `Diabetes`（未找到）
- `reach-and-maintain-a-healthy-weight` --appliesToType--> `Diabetes`（未找到）
- `get-enough-sleep` --appliesToType--> `Diabetes`（未找到）
- `take-care-of-your-mental-health` --appliesToType--> `Diabetes`（未找到）
- `diabetic-ketoacidosis` --presentsWith--> `Ketones in Urine`（未找到）
- `insulin` --hasContraindication--> `Diabetic ketoacidosis`（未找到）
- `continuous-glucose-monitor` --deviceMeasuresTest--> `Blood Glucose Level`（未找到）
- `artificial-pancreas` --deviceMeasuresTest--> `Continuous Glucose Monitor`（未找到）
- `artificial-pancreas` --deviceMeasuresTest--> `Insulin Pump`（未找到）
- `insulin-pump` --deviceMeasuresTest--> `Continuous Glucose Monitor`（未找到）
