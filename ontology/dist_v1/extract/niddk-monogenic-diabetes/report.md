# 抽取质量报告 — niddk-monogenic-diabetes

- 源文件：`ontology/knowledges/niddk-monogenic-diabetes.txt`（sha256 `2ac3b612770c…`）
- 目标图：`urn:dmo:extract:niddk-monogenic-diabetes`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：3

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **80.4%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 51.6% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 20.0% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 1.05 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 51 |
| 通过校验 | 41 |
| 丢弃 | 10 |
| 消解后实体 | 39 |
| 关系边 | 44 |
| 悬空关系 | 11 |
| 合并冲突 | 16 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_too_short` | 5 |
| `quote_not_found` | 5 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| riskFactor | 8 |
| diabetesType | 7 |
| complication | 7 |
| recommendation | 7 |
| drugClass | 3 |
| medication | 3 |
| symptom | 2 |
| labTest | 2 |

## 合并冲突样例

- diabetesType/monogenic-diabetes: name: 'Monogenic Diabetes' vs 'monogenic diabetes'
- diabetesType/monogenic-diabetes: definition: 'Monogenic diabetes is a group of uncommon forms of diabetes that are caused by a variant NIH external link, or change, in a single gene.' vs 'Monogenic diabetes is a form of diabetes caused by mutations in a single gene.'
- symptom/feeling-very-hungry-even-after-eating: name: 'Feeling Very Hungry Even After Eating' vs 'feeling very hungry, even after you have eaten'
- symptom/numbness-or-tingling-in-the-feet-or-hands: name: 'Numbness or Tingling in the Feet or Hands' vs 'numbness or tingling in the feet or hands'
- riskFactor/family-history-of-diabetes: name: 'Family History of Diabetes' vs '家族糖尿病史'
- riskFactor/autosomal-dominant-inheritance: name: 'Autosomal Dominant Inheritance' vs '常染色体显性遗传'
- riskFactor/gene-variant-in-a-single-gene: name: 'Gene Variant in a Single Gene' vs '单个基因变异'
- diabetesType/mody: definition: 'Most people with MODY forms of diabetes have inherited a gene for the disease from a parent who also had the disease.' vs 'MODY is a form of monogenic diabetes that typically presents in adolescence and is caused by mutations in specific genes such as HNF1A, HNF4A, and GCK.'
- riskFactor/autosomal-dominant-inheritance-of-monogenic-diabetes: name: 'Autosomal Dominant Inheritance of Monogenic Diabetes' vs 'autosomal dominant inheritance of monogenic diabetes'
- riskFactor/autosomal-recessive-inheritance-of-monogenic-diabetes: name: 'Autosomal Recessive Inheritance of Monogenic Diabetes' vs 'autosomal recessive inheritance of monogenic diabetes'
- riskFactor/family-history-of-monogenic-diabetes: name: 'Family History of Monogenic Diabetes' vs 'family history of monogenic diabetes'
- riskFactor/young-age-at-onset-of-diabetes: name: 'Young Age at Onset of Diabetes' vs 'young age at onset of diabetes'
- riskFactor/absence-of-overweight-or-obesity-in-diabetes-patients: name: 'Absence of Overweight or Obesity in Diabetes Patients' vs 'absence of overweight or obesity in diabetes patients'
- drugClass/sulfonylureas: name: 'Sulfonylureas' vs 'sulfonylureas'
- drugClass/insulin: name: 'Insulin' vs 'insulin'
- drugClass/glucagon-like-peptide-1-receptor-agonists: name: 'Glucagon-Like Peptide-1 Receptor Agonists' vs 'glucagon-like peptide-1 receptor (GLP-1) agonists'

## 悬空关系样例

- `monogenic-diabetes` --predisposesTo--> `Type 1 Diabetes`（未找到）
- `monogenic-diabetes` --predisposesTo--> `Type 2 Diabetes`（未找到）
- `maturity-onset-diabetes-of-the-young-mody` --predisposesTo--> `Monogenic Diabetes`（未找到）
- `neonatal-diabetes-mellitus-ndm` --predisposesTo--> `Monogenic Diabetes`（未找到）
- `family-history-of-diabetes` --increasesRiskOf--> `Maturity-Onset Diabetes of the Young`（未找到）
- `autosomal-dominant-inheritance` --increasesRiskOf--> `Maturity-Onset Diabetes of the Young`（未找到）
- `autosomal-dominant-inheritance` --increasesRiskOf--> `Neonatal Diabetes Mellitus`（未找到）
- `mody` --predisposesTo--> `monogenic diabetes`（未找到）
- `mody` --predisposesTo--> `monogenic diabetes`（未找到）
- `ndm` --predisposesTo--> `monogenic diabetes`（未找到）
- `use-of-glp-1-agonists-for-monogenic-diabetes` --recommendsDrugClass--> `GLP-1 agonists`（未找到）
