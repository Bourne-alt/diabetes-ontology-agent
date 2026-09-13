# 抽取质量报告 — niddk-diabetic-eye-disease

- 源文件：`ontology/knowledges/niddk-diabetic-eye-disease.txt`（sha256 `b7986310bc70…`）
- 目标图：`urn:dmo:extract:niddk-diabetic-eye-disease`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：3

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **89.4%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 64.5% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 58.9% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.23 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 85 |
| 通过校验 | 76 |
| 丢弃 | 9 |
| 消解后实体 | 62 |
| 关系边 | 46 |
| 悬空关系 | 66 |
| 合并冲突 | 50 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `unknown_relation_predicate` | 4 |
| `quote_not_found` | 3 |
| `quote_too_short` | 2 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| riskFactor | 16 |
| recommendation | 14 |
| complication | 9 |
| symptom | 9 |
| diabetesType | 4 |
| monitoringSchedule | 4 |
| medication | 3 |
| lifestyleIntervention | 2 |
| labTest | 1 |

## 合并冲突样例

- complication/diabetic-retinopathy: definition: 'Damaged blood vessels can harm the retina, causing a disease called diabetic retinopathy.' vs 'Diabetic retinopathy is the most common cause of vision loss in people with diabetes.'
- complication/proliferative-diabetic-retinopathy: mondoCode: 'MONDO:0005150' vs 'MONDO:0005116'
- complication/proliferative-diabetic-retinopathy: definition: 'If the disease gets worse, some blood vessels close off, which causes new blood vessels to grow, or proliferate, on the surface of the retina. This stage is called proliferative diabetic retinopathy.' vs 'A condition in which abnormal blood vessels grow in the retina due to diabetes, potentially leading to severe vision loss or blindness.'
- complication/diabetic-macular-edema: mondoCode: 'MONDO:0005151' vs 'MONDO:0005115'
- complication/diabetic-macular-edema: definition: 'The part of your retina that you need for reading, driving, and seeing faces is called the macula. Diabetes can lead to swelling in the macula, which is called diabetic macular edema.' vs 'A condition characterized by swelling in the macula of the retina due to diabetes, which can lead to vision loss.'
- complication/glaucoma: mondoCode: 'MONDO:0005152' vs 'MONDO:0005147'
- complication/glaucoma: definition: 'Glaucoma is a group of eye diseases that can damage the optic nerve—the bundle of nerves that connects the eye to the brain.' vs 'Your chances of developing glaucoma or cataracts are about twice that of someone without diabetes.'
- complication/cataracts: mondoCode: 'MONDO:0005153' vs 'MONDO:0005146'
- complication/cataracts: definition: 'The lenses within our eyes are clear structures that help provide sharp vision—but they tend to become cloudy as we age. People with diabetes are more likely to develop cloudy lenses, called cataracts.' vs 'Your chances of developing glaucoma or cataracts are about twice that of someone without diabetes.'
- symptom/blurry-vision: name: 'Blurry Vision' vs 'blurry vision'
- symptom/cloudy-vision: name: 'Cloudy Vision' vs 'cloudy vision'
- symptom/faded-colors: name: 'Faded Colors' vs 'faded colors'
- symptom/loss-of-side-vision: name: 'Loss of Side Vision' vs 'loss of side vision'
- riskFactor/high-blood-glucose: name: 'High Blood Glucose' vs '高血糖'
- riskFactor/high-blood-glucose: name: 'High Blood Glucose' vs '高血糖'
- riskFactor/high-blood-glucose: evidenceNote: '高血糖是糖尿病影响眼睛的主要原因，长期高血糖会损害视网膜的微小血管。' vs '未治疗的高血糖会增加糖尿病眼病的风险。'
- riskFactor/prediabetes: name: 'Prediabetes' vs '糖尿病前期'
- riskFactor/smoking: name: 'Smoking' vs '吸烟'
- riskFactor/smoking: name: 'Smoking' vs '吸烟'
- riskFactor/smoking: evidenceNote: '文档建议吸烟者应寻求帮助戒烟，暗示吸烟是可干预的风险因素。' vs '吸烟可能增加糖尿病眼病的风险。'

## 悬空关系样例

- `diabetic-retinopathy` --hasStage--> `Nonproliferative Diabetic Retinopathy`（未找到）
- `diabetic-retinopathy` --hasStage--> `Proliferative Diabetic Retinopathy`（未找到）
- `diabetic-retinopathy` --presentsWith--> `Diabetic Macular Edema`（未找到）
- `nonproliferative-diabetic-retinopathy` --hasStage--> `Diabetic Retinopathy`（未找到）
- `proliferative-diabetic-retinopathy` --hasStage--> `Diabetic Retinopathy`（未找到）
- `proliferative-diabetic-retinopathy` --presentsWith--> `Diabetic Retinopathy`（未找到）
- `diabetic-macular-edema` --presentsWith--> `Diabetic Retinopathy`（未找到）
- `diabetic-macular-edema` --presentsWith--> `Diabetic Retinopathy`（未找到）
- `glaucoma` --presentsWith--> `Diabetic Retinopathy`（未找到）
- `cataracts` --presentsWith--> `Diabetic Retinopathy`（未找到）
- `high-blood-glucose` --increasesRiskOf--> `Diabetic Retinopathy`（未找到）
- `high-blood-glucose` --increasesRiskOf--> `Diabetic Macular Edema`（未找到）
- `high-blood-glucose` --increasesRiskOf--> `Cataracts`（未找到）
- `high-blood-glucose` --increasesRiskOf--> `Glaucoma`（未找到）
- `high-blood-glucose` --increasesRiskOf--> `Diabetic Eye Disease`（未找到）
- `prediabetes` --increasesRiskOf--> `Diabetic Retinopathy`（未找到）
- `smoking` --increasesRiskOf--> `Diabetic Retinopathy`（未找到）
- `smoking` --increasesRiskOf--> `Diabetic Macular Edema`（未找到）
- `smoking` --increasesRiskOf--> `Glaucoma`（未找到）
- `smoking` --increasesRiskOf--> `Cataracts`（未找到）
