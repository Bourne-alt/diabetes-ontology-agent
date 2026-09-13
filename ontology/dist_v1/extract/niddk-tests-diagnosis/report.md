# 抽取质量报告 — niddk-tests-diagnosis

- 源文件：`ontology/knowledges/niddk-tests-diagnosis.txt`（sha256 `122009a36c70…`）
- 目标图：`urn:dmo:extract:niddk-tests-diagnosis`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：2

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **92.3%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 48.4% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 10.9% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.02 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 52 |
| 通过校验 | 48 |
| 丢弃 | 4 |
| 消解后实体 | 47 |
| 关系边 | 41 |
| 悬空关系 | 5 |
| 合并冲突 | 12 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 3 |
| `quote_too_short` | 1 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 18 |
| labTest | 8 |
| diabetesType | 5 |
| riskFactor | 5 |
| contraindication | 4 |
| monitoringSchedule | 4 |
| symptom | 3 |

## 合并冲突样例

- diabetesType/gestational-diabetes: definition: 'All pregnant women who do not have a previous diagnosis of diabetes should be tested for gestational diabetes between 24 and 28 weeks of pregnancy.' vs 'If you are pregnant, your doctor might test you for gestational diabetes with the glucose challenge test.'
- symptom/feeling-thirsty: name: 'Feeling Thirsty' vs 'feeling thirsty'
- symptom/having-to-urinate-more-often: name: 'Having to Urinate More Often' vs 'having to urinate more often'
- symptom/diabetic-ketoacidosis: name: 'Diabetic Ketoacidosis' vs 'diabetic ketoacidosis'
- riskFactor/age-35-or-older: name: 'Age 35 or Older' vs 'age 35 or older'
- riskFactor/overweight-or-have-obesity-and-have-at-least-one-other-risk-factor: name: 'Overweight or Have Obesity and Have at Least One Other Risk Factor' vs 'overweight or have obesity and have at least one other risk factor'
- riskFactor/a-woman-who-had-gestational-diabetes: name: 'A Woman Who Had Gestational Diabetes' vs 'a woman who had gestational diabetes'
- riskFactor/a-parent-who-had-diabetes-while-pregnant: name: 'A Parent Who Had Diabetes While Pregnant' vs 'a parent who had diabetes while pregnant'
- monitoringSchedule/adults-and-children-with-normal-diabetes-test-results-should-be-retested-every-3-years: name: 'Adults and children with normal diabetes test results should be retested every 3 years' vs 'Retesting for diabetes in individuals with normal results'
- monitoringSchedule/adults-and-children-diagnosed-with-prediabetes-should-be-tested-for-type-2-diabetes-every-year: name: 'Adults and children diagnosed with prediabetes should be tested for type 2 diabetes every year' vs 'Annual testing for type 2 diabetes in individuals diagnosed with prediabetes'
- monitoringSchedule/all-pregnant-women-who-do-not-have-a-previous-diagnosis-of-diabetes-should-be-tested-for-gestational-diabetes-between-24-and-28-weeks-of-pregnancy: name: 'All pregnant women who do not have a previous diagnosis of diabetes should be tested for gestational diabetes between 24 and 28 weeks of pregnancy' vs 'Gestational diabetes screening in pregnant women'
- monitoringSchedule/if-you-have-gestational-diabetes-you-should-get-tested-after-your-baby-is-born-to-see-if-you-have-type-2-diabetes-usually-within-12-weeks-after-delivery: name: 'If you have gestational diabetes, you should get tested after your baby is born to see if you have type 2 diabetes, usually within 12 weeks after delivery' vs 'Postpartum testing for type 2 diabetes in women with gestational diabetes'

## 悬空关系样例

- `prediabetes` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `oral-glucose-tolerance-test` --hasThreshold--> `Oral Glucose Tolerance Test-2h`（未找到）
- `follow-up-ogtt-after-abnormal-glucose-challenge-test` --appliesToType--> `Glucose Challenge Test for Gestational Diabetes Screening`（未找到）
- `use-of-ogtt-for-gestational-diabetes-diagnosis` --appliesToType--> `Oral Glucose Tolerance Test for Type 2 and Gestational Diabetes Detection`（未找到）
- `autoantibody-testing-for-type-1-diabetes-risk-assessment-in-relatives` --appliesToType--> `Autoantibody Testing for Type 1 Diabetes Identification`（未找到）
