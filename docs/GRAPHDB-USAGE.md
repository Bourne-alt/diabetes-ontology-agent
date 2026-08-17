# GraphDB 数据现状与使用说明

> 实测时间：2026-08-16　端点：`http://124.223.18.44:7200`　仓库：`dmo`
> 所有数字来自对该实例的实际 SPARQL 查询，不是从配置文件推断的。

本文分三部分：**一、怎么用**（连接、图布局、查询、重建流程）；**二、数据实际是什么状态**；
**三、动手前的检查清单**。

---

## 〇、2026-08-16 这一轮改了什么

进来时发现三条与文档不符的实测事实，现已全部处理：

| # | 文档/脚本声称 | 进来时实际是 | 现在 |
|---|---|---|---|
| 1 | ruleset = `owl2-rl-optimized` | `rdfsplus-optimized` | ✅ 已换成 `owl2-rl-optimized`（删库重建） |
| 2 | 规则层产出进 `urn:dmo:inferred` | 该图不存在（0 条） | ✅ 已物化 144 条 |
| 3 | `validationEnabled=false`，灌完再开 | `true`，且**关不掉** | ✅ 改用装载顺序规避，不再依赖这个开关 |

第 1 条的根因值得记一笔：`load_graphdb.py` 的 `create_repo()` 见到仓库已存在就直接
`return`，把自己写的 `repo_config()` 整个跳过。原来那个 `dmo` 仓库是用 Workbench 默认参数
建的（`baseURL` 停在 `http://example.org/owlim#` 是铁证），脚本从来没机会生效。
而验收里那条"推理机是否真的开着"用传递闭包做探针 —— **rdfs-plus 同样支持
`TransitiveProperty`，所以它永远通过，根本区分不出两种 ruleset**，给的是假的安全感。
现在 `create_repo()` 建完会回读 ruleset 并在不符时直接 `SystemExit`。

`--verify` 从 11 条检查增至 17 条，除一项纯转储外全部带断言，结果 **14 ✓ / 2 ✗**
（这一轮开始时是 1 ✗ —— 因为大部分检查根本不会失败）。

---

# 一、怎么用

## 1.1 连接

无鉴权，直接 HTTP。仓库 ID 固定为 `dmo`。

```bash
curl -s -H "Accept: text/csv" --data-urlencode \
  'query=SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }' \
  http://124.223.18.44:7200/repositories/dmo
```

Python 侧有两条路，**不要再写第三份 HTTP 封装**：

| 用途 | 模块 | 说明 |
|---|---|---|
| 构建/运维脚本 | [`ontology/tools/graphdb_http.py`](../ontology/tools/graphdb_http.py) | 纯标准库，零依赖 |
| 应用运行时 | [`src/dmo/graph/client.py`](../src/dmo/graph/client.py) | 走 `Config`，带 `sparql_csv()` / `ask()` / `construct_ttl()` |

**Accept 头有坑**：`ASK` 用 `text/csv` 会被拒成 406，必须
`application/sparql-results+json`；`CONSTRUCT` 用 `text/turtle`。

## 1.2 ⚠️ 命名图布局 —— 先读这一节，它决定你的查询对不对

| 图 URI | 三元组 | 内容 | 可信度 |
|---|---|---|---|
| `urn:dmo:tbox` | 2,202 | 手写公理 + 生成的类/属性骨架 | 高（人工） |
| `urn:dmo:seed` | 950 | 阈值 / 血糖目标 / 风险规则 / LabTest / SourcePassage | **最高**（人工策展 + 逐字出处） |
| `urn:dmo:sources` | 232 | source registry（26 份文档的元数据） | 高（机械） |
| `urn:dmo:extract:<sid>` ×50 | 62,520 | LLM 抽取产物，每份文档一图 | **参差**（见 §2.4） |
| `urn:dmo:inferred` | 144 | 规则层物化结果（当前全是 `alignedTo`） | 派生 |
| `urn:dmo:data` | 250 | 6 个合成患者 | **故意造错的反例夹具**，见下 |
| `urn:dmo:patient:<uuid>` | **0 个图** | 真实患者，每患者一图 | 未同步 |
| `…rdf4j#SHACLShapeGraph` | 242 | SHACL 形状 | 高 |

全库：**55 个命名图**，去重后 **79,563** 条（显式 59,649 + 推理 19,918）。

### 患者层有两套图，混淆它们是这套库上最贵的错误

- **`urn:dmo:data`** 装的是 6 个合成患者，每个都带 `demoScenario` 标签，
  其中 P005 缺单位、P006 单位不一致、P001 触发禁忌 —— 它们是**故意造错的
  SHACL 反例夹具**，用来验证形状和安全规则会不会误报/漏报。
- **`urn:dmo:patient:{uuid}`** 才是真实患者，由 `src/dmo/rdf/sync.py` 从 SQL 同步，
  每患者一图。**当前一个都没有。**

`ontology/rules/*.rq` 里除 `10-align` 外，患者侧一律写死：

```sparql
FILTER(STRSTARTS(STR(?pg), "urn:dmo:patient:"))
```

这是**刻意的守卫**，把夹具挡在结论层之外（`src/dmo/query/templates.py:7`、
`docs/API.md:350` 都记了这条）。

> ⚠️ **由此产生一个极易误判的现象**：没同步真实患者时，
> `20/21/30/40/50/51` 六条规则**全部零产出**。这是**正确行为**，不是规则坏了。
> 看到零产出就去掉前缀守卫，等于把故意造错的夹具喂进临床结论 —— 千万别。
> `--rules` 现在会在检测到 0 个患者图时直接把这段话打出来。

### 查询时要不要写 GRAPH

- **知识层（TBox / seed / 阈值 / 风险规则 / 术语）——不写 `GRAPH`。**
  让默认的图合并生效，也顺带吃到推理结果。
- **需要区分"这条事实来自哪份指南"——写 `GRAPH ?g` 并
  `FILTER(STRSTARTS(STR(?g), "urn:dmo:extract:"))`。**
- **患者事实——写 `GRAPH ?pg` + `urn:dmo:patient:` 前缀守卫**（真实患者），
  或显式 `GRAPH <urn:dmo:data>`（只在你确实想看夹具时）。

## 1.3 三条能直接抄的查询

**查一条阈值的完整证据链**（seed 层是唯一能逐字校验到原文的层）：

```sparql
PREFIX dmo: <https://example.org/dmo#>
SELECT ?th ?cls ?lowOp ?low ?upOp ?up ?unit ?hash ?src WHERE {
  ?th a dmo:DiagnosticThreshold ; dmo:classification ?cls ;
      dmo:thresholdCitesPassage ?p ; dmo:thresholdCitedFrom ?src .
  ?p dmo:contentHash ?hash .
  OPTIONAL { ?th dmo:lowerOperator ?lowOp ; dmo:lowerBound ?low }
  OPTIONAL { ?th dmo:upperOperator ?upOp ; dmo:upperBound ?up }
  OPTIONAL { ?th dmo:boundUnit ?unit }
}
```

⚠️ 边界必须按 `lowerOperator` / `upperOperator` 判定，**不能一律当闭区间**。
`A1C-NORMAL` 的 `upperOperator=LT`（5.7 本身属于 Prediabetes），
`A1C-PREDIABETES` 是 `LTE`。用 `<=` 一把梭会把 5.7 判成正常。

**按文档追溯某个概念的出处：**

```sparql
PREFIX dmo: <https://example.org/dmo#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?g ?e ?label ?quote WHERE {
  GRAPH ?g { ?e a dmo:Contraindication ; rdfs:label ?label ; dmo:evidenceQuote ?quote }
  FILTER(STRSTARTS(STR(?g), "urn:dmo:extract:"))
} LIMIT 20
```

**用药安全检查（V2 七跳，当前唯一能自动判定的禁令）：**

```sparql
PREFIX dmo: <https://example.org/dmo#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?pid ?drug ?cond WHERE {
  ?p dmo:patientId ?pid ; dmo:hasMedicationUse ?mu ; dmo:hasDiagnosis ?dx .
  ?mu dmo:usesMedication ?m .
  ?m  dmo:belongsToDrugClass ?c .
  ?c  dmo:hasContraindication ?k ; rdfs:label ?drug .
  ?k  dmo:severity 'Absolute' ; dmo:triggeredByCondition ?cond .
  ?dx dmo:clinicalStatus 'Active' ; dmo:diagnosisComplication ?cond
}
```

返回 1 行：`P001 / SGLT2 Inhibitors / KidneyFailure`。这是夹具刻意造的阳性例，
**不是**发现了真实的用药风险。（注意这条没写图守卫，所以扫得到夹具 —— 它是验收查询，不是产品查询。）

⚠️ **V1 谓词已废弃**：`dmo:takesMedication`、`dmo:hasComplication`、`dmo:hasDiabetesType`
在全库使用次数均为 **0**。沿用它们的查询会永远返回空 —— 而空结果和"没有违规"长得一模一样。
`--verify` 已加了一条断言盯这个。

## 1.4 重建流程

```bash
python3 ontology/tools/build_tbox.py --src ontology/graph/diabetes-ontology-v2.json \
                                     --out ontology/dist/tbox-v2.ttl
python3 ontology/tools/semantic_extract.py     # 产出 dist/extract/<sid>/<sid>.ttl
cd ontology/tools
python3 load_graphdb.py --create               # 仓库已存在则跳过
python3 load_graphdb.py --load                 # 按命名图整图 PUT
python3 load_graphdb.py --rules                # 产出 urn:dmo:inferred
python3 load_graphdb.py --verify
```

四点必须记住：

1. **一律 `PUT`（整图替换），不用 `POST`。** 多个源文件指向同一命名图时，
   必须先在客户端合并再 PUT，否则后一个文件会把前一个冲掉。
2. **`--rules` 逐条物化，顺序有意义。** `30` 读 `20` 的产出，`51` 读 `40`/`50` 的产出。
   攒到最后一起 PUT 的话，`30` 查到的是上一轮的结果，首次跑必然空且不报错。
3. **`*-unreliable.rq` 默认不跑。** 它们处理 `valueTrustLevel="Unverified"` 的值，
   结论强制 `Indeterminate`。默认跑会用 1300+ 条随机检验的 Assessment 淹没有意义的结论。
4. **改 ruleset 必须删库重建**（GraphDB 建仓时定死）。`--create` 现在会回读校验，
   不符直接退出，不会再出现"脚本以为建了、实际是别人用默认参数建的"。

### ⚠️ SHACL 校验的开关是坏的，别指望它

`validationEnabled` 在这个 GraphDB 11 实例上**关不掉**：

- 建仓时 `repo_config()` 传 `"false"` 被忽略，建完读回来是 `true`；
- 事后 `PUT /rest/repositories/dmo` 改它返回 **200，值纹丝不动**。

所以 §4.2「先关校验灌数据，灌完再开」这条路在本实例上走不通，
而脚本原来还会打印一句"SHACL 暂关"——那是假的，已删。

**改用不依赖开关的办法**：SHACL 校验只在 shapes 图非空时才触发，
所以 `collect()` 强制把 `SHACLShapeGraph` 排到装载序列**最末尾**，
前面 54 个图写入时 shapes 图还是空的，校验无从触发。效果等价于"先关后开"，
且不依赖任何配置项。实测 55 个图全部装载成功，零 SHACL 报错。

---

# 二、数据实际是什么状态

## 2.1 TBox 与推理

75 个 `owl:Class`（`dmo:` 下 32 个顶层类）、51 个 `owl:ObjectProperty`、
133 个 `owl:DatatypeProperty`、15 个 `owl:FunctionalProperty`、1 个 `owl:TransitiveProperty`。
V2 care-chain 五类齐全。术语层 33 个 SKOS ConceptScheme。

**换 ruleset 的收益是实打实的**：

| | rdfs-plus（换之前） | owl2-rl（现在） |
|---|---|---|
| 推理三元组 | 533 | **19,918** |
| 全库合计 | 60,165 | **79,563** |

## 2.2 ✅ 两条 OWL 公理从死代码变成有产出

进来时 `dmo-axioms.ttl` 里的 `propertyChainAxiom` 和 `equivalentClass` 推出 **0 条**。
根因有两层，**修一层不够**：

1. `rdfsplus-optimized` 不支持 `propertyChainAxiom` 和 `someValuesFrom` 的类成员推理；
2. 更根本的是，链首谓词 `dmo:hasComplication` / `dmo:hasDiabetesType`
   **全库使用次数为 0** —— V2 改 care-chain 后公理没跟着改。

现在两层都修了。公理改为：

```
hasAffectedOrgan ← (hasDiagnosis ∘ diagnosisComplication ∘ affectsOrgan)
DiabetesPatient  ≡ Patient ⊓ ∃hasDiagnosis.(∃diagnosisType.Diabetes)
InsulinDependentPatient ≡ Patient ⊓ ∃hasDiagnosis.(diagnosisType hasValue T1DM)
```

**过程中撞上一个 punning 的坑，值得单独记**：`someValuesFrom dmo:Diabetes`
检查的是**个体的 `rdf:type`**，而 `dmoid:T1DM` 只有 `rdfs:subClassOf dmo:Diabetes`
（那是它作为**类**的一面），没有 `a dmo:Diabetes`。少了这条断言，谓词改对了照样推 0 条。
`dmo-axioms.ttl` 新增 §1a 给 T1DM/T2DM/GDM/MODY/DM-Unspecified 补 `a dmo:Diabetes`，
**Prediabetes 刻意不补**。

GraphDB 实测（与本地 `owlrl` 全闭包结果完全一致）：

| | 修复前 | 现在 |
|---|---|---|
| `hasAffectedOrgan` | 0 | P001 → Kidney、P002 → Kidney |
| `DiabetesPatient` | 0 | P001–P006 共 6 个 |
| `InsulinDependentPatient` | 0 | P004 |
| 反例守卫 `Prediabetes a/⊑ Diabetes` | false | **仍为 false** ✅ |

另外修正了一处**已失效的旧注释**：它说"`hasDiabetesType` 的函数性 + 互斥 ⟹
断言两个分型推出不一致"。V2 把分型挂到 `Diagnosis` 上后，一个患者可以有多个
`Diagnosis`、各自函数性成立、跨 `Diagnosis` 不会合并 —— **这条推理链在 V2 下已经断了**。
M2 的可执行替代品是 `clinical-safety.shacl.ttl` 的分型唯一性形状。
`docs/DESIGN.md` 和 `SEMANTIC-LAYER-PLAN.md` 里对应的表格行也已更正。

## 2.3 规则层：144 条，其中患者侧全零（符合预期）

```
10-align-extracted.rq: +144 条
20-lab-assessment.rq:    +0 条   ← 零产出
21-target-attainment.rq: +0 条   ← 零产出
30-diagnosis-…:          +0 条   ← 零产出
40-contraindication-…:   +0 条   ← 零产出
50-risk-factor-hit.rq:   +0 条   ← 零产出
51-risk-stratification:  +0 条   ← 零产出
```

**六条零产出是对的** —— 原因见 §1.2 的患者图守卫。要让它们出结果，
先跑 `dmo rdf sync` 同步真实患者。

> **顺带修了 `run_rules()` 一个真 bug**：它原来按「Turtle 里以 `.` 结尾的行数」估条数 ——
> 而 **`@prefix` 声明行也以 `.` 结尾**。于是零产出的规则被报成"CONSTRUCT 出 ~8 条"
> （那 8 条是 8 行前缀声明），六条规则全部空转却看起来都在干活，
> 汇总还打印了个"共 ~145 条"。现在改成查图的**实际增量**，准确且顺带验证写入落库。

### 对齐覆盖率：87 个实体 / 1.3%

`10-align-extracted.rq` 命中 87 个抽取实体、42 个规范个体（144 条三元组）。分布：

| 类型 | 对齐数 | 该类抽取总数 |
|---|---|---|
| `LabTest` | 31 | 202 |
| `Complication` | 27 | 196 |
| `DiabetesType` | 21 | 67 |
| `DrugClass` | 8 | 138 |
| 其余全部类型 | **0** | — |

`Recommendation`(2,615)、`RiskFactor`(600)、`Contraindication`(359)、`Medication`(324)
一条都对不上。

**瓶颈不在匹配口径，在 canonical 一侧的词表只有 42 个个体。**
规则本身做了三层归一化（去括号补注、抓缩写、抹非字母数字）并吃 `skos:altLabel`，已经不严；
`Recommendation` 对不上是因为 seed/tbox 里**根本没有**规范的 Recommendation 个体。
`dmo-axioms.ttl` §9 的标题「补概念，不放宽匹配」诊断是对的 —— 放宽只会制造错对，
而错对是不可逆的数据污染。**提高覆盖率是补 seed 词表的领域策展工作。**

## 2.4 ⚠️ 抽取层质量分布极不均匀，出处机制与 seed 层不等价

50 个抽取图，6,594 个实体。管线口径（50 份 `report.json` 汇总）：

```
rawRecords 11,118  →  accepted 8,049  (拒绝 3,069，拒绝率 27.6%)
entities    6,594     edges     1,996     danglingRelations 2,237
```

**`danglingRelations` (2,237) 比 `edges` (1,996) 还多。** 模型给出的关系里超过一半
指向了不存在的实体。6,594 个实体之间只有不到 2,000 条边，连通性很差 ——
这解释了为什么绝大多数查询只能做单跳属性检索。

**`quoteHitRate`（原文逐字命中率）：中位数 0.82，均值 0.74，48 个有效源里 22 个低于 0.8。**

| 源 | quoteHitRate | raw → accepted |
|---|---|---|
| `nhc-adult-diabetes-dietary-guide-2023-qa` | **0.0** | 43 → **0** |
| `nhc-adult-diabetes-dietary-guide-2023` | 0.128 | 156 → 20 |
| `kdigo-2025-commentary-glp-1-…` | 0.237 | 59 → 14 |
| `ada-kdigo-consensus-report-…-2022` | 0.364 | 503 → 183 |
| `kdigo-2022-clinical-practice-guideline-…` | 0.491 | 1,839 → 902 |

两个规律都值得警惕：

- **中文源系统性失败。** `nhc-gdm-nutrition-2018` / `nhc-gdm-weight-standard-2023` /
  `nhc-adult-diabetes-dietary-guide-2023-qa` 三份最终接受 **0 条**记录，
  却各自装载了 12 条 PROV 骨架。查 `GuidelineSource` 时它们**在**，查事实时它们**空**。
- **越权威的长文档抽得越差。** KDIGO 2022（1,839 条原始记录，全库最大）命中率仅 0.49。
  分块策略在长 PDF 上明显退化，而这些恰好是临床价值最高的来源。

**出处机制是两套，且不等价：**

| 层 | 机制 | 可逐字校验？ |
|---|---|---|
| `urn:dmo:seed` | `SourcePassage` + `contentHash`（31 个，100% 带 hash） | ✅ |
| `urn:dmo:extract:*` | `dmo:evidenceQuote` 字符串 + `prov:wasDerivedFrom` | ❌ |

抽取层有 7,836 条 `evidenceQuote`，但 **0 条**指向 `SourcePassage`，无 `contentHash`、无 span。
而验收里"每条诊断阈值都有出处片段"只覆盖 seed 的 **17 条阈值**，
对 2,615 条 `Recommendation`、359 条 `Contraindication` **零约束** ——
这条验收给出的安全感和它的实际覆盖面严重不匹配（现已在 note 里写明）。

**建议**：不要因为验收全绿就把抽取层当成可直接引用的临床结论。
建议以 `quoteHitRate ≥ 0.8` 作为"可自动引用"的门槛，低于此的源在下游必须走人工确认。
这个分级现在没有落到图里，可以把 `report.json` 的 `quoteHitRate` 写成
`GuidelineSource` 上的一个数据属性，让查询侧能直接过滤。

## 2.5 ⚠️ 仍未解决：source registry 只覆盖 26/50

`urn:dmo:sources` 里 26 个 `GuidelineSource` 带完整元数据，但全库有 **50 个** ——
另外 24 个是抽取脚本自铸的骨架，只有 `localFile` / `sha256` / `byteSize`。

后果：按 `dmo:publisher` 或 `dmo:publishedYear` 筛选会静默漏掉近一半来源，
其中包括 JBDS 全系列和几份 VADoD。这是"空结果长得像没有匹配"的又一例。
`--verify` 已加断言（当前 `n_unregistered=24`）。

## 2.6 验收现状：14 ✓ / 2 ✗

`--verify` 这一轮从 11 条增至 17 条检查。除"各命名图三元组数"这一项纯转储外
**全部带断言**，支持 `==` / `>=` / `>`，并支持对非 COUNT 查询断言**结果行数**
（`("*", ">=", 1)`）。失败项在末尾单独汇总到 stderr，不再淹没在几十行转储里。

新增的 6 条全部针对"空结果长得像正常"这个反复出现的失败模式：

- ⚙️ **ruleset 探针** `hasAffectedOrgan` —— `owl2-rl` 独有，同时验 ruleset、公理谓词、数据通路
- ⚙️ **`urn:dmo:inferred` 非空** —— 规则层是否真的跑过
- ⚙️ **V1 废弃谓词零使用**
- ⚠️ **source registry 覆盖率**
- ⚠️ **空壳抽取图**
- ⚠️ **阈值边界算子齐全**

| 检查 | 结果 |
|---|---|
| TBox 类数量（≥70） | ✓ 75 |
| 推理机没关（传递闭包） | ✓ |
| ⚙️ ruleset 探针 `hasAffectedOrgan` | ✓ **2**（P001/P002 → Kidney） |
| ⚙️ V1 废弃谓词零使用 | ✓ 0 |
| 子类闭包 T1DM ⊑ Diabetes | ✓ |
| ⚙️ `urn:dmo:inferred` 非空 | ✓ 144 |
| 抽取实体对齐条数（≥80） | ✓ **87** |
| 跨图连通：抽取 T2DM → 公理 Diabetes | ✓ **true**（孤岛已打通） |
| S6 禁忌七跳（≥1 行） | ✓ 1 行（P001） |
| ⚠️ 反例：Prediabetes ⋢ Diabetes | ✓ false |
| V2 care-chain 五类齐全（=5） | ✓ |
| 诊断阈值出处（=0 缺失） | ✓ **仅覆盖 seed 的 17 条，见 §2.4** |
| 风险规则悬空引用（=0） | ✓ |
| 阈值边界算子齐全（=0） | ✓ |
| **⚠️ source registry 覆盖** | ✗ 24 未登记（期望 0） |
| **⚠️ 空壳抽取图** | ✗ 3 个（期望 0） |

剩下这 2 项是**内容缺口**，不是流水线问题：补 registry 元数据、修中文 PDF 抽取。
两件都是领域工作。**不要为了让它变绿而放宽阈值。**

---

# 三、动手前的检查清单

1. **你查的是哪套患者图？** `urn:dmo:patient:*`（真实，当前 0 个）还是
   `urn:dmo:data`（6 个故意造错的夹具）。混淆这两个是这套库上最贵的错误。
2. **规则零产出先别改规则。** 患者侧规则零产出通常是因为没同步真实患者，
   去掉前缀守卫会把夹具喂进临床结论。
3. **谓词在 V2 里还活着吗？** `hasComplication` / `hasDiabetesType` / `takesMedication` 已死。
4. **查阈值时按 `lowerOperator` / `upperOperator` 判边界**，别一律当闭区间。
5. **结果为空时**，先确认是"真没有"还是"图名/谓词写错"—— 这套图上两者不可区分。
6. **引用抽取层结论前**，先看该源的 `quoteHitRate`（`dist/extract/<sid>/report.json`）。
7. **改 ruleset 必须删库重建**，且要先备份（`GET /repositories/dmo/statements?infer=false`
   导出 n-quads）。
8. **`--verify` 现在每条检查都会真失败。** 当前那 2 个 ✗ 各自对应一件没做完的事，
   修好一件绿一条。
