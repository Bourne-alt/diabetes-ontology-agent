# 端点与字段语义

基址默认 `http://124.223.18.44:8100`（仅绑 127.0.0.1，无鉴权、无限流）。
完整叙述见 [docs/API.md](../../../../docs/API.md)；本文只保留**做判断时必须知道的字段含义**。

---

## 职责边界（写死的，不随需求飘）

| 问题形态 | 走哪一侧 |
|---|---|
| 有多少 / 哪些患者 / 分页 / 按 ICD-10 筛 | SQL（`/patients`、`/terms/*`） |
| 为什么 / 凭什么 / 依据哪条指南 / 能不能 | SPARQL（`/assessment`、`/safety`、`/query/*`） |
| 原始那一行长什么样 | SQL 回查（`assertedFacts[].sqlRow`） |
| 这个术语认不认识 / 为什么查不到 | SQL（`/terms/explain`） |

判断题问 SQL、检索题问 SPARQL，都是用错工具。

---

## `GET /health`

| 字段 | 读法 |
|---|---|
| `ok` | false 时另有 `postgres` / `graphdb` 字段说明哪侧断了 |
| `graphVersion` | 知识层四文件（TBox / 公理 / 阈值 seed / 风险映射）的内容哈希前 16 位。**变了 = 本体改过 = 旧结论全部需重查** |
| `patients` / `labResults` / `stratified` | SQL 侧计数 |
| `graphdbTriples` | 图库三元组总数 |

---

## `GET /patients`

参数：`icd10`、`origin`、`scenario`、`tier`、`page`、`size`（上限 200）。

| 字段 | 读法 |
|---|---|
| `fact_origin` | **唯一可信的真假判据**。`ehr-legacy` 真实上游 / `derived` 投影推出 / `demo-cohort` 演示队列。ID 前缀故意做成不可区分 |
| `birth_year` | `null` = 拒绝用错数据（上游 400 人中 329 人生日在未来，最晚 2063-09-14），**不是缺失** |
| `source_table` / `source_pk` | 回查原始行的坐标 |
| `riskStratification.tier` | 档位。**必须连同同一对象里的 `ruleId` / `ruleVersion` 一起转述**，单独说档位就是裸断言 |
| `riskStratification.notComputedReason` | 只在 `tier=null` 时出现。含义是**分层规则没跑过**（系统状态），与 `Insufficient-Evidence`（跑了、判定证据不足）方向相反，不许混说 |
| `riskStratification.evidenceEndpoint` | 只在 tier 为 High/Moderate/Low 时出现。逐字引文不在本端点，走这一跳取（`/patients/{pid}/risk` 的 `contributingFactors[]`） |
| `riskStratification.evidenceNotice` | 只在 `tier=Insufficient-Evidence` 时出现。**该档位没有逐字引文是正确的**；`insufficientReason` 是自由文本说明，不是可核验出处，不得转述成「依据某某指南」 |
| `provenanceNotice` | 顶层字段。说明本端点为什么不带引文、引文在哪 |

---

## `GET /patients/{pid}` — 七段返回体

`careChain` / `riskStratification` / `assertedFacts` / `inferredFacts` / `sources` / `unmapped` / `dataQualityNotice`（+ `patient`、`disclaimer`）。
分端点 `/care-chain` `/assessment` `/risk` `/safety` 只是取子集，字段语义完全一致。

### `assertedFacts[]`（原始事实，SQL 侧）

| 字段 | 读法 |
|---|---|
| `trust` | `Curated` 可用；**`Unverified` 一律不参与判定、不在回答里当数值引用** |
| `value` / `unit` | 规范化后的值。规范单位：A1C=`percent`，血糖=`mg-per-dL` |
| `source_value` / `source_unit` | 非空 ⟹ ETL 做过单位换算。换算只在 ETL 做，SPARQL 里一次都不做（系数是分析物特有的：葡萄糖 ×18.0182、肌酐 ÷88.4） |
| `sqlRow` | `{table, pk}`，回查原始行用 |

### `inferredFacts[]` — `type: "dmo:Assessment"`

| 字段 | 读法 |
|---|---|
| `conclusion` | `DiabetesRange` / `PrediabetesRange` / `NormalRange` / `Hypoglycemia` … |
| `ruleId` / `ruleVersion` | 哪条规则、哪个版本得出的。规则改了旧结论能被识别出来。**必须在回答里出现** |
| `applicableContext` | 带 `(assumed)` 后缀 = 无该状态记录、按缺省处理。**开放世界下"没记录" ≠ "没有"**，必须如实标注是假设 |
| `appliesThreshold` | 阈值 ID，如 `A1C-DIABETES-NONPREG` |
| `confirmationRequired` | true = 单次落区间**不足以**确诊。四条诊断级切点（A1C/FPG/OGTT2H/RPG）全为 true |
| `interval` | 由 `lowerOperator`/`upperOperator` 还原的开闭区间，如 `[6.5, +∞) percent`。`[` 来自 `GTE`，`(` 来自 `GT`。**用 `>=` 近似「below 5.7%」会把 5.7 错判成 Normal** |
| `basedOn` | `{labResultId, value, unit, sourceValue, sourceUnit}` |
| `caveat` | 非空必须原样转述 |

### `inferredFacts[]` — `type: "dmo:Diagnosis"`

| 字段 | 读法 |
|---|---|
| `verificationStatus` | `Provisional` = 只有一个日期的检验支撑，**不是确诊**；`Confirmed` = 另一日复测已确认。**必须连同 `supportedBy` 一起读**，见下一行 |
| `supportedBy` | 支撑它的 Assessment：`{assessment, conclusion, ruleId, ruleVersion}`。非 null ⟹ 这条诊断是本仓库规则推出来的，可回溯 |
| `provenanceNotice` | 只在 `supportedBy=null` 时出现。**含义是这条诊断由上游直接断言，不是本仓库推出来的，没有 ruleId 也没有可核验出处**。⚠️ 上游的 `Confirmed` 就是这一类——它不代表本仓库确认过任何事，转述时不得写成「系统确诊」 |
| `clinicalStatus` | `Active` / `Resolved` |
| `factOrigin` | `ehr-legacy` 真实上游 / `demo-cohort` 演示队列 / `derived` 系统推出来的。（旧文档写的 `asserted` 不是实际取值） |
| `externalCode` | ICD-10，如 `E11`。无分型信息时诊断落到 `DM-Unspecified` |

### `sources[]`

| 字段 | 读法 |
|---|---|
| `quote` | 指南**逐字原文**。31 条引文由 `verify_passages.py` 逐字回原文校验 |
| `sha256` | 原文内容哈希。**这一段里每条都非空**，每条都能过 `POST /adjudicate/citations`。禁忌类的 rationale 曾经带空串混在这里，现已移入 `unverifiableEvidence[]` |
| `supports` | 这条引文支撑谁：阈值 ID / `riskRule:<id>` |

### `unverifiableEvidence[]` — 能说明来源、但核验不了的东西

**和 `sources[]` 严格分开**：`sources` 里每条都能逐字核验，这一段刻意不能。
目前只有禁忌类的 `rationale`——它是抽取图里的 `dmo:evidenceQuote` 裸字符串，
不是带 `contentHash` 的 `SourcePassage`，没人逐字核过。
把它当引文喂给 `POST /adjudicate/citations`，本系统会判 **`fabricated`**。

| 字段 | 读法 |
|---|---|
| `quote` | ⚠️ **不是逐字引文**。可以说明这条禁忌信号从哪来，**不得写成「依据某某指南」** |
| `sha256` | 恒为 `null`。这不是缺失，是"本来就没有" |
| `why` | 为什么核不了。原样转述 |

与 `GET /graph/provenance` 的 `brokenLinks` 是同一件事的两种呈现，口径一致。

### `unmapped[]`

判不了的项。**返回空集与"有数据但不可判定"是两回事**，必须原样露出。
只收 `concept_iri IS NOT NULL` 的缺口——本体里有概念但数据判不了的才算缺口；
`semantic_link` 导进来那些没人核实的候选线索是"待办清单"，混进来只是噪声。

### `dataQualityNotice`

非 null ⟹ 本次涉及 `Unverified` 值。一旦出现，**后面所有数值结论降级**，只报管线事实。

---

## `GET /patients/{pid}/risk`

⚠️ 定性分层，**非概率预测**。上游 15 个 E11 患者、每人 1 次检验、检验值是随机数、零结局标签、零随访——在这上面训模型只能学到随机数的函数。

### tier 判定（写死在 `ontology/rules/51-risk-stratification.rq`，SQL 侧只物化不判定）

| tier | 触发条件 |
|---|---|
| `High` | 任一绝对禁忌命中 **或** 已确诊活动性慢性并发症 **或** 急性事件 |
| `Moderate` | 已确诊糖尿病 +（≥2 个可改变风险因子 **或** 存在监测缺口） |
| `Low` | 已确诊糖尿病，无上述任一项，且关键监测项齐全 |
| `Insufficient-Evidence` | 无可用血糖类证据 **或** 完全无可用风险侧事实 |

### `contributingFactors[]`

| 字段 | 读法 |
|---|---|
| `triggerBasis` | `corpus-verbatim` = 判定条件直接来自所引原文（如"每周活动少于 3 次"，边界 3 写在 CDC 原文里）；`external-standard` = **数值边界来自语料之外**，必配 `externalStandardNote` |
| `externalStandardNote` | 非空时**必须原样带进回答**。如 BMI≥30 来自 WHO，CDC 原文只说 "Being overweight"、没给任何数值切点 |
| `countedInTier` | false = 语料无可逐字引用的断言，**不参与 tier**，且 `quote`/`sha256` 为 null。仍需列出——过滤掉不等于假装不存在 |
| `riskCategory` | `Modifiable` / `NonModifiable` |
| `fromFact` | 触发它的那条事实 IRI |

`monitoringGaps` 是可行动信息（如缺 UACR/eGFR 年检），单独成段说。

---

## `GET /patients/{pid}/safety`

| `severity` | 含义 |
|---|---|
| `Absolute` | 真禁令。全库 FDA 语料只有两条：SGLT2i + 重度肾病/透析、bromocriptine + 哺乳 |
| `Relative` / `Caution` | 原文是 "Before you start…, **tell your doctor** if…" ——**告知义务不是禁令** |

已知缺口两处，如实上报、不许拿假数据填：
- 哺乳那条无法自动判定（哺乳是生理状态不是并发症，`triggeredByCondition` 接不上），由 `/terms/explain` 上报。
- 二甲双胍 + ESRD **必须零绝对禁忌**：语料对二甲双胍只有乳酸酸中毒的定性表述，无任何 eGFR 数值切点。补一个就是编造出处，有回归测试盯着。

---

## `POST /query/{template}`

请求体是患者号数组，**空数组返回 400**（不静默返回空集）。不接受自由 SPARQL。

| 模板 | 用途 |
|---|---|
| `care_chain` | 就诊 → 检验/观察 → 诊断 → 用药全链 |
| `assessment_evidence` | 阈值判定 + 所用阈值 + 逐字出处 + 内容哈希 |
| `diagnosis_evidence` | 诊断 + 断言还是推出 + 支撑它的评估 |
| `medication_safety` | 三级用药安全信号 |
| `risk_stratification` | 分层结论 + 每个因子及出处 |
| `latest_lab_result` | 每个患者每个检验项的最新一次结果 |

---

## `POST /patients/{pid}/simulate`

确定性病程推演。body 是**对象**不是数组（与 `/query/{template}` 不同）：

```json
{"assume": [{"term": "A1C", "value": 7.9, "unit": "percent", "date": "2026-02-20"}]}
```

| 返回字段 | 语义 |
|---|---|
| `hypotheticalFacts[]` | 这次假设了什么。`hypothetical` 恒 true，`factOrigin` 恒 `simulated` |
| `unchanged` | 假设没改变任何结论。**是结论不是故障** |
| `delta[]` | 结论级 diff：`changed` / `added` / `removed` |
| `derivationTree` | 推导树。`LabResult.provenance` = `measured` \| `hypothetical` |
| `derivationHash` | f(pid, graphVersion, 知识快照, 规则集, 假设集)。同输入必同哈希 |
| `before` / `after` | 两轮规则跑完的结论快照 |

400 的两类拒绝（**照抄 detail 给用户，不要改名重试**）：术语没挂阈值、单位缺失或无已核实换算系数。

全部细节见 [simulation.md](simulation.md)。

---

## `GET /terms/explain?term=X`

四类归宿（`verify_status`）：

| 状态 | 含义 | 参与判定 |
|---|---|---|
| `verified` | 人工核实过 | ✅ |
| `candidate` | 有线索但未核实 | ❌ |
| `unmappable` | 结构上无法数值判定（如尿蛋白是干化学定性项） | ❌ |
| `no-source-data` | 本体有概念，上游全库无数据 | ❌ |

关键读法：`upstreamResultRows: 0` + `upstreamParentItemOnly` 有 N 条 = **它作为检验大项名存在，但底下一条真数值都没有**。大项名与其下子项语义错位（`itemname='糖化血红蛋白'` 的单子下挂的是 AST/尿蛋白/血小板/尿素氮），所以大项名一律不做映射——映射它等于主动制造错误。

---

## `GET /demo/compare?term=X`

同一条上游数据，两栏并排：左栏是同库 `semantic_link` 的字符串匹配结果（`hasUnit:false`、`hasThreshold:false`、`hasProvenance:false`，却给 confidence 0.9），右栏是本方案。用户质疑"别的系统不是这么说的"时直接给它。

---

## 错误码

| 码 | 场景 |
|---|---|
| 400 | `POST /query/{tpl}` 给了空患者数组 |
| 404 | 患者不存在；模板名不在白名单 |
| 422 | 参数类型不合法 |
| 500 | PG / GraphDB 断连 → 先查 `/health` |
