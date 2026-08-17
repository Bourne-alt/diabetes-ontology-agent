---
name: dmo-patient-graph-analysis
description: 用糖尿病本体图知识库（dmo 融合查询 API）深度分析患者病情，并做确定性病程推演。当用户问某个患者的诊断依据、阈值判定、风险分层、用药安全、"凭什么这么说"、"为什么查不到某个检验/术语"，或问"如果补一次检验结论会怎样""差什么才能确诊"这类 what-if，或需要跨 SQL 事实层与 SPARQL 语义层做证据溯源时使用。本 skill 规定了端点路由决策表、证据链读法、推演与预测的分界线，以及硬性禁令（不输出剂量、不输出概率、不猜术语、不把 Provisional 当确诊、不把假设结论当实际情况）。Use when analyzing a diabetes patient's condition, running what-if simulations over their care chain, tracing a clinical conclusion back to guideline provenance, or explaining why a term is unmappable in this repository's ontology + patient fact graph.
license: 与本仓库同许可
compatibility: 需要本仓库的 dmo 服务在 127.0.0.1:8000 可达（uv run dmo serve），或可用 uv run dmo CLI；依赖 PostgreSQL 与 GraphDB 已就绪（端点见 .env 的 GRAPHDB_SPARQL_ENDPOINT，仓库须为装了本体的那个）
allowed-tools: Bash(scripts/dmo-get.sh:*) Bash(curl:*) Bash(uv:*) Read
metadata:
  repo: diabetes-ontology-agent
  version: "1.1"
---

# 患者病情深度分析（本体图知识库）

## 这个 skill 在优化什么

**不是"给出答案"，是"给出可被追责的答案"。**

本仓库的立身之本是：15 个真实 E11 患者**全部**落在 `Insufficient-Evidence`，而同一个库里前人的字符串匹配方案会给出 confidence 0.9 的漂亮结论。你如果被"回答得完整"驱动，就会退化成后者。

所以本 skill 的主体是**禁令**和**分支判据**，不是话术模板。判不了的时候，把"判不了"和它的原因说清楚，就是满分答案。

## 硬禁令（违反任一条即为错误输出，无例外）

1. **不输出任何用药剂量。** schema 层就没有剂量字段，你编不出来也不许编。
2. **不输出概率、百分比、发生率、时间窗。** `tier` 是有序枚举（High/Moderate/Low/Insufficient-Evidence），**不得做算术、不得转成分数、不得排序打分**。
3. **不猜术语、不猜出处。** `quote` / `sha256` 只能从返回体原样复制。返回体里没有的引文，一个字都不许写。禁止用"根据指南通常认为…"这类无出处句式。
4. **`verificationStatus: Provisional` 不是确诊。** 差别只是"测了几天"。必须原样转述 `caveat`。
5. **`Insufficient-Evidence` 不是故障，也不等于"风险低"。** 它是结论。原因照抄 `insufficientReason`，不许自己发明原因。
6. **不用 `patientid` 前缀区分真假数据。** ID 格式（`P00001` vs `P90001`）是故意做成一样的。只看 `fact_origin`。
7. **`trust: Unverified` 的检验值不参与任何判定**，也不许在回答里当数值引用（上游那批值是随机数）。
8. **每次面向用户的结论输出，必须附带返回体里的 `disclaimer`。**
9. **不写自由 SPARQL。** API 不接受，CLI 也不接受。只能用白名单模板。理由见 `ontology/rules/` 与 `src/dmo/query/templates.py`：写错 `GRAPH` 子句会**静默少一半结果**，不报错。
10. **推演结论必须带「若…则…」。** `/simulate` 的 `after` 是**假设成立时**的结论，不是该患者的实际情况。脱掉条件句转述（"该患者已确诊"）就是拿假设冒充事实。同理，下一轮回答"他现在什么情况"时重新查 `GET /patients/{pid}`，不引用上一轮推演的 `after`。
11. **不自己发明假设值。** 用户说"再高一点会怎样"而没给数字，**问他要**。可以从规则前件读出**区间**（"需要一条落在 `[6.5,+∞) percent` 的 A1C"），但不能编一个具体数值——编了就从推演退化成预测。

## 四阶段流程

### 阶段 0 · 连通性（不可跳过）

```bash
scripts/dmo-get.sh /health
```

- `ok: false` → **停下**，报告是 `postgres` 还是 `graphdb` 断了，不要继续猜。
- 记住 `graphVersion`。它是知识层四个文件的内容哈希；同一轮对话里若它变了，说明本体被改过，此前所有术语映射与分层结论都必须重新查一遍。
- 服务没起 → `uv run dmo serve --port 8000`，或全程改用 CLI（见文末对照表）。

### 阶段 1 · 定位患者，并先判真假

```bash
scripts/dmo-get.sh '/patients?icd10=E11&size=20'
```

拿到人之后，**在写任何一句结论之前**先落两件事：

- `fact_origin`：`ehr-legacy`（真实上游） / `derived`（投影推出） / `demo-cohort`（演示队列）。
  分析结论里必须交代这个患者是哪一类。拿 `demo-cohort` 的漂亮结论去代表真实数据能力，是本仓库最忌讳的误导。
- `birth_year: null` **不是缺数据，是拒绝用错数据**（上游 400 人里 329 人生日落在未来）。不要因此推年龄，也不要说"数据缺失"。

### 阶段 2 · 一次性取骨架

```bash
scripts/dmo-get.sh /patients/P90002
```

七段返回体，**按这个顺序读，顺序本身就是防错设计**：

| # | 字段 | 先读它的理由 |
|---|---|---|
| 1 | `dataQualityNotice` | 非 null 说明本次涉及不可信值。它一出现，后面所有数值结论都要降级 |
| 2 | `assertedFacts[].trust` | `Curated` 才可用；`Unverified` 的值一律不引用 |
| 3 | `inferredFacts` | 结论本体。每条带 `ruleId` / `ruleVersion` |
| 4 | `sources` | 逐字原文 + sha256。**没有 sources 支撑的结论不许说出口** |
| 5 | `unmapped` | 判不了的项。空集和"有数据但判不了"是两回事 |
| 6 | `riskStratification` | 定性分层 |
| 7 | `careChain` | 时间线，用来回答"几个日期""顺序如何" |

需要单段时用分端点：`/care-chain` `/assessment` `/risk` `/safety`。

### 阶段 3 · 动态深挖（本 skill 的核心）

**"动态"= 根据上一次返回体里的具体字段值，决定下一个查哪里。** 逐条比对下表，命中就执行：

| 你在返回体里看到 | 下一步 | 为什么必须查 |
|---|---|---|
| `inferredFacts` 为空，但 `assertedFacts` 非空 | `/terms/explain?term=<该检验名>` | 区分"上游无数据"与"有数据但结构上判不了"。直接说"无异常"是错的 |
| `dataQualityNotice` 非 null | 停止数值推断，只报管线事实 | 那批值是随机数，任何基于它的判断都是噪声的函数 |
| `verificationStatus: "Provisional"` | `POST /query/latest_lab_result` 或 `/care-chain` 看**有几个采样日期** | 只有一天 ⟹ 必然 Provisional；补一天复测才可能 Confirmed（对比 P90002 vs P90003） |
| `applicableContext` 带 `(assumed)` | 在 `careChain` 里找有无妊娠相关观察 | 开放世界：没记录 ≠ 没怀孕。找不到就明写"这是假设" |
| `basedOn.sourceValue` 非空 | 在回答里同时给出原值+原单位与换算后值 | P90012：7.8 mmol/L 不换算会落进 `FPG-NORMAL`，结论完全相反 |
| `interval` 里出现 `(` 或 `)` | 逐字复述开闭区间，不要用 `>=` 近似 | 5.7 / 6.4 / 6.5 三个边界例（P90017-19）专测这个 |
| `tier: "Insufficient-Evidence"` | 读 `insufficientReason`，原样转述 | 这是结论不是缺陷。自己编原因就是编造 |
| `contributingFactors[].countedInTier: false` | 照样列出，并明说"不参与 tier 判定，因语料无可逐字引用的断言" | 过滤掉它们 = 假装缺口不存在 |
| `externalStandardNote` 非空 | **原样带上这句话** | 它在说"这个数值边界不是本仓库语料给的"（如 BMI≥30 来自 WHO 而非 CDC 原文） |
| `monitoringGaps` 非空 | 单独成段陈述 | 缺 UACR/eGFR 是可行动信息，比结论本身更有用 |
| safety 里 `severity: Absolute` | 引 `rationale` 原文 | 全库 FDA 语料只有两条真禁令 |
| safety 里 `Relative` / `Caution` | 明说这是**告知义务**不是禁令 | 原文是 "tell your doctor if…"，不是 "Do not take" |
| safety 返回空但用户觉得该有 | `/terms/explain` | 如 P90009（ESRD+二甲双胍）**必须零绝对禁忌**，语料无 eGFR 切点，补一个就是编造 |
| 用户问"某个检验/术语怎么没有" | `/terms/explain?term=X` | 四类归宿：`verified` / `candidate` / `unmappable` / `no-source-data` |
| 用户质疑"别的系统不是这么说的" | `/demo/compare?term=X` | 并排给出字符串匹配方案的结论与本方案的结论 |
| 用户问"补一次 X 会怎样""差什么才能确诊" | `POST /patients/{pid}/simulate` | 见阶段 3.5。**给了数值才推**，没给就问 |
| 用户问"他会不会发展成糖尿病" | **不推演** | 那是预测。说明不做，再问"您想假设哪个数值？" |
| 用户质疑"你这结论稳不稳/会不会每次都不一样" | 同一请求连推 5 次，给 `derivationHash` | 5 个哈希相同。这是相对 LLM 最硬的一条差异 |

跨患者对比、或需要单一维度的行级数据时用模板：

```bash
scripts/dmo-get.sh -X POST /query/care_chain '["P90002","P90003"]'
```

可用模板：`care_chain` `assessment_evidence` `diagnosis_evidence` `medication_safety` `risk_stratification` `latest_lab_result`。**空患者数组返回 400**——这是刻意的，空结果和"没给患者"长得一模一样。

字段级语义见 [references/endpoints.md](references/endpoints.md)。

### 阶段 3.5 · 确定性病程推演（问到 what-if 才走）

```bash
scripts/dmo-get.sh -X POST /patients/P90002/simulate \
  '{"assume":[{"term":"A1C","value":7.9,"unit":"percent","date":"2026-02-20"}]}'
```

只能推挂了阈值的 7 项：`A1C FPG GCT1H GLU OGTT2H RPG UACR`。
库里上百个从指南抽出来的同名项**没有阈值**，推了得空集，而空集看起来和"结论没变"
一模一样——API 会 400 并列出可用项，**照抄那句拒绝理由，不要改个名字重试**。

读返回体的顺序：`hypotheticalFacts` → `unchanged` → `delta` → `derivationTree`。
`unchanged: true` 是结论不是故障。`derivationTree` 里每个 `LabResult` 节点都带
`provenance: measured | hypothetical`，**回答时必须逐条标出来**。

推演不写 GraphDB 一个字节（内存 Dataset，只发 CONSTRUCT），可以放心多跑。

完整字段语义、单位规则、边界自测用例见 [references/simulation.md](references/simulation.md)。

### 阶段 4 · 输出

结构固定，缺段即为不合格。写法与反例见 [references/report-contract.md](references/report-contract.md)。

```
【患者】P90002 · fact_origin=demo-cohort（演示队列，非真实上游）
【数据质量】<dataQualityNotice 原文，或"本次涉及的检验值均为 Curated">
【结论】<inferredFacts 逐条：结论 + ruleId@ruleVersion + 所用阈值区间>
【依据】<sources 逐条：quote 原文 + sha256 前 8 位 + supports>
【限定】<caveat / applicableContext 的 assumed / externalStandardNote>
【判不了的】<unmapped：项 + 原因>
【风险分层】<tier + 因子（含 countedInTier=false 的）+ 监测缺口>
⚠️ <disclaimer 原文>
```

推演（阶段 3.5）另用一套结构 —— 条件句必须在最前面，不能等到末尾才补：

```
【假设】若 P90002 补一条 2026-02-20 的 A1C 7.9% percent（由您给出，系统不生成数值）
【结论变化】Diagnosis.verificationStatus: Provisional → Confirmed
【为什么】<delta 里 changed 的 caveat 前后对照：从"只有 1 个日期支撑"到"2 个不同日期支撑">
【推导树】<逐层展开，每条 LabResult 标 [实测] / [假设]>
【确定性】derivationHash <前 16 位>；同一假设重复推演结果不变
⚠️ 以上结论建立在假设之上，不是该患者的实际情况。
⚠️ <disclaimer 原文>
```

## 交付前自检

逐条确认，任一条为"否"就不要发出：

- [ ] 每个结论都能指到 `ruleId` 或 `sources` 里的某一条？
- [ ] 所有 `quote` 都是从返回体复制的，没有一个字是我写的？
- [ ] 没有出现剂量、概率、百分比、时间窗？
- [ ] `Provisional` 有没有被我说成"确诊"或"患有"？
- [ ] `Insufficient-Evidence` 有没有被我说成"风险低"或"系统异常"？
- [ ] `fact_origin` 交代了吗？
- [ ] `unmapped` 和 `monitoringGaps` 露出来了吗，还是被我"整理"掉了？
- [ ] `disclaimer` 带上了吗？

做了推演的话，再加四条：

- [ ] 每一句推演结论都带「若…则…」，没有一句脱掉条件句？
- [ ] 假设值是用户给的，不是我填的？
- [ ] 推导树里 `[实测]` 与 `[假设]` 逐条标出来了，没有混在一起陈述？
- [ ] 有没有把推演的 `after` 当成该患者的现状？

## 什么时候**不要**用这个 skill

- 改本体 / 调 SHACL / 跑 ETL / 重建 TBox → 走 `ontology/tools/` 和 `uv run dmo db|etl|map|sync`，不走查询 API。
- 用户要真实临床建议 → 拒绝。这是技术验证服务，不是医疗器械。
- 用户要自由 SPARQL → 说明不提供，并给出最接近的模板。
- 用户要**病程预测**（会不会发展成、多久会、概率多大）→ 拒绝，说明本系统做的是条件推演不是预测，然后把问题转成可推演的形式："您想假设哪个检验、哪个数值？"

## API ↔ CLI 对照（服务没起时用右列）

| API | CLI |
|---|---|
| `GET /patients/{pid}` | `uv run dmo show P90002` |
| `POST /query/{tpl}` | `uv run dmo query care_chain --patient P90002` |
| `GET /query/templates` | `uv run dmo query` |
| `GET /terms/explain` | `uv run dmo explain 糖化血红蛋白` |
| `GET /demo/compare` | `uv run dmo demo compare --term 尿蛋白` |
| `POST /patients/{pid}/simulate` | `uv run dmo simulate P90002 --assume A1C 7.9 percent 2026-02-20` |
| `GET /health` | `uv run dmo db status` |

两条路径走**同一份** `query/hybrid.py`，答案必然一致。

## 自测语料

演示队列 P90001–P90030 覆盖 27 个场景，每个场景都有预期结论。改完 skill 或怀疑判断跑偏时，拿 [references/scenarios.md](references/scenarios.md) 里的用例对一遍。
