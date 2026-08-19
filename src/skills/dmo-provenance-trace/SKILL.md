---
name: dmo-provenance-trace
description: 在糖尿病本体图上逐跳探索概念关系，并把一条结论反向溯源到指南原文哪一句、数据库哪一行。当用户问「凭什么这么说」「这条结论的依据是哪句原文」「规则第几版、是怎么判的」「这两个概念怎么连上的」「某个概念的上下位是什么」「哪些结论其实没有出处」，或需要理解 RDF/SQL 列—谓词映射、需要动用自由 SPARQL 逃生口时使用。本 skill 规定了图探索的四步铁律（概念→节点→一跳/层次/路径，IRI 只能来自上一步）、chain/evidence/brokenLinks 必须同读、推理产物与断言类型的区分（prp-dom 会多报六倍），以及 SPARQL 静态检查的六条与零结果探针的读法。Use when tracing a conclusion back to its verbatim guideline provenance, exploring the ontology graph hop by hop, or introspecting the rules behind a judgement.
license: 与本仓库同许可
compatibility: 需要本仓库的 dmo 服务在 127.0.0.1:8100 可达（uv run dmo serve）；依赖 GraphDB（装了本体的那个仓库），SQL 回查环节还需要 PostgreSQL
allowed-tools: Bash(curl:*) Bash(uv:*) Read
metadata:
  repo: diabetes-ontology-agent
  version: "1.0"
---

# 图探索与反向溯源

## 这个 skill 在优化什么

**只报走通的环节，等于在暗示「这条结论有出处」。**

溯源层的价值全在 `brokenLinks` 上。走通的链谁都会展示；本仓库的差异化是把断掉的那一环
也摆出来，并说清它为什么断。你如果只渲染 `chain`，就把这个 skill 用反了。

图探索层的价值在**不给你一门查询语言**。GRAPH 子句由服务端拼，你只决定下一跳查什么 ——
因为自由 SPARQL 写错 `GRAPH` 子句会**静默少一半结果，不报错**。

## 硬禁令

1. **不猜 IRI。** 每一步的 IRI 都必须来自上一步的返回体。自己拼造的 IRI 查出来是空集，
   而空集和"这个概念不存在"长得一模一样。
2. **`quote` / `sha256` 只能从返回体原样复制。** 返回体里没有的引文，一个字都不许写。
   禁止"根据指南通常认为…"这类无出处句式。
3. **`chain`、`evidence`、`brokenLinks` 必须一起读、一起报。** `brokenLinks` 非空
   意味着证据链不完整，必须明确说出来。
4. **不拿 `rdf:type` 当"声明了这个类"用。** 见下面 prp-dom 那节。
5. **自由 SPARQL 是第 13 个工具，不是第 1 个。** guard 返回 400 时**照抄拒绝理由并按它
   给的修正句改**，不要绕过检查、不要换个写法硬试。
6. **`usable: false` 时，概念存在不代表能用于判定。** 继续调 `/terms/explain` 说明原因。
7. **只读。** 只提交 `SELECT`/`ASK`/`CONSTRUCT`/`DESCRIBE`，不查反例夹具，不做无界遍历。

## 调用约定

服务基址 `http://localhost:8100`（`uv run dmo serve --port 8100` 启动，只绑 127.0.0.1）。
**本 skill 不带封装脚本** —— 下面每条都是可直接粘贴的完整 curl，因此这四件事由你自己负责：

1. **连不上 ≠ 没有数据。** curl 报 `Connection refused` ⟹ 服务没起，先启动它，或全程
   改用 `uv run dmo …` CLI（**与 API 走同一份 `query/hybrid.py`，答案必然一致**）。
   **绝不因为够不着服务就改用常识作答。**
2. **必须看 HTTP 状态码**，别把 `{"detail":"…"}` 当数据读。排查时加
   `-w '\n-- HTTP %{http_code} --\n'`。
3. **POST 必须带 `-H 'Content-Type: application/json'`**，body 形状见各阶段示例。
4. 状态码分支：

   | 码 | 含义与处置 |
   |---|---|
   | **400** | `/graph/sparql` 的 guard 静态检查未通过。`detail` 里**给了该补的那一句**，照它改 —— 最常见是缺患者图守卫 `FILTER(STRSTARTS(STR(?pg),"urn:dmo:patient:"))`。**不要绕过检查、不要换个写法硬试**。图探索族 400 通常是 IRI 不合法或指向了反例夹具 |
   | **404** | 规则号不存在。`GET /graph/rules` 看全量清单，**不要猜另一个 id** |
   | **422** | 参数类型不合法 |
   | **503** | GraphDB 不可用 ⟹ 本 skill 全部停 |
   | **500** | PG 断连 ⟹ 溯源的 `sqlRows` 回查环节失效，**明确说这一环缺失**，不要当成"没有原始行" |

## 阶段 1 · 图探索四步铁律

**顺序不可颠倒，IRI 只能来自上一步。**

```bash
# ① 表面形式 → 准确 IRI（所有图探索的唯一入口）
curl -sS 'http://localhost:8100/graph/concepts?q=糖化血红蛋白'

# ② 邻接摘要：类型、所在图、出边/入边 + 计数
curl -sS 'http://localhost:8100/graph/node?iri=<①返回的 iri>'

# ③ 按需展开
curl -sS 'http://localhost:8100/graph/neighbors?iri=…&predicate=…&direction=out'
curl -sS 'http://localhost:8100/graph/taxonomy?iri=…&direction=up&depth=3'
curl -sS 'http://localhost:8100/graph/path?from=…&to=…&maxHops=3'
```

### `/graph/concepts`：并集才是重点

匹配的是本体的 `rdfs:label` / `skos:altLabel` **∪** 三张人工映射表里的上游中文名。
纯 SPARQL 版本查不到「糖化血红蛋白」—— 那个字符串只存在于 `map_lab_term.src_name`。

返回体的 **`usable`** 字段说明这个映射到底参不参与判定：A1C 在本体里有概念、有三条阈值，
但上游全库一条数值都没有，`verify_status=no-source-data` ⟹ `usable: false`。
**查得到 ≠ 判得了。** 这时继续调 `/terms/explain?term=X` 给出四类归宿之一。

### `/graph/node`：哪些类型是推理机推的

`assertedIn` 拿不到图名的类型，就是 owl2-rl 物化出来的：

```jsonc
{"short":"dmo:RiskFactorHit","assertedIn":["urn:dmo:inferred"],"inferredOnly":false}
{"short":"dmo:RiskRule",     "assertedIn":[],                  "inferredOnly":true}
```

后者是 **prp-dom** 顺着 `dmo:triggerBasis` 的 `rdfs:domain` 反推的 —— 一条患者命中记录
被判成了一条风险规则。回答里区分"声明的"与"推出来的"，别把 `inferredOnly: true` 说成
"本体里定义了它是 RiskRule"。

### `/graph/path`：为什么不放任意长度属性路径

`?a (<>|!<>)* ?b` 在十万三元组上没有封顶，**写错了不报错、只是跑很久然后超时** ——
又一种静默失败。所以路径由服务端做双向受控 BFS，跳数与每跳前沿都封顶。

遍历刻意跳过 `rdf:type` 与 `owl:sameAs`：任意两个节点都是 `owl:Thing`，经它们"连通"
的全是伪相关。实测一条检验结果到指南原文是三跳：

```
dmo:measuredByTest        → LabTest-A1C
dmo:hasThreshold          → threshold/A1C-DIABETES
dmo:thresholdCitesPassage → sourcePassage/A1C-DIABETES-Q
```

### 服务端替你兜住的三件事（不要自己再实现一遍）

| 情况 | 服务端做法 |
|---|---|
| 反例夹具（`urn:dmo:data` 里 6 个故意造错的合成患者，IRI 长得跟真患者一样） | `/graph/node` 与 `/graph/provenance` **拒绝并说明**；`/graph/neighbors` 过滤时在 `fixtureFiltered` 里明说 —— 悄悄过滤和静默少返是一回事 |
| 空节点（owl 限制类的 skolem ID 每次装载都变） | 一律滤掉 |
| 自反 `owl:sameAs` | 物化噪声，滤掉，不占 nextHop |

### 需要理解 RDF / SQL / 列↔谓词映射时

```bash
curl -sS 'http://localhost:8100/graph/schema?section=bridge'   # 39 对列↔谓词，由 emit.py 的 AST 静态解析得到
```

⚠️ 桥接表同时给出**值变换**：`core_patient.sex` 的 `M`/`F` 在 RDF 侧已经是
`Male`/`Female`，**按 `M` 查一条不返**。写任何跨层查询前先看这里。

## 阶段 2 · 规则内省：凭什么这么判

```bash
curl -sS 'http://localhost:8100/graph/rules?kind=risk&countsInTier=false'
curl -sS 'http://localhost:8100/graph/rules/A1C-DIABETES-NONPREG'
```

`/patients/{pid}/assessment` 回答"判成什么"，这里回答"凭什么这么判"。

### ⚠️ `?r a dmo:RiskRule` 会多查出六倍

```
?r a dmo:RiskRule                  → 73 条
?r a dmo:RiskRule ; dmo:riskRuleId → 12 条   ← 真正被规则链消费的
```

原因同上：prp-dom 把每个 `RiskFactorHit` 都反推成了一条风险规则。查询不报错、不告警，
**只是数字大了六倍**。本端点一律以**声明标记**（`riskRuleId` / `thresholdId` / `targetId`）
为准，不看 `rdf:type`。你自己写 SPARQL 时也必须带上声明标记那一句。

### 三个必须读懂的数字

```jsonc
"risk": { "declared": 12, "executable": 12, "countsInTier": 10,
          "classAssertions": 73, "inferenceArtifacts": 61 }
```

- `declared → countsInTier` 的差额 = **拿不出逐字出处的规则**，产出 `RiskFactorHit`
  但不计入 tier。当前是 `ICD-HYPERTENSION` 与 `ICD-DYSLIPIDEMIA`。
- `classAssertions → declared` 的差额 = prp-dom 反推的产物，不是规则。

### 管理目标的出处核不了

`kind=target` 的 10 条原文存在 `rdfs:comment` 里，**不是 `SourcePassage`、没有
`contentHash`**，`/adjudicate/citations` 核不了它们。返回体的 `citationCaveat` 会
自己说出来 —— **原样带进回答**。

## 阶段 3 · 反向溯源

```bash
curl -sS 'http://localhost:8100/graph/provenance?iri=<结论 IRI>'
```

「推理」与「可核查」在这里合流：

```
Diagnosis(Provisional)
  ← supportsDiagnosis ── Assessment(conclusion=…)
      ← appliesThreshold ── DiagnosticThreshold(confirmationRequired=true)
          ← thresholdCitesPassage ── SourcePassage(quote 逐字, sha256)
      ← basedOnLabResult ── LabResult(value/unit)
          ← sqlRow ── core_lab_result(source_table, source_pk)
```

### 拿不到结论 IRI 时怎么办

患者摘要接口不一定返回真实结论 IRI。**不要自己拼**，用逃生口查出来：

```bash
# ⚠️ query 必须压成一行 —— JSON 字符串值里不能有裸换行，多行贴过去必然 400
curl -sS -X POST http://localhost:8100/graph/sparql \
  -H 'Content-Type: application/json' \
  -d '{"query":"PREFIX dmo: <https://example.org/dmo#> SELECT ?pid ?concl WHERE { VALUES ?pid { \"P90002\" } GRAPH ?pg { ?p dmo:patientId ?pid . ?p dmo:hasDiagnosis|dmo:hasAssessment ?concl } FILTER(STRSTARTS(STR(?pg), \"urn:dmo:patient:\")) } LIMIT 20"}'
```

注意那句 `FILTER(STRSTARTS(...))` —— 患者图守卫，少了它 guard 直接拒（规则 A）。

### `brokenLinks` 与 `chain` 同等重要

实测三类断链，**每一类都要在回答里点名**：

| 断链 | 含义 |
|---|---|
| 禁忌的 `rationale` 是抽取产物的裸字符串 | **不是带 `contentHash` 的 SourcePassage**，`/adjudicate/citations` 核不了 |
| 上游直接断言的诊断（`factOrigin=ehr-legacy`）没有 Assessment 支撑 | **不是本系统推出来的**，只是照抄了上游 |
| 无 `riskRuleCitesPassage` 的风险规则产出 Hit | 计不进 tier（`51-risk-stratification.rq` 信号 5） |

### ⚠️ SQL 的 `*_id` 列存业务号，不是 IRI

图里节点是 `.../diagnosis/EHR-DX-P00002-C00002-D901`（`|` 换成了 `-`，否则 IRI 不合法），
而 `core_diagnosis.diagnosis_id` 存的是原始的 `EHR-DX-P00002|C00002|D901`。
拿 IRI 直接查 SQL 永远查不到，**而且查不到不报错** —— 回查那一环静默消失，返回体
看着仍然完整。端点内部已经先用图里的 `dmo:*Id` 字面量翻成业务号再回查；
你自己写跨层查询时必须做同样的事。

### 类型判定只看断言，不看 `rdf:type`

每个 `RiskFactorHit` 同时也被推成 `dmo:RiskRule` 和 `dmo:Assessment`。按 `rdf:type`
分派会把患者命中记录当成 Assessment 去溯源，**查出一堆空**。
**断言的类型在命名图里，推出来的不在** —— 只认前者。

## 阶段 4 · SPARQL 逃生口（最后手段）

上面那族能答的**别自己拼图模式**。它们的 GRAPH 子句由服务端拼，永远不会踩下面这两脚。

### 六条静态检查

| 规则 | 检测 | 处置 |
|---|---|---|
| **A 患者图守卫** | 每个 `GRAPH ?var` 是否被 `STRSTARTS(STR(?var),"urn:dmo:patient:")` 约束 | **拒**，理由里直接给出该补的那一句 |
| **B 知识侧禁具名图** | `GRAPH <urn:dmo:seed｜tbox｜sources｜inferred｜extract:*>` | **拒** —— 会静默少返 |
| **C 反例夹具** | 出现 `urn:dmo:data` | **拒** |
| **D 写操作** | 非 SELECT/ASK/CONSTRUCT/DESCRIBE，或含 INSERT/DELETE/DROP/… | **拒** |
| **E 行数上限** | 无 `LIMIT` → 追加 200；超过 200 → 改写为 200 | 记进 `rewrites`，**不算失败** |
| **F 全库扫描** | 触及患者图但没有 `VALUES` / 具体患者 IRI 收敛 | 警告，不拒 |

拒绝理由是**写给你看的**：它会作为 observation 回来让你自我修正。照它给的修正句改，
不要换个名字硬试。`rewrites` 非空时在回答里说明结果被截断到 200 行。

### 零结果探针

返回 0 行时不把空集直接给你，而是自动降级探一次：

> 返回 0 行，**但该患者图里有 10 条三元组**。0 行大概率是图模式写错了 ——
> 最常见的是把知识侧三元组也包进了 `GRAPH ?pg`。

**空集与"有但判不了"是两回事。** 拿到 0 行先读探针结论，不要直接回答"没有数据"。

九个端点的完整参数、返回体字段与常用查询骨架见 [references/endpoints.md](references/endpoints.md)。

## 阶段 5 · 输出

```
【问的是什么】<被溯源的结论 / 被探索的概念，及其准确 IRI（来自 /graph/concepts，非自拼）>
【链路】<chain 逐环：节点 + 谓词 + 关键字面量；标出哪些类型是推出来的>
【依据】<evidence 逐条：quote 原文 + 完整 sha256 + supports；没有可核验出处时明确说没有>
【断链】<brokenLinks 逐条：断在哪一环 + 为什么断 + 后果（核不了 / 不计分 / 非本系统推出）>
【规则】<ruleId@ruleVersion；countsInTier / citationCaveat 若有则原样带上>
【查询口径】<若走了 SPARQL：rewrites、零结果探针结论、guard 的警告>
⚠️ <disclaimer 原文>
```

## 交付前自检

- [ ] 每个 IRI 都来自上一步的返回体，没有一个是我拼的？
- [ ] `usable: false` 的概念，我有没有当成"能判定"用？
- [ ] `brokenLinks` 报出来了吗，还是我只渲染了 `chain`？
- [ ] 每条 `quote` 和完整 `sha256` 都是原样复制的？
- [ ] 有没有把 `inferredOnly: true` 的类型说成"本体里声明了"？
- [ ] 报规则数量时用的是声明标记（12 条），不是 `rdf:type`（73 条）？
- [ ] `citationCaveat`（管理目标核不了出处）带上了吗？
- [ ] 走 SPARQL 的话：guard 有没有被我绕过？0 行有没有先读探针？`rewrites` 说明了吗？
- [ ] `disclaimer` 带上了吗？

## 什么时候**不要**用这个 skill

- 用户问的是患者判成什么、有什么风险 → skill `dmo-patient-graph-analysis`。
- 用户问的是原始事实行、跨患者计数 → skill `dmo-sql-facts`。
- 用户要裁决**外部**给的引用或结论 → skill `dmo-adjudicate`。本 skill 溯的是自家结论。
- 用户要改本体 / 加规则 / 重建 TBox → `ontology/tools/`，不走查询 API。
