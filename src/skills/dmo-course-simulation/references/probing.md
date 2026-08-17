# 探针策略手册

SKILL.md 阶段 E 的展开。核心只有一句：**你自主的是"探哪里"，不是"探多少"。**

---

## 一、合法数值的两个出身（没有第三个）

### 出身 ①：用户显式给出

原样用，原样引。用户说"7.9"，你注入 7.9，回答里写"由您给出的 7.9%"。

用户说"再高一点""如果控制得好一点""比现在高"——**这不是数值，是意向**。
两条出路，选一条，不要自己填：

- 从规则前件读出**区间**回答："要落进 DiabetesRange，需要一条落在 `[6.5, +∞) percent` 的 A1C。"
- 直接问："您想假设哪一个具体数值？"

### 出身 ②：本体阈值区间的端点

先拿到 `interval` 原文（`GET /patients/{pid}/assessment` 的 `inferredFacts[].interval`，
或某次 simulate 的 `derivationTree` 里 `DiagnosticThreshold.interval`），再取端点。

| 允许 | 不允许 | 为什么 |
|---|---|---|
| `[6.5, +∞)` → 探 `6.5` | 探 `7.0`（"稍微高一点"） | 6.5 是 `dmo:lowerBound` 的字面量；7.0 是你编的 |
| `[5.7, 6.4]` → 探 `5.7` 或 `6.4` | 探 `6.0`（"区间中点"） | 中点在本体里不存在，它是算出来的，不是读出来的 |
| 相邻区间各自的端点，用来演示切点跳变 | `6.4 + 0.1`、`6.5 - 0.01` 之类微调 | 微调是在**搜索一个想要的结论**，不是在读本体 |

**取了端点必须标注出身**，格式见 SKILL.md 阶段 H：

> 该值取自阈值 `A1C-DIABETES-NONPREG` 的区间下界 `[6.5, +∞) percent`，非预测、非用户给定。

> ⚠️ 开区间端点要小心：`(-∞, 5.7)` 的 5.7 **不在**该区间内，它属于下一段 `[5.7, 6.4]`。
> 想探"刚好不落进 Normal"就是探 5.7 本身；想探"落在 Normal 里"则该端点不可用，须问用户要值。

---

## 二、可推演的只有 7 项

`A1C` `FPG` `GCT1H` `GLU` `OGTT2H` `RPG` `UACR` —— 只有它们挂了 `dmo:hasThreshold`。

库里另有上百个从指南 PDF 抽出来的同名检验项（`labTest/hba1c`、
`labTest/fasting-plasma-glucose`…），**它们没有阈值**，推了只会得到空集，
而空集看起来和"结论没变"一模一样。所以服务端宁可当场 400 也不做模糊匹配、不算编辑距离。

| 检验项 | 规范单位 |
|---|---|
| A1C | `percent` |
| FPG / GCT1H / GLU / OGTT2H / RPG | `mg-per-dL` |
| UACR | `mg-per-g` |

`mmol-per-L → mg-per-dL` 有已核实系数（葡萄糖 ×18.0182），服务端自动换算并在
`hypotheticalFacts[].sourceValue` / `sourceUnit` 保留原值——**两个都要在回答里给出**。

A1C 的 `mmol-per-mol` **没有**已核实系数，会被拒。**别自己算**：
换算系数是 analyte-specific 的，猜一个等于制造错误。

---

## 三、三类目标的标准打法

### T1 · `Provisional → Confirmed`（最典型）

差别常常只是"测了几天"。30 号规则数的是 `SUBSTR(collectedAt,1,10)` 的 **distinct 日期数**。

打法：先读诊断节点的 `gapToConfirmed`（它本身就是答案），再设计一步探针——
同一项、同一个落在诊断区间内的值、**一个不同的日历日**。

日期是本 skill 唯一允许你自主填的字段，且带三个约束：

1. 必须不同于已有采样日（同日重测不算复测）；
2. 不早于已有最新采样日（"补一次过去的检验"在语义上是另一回事，须用户明确）；
3. **必须声明它是占位符**：「该日期仅表示"不同于 2026-01-15 的另一个日历日"，不承载临床含义」。

```bash
scripts/course.py P90002 A1C:7.9:percent:2026-02-20
#   ⟹ Diagnosis.verificationStatus: Provisional → Confirmed

scripts/course.py P90002 A1C:7.9:percent:2026-01-15
#   ⟹ 无变化（与已有采样同日，distinct 日期没增加）
```

### T2 · 跨切点（最能说明确定性）

用相邻区间的端点排成一条轨迹，让切点跳变自己说话：

```bash
scripts/course.py P90002 A1C:5.6:percent:2026-02-20   # ⟹ NormalRange
scripts/course.py P90002 A1C:5.7:percent:2026-02-20   # ⟹ PrediabetesRange
scripts/course.py P90002 A1C:6.4:percent:2026-02-20   # ⟹ PrediabetesRange
scripts/course.py P90002 A1C:6.5:percent:2026-02-20   # ⟹ DiabetesRange
```

注意 5.6 不是端点、是用户给定值时才能用；单纯做切点演示时，
合法的探针是 `5.7` / `6.4` / `6.5` 这三个本体里写着的数。

### T3 · tier 跃迁（多半推不动，先说清楚）

`riskTier` 由禁忌命中、已确诊活动性并发症、可改变风险因子数、监测缺口共同决定。
补一条检验通常**改不了它**——这不是系统缺陷，是分层规则的结构。

正确打法不是硬推，是**降级为解释**：读 `insufficientReason` 与 `monitoringGaps` 原文，
回答"是这几个缺口在挡路"，并说明补哪一类数据才可能进入分层——**但不要承诺补了就会变成某个 tier**。

---

## 四、探针预算与收敛

| 上限 | 值 | 违反后果 |
|---|---|---|
| 单次 `assume` 条数 | 10（API 硬上限） | 服务端 400 |
| 单个目标的 simulate 次数 | 4 | 超了就停，报"未收敛"，交回用户 |
| 整轮对话 | 12 | 同上 |

**无预算的搜索会滑成"调到出现想要的结论为止"**——那是结果导向的编造，
比答不出来危害大得多。

收敛判据：命中目标态 / 连续两步 `unchanged` / 400 拒绝 / 预算用尽。任一命中即停。

---

## 五、确定性怎么当场证明

```bash
scripts/course.py P90002 A1C:7.9:percent:2026-02-20 --repeat 5
```

5 个 `derivationHash` 相同。这是本方案相对纯 LLM 最硬的一条差异：
同一个问题问 LLM 五遍，答案会飘；这里连哈希都不动。

注入顺序不影响哈希（先 A1C 后 FPG 与先 FPG 后 A1C 同哈希）——顺序不影响结论，
也就不该影响哈希。

哈希变了只有三种可能：假设变了、本体改了、规则改了。
**同一轮对话里假设没变而哈希变了 ⟹ 服务端本体/规则被改过，此前所有轨迹作废。**

---

## 六、推演不写 GraphDB 一个字节

全程在内存 rdflib Dataset 里跑，对 GraphDB 只发 `CONSTRUCT`。
推多少次，库里三元组数一条都不变（`tests/test_simulate.py::test_simulation_never_writes_to_graphdb`
用前后 `size()` 相等盯着）。

所以**推演可以放心多跑**，不需要担心污染，也不需要"清理"。
用户问"这会不会改到真实数据"时，答案是"结构上不可能，沙箱没有写路径"。

---

## 七、自测用例（改完 skill 或怀疑跑偏时对一遍）

演示队列 `P90001–P90030` 覆盖 27 个场景。

```bash
# 黄金用例：差别只有"测了几天"
scripts/course.py P90002 A1C:7.9:percent:2026-02-20

# 单位换算（原值原单位必须一并转述）
scripts/course.py P90002 FPG:7.8:mmol-per-L:2026-03-01
#   ⟹ 换算 140.54 mg-per-dL；不换算会落进 FPG-NORMAL，结论完全相反

# 拒绝路径：照抄拒绝理由，不要改名重试
scripts/course.py P90002 hba1c:7.9:percent:2026-02-20     # ⟹ 400 不猜术语
scripts/course.py P90002 A1C:48:mmol-per-mol:2026-02-20   # ⟹ 400 无已核实换算系数

# 重复假设：同一 (项,值,日期) 注入两次会被拒（图里是同一个 IRI，第二条会被静默吞掉）
scripts/course.py P90002 A1C:7.9:percent:2026-02-20 A1C:7.9:percent:2026-02-20
```
