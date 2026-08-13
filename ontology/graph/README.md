# 糖尿病本体图（Ontology Playground / Fabric IQ 视图）

本目录是**图层设计**，不是 `docs/DESIGN.md` 里那套 OWL 语义层。两者是同一领域的两种投影，
必须分清楚，否则会把 ER 模型当成 TBox 用。

| 文件 | 说明 |
|---|---|
| `diabetes-ontology.json` | V1 设计源文件（保留，不覆盖） |
| `diabetes-ontology.rdf` | V1 生成物（保留，不覆盖） |
| `diabetes-ontology-v2.json` | V2 设计源：采用 ClinicalObservation → Diagnosis → MedicationUse 的 care-chain 模式 |
| `diabetes-ontology-v2.rdf` | V2 RDF/XML 生成物，用于导入 Designer |
| `../tools/build_playground_rdf.py` | JSON → RDF/XML 编译器，附带 Fabric IQ 校验 |

```bash
python3 ontology/tools/build_playground_rdf.py          # 校验 + 生成
python3 ontology/tools/build_playground_rdf.py --check  # 只校验

# 生成或校验 V2（不会覆盖 V1）
python3 ontology/tools/build_playground_rdf.py \
  --src ontology/graph/diabetes-ontology-v2.json \
  --out ontology/graph/diabetes-ontology-v2.rdf
python3 ontology/tools/build_playground_rdf.py --check \
  --src ontology/graph/diabetes-ontology-v2.json \
  --out ontology/graph/diabetes-ontology-v2.rdf
```

导入方式：打开 `http://localhost:5173/#/designer` → 右侧 **RDF** 页签 → **Edit RDF** →
粘贴 `diabetes-ontology.rdf` 全文 → **Load into Designer**。当前版本在 Designer 的
Validate 下为 **No issues found**（20 实体 / 109 属性 / 33 关系）。

---

## 一、这个工具能表达什么，不能表达什么

Ontology Playground 的 Designer 面向 **Microsoft Fabric IQ**，它的数据模型是
**实体类型 + 带类型的属性 + 二元关系（含基数）**——本质是 ER 模型，不是 OWL DL。
它的 RDF 导入器（`src/lib/rdf/parser.ts`）只读取 `owl:Class` 的 label/comment/图标颜色、
`owl:DatatypeProperty` 的 domain/range、`owl:ObjectProperty` 的 domain/range/cardinality。

**下面这些 `docs/DESIGN.md` 明确要学的 OWL 特性，这个工具全部读不到，写进去也会被丢弃：**

| OWL 特性 | 在本图中的替代表达 |
|---|---|
| `rdfs:subClassOf`（T1DM ⊑ Diabetes） | 分型降级为 `DiabetesType` 的**实例**，层次靠 `mondoCode` 外挂 |
| `owl:disjointWith`（T1DM ⊥ T2DM） | 退化为 `hasDiabetesType` 的 many-to-one 基数 |
| `owl:equivalentClass` + datatype restriction | 拆成 `DiagnosticThreshold` 数据节点 + SPARQL CONSTRUCT |
| `owl:propertyChainAxiom` | 拆成 `hasComplication` + `Complication.affectedOrgan` 两跳 |
| `owl:TransitiveProperty`（分期 worseThan） | 退化为 `ComplicationStage.stageOrder` 整数序 |
| `owl:FunctionalProperty` | 仅在关系描述里注明，无形式化约束 |

**结论：这张图是本体的「数据形态视图」，可以直接当 ABox schema / Fabric IQ 语义模型用；
TBox 公理仍必须写在 `ontology/src/*.ttl` 里。两边靠同一套编码（`*Code` 字段）对齐。**

## 二、五条主轴

```
                    RiskFactor ──increasesRiskOf──▶ DiabetesType ──predisposesTo──▶ Complication
                        ▲                                ▲                              │
                        │                                │ classifiesInto               │ hasStage
   Patient ──hasRiskFactor                    DiagnosticThreshold                       ▼
      │                                                  ▲ hasThreshold        ComplicationStage
      ├─hasEncounter──▶ ClinicalEncounter ──▶ LabResult ─┴──▶ LabTest ◀──screenedByTest──┤
      ├─hasComplication ─────────────────────────────────────────▶ Complication ─────────┘
      ├─takesMedication ─▶ Medication ─▶ DrugClass ─▶ Contraindication ─triggeredBy─▶ Complication
      ├─usesDevice ─▶ Device                    └─▶ AdverseEffect
      └─followsIntervention ─▶ LifestyleIntervention ─mitigates─▶ RiskFactor

   Recommendation ─▶ {DiabetesType, Complication, DrugClass, LifestyleIntervention,
                      GlycemicTarget, MonitoringSchedule} ─citesSource─▶ GuidelineSource
```

1. **患者轴** `Patient` `ClinicalEncounter` —— 时间锚点与事实汇聚
2. **检验轴** `LabTest` `LabResult` `DiagnosticThreshold` `GlycemicTarget` —— 数值与阈值分离
3. **疾病轴** `DiabetesType` `Complication` `ComplicationStage` `Symptom` `RiskFactor`
4. **治疗轴** `DrugClass` `Medication` `Contraindication` `AdverseEffect` `LifestyleIntervention` `Device`
5. **指南轴** `Recommendation` `MonitoringSchedule` `GuidelineSource` —— provenance 是一等公民

## 三、几个刻意的设计决定

- **诊断阈值 ≠ 管理目标。** `DiagnosticThreshold`（A1C ≥ 6.5% ⟹ 糖尿病）回答「是不是」，
  `GlycemicTarget`（多数成人 A1C < 7%）回答「管得好不好」。合并成一个节点是常见错误，
  会让 agent 把「诊断切点」当「治疗目标」答出去。
- **阈值带 `populationContext`。** 妊娠、儿童与非妊娠成人 cutoff 不同（GDM 用糖筛/OGTT，
  且孕中晚期 A1C 不可靠）。不分人群的阈值节点在 GDM 问题上必然答错。
- **禁忌挂在 `DrugClass` 而非 `Medication`。** FDA 原文的警示是类别级的
  （二甲双胍—肾功能/乳酸酸中毒、SGLT2i—重度肾功能损害/透析、TZD—心衰、SU—低血糖）。
- **`Contraindication` 是数据不是公理。** 「一般用 X，除非 Y」是默认规则，OWL 单调推理
  表达不了，塞进 TBox 会导致不一致——这是 `docs/DESIGN.md` 陷阱 #2 的落点。
- **不建模剂量。** `takesMedication` 只有 `startDate` / `regimenRole`，
  `Medication` 只有药代特征（onset/duration），没有任何剂量字段。schema 层面堵死越界输出。
- **`AdverseEffect` 与 `Complication` 分开。** 低血糖既是并发症也是药物不良反应，
  归因不同——靠边的方向区分，而不是靠一个节点身兼两职。
- **`GuidelineSource.localFile` 指向采集副本。** 每条推荐都能回溯到
  `ontology/knowledges/*.txt` 的具体文件，evals 的 provenance 指标可直接机器校验。

## 四、概念到知识来源的映射

| 实体 | 主要来源 |
|---|---|
| `DiabetesType` | `niddk-diabetes-overview.txt`、`niddk-monogenic-diabetes.txt`、`niddk-gestational-diabetes.txt` |
| `LabTest` / `DiagnosticThreshold` | `niddk-tests-diagnosis.txt`（诊断切点表）、`niddk-a1c-test.txt`、`niddk-diabetes-prediabetes-tests.txt`、`niddk-uacr-egfr.txt` |
| `GlycemicTarget` | `niddk-managing-diabetes.txt`（ABCS、餐前/餐后目标、TIR） |
| `Complication` / `ComplicationStage` | `niddk-diabetic-kidney-disease.txt`、`niddk-diabetic-eye-disease.txt`（NPDR/PDR/DME）、`niddk-diabetic-neuropathy.txt`（周围/自主/局灶/近端）、`niddk-diabetic-foot-problems.txt`、`niddk-cardiovascular-disease.txt`、`cdc-hypoglycemia.txt`、`cdc-diabetic-ketoacidosis.txt` |
| `DrugClass` / `Medication` / `Contraindication` / `AdverseEffect` | `fda-diabetes-drug-classes.txt`、`niddk-insulin-medicines-treatments.txt` |
| `RiskFactor` / `LifestyleIntervention` | `cdc-prediabetes-prevention.txt`、`niddk-healthy-living-with-diabetes.txt` |
| `MonitoringSchedule` | `niddk-uacr-egfr.txt`（UACR/eGFR 每年）、`niddk-tests-diagnosis.txt`（3 年复查、GDM 24–28 周、产后 12 周） |
| `Device` | `niddk-insulin-medicines-treatments.txt`（CGM、泵、人工胰腺）、`cdc-diabetic-ketoacidosis.txt`（尿酮试纸） |

## 五、已知缺口（下一步要补的，不是可以忽略的）

1. **`ontology/knowledges/nhc-gdm-nutrition-2018.txt` 和 `nhc-gdm-weight-standard-2023.txt`
   只抓到了网页导航壳，没有正文**——只有标准号 `WS/T 601—2018` / `WS/T 828—2023`，
   正文在 PDF 里。目前这两份对本体零贡献，GDM 分支的中国标准是空的。要么补抓 PDF，要么从来源清单里划掉。
2. `nhc-diabetes-action-plan-2024.txt` / `nhc-diabetes-day-2025.txt` 是政策与宣传口径文本，
   含大量非临床内容，尚未做抽取；目前本图的临床阈值全部来自美国来源（ADA/NIDDK/CDC/FDA）。
   若目标人群是中国，诊断口径与药物可及性需要另建一层，不能直接照搬。
3. 本图只有 schema，**没有实例**。`docs/DESIGN.md` 里的 `synthetic-patients.ttl`（20–30 例合成患者）
   还没建；没有实例就无法验证 `classify_patient` / `check_contraindication` 这两个工具。
4. 外部术语的 `mondoCode` / `loincCode` / `atcCode` / `hpoCode` / `rxNormCode` 目前只是**字段位**，
   实际取值待 `imports_fetch.py` 从 OLS4 拉取后回填。

---

> ⚠️ 技术学习用途，不是医疗器械，不构成医疗建议；本目录任何文件都不含具体用药剂量。
