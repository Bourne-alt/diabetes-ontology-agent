---
name: dmo-course-simulation
description: 由患者数据主导、在糖尿病本体语义层上做多步确定性病程推演。当用户问"差什么才能确诊""从 Provisional 到 Confirmed 还缺哪一步""这个 6.4 要是过了切点会怎样""补几次检验才够""按这条线走结论会怎么变"，或需要围绕一个目标态自主设计探针、跑出可复现的结论轨迹时使用。本 skill 规定了远端 HTTP 接入自检、目标态归一化、探针合法数值的唯一两个来源（用户显式给出 / 本体阈值区间端点）、前缀累加轨迹的正确读法、探针预算与收敛判据，以及硬性禁令（不预测、不发明数值、不把轨迹叙述成病情演变、不把假设结论当患者现状）。Use when driving multi-step, goal-directed deterministic simulation of a diabetes patient's course over the ontology semantic layer from a remote agent platform.
license: 与本仓库同许可
compatibility: 需要 dmo 融合查询 API 可达，基址由环境变量 DMO_BASE 给出（服务默认只绑 127.0.0.1，远端使用须由部署方显式暴露）；服务端依赖 PostgreSQL 与 GraphDB
allowed-tools: Bash(scripts/dmo.sh:*) Bash(scripts/course.py:*) Bash(python3:*) Bash(curl:*) Read
metadata:
  repo: diabetes-ontology-agent
  version: "1.0"
  audience: 远端代码平台智能体
---

# 病程推演（语义层目标驱动探索）

## 这个 skill 在优化什么

**不是"多调几次 API"，是"在一个确定性引擎上做有目标、有预算、可复现的搜索"。**

引擎侧已经确定：同样的输入必然得到同样的 `derivationHash`。所以推演质量的全部变数在你这一侧——
你**选了哪些探针**、**凭什么选**、**什么时候停**、**怎么转述**。这四件事写错，
一个确定性系统会被你叙述成一个概率系统，那正是本仓库要反对的东西。

判不动的时候，把"推不动"和它的结构性原因说清楚，就是满分答案。

## 硬禁令（违反任一条即为错误输出，无例外）

1. **不预测。** 不输出概率、百分比、发生率、时间窗、进展速度。"多久会发展成""会不会恶化"一律拒绝，然后把问题转写成可推演的目标态（见阶段 C）。
2. **不发明数值。** 假设值的合法来源**只有两个**：① 用户显式给出；② 本体阈值区间的端点（原样取自返回体的 `interval`）。**取区间中点、±0.1 微调、"典型值"、"稍高一点"全部违禁**——那些数是你编的。
3. **边界值必须标注出身。** 用了 6.5 就要写"该值取自阈值 `A1C-DIABETES-NONPREG` 的区间下界 `[6.5, +∞) percent`，非预测、非用户给定"。不标注 = 拿本体的数冒充临床判断。
4. **不脱「若…则…」。** ❌"该患者已确诊" ✅"**若**补一条 X，结论**则**转 Confirmed"。
5. **不把轨迹叙述成病情演变。** 轨迹的每一步都是**从同一个真实基线**重跑的（见阶段 F 的 ⚠️），第 k 步不是第 k−1 步的后续状态。写成"病情逐步进展/恶化"是把平行假设伪装成时间演化。
6. **不把推演的 `after` 当患者现状。** 下一轮回答"他现在什么情况"要重新 `GET /patients/{pid}`。
7. **不猜术语。** 可推演的只有 7 项。400 拒绝里的理由**就是答案**，照抄给用户，**不许改个名字或换个单位重试**。
8. **不输出剂量。** schema 层没有剂量字段。
9. **`unchanged: true` 与 `Insufficient-Evidence` 是结论，不是故障，也不等于"风险低"。**
10. **每次输出必须带返回体里的 `hypotheticalNote` 与 `disclaimer` 原文。**
11. **`graphVersion` 在一轮对话里变了 ⟹ 本体被改过，此前所有轨迹作废，全部重跑。**

## 探索循环（A→H，跳步即失效）

### 阶段 A · 接入自检（不可跳过、不可降级）

```bash
export DMO_BASE=https://<你的部署地址>     # 未设置时脚本直接报错，不回落 localhost
scripts/dmo.sh /health
```

- `DMO_BASE` 没设 / 连不上 → **停下并如实报告"远端够不着这套服务"**。不要改用猜测回答，不要"先按一般情况分析"。
- `ok: false` → 报告是 `postgres` 还是 `graphdb` 断了，停。
- 记下 `graphVersion`（前 16 位）。它是禁令 11 的比对基准。

> 服务默认只绑 127.0.0.1、无鉴权无限流。远端能访问说明部署方做了暴露；
> 那不是你的授权范围，**不要尝试写入类操作**——本 API 也没有写端点。

### 阶段 B · 锚定基线（轨迹的第 0 步）

```bash
scripts/dmo.sh /patients/P90002
```

按序读，顺序本身是防错设计：`dataQualityNotice` → `assertedFacts[].trust` →
`inferredFacts` → `sources` → `unmapped` → `riskStratification` → `careChain`。

落三件事，缺一件就不要往下走：

| 必记 | 为什么 |
|---|---|
| `fact_origin` | `ehr-legacy` 真实上游 / `derived` 投影 / `demo-cohort` 演示队列。**ID 前缀不能用来区分真假**，只看这个字段。拿演示队列的漂亮轨迹去代表真实数据能力，是本仓库最忌讳的误导 |
| `dataQualityNotice` / `trust` | 非 null 或出现 `Unverified` ⟹ 该值不参与判定、不在回答里当数值引用（上游那批是随机数）。此时只报管线事实 |
| 现状快照 | `Diagnosis.verificationStatus`、各 `Assessment.conclusion`、`riskTier`、`unmapped`、`monitoringGaps` |

**基线只能来自这个端点**，不能用 simulate 返回体里的 `before` 代替对外陈述现状——
`before` 是沙箱重跑的结果，用途是交叉核对，不是患者档案。

### 阶段 C · 目标态归一化

把用户的话翻成一个**可判定的目标**。只有三类可推：

| 类型 | 目标态 | 可推性 |
|---|---|---|
| T1 | `Diagnosis.verificationStatus`：`Provisional → Confirmed` | ✅ 最典型，差别常常只是"测了几天" |
| T2 | `Assessment.conclusion` 跨切点：`NormalRange → PrediabetesRange → DiabetesRange` | ✅ 边界跳变，最能说明确定性 |
| T3 | `riskTier` 跃迁（如 `Insufficient-Evidence → Moderate`） | ⚠️ **多半推不动**：tier 由禁忌命中、已确诊并发症、风险因子数、监测缺口共同决定，补一条检验通常改不了它。**先说明这一点，再降级成"哪些缺口在挡路"**（读 `insufficientReason` + `monitoringGaps` 原文） |

翻不成上面任一条的（"会不会得""多久""概率多大""要不要吃药"）→ **拒绝**，说明本系统做条件推演不做预测，
然后主动给出可推的形式："您是想问'补一条落在 `[6.5,+∞) percent` 的 A1C 之后结论会怎样'吗？"

### 阶段 D · 从返回体读差距（读出来的，不是想出来的）

| 差距来源 | 字段 | 回答什么 |
|---|---|---|
| 诊断节点 | `gapToConfirmed` | "还差什么"——**直接就是答案，优先引用它** |
| 评估节点 | `interval`（如 `[6.5, +∞) percent`）、`confirmationRequired` | 目标区间在哪、单次够不够 |
| 分层节点 | `insufficientReason`、`monitoringGaps` | T3 推不动时的真实原因 |
| 缺口清单 | `unmapped` | "有数据但结构上判不了"与"上游无数据"是两回事 |

`interval` 必须**逐字复述开闭区间**，不许用 `>=` 近似：三个切点是 `(-∞,5.7)` / `[5.7,6.4]` / `[6.5,+∞)`，
把开区间说成闭区间会把 5.7 从 Prediabetes 错判成 Normal。

### 阶段 E · 设计探针（自主度合同就在这一段）

**你可以自主决定：探哪一项、探哪个切点、探几步、按什么顺序。**
**你不可以自主决定：具体数值是多少。** 数值只有两个合法出身，见禁令 2/3。

| 探针要素 | 规则 |
|---|---|
| 检验项 | 只有 `A1C FPG GCT1H GLU OGTT2H RPG UACR` 挂了阈值。库里另有上百个同名抽取项**没有阈值**，推了得空集，而空集和"结论没变"长得一模一样 |
| 单位 | A1C=`percent`；FPG/GCT1H/GLU/OGTT2H/RPG=`mg-per-dL`；UACR=`mg-per-g`。`mmol-per-L→mg-per-dL` 服务端有已核实系数会自动换算并保留原值；**A1C 的 `mmol-per-mol` 没有系数，会被拒——别自己算** |
| 数值 | 用户给的原样用；否则取 `interval` 端点原样用并标注出身。**中点、微调、典型值一律违禁** |
| 日期 | 仅 T1 允许你自主铺**第二个日历日**（同一项、同一值），且必须声明"该日期只是一个不同于已有采样日的占位符，不承载临床含义"。同日重测不算——30 号规则数的是 distinct 日期。其他场景日期须来自用户 |
| 规模 | 一次 `assume` ≤ 10 条（API 上限）；同一 (项,值,日期) 重复会被当场拒绝 |

**探针预算：单个目标 ≤ 4 次 simulate，整轮对话 ≤ 12 次。** 用尽即停并报告"未收敛"，
不许继续加码试探——无预算的搜索会滑成"调到出现想要的结论为止"，那是结果导向的编造。

### 阶段 F · 跑轨迹（前缀累加）

单点 what-if：

```bash
scripts/dmo.sh -X POST /patients/P90002/simulate \
  '{"assume":[{"term":"A1C","value":7.9,"unit":"percent","date":"2026-02-20"}]}'
```

多步轨迹（第 k 步注入前 k 条假设，自动逐步 diff）：

```bash
scripts/course.py P90002 A1C:6.5:percent:2026-02-20 A1C:6.5:percent:2026-03-05
```

> ⚠️ **轨迹不是链式演化。** 每次调用都从**同一个真实基线**重新跑两遍规则链
> （`runner.py` 每次新建 Dataset），所以每一步的 `before` 恒等于基线。
> 第 k 步的含义是"基线 + 前 k 条假设"，**不是**"第 k−1 步之后又发生了什么"。
> 叙述成"病情一步步进展"就是禁令 5。

返回体读序：`hypotheticalFacts` → `unchanged` → `delta` → `derivationTree` → `derivationHash`。
`derivationTree` 里每个 `LabResult` 带 `provenance: measured | hypothetical`，**回答时必须逐条标出来**。

推演全程在内存 rdflib Dataset 里跑，对 GraphDB 只发 CONSTRUCT——**推多少次库里三元组一条不变**，
放心多跑，不需要清理。用户问"会不会改到真实数据"，答案是"结构上不可能，沙箱没有写路径"。

### 阶段 G · 收敛判据（命中任一条就停）

| 停 | 怎么报 |
|---|---|
| 命中目标态 | 给出命中的那一步、`delta` 里 `changed` 的字段前后对照、该步 `derivationHash` |
| 连续两步 `unchanged: true` | 报"该方向推不动"，并从 `insufficientReason`/`interval` 说明结构性原因 |
| 400 拒绝 | **照抄 detail**，停。不换名、不换单位重试 |
| 预算用尽 | 报"未收敛"+ 已试探针清单，交回用户决定下一个假设 |

用户质疑"你这结论稳不稳"→ 同一请求连跑 5 次给哈希：

```bash
scripts/course.py P90002 A1C:7.9:percent:2026-02-20 --repeat 5
```

5 个哈希相同。这是本方案相对纯 LLM 最硬的一条差异。哈希变了只有三种可能：假设变了、本体改了、规则改了。

### 阶段 H · 输出

结构固定，缺段即不合格。措辞与反例见 [references/report-contract.md](references/report-contract.md)。

```
【目标】T1 · P90002 的 Diabetes 诊断 Provisional → Confirmed
【基线】fact_origin=demo-cohort（演示队列，非真实上游）；数据质量：<原文或"均为 Curated">；
        现状：<verificationStatus / conclusion / tier 原样>
【差距】<gapToConfirmed 或 interval / insufficientReason 原文>
【探针】第1步 A1C 6.5 percent @2026-02-20
        └ 数值取自阈值 A1C-DIABETES-NONPREG 的区间下界 [6.5, +∞) percent，非预测、非用户给定
        └ 日期为占位符：仅表示"不同于 2026-01-15 的另一个日历日"，不承载临床含义
【轨迹】步 | 假设集 | unchanged | delta（changed 字段前后） | derivationHash 前16位
【推导树】<逐层展开，每条 LabResult 标 [实测] / [假设]>
【收敛】命中 / 未收敛（原因）
【仍判不了的】<unmapped + monitoringGaps 原样>
⚠️ <hypotheticalNote 原文>
⚠️ <disclaimer 原文>
```

## 交付前自检

任一条为"否"就不要发出：

- [ ] 每个假设数值都能指到"用户原话"或"某个阈值 ID 的区间端点"？没有一个是我调出来的？
- [ ] 边界值标了出身（阈值 ID + 区间原文）？
- [ ] 每句推演结论都带「若…则…」，没有一句脱掉条件句？
- [ ] 轨迹的措辞是"基线+前 k 条假设"，没有写成"病情逐步进展"？
- [ ] 推导树里 `[实测]` / `[假设]` 逐条标出来了？
- [ ] `fact_origin` 交代了？`unmapped` / `monitoringGaps` 露出来了，没被我"整理"掉？
- [ ] 没有出现剂量、概率、百分比、时间窗？
- [ ] `unchanged` / `Insufficient-Evidence` 有没有被我说成"故障"或"风险低"？
- [ ] `hypotheticalNote` 与 `disclaimer` 都带上了？
- [ ] 探针次数在预算内？超了有没有如实说"未收敛"？

## 什么时候**不要**用这个 skill

- 用户只问现状 / 诊断依据 / 用药安全 / 术语为什么查不到 → 走常规查询端点，不要为了用推演而推演。
- 用户要病程**预测**（会不会、多久、概率）→ 拒绝，转写成阶段 C 的目标态。
- 用户要真实临床建议 → 拒绝。这是技术验证服务，不是医疗器械。
- 用户要自由 SPARQL → 不提供，给最接近的模板（`/query/templates`）。
- 改本体 / 调规则 / 跑 ETL → 不在本 skill 范围，也不在远端权限范围。

## 深入

- 端点与字段语义（自足摘要）：[references/endpoints.md](references/endpoints.md)
- 探针策略手册与自测用例：[references/probing.md](references/probing.md)
- 输出措辞契约与逐条反例：[references/report-contract.md](references/report-contract.md)
