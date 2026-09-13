# 抽取质量报告 — jbds_12_managing_diabetes_and_hyperglycaemia_during_labour_and_birth_with_qr_code_february_2023

- 源文件：`ontology/knowledges/pdfs/JBDS_12_Managing_diabetes_and_hyperglycaemia_during_labour_and_birth_with_QR_code_February_2023.pdf`（sha256 `5c9eb2f58b2c…`）
- 目标图：`urn:dmo:extract:jbds_12_managing_diabetes_and_hyperglycaemia_during_labour_and_birth_with_qr_code_february_2023`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：28

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **85.4%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 95.2% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 43.2% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.38 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 698 |
| 通过校验 | 596 |
| 丢弃 | 102 |
| 消解后实体 | 431 |
| 关系边 | 158 |
| 悬空关系 | 120 |
| 合并冲突 | 287 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 80 |
| `quote_too_short` | 18 |
| `unknown_relation_predicate` | 4 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 215 |
| monitoringSchedule | 32 |
| riskFactor | 29 |
| medication | 27 |
| labTest | 26 |
| device | 21 |
| drugClass | 20 |
| complication | 15 |
| diabetesType | 14 |
| symptom | 14 |
| adverseEffect | 8 |
| contraindication | 5 |
| lifestyleIntervention | 5 |

## 合并冲突样例

- diabetesType/gestational-diabetes: name: 'gestational diabetes' vs 'Gestational Diabetes'
- diabetesType/gestational-diabetes: prevalenceShare: 0.05 vs 0.0
- diabetesType/gestational-diabetes: definition: 'This guideline provides guidance on the management of women with pre-existing diabetes (type 1 or type 2), or gestational diabetes when admitted to maternity units in the following situations' vs 'Gestational Diabetes'
- diabetesType/gestational-diabetes: name: 'gestational diabetes' vs 'Gestational Diabetes'
- diabetesType/gestational-diabetes: mondoCode: 'MONDO:0005147' vs 'MONDO:0005149'
- diabetesType/gestational-diabetes: definition: 'This guideline provides guidance on the management of women with pre-existing diabetes (type 1 or type 2), or gestational diabetes when admitted to maternity units in the following situations' vs 'different types of diabetes (type 1, type 2 or gestational) would require different approaches depending upon the risk factors, antenatal treatment (diet, metformin, insulin), risk of hypoglycaemia, risk of anaesthesia and the presence of obstetric complications.'
- diabetesType/gestational-diabetes: prevalenceShare: 0.05 vs 0.0
- diabetesType/gestational-diabetes: definition: 'This guideline provides guidance on the management of women with pre-existing diabetes (type 1 or type 2), or gestational diabetes when admitted to maternity units in the following situations' vs 'Women with GDM should be informed that all glucose lowering therapies will be stopped after the delivery of placenta'
- diabetesType/gestational-diabetes: name: 'gestational diabetes' vs 'Gestational Diabetes'
- diabetesType/gestational-diabetes: mondoCode: 'MONDO:0005147' vs 'MONDO:0005148'
- diabetesType/gestational-diabetes: prevalenceShare: 0.05 vs 0.07
- diabetesType/gestational-diabetes: definition: 'This guideline provides guidance on the management of women with pre-existing diabetes (type 1 or type 2), or gestational diabetes when admitted to maternity units in the following situations' vs 'Gestational Diabetes is a form of diabetes that develops during pregnancy and typically resolves after delivery.'
- diabetesType/gestational-diabetes: name: 'gestational diabetes' vs 'Gestational diabetes'
- diabetesType/gestational-diabetes: definition: 'This guideline provides guidance on the management of women with pre-existing diabetes (type 1 or type 2), or gestational diabetes when admitted to maternity units in the following situations' vs 'Women with gestational diabetes have a ten times increased risk of developing type 2 diabetes within 5 years'
- diabetesType/gestational-diabetes: name: 'gestational diabetes' vs 'Gestational Diabetes'
- diabetesType/gestational-diabetes: mondoCode: 'MONDO:0005147' vs 'MONDO:0005149'
- diabetesType/gestational-diabetes: definition: 'This guideline provides guidance on the management of women with pre-existing diabetes (type 1 or type 2), or gestational diabetes when admitted to maternity units in the following situations' vs 'Neonatal hypoglycaemia results from excessive fetal insulin production as a consequence of the sudden cessation of maternal-fetal glucose transfer after birth.'
- diabetesType/gestational-diabetes: name: 'gestational diabetes' vs 'Gestational Diabetes'
- diabetesType/gestational-diabetes: mondoCode: 'MONDO:0005147' vs 'MONDO:0005149'
- diabetesType/gestational-diabetes: prevalenceShare: 0.05 vs 0.65

## 悬空关系样例

- `gestational-diabetes` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `gestational-diabetes` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `diabetic-ketoacidosis` --presentsWith--> `Abdominal Pain`（未找到）
- `type-2-diabetes` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `type-2-diabetes` --predisposesTo--> `Gestational diabetes`（未找到）
- `insulin` --hasContraindication--> `Diabetic Ketoacidosis`（未找到）
- `insulin` --hasContraindication--> `Metformin`（未找到）
- `insulin` --hasContraindication--> `Insulin pump use near diathermy sites`（未找到）
- `insulin` --hasContraindication--> `Diabetic Ketoacidosis`（未找到）
- `insulin` --hasContraindication--> `Pregnancy`（未找到）
- `insulin` --hasContraindication--> `Corticosteroids`（未找到）
- `insulin` --hasContraindication--> `Insulin`（未找到）
- `insulin` --causesAdverseEffect--> `Hypoglycemia`（未找到）
- `type-1-diabetes` --increasesRiskOf--> `Sustained Maternal Hyperglycaemia During Pregnancy`（未找到）
- `metformin` --hasContraindication--> `Insulin`（未找到）
- `metformin` --causesAdverseEffect--> `Gastrointestinal disturbances`（未找到）
- `target-glucose-levels-during-labour` --definesTarget--> `Target glucose levels during labour`（未找到）
- `glucose-monitoring-during-general-anaesthesia` --appliesToType--> `Hourly blood glucose monitoring in established labour`（未找到）
- `glucose-target-range-for-vriii-use` --definesTarget--> `Glucose target range for VRIII use`（未找到）
- `use-of-capillary-blood-glucose-to-adjust-vriii-doses` --appliesToType--> `Use of VRIII for glucose control in labour`（未找到）
