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
uv run dmo serve --port 8000

# python（已 pip/uv sync 安装 dmo 包时）
python -m dmo.cli serve --port 8000

# uvicorn（直接挂载 FastAPI app，便于热重载）
uvicorn dmo.api:app --host 127.0.0.1 --port 8000 --reload
```

前置：PG 可达、GraphDB 在 `localhost:7200`、数据管线已跑过一轮（见 [README](../README.md) 端到端复现）。

无鉴权、无限流，**仅绑定 `127.0.0.1`**。这是技术验证服务，不要暴露到公网。

交互式文档：`http://localhost:8000/docs`（FastAPI 自带 Swagger UI）。

---

## 2. 端点总览

| 方法 | 路径 | 走 SQL 还是 SPARQL | 用途 |
|---|---|---|---|
| GET | `/health` | 两者 | 连通性 + 数据量 + 本体版本 |
| GET | `/patients` | **SQL** | 检索与分页 |
| GET | `/patients/{pid}` | 两者 | 完整返回体（七段） |
| GET | `/patients/{pid}/care-chain` | SPARQL | 就诊→检验→诊断→用药全链 |
| GET | `/patients/{pid}/assessment` | SPARQL | 阈值判定 + 出处 |
| GET | `/patients/{pid}/risk` | SQL（读物化结果） | 风险分层 |
| GET | `/patients/{pid}/safety` | SPARQL | 用药安全信号 |
| POST | `/patients/{pid}/simulate` | **内存推演** | 确定性病程推演 + 推导树 |
| GET | `/query/templates` | — | 列出模板白名单 |
| POST | `/query/{template}` | SPARQL | 跑参数化模板 |
| GET | `/terms/unmapped` | SQL | 全部未命中/不可用术语 |
| GET | `/terms/explain` | SQL | **为什么查不到某个术语** |
| GET | `/demo/compare` | 两者 | 字符串匹配 vs 本体，并排对照 |

**职责边界是写死的**：有多少 / 哪些 / 分页 → SQL；为什么 / 凭什么 / 依据哪条指南 → SPARQL；
原始那一行长什么样 → SQL（`source_pk` 回查）。

---

## 3. `GET /health`

```bash
curl http://localhost:8000/health
```

```json
{
  "ok": true,
  "graphVersion": "1698163014811f2c",
  "patients": 430,
  "labResults": 1374,
  "stratified": 33,
  "graphdbTriples": 64768
}
```

`graphVersion` 是**知识层四个文件的内容哈希**（TBox / 公理 / 阈值 seed / 风险映射）。
它变了就说明本体改过，此前的术语映射和分层结论都该重新审视。

`ok: false` 时会多出 `postgres` 或 `graphdb` 字段说明是哪一侧断了。

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
curl 'http://localhost:8000/patients?icd10=E11&size=2'
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
curl http://localhost:8000/patients/P90002/assessment
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
curl http://localhost:8000/patients/P90020/risk
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
curl http://localhost:8000/patients/P00016/risk
```

15 个真实 E11 患者**全部**落在这一档，`insufficientReason` 说清三个原因：
检验值均为 `Unverified`、无任何可用风险侧事实、年龄推不出来。

这不是 bug。同一个库里前人的做法是给一个 confidence 0.9 的答案（见 `/demo/compare`）。

---

## 7. `GET /patients/{pid}/safety` — 用药安全

```bash
curl http://localhost:8000/patients/P90008/safety
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
curl http://localhost:8000/query/templates
curl -X POST http://localhost:8000/query/care_chain \
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
curl 'http://localhost:8000/terms/explain?term=糖化血红蛋白'
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
curl 'http://localhost:8000/demo/compare?term=尿蛋白'
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
| 400 | `POST /query/{template}` 给了空患者数组 |
| 404 | 患者不存在；模板名不在白名单 |
| 422 | 参数类型不合法（FastAPI 自动校验） |
| 500 | PG / GraphDB 断连。先查 `/health` |

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

---

## 12.5 `POST /patients/{pid}/simulate` — 确定性病程推演

回答「**若** 补一条检验，结论**则**变成什么」，并把每一步的依据摊开。

```bash
curl -X POST localhost:8000/patients/P90002/simulate \
  -H 'Content-Type: application/json' \
  -d '{"assume":[{"term":"A1C","value":7.9,"unit":"percent","date":"2026-02-20"}]}'
```

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
  curl -s -X POST localhost:8000/patients/P90002/simulate \
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

## 13. 对应的 CLI

每个端点都有等价的命令行入口，走**同一条代码路径**（薄 HTTP 门面，逻辑全在 `query/hybrid.py`）：

```bash
uv run dmo show P90002              # ≈ GET /patients/P90002
uv run dmo explain 糖化血红蛋白       # ≈ GET /terms/explain
uv run dmo demo compare --term 尿蛋白 # ≈ GET /demo/compare
uv run dmo query care_chain --patient P90002   # ≈ POST /query/care_chain
uv run dmo query                    # 列模板

# 确定性病程推演 ≈ POST /patients/P90002/simulate
uv run dmo simulate P90002 --assume A1C 7.9 percent 2026-02-20
```

CLI 与 API 必须走同一条路径，否则两边的答案会慢慢分叉，而演示时用的是哪一条谁也说不清。

---

> ⚠️ 技术验证用途，不是医疗器械，不构成任何医疗建议。
> 所有输出均不包含具体用药剂量；风险分层为规则式定性分层，非概率预测。
