# 抽取质量报告 — niddk-healthy-living-with-diabetes

- 源文件：`ontology/knowledges/niddk-healthy-living-with-diabetes.txt`（sha256 `f8169016f763…`）
- 目标图：`urn:dmo:extract:niddk-healthy-living-with-diabetes`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：4

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **74.0%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 69.3% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 33.0% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.09 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 100 |
| 通过校验 | 74 |
| 丢弃 | 26 |
| 消解后实体 | 68 |
| 关系边 | 61 |
| 悬空关系 | 30 |
| 合并冲突 | 19 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 24 |
| `unknown_relation_predicate` | 2 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 36 |
| lifestyleIntervention | 9 |
| contraindication | 5 |
| riskFactor | 5 |
| complication | 4 |
| drugClass | 2 |
| adverseEffect | 2 |
| diabetesType | 2 |
| medication | 2 |
| labTest | 1 |

## 合并冲突样例

- drugClass/sulfonylureas: mechanism: 'Stimulate insulin secretion from the pancreas' vs 'Sulfonylureas stimulate the pancreas to release more insulin.'
- drugClass/sulfonylureas: name: 'Sulfonylureas' vs 'sulfonylureas'
- drugClass/sulfonylureas: mechanism: 'Stimulate insulin secretion from the pancreas' vs 'Stimulate the pancreas to release more insulin'
- drugClass/insulin: mechanism: 'Replaces or supplements insulin in the body to lower blood glucose' vs 'Insulin is a hormone that helps regulate blood glucose levels by allowing cells to take in glucose from the bloodstream.'
- drugClass/insulin: weightEffect: 'Gain' vs 'Neutral'
- drugClass/insulin: name: 'Insulin' vs 'insulin'
- drugClass/insulin: mechanism: 'Replaces or supplements insulin in the body to lower blood glucose' vs 'Replace or supplement insulin in the body to lower blood glucose'
- adverseEffect/hypoglycemia: name: 'Hypoglycemia' vs '低血糖'
- lifestyleIntervention/healthy-meal-plan: name: 'Healthy meal plan' vs 'Healthy Meal Plan'
- lifestyleIntervention/healthy-meal-plan: activityTarget: 'Include dairy or plant-based dairy products, fruits, nonstarchy vegetables, protein foods, and whole grains; choose foods with vitamins, calcium, fiber, and healthy fats; limit foods high in saturated fat, sodium, and added sugar; limit alcohol; consider carb counting or the plate method for portion control' vs 'Following a healthy meal plan'
- lifestyleIntervention/healthy-meal-plan: expectedBenefit: 'Help keep blood glucose, blood pressure, and cholesterol levels in recommended ranges; help reach and maintain a healthy weight; prevent or delay diabetes-related health problems' vs 'Help you reach and maintain a healthy weight'
- complication/low-blood-glucose: mondoCode: 'MONDO:0005004' vs 'MONDO:0005040'
- complication/low-blood-glucose: definition: 'Low blood glucose levels may last for hours or days after physical activity. You are most likely to have low blood glucose if you take insulin or some other diabetes medicines, such as sulfonylureas.' vs 'Low blood glucose can be a serious medical emergency that must be treated right away.'
- adverseEffect/low-blood-glucose: name: 'Low Blood Glucose' vs '低血糖'
- riskFactor/overweight: name: 'Overweight' vs 'overweight'
- riskFactor/obesity: name: 'Obesity' vs 'obesity'
- riskFactor/diabetes-mellitus: name: 'Diabetes Mellitus' vs 'diabetes mellitus'
- medication/insulin: name: 'Insulin' vs 'insulin'
- medication/sulfonylureas: name: 'Sulfonylureas' vs 'sulfonylureas'

## 悬空关系样例

- `sulfonylureas` --hasContraindication--> `Physical activity`（未找到）
- `insulin` --hasContraindication--> `Physical activity`（未找到）
- `insulin` --causesAdverseEffect--> `Diabetic ketoacidosis`（未找到）
- `healthy-meal-plan` --mitigatesRiskFactor--> `Overweight or Obesity`（未找到）
- `reach-or-maintain-a-healthy-weight` --mitigatesRiskFactor--> `Overweight or obesity`（未找到）
- `include-nutrient-rich-foods-in-meal-plan` --appliesToType--> `Plan Healthy Meals and Snacks`（未找到）
- `ask-about-eating-before-during-or-after-physical-activity` --appliesToType--> `Plan Healthy Meals and Snacks`（未找到）
- `use-carb-counting-or-plate-method-for-portion-control` --appliesToType--> `Plan Healthy Meals and Snacks`（未找到）
- `use-carb-counting-to-adjust-insulin-dose` --appliesToType--> `Use Carb Counting or Plate Method for Portion Control`（未找到）
- `aerobic-activities` --mitigatesRiskFactor--> `High blood glucose`（未找到）
- `aerobic-activities` --mitigatesRiskFactor--> `High blood pressure`（未找到）
- `aerobic-activities` --mitigatesRiskFactor--> `High cholesterol`（未找到）
- `strength-training-or-resistance-training` --mitigatesRiskFactor--> `Weak muscles`（未找到）
- `strength-training-or-resistance-training` --mitigatesRiskFactor--> `Osteoporosis`（未找到）
- `balance-and-stretching-activities` --mitigatesRiskFactor--> `Poor balance`（未找到）
- `balance-and-stretching-activities` --mitigatesRiskFactor--> `Muscle stiffness`（未找到）
- `plate-method-composition` --appliesToType--> `Use of Plate Method for Portion Control`（未找到）
- `carb-counting-not-required-for-non-insulin-users-using-plate-method` --appliesToType--> `Use of Plate Method for Portion Control`（未找到）
- `include-diabetes-educator-or-registered-dietitian-in-care-team` --appliesToType--> `Work with Health Care Team to Create Personalized Meal Plan`（未找到）
- `strength-training-twice-weekly` --appliesToType--> `Engage in Regular Physical Activity for Diabetes Management`（未找到）
