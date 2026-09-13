# 抽取质量报告 — jbds_06_management_of_hhs_in_adults

- 源文件：`ontology/knowledges/pdfs/JBDS_06_Management_of_HHS_in_Adults.pdf`（sha256 `8915bdcdb7a7…`）
- 目标图：`urn:dmo:extract:jbds_06_management_of_hhs_in_adults`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：20

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **77.7%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 85.5% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 48.5% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.2 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 453 |
| 通过校验 | 352 |
| 丢弃 | 101 |
| 消解后实体 | 293 |
| 关系边 | 84 |
| 悬空关系 | 79 |
| 合并冲突 | 161 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 72 |
| `quote_too_short` | 29 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 142 |
| labTest | 30 |
| symptom | 26 |
| contraindication | 20 |
| complication | 19 |
| medication | 17 |
| monitoringSchedule | 11 |
| device | 8 |
| lifestyleIntervention | 8 |
| riskFactor | 5 |
| diabetesType | 4 |
| drugClass | 3 |

## 合并冲突样例

- diabetesType/t1-dm: name: 'T1 DM' vs 'Type 1 diabetes mellitus'
- diabetesType/t2-dm: name: 'T2 DM' vs 'Type 2 diabetes mellitus'
- labTest/osmolality: definition: 'A measure of the concentration of solutes in the blood, calculated as (2Na+) + glucose + urea, used to monitor the response to treatment and avoid sudden osmotic shifts in HHS.' vs 'Osmolality (mOsm/kg) = (2xNa+) + glucose + urea'
- labTest/osmolality: definition: 'A measure of the concentration of solutes in the blood, calculated as (2Na+) + glucose + urea, used to monitor the response to treatment and avoid sudden osmotic shifts in HHS.' vs 'Check creatinine, electrolyte and venous bicarbonate and pH at 1-2 hours then 2 to 4 hourly until osmolality normalised'
- complication/hyperosmolar-hyperglycaemic-state: mondoCode: 'MONDO:0005117' vs 'MONDO:0005200'
- complication/hyperosmolar-hyperglycaemic-state: definition: 'The Hyperosmolar Hyperglycaemic State (HHS) is a medical emergency. It occurs much less frequently than the other hyperglycaemic emergency, diabetic ketoacidosis (DKA), and its treatment requires a different approach.' vs 'The Hyperosmolar Hyperglycaemic State (HHS) is a medical emergency. HHS is associated with a significant morbidity and mortality and must be diagnosed promptly and managed intensively.'
- complication/hyperosmolar-hyperglycaemic-state: mondoCode: 'MONDO:0005117' vs 'MONDO:0019205'
- complication/hyperosmolar-hyperglycaemic-state: definition: 'The Hyperosmolar Hyperglycaemic State (HHS) is a medical emergency. It occurs much less frequently than the other hyperglycaemic emergency, diabetic ketoacidosis (DKA), and its treatment requires a different approach.' vs 'marked hypovolaemia, measured or calculated serum osmolality usually ≥320 mOsm/kg, marked hyperglycaemia (≥30 mmol/L), without significant hyperketonaemia (ketones ≤3.0 mmol/L), without significant acidosis (pH ≥7.3 and blood or serum bicarbonate ≥15.0 mmol/L)'
- complication/hyperosmolar-hyperglycaemic-state: mondoCode: 'MONDO:0005117' vs 'MONDO:0005200'
- complication/hyperosmolar-hyperglycaemic-state: definition: 'The Hyperosmolar Hyperglycaemic State (HHS) is a medical emergency. It occurs much less frequently than the other hyperglycaemic emergency, diabetic ketoacidosis (DKA), and its treatment requires a different approach.' vs 'HHS is uncommon, in the USA accounting for only 13% of hyperglycaemia related emergency admissions (2), but has a higher mortality than DKA (4; 17-19).'
- complication/hyperosmolar-hyperglycaemic-state: mondoCode: 'MONDO:0005117' vs 'MONDO:0019225'
- complication/hyperosmolar-hyperglycaemic-state: definition: 'The Hyperosmolar Hyperglycaemic State (HHS) is a medical emergency. It occurs much less frequently than the other hyperglycaemic emergency, diabetic ketoacidosis (DKA), and its treatment requires a different approach.' vs 'Hypovolaemia + Osmolality >320 mOsm/kg + Marked hyperglcaemia (>30.0 mmol/L) + Without significant hyperketonaemia (<3.0 mmol/L) Without significant acidosis (pH>7.3) and bicarbonate >15.0 mmol/L'
- complication/hyperosmolar-hyperglycaemic-state: mondoCode: 'MONDO:0005117' vs 'MONDO:0005072'
- complication/hyperosmolar-hyperglycaemic-state: definition: 'The Hyperosmolar Hyperglycaemic State (HHS) is a medical emergency. It occurs much less frequently than the other hyperglycaemic emergency, diabetic ketoacidosis (DKA), and its treatment requires a different approach.' vs 'The key parameter in HHS that needs to be taken into account is osmolality.'
- complication/hyperosmolar-hyperglycaemic-state: mondoCode: 'MONDO:0005117' vs 'MONDO:0005200'
- complication/hyperosmolar-hyperglycaemic-state: definition: 'The Hyperosmolar Hyperglycaemic State (HHS) is a medical emergency. It occurs much less frequently than the other hyperglycaemic emergency, diabetic ketoacidosis (DKA), and its treatment requires a different approach.' vs 'A severe metabolic complication of diabetes characterized by extreme hyperglycaemia, hyperosmolality, and absence of significant ketonaemia, requiring urgent medical intervention.'
- complication/hyperosmolar-hyperglycaemic-state: mondoCode: 'MONDO:0005117' vs 'MONDO:0019205'
- complication/hyperosmolar-hyperglycaemic-state: definition: 'The Hyperosmolar Hyperglycaemic State (HHS) is a medical emergency. It occurs much less frequently than the other hyperglycaemic emergency, diabetic ketoacidosis (DKA), and its treatment requires a different approach.' vs 'A severe hyperglycaemic condition characterized by significant hyperosmolality, dehydration, and altered mental status, often without significant ketonemia, typically occurring in patients with type 2 diabetes.'
- complication/cerebral-oedema: mondoCode: 'MONDO:0005118' vs 'MONDO:0005201'
- complication/cerebral-oedema: definition: 'Neurological complications, such as cerebral oedema and central pontine myelinolysis (CPM) / osmotic demyelination syndrome are uncommon but can be seen as a complication of the rapid changes in osmolality during treatment of HHS (5; 6).' vs 'assessment of complications of treatment e.g. fluid overload, cerebral oedema or CPM / osmotic demyelination syndrome (as indicated by a deteriorating conscious level) must be undertaken frequently (every 1-2 hours).'

## 悬空关系样例

- `cerebral-oedema` --presentsWith--> `Hyperosmolar Hyperglycaemic State`（未找到）
- `cerebral-oedema` --presentsWith--> `Hyperosmolar Hyperglycaemic State`（未找到）
- `cerebral-oedema` --presentsWith--> `Hyperosmolar Hyperglycaemic State`（未找到）
- `cerebral-oedema` --presentsWith--> `Hyperosmolar Hyperglycemic State`（未找到）
- `cerebral-oedema` --presentsWith--> `HHS`（未找到）
- `cerebral-oedema` --presentsWith--> `Hyperosmolar Hyperglycaemic State`（未找到）
- `central-pontine-myelinolysis` --presentsWith--> `Hyperosmolar Hyperglycaemic State`（未找到）
- `central-pontine-myelinolysis` --presentsWith--> `Hyperosmolar Hyperglycaemic State`（未找到）
- `osmotic-demyelination-syndrome` --presentsWith--> `Hyperosmolar Hyperglycaemic State`（未找到）
- `osmotic-demyelination-syndrome` --presentsWith--> `Hyperosmolar Hyperglycaemic State`（未找到）
- `osmotic-demyelination-syndrome` --presentsWith--> `Hyperosmolar Hyperglycaemic State`（未找到）
- `myocardial-infarction` --presentsWith--> `Hyperosmolar Hyperglycaemic State`（未找到）
- `stroke` --presentsWith--> `Hyperosmolar Hyperglycaemic State`（未找到）
- `peripheral-arterial-thrombosis` --presentsWith--> `Hyperosmolar Hyperglycaemic State`（未找到）
- `serum-osmolality` --hasThreshold--> `Rate of fall of serum osmolality`（未找到）
- `fluid-overload` --presentsWith--> `Hyperosmolar Hyperglycaemic State`（未找到）
- `fluid-overload` --presentsWith--> `Hyperosmolar Hyperglycemic State`（未找到）
- `only-commence-insulin-infusion-quickly-in-the-following-circumstances` --definesTarget--> `HHS and ketonaemia (blood ketones 3ß-hydroxybutyrate >1.0 - ≤3.0 mmol/L or urine ketones < 2+) and not acidotic (venous pH >7.3 and bicarbonate >15.0 mmol/L)`（未找到）
- `only-commence-insulin-infusion-quickly-in-the-following-circumstances` --definesTarget--> `significant ketonaemia (3ß-hydroxybutyrate >3.0 mmol/L) or ketonuria (≥ 2+) with a pH <7.3 and bicarbonate <15 mmol/L (i.e. mixed DKA and HHS)`（未找到）
- `foot-ulceration` --presentsWith--> `Hyperosmolar Hyperglycaemic State`（未找到）
