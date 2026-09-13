# 抽取质量报告 — niddk-symptoms-causes

- 源文件：`ontology/knowledges/niddk-symptoms-causes.txt`（sha256 `644724a0516b…`）
- 目标图：`urn:dmo:extract:niddk-symptoms-causes`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：3

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **73.5%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 46.8% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 46.8% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.06 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 98 |
| 通过校验 | 72 |
| 丢弃 | 26 |
| 消解后实体 | 68 |
| 关系边 | 41 |
| 悬空关系 | 36 |
| 合并冲突 | 52 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 18 |
| `quote_too_short` | 8 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| riskFactor | 35 |
| diabetesType | 13 |
| symptom | 11 |
| medication | 6 |
| adverseEffect | 1 |
| lifestyleIntervention | 1 |
| recommendation | 1 |

## 合并冲突样例

- diabetesType/type-2-diabetes: mondoCode: 'MONDO:0005148' vs 'MONDO:0005147'
- diabetesType/type-2-diabetes: definition: 'Type 2 diabetes develops when your pancreas doesn’t produce enough insulin, and your body has trouble using insulin, a condition called insulin resistance.' vs 'The Diabetes Prevention Program (DPP) studied how to prevent or delay disease in people at high risk of developing type 2 diabetes. The study found that participants who did regular physical activity and lost 5% to 7% of their body weight lowered their chance of developing type 2 diabetes.'
- symptom/feeling-very-hungry-even-after-eating: name: 'Feeling Very Hungry Even After Eating' vs 'feeling very hungry, even after you have eaten'
- symptom/frequent-infections: name: 'Frequent Infections' vs 'frequent infections, such as urinary tract infections, skin infections NIH external link, or yeast infections NIH external link'
- symptom/unexplained-weight-loss: name: 'Unexplained Weight Loss' vs 'unexplained weight loss'
- symptom/trouble-breathing: name: 'Trouble Breathing' vs 'having trouble breathing'
- symptom/fruity-smelling-breath: name: 'Fruity-Smelling Breath' vs 'having fruity-smelling breath'
- symptom/fainting-from-dehydration: name: 'Fainting from Dehydration' vs 'fainting from dehydration'
- symptom/abdominal-pain: name: 'Abdominal Pain' vs 'having pain in your abdomen, nausea, or vomiting'
- symptom/nausea: name: 'Nausea' vs 'having pain in your abdomen, nausea, or vomiting'
- symptom/vomiting: name: 'Vomiting' vs 'having pain in your abdomen, nausea, or vomiting'
- symptom/pain-numbness-or-tingling-in-feet-or-hands: name: 'Pain, Numbness, or Tingling in Feet or Hands' vs 'pain, numbness, or tingling in the feet or hands'
- symptom/chest-pain: name: 'Chest Pain' vs 'chest pain'
- riskFactor/history-of-gestational-diabetes: name: 'History of Gestational Diabetes' vs 'Gestational diabetes history'
- riskFactor/history-of-gestational-diabetes: name: 'History of Gestational Diabetes' vs 'history of gestational diabetes'
- riskFactor/history-of-gestational-diabetes: evidenceNote: 'People with a history of gestational diabetes are at higher risk of developing type 2 diabetes later in life.' vs 'have a history of gestational diabetes, a type of diabetes that develops during pregnancy, or gave birth to a baby weighing 9 pounds or more.'
- riskFactor/overweight: name: 'Overweight' vs 'overweight'
- riskFactor/obesity: name: 'Obesity' vs 'obesity'
- riskFactor/large-waist-size: name: 'Large Waist Size' vs 'large waist size'
- riskFactor/age-35-or-older: name: 'Age 35 or Older' vs 'age 35 or older'

## 悬空关系样例

- `type-2-diabetes` --predisposesTo--> `Prediabetes`（未找到）
- `gestational-diabetes` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `prediabetes` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `monogenic-diabetes` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `cushing-s-syndrome` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `acromegaly` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `hyperthyroidism` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `hypothyroidism` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `pancreatitis` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `antiseizure-medicines` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `immunosuppressants` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `monogenic-diabetes` --increasesRiskOf--> `Diabetes`（未找到）
- `cystic-fibrosis` --increasesRiskOf--> `Diabetes`（未找到）
- `hemochromatosis` --increasesRiskOf--> `Diabetes`（未找到）
- `cushing-s-syndrome` --increasesRiskOf--> `Insulin Resistance`（未找到）
- `cushing-s-syndrome` --increasesRiskOf--> `Diabetes`（未找到）
- `acromegaly` --increasesRiskOf--> `Insulin Resistance`（未找到）
- `acromegaly` --increasesRiskOf--> `Diabetes`（未找到）
- `hyperthyroidism` --increasesRiskOf--> `Insulin Resistance`（未找到）
- `hyperthyroidism` --increasesRiskOf--> `Diabetes`（未找到）
