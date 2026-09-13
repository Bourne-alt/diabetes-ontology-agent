# 抽取质量报告 — niddk-pregnancy-preexisting-diabetes

- 源文件：`ontology/knowledges/niddk-pregnancy-preexisting-diabetes.txt`（sha256 `0717b4f58acd…`）
- 目标图：`urn:dmo:extract:niddk-pregnancy-preexisting-diabetes`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：4

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **66.4%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 85.5% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 54.9% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.07 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 122 |
| 通过校验 | 81 |
| 丢弃 | 41 |
| 消解后实体 | 76 |
| 关系边 | 37 |
| 悬空关系 | 45 |
| 合并冲突 | 33 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 36 |
| `unknown_relation_predicate` | 5 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 27 |
| riskFactor | 11 |
| complication | 10 |
| lifestyleIntervention | 6 |
| monitoringSchedule | 6 |
| contraindication | 3 |
| labTest | 3 |
| device | 3 |
| symptom | 3 |
| diabetesType | 2 |
| drugClass | 1 |
| medication | 1 |

## 合并冲突样例

- diabetesType/type-2-diabetes: mondoCode: 'MONDO:0005147' vs 'MONDO:0005148'
- diabetesType/type-2-diabetes: definition: 'Some people develop diabetes during pregnancy that goes away after they have the baby. This type of diabetes is called gestational diabetes. However, having gestational diabetes increases your risk of getting type 2 diabetes later in life.' vs 'If you have gestational diabetes, you are more likely to develop type 2 diabetes later in life.'
- diabetesType/gestational-diabetes: mondoCode: 'MONDO:0005148' vs 'MONDO:0005147'
- diabetesType/gestational-diabetes: prevalenceShare: 0.07 vs 0.05
- diabetesType/gestational-diabetes: definition: 'Some people develop diabetes during pregnancy that goes away after they have the baby. This type of diabetes is called gestational diabetes.' vs 'If you had gestational diabetes, your health care team will check your blood glucose levels in the first 3 months after having your baby to see if your gestational diabetes has completely gone away.'
- riskFactor/high-blood-glucose-levels: name: 'High Blood Glucose Levels' vs '高血糖水平'
- riskFactor/high-blood-glucose-levels: name: 'High Blood Glucose Levels' vs 'high blood glucose levels'
- riskFactor/high-blood-glucose-levels: evidenceNote: '高血糖水平在怀孕早期会损害胎儿，增加出生缺陷的风险。' vs 'The document states that high blood glucose levels can worsen diabetes-related health problems during pregnancy.'
- riskFactor/gestational-diabetes: name: 'Gestational Diabetes' vs '妊娠期糖尿病'
- riskFactor/gestational-diabetes: name: 'Gestational Diabetes' vs 'Gestational diabetes'
- riskFactor/gestational-diabetes: riskCategory: 'Modifiable' vs 'Obstetric'
- riskFactor/gestational-diabetes: evidenceNote: '妊娠期糖尿病在产后通常会消失，但会增加未来患2型糖尿病的风险。' vs 'Gestational diabetes is a condition that occurs during pregnancy and increases the risk of developing type 2 diabetes later in life.'
- riskFactor/being-overweight: name: 'Being Overweight' vs '超重'
- riskFactor/physical-inactivity: name: 'Physical Inactivity' vs '久坐不动'
- complication/diabetic-eye-disease: mondoCode: 'MONDO:0005147' vs 'MONDO:0005041'
- complication/diabetic-eye-disease: definition: 'Diabetic eye disease can get worse during your pregnancy, and you may need special care.' vs 'Diabetic eye disease may get worse after you have a baby.'
- riskFactor/diabetes: name: 'Diabetes' vs 'diabetes'
- riskFactor/preeclampsia: name: 'Preeclampsia' vs 'preeclampsia'
- riskFactor/large-for-gestational-age-baby: name: 'Large for Gestational Age Baby' vs 'large for gestational age baby'
- riskFactor/smoking: name: 'Smoking' vs 'smoking'

## 悬空关系样例

- `type-2-diabetes` --predisposesTo--> `Gestational Diabetes`（未找到）
- `type-2-diabetes` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `gestational-diabetes` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `gestational-diabetes` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `birth-defects` --presentsWith--> `High blood glucose levels`（未找到）
- `preterm-birth` --presentsWith--> `High blood glucose levels`（未找到）
- `miscarriage` --presentsWith--> `High blood glucose levels`（未找到）
- `obesity` --presentsWith--> `High blood glucose levels`（未找到）
- `high-blood-glucose-levels` --increasesRiskOf--> `Birth Defects`（未找到）
- `high-blood-glucose-levels` --increasesRiskOf--> `Preterm Birth`（未找到）
- `high-blood-glucose-levels` --increasesRiskOf--> `Large for Gestational Age`（未找到）
- `high-blood-glucose-levels` --increasesRiskOf--> `Neonatal Respiratory Distress Syndrome`（未找到）
- `high-blood-glucose-levels` --increasesRiskOf--> `Neonatal Hypoglycemia`（未找到）
- `high-blood-glucose-levels` --increasesRiskOf--> `Miscarriage`（未找到）
- `high-blood-glucose-levels` --increasesRiskOf--> `Stillbirth`（未找到）
- `high-blood-glucose-levels` --increasesRiskOf--> `Childhood Obesity`（未找到）
- `high-blood-glucose-levels` --increasesRiskOf--> `Type 2 Diabetes in Offspring`（未找到）
- `high-blood-glucose-levels` --increasesRiskOf--> `Preeclampsia`（未找到）
- `high-blood-glucose-levels` --increasesRiskOf--> `Diabetic Eye Disease`（未找到）
- `high-blood-glucose-levels` --increasesRiskOf--> `Diabetic Kidney Disease`（未找到）
