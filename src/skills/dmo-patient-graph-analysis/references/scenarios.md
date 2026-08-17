# 演示队列自测用例（P90001–P90030 / S01–S27）

来源：`src/dmo/db/seed/cohort_patient.csv`（`demo_note` 列即预期结论）。
**全部是 `fact_origin = demo-cohort`。** 用它们校准判断，但**不得**拿它们的漂亮结论去代表真实数据的能力——真实侧（`ehr-legacy`）15 个 E11 患者全部是 `Insufficient-Evidence`。

用法：

```bash
scripts/dmo-get.sh /patients/P90002/assessment   # 对照下表"预期"列
```

---

## 阈值与区间边界

| 患者 | 场景 | 预期 |
|---|---|---|
| P90001 | S01 | 三项检验全在正常区间 ⟹ **零 Diagnosis** |
| P90002 | S02 | A1C 7.4% 单次 ⟹ `confirmationRequired=true` 且只一天 ⟹ **Provisional 而非 Confirmed** |
| P90003 | S03 | 两个不同日期各一次 A1C 超标 ⟹ **Confirmed**，`supportsDiagnosis` 连回两条 Assessment |
| P90010 | S09 | A1C 6.0% ⟹ Prediabetes，**不得**推出 Diabetes |
| P90011 | S10 | 血糖 62 mg/dL ⟹ 落在 `GLUCOSE-HYPO` 的 `[54,70)` 开区间 |
| P90017 | S16 | A1C 恰好 **5.7** ⟹ 归 Prediabetes 不归 Normal（开区间下界） |
| P90018 | S16 | A1C 恰好 **6.4** ⟹ Prediabetes 上界（闭区间） |
| P90019 | S16 | A1C 恰好 **6.5** ⟹ Diabetes 下界（闭区间） |

> S16 三例专测"用 `>=` 近似开闭区间"这一类错误。任何把 `interval` 口语化成大小比较的写法，都会在这三例上翻车。

## 上下文敏感（开放世界）

| 患者 | 场景 | 预期 |
|---|---|---|
| P90004 | S04 | 孕 26 周糖筛 142 mg/dL ⟹ 命中妊娠期转诊触发点 |
| P90005 | S04b | **非妊娠同值** 142 mg/dL ⟹ **零命中**（GCT1H 阈值 `populationContext=Pregnant`） |

> 同一个数值、两个结论。这一对是 `applicableContext` 存在的全部理由。

## 单位与缺失

| 患者 | 场景 | 预期 |
|---|---|---|
| P90012 | S11 | 空腹血糖 7.8 **mmol/L** ⟹ 换算后 140.5 mg/dL 判 Diabetes；**不换算会误判 Normal** |
| P90013 | S12 | A1C 结果**缺单位** ⟹ 拒绝进 LabResult，进 `unmapped[]` |
| P90028 | S25 | 有就诊记录但一条检验都没有 ⟹ 优雅降级，不报错 |

## 诊断分型与并发症

| 患者 | 场景 | 预期 |
|---|---|---|
| P90006 | S05 | DKD + 白蛋白尿分期，UACR 420 mg/g ⟹ Macroalbuminuria |
| P90014 | S13 | 仅有阈值证据、无 ICD-10 分型 ⟹ `diagnosisType` 落到 **DM-Unspecified** |
| P90015 | S14 | 纵向随访 A1C 8.9 → 7.6 → 6.8，达标判定取**最新**一次 |
| P90016 | S15 | 同时有 E10 与 E11 两条已确诊分型 ⟹ **SHACL 分型唯一性违规** |
| P90029 | S26 | DKA 急性事件 + 血糖 320 mg/dL ⟹ 同时命中酮症警戒与急诊阈值 |

## 用药安全

| 患者 | 场景 | 预期 |
|---|---|---|
| P90007 | S06 | 一条二甲双胍用药同时 `treats` 糖尿病与糖尿病肾病两条诊断 |
| P90008 | S07 | ESRD/透析 + 恩格列净 ⟹ **绝对禁忌违规**，带 FDA 原文 |
| P90009 | S08 | ESRD + 二甲双胍 ⟹ **零违规**（语料对二甲双胍只有 Caution 级表述） |
| P90027 | S24 | 用药名在 `map_drug_term` 里未映射 ⟹ 记入 `unmapped`，**不猜** |

> P90009 是最容易被"帮忙补全"毁掉的一例。凭常识说"ESRD 该停二甲双胍"就是编造出处——语料里没有任何 eGFR 数值切点。有回归测试盯着。

## 风险分层

| 患者 | 场景 | 预期 |
|---|---|---|
| P90020 | S17 | BMI 31.2 + 家族史 + 每周活动 1 次 + 已确诊 ⟹ 多因子样本 |
| P90021 | S18 | 仅 BMI 26.4（超重档）+ 已确诊 ⟹ 单一可改变因子 |
| P90022 | S19 | 已确诊但**无任何可观测事实** ⟹ `Insufficient-Evidence` |
| P90023 | S20 | 已确诊 + 已确诊 DKD ⟹ 慢性并发症在身 ⟹ `High` |
| P90024 | S21 | 已确诊 + 完整监测（UACR/eGFR 齐全）+ 无风险因子 ⟹ `Low` |
| P90025 | S22 | 已确诊 + 缺 UACR 年检 ⟹ **监测缺口** |
| P90030 | S27 | 高血压 I10 + 高脂血症 E78 ⟹ 两条 `external-standard` 且**无出处**的风险规则，`countedInTier=false`，**不参与 tier** |

## 数据质量

| 患者 | 场景 | 预期 |
|---|---|---|
| P90026 | S23 | 全部检验 `trust=Unverified` ⟹ **零 Assessment** + `dataQualityNotice` |

---

## 真实侧对照

```bash
scripts/dmo-get.sh /patients/P00016/risk
```

15 个真实 E11 患者**全部**是 `Insufficient-Evidence`，`insufficientReason` 说清三个原因：检验值均为 `Unverified`、无任何可用风险侧事实、年龄推不出来。

**这是本仓库最重要的一条基线。** 如果你对某个 `ehr-legacy` 患者给出了比这更"完整"的结论，先怀疑自己。

---

## 推演的自测用例

上表的 S02 / S03 一对（单次 ⟹ Provisional、两日 ⟹ Confirmed）与 S16 三个边界例
（5.7 / 6.4 / 6.5），在推演里可以**在同一个患者身上**当场复现，不必换患者：

```bash
uv run dmo simulate P90002 --assume A1C 7.9 percent 2026-02-20  # ⟹ Provisional → Confirmed
uv run dmo simulate P90002 --assume A1C 5.7 percent 2026-02-20  # ⟹ Prediabetes（开区间下界）
```

完整清单见 [simulation.md](simulation.md#自测用例)。
