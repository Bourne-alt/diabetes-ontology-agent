# 抽取质量报告 — niddk-diabetic-foot-problems

- 源文件：`ontology/knowledges/niddk-diabetic-foot-problems.txt`（sha256 `9775da439bd6…`）
- 目标图：`urn:dmo:extract:niddk-diabetic-foot-problems`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：3

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **68.9%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 38.7% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 37.5% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.03 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 103 |
| 通过校验 | 71 |
| 丢弃 | 32 |
| 消解后实体 | 69 |
| 关系边 | 15 |
| 悬空关系 | 9 |
| 合并冲突 | 13 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 16 |
| `unknown_relation_predicate` | 16 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 40 |
| riskFactor | 7 |
| complication | 6 |
| lifestyleIntervention | 5 |
| symptom | 5 |
| contraindication | 4 |
| monitoringSchedule | 2 |

## 合并冲突样例

- complication/gangrene: mondoCode: 'MONDO:0005150' vs 'MONDO:0005141'
- complication/gangrene: onsetPattern: 'Chronic' vs 'Acute'
- complication/gangrene: isEmergency: False vs True
- complication/gangrene: definition: 'The infection might lead to gangrene.' vs 'a foot infection that becomes black and smelly—signs you might have gangrene'
- riskFactor/diabetic-neuropathy: name: 'Diabetic Neuropathy' vs 'diabetic neuropathy'
- riskFactor/poor-blood-flow-to-feet: name: 'Poor Blood Flow to Feet' vs 'poor blood flow to feet'
- riskFactor/high-blood-glucose-levels: name: 'High Blood Glucose Levels' vs 'high blood glucose levels'
- recommendation/wear-shoes-and-socks-at-all-times: statement: 'Wear shoes and socks at all times.' vs 'Wear shoes and socks at all times. Do not walk barefoot or in just socks – even when you are indoors. You could step on something and hurt your feet. You may not feel any pain and may not know that you hurt yourself.'
- symptom/loss-of-feeling-in-feet: name: 'Loss of Feeling in Feet' vs 'loss of feeling in your feet'
- symptom/red-warm-or-painful-skin-on-foot: name: 'Red, Warm, or Painful Skin on Foot' vs 'skin on your foot that becomes red, warm, or painful—signs of a possible infection'
- symptom/cut-blister-or-bruise-on-foot-that-does-not-heal: name: 'Cut, Blister, or Bruise on Foot That Does Not Heal' vs 'a cut, blister, or bruise on your foot that does not start to heal after a few days'
- symptom/callus-with-dried-blood-inside: name: 'Callus with Dried Blood Inside' vs 'a callus with dried blood inside of it,which often can be the first sign of a wound under the callus'
- symptom/foot-infection-with-black-and-smelly-appearance: name: 'Foot Infection with Black and Smelly Appearance' vs 'a foot infection that becomes black and smelly—signs you might have gangrene'

## 悬空关系样例

- `gangrene` --presentsWith--> `Foot Ulcers`（未找到）
- `charcot-s-foot` --presentsWith--> `Diabetic Neuropathy`（未找到）
- `diabetic-neuropathy` --increasesRiskOf--> `Foot Ulcers`（未找到）
- `diabetic-neuropathy` --increasesRiskOf--> `Gangrene`（未找到）
- `poor-blood-flow-to-feet` --increasesRiskOf--> `Foot Ulcers`（未找到）
- `poor-blood-flow-to-feet` --increasesRiskOf--> `Gangrene`（未找到）
- `high-blood-glucose-levels` --increasesRiskOf--> `Diabetic Neuropathy`（未找到）
- `high-blood-glucose-levels` --increasesRiskOf--> `Poor Blood Flow to Feet`（未找到）
- `stop-smoking` --mitigatesRiskFactor--> `Peripheral artery disease`（未找到）
