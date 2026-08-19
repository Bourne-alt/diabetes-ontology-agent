# 图探索 / 规则 / 溯源族端点：参数与返回体字段

九个端点。读之前先确认 SKILL.md 的七条硬禁令，本文件只补字段细节。

**贯穿全族的两个字段**，每个端点都有，每次都要读：

| 字段 | 读法 |
|---|---|
| `nextHops[]` | 服务端替你算好的下一跳：`{rel, endpoint, why}`。**照它走，不要自己拼 IRI** |
| `emptyReason` | 空集是哪一种空。**返回 0 条时先读它，不许直接回答"没有"** |

---

## `GET /graph/concepts` — 所有图探索的唯一入口

| 参数 | 说明 |
|---|---|
| `q` | 必填。中文表面形式 / 编码 / 英文 label |
| `kind` | 选填。`LabTest` / `Medication` / `RiskFactor` … |
| `limit` | 默认 20 |

返回体里 **`usable`** 是关键：`true` 才参与判定。`false` 时**必须**继续
`GET /terms/explain?term=…` 说明是四类归宿的哪一类
（`verified` / `candidate` / `unmappable` / `no-source-data`）。

匹配范围是本体 `rdfs:label` / `skos:altLabel` **∪** 三张人工映射表的上游中文名 ——
纯 SPARQL 版本查不到「糖化血红蛋白」，那个字符串只存在于 `map_lab_term.src_name`。

---

## `GET /graph/node` — 邻接摘要

参数：`iri`（必填，**来自上一步返回体**）。

| 字段 | 读法 |
|---|---|
| `types[].assertedIn` | 空数组 = 这个类型是推理机推的，不是任何文件里写的 |
| `types[].inferredOnly` | `true` ⟹ **不许说"本体里声明了它是这个类"** |
| `outEdges` / `inEdges` | 谓词 + 计数。计数大的先展开，别一条条试 |

⚠️ 传入 `urn:dmo:data` 里的反例夹具 IRI 会**被拒绝并说明原因**（不是静默过滤）。

---

## `GET /graph/neighbors` — 一跳展开

| 参数 | 说明 |
|---|---|
| `iri` | 必填 |
| `predicate` | 选填。不给则全部谓词 |
| `direction` | `out` 取对象 / `in` 取主语，默认 `out` |
| `limit` | 默认 50 |

`fixtureFiltered` 非空 = 本次过滤掉了反例夹具，**在回答里提一句**，别让读者以为返回是全集。

---

## `GET /graph/taxonomy` — 类层次

| 参数 | 说明 |
|---|---|
| `iri` | 必填 |
| `direction` | `up` 上位 / `down` 下位，默认 `up` |
| `depth` | 默认 3 |

`inferenceNotice` 指出哪几条边**不在任何文件里写着、是 owl2-rl 推出来的**。原样带上。

---

## `GET /graph/path` — 两点怎么连上的

| 参数 | 说明 |
|---|---|
| `from` | 必填（查询串里就写 `from`） |
| `to` | 必填 |
| `maxHops` | 默认 3 |

服务端做双向受控 BFS，跳数与每跳前沿都封顶 —— 不放任意长度属性路径出去，因为
`?a (<>|!<>)* ?b` **写错了不报错，只是跑很久然后超时**。

遍历刻意跳过 `rdf:type` 与 `owl:sameAs`：任意两节点都是 `owl:Thing`，经它们"连通"
的全是伪相关。找不到路径时，`emptyReason` 会说明是超跳数还是真不连通。

---

## `GET /graph/schema` — RDF / SQL / 桥接卡片

参数：`section` = `rdf` / `sql` / `bridge`，不给则全给。

`bridge` 段的 39 对列↔谓词由 `rdf/emit.py` 的 **AST 静态解析**得到，不可能与实际发射
逻辑分叉。同时给出**值变换**：

> `core_patient.sex` 的 `M`/`F` 在 RDF 侧已经是 `Male`/`Female` —— **按 `M` 查一条不返。**

写任何跨层查询前先看这里。

---

## `GET /graph/passages` — 可引用出处检索

| 参数 | 说明 |
|---|---|
| `sha256` | 按内容哈希精确查 |
| `q` | 引文子串（规范化后、大小写不敏感） |
| `passageId` | 按 id |
| `citedBy` | `thresholdId` 或 `riskRuleId` —— **反查"这条规则引了哪句原文"** |
| `limit` | 默认 50 |

与 `/adjudicate/citations` **共用底表**（`urn:dmo:seed` 里那 31 条，
由 `verify_passages.py` 逐字回原文校验过）。

---

## `GET /graph/rules` — 规则内省

| 参数 | 说明 |
|---|---|
| `kind` | `threshold` / `target` / `risk` |
| `q` | 文本筛 |
| `executable` | 规则链的 WHERE 真的匹配得上吗 |
| `countsInTier` | 风险规则：有逐字出处、真正计分吗。**`false` 查出的就是"命中也不计分"那批** |
| `concept` | 按检验项筛，如 `A1C` / `FPG` |
| `context` | 人群语境：`NonPregnant` / `Pregnant` / `Any` |
| `limit` | 默认 50 |

`counts` 段如实报三个落差（阈值 17/17、风险规则 **73 → 12 → 10**）：

```jsonc
"risk": { "declared": 12, "executable": 12, "countsInTier": 10,
          "classAssertions": 73, "inferenceArtifacts": 61 }
```

- `declared → countsInTier` 差额 = 拿不出逐字出处的规则（当前 `ICD-HYPERTENSION`、
  `ICD-DYSLIPIDEMIA`），产出 Hit 但不计入 tier；
- `classAssertions → declared` 差额 = prp-dom 反推的产物，**不是规则**。

`citationCaveat`（`kind=target` 的 10 条原文存在 `rdfs:comment` 里，不是 `SourcePassage`、
没有 `contentHash`，`/adjudicate/citations` 核不了）—— **原样带进回答**。

### `GET /graph/rules/{rule_id}`

单条规则全貌，出处展开成完整 passage（含 `quote` 与 `sha256`）。
404 ⟹ 规则号不存在，回 `GET /graph/rules` 看全量清单，**不要猜另一个 id**。

---

## `GET /graph/provenance` — 反向溯源

参数：`iri`（必填，**结论节点**）。

| 字段 | 读法 |
|---|---|
| `kind` | 五类可溯源结论之一：`Assessment` `Diagnosis` `RiskFactorHit` `ContraindicationFlag` `RiskStratification` |
| `assertedTypes` | **断言的**类型（在命名图里）。推出来的不在这里 |
| `patient` | `{patientId}` 或 null |
| `chain[]` | `{step, role, kind, iri, detail}`。`role` 取值：`conclusion` / `supportedBy` / `appliesThreshold` / `basedOnLabResult` / `citesPassage` / `sqlRow` |
| `evidence[]` | 逐字 `quote` + 完整 `sha256`。**只能原样复制** |
| `sqlRows` | 回查到的 `stg_*` / `core_*` 原始行 |
| **`brokenLinks`** | ⚠️ 非 null ⟹ 证据链不完整。**与 `chain` 同等重要，必须报** |
| `graphVersion` | 变了 ⟹ 结论作废重查 |

### `kind: null` 时怎么办

返回体的 `emptyReason` 会说清：这个 IRI 断言的类型是什么、可溯源的有哪几类，并提醒

> 别拿 `?x a dmo:Assessment` 去找结论 —— prp-dom 会把每条患者命中记录也判成 Assessment。

按 `nextHops` 走 `GET /graph/node?iri=…` 先看它到底是什么。

### 三类实测断链

| 断链 | 后果 |
|---|---|
| 禁忌的 `rationale` 是抽取产物的裸字符串，不是带 `contentHash` 的 SourcePassage | `/adjudicate/citations` 核不了 |
| 上游直接断言的诊断（`factOrigin=ehr-legacy`）没有 Assessment 支撑 | 不是本系统推出来的，只是照抄上游 |
| 无 `riskRuleCitesPassage` 的风险规则产出 Hit | 不计入 tier（`51-risk-stratification.rq` 信号 5） |

---

## `POST /graph/sparql` — 逃生口

```jsonc
{"query": "SELECT ?x WHERE { … } LIMIT 20"}
```

### 六条静态检查（guard）

| 规则 | 检测 | 处置 |
|---|---|---|
| **A 患者图守卫** | 每个 `GRAPH ?var` 是否被 `STRSTARTS(STR(?var),"urn:dmo:patient:")` 约束 | **拒**，理由里给出该补的那一句 |
| **B 知识侧禁具名图** | `GRAPH <urn:dmo:seed｜tbox｜sources｜inferred｜extract:*>` | **拒** —— 会静默少返 |
| **C 反例夹具** | 出现 `urn:dmo:data` | **拒** |
| **D 写操作** | 非 SELECT/ASK/CONSTRUCT/DESCRIBE，或含 INSERT/DELETE/DROP/… | **拒** |
| **E 行数上限** | 无 `LIMIT` → 追加 200；超过 200 → 改写为 200 | 记进 `rewrites`，**不算失败** |
| **F 全库扫描** | 触及患者图但没有 `VALUES` / 具体患者 IRI 收敛 | 警告，不拒 |

拒绝理由是**写给模型看的** —— 它会作为 observation 回来让你自我修正。照它改，
不要绕过、不要换个写法硬试。

### 返回体

| 字段 | 读法 |
|---|---|
| `rows` | 结果行 |
| `rewrites` | 非空 ⟹ 查询被改写过（通常是 LIMIT）。**在回答里说明结果被截断** |
| `warnings` | 规则 F 的告警等 |
| `zeroResultProbe` | 0 行时的降级探针结论，如"该患者图里有 10 条三元组，0 行大概率是图模式写错了" |

**空集与"有但判不了"是两回事。** 拿到 0 行先读探针，不要直接回答"没有数据"。

### 常用查询骨架：从患者号查结论 IRI

```sparql
PREFIX dmo: <https://example.org/dmo#>
SELECT ?pid ?concl WHERE {
  VALUES ?pid { "P90002" }
  GRAPH ?pg {
    ?p dmo:patientId ?pid .
    ?p dmo:hasDiagnosis|dmo:hasAssessment ?concl
  }
  FILTER(STRSTARTS(STR(?pg), "urn:dmo:patient:"))
} LIMIT 20
```

那句 `FILTER` 是规则 A 的守卫，少了它直接被拒。

---

## `GET /agent/manifest` — 能力清单

无参数。端点清单从 `app.routes` 现场生成，**不可能与实际服务分叉**。

`coverage.ontology.assessableLabTests` 是**可判定边界**：只有表内的检验项挂了阈值。
用户问表外的项时直接说本库判不了并走 `/terms/explain`，
**不要逐个去试概念解析和阈值判定**。
