"""融合查询编排。**只有一种编排模式，不发明第二种。**

    SQL 先收敛患者集合（快、可分页、能按 ICD-10/场景筛）
      → rdf/iri.py 转成 IRI 列表
      → SPARQL 用 VALUES ?pat 注入（永不全库扫描患者图）
      → 拿语义结论 + 出处
      → 按 source_table + source_pk 拼回 SQL 原始行

职责边界（写死，不随需求飘）：
    有多少 / 哪些患者 / 最近一次 / 分页    → SQL
    为什么 / 凭什么 / 能不能 / 依据哪条指南 → SPARQL
    原始那一行长什么样                      → SQL（source_pk 回查）
    这个术语认不认识 / 为什么查不到          → SQL（map_*）

返回结构固定七段，缺一不可 —— 尤其是 `unmapped` 和 `dataQualityNotice`：
**答不出来的部分必须说出来**，返回空集让人以为"没查到"是本项目最反对的行为。
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..db.engine import onto_conn
from ..graph.client import GraphDBClient
from ..rdf import iri as I
from . import templates

DISCLAIMER = (
    "⚠️ 技术验证用途，不是医疗器械，不构成医疗建议。"
    "本系统不输出任何用药剂量，风险分层为规则式定性分层、非概率预测。"
)


def find_patients(
    cfg: Config,
    *,
    icd10: str | None = None,
    origin: str | None = None,
    scenario: str | None = None,
    tier: str | None = None,
    page: int = 1,
    size: int = 20,
) -> dict[str, Any]:
    """SQL 侧的患者检索。分页与筛选都在这一层做完，SPARQL 只处理收敛后的小集合。"""
    where, params = ["1=1"], []
    if icd10:
        where.append(
            "EXISTS (SELECT 1 FROM diabetes.core_diagnosis d "
            "WHERE d.patientid = p.patientid AND d.external_code = %s)")
        params.append(icd10)
    if origin:
        where.append("p.fact_origin = %s")
        params.append(origin)
    if scenario:
        where.append("p.demo_scenario = %s")
        params.append(scenario)
    if tier:
        where.append(
            "EXISTS (SELECT 1 FROM diabetes.pred_risk_stratification r "
            "WHERE r.patientid = p.patientid AND r.tier = %s)")
        params.append(tier)
    clause = " AND ".join(where)
    size = max(1, min(size, 200))
    offset = (max(1, page) - 1) * size

    with onto_conn(cfg) as conn:
        total = conn.scalar(
            f"SELECT count(*) FROM diabetes.core_patient p WHERE {clause}", tuple(params))
        rows = conn.fetchall(
            f"""
            SELECT p.patientid, p.sex, p.birth_year, p.fact_origin, p.demo_scenario,
                   p.source_table, p.source_pk,
                   r.tier, r.insufficient_reason
            FROM diabetes.core_patient p
            LEFT JOIN diabetes.pred_risk_stratification r ON r.patientid = p.patientid
            WHERE {clause}
            ORDER BY p.patientid
            LIMIT %s OFFSET %s
            """,
            (*params, size, offset),
        )
    return {"total": total, "page": page, "size": size, "patients": rows}


def _sparql(cfg: Config, template: str, pids: list[str]) -> list[dict[str, str]]:
    iris = [I.patient_iri(p) for p in pids]
    return GraphDBClient(cfg).sparql_csv(templates.render(template, iris))


def _asserted_facts(conn, pid: str) -> list[dict[str, Any]]:
    """患者的原始事实，每条带回 SQL 那一行的坐标（source_table + source_pk）。"""
    labs = conn.fetchall(
        """
        SELECT lab_result_id AS iri, lab_test_code AS test, result_value AS value,
               result_unit AS unit, source_value, source_unit, collected_at,
               trust_level AS trust, fact_origin AS origin, demo_scenario,
               source_table, source_pk
        FROM diabetes.core_lab_result WHERE patientid = %s ORDER BY collected_at
        """, (pid,))
    for r in labs:
        r["kind"] = "LabResult"
        r["sqlRow"] = {"table": r.pop("source_table"), "pk": r.pop("source_pk")}
    return labs


def _unmapped_notes(conn, pid: str) -> list[dict[str, str]]:
    """这个患者身上**判不了**的那些项 —— 必须说出来。"""
    rows = conn.fetchall(
        """
        SELECT observation_id, value_text
        FROM diabetes.core_observation
        WHERE patientid = %s AND observation_type = 'Other'
          AND value_text LIKE '%%未作数值判定%%'
        ORDER BY observation_id
        """, (pid,))
    out = [{"item": r["observation_id"], "reason": r["value_text"]} for r in rows]

    # 全局缺口：本体里**有概念**但数据判不了的项。
    # 刻意要求 concept_iri IS NOT NULL —— semantic_link 导入的那些候选线索
    # （alt / ast / c肽 …）没有概念、也没人核实过，它们是"待办清单"不是"缺口"，
    # 混进每个患者的返回体里只是噪声。
    gaps = conn.fetchall(
        """
        SELECT src_name, verify_status, note FROM diabetes.map_lab_term
        WHERE verify_status IN ('no-source-data', 'unmappable')
          AND concept_iri IS NOT NULL
        ORDER BY src_name
        """)
    out += [
        {"item": g["src_name"], "status": g["verify_status"],
         "reason": (g["note"] or "")[:240]}
        for g in gaps
    ]
    return out


def _data_quality_notice(conn, pid: str) -> str | None:
    n = conn.scalar(
        "SELECT count(*) FROM diabetes.core_lab_result "
        "WHERE patientid = %s AND trust_level = 'Unverified'", (pid,))
    if not n:
        return None
    return (
        f"本次涉及 {n} 条 valueTrustLevel=Unverified 的上游检验值。"
        "上游 cdr_lis_result 的数值与其参考范围无关（实测全库集中在 0~25，"
        "血小板 15.3 而参考范围 100-300 却标『正常』），因此这些值"
        "**默认不参与任何阈值判定**，仅用于说明管线，不具临床含义。"
    )


def patient_bundle(cfg: Config, pid: str, *, sections: tuple[str, ...] = ()) -> dict[str, Any]:
    """一个患者的完整返回体。七段齐全。"""
    want = set(sections) if sections else {"care_chain", "assessment", "safety", "risk"}
    with onto_conn(cfg) as conn:
        patient = conn.fetchone(
            "SELECT * FROM diabetes.core_patient WHERE patientid = %s", (pid,))
        if patient is None:
            raise KeyError(pid)
        asserted = _asserted_facts(conn, pid)
        unmapped = _unmapped_notes(conn, pid)
        notice = _data_quality_notice(conn, pid)
        strat = conn.fetchone(
            "SELECT * FROM diabetes.pred_risk_stratification WHERE patientid = %s", (pid,))
        factors = conn.fetchall(
            "SELECT * FROM diabetes.pred_factor_hit WHERE patientid = %s "
            "ORDER BY counted_in_tier DESC, risk_rule_id", (pid,))

    inferred: list[dict[str, Any]] = []
    sources: list[dict[str, str]] = []
    care_chain: list[dict[str, str]] = []
    safety: list[dict[str, str]] = []

    if "care_chain" in want:
        care_chain = _sparql(cfg, "care_chain", [pid])
    if "assessment" in want:
        for r in _sparql(cfg, "assessment_evidence", [pid]):
            inferred.append({
                "type": "dmo:Assessment",
                "conclusion": r.get("conclusion"),
                "ruleId": r.get("ruleId"),
                "ruleVersion": r.get("ruleVersion"),
                "applicableContext": r.get("context"),
                "appliesThreshold": r.get("thresholdId"),
                "confirmationRequired": r.get("confirm") == "true",
                "interval": _interval(r),
                "basedOn": {"labResultId": r.get("resultId"),
                            "value": r.get("resultValue"), "unit": r.get("resultUnit"),
                            "sourceValue": r.get("sourceValue") or None,
                            "sourceUnit": r.get("sourceUnit") or None},
                "caveat": r.get("caveat") or None,
            })
            if r.get("quote"):
                sources.append({"quote": r["quote"], "sha256": r.get("sha256", ""),
                                "supports": r.get("thresholdId", "")})
        for r in _sparql(cfg, "diagnosis_evidence", [pid]):
            inferred.append({
                "type": "dmo:Diagnosis",
                "diagnosisId": r.get("diagnosisId"),
                "kind": r.get("kind"),
                "verificationStatus": r.get("verification"),
                "clinicalStatus": r.get("status"),
                "factOrigin": r.get("origin"),
                "externalCode": r.get("code") or None,
                "caveat": r.get("caveat") or None,
            })
    if "safety" in want:
        safety = _sparql(cfg, "medication_safety", [pid])
        for s in safety:
            if s.get("rationale"):
                sources.append({"quote": s["rationale"], "sha256": "",
                                "supports": f"contraindication:{s.get('severity')}"})

    risk = None
    if "risk" in want and strat:
        risk = {
            "tier": strat["tier"],
            "ruleId": strat["rule_id"],
            "ruleVersion": strat["rule_version"],
            "insufficientReason": strat["insufficient_reason"],
            "monitoringGaps": [strat["monitoring_gap"]] if strat["monitoring_gap"] else [],
            "contributingFactors": [
                {
                    "riskRuleId": f["risk_rule_id"],
                    "label": f["risk_factor_label"],
                    "riskCategory": f["risk_category"],
                    "triggerBasis": f["trigger_basis"],
                    "countedInTier": f["counted_in_tier"],
                    "quote": f["quote"],
                    "sha256": f["sha256"],
                    # 数值边界不是本仓库语料说的时，这一句必须出现在返回体里
                    "externalStandardNote": f["external_note"],
                    "fromFact": f["from_fact_iri"],
                } for f in factors
            ],
            "note": strat["caveat"],
        }
        sources += [
            {"quote": f["quote"], "sha256": f["sha256"] or "",
             "supports": f"riskRule:{f['risk_rule_id']}"}
            for f in factors if f["quote"]
        ]

    # 去重但保序
    seen, uniq = set(), []
    for s in sources:
        key = (s["quote"], s["supports"])
        if key not in seen:
            seen.add(key)
            uniq.append(s)

    return {
        "patient": patient,
        "careChain": care_chain,
        "riskStratification": risk,
        "assertedFacts": asserted,
        "inferredFacts": inferred,
        "sources": uniq,
        "unmapped": unmapped,
        "dataQualityNotice": notice,
        "disclaimer": DISCLAIMER,
    }


def _interval(r: dict[str, str]) -> str | None:
    """把 operator + bound 还原成人能读的区间，如 "[6.5, ∞) percent"。"""
    lo_op, up_op = r.get("loOp"), r.get("upOp")
    if not lo_op and not up_op:
        return None
    lo = "(-∞" if lo_op == "None" else (
        f"[{r.get('lo')}" if lo_op == "GTE" else f"({r.get('lo')}")
    up = "+∞)" if up_op == "None" else (
        f"{r.get('up')}]" if up_op == "LTE" else f"{r.get('up')})")
    return f"{lo}, {up} {r.get('boundUnit', '')}".strip()


def explain_gap(cfg: Config, term: str) -> dict[str, Any]:
    """诚实回答「为什么查不到」。本项目最有说服力的一个工具。"""
    with onto_conn(cfg) as conn:
        mapped = conn.fetchall(
            """
            SELECT m.src_name, m.src_ref_range, m.value_kind, m.verify_status,
                   m.unit_src, m.unit_target, m.conv_factor, m.note,
                   c.label AS concept_label, c.iri AS concept_iri
            FROM diabetes.map_lab_term m
            LEFT JOIN diabetes.map_concept_ref c ON c.iri = m.concept_iri
            WHERE m.src_name ILIKE %s
            """, (f"%{term}%",))
        unmapped = conn.fetchall(
            "SELECT * FROM diabetes.map_unmapped_term WHERE term ILIKE %s",
            (f"%{term}%",))
        concepts = conn.fetchall(
            """
            SELECT iri, concept_kind, code, label, alt_labels, unit_canonical
            FROM diabetes.map_concept_ref
            WHERE label ILIKE %s OR code ILIKE %s OR %s = ANY(alt_labels)
            LIMIT 10
            """, (f"%{term}%", f"%{term}%", term))
        upstream_rows = conn.scalar(
            "SELECT count(*) FROM diabetes.stg_lis_result WHERE itemname ILIKE %s",
            (f"%{term}%",))
        parent_only = conn.fetchall(
            """
            SELECT DISTINCT itemname, count(*) OVER (PARTITION BY itemname) AS n
            FROM diabetes.stg_lis_detail WHERE itemname ILIKE %s
            """, (f"%{term}%",))

    verdicts = []
    for m in mapped:
        if m["verify_status"] == "no-source-data":
            verdicts.append(
                f"「{m['src_name']}」在本体里有概念（{m['concept_label']}），"
                f"但上游全库**没有这个检验的数值**。{m['note'] or ''}")
        elif m["verify_status"] == "unmappable":
            verdicts.append(
                f"「{m['src_name']}」结构上无法作数值判定。{m['note'] or ''}")
        elif m["verify_status"] == "candidate":
            verdicts.append(
                f"「{m['src_name']}」的映射**尚未人工核实**，因此不参与判定。"
                f"{m['note'] or ''}")
    if parent_only and not upstream_rows:
        verdicts.append(
            f"上游有名为「{term}」的**检验大项**（{parent_only[0]['n']} 条），"
            "但大项名与其下子项的实际内容语义错位（实测 itemname='糖化血红蛋白' "
            "的检验单下挂的子项是 AST/尿蛋白/血小板/尿素氮），"
            "因此大项名一律不做术语映射 —— 映射它等于主动制造错误。")
    if not verdicts and not concepts:
        verdicts.append(f"本体与映射表里都没有「{term}」。未命中只记账，不猜。")
    # 同一个术语可能有多行映射（不同参考范围），说明文字却是同一句。去重但保序。
    verdicts = list(dict.fromkeys(verdicts))

    return {
        "term": term,
        "verdicts": verdicts,
        "mappings": mapped,
        "unmappedRecords": unmapped,
        "candidateConcepts": concepts,
        "upstreamResultRows": upstream_rows,
        "upstreamParentItemOnly": parent_only,
        "disclaimer": DISCLAIMER,
    }
