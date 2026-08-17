# 患者关系库 × 糖尿病本体图谱 融合方案

> 本文是 [`RELATIONAL-GRAPH-INTEGRATION-PLAN.md`](./RELATIONAL-GRAPH-INTEGRATION-PLAN.md) 落到真实数据库
> （`hospital_zd` @124.223.18.44:5000，schema `patient_analysis`）之后的**修正版**，
> 不是另起炉灶。原计划的架构决策（PG 为患者事实来源、每患者一命名图、内容哈希幂等 PUT、
> 查询边界）全部保留；被真实数据推翻的三处修正见「架构」一节。
>
> 调研日期：2026-08-13。

## Context

`ontology/` 下的糖尿病语义层已建完（TBox + 17 条诊断阈值 + SHACL + 抽取产物，GraphDB `dmo` 仓库 6479 三元组），但它只有 6 例手写合成患者，**从未接过真实患者库**。`docs/RELATIONAL-GRAPH-INTEGRATION-PLAN.md` 写了一份 304 行的设计，零代码落地：`src/dmo/` 包不存在，`pyproject.toml` 里 `dmo = "dmo.cli:main"` 是空入口，psycopg/SQLAlchemy 都没装。

本次要把 `hospital_zd` 的 `patient_analysis` 接进来，做到"根据需求在语义层和数据库中探索准确答案"。约束：**原有数据一行不改**，演示数据可新增。

### 调研结论：上游数据质量决定了方案形态

实测 `patient_analysis`（400 门诊 + 120 住院），糖尿病相关部分基本不可用：

| 问题 | 实测证据 |
|---|---|
| 队列极小 | 只有 **15 个 E11**，无 E10/E13、无 O24 妊娠糖尿病 |
| **主子表语义错位** | `ITEM14 糖化血红蛋白` 的 4 个子项是「血小板/AST/尿蛋白/尿素氮」；`ITEM15 尿微量白蛋白` 的子项是「总胆固醇/尿素氮/血小板/AST」 |
| **全库无 HbA1c 数值** | 子项名只有 12 种，不含糖化血红蛋白 |
| 数值是随机数 | 血小板 15.3（参考范围 100-300）却标"正常"；尿蛋白 9.5（参考范围"阴性"） |
| 无单位列 | `cdr_lis_result` 没有 unit；血糖参考范围 3.9-6.1 ⟹ mmol/L，而本体阈值是 mg/dL |
| 用药不相关 | 15 个 E11 患者里只有 1 人用二甲双胍，其余是阿莫西林/奥美拉唑/布洛芬。全库唯一降糖药就是二甲双胍 |
| 无纵向随访 | 每个 E11 患者只有 1 次检验、4 条结果 |

`semantic_link` schema 里已有一次**失败的前人尝试**（2026-07-17，wfs 项目，命名空间 `https://example.org/wfs/`）：纯字符串名称匹配，把「尿蛋白 10.4」同时链到"1型糖尿病的糖尿病肾病"和"2型糖尿病的糖尿病肾病"，confidence 都写 0.9，无单位、无阈值、无出处。**它是本方案最好的对照组**，保留只读不动。

`decision_support`（8000 患者 / 70111 条带单位的检验）**不接入**：patient_id 格式不同（P000001 vs P00001）、与 `patient_analysis` 无任何关联、值同样随机（RBC 8.99 g/L）。

### 三个必须先修的仓库现状

| # | 问题 | 证据 |
|---|---|---|
| C1 | **`ontology/data/` 目录已从工作区删除** | `git status` = `AD`；`load_graphdb.py:44` 仍引用它，靠 `.exists()` 静默跳过 —— GraphDB 里 `urn:dmo:data` 那 77 条是上次装载的残留 |
| C2 | **GraphDB 里的 TBox 是 V1** | `build_tbox.py:30` `DEFAULT_SRC` 指向 V1；实测 tbox 图里 `dmo:Assessment/Diagnosis/MedicationUse/ClinicalObservation/SourcePassage` **一个都没有**，只有 `Patient`/`LabResult` |
| C3 | `ontology/dist/tbox-generated.ttl` 与 `sources.ttl` 不在磁盘 | 需先跑 `build_tbox.py` + `source_registry.py` |

### 已定决策

1. **直接切 V2，重写下游**（不做 V1/V2 桥接兼容层）
2. 交付形态：**CLI + FastAPI 服务**
3. 节奏：**先最小闭环（3 场景）再铺开**

---

## 架构

```
┌─ PostgreSQL @124.223.18.44:5000/hospital_zd ────────────────────┐
│ patient_analysis.*   【L0 原始 · 只读 · 一行不改】                │
│ semantic_link.*      【前人方案 · 只读 · 对照组】                 │
│        │ 会话级 READ ONLY                                        │
│        ▼                                                         │
│ dmo_src.v_*     视图  【L1 规范化投影】= 原表 UNION ALL ext_*     │
│ dmo_src.ext_*   表    【L2 演示队列 · 结构与原表逐字一致】         │
│ dmo_map.*       表    【术语对齐 · 中文名/ICD10/药名 → dmo IRI】   │
│        │ dmo project run（ETL：单位换算 + 术语解析 + 可信度打标）  │
│        ▼                                                         │
│ dmo_core.*      表    【L3 V2 care-chain 快照 · 唯一同步来源】     │
│                       每行带 source_table/source_pk/fact_origin  │
└────────────────┬─────────────────────────────────────────────────┘
                 │ dmo sync（内容哈希 → GSP PUT 整图替换）
                 ▼
┌─ GraphDB @localhost:7200/dmo ───────────────────────────────────┐
│ urn:dmo:tbox / seed / sources / extract:*  【知识层 · 静态】      │
│ urn:dmo:patient:{uuid}                     【每患者一图】         │
│ urn:dmo:inferred  ← rules/*.rq CONSTRUCT   【整图替换】           │
└────────────────┬─────────────────────────────────────────────────┘
                 ▼
   src/dmo/query/hybrid.py → agent tools → dmo ask / FastAPI
   返回 { assertedFacts | inferredFacts | sources | unmapped }
```

**职责边界**：SQL 管患者事实、计数、排序、分页、术语映射状态；GraphDB 管 TBox、阈值、推理、provenance；**SPARQL 只做区间比较，单位换算一律在 ETL 做**（换算系数是 analyte-specific 的，葡萄糖 ×18.0182、肌酐 ÷88.4，写进 SPARQL 必错）；SHACL 管 RDF 结构与安全约束。

**对原计划的三处修正**：

| 原计划 | 改为 | 理由 |
|---|---|---|
| IRI `https://example.org/dmo/patient/{uuid}` | `https://example.org/dmo/id/patient/{uuid}` | 与 `source_registry.py:89`、seed TTL 的 `dmo/id/` 保持一套 |
| SQLAlchemy 2 + Alembic | **psycopg 3 + 编号 `.sql` + `dmo_core.schema_migration`** | schema 我们独占、无 ORM 需求，ORM 会让 schema 有两份定义 |
| 迁移 `synthetic-patients.ttl` 为 SQL seed | **留作 SHACL 夹具**，SQL 侧另建演示队列 | P001-P006 是 shape 的反例夹具，混进患者链路会污染 |

---

## 一、「不动原数据」的三道锁

1. **会话级只读** — `src/dmo/db/engine.py` 两个连接工厂：`readonly_conn()` 连上立刻 `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY`，读 `patient_analysis` 的代码只能拿这个；`write_conn()` 仅用于 `dmo_src`/`dmo_map`/`dmo_core`。
2. **语句守卫** — `write_conn()` 执行前校验目标 schema ∈ `{dmo_src, dmo_map, dmo_core}`，否则抛异常。配单测：对 `patient_analysis.patient_basic_info` 做 UPDATE 必须失败。
3. **基线校验** — R0 时对 12 张关键表算行数 + `md5(string_agg(...))` 存进 `dmo_core.upstream_baseline`；每次 `dmo project run` 前重算比对，不一致直接拒跑。

### 三层事实的来源标识

```sql
-- dmo_src/ddl/003_ext_tables.sql
CREATE TABLE dmo_src.ext_diagnose_query
  (LIKE patient_analysis.diagnose_query INCLUDING DEFAULTS);
ALTER TABLE dmo_src.ext_diagnose_query
  ADD COLUMN demo_scenario text NOT NULL, ADD COLUMN demo_note text;

CREATE VIEW dmo_src.v_diagnosis AS
  SELECT 'ehr-legacy'::text AS src_origin, NULL::text AS demo_scenario, *
    FROM patient_analysis.diagnose_query
UNION ALL
  SELECT 'demo-cohort', demo_scenario, <原表同名列…>
    FROM dmo_src.ext_diagnose_query;
```

单位侧表 `dmo_src.ext_lab_unit(testcode, itemcode, unit)` —— **刻意不给 `ext_cdr_lis_result` 加单位列**，因为原表没有，加了就破坏「结构逐字一致」。

一路带到 RDF：`dmo:factOrigin ∈ {ehr-legacy, derived, demo-cohort}`、`dmo:demoScenario`、`prov:wasDerivedFrom <urn:pg:patient_analysis.cdr_lis_result#TESTxxx>`。

### 原始随机检验值：分级准入

| 上游内容 | 处置 |
|---|---|
| 人口学、挂号、`diagnose_query` ICD10、`op_order_query` 药名 | **进，trust=`Attested`**（ICD10 是真编码，「二甲双胍」是真药名） |
| `cdr_lis_detail.itemname`（大项 ITEM01-15） | **完全丢弃不映射** —— 大项名是纯噪声，映射它等于主动制造错误 |
| `cdr_lis_result.itemname`（12 种子项） | **唯一的 analyte 来源**，进 |
| `cdr_lis_result.inspectionresult` 数值 | **进，强制 trust=`Unverified`** |
| `resultstateclass`（正常/偏高/偏低） | 进为 `ClinicalObservation`，**不进 `Assessment`** —— 上游判读与我们的阈值判定必须物理隔离 |

`Unverified` 的实际效力（不是打个标就完事）：
1. `20-lab-assessment.rq` 硬门禁 `FILTER NOT EXISTS { ?res dmo:valueTrustLevel "Unverified" }`，**默认永不参与阈值判定**；
2. `dmo sync all --include-unreliable` 可放行，走 `20b-*.rq`，结论强制 `Indeterminate` + `dmo:caveat`；
3. 查询层：回答含 Unverified 事实时强制插入 `dataQualityNotice`。

**「全库无 HbA1c」不假装有**：`lab_term_map` 里 A1C 一行 `verify_status='no-source-data'`，`explain_gap()` 工具如实回答缺口。这种"知道自己不知道"正是有本体相对于字符串匹配的核心卖点。

---

## 二、切 V2 要重写的下游（本体侧，纯本地，不碰 PG）

V2 相对 V1 丢了三样东西，必须补：

### 2.1 回填 `tbox.route`（**必做，否则双轨制失效**）

V1 有 9 处 route 标注，V2 **一处都没有**。不补的话 `build_tbox.py:65` 会把所有类型退化成 `individual`，punning 与 SKOS 全废，`dmo-axioms.ttl` 的 `equivalentClass`（`DiabetesPatient ≡ Patient ⊓ ∃hasDiabetesType.Diabetes`）直接失效。

改 `ontology/graph/diabetes-ontology-v2.json`，把 V1 的 9 条原样搬入，5 个新事件实体标 `individual`：

```
class: diabetesType, complication, complicationStage
skos:  labTest, symptom, riskFactor, drugClass, lifestyleIntervention, device
individual: clinicalObservation, diagnosis, assessment, medicationUse, sourcePassage
```

### 2.2 阈值属性从 `inclusive` 改 `operator`，`citation` 改 `SourcePassage`

V2 的 `diagnosticThreshold` 属性是 `lowerOperator`/`upperOperator`（GT/GTE/None）+ `confirmationRequired`，**删掉了 `citation`**，改用 `thresholdCitesPassage → SourcePassage{passageId, locator, quote, contentHash}`。

改 `ontology/src/dmo-threshold-seed.ttl`（17 条阈值，机械转换）：

```turtle
# 旧（V1）                          # 新（V2）
dmo:lowerBound 6.5 ;                dmo:lowerBound 6.5 ;
dmo:lowerInclusive true ;    →      dmo:lowerOperator "GTE" ;
dmo:citation "6.5% or above" ;      dmo:confirmationRequired true ;
                                    dmo:thresholdCitesPassage dmosp:A1C-DIABETES-Q1 .

dmosp:A1C-DIABETES-Q1 a dmo:SourcePassage ;
    dmo:passageId "A1C-DIABETES-Q1" ; dmo:locator "诊断表" ;
    dmo:quote "6.5% or above" ;
    dmo:contentHash "<sha256 of quote>" .
```

同时补：
- **`confirmationRequired`**：A1C/FPG/OGTT2H/RPG 的 `-DIABETES` 四条置 `true`，其余全 `false`。这是 S02「单次异常 ≠ 确诊」的数据基础。
- **10 个「有概念、无阈值」的 LabTest**：肌酐/血小板/甘油三酯/血红蛋白/AST/ALT/白细胞/TSH/总胆固醇/尿素氮。带 `skos:altLabel` 中文名供映射命中，但**刻意不挂 `dmo:hasThreshold`**：

```turtle
dmoid:LabTest-CREATININE a dmo:LabTest, skos:Concept ;
    dmo:labTestCode "CREAT" ; rdfs:label "Serum Creatinine" ;
    skos:altLabel "肌酐", "creatinine" ; dmo:unitOfMeasure "mg-per-dL" ;
    rdfs:comment "⚠️ 刻意不挂 hasThreshold：本仓库语料未收录肌酐的诊断切点。
                  能识别 ≠ 能判定。" .
```

**这是术语层最重要的设计**：`20-lab-assessment.rq` 对这些项自然返回零结果，不需要任何黑名单。对比 `semantic_link`（尿蛋白 10.4 → 糖尿病肾病 0.9），差别一目了然。

### 2.3 V2 缺的、本方案要加的 schema 元素

改 `diabetes-ontology-v2.json`，新增：

| 元素 | 类型 | 用途 |
|---|---|---|
| `hasAssessment` | Patient→Assessment, one-to-many | V2 里 Assessment 到 Patient 要走 4 跳（`basedOnLabResult`→`producesLabResult`→`hasEncounter`），查询极难写 |
| `valueTrustLevel` | LabResult/ClinicalObservation, enum `Attested/Curated/Unverified` | 可信度门禁 |
| `factOrigin` | 患者事实实体, enum `ehr-legacy/derived/demo-cohort` | 三层来源 |
| `sourceValue`/`sourceUnit` | LabResult | 单位换算前的原始值 |
| `caveat` | Assessment/Diagnosis | 「单次异常不等于确诊」 |
| `demoScenario` | Patient | 演示场景编号 |

### 2.4 重写 SHACL 与验收查询

| 文件 | 改法 |
|---|---|
| `ontology/shapes/clinical-safety.shacl.ttl` | 五跳换 V2 七跳：`Patient -hasMedicationUse-> MedicationUse -usesMedication-> Medication -belongsToDrugClass-> DrugClass -hasContraindication-> Contraindication[severity="Absolute"] -triggeredByCondition-> ?cond`，且 `Patient -hasDiagnosis-> Diagnosis[clinicalStatus="Active"] -diagnosisComplication-> ?cond` |
| `ontology/shapes/data-quality.shacl.ttl` | ① `DiagnosticThresholdShape` 的 `citation minCount 1` → `thresholdCitesPassage minCount 1`；② 上下界互斥检查改用 `lowerOperator/upperOperator`；③ `PatientShape` 的 `hasDiabetesType maxCount 1` → SPARQL 约束：至多一条 `verificationStatus="Confirmed"` 且 `diagnosisKind="Diabetes"` 的 Diagnosis 指向不同 `diagnosisType` |
| `ontology/data/synthetic-patients.ttl` | **先恢复**（`git show :ontology/data/synthetic-patients.ttl > …`），再改写为 V2：`hasDiabetesType`→`hasDiagnosis/diagnosisType`、`hasComplication`→`hasDiagnosis/diagnosisComplication`、`takesMedication`→`hasMedicationUse/usesMedication`、`bmi/isPregnant/smokingStatus`→`ClinicalObservation`。6 例的**刻意违规点必须原样保留**（P005 缺单位、P006 单位不一致、P001 触发禁忌、P002 反例不触发） |
| `ontology/tools/load_graphdb.py` | ① `DEFAULT_SRC` 侧的 `GRAPH_SOURCES` 缺文件时改成**显式 WARN** 而非静默跳过（C1 的根因）；② `CHECKS`（:219-277）的 S6 禁忌查询改 V2 谓词；③ 新增 3 条患者图检查 |
| `ontology/tools/build_tbox.py:30` | `DEFAULT_SRC` → `diabetes-ontology-v2.json` |
| `ontology/tools/validate_shacl.py:16-22` | `DATA` 增加 `ontology/dist/patients/*.ttl`（同步管线本地导出，供 CI 无 GraphDB 时体检） |
| `ontology/rules/align-extracted.rq` | 重命名 `10-align-extracted.rq`（`run_rules` 是 `sorted(glob)`，靠数字前缀定序） |

**⚠️ 唯一的强一致性风险**：`build_tbox.py:205` 把 `many-to-one` 编译成 `owl:FunctionalProperty`。V2 的 `diagnosisType` 是 many-to-one，若一条 Diagnosis 被赋两个 `diagnosisType`，owl2-rl 会推出两个分型 `owl:sameAs`，与 `dmo-axioms.ttl:76` 的 `AllDisjointClasses` 冲突，**整个本体不一致且不报错**（与 §2.5 hasKey 事故同款机制）。ETL 侧强制一条 Diagnosis 至多一个 `diagnosisType`；`load_graphdb.py` 的「Prediabetes ⋢ Diabetes」反例查询作哨兵，每次 `--verify` 都跑。

---

## 三、术语对齐层 `dmo_map`

五张表（`src/dmo/db/ddl/004_dmo_map.sql`）：

- **`concept_ref`** — `iri PK, concept_kind, code, label, alt_labels[], unit_canonical, graph_version` — 从 GraphDB SPARQL 拉，`dmo map sync-concepts` 幂等重建。`graph_version` 存 tbox 内容哈希，防止映射指向已删概念。
- **`lab_term_map`** — 核心。`src_name`（'血糖'）, `src_ref_range`（'3.9-6.1'，单位推断的唯一线索）, `concept_iri`, `unit_src`/`unit_target`/`conv_factor`/`conv_offset`, `value_kind ∈ {quantitative, qualitative, unusable}`, `trust_default`, `verify_status ∈ {verified, candidate, rejected, unmappable, no-source-data}`, `verified_by/at`。
- **`icd10_map`** — `icd10code PK → concept_iri, concept_kind ∈ {DiabetesType, Complication, Comorbidity}`。
- **`drug_term_map`** — `src_name PK → medication_iri, drug_class_iri, is_antidiabetic`。
- **`unmapped_term`** — 未命中只记账，**绝不猜**。

### 单位换算三条硬规则

1. 换算只在 ETL（`src/dmo/terms/units.py`）做，SPARQL 里一次都不做。进 GraphDB 的 `dmo:resultUnit` 一律已是 `concept_ref.unit_canonical`。
2. 原始值必须保留：`dmo:sourceValue`/`dmo:sourceUnit` 一并写入。演示时当场展示「7.8 mmol/L → 140.5 mg/dL，不换算会被误判 Normal」。
3. **单位推断不出来就不换算**。原库无单位列，只能从 `inspectionresultrange` 反推（血糖 `3.9-6.1` ⟹ mmol/L）。推不出的（尿蛋白参考范围"阴性"）标 `qualitative` + `unmappable`，该项**永不进 LabResult**，只进 `ClinicalObservation(valueText)`。
   ⚠️ 这是**推断不是断言**，`verify_status` 必须人工置 `verified` 才生效。

### 对 `semantic_link` 的处置

**不迁移、不复用、不修改。** 理由：命名空间是 `https://example.org/wfs/`（URL 编码中文），与 `https://example.org/dmo#` 不是一套；89 行全部 `verified=false`；`relation` 与 `disease_iri` 混在一张表，粒度不对应。

只做一次性候选种子导入，**刻意丢弃它的 IRI**：`dmo map import-wfs --as-candidate` 读它（只读）取 `analyte_norm` 去重，写 `lab_term_map` 时 `concept_iri=NULL, verify_status='candidate'`，输出待人工填 IRI 的清单。

它同时是**演示对照组**（Q5）。

### 未命中行为

```
verified                        → 正常映射
candidate / rejected            → 跳过 + 计数
unmappable / no-source-data     → 跳过 + 记入返回体 unmapped[]
完全未命中                       → UPSERT unmapped_term，跳过 + 计数
```

`dmo sync` 遇未映射概念**拒发不完整 RDF**（沿用原计划失败策略）。

---

## 四、演示队列

**ID**：`P90001`–`P90030`，与现有 `P00001`–`P00400` 同格式，数值段不冲突。
**UUID**：不存种子表，用确定性派生 —— `src/dmo/rdf/iri.py`:

```python
DMO_NS = uuid.uuid5(uuid.NAMESPACE_URL, "https://example.org/dmo/id/patient/")
def patient_uuid(patientid: str) -> uuid.UUID:  return uuid.uuid5(DMO_NS, patientid)
```

`P90002` → 永远同一 UUID → 同一 IRI 与命名图，测试可重放。原始 400 个患者用同一函数。

**锚点策略混合**：
- **A 组（6 例）**：从现有 15 个 E11 患者里选，**不改任何原行**，只在 `ext_*` 里追加规范检验/用药/随访。演示价值：*"同一患者，原库 4 条随机检验判不出任何东西；补 3 条规范检验后，本体链路立刻给出带出处的结论。"*
- **B 组**：`P90001+` 全新，覆盖原库结构上造不出的场景（妊娠、SGLT2i、肾衰竭、低血糖）。

### 最小闭环三场景（R4 只造这 3 个）

| # | 场景 | 患者 | 数据 | 验证 |
|---|---|---|---|---|
| **S02** | A1C 命中糖尿病·**单次** | P90002 | A1C 7.4%（1 次） | `confirmationRequired=true` ⟹ Diagnosis `verificationStatus="Provisional"`，**不是** Confirmed |
| **S07** | 绝对禁忌触发 | P90008 | ESRD/透析 + 恩格列净 | `clinical-safety.shacl` Violation，带出处原文 |
| **S08** | 安全反例（不应误报） | P90009 | ESRD + 二甲双胍 | **零违规**。语料对二甲双胍无绝对禁忌，补 eGFR<30 = 编造出处 |

### R8 铺开的剩余场景

S01 正常 / S03 复测确诊（多 LabResult 支撑一次 Assessment）/ S04 妊娠 GCT1H 142 + S04b 非妊娠同值对照 / S05 DKD + CKD-G4 分期 / S06 MedicationUse 关联多 Diagnosis / S09 前期 / S10 低血糖开区间 / S11 单位陷阱（7.8 mmol/L）/ S12 缺单位 / S13 未分型 ⟹ `DM-Unspecified` / S14 纵向随访 A1C 8.9→7.6→6.8 / S15 类型冲突 E10+E11 / S16 开闭区间边界 5.7/6.4/6.5。

**落地**：`dmo_src/seed/cohort_*.csv`（patient/encounter/diagnosis/lab/medication/observation，人可读可 diff），`dmo db seed` 幂等 UPSERT 进 `ext_*`。

---

## 五、`src/dmo/` 包结构（全部新建）

```
src/dmo/
├─ cli.py            argparse 子命令树，pyproject 的 dmo 入口
├─ config.py         DMO_DATABASE_URL / DMO_GRAPHDB_ENDPOINT / DMO_GRAPHDB_REPOSITORY
│                    兼容读现有 .env 的 PG_DSN / GRAPHDB_SPARQL_ENDPOINT
├─ api.py            FastAPI 应用（R7）
├─ db/  engine.py(只读+守卫) migrate.py baseline.py cohort.py projection.py ddl/*.sql
├─ terms/ concepts.py resolve.py units.py
├─ rdf/  iri.py emit.py canonical.py sync.py
├─ graph/ client.py rules.py
├─ query/ templates.py hybrid.py
└─ agent/ tools.py loop.py prompts.py trace.py
```

`dmo_core` **先建 7 张核心表**：`patient / clinical_encounter / lab_result / clinical_observation / diagnosis / medication_use / rdf_sync_state` + `schema_migration` + `upstream_baseline`。原计划的 `patient_risk_factor`/`device_use`/`intervention` **推迟** —— 真实库这三类数据一条都没有，建了是空表。

### 复用 `load_graphdb.py`（抽公共层，不复制粘贴）

把下列函数移到**新建**的 `ontology/tools/graphdb_http.py`，`load_graphdb.py` 改为 import：

| 函数 | 行号 | 用途 |
|---|---|---|
| `request()` | 101-111 | 纯 stdlib，`URLError` 已给出人话报错 |
| `put_graph()` | 142-156 | **患者图同步直接用**，走完全相同的 GSP PUT |
| `sparql()` | 159-170 | 拉 concept_ref、跑 CONSTRUCT、查询层 |
| `repo_exists()` | 114-120 | `dmo graph status` |
| `merge()` | 187-193 | 多文件合并再 PUT |

`src/dmo/graph/client.py` 只做薄封装：超时可配、错误抛异常而非 `SystemExit`（便于 `sync all` 单患者失败继续）。

### 幂等

```python
# rdf/canonical.py
lines = sorted(l for l in g.serialize(format="nt").splitlines() if l.strip())
return hashlib.sha256("\n".join(lines).encode()).hexdigest()
```

**患者图内一个空节点都不许有** —— 有 bnode 则 skolem ID 每次不同，哈希永不稳定。`emit.py` 出口加断言 + 单测。

流程沿用原计划阶段 4：一致性快照 → 规范排序 → SHA-256 → 比对 `rdf_sync_state.content_hash` → 不同才 PUT → 失败保留旧哈希 → `sync all` 汇总，有失败非零退出 → `--prune` 只删已登记但 SQL 中已不存在的 `urn:dmo:patient:*`。

**日志脱敏**：`patient_basic_info.name` / `idenno` **不进 `dmo_core`、不进 RDF、不进日志**，只保留 `patientid` 作假名。

### CLI

```bash
dmo db status | migrate | seed | guard-test | baseline [--check]
dmo map sync-concepts | import-wfs | list-unmapped | verify --id N --iri …
dmo project run [--patient P90002] [--no-unit-conversion]
dmo sync patient --patient P90002 | sync all [--prune] [--include-unreliable]
dmo graph status | load | rules | verify
dmo query <template> --param k=v
dmo ask "…"
dmo demo compare --scenario S11
dmo serve --port 8100          # FastAPI
```

---

## 六、阈值判定规则（`ontology/rules/`，数字前缀定序）

| 文件 | 作用 |
|---|---|
| `10-align-extracted.rq` | 重命名自 `align-extracted.rq`，内容不改 |
| `20-lab-assessment.rq` | **新** LabResult × DiagnosticThreshold → Assessment |
| `20b-lab-assessment-unreliable.rq` | **新** `Unverified` 变体，结论强制 Indeterminate + caveat |
| `21-target-attainment.rq` | **新** 最新 A1C × `dmotgt:A1C`(<7%) 达标判定（与诊断严格分开） |
| `30-diagnosis-from-assessment.rq` | **新** `confirmationRequired` 处置 |
| `40-contraindication-flag.rq` | **新** 禁忌命中的 SPARQL 版（SHACL 只在校验入口跑，查询层要能直接查） |

### `20-lab-assessment.rq` 的五条硬约束

```sparql
# 1 单位逐字相等 —— 换算已在 ETL 做完，SPARQL 里一次都不做
FILTER(STR(?unit) = STR(?bunit))

# 2 可信度门禁 —— 上游随机值默认不参与
FILTER NOT EXISTS { GRAPH ?pg { ?res dmo:valueTrustLevel "Unverified" } }

# 3 populationContext —— 妊娠状态取自同一次就诊的 ClinicalObservation；
#   取不到按 NonPregnant 处理，但 applicableContext 如实写 "NonPregnant(assumed)"
#   （OWA 下"没记录"≠"没怀孕"，这是闭世界近似，不冒充断言事实）
FILTER(?pctx = ?ctxMatch || ?pctx = "Any")

# 4 开闭区间 —— 按 lowerOperator/upperOperator (GT/GTE/LT/LTE/None) 精确判定
#   「below 5.7%」是开区间，用 >= 近似会把 5.7 错判成 Normal
FILTER( ?loOp = "None" || IF(?loOp = "GTE", ?v >= ?lo, ?v > ?lo) )

# 5 Assessment 只回答「这次检验落在哪个区间」，绝不下诊断
```

两处 GraphDB 特有陷阱，写进规则注释：

- **患者侧用 `GRAPH ?pg` + `STRSTARTS(STR(?pg), "urn:dmo:patient:")`**（?pg 本身就是 provenance）；**知识侧不写 GRAPH** —— GraphDB 的 owl2-rl 物化三元组不在任何用户命名图里，写 `GRAPH <urn:dmo:seed>` 会静默丢结果。
- **Assessment IRI 由 `SHA1(labResult|thresholdId|ruleVersion)` 确定性铸造**，规则重跑得同一 IRI，`urn:dmo:inferred` 整图 PUT 才真幂等。

`classification` → `conclusion` 两套 enum 取值域不同名，必须显式 `BIND(IF(...))` 映射链，映射不上一律 `Indeterminate`，不猜。

### `30-diagnosis-from-assessment.rq`

```
conclusion="DiabetesRange" 且 threshold.confirmationRequired = false
    ⟹ Diagnosis(diagnosisKind="Diabetes", verificationStatus="Confirmed")
confirmationRequired = true：
    COUNT(DISTINCT ?day) ≥ 2 ⟹ "Confirmed"，supportsDiagnosis 连回全部支撑 Assessment
    否则                      ⟹ "Provisional" + caveat "单次异常不等于确诊，需另一日复测确认"
diagnosisType 一律 dmoid:DM-Unspecified（阈值只说明「是糖尿病」，不说明哪一型）；
    仅当患者另有 ICD10 断言的分型 Diagnosis 时才用那一条
```

`COUNT(DISTINCT ?day)` 用内联 `{ SELECT ?pat (COUNT(DISTINCT ?d) AS ?n) … GROUP BY ?pat }`，GraphDB 支持。

---

## 七、查询与问答层

**路由原则**（只有一种编排模式，不发明第二种）：

```
SQL 先收敛患者集合（快、可分页、带权限）
  → rdf/iri.py 转 IRI 列表
  → SPARQL 用 VALUES ?pat { … } 注入（永不全库扫描患者图）
  → 拿语义结论 + 出处
  → hybrid.py 按 source_pk 与 SQL 原始行拼接
```

| 问题形态 | 走哪 |
|---|---|
| 有多少 / 哪些患者 / 最近一次 / 分页 | **SQL** |
| 为什么 / 凭什么 / 能不能 / 依据哪条指南 | **SPARQL** |
| 原始那一行长什么样 | **SQL**（`source_table`+`source_pk` 回查） |
| 这个术语认不认识 / 为什么查不到 | **SQL**（`dmo_map`） |

### Agent 工具集（DESIGN.md:142-150 那套接真实数据）

| 工具 | 接真实数据的关键 |
|---|---|
| `search_concept` | SPARQL 的 `rdfs:label`/`skos:altLabel` **∪ SQL 的 `lab_term_map.src_name`/`icd10_map.icd10name`/`drug_term_map.src_name`**。这个并集是核心 —— 纯 SPARQL 版本查不到中文表面形式 |
| `find_patient`【新增】 | SQL over `dmo_src.v_*`，按 ICD10/科室/场景筛。接真实库的入口 |
| `run_query(template, params)` | 参数化模板：`patient_care_chain` / `latest_lab_result` / `diagnosis_evidence` / `medication_safety` + 本方案新增 |
| `classify_patient` | 直接查 `urn:dmo:inferred` 已物化的 Assessment/Diagnosis，不再临时建图跑规则 |
| `check_contraindication` | `40-*.rq` 结果 + 可选 pyshacl 复核，带 `dmo:rationale` 原文 |
| `get_recommendation` | SPARQL over `urn:dmo:extract:*` + `urn:dmo:sources`，带 quote + sha256 |
| `explain_gap(term)`【新增】 | SQL over `unmapped_term` + `verify_status`。**诚实回答"为什么没有"**，本项目最有说服力的工具 |
| `raw_sparql` | 逃生口：拒 INSERT/DELETE/DROP/LOAD/CLEAR + 超时 + 行数上限 |

三条原则不变（DESIGN.md:152-155）：不让 LLM 自由写 SPARQL（强制 `search_concept` → 准确 IRI → 模板）、每个回答带 provenance、schema 注入而非数据注入。

### 返回结构

```jsonc
{ "answer": "…（含免责声明，绝不出现具体剂量数字）",
  "dataQualityNotice": "本次使用了 2 条 trust=Unverified 的上游检验值，仅说明管线，不具临床含义。",
  "assertedFacts": [{ "iri":…, "value":7.4, "unit":"percent",
                      "origin":"demo-cohort", "trust":"Curated", "demoScenario":"S02",
                      "sqlRow":{"table":"dmo_src.ext_cdr_lis_result","pk":"TEST-90002-01"},
                      "sourceValue":7.4, "sourceUnit":"percent" }],
  "inferredFacts": [{ "type":"dmo:Assessment", "ruleId":"LAB-THRESHOLD-MATCH", "ruleVersion":"1.0.0",
                      "conclusion":"DiabetesRange", "applicableContext":"NonPregnant(assumed)",
                      "appliesThreshold":"…/threshold/A1C-DIABETES", "confirmationRequired":true },
                    { "type":"dmo:Diagnosis", "verificationStatus":"Provisional",
                      "caveat":"单次异常不等于确诊，需另一日复测确认" }],
  "sources": [{ "sourceId":"niddk-tests-diagnosis", "quote":"6.5% or above", "sha256":"…" }],
  "unmapped": [{ "term":"尿蛋白", "reason":"qualitative；参考范围『阴性』，原库无单位列，拒绝数值判定" }] }
```

FastAPI（`src/dmo/api.py`，新增 `fastapi`/`uvicorn` 依赖）暴露：`POST /ask`、`GET /patients`、`GET /patients/{id}/care-chain`、`GET /patients/{id}/safety`、`POST /query/{template}`、`GET /terms/unmapped`、`GET /demo/compare`。响应体即上述结构。

### 五个演示问题

| Q | 路径 | 亮点 |
|---|---|---|
| **Q1** P90002 是糖尿病吗？依据？ | find_patient → care_chain → assessment_evidence | A1C 7.4% 命中 A1C-DIABETES（≥6.5%，GTE，NonPregnant），但 `confirmationRequired=true` 且只 1 次 ⟹ **Provisional 而非 Confirmed**。出处「6.5% or above」+ sha256。**纯 LLM 和字符串匹配都会直接说"是糖尿病"** |
| **Q2** P90004 孕 26 周糖筛 142 要不要处理？ | Assessment.applicableContext="Pregnant" → GCT1H-REFER-PREG | 命中妊娠期**转诊触发点**，需返回做 OGTT；⚠️ 这**不是** GDM 诊断切点，本仓库语料未收录 OGTT 的 GDM 数值切点，不给数字。对照 P90005（同值非妊娠）零命中 |
| **Q3** P90008 能用恩格列净吗？P90009 的二甲双胍呢？ | `40-contraindication-flag.rq` | P90008 **绝对禁忌**，原文 `fda-diabetes-drug-classes.txt:280`；P90009 **零命中** —— 语料对二甲双胍只有定性表述，补 eGFR<30 就是编造出处。一正一反证明不误报 |
| **Q4** 真实 E11 患者 P00xxx 的检验能判断血糖控制吗？ | SQL 拿 4 条原始行 → 大项丢弃 → 子项映射命中但**均无 hasThreshold** → 零 Assessment → `explain_gap` | 系统主动指出上游主子表错位（4 条检验挂在名为「糖化血红蛋白」的大项下，实际是血小板/AST/尿蛋白/尿素氮），且值 trust=Unverified。**全场最有说服力的一屏** |
| **Q5** 同一条「尿蛋白 10.4」两种做法？ | `dmo demo compare` | 左栏 `semantic_link`：链两个互斥疾病、confidence 均 0.9、无单位无阈值无出处；右栏本方案：`qualitative`+参考范围"阴性"+无单位 ⟹ `unmappable`，零 Assessment，如实说明；要判白蛋白尿需 UACR(mg/g)，阈值 UACR-ALBUMINURIA(>30, GT)，出处 niddk-uacr-egfr |

---

## 八、里程碑与验收

| 里程碑 | 交付 | 验收命令 | 完成标准 |
|---|---|---|---|
| **R0** 骨架+守卫 | `src/dmo/` 包、config、engine+守卫、依赖加 `psycopg[binary]`/`fastapi`/`uvicorn`、恢复 `synthetic-patients.ttl` | `uv run dmo --help`<br>`uv run dmo db status`<br>`uv run dmo graph status`<br>`uv run dmo db guard-test` | CLI 可跑；PG/GraphDB 连通；越权写测试**失败**（守卫生效）；逐表 `has_table_privilege` 探测确认 SELECT + CREATE |
| **R1** 切 V2（本体侧，不碰 PG） | V2 JSON 回填 route + 新增 6 元素；seed 转 operator + SourcePassage + confirmationRequired + 10 个无阈值检验项；两个 SHACL 重写；夹具改 V2；`build_tbox` 换源；`graphdb_http.py` 抽取 | `python3 ontology/tools/build_tbox.py`<br>`python3 ontology/tools/source_registry.py`<br>`python3 ontology/tools/load_graphdb.py --load --verify`<br>`python3 ontology/tools/validate_shacl.py` | tbox 里 `Assessment/Diagnosis/MedicationUse/ClinicalObservation/SourcePassage` **5 类齐全**（当前 0）；**原有 8 条 CHECKS 全过**（含 S6 禁忌 + Prediabetes 反例）；SHACL 违规 = 3（P005/P006/P001 三条已知刻意违规） |
| **R2** 只读投影 | `dmo_src` schema、5 张视图、`upstream_baseline` | `uv run dmo db migrate`<br>`uv run dmo db baseline [--check]` | 视图行数 = 原表行数；二次比对一致；`pg_stat_user_tables` 上 `patient_analysis` 的 `n_tup_upd/ins/del` 增量为 **0** |
| **R3** 术语映射 | `dmo_map` 5 表、`terms/*.py`、`import-wfs` | `uv run dmo map sync-concepts`<br>`uv run dmo map list-unmapped` | `concept_ref` ≥ 60 行；**12 个子项名 100% 有归宿**（verified/unmappable/no-source-data 三选一，无空白）；血糖行 `conv_factor=18.0182` 已人工 verified |
| **R4** 最小队列（3 场景） | `cohort_*.csv`（S02/S07/S08）、`ext_*` 表、`db/cohort.py` | `uv run dmo db seed` ×2<br>`uv run dmo db baseline --check` | 3 场景落地；重跑幂等（行数不变）；原表零变动 |
| **R5** ETL + 同步 | `db/projection.py`、`rdf/*`、`dmo_core` 7 表 | `uv run dmo project run`<br>`uv run dmo sync all` ×2<br>`uv run dmo sync all --prune` | 首跑 PUT N 图；**二跑全 skipped、零 PUT**；`--prune` 后 tbox/seed/sources/extract 三元组数**不变**；日志无姓名/身份证 |
| **R6** 阈值规则 | `20/20b/21/30/40-*.rq` | `python3 ontology/tools/load_graphdb.py --rules --verify`<br>`uv run dmo query assessment_evidence --param pat=P90002` | S02 出 **Provisional 不出 Confirmed**；S07 报违规；S08 **零违规**；`Unverified` 值零 Assessment |
| **R7** CLI + FastAPI | `query/*`、`agent/*`、`explain_gap`、`api.py`、`demo compare` | `uv run dmo ask "P90008 能继续用恩格列净吗"`<br>`uv run dmo serve` + `curl POST /ask`<br>`uv run pytest` | Q1/Q3/Q4/Q5 走通；返回体四段齐全；含免责声明、**零剂量数字**；pytest 全绿 |
| **R8** 铺开剩余 15 场景 | 补 cohort CSV + 逐场景断言测试 | `uv run pytest -k scenario`<br>`uv run dmo demo compare --scenario S11` | 18 场景逐条断言全过：S04 命中 Pregnant 而 S04b 零命中；S16 的 5.7 归 Prediabetes 不归 Normal；S03 `basedOnLabResult` 2 条且 Confirmed |

### 端到端复现（R7 后）

```bash
uv sync --extra dev
uv run dmo db migrate && uv run dmo db baseline
uv run dmo map sync-concepts && uv run dmo db seed
python3 ontology/tools/build_tbox.py
python3 ontology/tools/source_registry.py
python3 ontology/tools/load_graphdb.py --create --load
uv run dmo project run && uv run dmo sync all
python3 ontology/tools/load_graphdb.py --rules --verify
python3 ontology/tools/validate_shacl.py --allow 3
uv run pytest
uv run dmo ask "P90008 能继续用恩格列净吗"
```

---

## 九、风险

| # | 风险 | 缓解 |
|---|---|---|
| R-1 | 只确认了 database 级 CREATE，**未确认逐表 SELECT 与建视图权限** | R0 第一件事就是逐表 `has_table_privilege` 探测。若无 SELECT，退化为一次性 `COPY` 快照到 `dmo_src.snap_*`，其余不变 |
| R-2 | `diagnosisType` 是 many-to-one ⟹ FunctionalProperty，一条 Diagnosis 挂两个分型会推出 `sameAs`，与 `AllDisjointClasses` 冲突，**整个本体不一致且不报错** | ETL 强制一条 Diagnosis 至多一个 `diagnosisType`；「Prediabetes ⋢ Diabetes」反例查询作哨兵 |
| R-3 | **切 V2 是本方案最大的单点工作量**：两个 SHACL + 夹具 + 验收查询 + seed 全部重写，任一处漏改都会让 R1 验收失败 | R1 独立成一个里程碑，纯本地不碰 PG，验收标准是**原有 8 条 CHECKS 全过 + SHACL 违规恰好 3 条**，跑不通不进 R2 |
| R-4 | 主子表错位可能**不止 ITEM14/ITEM15** | 映射一律以子项 `itemname` 为准、大项全丢；R3 验收要求 12 个子项名 100% 有明确归宿 |
| R-5 | 单位靠参考范围反推是**推断不是断言** | `verify_status` 必须人工 `verified` 才生效；`sourceValue`/`sourceUnit` 全程保留；S11 专门演示换算前后差异 |
| R-6 | GraphDB 跨图查询里写 `GRAPH <urn:dmo:seed>` 会**丢掉 owl2-rl 物化边**，静默少结果 | 已写进 `20-lab-assessment.rq` 注释；R6 验收逐场景断言，不是"跑通就行" |
| R-7 | `dmo_core` 与上游漂移 | `upstream_baseline` 每次 `project run` 前强制比对，不一致拒跑 |
| R-8 | 演示队列被误当真实数据 | 每条 demo 事实强制带 `dmo:factOrigin "demo-cohort"` + `dmo:demoScenario`；返回体每条 asserted fact 带 origin；CLI/API 区分显示 |
| R-9 | Java 8 ⟹ HermiT 跑不了，DL 一致性检查**永远无法验收** | 不假装能做。用 SHACL 的 Diagnosis 层分型唯一性约束（S15）作**可执行的替代验收**，文档注明这不等价于 DL 一致性检查 |

## 不在范围内

原计划已排除的全部保留（PHI、多租户/RBAC、CDC/MQ、GraphDB 作唯一患者库、剂量建议、`owl:hasKey`/`owl:sameAs` 患者合并），再加：

- **`decision_support` schema 接入**（R-6 的理由）
- **对 `patient_analysis` 的任何写操作**，包括在原表 INSERT 演示患者
- **ORM / Alembic**
- **`semantic_link` 的迁移或修改**、`https://example.org/wfs/` 命名空间的任何引用
- **HermiT / DL 一致性检查**
- `patient_risk_factor` / `device_use` / `intervention` 三张表（真实库无对应数据）
- 住院侧 `ip_order_query`/`surgical_operation` 的深度建模（只做 `patientid_to_inpatientno` 最小接入，够 MedicationUse 用）
