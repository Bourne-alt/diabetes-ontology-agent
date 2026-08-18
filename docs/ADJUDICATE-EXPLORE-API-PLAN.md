# 结论裁决 API × 图探索原语 API

> 配套：整体方案 [DESIGN.md](DESIGN.md)｜端点契约 [API.md](API.md)｜图层写法 [GRAPHDB-USAGE.md](GRAPHDB-USAGE.md)｜ReAct 智能体 [AGENT-INVESTIGATE-PLAN.md](AGENT-INVESTIGATE-PLAN.md)
>
> 本文回应两个诉求：**(A) 对已有结论做合理性裁决**、**(B) 细粒度图查询，放开智能体的自由度**。
> 起草日期：2026-08-18。

---

## 0. 先纠三个说法，不然端点会设计歪

### 0.1 「校验结果合理性」混了三件事，其中一件本体库根本做不到

| 问的是什么 | 可判定？ | 靠什么判 |
|---|---|---|
| a. 这条结论与本体的阈值 / 规则一致吗 | ✅ 完全可判定 | 20/21/30/40/50/51 规则链的产出，按语义键比对 |
| b. 这条结论声称的出处是真的吗 | ✅ 完全可判定 | `urn:dmo:seed` 里 31 条 `SourcePassage`，100% 带 `contentHash`，已被 `verify_passages.py` 逐字回原文校验过 |
| c. 这条结论「临床上合理」吗 | ❌ **做不到** | 50 份语料 + 31 条可引用出处覆盖的是很窄的一片。「没查到反驳证据」≠「合理」 |

**如果端点返回 `{"reasonable": true}`，那是在撒谎，而且是最危险的一种撒谎** —— 等于给外部系统发了一枚「已通过本体校验」的印章。一个 A1C 6.8% 的患者，按诊断切点超标、按管理目标达标（`21-target-attainment.rq` 开头专门写了这一条），同一个数两个相反结论，「合理」这个词在这里没有单一真值。

所以裁决结果必须是**四值枚举**，永远不出现 boolean：

```
supported        本体推出了同一条结论，且出处可逐字回查
contradicted     本体推出了相反结论（语义键冲突）
unsupported      本体没有相反结论，但也拿不出支撑 —— 证据不足
not-adjudicable  这类断言本体压根不管（剂量、概率、预后、非糖尿病域）
```

且 `not-adjudicable` 应当是**常见返回值而不是异常**，`Insufficient-Evidence` 在 `/risk` 上已经是常态（API.md §6），同一条诚实标准这里照搬。

### 0.2 「校准」这个词用错了

校准（calibration）在 ML 里专指概率校准。本仓库 `51-risk-stratification.rq` 开头明写「不输出概率、不输出百分比、不输出时间窗」。这里实际做的是**裁决 / 对账（adjudication）**：把外部断言与本体推理产物按语义键比对。

端点叫 `/calibrate` 会让调用方以为能拿到置信度分数，然后自己编一个出来。**用 `/adjudicate`。**

### 0.3 「开放更大自由度」≠「开放 SPARQL」

`query/templates.py` 开头按严重程度排了三条理由，最狠的一条是：

> 写错 GRAPH 子句会**静默少结果** —— 查询不报错，只是答案少一半。这类错误没法靠看输出发现。

真正的风险从来不是 agent 删库（只读角色能挡），是**它给你半个答案而你看不出来**。所以自由度要开在正确的维度上：

| 错误的自由度 | 正确的自由度 |
|---|---|
| 让 agent 自己写 GRAPH 子句 | 让 agent 自己决定**下一跳查什么** |
| 给一个 `raw_sparql` 大洞 | 给一组**正交、可组合的图原语**，GRAPH 子句由服务端拼 |
| 靠 prompt 叮嘱它加守卫 | 守卫在服务端，agent 碰不到那两个必犯的错 |

12 个正交原语的组合空间比 6 个模板大几个数量级，而每个原语的图模式都是仓库自己写的。`raw_sparql` 仍然要有（[AGENT-INVESTIGATE-PLAN.md](AGENT-INVESTIGATE-PLAN.md) §2 的 guard 已设计完），但它是**第 13 个工具，不是第 1 个**。

---

## 1. 两族端点

```
POST /adjudicate/claim        单条结论裁决          ← 亮点 2「校验」
POST /adjudicate/batch        整份报告逐条裁决
POST /adjudicate/citations    只查出处真伪（无需患者）★ 最先做
GET  /adjudicate/scope        我能裁决什么、不能裁决什么

GET  /graph/concepts          概念检索 → 准确 IRI（唯一入口）
GET  /graph/node              节点邻接摘要
GET  /graph/neighbors         展开一跳
GET  /graph/path              两点间路径（受控 property path）
GET  /graph/taxonomy          上位/下位（owl2-rl 物化边）  ← 亮点 1「推理」
GET  /graph/rules             规则清单（阈值 / 风险 / 禁忌）
GET  /graph/rules/{id}        单条规则的边界与出处
GET  /graph/thresholds        阈值检索
GET  /graph/passages          出处检索
GET  /graph/provenance        反向溯源：推断产物 → 支撑链 → 原文 → SQL 行
GET  /graph/schema            schema card（RDF 侧 / SQL 侧 / 桥接表）
POST /graph/sparql            guard 后的逃生口（第 13 个，不是第 1 个）

GET  /agent/manifest          上面全部端点的机器可读清单 + 使用铁律 + 硬禁令
```

---

## 2. A 族：结论裁决

### 2.1 `POST /adjudicate/claim`

**只接受结构化断言，不接受自然语言。** 接受自然语言就要先用 LLM 解析，确定性当场丢光 —— 那正是 `simulate` 的 `derivationHash` 花力气守住的东西。需要 NL 入口的话另开 `/adjudicate/parse`，返回体显式标 `nondeterministic: true`，让调用方自己决定要不要信那一步。

```jsonc
// 请求
{
  "patientId": "P90002",
  "claim": {
    "type": "Diagnosis",                    // Assessment|Diagnosis|RiskTier|
                                            // TargetAttainment|MedicationSafety
    "value": { "kind": "T2DM", "verificationStatus": "Confirmed" }
  },
  "assertedBy": "external-llm/some-model",  // 只记账，不影响判定
  "citations": [ { "quote": "…", "sha256": "…" } ]   // 外部**声称**的出处，可空
}
```

```jsonc
// 响应
{
  "verdict": "contradicted",
  "verdictReason": "本体推出的是 verificationStatus=Provisional：A1C 7.4% 命中的诊断切点 confirmationRequired=true，该患者只有 1 个采样日。",
  "systemConclusion": { "kind": "T2DM", "verificationStatus": "Provisional", "…": "…" },
  "comparison": {
    "semanticKey": ["kind", "verificationStatus"],
    "matched":  ["kind"],
    "conflicts": [ { "field": "verificationStatus", "claimed": "Confirmed", "system": "Provisional" } ]
  },
  "basedOn": [ { "labResultId": "…", "value": 7.4, "unit": "percent",
                 "sqlRow": { "table": "core_lab_result", "pk": "…" } } ],
  "rulesApplied":      [ { "ruleId": "…", "ruleVersion": "…", "file": "30-diagnosis-from-assessment.rq" } ],
  "thresholdsApplied": [ { "thresholdId": "…", "interval": "[6.5, ∞) percent",
                           "confirmationRequired": true } ],

  "citationCheck": {                        // ★ 独立价值最高的一段
    "claimed": 2, "verbatim": 1, "hashMatched": 1,
    "fabricated": [ { "sha256": "dead…", "reason": "本库 31 条 SourcePassage 里没有这个 contentHash" } ],
    "misattributed": [ { "quote": "…", "reason": "原文存在，但它支撑的是管理目标，不是诊断切点" } ]
  },

  "missingEvidence": [ { "need": "另一日复测 A1C 或 FPG", "because": "所用阈值 confirmationRequired=true",
                         "wouldChangeVerdictTo": "supported" } ],
  "whyNotAdjudicable": null,               // verdict=not-adjudicable 时必填

  "adjudicationHash": "sha256(claim ‖ graphVersion ‖ rulesFingerprint)",
  "graphVersion": "…", "rulesFingerprint": "…",
  "unmapped": [ … ], "dataQualityNotice": null,
  "disclaimer": "⚠️ 技术验证用途，不是医疗器械…"
}
```

四个设计要点：

1. **`adjudicationHash` 是这个端点的 `derivationHash`。** 同一条断言在同一版知识层下裁决 100 次必须同哈希。没有这个，它就只是又一个说不清的端点。
2. **`missingEvidence.wouldChangeVerdictTo`** 把裁决和 `simulate` 接上：「补一次复测会怎样」直接交给 `POST /simulate` 跑，不在这里猜。
3. **`citationCheck.misattributed`** 比 `fabricated` 更难也更值钱 —— 引用真实存在但支撑错了对象，是 LLM 最典型的错法，纯字符串比对抓不到，要靠 `thresholdCitesPassage` / `riskRuleCitesPassage` 的边反查。
4. **`assertedBy` 绝不参与判定。** 谁说的不影响对不对。

### 2.2 `POST /adjudicate/citations` ★ 最先做

只查出处真伪，**不需要患者、不需要 GraphDB 之外的任何东西、完全确定性**：

```jsonc
// 请求  { "citations": [ { "quote": "…", "sha256": "…" }, … ], "assertedBy": "…" }
// 响应  逐条 { "index": 0, "verdict": "…", "reason": "…",
//             "matched": [{ passageId, quote, sha256, sourceId, citedBy, trusted }],
//             "sha256Computed": "…" }
```

**实施时把 §0.1 的四值细分成五个**（落地后回填）—— 出处这一层能分得更细，而每多分出一档，
调用方就少一次误读：

| verdict | 判据 | 为什么值得单列 |
|---|---|---|
| `verbatim` | 引文逐字命中，哈希（若给）相符 | 唯一一个「引用成立」 |
| `hash-only` | 哈希命中，但引文与该条不一致（或未给引文） | ★ **引文在转述中被改写** —— 纯字符串比对和纯哈希比对**各自都抓不到**，必须两条线一起看 |
| `quote-only` | 引文逐字命中，但给的哈希与该条不符 | 哈希是编的；若该哈希指向另一条真出处，返回体点名是哪一条 |
| `not-verbatim` | 引文与某条存在**包含关系**，哈希未命中 | 截取或加话，与凭空编造是两回事 |
| `fabricated` | 引文与哈希都无对应 | 措辞必须写明「不等于指控伪造」—— 也可能引自本仓库未收录的资料 |

包含关系是纯机械可判定的，不违反「未命中只记账，绝不猜」；**相似度匹配一律不做** ——
`verify_passages.py` 的原话是「漏报远比误报安全」，0.87 的相似度判成「引用成立」等于用一个数字把伪造洗白。

**这是整个方案里依赖最少、可独立上线、外部可复现的一个端点。第一个落地。**

### 2.3 `GET /adjudicate/scope` —— 把能力边界本身做成 API

```jsonc
{
  "adjudicable": [
    { "claimType": "Assessment",  "coverage": "…个诊断/管理阈值，覆盖 A1C/FPG/OGTT2H/RPG",
      "ruleFiles": ["20-lab-assessment.rq", "21-target-attainment.rq"] },
    { "claimType": "RiskTier", "coverage": "…条 RiskRule，其中 N 条无可引用出处、不参与计分" }
  ],
  "notAdjudicable": [
    { "topic": "用药剂量",   "why": "本仓库任何路径都不输出剂量" },
    { "topic": "发病概率 / 时间窗", "why": "无结局标签、无随访，训练不出来，编出来就是造假" },
    { "topic": "非糖尿病域", "why": "语料只覆盖糖尿病及其并发症" }
  ],
  "corpus": { "guidelineSources": 50, "citablePassages": 31, "…": "…" },
  "graphVersion": "…"
}
```

**让 agent 在调用前就能自己判断该不该调**，比事后返回 `not-adjudicable` 便宜得多。这也是防止 API 被当成「权威印章」的第一道防线。

---

## 3. B 族：图探索原语

共同约定，逐条都是硬性的：

- **GRAPH 子句一律由服务端拼**。患者侧永远带 `STRSTARTS(STR(?pg),"urn:dmo:patient:")`，知识侧永远不写 `GRAPH`（写了就吃不到 owl2-rl 物化边）。守卫常量取自 `templates.PG_GUARD`，**不抄第二份**。
- **每个返回体带 `nextHops`**：可继续展开的谓词 + 现成的端点 URL。agent 不该靠猜谓词名。
- **每个返回体带 `emptyReason`**：返回空集时必须区分「图里确实没有」/「你的问法收敛错了」/「映射表说这项判不了」。这是 `explain_gap` 的诚实标准推广到整个查询族（详见 §4.1）。
- **一律有 `limit`，默认 50、上限 200**，与 guard 规则 E 一致。

| 端点 | 回答什么 | 复用什么 |
|---|---|---|
| `GET /graph/concepts?q=&kind=&limit=` | 中文表面形式 → 准确 IRI。**所有图探索的唯一入口** | `map_concept_ref` 的 `label ILIKE ∪ code ILIKE ∪ ANY(alt_labels)`，照搬 `hybrid.explain_gap` 的候选概念查询 |
| `GET /graph/node?iri=` | 该节点的**邻接摘要**：rdf:type、出边/入边（谓词 + 对端 label + 计数）、所在图。**不返回全部三元组** —— agent 要的是「下一跳去哪」，不是一屏 turtle | 新建 |
| `GET /graph/neighbors?iri=&predicate=&direction=out\|in` | 展开一跳，带分页 | 新建 |
| `GET /graph/path?from=&to=&maxHops=3` | 「这个患者事实和这条指南结论是怎么连上的」。受控 property path，跳数写死上限 | 新建 |
| `GET /graph/taxonomy?iri=&direction=up\|down&depth=` | 上位/下位。**这一条直接展示 owl2-rl 的物化推理边** —— 亮点 1 的展示面 | 新建 |
| `GET /graph/rules?kind=threshold\|risk\|contraindication` | 规则内省：边界、operator、`confirmationRequired`、`triggerBasis`、引用的 passage、**有没有出处（决定参不参与计分）** | `map_risk_rule` 已投影在 SQL，白拿 |
| `GET /graph/rules/{id}` | 单条规则全貌 + 命中它的患者数 | 同上 |
| `GET /graph/thresholds?concept=&context=` | 按概念/语境检索阈值，返回可读区间（复用 `hybrid._interval`） | 新建 |
| `GET /graph/passages?sha256=&q=&citedBy=` | 出处检索，与 `/adjudicate/citations` 同一份底表 | 新建 |
| `GET /graph/provenance?iri=` | **反向溯源**：给一个推断产物 IRI（Assessment/Diagnosis/RiskFactorHit/ContraindicationFlag），返回完整支撑链直到 SourcePassage 原文与 `source_table+source_pk` | 新建 |
| `GET /graph/schema` | schema card：RDF 侧（ER JSON + 3 个规则产物类）、SQL 侧（`COMMENT ON` dumper）、桥接表（`COLUMN_PREDICATE_MAP`） | [AGENT-INVESTIGATE-PLAN.md](AGENT-INVESTIGATE-PLAN.md) §4 |
| `POST /graph/sparql` | 自由 SPARQL → guard A–F → 零结果探针 | [AGENT-INVESTIGATE-PLAN.md](AGENT-INVESTIGATE-PLAN.md) §2 |

### 3.0 实施中发现：`?r a dmo:RiskRule` 会多查出六倍 ★

落地 `/graph/rules` 时实测到的，值得写进本文，因为它正好是「细粒度原语为什么必须由服务端拼」的最好例证：

```
?r a dmo:RiskRule                  → 73 条
?r a dmo:RiskRule ; dmo:riskRuleId → 12 条   ← 真正被规则链消费的
```

`dmo:triggerBasis` 的 `rdfs:domain` 是 `dmo:RiskRule`（`dmo-risk-map.ttl:98`），而
`50-risk-factor-hit.rq` 产出的每条 `RiskFactorHit` 都带 `triggerBasis`。OWL-RL 的 **prp-dom**
顺着 domain 反推，把**每个患者命中记录**都判成一条「风险规则」。`dmo:ruleId` 的 domain 是
`dmo:Assessment`，于是这些 Hit 同时又是 Assessment（`?a a dmo:Assessment` 当前查出 143 条）。

查询不报错、不告警，只是数字大了六倍。一个自己写 SPARQL 的 agent 八成会踩这一脚，
而且**它没有任何办法从返回结果里看出自己踩了**。

处理：所有规则一律以**声明标记**（`dmo:riskRuleId` / `dmo:thresholdId` / `dmo:targetId`）为准，
不以 `rdf:type` 为准；并把 73 与 12 的差额当一等公民报进 `counts.risk.classAssertions`
与 `inferenceArtifacts`。`tests/test_graph_explore.py::test_risk_rule_class_is_contaminated`
正面断言这个坑存在 —— 两个数字相等就说明推理机没跑或 ruleset 被换掉了，那本身就该亮。

### 3.2 实施中发现：SQL 的 `*_id` 列存业务号，不是 IRI

落地 `/graph/provenance` 时撞到的第二个静默失败：

```
图里节点 IRI      https://example.org/dmo/id/diagnosis/EHR-DX-P00002-C00002-D901
SQL diagnosis_id  EHR-DX-P00002|C00002|D901
```

`|` 在 IRI 里不合法，铸 IRI 时换成了 `-`。拿节点 IRI 直接查 `core_*` 永远查不到，
**而且查不到不报错** —— 「回查 SQL 原始行」那一环静默消失，返回体看着仍然完整。

处理：先用图里的 `dmo:labResultId` / `dmo:diagnosisId` / `dmo:observationId` /
`dmo:medicationUseId` 字面量把 IRI 翻成业务号（这一步带患者图守卫，顺便挡掉夹具），
再回查。`tests/test_graph_explore.py::test_sql_lookup_uses_business_id_not_iri` 断言
`factId != iri`，守的就是这个静默。

### 3.3 实施中发现：注释剥离会吃掉 IRI 里的 `#`

写 guard 时撞到的第三个静默失败，而且它藏在**检查器自己**里面：

```python
re.sub(r"#[^\n]*", "", query)      # 看着人畜无害
```

本体的词汇命名空间是 `https://example.org/dmo#`。这条正则把
`<https://example.org/dmo#>` 的 `#>` 当行注释吃掉 —— **连闭合的 `>` 一起** ——
于是从 PREFIX 那一行起，整条查询被粘成一个巨大的「IRI」，后面所有规则都在一段
面目全非的文本上跑。**guard 照常给判定，只是判在错的输入上。**

处理：逐字符扫，`#` 只有在 `<…>` 与字符串字面量之外才算注释。
`tests/test_guard.py::test_hash_inside_an_iri_is_not_a_comment` 正面钉住这一条。

> 三个坑同一个形状：**不报错、只少答**。这正是图探索族存在的全部理由 ——
> 服务端替调用方兜住的就是这类东西，而 guard 是这一族里唯一一个「自己也可能踩坑」的模块，
> 所以它的纯单测（19 条，零基础设施依赖）比端到端测试更重要。

### 3.4 实施中发现：诊断切点与管理目标必须分开裁决

`21-target-attainment.rq` 与 `20-lab-assessment.rq` 的产出**都是 `dmo:Assessment`**，
都进 `assessment_evidence` 模板，只有 `ruleId` 能区分
（`TARGET-ATTAINMENT` / `LAB-THRESHOLD-MATCH`）。

第 5 步先落地的 `Assessment` 裁决没有按 `ruleId` 收敛，于是一条「conclusion=High」的断言
会同时去和两类结论比 —— 而 `High` 是管理目标的词。实测 P90003 同时有
`High`（管理目标）与 `DiabetesRange`（诊断切点）两条结论，不分开判出来的对错是随机的。

第 8 步把它拆成两个 claim 类型：`Assessment` 只看 `LAB-THRESHOLD-MATCH`，
`TargetAttainment` 只看 `TARGET-ATTAINMENT`。这正是 21 号规则开头那段警告的
API 层对应物：**一个 A1C 6.8% 的患者，按诊断切点是超标，按管理目标是达标。**

### 3.1 `GET /graph/provenance` 是两个亮点的交汇点

「推理」和「可核查」在这一个端点上合流：

```
Diagnosis(Provisional)
  ← supportsDiagnosis ── Assessment(conclusion=…)
      ← appliesThreshold ── DiagnosticThreshold(confirmationRequired=true)
          ← thresholdCitesPassage ── SourcePassage(quote 逐字, sha256)
              ← GuidelineSource(26 份带完整元数据)
      ← basedOnLabResult ── LabResult(value/unit)
          ← sqlRow ── core_lab_result(source_table, source_pk)
```

一条链从「机器推出来的结论」一路到「原文哪一句」和「数据库哪一行」。**`/adjudicate/claim` 的 `basedOn` 与 `citationCheck` 就是这条链的两个切片** —— 两族端点共用同一份实现，不写两遍。

### 3.2 `GET /agent/manifest`

把全部端点连同 JSON schema、调用顺序铁律（SQL 收敛 → `patient_iri()` → SPARQL 注入 → `source_pk` 回查）、硬禁令（不剂量、不概率、不猜术语、不把 Provisional 当确诊）一次性吐给 agent。

**「辅助智能体自主规划」的正解是让能力可发现，不是让语言更自由。** 端点清单硬编在 prompt 里，每加一个端点就要改 prompt，还必然漏改。

---

## 4. 两族共用的三个机制

### 4.1 零结果探针（通用中间件，不只给 raw sparql）

任何 `/graph/*` 返回空集，都走同一条降级链：

1. 该 IRI 在图里存在吗？（`ASK { <iri> ?p ?o }`）
2. 若涉及患者：该患者图里有几条三元组？
3. 若涉及术语：`map_lab_term` / `map_unmapped_term` 怎么说？

`emptyReason` 写成人话，例如：

> 该患者图里有 47 条三元组，但没有 `dmo:hasAssessment`。最可能的原因是所有检验值 `valueTrustLevel=Unverified`，被 `20-lab-assessment.rq` 挡在门外 —— 加 `?includeUnreliable=true` 能看到降级成 Indeterminate 的结论。

**返回空集让人以为「没查到」，是 `hybrid.py` 开头点名最反对的行为。** 这条标准适用于新端点的每一个。

### 4.2 `evidenceRef` —— 把伪造出处从事后扫描变成事中绑定

每个 `/graph/*` 返回体带一个 `evidenceRef`（该次查询结果的内容哈希）。agent 之后调 `/adjudicate/claim` 时把 `evidenceRef` 一起带上，服务端能核对「你引的这条证据确实是你查到的」。

比 `postcheck.py` 的事后正则扫描强一个量级：事后扫只能查「这个 sha256 存不存在」，事中绑定能查「**你有没有真的查过它**」。

### 4.3 一切都挂 `graphVersion` + `rulesFingerprint`

`concepts.graph_version()`（知识层文件内容哈希）与 `engine.rules_fingerprint()` 都是现成的。知识层改一个字，全部裁决结论作废 —— 必须能一眼看出是哪一版下的判断。

---

## 5. 与既有端点的关系

| 既有 | 会不会动 |
|---|---|
| `/patients/*`、`/query/{template}`、`/terms/*`、`/demo/compare` | **一行不动** |
| `POST /simulate` | **一行不动**。`derivationHash` 是核心资产，`/adjudicate` 反过来把它当工具调 |
| `templates.py` 的 6 个模板 | 保留。`/graph/*` 是补充不是替代：模板答得了的，prompt 里明说别自己拼 |
| [DESIGN.md](DESIGN.md) 原则 1 | 已由 [AGENT-INVESTIGATE-PLAN.md](AGENT-INVESTIGATE-PLAN.md) 有意推翻，本文延续同一条推翻理由：**代价用机械检查补，不用自觉补** |
| 原则 2（provenance 必带）、原则 3（schema 注入非数据注入） | **加强**。§4.2 把原则 2 从「必带」升级成「可核对」 |

---

## 6. 实施顺序

| # | 内容 | 验收 | 依赖 |
|---|---|---|---|
| 1 | ✅ `POST /adjudicate/citations` + `GET /graph/passages` | 编造 sha256 必被判 `fabricated`；改写引文必被判 `hash-only` | 无（只读 seed 图） |
| 2 | ✅ `GET /adjudicate/scope` + `GET /graph/rules{,/id}` | 无出处的风险规则在返回体里明确标「不参与计分」 | 只读图（**改为读图，不读 `map_risk_rule`**，见 §3.0） |
| 3 | ✅ `GET /graph/concepts` + `/node` + `/neighbors` + `/taxonomy` | 每条 SPARQL 人工复核 GRAPH 子句；`/taxonomy` 能查到 owl2-rl 物化边 | `map_concept_ref` |
| 4 | ✅ `GET /graph/provenance` | 任一 Assessment IRI 能一路溯到原文与 SQL 行 | 3 |
| 5 | ✅ `POST /adjudicate/claim`（Assessment / Diagnosis） | `adjudicationHash` 跑 5 遍相同 | 4 |
| 6 | ✅ `/graph/path`、`/schema`、`/agent/manifest`（`/thresholds` 并入 `/graph/rules`，见 §3.3） | manifest 能驱动 agent 走完一次完整调查 | 3 |
| 7 | `POST /graph/sparql`（guard + 零结果探针） | [AGENT-INVESTIGATE-PLAN.md](AGENT-INVESTIGATE-PLAN.md) §10 层一测试全绿 | guard |
| 8 | ✅ `RiskTier` / `MedicationSafety` / `TargetAttainment` 裁决 | —— | 5 |

**第 1 步做完先上线。** 它零 LLM、零新基础设施、外部可独立复现，是这两个亮点里最容易被人一眼看懂的证据。

> 第 6–8 步同日落地：`src/dmo/graph/{guard,schema_card}.py`、`src/dmo/manifest.py`、
> `explore.path()`、`claim.py` 的三个新类型。测试 `tests/test_guard.py`（19 条**纯单测，
> 零基础设施依赖** —— guard 挡不住的东西后面全是白搭，所以它必须能独立验收）
> + 图探索/裁决族共 94 条。实施中发现的第三、四个坑写进了 §3.3、§3.4。
>
> 偏离计划两处，都记在正文里：`/graph/thresholds` 并入 `/graph/rules`
> （同一件事不允许有两份定义）；桥接表改为 AST 静态解析 `emit.py` 而不是新造
> `COLUMN_PREDICATE_MAP` 常量（不动同步代码，且不可能与发射逻辑分叉）。
>
> 第 3–5 步同日落地：`src/dmo/graph/{explore,provenance}.py`、`src/dmo/adjudicate/claim.py`。
> 实施中发现的第二个坑写进了 §3.2。裁决族的 `misattributed`（引文属实但支撑错对象）
> 已可用，判据是 `thresholdCitesPassage` 的边反查。
>
> 第 1、2 步已落地（2026-08-18）：`src/dmo/graph/{passages,rules}.py`、`src/dmo/adjudicate/`，
> `tests/test_adjudicate.py` + `tests/test_graph_explore.py` 共 28 条断言全绿。
> 实测口径：31 条可引用出处（100% 带 contentHash，来自 6 份指南）、17 条诊断阈值、
> 10 条管理目标、12 条声明的风险规则（10 条计入 tier）。
> 第 2 步原计划读 `map_risk_rule`，实施时改为读图 —— 那份 SQL 投影只收得下可执行的 12 条，
> 看不到 §3.0 那个六倍落差，而落差正是要报的东西。

---

## 7. 测试

`tests/test_adjudicate.py` / `tests/test_graph_explore.py`

**裁决族**
- `test_adjudication_hash_is_stable` —— 照搬 `test_simulate.py::test_derivation_hash_is_stable`
- `test_verdict_is_never_boolean` —— 返回体里不得出现 `reasonable` / `valid` / `ok` 这类字段名
- `test_fabricated_sha256_is_caught` —— 编一个哈希，必判 `fabricated`
- `test_rewritten_quote_is_caught` —— 原文改两个字，必判 `hash-only`
- `test_misattributed_citation_is_caught` —— 拿管理目标的出处去支撑诊断断言，必判 `misattributed`
- `test_confirmed_vs_provisional` —— 单采样日 + `confirmationRequired=true` 的 `Confirmed` 断言必判 `contradicted`
- `test_dosage_claim_is_not_adjudicable` —— 剂量断言必返 `not-adjudicable`，且不给任何数字
- `test_asserted_by_does_not_change_verdict` —— 换 `assertedBy` 结论不变

**图探索族**
- `test_every_patient_query_has_pg_guard` —— 遍历所有 `/graph/*` 实际发出的 SPARQL，静态断言患者侧全带 `STRSTARTS`
- `test_no_named_graph_on_knowledge_side` —— 知识侧一律不出现 `GRAPH <urn:dmo:`
- `test_never_touches_fixture_graph` —— 任何端点返回体不得含 `urn:dmo:data` 的 6 例反例夹具
- `test_empty_result_always_has_reason` —— 空集必带 `emptyReason`
- `test_graph_endpoints_never_write` —— 全端点跑一遍，前后 `GraphDBClient.size()` 相等
- 复用 `test_api.py::test_no_dosage_and_no_probability_in_any_response` 的判据覆盖新端点

---

## 8. 医疗免责

与本仓库其余部分同一条：**技术验证用途，不是医疗器械，不构成医疗建议。不输出任何用药剂量，风险分层为规则式定性分层、非概率预测。**

只属于裁决族的一条：**`verdict=supported` 的含义严格限定为「与本仓库当前版本知识层的规则和阈值一致，且所引出处可逐字回查」，不代表临床上正确、不代表适用于该患者、更不是任何形式的诊疗背书。**
