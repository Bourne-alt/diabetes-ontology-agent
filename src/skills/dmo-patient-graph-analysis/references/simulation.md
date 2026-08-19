# 确定性病程推演（`POST /patients/{pid}/simulate`）

回答「**若**补一条检验，结论**则**变成什么」，并把每一步依据摊开。

本文只讲推演。常规查询看 [endpoints.md](endpoints.md)，措辞看 [report-contract.md](report-contract.md)。

---

## 一条分界线：推演不是预测

| ✅ 推演（做） | ❌ 预测（不做） |
|---|---|
| 「**若** A1C = 7.9%，**则** 触发 R30，结论 Confirmed」 | 「该患者 A1C 可能升到 7.9%」 |
| 条件蕴含，逻辑 | 状态外推，猜测 |

**假设值只能由用户显式给出。** 用户说"如果他血糖再高一点会怎样"而没给数字，
**问他要数字**，不要自己填一个"典型值"——填了就从推演退化成预测，
而预测正是本仓库明确不做的事（README「明确不做的事」第一条）。

唯一的例外是**区间**：回答"要达到 Confirmed 需要什么"时，可以说
"需要一条落在 `[6.5, +∞) percent` 的 A1C"——那是规则前件的直接读出，不是编的数值。
但**不能**说"需要一条 7.0% 的 A1C"，那个 7.0 是你编的。

---

## 什么时候用

| 用户这么问 | 用推演 |
|---|---|
| "如果他补一次 A1C 7.9 会怎样" | ✅ 直接推 |
| "差什么才能从 Provisional 变 Confirmed" | ✅ 推一条不同日期的同项检验，用结果回答 |
| "这个 6.4 要是 6.5 呢" | ✅ 边界跳变，最能说明问题的一类 |
| "他会不会发展成糖尿病" | ❌ 这是预测。说明不做，然后改问"您想假设哪个数值？" |
| "他现在什么情况" | ❌ 走 `GET /patients/{pid}`，不要为了用推演而推演 |

---

## 调用

```bash
curl -sS -X POST http://124.223.18.44:8100/patients/P90002/simulate \
  -H 'Content-Type: application/json' \
  '{"assume":[{"term":"A1C","value":7.9,"unit":"percent","date":"2026-02-20"}]}'
```

CLI 等价（服务没起时）：

```bash
uv run dmo simulate P90002 --assume A1C 7.9 percent 2026-02-20
```

### 只能推这 7 项

`A1C` `FPG` `GCT1H` `GLU` `OGTT2H` `RPG` `UACR` —— 只有它们挂了诊断阈值。

库里另有上百个从指南 PDF 抽出来的同名检验项（`labTest/hba1c`、
`labTest/fasting-plasma-glucose`…），**它们没有阈值**，推了只会得到空集，
而空集看起来和"结论没变"一模一样。API 会 400 拒绝并列出可用项——
**照抄那句拒绝理由给用户，不要改用别的名字重试**。

### 单位必须是规范单位

| 检验项 | 规范单位 |
|---|---|
| A1C | `percent` |
| FPG / GCT1H / GLU / OGTT2H / RPG | `mg-per-dL` |
| UACR | `mg-per-g` |

`mmol-per-L → mg-per-dL` 有已核实系数（葡萄糖 ×18.0182），会自动换算并在
`hypotheticalFacts[].sourceValue` / `sourceUnit` 里保留原值——**回答时两个都要给出**，
因为"7.8 mmol/L 不换算会落进 `FPG-NORMAL`，结论完全相反"正是这里最值得讲的一句。

A1C 的 `mmol-per-mol` **没有**已核实系数，会被拒。别自己算，
换算系数是 analyte-specific 的，猜一个等于制造错误。

---

## 返回体怎么读

按这个顺序，顺序本身是防错设计：

| # | 字段 | 先读它的理由 |
|---|---|---|
| 1 | `hypotheticalFacts[]` | 这次假设了什么。**任何结论转述前必须先交代它** |
| 2 | `unchanged` | 为 `true` 说明假设没改变任何结论——**这是结论不是故障** |
| 3 | `delta[]` | 结论级变化。`changed` / `added` / `removed` |
| 4 | `derivationTree` | 推导树，每个 `LabResult` 节点标 `measured` 或 `hypothetical` |
| 5 | `derivationHash` | 确定性凭证。同输入必同哈希 |
| 6 | `before` / `after` | 两轮规则跑完的结论快照，用于交叉核对 |

### `delta[].change` 三种取值

- `changed` —— 同一条结论的字段变了。**最重要的一类**，
  `fields.verificationStatus` 的 `Provisional → Confirmed` 就在这里。
- `added` —— 新增结论（假设检验产生了新的 Assessment）。
- `removed` —— 结论消失。少见，出现时要特别说明。

### `derivationTree` 节点

```
◆ Diagnosis   diagnosisKind / verificationStatus / caveat / gapToConfirmed
  ▸ Assessment  conclusion / rule / applicableContext
    · DiagnosticThreshold  thresholdId / interval / confirmationRequired / sources[]
    · LabResult   value / unit / collectedDate / provenance
```

`provenance` 只有两个值：`measured`（实测）与 `hypothetical`（假设）。
**在回答里必须逐条标出来**——把假设的那条混在实测里陈述，
等于拿假设冒充事实，是本 skill 最严重的一类错误。

`Provisional` 的诊断节点带 `gapToConfirmed`，直接回答"还差什么"。

---

## derivationHash 怎么用

它 = f(pid, graphVersion, 知识层快照, 规则集哈希, 假设集)。

**用户质疑"你这结论稳不稳"时，当场跑 5 遍给他看哈希一样。**
这是本体相对 LLM 最硬的一条差异：同一个问题问 LLM 五遍，答案会飘。

注入顺序不影响哈希（先 A1C 后 FPG 与先 FPG 后 A1C 同哈希）——
因为顺序不影响结论，也就不该影响哈希。

哈希变了只有三种可能：假设变了、本体改了、规则改了。
**同一轮对话里哈希无故变化，说明本体被人改过，此前所有推演结论都要重跑。**

---

## 不写 GraphDB 一个字节

推演全程在内存 rdflib Dataset 里跑，对 GraphDB 只发 `CONSTRUCT`。
推多少次，库里三元组数一条都不变（`tests/test_simulate.py::test_simulation_never_writes_to_graphdb`
用前后 `size()` 相等盯着）。

所以：**推演可以放心多跑**，不需要担心污染，也不需要"清理"。
用户问"这会不会改到真实数据"时，答案是"结构上不可能，沙箱没有写路径"。

---

## 三条推演专属禁令

1. **不脱离「若…则…」转述结论。**
   ❌「该患者已确诊糖尿病」
   ✅「**若**补一条 2026-02-20 的 A1C 7.9%，诊断**则**从 `Provisional` 转 `Confirmed`」

2. **不自己发明假设值。** 用户没给数字就问他要。区间可以从规则前件读出，具体数值不行。

3. **不拿推演结论去更新对患者现状的判断。** 推完之后，该患者的实际状态
   仍然是推演前的那个。下一轮回答"他现在什么情况"时，用 `GET /patients/{pid}`，
   不要引用上一轮推演的 `after`。

---

## 自测用例

```bash
# 黄金用例：差别只有"测了几天"
uv run dmo simulate P90002 --assume A1C 7.9 percent 2026-02-20
#   ⟹ Diagnosis.verificationStatus: Provisional → Confirmed

# 边界四段跳（S16 三个切点）
uv run dmo simulate P90002 --assume A1C 5.6 percent 2026-02-20   # ⟹ Normal
uv run dmo simulate P90002 --assume A1C 5.7 percent 2026-02-20   # ⟹ Prediabetes
uv run dmo simulate P90002 --assume A1C 6.4 percent 2026-02-20   # ⟹ Prediabetes
uv run dmo simulate P90002 --assume A1C 6.5 percent 2026-02-20   # ⟹ DiabetesRange

# 同日重测不算复测（30 号规则数的是 distinct 日期）
uv run dmo simulate P90002 --assume A1C 7.9 percent 2026-01-15   # ⟹ 无变化

# 单位换算（S11）：原值原单位必须一并转述
uv run dmo simulate P90002 --assume FPG 7.8 mmol-per-L 2026-03-01
#   ⟹ 换算 140.54 mg-per-dL，不换算会落进 FPG-NORMAL

# 拒绝路径：照抄拒绝理由，不要改名重试
uv run dmo simulate P90002 --assume hba1c 7.9 percent 2026-02-20  # ⟹ 400 不猜术语
```
