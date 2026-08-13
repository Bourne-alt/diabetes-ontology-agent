# 语义层构建计划：从 ER 图 + 知识文档 到 GraphDB

> 配套文档：整体方案见 [DESIGN.md](DESIGN.md)，图层设计见 [ontology/graph/README.md](../ontology/graph/README.md)。
> 本文只解决一件事：**已经有了 ER 图（20 实体 / 33 关系）和 26 份知识原文，怎么变成一个能被 agent 查询的语义层，并装进 GraphDB。**

---

## 0. 环境现状（2026-08-12 实测）

| 项 | 状态 | 影响 |
|---|---|---|
| GraphDB | Free **11.3.2**，运行于 `localhost:7200` | 可用。Free 版无集群、并发查询受限，本项目够用 |
| 已有仓库 | `med_repo`（"医疗图知识库"，2109 三元组） | **属于另一个项目**（`example.org/wfs/disease-ontology#`，160 个 SKOS Concept、23 个 AxiomProvenance）。**不得混用** |
| `med_repo` ruleset | `rdfsplus-optimized` | 与本项目所需的 `owl2-rl` 不兼容 |
| 系统 Java | **1.8.0_351** | GraphDB Desktop 自带 JRE 可跑；但 `dmo build --with-hermit` 需 Java 17，**当前机器跑不了** |
| Python | 3.12.12 + `uv` 已装，`rdflib` 未装 | 待 `uv sync` |

**结论 0-A：新建 `dmo` 仓库，不碰 `med_repo`。**
理由有二：混库后无法区分三元组归属、重跑抽取时无法整体清理；且 **GraphDB 的 ruleset 在建仓时定死，事后变更需 reload 全部数据**，`rdfsplus-optimized` 不能升级成 `owl2-rl`。

---

## 1. 架构决策：GraphDB 放在哪一层

`DESIGN.md` 的技术栈明确要求「纯 Python，无 Java」「默认构建零 Java 依赖」。引入 GraphDB 与之冲突。**解法不是二选一，是分层。**

| 层 | 工具 | 职责 | 是否进 CI |
|---|---|---|---|
| **构建 / 测试层** | `rdflib` + `owlrl` + `pyshacl` | 合并、实体化、跑规则、SHACL 校验、单测 | ✅ 是（零 Java） |
| **服务 / 查询层** | GraphDB `dmo` 仓库 | agent 的 `run_query` / `raw_sparql` 端点；Workbench 图谱浏览；增量 SHACL | ❌ 否（本地/部署环境） |

两层的交付物是 `ontology/dist/dmo-full.ttl`。**GraphDB 是消费者，不是构建器。** 这样 CI 不需要 GraphDB，本地开发又拿得到可视化和真 SPARQL endpoint。

### ⚠️ 换 GraphDB 不解决数值推理问题

`owl2-rl` ruleset **依然做不到 datatype range restriction 推理**。「HbA1c ≥ 6.5 ⟹ 分类为糖尿病患者」在 GraphDB 里和在 `owlrl` 里一样推不出来——这是 OWL-RL profile 的边界，不是实现的弱点。

**`DESIGN.md` 陷阱 #3 的对策不变：核心分类逻辑用 SPARQL CONSTRUCT。** 不要指望换推理机能省掉这一步。

---

## 2. TBox：从 ER 图长出语义层

**ER 图 → OWL 不是 1:1 翻译。** 必须把「可机械生成」和「必须手写」分开，混在一起是这类项目最常见的失败点。

### 2.1 可机械生成（脚本从 `ontology/graph/diabetes-ontology.json` 编译）

| ER 元素 | OWL 产出 |
|---|---|
| 20 个 `entityType` | `owl:Class` + `rdfs:label` + `rdfs:comment` |
| 109 个 `property` | `owl:DatatypeProperty` + `rdfs:domain` + `rdfs:range`（xsd 类型） |
| 33 条 `relationship` | `owl:ObjectProperty` + `rdfs:domain` + `rdfs:range` |
| `cardinality: many-to-one` | `owl:FunctionalProperty` ← 唯一真能推出新事实的机械转换 |
| `cardinality: one-to-many` | `owl:InverseFunctionalProperty` |
| `isIdentifier: true` | ~~`owl:hasKey`~~ **已停用**，见 §2.5 |
| `type: enum` 的 `values` | `skos:ConceptScheme` + 每个取值一个 `skos:Concept` |
| `unit` | `dmo:unit` 注解（或 QUDT 映射，二期） |

产物：`ontology/dist/tbox-generated.ttl`，**不手改**，由 `build_tbox.py` 幂等重生成。

### 2.2 必须手写（图里根本没有这些信息）

`ontology/src/dmo-axioms.ttl` —— 这里才是 `DESIGN.md`「学习价值点」表格的落地处：

| OWL 特性 | 具体公理 | 验收方式 |
|---|---|---|
| `owl:disjointWith` | `T1DM ⊥ T2DM` | 造一个同时断言两型的患者，一致性检查必须报错 |
| `owl:equivalentClass` | `DiabetesPatient ≡ Patient ⊓ ∃hasObservation.(...)` | 见 §2.4：数值部分退到 SPARQL |
| `owl:propertyChainAxiom` | `hasComplication ∘ affectsOrgan ⊑ hasAffectedOrgan` | 查「所有肾脏受累患者」应命中 DKD 患者 |
| `owl:TransitiveProperty` | `ComplicationStage worseThan` | CKD G4 worseThan G2 应被推出 |
| `owl:FunctionalProperty` | `hasDiabetesType` | 断言两个分型触发推理冲突 |
| `skos:exactMatch` / `closeMatch` | 自建概念 ↔ MONDO / LOINC / ATC | 术语映射层，全项目最实用的部分 |

**机械生成的是骨架，学习价值全在手写的这 6 条。**

### 2.3 ⏸ 待拍板：分型建模走哪条路

ER 图里 `DiabetesType` 是**实体类型**，T1DM/T2DM/GDM 是它的**实例**。转 OWL 有两条路，**这是本计划唯一需要人决策的地方**：

**方案 A — SKOS 术语路线**
T2DM 是 `dmo:DiabetesType` 的实例 + `skos:Concept`，层次用 `skos:broader`。
- ✅ 简单、安全、不会引起本体不一致；GraphDB 对 SKOS 有原生支持
- ❌ **做不了 `disjointWith`，做不了患者自动分类** —— 直接砍掉 M2 里程碑

**方案 B — 类路线（OWL 2 punning）**
T2DM 是 `owl:Class` 且 `rdfs:subClassOf dmo:Diabetes`，`dmo:DiabetesType` 成为元类。
- ✅ 能写 `T1DM owl:disjointWith T2DM`；「同时是 T1DM 和 T2DM 的患者」会被一致性检查抓出来 —— **这正是 M2 的验收标准**
- ❌ 进入 OWL 2 DL punning 领域，HermiT 支持但需谨慎；且当前机器 Java 8 跑不了 HermiT

**📌 推荐：双轨制**

| 走方案 B（类路线） | 走方案 A（SKOS） |
|---|---|
| `DiabetesType`、`Complication`、`ComplicationStage` | `LabTest`、`DrugClass`、`Symptom`、`RiskFactor`、`Device`、`LifestyleIntervention` |
| 需要自动分类与互斥检查 | 纯术语目录，SKOS 够用 |

这是本体工程的标准做法，也和 `med_repo` 里已有的 SKOS + AxiomProvenance 实践一致。

### 2.5 ⚠️ 实测修正：`owl:hasKey` 已停用

§2.1 原本要求 `isIdentifier → owl:hasKey`。**实测后撤销。**

owlrl 的 `prp-key` 规则会把同类实例**无视键值差异**全部折叠成 `owl:sameAs`——
`CKD-G1` 与 `CKD-G5` 的 `stageCode` 明明不同，仍被判为 `sameAs`（202 对）。
叠加方案 B 的 `disjointWith` 后整个本体不一致，推出 `T1DM ⊑ T2DM`、
`Prediabetes ⊑ Diabetes`，即「前期就是糖尿病」这个本领域最经典的错误结论。

二分定位结果（其余公理逐一移除均无效，仅移除 hasKey 有效）：

| 移除项 | 是否仍不一致 |
|---|---|
| 全量 | ✗ 不一致 |
| **去 `owl:hasKey`** | **✓ 一致** |
| 去 `InverseFunctionalProperty` | ✗ 不一致 |
| 去 `AllDisjointClasses` | ✗ 不一致 |
| 去 `equivalentClass` | ✗ 不一致 |

**对策**：`build_tbox.py` 默认不发 `owl:hasKey`，改为 `--with-haskey` 显式开启。
代价可接受——ABox 的 URI 本来就由标识属性确定性铸造，hasKey 没有额外收益。
换 HermiT（Java 17）后应重测：这很可能是 owlrl 的实现问题而非 OWL 2 语义问题。

### 2.4 阈值不进 TBox

`DiagnosticThreshold` 保持为**数据实例**，由 SPARQL CONSTRUCT 消费。理由见 §1 的警告和 `DESIGN.md` 陷阱 #1/#2/#3。同理，`Contraindication`（「一般用 X，除非 Y」）是默认规则，单调推理表达不了，**一律作为数据 + SHACL**。

---

## 3. ABox：26 份知识文档怎么变成三元组

**直接让 LLM 读完输出 Turtle 是最坏的做法。** 你会得到一堆看起来很对、但数字是编的三元组，且事后无法审计。分四层递进，风险从零到高。

### 第 0 层 — source registry（零幻觉，纯机械）

每个 `ontology/knowledges/*.txt` → 一个 `dmo:GuidelineSource` 实例：

```turtle
dmo:src-niddk-a1c-test a dmo:GuidelineSource ;
    dmo:name "The A1C Test & Diabetes" ;
    dmo:publisher dmo:NIDDK ;
    dmo:publishedYear 2018 ;
    dmo:sourceUrl <https://...> ;
    dmo:localFile "ontology/knowledges/niddk-a1c-test.txt" ;
    dmo:sha256 "…" .
```

**`sha256` 是关键**：知识文件一改，所有从它抽出的三元组自动标记为过期，重跑抽取有明确触发条件。

### 第 1 层 — 高危常量手写，不许 LLM 碰

`ontology/src/dmo-threshold-seed.ttl` 手写以下常量：

| 指标 | 切点 | 来源 |
|---|---|---|
| A1C | 正常 <5.7% / 前期 5.7–6.4% / 糖尿病 ≥6.5% | `niddk-tests-diagnosis.txt` 诊断表 |
| FPG | ≤99 / 100–125 / ≥126 mg/dL | 同上 |
| OGTT-2h | ≤139 / 140–199 / ≥200 mg/dL | 同上 |
| 随机血糖 | ≥200 mg/dL（伴症状） | 同上 |
| 糖筛 1h | ≥135–140 mg/dL 需转 OGTT | 同上 |
| UACR | 白蛋白尿 >30 mg/g；大量白蛋白尿 >300 | `niddk-uacr-egfr.txt` |
| 低血糖 | <70 mg/dL；严重 <54 mg/dL | `cdc-hypoglycemia.txt` |
| 酮症警戒 | 血糖 ≥250 查酮体；≥300 急诊 | `cdc-diabetic-ketoacidosis.txt` |
| 管理目标 | A1C <7%；餐前 80–130；餐后 <180；TIR 70–180 ≥70%；BP <130/80 | `niddk-managing-diabetes.txt` |

**LLM 在这一层只做反向验证**：给它一条阈值，让它在原文里找出支持句；找不到就报警。**方向反过来，风险就没了。** 这些数字错一个，整个 agent 就废，不能赌。

### 第 2 层 — span-anchored 抽取（核心安全阀）

其余实体（`DrugClass` / `Medication` / `Complication` / `Symptom` / `RiskFactor` / `Recommendation` / `Contraindication` / `AdverseEffect`）用 Claude structured output 抽取，**强制每条输出携带原文引用**：

```json
{
  "entity": "SGLT2Inhibitor",
  "field": "contraindication",
  "value": "severe kidney problems or dialysis",
  "quote": "Do not take these drugs if you have severe kidney problems or are on dialysis.",
  "sourceFile": "fda-diabetes-drug-classes.txt"
}
```

抽取后**程序化校验**：normalize 空白后，`quote` 必须在原文中逐字存在，否则整条丢弃并写入 `ontology/dist/rejected.jsonl`。

- 把幻觉率压到接近 0
- 产出一个可量化的抽取质量指标（reject rate），可进 eval 报告
- **这不是可选项，是整条链路的安全阀**

模型配置：`claude-opus-5`，structured output，`thinking={"type":"adaptive"}`。

### 第 3 层 — PROV-O 记账 + named graph 分区

每次抽取写入 `urn:dmo:extract:<source-id>`，图本身带来源与生成活动：

```turtle
<urn:dmo:extract:niddk-a1c-test> a prov:Entity ;
    prov:wasDerivedFrom dmo:src-niddk-a1c-test ;
    prov:wasGeneratedBy [ a prov:Activity ;
        dmo:model "claude-opus-5" ;
        dmo:promptVersion "extract-v3" ;
        prov:endedAtTime "2026-08-12T…"^^xsd:dateTime ] .
```

**⏸ 具化方式选择：named graph（推荐）vs RDF-star vs AxiomProvenance 节点**

选 **named graph per source**，理由很实际：重跑抽取时可用 Graph Store Protocol `PUT` **整图原子替换**；RDF-star 和具化节点都得先算差集再删，幂等性难保证。`DESIGN.md` 要求「构建必须幂等且可重复」，named graph 是唯一能轻松做到的。

（`med_repo` 里用的是 `AxiomProvenance` 具化节点——那个项目的选择，本项目不沿用。）

---

## 4. GraphDB 装载

### 4.1 命名图布局

| 图 URI | 内容 | 重灌方式 |
|---|---|---|
| `urn:dmo:tbox` | 手写公理 + 机械生成的类/属性骨架 | 每次 build 整图 PUT |
| `urn:dmo:terms` | SKOS 术语 + 外部映射 slim（MONDO/LOINC/ATC/HPO） | 术语更新时 PUT |
| `urn:dmo:seed` | 手写阈值/目标常量 | 手改后 PUT |
| `urn:dmo:extract:<source-id>` | 每份知识文件一图，共 26 个 | 单文件重抽只动一图 |
| `urn:dmo:inferred` | SPARQL CONSTRUCT 物化结果 | 每次跑规则整图替换 |
| `http://rdf4j.org/schema/rdf4j#SHACLShapeGraph` | SHACL shapes（GraphDB 约定路径） | 谨慎，见 §4.2 |

### 4.2 建仓库

```bash
curl -X POST http://localhost:7200/rest/repositories \
  -H "Content-Type: application/json" \
  -d '{"id":"dmo","title":"Diabetes Management Ontology","type":"graphdb","params":{
        "ruleset":{"name":"ruleset","value":"owl2-rl-optimized"},
        "validationEnabled":{"name":"validationEnabled","value":"false"},
        "disableSameAs":{"name":"disableSameAs","value":"true"},
        "baseURL":{"name":"baseURL","value":"https://example.org/dmo#"}}}'
```

**三个坑**（第 3 条是实测新增）：

1. **`ruleset` 建仓时定死**，事后改要 reload 全部数据。一次选对：`owl2-rl-optimized`。
2. **`validationEnabled` 先设 `false`**。SHACL shapes 一旦进 shapes graph，之后每次写入都触发校验，批量导入会以一堆难读的错误炸掉。**先关校验灌数据，灌完再开。**
3. **每个参数必须带 `label`。** GraphDB 11 只给 `name`/`value` 会 400，而且报错文本用的是
   label 而不是参数名——`Missing parameter Default namespaces for imports` 指的其实是
   `defaultNS`，很容易误判成参数名写错。上面的 curl 示例因此是**跑不通的**，
   正确 payload 见 `load_graphdb.py` 的 `repo_config()`。

### 4.3 幂等灌图

**用 `PUT`（整图替换），不要用 `POST`（追加）**：

```bash
curl -X PUT -H "Content-Type: text/turtle" \
  --data-binary @ontology/dist/tbox.ttl \
  "http://localhost:7200/repositories/dmo/rdf-graphs/service?graph=urn:dmo:tbox"
```

### 4.4 验收查询

```bash
# 各命名图三元组数
curl -s -H "Accept: text/csv" --data-urlencode \
  'query=SELECT ?g (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } } GROUP BY ?g ORDER BY DESC(?n)' \
  http://localhost:7200/repositories/dmo

# M1 验收：所有 T2DM 患者的最近 HbA1c
# M3 验收：eGFR<30 且在用二甲双胍的患者（应被 clinical-safety shape 检出）
```

---

## 5. 待建文件清单

| 文件 | 类型 | 说明 |
|---|---|---|
| `ontology/tools/build_tbox.py` | ✅ **已建** | JSON → TBox 骨架，幂等。20 类 / 94 数据属性 / 33 对象属性 / 30 ConceptScheme |
| `ontology/src/dmo-axioms.ttl` | ✅ **已建** | 6 条 OWL 特性全部到位，owlrl 实体化 1528 → 3664 三元组 |
| `ontology/src/dmo-threshold-seed.ttl` | ✅ **已建·手写** | 17 条诊断阈值 + 5 条管理目标 + 8 个检验项，条条带 citation |
| `ontology/tools/source_registry.py` | ✅ **已建** | 26 份来源 + sha256；空壳文件机械判出并标 `contentStatus=shell` |
| `ontology/tools/semantic_extract.py` | ✅ **已建** | span-anchored 抽取；真实跑通 quote 命中 100%，但关系边为 0（见工具 README 局限 #5）|
| `ontology/tools/load_graphdb.py` | ✅ **已建** | 建仓 + 幂等 PUT + 验收查询。纯 stdlib，不依赖 httpx |
| `ontology/shapes/*.shacl.ttl` | ✅ **已建** | data-quality（68）+ clinical-safety（24），pyshacl 验证 3 条刻意违规全命中、零误报 |
| `ontology/tools/validate_shacl.py` | ✅ **已建** | 构建层 SHACL 门禁，纯 Python，不依赖 GraphDB |
| `ontology/data/synthetic-patients.ttl` | ✅ **已建** | 6 例合成患者，专为触发/不触发各条约束而造 |
| `ontology/rules/align-extracted.rq` | ✅ **已建** | 抽取产物 → 规范个体对齐。分类/指南 CONSTRUCT 待建 |

## 6. 实施顺序

| 步骤 | 内容 | 阻塞条件 | 验收 |
|---|---|---|---|
| **S1** | ✅ `build_tbox.py` → TBox 骨架 | ~~无~~ 已完成 | 生成的 ttl 能被 rdflib 解析，类/属性数量对得上 20/109/33 |
| **S2** | ✅ `dmo-axioms.ttl` 手写公理 | ~~⏸~~ 已拍板双轨制 | 造 T1DM∧T2DM 患者，一致性检查报错 |
| **S3** | ✅ `source_registry.py` + 阈值 seed | ~~⏸~~ 空壳已机械判定 | 26 个 GuidelineSource 实例，sha256 齐全 |
| **S4** | ✅ `load_graphdb.py` + 建 `dmo` 仓库 | ~~S1~~ 已完成 | ✅ 已验收：幂等（连灌 3 次 1528 不变）、owl2-rl 真在推理 |
| **S5** | `extract.py` —— **先只跑 2–3 个文件**，看 reject 率再铺开 | S3 | reject rate 可量化；抽出的三元组能反查到原文 |
| **S6** | ✅ SHACL shapes | ~~S4、S5~~ 已完成 | ⚠️ **验收标准已改**，见下 |

**当前状态：S1–S6 全部完成并验收。计划的编号步骤走完了。**

### ⚠️ S6 验收标准的修正（重要）

计划原文写的是「**eGFR<30 患者用二甲双胍能被检出**」。**这条写不出来，已替换。**

实测：`eGFR` 在 `ontology/knowledges/` 全语料中出现 **0 次**；FDA 药物文件对二甲双胍
只有定性表述（"Talk to your doctor about your kidney health"、"people with kidney
problems may have a rare side effect called lactic acidosis"），**没有任何数值切点**。
把 30 这个数字写进本体 = 编造出处，与 §3 第 1 层「高危常量不许编」的原则直接冲突。

→ 改用语料里**唯一一条明确禁令**做验收：
   `"Do not take these drugs if you have severe kidney problems or are on dialysis."`
   （SGLT2 Inhibitors，`fda-diabetes-drug-classes.txt:280`）

实测结果：`P001,SGLT2 Inhibitors,KidneyFailure` —— 命中。
而 P002（肾衰竭 + 二甲双胍）**刻意不触发**，证明形状没有过度触发。
§7 风险 1（NHC 空壳）已由 `source_registry.py` 机械判定解决：长句 1 行 vs 其余 13–83 行，
分离干净，两份文件标 `contentStatus=shell` 并排除出抽取。
§8.1 对齐规则已建，跨图连通验证通过。剩余问题见 §8。

## 8. 实施中新发现的问题（6 条已办，2 条新增）

### ✅ 已解决

1. **~~抽取关系边恒为 0~~** → 加了 **4b link 第二遍**：实体消解后把已解析实体清单
   喂回模型，只问关系。实测 `niddk-uacr-egfr` **0 → 20 条边，20 个候选全过 quote 校验**。
   `danglingRelationRate` 从 `n/a`（失效）变成 0.0909（活的）。`--no-link` 可跳过省 token。

2. **~~`DiagnosticThreshold` 缺开闭区间标志~~** → schema 加 `lowerInclusive` /
   `upperInclusive`。现在能**精确**表达而非按报告精度近似：
   「below 5.7%」= `upperBound 5.7 + upperInclusive false`（原写成 ≤5.6）；
   「more than 300 mg/g」= `lowerBound 300 + lowerInclusive false`（原硬凑成 301）。

3. **~~`classifiesInto` 错指 T2DM~~** → 新增 `dmoid:DM-Unspecified`（⊑ Diabetes，
   **刻意不进 AllDisjointClasses**——未分型病例日后可能归为 T1DM 或 T2DM，
   断言互斥会让「先记未分型、后补分型」这个正常流程推出不一致）。4 条边已改指。

4. **GDM 切点** → 拆成两半：
   - ✅ **妊娠期管理目标**语料里有全套（`niddk-pregnancy-preexisting-diabetes.txt:164-178`），
     已补 5 条（空腹 70–95 / 餐后 1h 110–140 / 2h 100–120 / CGM TIR 63–140 / A1C ≤6.5%）。
     此前 `populationContext="Pregnant"` 的目标**一条都没有**。
   - ❌ **GDM 的 OGTT 诊断切点仍缺**。NIDDK 原文只说「high two or more times」不给数值。
     缺的是 NIDDK「Gestational Diabetes → Tests & Diagnosis」子页，当前语料只抓了章节索引。
     **需要你决定是否补抓**——凭记忆补 IADPSG 的 92/180/153 是编造出处，不做。

5. **~~对齐覆盖率 4/9~~** → 补 seed（`LabTest-SCR`、`CKD` 并发症层次、
   `Microalbuminuria`/`Macroalbuminuria` 分期），并修了一个**分层错误**：
   `KidneyFailure`、药物类别、禁忌规则原先放在 `synthetic-patients.ttl` 里，
   而对齐规则只扫 tbox/seed，永远够不着——已移入 `dmo-axioms.ttl`。

6. **~~`Patient` 接不到 `ComplicationStage`~~** → 新增关系 `hasComplicationStage`
   （patient → complicationStage，many-to-many，带 `assessedDate`）。

### ⚠️ 新发现

7. **抽取的 URI 不可重现 —— 违反「构建必须幂等且可重复」。**
   同一篇文档跑两次，模型给的 `canonicalName` 风格完全不同：
   第一次 `"Type 1 Diabetes"` / `"Urine Albumin-to-Creatinine Ratio (UACR)"`，
   第二次 `"Type1Diabetes"` / `"UACR"` / `"CKD_A1"` —— 它把「规范名称」理解成了标识符。
   URI 是从 canonicalName 铸的，于是整个 ABox 的 URI 变了，对齐从 4 掉到 2，跨图连通断开。

   已做两层修：
   - **prompt 侧**：明确 canonicalName 是自然语言写法，不要驼峰/下划线/括号后缀。
     ⚠️ **未验证**——确认要再烧一次调用。
   - **规则侧**（真正管用的那层）：对齐比对时抹掉全部非字母数字，
     `Type1Diabetes` 与 `Type 1 Diabetes` 归一化后相等。**仍是精确匹配，不是编辑距离。**
     不依赖模型听话，对齐已恢复到 4。

   → 更彻底的修法是让 URI 不依赖模型输出（例如用 `sourceId + chunk + 序号` 铸 URI，
     canonicalName 只作 label）。但那样跨文档消解就完全靠对齐规则了，是个取舍。

8. **`mergeConflicts` 升到 9。** 属性冲突数随抽取量上升，目前只记账不处理。
   需要定一个冲突消解策略（先到先得 / 取多数 / 标记待人工）。

---

---

> ⚠️ 本项目仅用于技术学习，不是医疗器械，不构成任何医疗建议。所有产物均不包含具体用药剂量。
