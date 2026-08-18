# 融合查询 API 使用说明

> 本文所有响应示例均由**实际运行的服务**导出，未经手工编辑。
> 数据来自 `hospital_zd.patient_analysis`（400 真实患者，只读）+ 30 例演示队列。

---

## 0. 这个 API 和普通 CRUD 的差别

它回答的不是「这个患者的 A1C 是多少」，而是**「凭什么这么说」**。所以每个响应都强制带四样东西：

| 字段 | 存在的理由 |
|---|---|
| `sources` | 每条结论回溯到指南**逐字原文** + sha256。31 条引文由 `verify_passages.py` 逐字回原文校验 |
| `inferredFacts[].ruleId` / `ruleVersion` | 结论是哪条规则、哪个版本得出的。规则改了，旧结论能被识别出来 |
| `unmapped` | **判不了的东西必须说出来**。返回空集和「有数据但不可判定」是两回事 |
| `dataQualityNotice` | 涉及不可信值时强制出现 |

三条硬约束，有测试断言兜底：

1. **不输出任何用药剂量**（schema 层就没有剂量字段）
2. **不输出概率、百分比、时间窗**。`tier` 是有序枚举不是分数
3. **不猜术语**。未命中只记账，无编辑距离、无 embedding

---

## 1. 启动

任选其一（均需已安装 `serve` / `db` 依赖，见 [README](../README.md)）：

```bash
# uv（推荐）
uv run dmo serve --port 8100

# python（已 pip/uv sync 安装 dmo 包时）
python -m dmo.cli serve --port 8100

# uvicorn（直接挂载 FastAPI app，便于热重载）
uvicorn dmo.api:app --host 127.0.0.1 --port 8100 --reload
```

前置：PG 可达、GraphDB 在 `localhost:7200`、数据管线已跑过一轮（见 [README](../README.md) 端到端复现）。

⚠️ `DMO_GRAPHDB_ENDPOINT` **只填根地址**（`http://host:7200`），不带 `/repositories`、
也不带任何路径前缀 —— 应用自己拼 `/repositories/<repository>`。填成 `http://host:7200/dmo`
会拼出 `/dmo/repositories/dmo`，GraphDB 回 405/406，`/health` 里表现为 `graphdb` 断连。
详见 [DOCKER.md](DOCKER.md)。

无鉴权、无限流，**仅绑定 `127.0.0.1`**。这是技术验证服务，不要暴露到公网。

交互式文档：`http://localhost:8100/docs`（FastAPI 自带 Swagger UI）。

---

## 2. 端点总览

| 方法 | 路径 | 走 SQL 还是 SPARQL | 用途 |
|---|---|---|---|
| GET | `/` | — | 服务信息与关键入口导航 |
| GET | `/health` | 两者 | 连通性 + 数据量 + 本体版本 |
| GET | `/patients` | **SQL** | 检索与分页 |
| GET | `/patients/{pid}` | 两者 | 完整返回体（七段） |
| GET | `/patients/{pid}/care-chain` | SPARQL | 就诊→检验→诊断→用药全链 |
| GET | `/patients/{pid}/assessment` | SPARQL | 阈值判定 + 出处 |
| GET | `/patients/{pid}/risk` | SQL（读物化结果） | 风险分层 |
| GET | `/patients/{pid}/safety` | SPARQL | 用药安全信号 |
| POST | `/patients/{pid}/simulate` | **内存推演** | 确定性病程推演 + 推导树 |
| POST | `/simulate` | **内存推演** | 同上，`patientId` 走 body（静态路径，给 MCP 用） |
| GET | `/query/templates` | — | 列出模板白名单 |
| POST | `/query/{template}` | SPARQL | 跑参数化模板 |
| GET | `/terms/unmapped` | SQL | 全部未命中/不可用术语 |
| GET | `/terms/explain` | SQL | **为什么查不到某个术语** |
| GET | `/demo/compare` | 两者 | 字符串匹配 vs 本体，并排对照 |
| **裁决族** | | | **提问方向相反：不是「这个患者什么情况」，是「有人说了这句话，对不对」** |
| GET | `/adjudicate/scope` | SPARQL | **我能裁决什么、不能裁决什么**（调裁决前先读） |
| POST | `/adjudicate/citations` | SPARQL | 裁决别人的**引用**是不是逐字成立 |
| POST | `/adjudicate/claim` | 两者 | 裁决别人给出的**结论**对不对 |
| **图探索族** | | | **给智能体的「下一跳」，GRAPH 子句由服务端拼** |
| GET | `/graph/concepts` | SQL | **中文表面形式 → 准确 IRI**（图探索唯一入口） |
| GET | `/graph/node` | SPARQL | 节点邻接摘要 + 哪些类型是推理机推的 |
| GET | `/graph/neighbors` | SPARQL | 展开一跳 |
| GET | `/graph/taxonomy` | SPARQL | 上位/下位，标出哪些边是推出来的 |
| GET | `/graph/path` | SPARQL | 两个节点之间怎么连上的（受控 BFS） |
| GET | `/graph/rules` | SPARQL | 规则内省：阈值 / 管理目标 / 风险规则 |
| GET | `/graph/rules/{id}` | SPARQL | 单条规则全貌 + 展开的逐字出处 |
| GET | `/graph/passages` | SPARQL | 可引用出处检索 |
| GET | `/graph/provenance` | 两者 | **结论 → 支撑链 → 原文 → SQL 原始行** |
| GET | `/graph/schema` | 两者 | schema 卡片：RDF 侧 / SQL 侧 / 列↔谓词桥接表 |
| POST | `/graph/sparql` | SPARQL | 自由 SPARQL 逃生口（静态检查通过才执行） |
| GET | `/agent/manifest` | — | **能力清单 + 调用顺序 + 铁律 + 硬禁令**（智能体自举） |

后两族出自 [ADJUDICATE-EXPLORE-API-PLAN.md](ADJUDICATE-EXPLORE-API-PLAN.md)，见 §12.6–12.13。
**智能体从 `GET /agent/manifest` 起步**：那里有全部端点、参数名、七步调用顺序与硬禁令，
且从 `app.routes` 现场生成，不会和实际服务分叉。

**职责边界是写死的**：有多少 / 哪些 / 分页 → SQL；为什么 / 凭什么 / 依据哪条指南 → SPARQL；
原始那一行长什么样 → SQL（`source_pk` 回查）。

---

## 3. `GET /health`

```bash
curl http://localhost:8100/health
```

```json
{
  "ok": true,
  "graphVersion": "1ef104f6e31a6861",
  "patients": 430,
  "labResults": 1374,
  "stratified": 33,
  "graphdbTriples": 102234
}
```

`graphVersion` 是**知识层四个文件的内容哈希**（TBox / 公理 / 阈值 seed / 风险映射）。
它变了就说明本体改过，此前的术语映射和分层结论都该重新审视。

`ok: false` 时会多出 `postgres` 或 `graphdb` 字段说明是哪一侧断了。

`graphdbTriples` 随装载批次变化（抽取图装了多少份语料、规则跑没跑过），
**不是**判断"数据对不对"的指标；判断对不对看 `graphVersion` 和 `GET /graph/rules` 的 `counts`。

---

## 4. `GET /patients` — SQL 侧检索

| 参数 | 取值 | 说明 |
|---|---|---|
| `icd10` | 如 `E11` | 按诊断的外部编码筛 |
| `origin` | `ehr-legacy` / `derived` / `demo-cohort` | **真实数据与演示数据的分界线** |
| `scenario` | 如 `S02` | 演示场景编号 |
| `tier` | `High` / `Moderate` / `Low` / `Insufficient-Evidence` | 风险分层 |
| `page` / `size` | 默认 1 / 20，`size` 上限 200 | |

```bash
curl 'http://localhost:8100/patients?icd10=E11&size=2'
```

```json
{
  "total": 31,
  "page": 1,
  "size": 2,
  "patients": [
    {
      "patientid": "P00016",
      "sex": "F",
      "birth_year": null,
      "fact_origin": "ehr-legacy",
      "demo_scenario": null,
      "source_table": "patient_analysis.patient_basic_info",
      "source_pk": "P00016",
      "tier": "Insufficient-Evidence",
      "insufficient_reason": "没有可用于阈值判定的血糖类检验（上游数值均为 valueTrustLevel=Unverified，或该检验项在本仓库语料中无诊断切点）。没有任何可用的风险侧事实（无临床观察、无共病或并发症诊断）——无法据此说风险低，只能说不知道。"
    }
  ]
}
```

**`birth_year: null` 不是缺数据，是拒绝用错数据。** 上游 `birthday` 400 人里有 329 人落在未来
（最晚 2063-09-14），投影层判定不可信后置 NULL —— 缺失是诚实的，负数年龄不是。

**永远用 `fact_origin` 区分真假。** ID 格式故意做成一样的（`P00001` vs `P90001`），
就是为了证明管线不靠 ID 形状区分，而靠数据上的显式标记。

---

## 5. `GET /patients/{pid}/assessment` — 阈值判定与出处

这是最能说明问题的端点。

```bash
curl http://localhost:8100/patients/P90002/assessment
```

```json
{
  "inferredFacts": [
    {
      "type": "dmo:Assessment",
      "conclusion": "DiabetesRange",
      "ruleId": "LAB-THRESHOLD-MATCH",
      "ruleVersion": "1.0.0",
      "applicableContext": "NonPregnant(assumed)",
      "appliesThreshold": "A1C-DIABETES-NONPREG",
      "confirmationRequired": true,
      "interval": "[6.5, +∞) percent",
      "basedOn": {
        "labResultId": "L90002-A1C", "value": "7.4", "unit": "percent",
        "sourceValue": null, "sourceUnit": null
      },
      "caveat": null
    },
    {
      "type": "dmo:Diagnosis",
      "verificationStatus": "Provisional",
      "clinicalStatus": "Active",
      "factOrigin": "derived",
      "caveat": "⚠️ **单次异常不等于确诊**：阈值 A1C-DIABETES-NONPREG 标注 confirmationRequired=true，而目前只有 1 个日期的检验支撑。需另一日复测确认后才能定为 Confirmed。"
    }
  ],
  "sources": [
    {
      "quote": "6.5% or above",
      "sha256": "96495c7d996a92b5bee7132029744f08e5154be98dd1be7e177399320d7d1447",
      "supports": "A1C-DIABETES-NONPREG"
    }
  ],
  "assertedFacts": [
    {
      "iri": "L90002-A1C", "test": "A1C", "value": "7.4", "unit": "percent",
      "trust": "Curated", "origin": "demo-cohort", "demo_scenario": "S02",
      "sqlRow": { "table": "diabetes.sim_lab_result", "pk": "L90002-A1C" }
    }
  ],
  "disclaimer": "⚠️ 技术验证用途，不是医疗器械，不构成医疗建议。……"
}
```

### 三个必须读懂的字段

**`verificationStatus: "Provisional"` 而不是 `Confirmed`。**
A1C 7.4% 确实落在糖尿病区间，但指南的诊断表说的是「单次测量落在哪一档」，不等于确诊。
四条诊断级切点（A1C/FPG/OGTT2H/RPG）都标了 `confirmationRequired=true`，
需要**另一个日期**的复测。P90003 有两天数据，同样的阈值就出 `Confirmed`。

> 纯 LLM 和字符串匹配在这里都会直接说「是糖尿病」。

**`applicableContext: "NonPregnant(assumed)"` 的 `(assumed)` 是关键。**
患者没有妊娠状态记录时按非妊娠处理，但如实标注这是**假设**不是事实 ——
开放世界下「没记录」≠「没怀孕」。对比 P90004（孕 26 周）与 P90005（同为 142 mg/dL 非妊娠）：
前者命中妊娠期转诊触发点，后者零命中。

**`interval` 是把开闭区间还原成人能读的形式。** `[6.5, +∞)` 的方括号来自 `lowerOperator="GTE"`。
用 `>=` 近似「below 5.7%」会把 5.7 错判成 Normal —— S16 三例专测这个边界。

**`sourceValue` / `sourceUnit`** 在发生过单位换算时非空。P90012（S11）是这个字段的用途：

```json
{ "value": "140.54196", "unit": "mg-per-dL",
  "sourceValue": "7.8", "sourceUnit": "mmol-per-L" }
```

7.8 mmol/L 不换算会被当成 mg/dL 读，落进 `FPG-NORMAL`（≤99）—— 结论完全相反。
换算只在 ETL 做，SPARQL 里一次都不做（系数是分析物特有的：葡萄糖 ×18.0182、肌酐 ÷88.4）。

---

## 6. `GET /patients/{pid}/risk` — 风险分层

⚠️ **这不是概率预测。** 不输出百分比、不输出时间窗。理由见 [README](../README.md)：
上游 15 个 E11 患者、每人 1 次检验、检验值是随机数、零结局标签、零随访 ——
在这上面训练任何模型，学到的都是随机数的函数。

```bash
curl http://localhost:8100/patients/P90020/risk
```

```json
{
  "riskStratification": {
    "tier": "Moderate",
    "ruleId": "RISK-STRATIFICATION",
    "ruleVersion": "1.0.0",
    "insufficientReason": null,
    "monitoringGaps": ["缺 UACR（尿白蛋白肌酐比）。语料要求对糖尿病患者定期监测 UACR 与 eGFR。"],
    "contributingFactors": [
      {
        "riskRuleId": "BMI-OBESITY",
        "label": "Obesity",
        "riskCategory": "Modifiable",
        "triggerBasis": "external-standard",
        "countedInTier": true,
        "quote": "However, people are more likely to develop type 2 diabetes if they have overweight, obesity, or a large waist size.",
        "sha256": "9449c5863f9c534b8e8ca36cef03f3977929d1dd2df2dc4076280bcd9009456f",
        "externalStandardNote": "BMI 30 kg/m² 的肥胖切点来自 WHO 通用定义，不在本仓库语料中。",
        "fromFact": "https://example.org/dmo/id/observation/O90020-BMI"
      },
      {
        "riskRuleId": "PHYSICAL-INACTIVITY",
        "label": "Physical Inactivity Less Than 3 Times a Week",
        "riskCategory": "Modifiable",
        "triggerBasis": "corpus-verbatim",
        "countedInTier": true,
        "quote": "Being physically active less than 3 times a week",
        "sha256": "6f99e6e1ba52ad2887fb8c826225919ceb9d7d18467b8d0799260a13f22e5d91",
        "externalStandardNote": null,
        "fromFact": "https://example.org/dmo/id/observation/O90020-ACT"
      }
    ],
    "note": "定性分层，非概率预测：不含发生概率、不含时间窗。……"
  }
}
```

### 四档的判定规则

| tier | 触发条件 |
|---|---|
| `High` | 任一绝对禁忌命中，**或**已确诊活动性慢性并发症，**或**急性事件 |
| `Moderate` | 已确诊糖尿病 + （≥2 个可改变风险因子 **或** 存在监测缺口） |
| `Low` | 已确诊糖尿病，无上述任一项，且关键监测项齐全 |
| `Insufficient-Evidence` | 没有可用的血糖类证据，**或**完全没有可用的风险侧事实 |

规则写死在 `ontology/rules/51-risk-stratification.rq`，版本化。SQL 侧只物化结果、**不做判定**。

### `triggerBasis` 是这个端点最重要的字段

| 取值 | 含义 |
|---|---|
| `corpus-verbatim` | 判定条件**直接来自所引原文**。如「每周体力活动少于 3 次」，边界 3 就写在 CDC 原文里 |
| `external-standard` | **数值边界来自本仓库语料之外**，必须配 `externalStandardNote` 说明来源 |

CDC 原文只说 "Being overweight"，**没有给任何 BMI 数值切点**。所以「BMI ≥ 30」这个边界
不是指南说的，是 WHO 的通用定义。假装它有出处，就和对照组把「尿蛋白 10.4」链到
糖尿病肾病是同一类错误，只是更隐蔽。

### `countedInTier: false` 的因子

有些风险因子在抽取产物里有，但本仓库语料**没有可逐字引用的断言**
（如「高血压 ⟹ 2 型糖尿病风险升高」）。这类规则：

- 照样产出命中记录，出现在 `contributingFactors` 里
- 但 `countedInTier: false`，**不参与 tier 判定**
- `quote` 与 `sha256` 为 `null`

这是刻意的：过滤掉它们不等于假装它们不存在。缺口要可见。

### `Insufficient-Evidence` 才是常态

```bash
curl http://localhost:8100/patients/P00016/risk
```

15 个真实 E11 患者**全部**落在这一档，`insufficientReason` 说清三个原因：
检验值均为 `Unverified`、无任何可用风险侧事实、年龄推不出来。

这不是 bug。同一个库里前人的做法是给一个 confidence 0.9 的答案（见 `/demo/compare`）。

---

## 7. `GET /patients/{pid}/safety` — 用药安全

```bash
curl http://localhost:8100/patients/P90008/safety
```

`sources` 里会出现绝对禁忌的原文：

```json
[{ "quote": "Do not take these drugs if you have severe kidney problems or are on dialysis.",
   "sha256": "", "supports": "contraindication:Absolute" }]
```

> ⚠️ 已知限制：禁忌的 `rationale` 目前是 `dmo-axioms.ttl` 里的直引字符串，**尚未建成
> `SourcePassage`**，所以 `sha256` 为空字符串。阈值那条链是完整的，禁忌这条链还差一步。

### 语料里只有两条真禁令

全库 FDA 语料中，明确的 "Do not take" 只有两条：
SGLT2i + 重度肾病/透析、bromocriptine + 哺乳。
其余全部是 "Before you start taking these drugs, **tell your doctor** if…" ——
那是**告知义务不是禁令**，一律标为 `Relative` / `Caution`。

所以 **P90009（ESRD + 二甲双胍）必须零绝对禁忌**。语料对二甲双胍只有乳酸酸中毒的定性表述，
没有任何 eGFR 数值切点，补一个就是编造出处。这一点有回归测试盯着。

第二条禁令（哺乳）**无法自动判定**：哺乳是生理状态不是并发症，schema 的
`triggeredByCondition` 接不上。这个缺口由 `/terms/explain` 如实上报，不用假的 Complication 掩盖。

---

## 8. `POST /query/{template}` — 参数化模板

**不接受自由 SPARQL。** 三个理由，按严重程度排：

1. 知识侧误写 `GRAPH <urn:dmo:seed>` 会吃不到 owl2-rl 的物化边 —— 查询不报错，**只是答案少一半**
2. 患者侧漏写 `STRSTARTS(?pg, "urn:dmo:patient:")` 会扫到 6 例故意造错的 SHACL 反例夹具
3. 全库扫描 430 个患者图，在演示里看不出问题，上量就是灾难

```bash
curl http://localhost:8100/query/templates
curl -X POST http://localhost:8100/query/care_chain \
     -H 'Content-Type: application/json' -d '["P90002"]'
```

```json
{
  "template": "care_chain",
  "rows": [
    { "pid": "P90002", "kind": "Encounter",
      "node": "https://example.org/dmo/id/encounter/E90002-1",
      "label": "Routine", "value": "", "unit": "", "at": "2026-01-15" },
    { "pid": "P90002", "kind": "LabResult",
      "node": "https://example.org/dmo/id/labResult/L90002-A1C",
      "label": "A1C", "value": "7.4", "unit": "percent", "at": "2026-01-15T09:00:00" }
  ]
}
```

| 模板 | 用途 |
|---|---|
| `care_chain` | 就诊 → 检验/观察 → 诊断 → 用药全链 |
| `assessment_evidence` | 阈值判定 + 所用阈值 + 逐字出处 + 内容哈希 |
| `diagnosis_evidence` | 诊断记录 + 是断言的还是推出来的 + 支撑它的评估 |
| `medication_safety` | 用药安全信号（三个级别） |
| `risk_stratification` | 分层结论 + 每个因子及其出处 |
| `latest_lab_result` | 每个患者每个检验项的最新一次结果 |

请求体是患者号数组。**空数组返回 400**，不静默返回空集 —— 空结果和「没给患者」长得一模一样。

---

## 9. `GET /terms/explain` — 为什么查不到

```bash
curl 'http://localhost:8100/terms/explain?term=糖化血红蛋白'
```

```json
{
  "term": "糖化血红蛋白",
  "verdicts": [
    "「糖化血红蛋白」在本体里有概念（A1C Test），但上游全库**没有这个检验的数值**：cdr_lis_result 的 12 种子项名不含它。……",
    "上游有名为「糖化血红蛋白」的**检验大项**（19 条），但大项名与其下子项的实际内容语义错位（实测其下挂的子项是 AST/尿蛋白/血小板/尿素氮），因此大项名一律不做术语映射 —— 映射它等于主动制造错误。"
  ],
  "upstreamResultRows": 0,
  "upstreamParentItemOnly": [{ "itemname": "糖化血红蛋白", "n": 19 }],
  "candidateConcepts": [{
    "iri": "https://example.org/dmo/id/LabTest-A1C",
    "concept_kind": "LabTest", "code": "A1C", "label": "A1C Test",
    "alt_labels": ["A1C", "HbA1c", "hemoglobin A1C", "glycated hemoglobin", "糖化血红蛋白", "糖化血红蛋白A1c"],
    "unit_canonical": "percent"
  }]
}
```

`upstreamResultRows: 0` 但 `upstreamParentItemOnly` 有 19 条 —— 这一对数字就是整个故事：
**它作为大项名存在，但底下一条真的 A1C 数值都没有。**

四类归宿（`verify_status`）：

| 状态 | 含义 | 是否参与判定 |
|---|---|---|
| `verified` | 人工核实过 | ✅ |
| `candidate` | 有线索但**未核实** | ❌ |
| `unmappable` | 结构上无法数值判定（尿蛋白是定性项） | ❌ |
| `no-source-data` | 本体有概念，**上游全库无数据** | ❌ |

---

## 10. `GET /demo/compare` — 两种做法并排

```bash
curl 'http://localhost:8100/demo/compare?term=尿蛋白'
```

同一条上游数据「尿蛋白 = 10.4，参考范围『阴性』」：

**左栏**（同库 `semantic_link` schema，前人的字符串匹配尝试）：
链到「微量白蛋白定量」confidence 0.95、「糖尿病肾病」confidence 0.9，
`hasUnit: false`、`hasThreshold: false`、`hasProvenance: false`。

**右栏**（本方案）：概念 `Urine Protein (dipstick)`，
`value_kind: qualitative`、`verify_status: unmappable`，理由写在 `note` 里 ——
参考范围是「阴性」说明这是干化学定性项，那个「10.4」根本不该当数值读；
要判断白蛋白尿必须用 UACR（mg/g，切点 >30），是另一个检验。

> `semantic_link` 保留只读、不迁移、不修改。它是本方案最好的对照组。

---

## 11. 错误响应

FastAPI 标准形状：

```json
{ "detail": "core_patient 里没有 P99999" }
```

| 状态码 | 场景 |
|---|---|
| 400 | `POST /query/{template}` 给了空患者数组；`/simulate` 的假设不合法（术语不在白名单、缺单位）；`/adjudicate/*` 的入参不成立；`/graph/*` 的 `iri` 不是完整 IRI；`POST /graph/sparql` **未通过静态检查** |
| 404 | 患者不存在；模板名不在白名单；`/graph/rules/{id}` 无此规则 |
| 422 | 参数类型不合法（FastAPI 自动校验） |
| 500 | 本服务自身出错 |
| 503 | **GraphDB 不可用**。返回体带 `hint`，先查 `/health` |

**400 不等于"你传错了格式"。** 本 API 有一批拒绝是**有意的业务判断**，消息本身就是答案：

```jsonc
// POST /simulate
{ "detail": "「糖化血红蛋白」不在可推演的 7 个术语里 —— 库里上百个同名检验项没有阈值，
            接受它们只会推出空集，而空集看起来和「结论没变」一模一样。" }

// POST /graph/sparql
{ "detail": "查询未通过静态检查。",
  "guard": { "passed": false,
             "reasons": ["`?pg` 没有患者图守卫。不加会扫到 urn:dmo:data 里那 6 例
                          **故意造错的反例夹具**……请加上：FILTER(STRSTARTS(…))"] } }
```

`guard.reasons` 是**写给模型看的**：它会作为 observation 回去自我修正，
所以写的是"该补哪一句"，不是 "rule A violation"。

**500 与 503 的区分是刻意的。** 500 的含义是"本服务出错了"，会让调用方去查自己的请求；
连不上上游是**依赖不可用**，是运维问题。混在一起每次都要翻堆栈才知道不是代码的锅。

---

## 12. 常见误用

| 做法 | 为什么不行 |
|---|---|
| 用 `patientid` 前缀区分真假数据 | ID 格式故意做成一样的。用 `fact_origin` |
| 把 `tier` 当风险评分做算术 | 它是有序枚举不是分数。想要连续值就得训模型，而这批数据训不出东西 |
| 把 `verificationStatus: Provisional` 当确诊 | 差别就是「测了几天」。`caveat` 里写清楚了 |
| 忽略 `externalStandardNote` | 那句话在说「这个数值边界不是指南给的」 |
| 拿 `Insufficient-Evidence` 当「系统故障」 | 那是结论。`insufficientReason` 说清了为什么 |
| 直接用上游检验数值 | `trust: Unverified` 的值是随机数，默认不参与任何判定 |
| 期待返回体里有用药剂量 | schema 层就没有这个字段。这是设计不是遗漏 |
| 用 `?x a dmo:RiskRule` 数规则 | prp-dom 会把每条患者命中记录也判成规则，查出来是 73 条不是 12 条。以 `riskRuleId` 为准，见 §12.10 |
| 把 `citations` 的 `verbatim` 当"这条结论对" | 它只说明引文与本库某条出处逐字一致。引对了话可能用错地方 —— 那是 `/adjudicate/claim` 的 `misattributed` |
| 把 `adjudicate` 的 `unsupported` 当"判定为错" | 证据不足与判错是两回事。`missingEvidence` 说清差什么 |
| 拿 `/adjudicate/scope` 里 `status: planned` 的类型当"判过了没问题" | planned = 没接线。真调用会返 `not-adjudicable` |
| 先写 SPARQL 再想办法拿 IRI | 反了。`GET /graph/concepts` 是图探索的唯一入口，拼错的 IRI 查出来是空集，和"没有数据"长得一模一样 |
| 拿 `POST /graph/sparql` 当默认查询手段 | 它是第 13 个工具不是第 1 个。前 12 个的 GRAPH 子句由服务端拼，不会静默少返 |

---

## 12.5 `POST /patients/{pid}/simulate` — 确定性病程推演

回答「**若** 补一条检验，结论**则**变成什么」，并把每一步的依据摊开。

```bash
curl -X POST localhost:8100/patients/P90002/simulate \
  -H 'Content-Type: application/json' \
  -d '{"assume":[{"term":"A1C","value":7.9,"unit":"percent","date":"2026-02-20"}]}'
```

患者号也可以放进 body，路径写死 —— 给只能配静态 URL 的调用方（如 MCP 工具定义）：

```bash
curl -X POST localhost:8100/simulate \
  -H 'Content-Type: application/json' \
  -d '{"patientId":"P90002",
       "assume":[{"term":"A1C","value":7.9,"unit":"percent","date":"2026-02-20"}]}'
```

两条路由是同一个函数、同一个 `derivationHash`；`patientId` 缺失或为空 → 400。

P90002 现有一次 A1C 7.4%（S02，单次异常 ⟹ `Provisional`）。补一个**不同日期**的
7.9% 之后：

```
Diagnosis.verificationStatus: Provisional → Confirmed
```

两次结论的差别**只有测了几天** —— 30 号规则数的是 `COUNT(DISTINCT ?day)`。

### 这不是预测

| 允许 | 禁止 |
|---|---|
| 「**若** A1C = 7.9%，**则** 触发 R30，结论 Confirmed」 | 「该患者 A1C 可能升到 7.9%」 |
| 条件蕴含 | 状态外推 |

假设值**只能由调用方显式给出**。系统没有任何生成候选值的代码路径 ——
`hypotheticalFacts[].hypothetical` 恒为 `true`，`factOrigin` 恒为 `simulated`。

### 返回体要点

| 字段 | 说明 |
|---|---|
| `derivationHash` | = f(pid, graphVersion, 知识快照, 规则集哈希, 假设集)。**同输入必同哈希** |
| `delta` | 结论级 diff：`changed` / `added` / `removed`，不是三元组级噪声 |
| `derivationTree` | 推导树。每个 `LabResult` 节点标 `measured` 或 `hypothetical` |
| `before` / `after` | 两轮规则跑完的结论快照 |
| `unchanged` | 假设没改变任何结论时为 `true` —— 这是结论，不是故障 |

### 确定性可当场验证

```bash
for i in 1 2 3 4 5; do
  curl -s -X POST localhost:8100/patients/P90002/simulate \
    -H 'Content-Type: application/json' \
    -d '{"assume":[{"term":"A1C","value":7.9,"unit":"percent","date":"2026-02-20"}]}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["derivationHash"])'
done
```

五行输出完全相同。同一个问题问 LLM 五遍，答案会飘 —— 这是本体最硬的一条差异。

### 两条拒绝（400），和能推出结论同等重要

| 请求 | 拒绝理由 |
|---|---|
| `term: "糖化血红蛋白"` / `"hba1c"` | 只有挂了阈值的 7 项可推演：`A1C FPG GCT1H GLU OGTT2H RPG UACR`。库里上百个从指南抽取的同名检验项**没有阈值**，接受它们只会推出空集 —— 而空集看起来和「结论没变」一模一样 |
| `unit` 缺失或无已核实换算系数 | 148 是 mg/dL 还是 mmol/L，结论天差地别。`mmol-per-L → mg-per-dL` 有已核实系数（×18.0182），会换算并保留 `sourceValue`/`sourceUnit`；A1C 的 `mmol-per-mol` 没有，直接拒 |

### 不写 GraphDB 一个字节

推演全程在内存 rdflib Dataset 里跑，对 GraphDB 只发 `CONSTRUCT`。
调多少次，库里三元组数一条都不变 —— `tests/test_simulate.py::test_simulation_never_writes_to_graphdb`
用前后 `size()` 相等盯着这件事。

不在 GraphDB 里建临时图的三个理由见 `src/dmo/simulate/sandbox.py` 开头，
核心一条：规则的患者侧写死了 `STRSTARTS(?pg, "urn:dmo:patient:")`，
sandbox 图想被规则看见就得用这个前缀，那它同时会被全库扫描扫到，
假设数据当场变成「真患者」。

---

## 12.6 `GET /adjudicate/scope` — 能力边界本身也是 API

调用裁决族之前先读这个。两个用途：让智能体在调用前就能判断该不该调；挡住把本 API
当「权威印章」用。

- `adjudicable[].status` 如实标 `available` / `planned`。当前 6 类全部 available：
  `Citation`、`Assessment`、`TargetAttainment`、`Diagnosis`、`RiskTier`、`MedicationSafety`。
  **这个字段和代码里真正接线的 `adjudicate.claim.ADJUDICABLE` 有测试对齐** ——
  以后加类型忘了改 scope，CI 会亮。把没接线的类型标成 available 是这个端点最不能犯的错。
- `notAdjudicable` 点名剂量、概率与时间窗、个体化治疗决策、糖尿病域外、指南原文之外的共识。
- `corpus` 同时给「收录了多少份指南」和「多少份真的拿得出逐字出处」——
  当前 32 份收录、只有 6 份贡献了那 31 条出处。**别拿收录份数当覆盖面。**

---

## 12.7 `POST /adjudicate/citations` — 裁决引用是不是逐字成立

**不需要患者、不碰 PostgreSQL、不跑规则链，完全确定性。** 只拿调用方声称的
`quote` / `sha256` 去比对 `urn:dmo:seed` 里那 31 条已被 `verify_passages.py`
逐字回原文校验过的 `SourcePassage`。

```bash
curl -X POST localhost:8100/adjudicate/citations \
     -H 'Content-Type: application/json' \
     -d '{"citations":[
           {"quote":"6.5% or above",
            "sha256":"96495c7d996a92b5bee7132029744f08e5154be98dd1be7e177399320d7d1447"},
           {"quote":"6.5 percent or higher",
            "sha256":"96495c7d996a92b5bee7132029744f08e5154be98dd1be7e177399320d7d1447"},
           {"quote":"根据指南，通常认为血糖偏高即可诊断糖尿病"}],
          "assertedBy":"external-llm/some-model"}'
```

五个判定值：

| verdict | 含义 |
|---|---|
| `verbatim` | 引文逐字命中，哈希相符 —— 唯一一个「引用成立」 |
| `hash-only` | **哈希是真的，引文被改写过**。上面第二条就是：`6.5% or above` 被转述成 `6.5 percent or higher` |
| `quote-only` | 引文对、哈希不对。哈希若指向另一条真出处，返回体会点名是哪一条 |
| `not-verbatim` | 与某条出处存在包含关系（截取或加话），哈希未命中 |
| `fabricated` | 引文与哈希都无对应 |

### `hash-only` 是这个端点存在的理由

引用真实存在、但在转述中被悄悄改了措辞 —— **纯字符串比对抓不到**（引文和库里任何一条都不相同），
**纯哈希比对也抓不到**（哈希确实存在）。必须两条线一起看才会暴露。这是 LLM 最典型的错法。

### 四条硬性口径

1. **永远不返回布尔。** 没有 `reasonable` / `valid` / `passed` 这类字段 ——
   返回「已通过本体校验」等于给外部系统发一枚它承担不起的印章。
2. **不做模糊匹配。** 没有编辑距离、没有 embedding。相似度 0.87 判成「引用成立」，
   等于用一个数字把伪造洗白。包含关系是纯机械可判定的，所以留着。
3. **`fabricated` 不是道德判断。** 含义严格是「本库 31 条里没有逐字对应」——
   也可能引自本仓库未收录的资料，返回体里会把这句话说清楚。
4. **`assertedBy` 只记账，绝不参与判定。** 谁说的不影响对不对。

### `verbatim` ≠ 用对了地方

它只说明「与本库某条出处逐字一致」。**引文用对了地方没有，是另一个问题** ——
交给 [§12.8 `/adjudicate/claim`](#128-post-adjudicateclaim--裁决一条已经给出的结论)
的 `misattributed`：引文逐字属实、但不在支撑那条结论的出处里。

---

## 12.8 `POST /adjudicate/claim` — 裁决一条已经给出的结论

把外部（另一个模型、另一套系统、一份报告）给出的结论，和本体自己推出来的那条并排比对。

```bash
curl -X POST localhost:8100/adjudicate/claim \
     -H 'Content-Type: application/json' \
     -d '{"patientId":"P90002",
          "claim":{"type":"Diagnosis",
                   "value":{"kind":"Diabetes","verificationStatus":"Confirmed"}},
          "assertedBy":"external-llm/some-model"}'
```

返回 `verdict: "contradicted"`，`comparison.conflicts` 指出
`verificationStatus: Confirmed → 系统 Provisional`，`missingEvidence` 说清差什么：

> 另一采样日的复测 —— 所用诊断切点 `confirmationRequired=true`，
> 单次落在区间内 ≠ 确诊（`30-diagnosis-from-assessment.rq`）。

**这是整套 API 最有说服力的一次比对。** A1C 落在糖尿病区间，纯 LLM 会说「是糖尿病」，
字符串匹配也会说「是糖尿病」；本体说的是「Provisional，还差一次复测」。

### 四个判定值

| verdict | 含义 |
|---|---|
| `supported` | 本体按同一套规则推出了同一条结论 |
| `contradicted` | 语义键上冲突 |
| `unsupported` | 既拿不出支撑也拿不出反驳 —— **证据不足与「判定为错」是两回事** |
| `not-adjudicable` | 这类断言本体压根不管。**这是常见返回值，不是异常** |

### 五个 claim 类型

`Assessment`（诊断切点）、`TargetAttainment`（管理目标）、`Diagnosis`、`RiskTier`、
`MedicationSafety`。

⚠️ **诊断切点与管理目标必须分开裁决。** 两类结论都是 `dmo:Assessment`，都进同一个模板，
**只有 `ruleId` 能区分**（`LAB-THRESHOLD-MATCH` / `TARGET-ATTAINMENT`）。实测 P90003
同时有 `High`（管理目标）与 `DiabetesRange`（诊断切点）两条结论 —— 不按 `ruleId` 收敛，
一条「conclusion=High」的断言判出来的对错是随机的。这正是
[`21-target-attainment.rq`](../ontology/rules/21-target-attainment.rq) 开头那段警告的 API 层对应物。

### `misattributed` —— 引对了话，用错了地方

传 `citations` 时会额外做一层核查：引文逐字属实、但**不在支撑这条结论的出处里**，
标 `misattributed`。拿 FPG 的切点原文（`126 mg/dL or above`）去支撑一条 A1C 结论就会命中。
纯字符串比对抓不到（引文是真的），纯哈希比对也抓不到（哈希是真的）——
要靠 `thresholdCitesPassage` 的边反查它到底支撑了什么。

### `adjudicationHash`

`sha256(claim ‖ patientId ‖ graphVersion ‖ rulesFingerprint)`。同一条断言、同一版知识层与
规则集，跑一百次同哈希。**`assertedBy` 与 `citations` 不进哈希** —— 谁说的、引了什么，
都不改变本体自己推出来的那条结论。

### 只接受结构化断言

不接受自然语言。接受了就要先用模型解析，确定性当场丢光 —— 那正是 `simulate` 的
`derivationHash` 花力气守住的东西。

---

## 12.9 图探索原语 —— 给智能体的「下一跳」

`templates.py` 拒绝让 LLM 自由写 SPARQL 的理由（**静默少返**）到今天仍然成立。
所以这一族的做法不是给它一门查询语言，而是：**agent 自己决定下一跳查什么，
GRAPH 子句由服务端拼。**

```bash
curl 'http://localhost:8100/graph/concepts?q=糖化血红蛋白'   # 表面形式 → 准确 IRI
curl 'http://localhost:8100/graph/node?iri=…'                 # 邻接摘要
curl 'http://localhost:8100/graph/neighbors?iri=…&predicate=…'
curl 'http://localhost:8100/graph/taxonomy?iri=…&direction=up'
curl 'http://localhost:8100/graph/path?from=…&to=…&maxHops=3'
curl 'http://localhost:8100/graph/schema?section=bridge'
```

### `/graph/path`：不放任意长度属性路径出去

`?a (<>|!<>)* ?b` 在十万三元组上没有封顶，一条查询能把库拖垮，**而且写错了不报错、
只是跑很久然后超时** —— 又一种静默失败。所以路径由服务端做双向受控 BFS，
跳数与每跳前沿都封顶。

遍历刻意跳过 `rdf:type` 与 `owl:sameAs`：任意两个节点都是 `owl:Thing`，
经它们「连通」的全是伪相关。实测一条检验结果到指南原文是三跳：

```
dmo:measuredByTest → LabTest-A1C
dmo:hasThreshold   → threshold/A1C-DIABETES
dmo:thresholdCitesPassage → sourcePassage/A1C-DIABETES-Q
```

### `/graph/schema`：桥接表由 AST 抽出来

`rdf/emit.py` 是 SQL 列名 ↔ RDF 谓词的唯一权威对照，但它以命令式代码存在。
`section=bridge` 返回的 39 对对照是**静态解析那份源码**得到的 —— 不可能与实际发射逻辑分叉
（新造一个常量则要靠「改了 emit 记得改常量」的自觉）。

同时给出值变换：`core_patient.sex` 的 `M`/`F` 在 RDF 侧已经是 `Male`/`Female`，
**按 `M` 查一条不返**。

### `/graph/concepts`：并集才是重点

本体的 `rdfs:label` / `skos:altLabel` **∪** 三张人工映射表里的上游中文名。
纯 SPARQL 版本查不到「糖化血红蛋白」—— 那个字符串只存在于 `map_lab_term.src_name`。

返回体的 `usable` 字段说明这个映射到底参不参与判定：A1C 在本体里有概念、有三条阈值，
但上游全库一条数值都没有，`verify_status=no-source-data` ⟹ `usable: false`。
**查得到 ≠ 判得了。**

### `/graph/node`：哪些类型是推理机推的

`assertedIn` 拿不到图名的类型，就是 owl2-rl 物化出来的。一条 `RiskFactorHit` 上会看到：

```jsonc
{"short":"dmo:RiskFactorHit","assertedIn":["urn:dmo:inferred"],"inferredOnly":false}
{"short":"dmo:RiskRule",     "assertedIn":[],                  "inferredOnly":true}
```

后者是 prp-dom 顺着 `dmo:triggerBasis` 的 domain 反推的。**别拿 `?x a <类>` 当
「声明了这个类」用。**

### 三件服务端替调用方兜住的事

1. **反例夹具**：`urn:dmo:data` 里 6 个合成患者是故意造错的，IRI 长得跟真患者一样。
   `/graph/node` 与 `/graph/provenance` 直接**拒绝并说明**，不悄悄过滤 ——
   悄悄过滤和静默少返是一回事。`/graph/neighbors` 过滤时会在 `fixtureFiltered` 里明说。
2. **空节点**：owl 限制类的 skolem ID 每次装载都变，一律滤掉。
3. **自反 `owl:sameAs`**：物化噪声，留着白占一个 nextHop。

---

## 12.10 `GET /graph/rules` — 规则内省

回答「判定是按什么判的、哪些规则根本判不了、哪些命中了也不计分」。
`/patients/{pid}/assessment` 回答的是判成什么，这里回答的是凭什么这么判。

```bash
curl 'http://localhost:8100/graph/rules?kind=risk&countsInTier=false'
curl 'http://localhost:8100/graph/rules/A1C-DIABETES-NONPREG'
```

### ⚠️ `?r a dmo:RiskRule` 会多查出六倍

```
?r a dmo:RiskRule                  → 73 条
?r a dmo:RiskRule ; dmo:riskRuleId → 12 条   ← 真正被规则链消费的
```

`dmo:triggerBasis` 的 `rdfs:domain` 是 `dmo:RiskRule`，而 `50-risk-factor-hit.rq` 产出的
每条 `RiskFactorHit` 都带 `triggerBasis`。OWL-RL 的 **prp-dom** 顺着 domain 反推，
把**每个患者命中记录**都判成一条风险规则。查询不报错、不告警，只是数字大了六倍。

本端点一律以**声明标记**（`riskRuleId` / `thresholdId` / `targetId`）为准，不看 `rdf:type`，
并把落差报进 `counts.risk.classAssertions` 与 `inferenceArtifacts`。

### 三个必须读懂的数字

```jsonc
"risk": { "declared": 12, "executable": 12, "countsInTier": 10,
          "classAssertions": 73, "inferenceArtifacts": 61 }
```

- `declared → countsInTier` 的差额：拿不出逐字出处的规则，产出 `RiskFactorHit` 但**不计入 tier**
  （`51-risk-stratification.rq` 信号 5）。当前是 `ICD-HYPERTENSION` 与 `ICD-DYSLIPIDEMIA`。
- `classAssertions → declared` 的差额：上面那个 prp-dom 反推的产物，不是规则。

### 管理目标的出处核不了

`kind=target` 的 10 条原文存在 `rdfs:comment` 里，**不是 `SourcePassage`、没有 `contentHash`**，
`/adjudicate/citations` 核不了它们。返回体的 `citationCaveat` 字段会自己说出来。

---

## 12.11 `GET /graph/provenance` — 反向溯源

「推理」与「可核查」在这里合流：

```
Diagnosis(Provisional)
  ← supportsDiagnosis ── Assessment(conclusion=…)
      ← appliesThreshold ── DiagnosticThreshold(confirmationRequired=true)
          ← thresholdCitesPassage ── SourcePassage(quote 逐字, sha256)
      ← basedOnLabResult ── LabResult(value/unit)
          ← sqlRow ── core_lab_result(source_table, source_pk)
```

### `brokenLinks` 与 `chain` 同等重要

只报走通的环节，等于在暗示「这条结论有出处」。实测三类断链：

- 禁忌的 `rationale` 是抽取产物的裸字符串，**不是带 `contentHash` 的 SourcePassage**，
  `/adjudicate/citations` 核不了；
- 上游直接断言的诊断（`factOrigin=ehr-legacy`）没有 Assessment 支撑，不是本系统推出来的；
- 无 `riskRuleCitesPassage` 的风险规则产出 Hit 但不计入 tier。

### ⚠️ SQL 的 `*_id` 列存业务号，不是 IRI

图里节点是 `.../diagnosis/EHR-DX-P00002-C00002-D901`（`|` 换成了 `-`，否则 IRI 不合法），
而 `core_diagnosis.diagnosis_id` 存的是原始的 `EHR-DX-P00002|C00002|D901`。
拿 IRI 直接查 SQL 永远查不到，而且**查不到不报错** —— 回查那一环静默消失，
返回体看着仍然完整。本端点先用图里的 `dmo:*Id` 字面量翻成业务号再回查。

---

## 12.12 `POST /graph/sparql` — 自由 SPARQL 逃生口

⚠️ **这是第 13 个工具，不是第 1 个。** 上面那族能答的别自己拼图模式 —— 它们的 GRAPH 子句
由服务端拼，永远不会踩下面这两脚。

### 六条静态检查

| 规则 | 检测 | 处置 |
|---|---|---|
| **A 患者图守卫** | 每个 `GRAPH ?var` 是否被 `STRSTARTS(STR(?var),"urn:dmo:patient:")` 约束 | **拒**，理由里直接给出该补的那一句 |
| **B 知识侧禁具名图** | `GRAPH <urn:dmo:seed｜tbox｜sources｜inferred｜extract:*>` | **拒** —— 会静默少返 |
| **C 反例夹具** | 出现 `urn:dmo:data` | **拒** |
| **D 写操作** | 非 SELECT/ASK/CONSTRUCT/DESCRIBE，或含 INSERT/DELETE/DROP/… | **拒** |
| **E 行数上限** | 无 `LIMIT` → 追加 200；超过 200 → 改写为 200 | 记进 `rewrites`，**不算失败** |
| **F 全库扫描** | 触及患者图但没有 `VALUES` / 具体患者 IRI 收敛 | 警告，不拒 |

拒绝理由是**写给模型看的**：它会作为 observation 回去自我修正，写 "rule A violation"
等于浪费一轮。

### 零结果探针

返回 0 行时不把空集直接回去，而是自动降级探一次：

> 返回 0 行，**但该患者图里有 10 条三元组**。0 行大概率是图模式写错了 ——
> 最常见的是把知识侧三元组也包进了 `GRAPH ?pg`。

**空集与「有但判不了」是两回事** —— `/terms/explain` 早就在做这件事，这里只是把同一条
诚实标准套到自由查询上。

### ⚠️ 剥注释不能用正则

本体的词汇命名空间就是 `https://example.org/dmo#`。`re.sub(r"#[^\n]*", "", q)` 会把
`<https://example.org/dmo#>` 的 `#>` 一起吃掉 —— 连闭合的 `>` 都没了，整条查询被粘成
一个巨大的「IRI」，**guard 照常给判定，只是判在错的输入上**。所以是逐字符扫，
`#` 只有在 `<…>` 与字面量之外才算注释。

---

## 12.13 `GET /agent/manifest` — 给智能体的能力清单

「辅助智能体自主规划」的正解是**让能力可发现**，不是让语言更自由。

- `endpoints` 从 `app.routes` 现场生成，附带每个端点的参数名 —— 新增端点自动出现，
  不可能与实际服务分叉；
- `callOrder` 七步调用顺序（先查概念拿准确 IRI → SQL 收敛患者 → 图上逐跳 → 溯源 → 裁决）；
- `graphRules` 三条图层铁律；
- `prohibitions` 七条硬禁令（不剂量、不概率、不猜术语、不编出处、不把 Provisional 当确诊…）；
- `determinism` 说明哪些端点确定、哪些不确定（当前**没有**任何由模型规划路径的端点）；
- `coverage` **能力与边界一起给** —— 只给能力不给边界，等于鼓励越界使用。

---

## 13. 对应的 CLI

核心端点有等价的命令行入口，走**同一条代码路径**（薄 HTTP 门面，逻辑全在 `query/hybrid.py`
与 `graph/` 下面）。图探索族目前只有 `dmo rules` 一个入口，其余走 HTTP —— 它们本来就是
给程序调的，不是给人在终端里读的：

```bash
uv run dmo show P90002              # ≈ GET /patients/P90002
uv run dmo explain 糖化血红蛋白       # ≈ GET /terms/explain
uv run dmo demo compare --term 尿蛋白 # ≈ GET /demo/compare
uv run dmo query care_chain --patient P90002   # ≈ POST /query/care_chain
uv run dmo query                    # 列模板

# 确定性病程推演 ≈ POST /patients/P90002/simulate
uv run dmo simulate P90002 --assume A1C 7.9 percent 2026-02-20

# 裁决引用 ≈ POST /adjudicate/citations（退出码：全部 verbatim 才是 0）
uv run dmo adjudicate --cite "6.5% or above" \
                      --cite "6.5 percent or higher" 96495c7d996a92b5…

# 规则内省 ≈ GET /graph/rules
uv run dmo rules --kind risk
uv run dmo rules A1C-DIABETES-NONPREG      # ≈ GET /graph/rules/{id}
```

CLI 与 API 必须走同一条路径，否则两边的答案会慢慢分叉，而演示时用的是哪一条谁也说不清。

---

> ⚠️ 技术验证用途，不是医疗器械，不构成任何医疗建议。
> 所有输出均不包含具体用药剂量；风险分层为规则式定性分层，非概率预测。
