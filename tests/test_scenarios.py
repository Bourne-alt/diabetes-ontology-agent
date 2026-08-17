"""场景断言 —— 每条对应 seed/cohort_patient.csv 里的一个验证点。

这些不是"跑通就行"的冒烟测试。每一条都在断言一个**具体的、错了会出临床问题的行为**：
单次异常不等于确诊、妊娠与非妊娠用不同切点、开区间边界、单位换算、
安全形状不误报、不可信值不参与判定。
"""

from __future__ import annotations

import pytest


def _tiers(ask, pid_filter: str) -> dict[str, str]:
    rows = ask(
        f"""SELECT ?pid ?tier WHERE {{
          GRAPH ?g {{ ?p dmo:patientId ?pid }}
          FILTER(STRSTARTS(STR(?g), "urn:dmo:patient:"))
          ?p dmo:hasRiskStratification ?s . ?s dmo:riskTier ?tier .
          FILTER(STRSTARTS(?pid, "{pid_filter}")) }}"""
    )
    return {r["pid"]: r["tier"] for r in rows}


def _assessments(ask, pid: str) -> list[tuple[str, str, str]]:
    rows = ask(
        f"""SELECT ?tid ?concl ?ctx WHERE {{
          GRAPH ?g {{ ?p dmo:patientId "{pid}" }}
          ?p dmo:hasAssessment ?a .
          ?a dmo:conclusion ?concl ; dmo:applicableContext ?ctx ;
             dmo:appliesThreshold ?th .
          ?th dmo:thresholdId ?tid }}"""
    )
    return [(r["tid"], r["concl"], r["ctx"]) for r in rows]


def _derived_dx(ask, pid: str) -> list[tuple[str, str]]:
    rows = ask(
        f"""SELECT ?status ?caveat WHERE {{
          GRAPH ?g {{ ?p dmo:patientId "{pid}" }}
          ?p dmo:hasDiagnosis ?dx .
          ?dx dmo:factOrigin "derived" ; dmo:verificationStatus ?status ;
              dmo:caveat ?caveat }}"""
    )
    return [(r["status"], r["caveat"]) for r in rows]


# ── S02 / S03：单次异常 ≠ 确诊 ──────────────────────────────────────


def test_s02_single_abnormal_is_provisional_not_confirmed(ask):
    """A1C 7.4% 只测了一次 ⟹ Provisional。

    这是整个项目最有说服力的一条：纯 LLM 和字符串匹配在这里都会直接说"是糖尿病"。
    指南的诊断表给的是**单次测量落在哪一档**，不等于确诊。
    """
    dx = _derived_dx(ask, "P90002")
    assert dx, "P90002 应该有一条由阈值推出的 Diagnosis"
    statuses = {s for s, _ in dx}
    assert statuses == {"Provisional"}, f"期望只有 Provisional，实际 {statuses}"
    assert any("单次异常不等于确诊" in c for _, c in dx), "Provisional 必须带 caveat 说明原因"


def test_s03_two_distinct_days_confirms(ask):
    """同一阈值在两个不同日期各命中一次 ⟹ Confirmed。与 S02 的差别只有"测了几天"。"""
    statuses = {s for s, _ in _derived_dx(ask, "P90003")}
    assert statuses == {"Confirmed"}, f"期望 Confirmed，实际 {statuses}"


# ── S04 / S04b：人群上下文 ──────────────────────────────────────────


def test_s04_pregnancy_context_gates_threshold(ask):
    """同样 142 mg/dL：妊娠命中转诊触发点，非妊娠零命中。

    populationContext 不生效的话，非妊娠患者也会被扣上"需做 OGTT"的帽子。
    """
    preg = _assessments(ask, "P90004")
    nonpreg = [a for a in _assessments(ask, "P90005") if a[0].startswith("GCT1H")]
    assert any(t == "GCT1H-REFER-PREG" for t, _, _ in preg), f"P90004 应命中转诊触发点，实际 {preg}"
    assert all(c == "Pregnant" for _, _, c in preg if _), "上下文应为 Pregnant"
    assert nonpreg == [], f"P90005 非妊娠不该命中妊娠期阈值，实际 {nonpreg}"


# ── S09 / S16：开闭区间与边界 ───────────────────────────────────────


def test_s09_prediabetes_never_implies_diabetes(ask):
    """A1C 6.0 只能是 Prediabetes。推出 DiabetesRange 说明区间判定错了。"""
    concls = {c for _, c, _ in _assessments(ask, "P90010")}
    assert concls == {"Prediabetes"}, f"期望只有 Prediabetes，实际 {concls}"


@pytest.mark.parametrize(
    "pid,value,expected",
    [
        ("P90017", "5.7", "Prediabetes"),    # A1C-NORMAL 上界是 LT ⟹ 5.7 不属于 Normal
        ("P90018", "6.4", "Prediabetes"),    # Prediabetes 上界 LTE ⟹ 6.4 仍在内
        ("P90019", "6.5", "DiabetesRange"),  # Diabetes 下界 GTE ⟹ 6.5 落进来
    ],
)
def test_s16_open_closed_interval_boundaries(ask, pid, value, expected):
    """开闭区间必须精确。用 >= 近似「below 5.7%」会把 5.7 错判成 Normal。"""
    concls = {c for _, c, _ in _assessments(ask, pid)}
    assert concls == {expected}, f"A1C {value} 期望 {expected}，实际 {concls}"


def test_s10_hypoglycemia_open_upper_bound(ask):
    """血糖 62 落在 GLUCOSE-HYPO 的 [54, 70)。"""
    tids = {t for t, _, _ in _assessments(ask, "P90011")}
    assert "GLUCOSE-HYPO" in tids, f"实际命中 {tids}"


# ── S11：单位陷阱 ───────────────────────────────────────────────────


def test_s11_unit_conversion_changes_the_conclusion(ask):
    """7.8 mmol/L 换算成 140.5 mg/dL 才命中 FPG-DIABETES。

    不换算的话 7.8 会被当成 mg/dL 读，落进 FPG-NORMAL（≤99）—— 结论完全相反。
    原始值必须保留，否则事后无从复核。
    """
    rows = ask(
        """SELECT ?v ?u ?sv ?su ?tid WHERE {
          GRAPH ?g { ?p dmo:patientId "P90012" ; dmo:hasEncounter ?e .
                     ?e dmo:producesLabResult ?r .
                     ?r dmo:resultValue ?v ; dmo:resultUnit ?u ;
                        dmo:sourceValue ?sv ; dmo:sourceUnit ?su }
          ?p dmo:hasAssessment ?a .
          ?a dmo:basedOnLabResult ?r ; dmo:appliesThreshold ?th .
          ?th dmo:thresholdId ?tid }"""
    )
    assert rows, "P90012 应有基于换算后数值的 Assessment"
    r = rows[0]
    assert r["su"] == "mmol-per-L" and r["u"] == "mg-per-dL"
    assert abs(float(r["v"]) - 140.54) < 0.1, f"换算结果应约 140.5，实际 {r['v']}"
    assert any(x["tid"] == "FPG-DIABETES-NONPREG" for x in rows)


def test_s12_missing_unit_never_enters_lab_result(db):
    """缺单位的检验结果拒绝进 core_lab_result。148 是 mg/dL 还是 mmol/L，结论天差地别。"""
    from dmo.db.engine import onto_conn

    with onto_conn(db) as conn:
        in_lab = conn.scalar(
            "SELECT count(*) FROM diabetes.core_lab_result WHERE lab_result_id = %s",
            ("L90013-A1C",))
        in_obs = conn.scalar(
            "SELECT count(*) FROM diabetes.core_observation WHERE observation_id = %s",
            ("L90013-A1C",))
    assert in_lab == 0, "缺单位的结果不该进 core_lab_result"
    assert in_obs == 1, "但必须留在 core_observation 里，不能沉默丢弃"


# ── S07 / S08：安全形状一正一反 ─────────────────────────────────────


def test_s07_absolute_contraindication_fires_with_source(ask):
    """ESRD + 恩格列净 ⟹ 绝对禁忌，且必须带原文。"""
    rows = ask(
        """SELECT ?sev ?rat WHERE {
          GRAPH ?g { ?p dmo:patientId "P90008" }
          ?p dmo:hasContraindicationFlag ?f .
          ?f dmo:flagSeverity ?sev ; dmo:rationale ?rat }"""
    )
    absolutes = [r for r in rows if r["sev"] == "Absolute"]
    assert absolutes, f"P90008 应报绝对禁忌，实际 {rows}"
    assert "Do not take these drugs" in absolutes[0]["rat"], "必须带 FDA 原文"


def test_s08_metformin_with_esrd_raises_no_absolute_flag(ask):
    """ESRD + 二甲双胍 ⟹ **零绝对禁忌**。

    语料对二甲双胍只有 Caution 级表述（乳酸酸中毒风险），没有任何 eGFR 数值切点。
    补一个 eGFR<30 就是编造出处。这条测试是防止"顺手加严一点"的回归哨兵。
    """
    rows = ask(
        """SELECT ?sev WHERE {
          GRAPH ?g { ?p dmo:patientId "P90009" }
          ?p dmo:hasContraindicationFlag ?f . ?f dmo:flagSeverity ?sev }"""
    )
    sevs = {r["sev"] for r in rows}
    assert "Absolute" not in sevs, f"P90009 不该报绝对禁忌，实际 {sevs}"


def test_pregnancy_targets_never_apply_to_non_pregnant(ask):
    """管理目标也要过人群上下文，不只是诊断阈值。

    回归测试：早先 21-target-attainment.rq 只按检验项目匹配 GlycemicTarget，
    于是**男性患者**被拿「备孕期 A1C ≤6.5%」这条妊娠期目标判定是否达标，
    而且不报任何错。targetPopulation 是给人读的自由文本，机器过滤不了；
    必须靠结构化的 targetPopulationContext。
    """
    rows = ask(
        """SELECT ?pid ?ctx WHERE {
          GRAPH ?g { ?p dmo:patientId ?pid }
          FILTER(STRSTARTS(STR(?g), "urn:dmo:patient:"))
          ?p dmo:hasAssessment ?a .
          ?a dmo:ruleId "TARGET-ATTAINMENT" ; dmo:applicableContext ?ctx .
          FILTER(CONTAINS(?ctx, "妊娠") || CONTAINS(?ctx, "备孕")) }"""
    )
    # 只有真的记录了 PregnancyStatus=Pregnant 的患者才允许出现妊娠期目标
    pregnant = {
        r["pid"] for r in ask(
            """SELECT ?pid WHERE {
              GRAPH ?g { ?p dmo:patientId ?pid ; dmo:hasClinicalObservation ?o .
                         ?o dmo:observationType "PregnancyStatus" ;
                            dmo:valueText "Pregnant" } }""")
    }
    offenders = {r["pid"] for r in rows} - pregnant
    assert not offenders, f"非妊娠患者被套用了妊娠期管理目标：{sorted(offenders)[:5]}"


# ── S23：可信度门禁 ─────────────────────────────────────────────────


def test_s23_unverified_values_produce_no_assessment(ask):
    """trust=Unverified 的检验默认不参与阈值判定。"""
    rows = ask(
        """SELECT ?a WHERE {
          GRAPH ?g { ?p dmo:patientId "P90026" } ?p dmo:hasAssessment ?a }"""
    )
    assert rows == [], f"P90026 全部值不可信，应零 Assessment，实际 {len(rows)} 条"


# ── 风险分层 ────────────────────────────────────────────────────────


def test_real_ehr_patients_are_all_insufficient_evidence(ask):
    """真实 E11 患者**必然**落在 Insufficient-Evidence。

    这不是 bug，是本方案要演示的核心结论。三个独立原因：
      · 检验值全部 trust=Unverified（上游是 0~25 的随机数）；
      · 每个患者恰好一条诊断，零共病，风险侧无事实；
      · birthday 有 329/400 在未来，年龄推不出来。
    对照组的做法是给一个 confidence 0.9 的答案；这里的做法是说清为什么判不了。
    """
    tiers = _tiers(ask, "P00")
    assert tiers, "真实患者应该有分层记录（哪怕结论是判不了）"
    assert set(tiers.values()) == {"Insufficient-Evidence"}, \
        f"真实患者不该出现其他 tier，实际 {sorted(set(tiers.values()))}"


@pytest.mark.parametrize(
    "pid,expected",
    [
        ("P90008", "High"),                   # 绝对禁忌命中
        ("P90023", "High"),                   # 已确诊 DKD
        ("P90020", "Moderate"),               # 多个可改变风险因子
        ("P90025", "Moderate"),               # 监测缺口（无 UACR）
        ("P90024", "Low"),                    # 监测齐全、无风险因子
        ("P90022", "Insufficient-Evidence"),  # 无任何可观测事实
    ],
)
def test_risk_tier_per_scenario(ask, pid, expected):
    assert _tiers(ask, pid).get(pid) == expected


def test_factors_without_provenance_never_count_toward_tier(db):
    """列不出出处的因子**不参与判定**，但仍出现在返回体里。

    ICD-HYPERTENSION / ICD-DYSLIPIDEMIA 就是这样：抽取产物里有对应的风险因子，
    但本仓库语料没有可逐字引用的「高血压 ⟹ 2 型糖尿病风险升高」断言。
    过滤掉它们不等于假装它们不存在 —— 缺口要可见。
    """
    from dmo.db.engine import onto_conn

    with onto_conn(db) as conn:
        counted_without_source = conn.scalar(
            "SELECT count(*) FROM diabetes.pred_factor_hit "
            "WHERE counted_in_tier AND (sha256 IS NULL OR sha256 = '')")
        no_source_rules = {
            r["risk_rule_id"] for r in conn.fetchall(
                "SELECT DISTINCT risk_rule_id FROM diabetes.pred_factor_hit "
                "WHERE NOT counted_in_tier")}
    assert counted_without_source == 0, "计入 tier 的因子必须有 sha256 出处"
    assert {"ICD-HYPERTENSION", "ICD-DYSLIPIDEMIA"} <= no_source_rules, \
        f"这两条无出处的规则应出现在不计入的名单里，实际 {no_source_rules}"


def test_no_probability_or_time_window_anywhere(db):
    """返回体里绝不出现概率、百分比、时间窗。

    tier 是有序枚举不是分数。这条测试是对「不做伪预测」这个承诺的可执行断言。
    """
    import re

    from dmo.db.engine import onto_conn

    # ⚠️ 必须带**数字**才算违规。只匹配「概率」这个词会误伤免责声明本身
    #    （"定性分层，非概率预测：不含发生概率、不含时间窗"）——
    #    那句话恰恰是在声明不做这件事，把它判成违规就本末倒置了。
    banned = re.compile(
        r"\d+(\.\d+)?\s*%"                      # 23%
        r"|\d+\s*年(内|后)"                      # 5 年内
        r"|\d+(\.\d+)?\s*倍(风险)?"              # 2.3 倍风险
        r"|(probability|risk\s*score)\s*[:=]?\s*\d",   # probability: 0.23
        re.IGNORECASE,
    )
    with onto_conn(db) as conn:
        texts = [
            (r["patientid"], t)
            for r in conn.fetchall(
                "SELECT patientid, tier, caveat, insufficient_reason, monitoring_gap "
                "FROM diabetes.pred_risk_stratification")
            for t in (r["tier"], r["caveat"], r["insufficient_reason"] or "",
                      r["monitoring_gap"] or "")
        ]
    hits = [(pid, t) for pid, t in texts if banned.search(t)]
    assert not hits, f"分层输出里出现了概率/时间窗表述：{hits[:3]}"
