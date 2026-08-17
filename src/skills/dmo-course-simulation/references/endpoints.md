# 端点与字段语义（推演所需的自足摘要）

基址由 `DMO_BASE` 给出。本文只保留**做推演判断时必须知道的字段含义**；
完整叙述见仓库 `docs/API.md`。

---

## 职责边界（写死的，不随需求飘）

| 问题形态 | 走哪一侧 |
|---|---|
| 有多少 / 哪些患者 / 按 ICD-10 筛 | SQL：`/patients`、`/terms/*` |
| 为什么 / 凭什么 / 依据哪条指南 | SPARQL：`/assessment`、`/safety`、`/query/*` |
| 若…则…（假设成立时结论怎么变） | 沙箱：`/patients/{pid}/simulate` |
| 这个术语认不认识 / 为什么查不到 | SQL：`/terms/explain?term=X` |

判断题问 SQL、检索题问 SPARQL、现状题问 simulate，都是用错工具。

---

## `GET /health`

| 字段 | 读法 |
|---|---|
| `ok` | false 时另有 `postgres` / `graphdb` 说明哪侧断了 |
| `graphVersion` | 知识层四文件的内容哈希前 16 位。**变了 = 本体改过 = 此前所有轨迹作废** |

---

## `GET /patients` / `GET /patients/{pid}`

七段返回体：`careChain` / `riskStratification` / `assertedFacts` / `inferredFacts` /
`sources` / `unmapped` / `dataQualityNotice`（+ `patient`、`disclaimer`）。
分端点 `/care-chain` `/assessment` `/risk` `/safety` 只是取子集。

| 字段 | 读法 |
|---|---|
| `fact_origin` | **唯一可信的真假判据**：`ehr-legacy` 真实上游 / `derived` 投影 / `demo-cohort` 演示队列。ID 前缀（`P00001` vs `P90001`）故意做成不可区分 |
| `birth_year: null` | 不是缺数据，是**拒绝用错数据**（上游 400 人中 329 人生日在未来）。不要据此推年龄，也不要说"数据缺失" |
| `assertedFacts[].trust` | `Curated` 可用；**`Unverified` 一律不参与判定、不在回答里当数值引用** |
| `dataQualityNotice` | 非 null ⟹ 本次涉及 Unverified 值，**后续所有数值结论降级**，只报管线事实 |
| `inferredFacts[].interval` | 由 `lowerOperator`/`upperOperator` 还原的开闭区间，如 `[6.5, +∞) percent`。**这是探针边界值的唯一合法来源**，逐字复述，不用 `>=` 近似 |
| `inferredFacts[].confirmationRequired` | true = 单次落区间**不足以**确诊。四条诊断级切点（A1C/FPG/OGTT2H/RPG）全为 true |
| `inferredFacts[].applicableContext` | 带 `(assumed)` = 无该状态记录、按缺省处理。开放世界下"没记录" ≠ "没有" |
| `verificationStatus` | `Provisional` = 只有一个日期的检验支撑，**不是确诊**；`Confirmed` = 另一日复测已确认 |
| `sources[].quote` / `sha256` | 逐字原文 + 内容哈希。**只能原样复制，返回体里没有的引文一个字都不许写** |
| `unmapped[]` | 判不了的项。空集与"有数据但判不了"是两回事，必须原样露出 |
| `monitoringGaps` | 可行动信息（如缺 UACR/eGFR 年检），单独成段说 |
| `insufficientReason` | `Insufficient-Evidence` 的原因，**原样转述，不许自己发明** |

### tier 判定（写死在 `ontology/rules/51-risk-stratification.rq`）

| tier | 触发条件 |
|---|---|
| `High` | 任一绝对禁忌命中 **或** 已确诊活动性慢性并发症 **或** 急性事件 |
| `Moderate` | 已确诊糖尿病 +（≥2 个可改变风险因子 **或** 存在监测缺口） |
| `Low` | 已确诊糖尿病，无上述任一项，且关键监测项齐全 |
| `Insufficient-Evidence` | 无可用血糖类证据 **或** 完全无可用风险侧事实 |

⚠️ `tier` 是**有序枚举**，不是分数：不得做算术、不得转成百分比、不得排序打分。
这也是 SKILL.md 里 T3 目标"多半推不动"的原因——它依赖禁忌/并发症/风险因子，
补一条检验通常改不了它。

---

## `POST /patients/{pid}/simulate`

body 是**对象**不是数组：

```json
{"assume": [{"term": "A1C", "value": 7.9, "unit": "percent", "date": "2026-02-20"}]}
```

可选：`refresh: true`（强制重取知识层快照，怀疑缓存过期时用）、
`includeUnreliable: true`（把 Unverified 值的规则也跑上——**默认不要开**，
会用 1300+ 条噪声结论淹没 diff）。

| 返回字段 | 语义 |
|---|---|
| `hypotheticalFacts[]` | 这次假设了什么。`hypothetical` 恒 true，`factOrigin` 恒 `simulated`。有 `conversionNote` 说明做过单位换算，**原值原单位必须一并转述** |
| `unchanged` | 假设没改变任何结论。**是结论不是故障** |
| `delta[]` | 结论级 diff：`changed`（最重要，`verificationStatus` 的 Provisional→Confirmed 在这里）/ `added` / `removed` |
| `derivationTree` | 推导树。`LabResult.provenance` = `measured` \| `hypothetical`，**回答时逐条标出** |
| `derivationHash` | f(pid, graphVersion, 知识快照, 规则集, 假设集)。同输入必同哈希；注入顺序不影响哈希 |
| `before` / `after` | 两轮规则跑完的结论快照。`before` 用于交叉核对，**不用于对外陈述患者现状** |
| `hypotheticalNote` / `disclaimer` | 两条尾注，**都要原样带上** |

### 推导树节点形状

```
◆ Diagnosis   diagnosisKind / verificationStatus / caveat / gapToConfirmed
  ▸ Assessment  conclusion / rule / applicableContext
    · DiagnosticThreshold  thresholdId / interval / confirmationRequired / sources[]
    · LabResult   value / unit / collectedDate / provenance
```

`Provisional` 的诊断节点带 `gapToConfirmed`——**它直接就是"还差什么"的答案，优先引用它**。

### 400 的两类拒绝

术语没挂阈值、单位缺失或无已核实换算系数。**照抄 detail 给用户，不要改名或换单位重试。**

---

## `GET /terms/explain?term=X`

四类归宿：`verified`（可参与判定）/ `candidate`（有线索未核实）/
`unmappable`（结构上无法数值判定，如尿蛋白是干化学定性项）/ `no-source-data`（本体有概念、上游无数据）。

推演推不动时，用它区分"上游无数据"与"有数据但结构上判不了"——
这两种"推不动"的原因完全不同，不能混为一谈。

---

## 错误码

| 码 | 场景 |
|---|---|
| 400 | 术语/单位被拒；模板给了空患者数组；`assume` 为空 |
| 404 | 患者不存在（或未 sync 进图库）；模板名不在白名单 |
| 422 | 参数类型不合法 |
| 500 | 服务端 PG / GraphDB 断连 → 先 `/health` |
