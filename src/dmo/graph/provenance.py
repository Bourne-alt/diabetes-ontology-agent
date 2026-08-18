"""反向溯源 —— 从一个**机器推出来的结论**一路走到原文哪一句、数据库哪一行。

「推理」和「可核查」两个亮点在这里合流：

    Diagnosis(Provisional)
      ← supportsDiagnosis ── Assessment(conclusion=…)
          ← appliesThreshold ── DiagnosticThreshold(confirmationRequired=true)
              ← thresholdCitesPassage ── SourcePassage(quote 逐字, sha256)
                  ← GuidelineSource
          ← basedOnLabResult ── LabResult(value/unit)
              ← sqlRow ── core_lab_result(source_table, source_pk)

`/patients/{pid}/assessment` 给的是同一条链的**汇总视图**，按患者组织；这里按**单个结论**
组织，且能从链上任何一个中间节点起步。差别在提问方式：前者问「这个患者判成什么」，
后者问「这一条结论凭什么」。

## 断链必须报出来，不能只报走通的那部分

`51-risk-stratification.rq` 的信号 5 明说：没有 `riskRuleCitesPassage` 的规则产出 Hit
但不计入 tier。这类 Hit 溯源到规则那一步就断了 —— 返回体如果只列走通的环节，
读的人会以为「这条结论有出处」。所以 `brokenLinks` 与 `chain` 同等重要。

## 类型判定只看断言，不看 rdf:type

owl2-rl 的 prp-dom 会顺着谓词的 domain 反推类型：每个 `RiskFactorHit` 同时也是
`dmo:RiskRule` 和 `dmo:Assessment`（见 rules.py 与 explore.py）。按 `rdf:type` 分派
会把患者命中记录当成 Assessment 去溯源，查出一堆空。
**断言的类型在命名图里，推出来的不在** —— 只认前者。
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from .explore import _Q_GRAPHS, PREFIXES, ExploreError, _guard_fixture, _iri_ok, _short

# 能溯源的结论类型。顺序即优先级：一个节点被断言成多个类时取第一个。
KINDS = ("Assessment", "Diagnosis", "RiskFactorHit", "ContraindicationFlag",
         "RiskStratification")

# ⚠️ **SQL 的 `*_id` 列存的是业务号，不是 IRI。**
#    图里节点 IRI 是 `.../diagnosis/EHR-DX-P00002-C00002-D901`（`|` 换成了 `-`，
#    否则 IRI 不合法），而 `core_diagnosis.diagnosis_id` 存的是原始的
#    `EHR-DX-P00002|C00002|D901`。拿 IRI 直接去 SQL 查永远查不到，而且**查不到不报错**
#    —— 只是回查那一环静默消失，返回体看着仍然完整。
#    所以先用图里的 `dmo:*Id` 字面量把 IRI 翻成业务号，再回查。
FACT_TABLES = (
    ("core_lab_result", "lab_result_id", "LabResult"),
    ("core_diagnosis", "diagnosis_id", "Diagnosis"),
    ("core_observation", "observation_id", "ClinicalObservation"),
    ("core_medication_use", "medication_use_id", "MedicationUse"),
)

_Q_FACT_IDS = PREFIXES + """
SELECT ?f ?id WHERE {
  VALUES ?f { %s }
  GRAPH ?pg {
    { ?f dmo:labResultId ?id } UNION { ?f dmo:diagnosisId ?id }
    UNION { ?f dmo:observationId ?id } UNION { ?f dmo:medicationUseId ?id }
  }
  FILTER(STRSTARTS(STR(?pg), "urn:dmo:patient:"))
}
"""

_Q_ASSERTED_TYPES = PREFIXES + """
SELECT DISTINCT ?t WHERE {{ GRAPH ?g {{ <{iri}> a ?t }} FILTER(!isBlank(?t)) }}
"""

_Q_ASSESSMENT = PREFIXES + """
SELECT ?pid ?conclusion ?ruleId ?ruleVersion ?context ?caveat
       ?th ?thresholdId ?lo ?loOp ?up ?upOp ?boundUnit ?confirm
       ?psg ?res ?resultValue ?resultUnit ?collectedAt ?labResultId
WHERE {{
  <{iri}> dmo:conclusion ?conclusion ; dmo:ruleId ?ruleId ; dmo:ruleVersion ?ruleVersion .
  OPTIONAL {{ <{iri}> dmo:applicableContext ?context }}
  OPTIONAL {{ <{iri}> dmo:caveat ?caveat }}
  OPTIONAL {{ ?pat dmo:hasAssessment <{iri}> .
             GRAPH ?pg {{ ?pat dmo:patientId ?pid }}
             FILTER(STRSTARTS(STR(?pg), "urn:dmo:patient:")) }}
  OPTIONAL {{ <{iri}> dmo:appliesThreshold ?th .
             OPTIONAL {{ ?th dmo:thresholdId ?thresholdId }}
             OPTIONAL {{ ?th dmo:lowerBound ?lo }}   OPTIONAL {{ ?th dmo:lowerOperator ?loOp }}
             OPTIONAL {{ ?th dmo:upperBound ?up }}   OPTIONAL {{ ?th dmo:upperOperator ?upOp }}
             OPTIONAL {{ ?th dmo:boundUnit ?boundUnit }}
             OPTIONAL {{ ?th dmo:confirmationRequired ?confirm }}
             OPTIONAL {{ ?th dmo:thresholdCitesPassage ?psg }} }}
  OPTIONAL {{ <{iri}> dmo:basedOnLabResult ?res .
             GRAPH ?pg2 {{ ?res dmo:labResultId ?labResultId ;
                              dmo:resultValue ?resultValue ; dmo:resultUnit ?resultUnit .
                          OPTIONAL {{ ?res dmo:collectedAt ?collectedAt }} }}
             FILTER(STRSTARTS(STR(?pg2), "urn:dmo:patient:")) }}
}}
"""

_Q_DIAGNOSIS = PREFIXES + """
SELECT ?pid ?kind ?verification ?status ?origin ?code ?caveat ?diagnosisId
       ?support ?supportConclusion ?supportThresholdId
WHERE {{
  <{iri}> dmo:diagnosisKind ?kind .
  OPTIONAL {{ <{iri}> dmo:verificationStatus ?verification }}
  OPTIONAL {{ <{iri}> dmo:clinicalStatus ?status }}
  OPTIONAL {{ <{iri}> dmo:factOrigin ?origin }}
  OPTIONAL {{ <{iri}> dmo:externalCode ?code }}
  OPTIONAL {{ <{iri}> dmo:caveat ?caveat }}
  OPTIONAL {{ <{iri}> dmo:diagnosisId ?diagnosisId }}
  OPTIONAL {{ ?pat dmo:hasDiagnosis <{iri}> .
             GRAPH ?pg {{ ?pat dmo:patientId ?pid }}
             FILTER(STRSTARTS(STR(?pg), "urn:dmo:patient:")) }}
  OPTIONAL {{ ?support dmo:supportsDiagnosis <{iri}> .
             OPTIONAL {{ ?support dmo:conclusion ?supportConclusion }}
             OPTIONAL {{ ?support dmo:appliesThreshold ?sth . ?sth dmo:thresholdId ?supportThresholdId }} }}
}}
"""

_Q_RISK_HIT = PREFIXES + """
SELECT ?pid ?basis ?rule ?riskRuleId ?ruleLabel ?externalNote ?psg
       ?riskFactor ?riskFactorLabel ?category ?fact
WHERE {{
  <{iri}> dmo:hitsRiskRule ?rule .
  OPTIONAL {{ <{iri}> dmo:triggerBasis ?basis }}
  OPTIONAL {{ <{iri}> dmo:hitFromFact ?fact }}
  OPTIONAL {{ <{iri}> dmo:hitRiskFactor ?riskFactor .
             OPTIONAL {{ ?riskFactor rdfs:label ?riskFactorLabel }}
             OPTIONAL {{ ?riskFactor dmo:riskCategory ?category }} }}
  OPTIONAL {{ ?rule dmo:riskRuleId ?riskRuleId }}
  OPTIONAL {{ ?rule rdfs:label ?ruleLabel }}
  OPTIONAL {{ ?rule dmo:externalStandardNote ?externalNote }}
  OPTIONAL {{ ?rule dmo:riskRuleCitesPassage ?psg }}
  OPTIONAL {{ ?pat dmo:hasRiskFactorHit <{iri}> .
             GRAPH ?pg {{ ?pat dmo:patientId ?pid }}
             FILTER(STRSTARTS(STR(?pg), "urn:dmo:patient:")) }}
}}
"""

_Q_FLAG = PREFIXES + """
SELECT ?pid ?severity ?rationale ?mu ?med ?medLabel ?cond ?condLabel
WHERE {{
  <{iri}> dmo:flagSeverity ?severity .
  OPTIONAL {{ <{iri}> dmo:rationale ?rationale }}
  OPTIONAL {{ <{iri}> dmo:flagMedicationUse ?mu .
             GRAPH ?pg2 {{ ?mu dmo:usesMedication ?med }}
             FILTER(STRSTARTS(STR(?pg2), "urn:dmo:patient:"))
             OPTIONAL {{ ?med rdfs:label ?medLabel }} }}
  OPTIONAL {{ <{iri}> dmo:flagCondition ?cond . OPTIONAL {{ ?cond rdfs:label ?condLabel }} }}
  OPTIONAL {{ ?pat dmo:hasContraindicationFlag <{iri}> .
             GRAPH ?pg {{ ?pat dmo:patientId ?pid }}
             FILTER(STRSTARTS(STR(?pg), "urn:dmo:patient:")) }}
}}
"""

_Q_STRATIFICATION = PREFIXES + """
SELECT ?pid ?tier ?ruleId ?ruleVersion ?reason ?gap ?caveat ?hit
WHERE {{
  <{iri}> dmo:riskTier ?tier .
  OPTIONAL {{ <{iri}> dmo:ruleId ?ruleId }}
  OPTIONAL {{ <{iri}> dmo:ruleVersion ?ruleVersion }}
  OPTIONAL {{ <{iri}> dmo:insufficientReason ?reason }}
  OPTIONAL {{ <{iri}> dmo:monitoringGap ?gap }}
  OPTIONAL {{ <{iri}> dmo:caveat ?caveat }}
  OPTIONAL {{ ?pat dmo:hasRiskStratification <{iri}> .
             GRAPH ?pg {{ ?pat dmo:patientId ?pid }}
             FILTER(STRSTARTS(STR(?pg), "urn:dmo:patient:"))
             OPTIONAL {{ ?pat dmo:hasRiskFactorHit ?hit }} }}
}}
"""


def _first(rows: list[dict[str, str]], key: str) -> str | None:
    for r in rows:
        if r.get(key):
            return r[key]
    return None


def _distinct(rows: list[dict[str, str]], key: str) -> list[str]:
    out: list[str] = []
    for r in rows:
        v = r.get(key)
        if v and v not in out:
            out.append(v)
    return out


def _fact_ids(client, fact_iris: list[str]) -> dict[str, str]:
    """事实 IRI → 业务号。患者图守卫在这里，绝不会摸到 urn:dmo:data 的夹具。"""
    if not fact_iris:
        return {}
    values = " ".join(f"<{i}>" for i in fact_iris)
    return {r["f"]: r["id"] for r in client.sparql_csv(_Q_FACT_IDS % values) if r.get("id")}


def _sql_rows(cfg: Config, id_by_iri: dict[str, str]) -> list[dict[str, Any]]:
    """业务号 → SQL 原始行的坐标。链的最后一环，也是最容易被省掉的一环。"""
    if not id_by_iri:
        return []
    from ..db.engine import onto_conn

    iri_by_id = {v: k for k, v in id_by_iri.items()}
    ids = list(iri_by_id)
    out: list[dict[str, Any]] = []
    with onto_conn(cfg) as conn:
        for table, pk_col, kind in FACT_TABLES:
            for r in conn.fetchall(
                    f"SELECT * FROM diabetes.{table} WHERE {pk_col} = ANY(%s)", (ids,)):
                out.append({
                    "kind": kind, "iri": iri_by_id.get(r[pk_col]), "id": r[pk_col],
                    "sqlRow": {"table": r["source_table"], "pk": r["source_pk"]},
                    "projectedInto": f"diabetes.{table}",
                    "factOrigin": r.get("fact_origin"),
                    "trustLevel": r.get("trust_level"),
                    "row": {k: v for k, v in r.items()
                            if k not in ("source_table", "source_pk")},
                })
    return out


def trace(cfg: Config, iri: str) -> dict[str, Any]:
    from .client import GraphDBClient
    from .passages import load as load_passages

    iri = _iri_ok(iri)
    client = GraphDBClient(cfg)

    # 反例夹具里的结论也是「结论」，溯源它只会得到一条走得通、但全错的链。
    # 与 /graph/node 同一条口径：拒绝并说明，不悄悄过滤。
    _guard_fixture(iri, client.sparql_csv(_Q_GRAPHS.format(iri=iri)))

    asserted = [r["t"] for r in client.sparql_csv(_Q_ASSERTED_TYPES.format(iri=iri))]
    short = {_short(t).removeprefix("dmo:") for t in asserted}
    kind = next((k for k in KINDS if k in short), None)
    if kind is None:
        return {
            "iri": iri, "kind": None, "chain": [], "evidence": [],
            "emptyReason": (
                f"{iri} 不是可溯源的结论节点。断言的类型是 "
                f"{'、'.join(sorted(short)) or '（无 —— 这个 IRI 在图里可能不存在）'}，"
                f"可溯源的是：{'、'.join(KINDS)}。"
                "⚠️ 别拿 `?x a dmo:Assessment` 去找结论 —— owl2-rl 的 prp-dom 会把每条"
                "患者命中记录也判成 Assessment。用 GET /graph/node?iri=… 看断言类型。"),
            "nextHops": [{"rel": "node", "endpoint": f"GET /graph/node?iri={iri}",
                          "why": "先看这个节点到底是什么"}],
        }

    handler = {
        "Assessment": _trace_assessment,
        "Diagnosis": _trace_diagnosis,
        "RiskFactorHit": _trace_risk_hit,
        "ContraindicationFlag": _trace_flag,
        "RiskStratification": _trace_stratification,
    }[kind]
    chain, passage_iris, fact_iris, broken, patient = handler(client, iri)

    pidx = load_passages(cfg)
    by_iri = {p.iri: p for p in pidx.passages}
    evidence = []
    for p_iri in passage_iris:
        p = by_iri.get(p_iri)
        if p is None:
            broken.append({
                "at": "SourcePassage", "iri": p_iri,
                "why": "引用了一条不在 urn:dmo:seed 里的出处 —— 无法逐字核验。"})
            continue
        evidence.append({"quote": p.quote, "sha256": p.content_hash,
                         "passageId": p.passage_id, "sourceId": p.source_id,
                         "supports": kind})
        chain.append({"role": "citesPassage", "kind": "SourcePassage", "iri": p.iri,
                      "detail": {"passageId": p.passage_id, "quote": p.quote,
                                 "sha256": p.content_hash, "locator": p.locator,
                                 "sourceId": p.source_id}})

    id_by_iri = _fact_ids(client, fact_iris)
    unresolved = [f for f in fact_iris if f not in id_by_iri]
    broken += [{"at": "factId", "iri": f,
                "why": "这个事实在真实患者图里没有业务号（dmo:*Id）—— "
                       "它可能只存在于知识侧或反例夹具，回查不到 SQL 行。"}
               for f in unresolved]

    sql = _sql_rows(cfg, id_by_iri)
    for s in sql:
        chain.append({"role": "sqlRow", "kind": s["kind"], "iri": s["iri"],
                      "detail": {"factId": s["id"],
                                 "projectedInto": s["projectedInto"],
                                 "sqlRow": s["sqlRow"],
                                 "factOrigin": s["factOrigin"],
                                 "trustLevel": s["trustLevel"]}})
    broken += [{"at": "sqlRow", "iri": iri,
                "why": f"图里有业务号 {fid}，但 core_* 里回查不到对应行 —— "
                       "多半是同步之后 SQL 侧被重建过，两侧不同步。"}
               for iri, fid in id_by_iri.items()
               if fid not in {s["id"] for s in sql}]

    # 已经有更具体的出处断链说明时不再补一句泛泛的 —— 两条并列只会稀释真正的原因。
    if not evidence and not any(b["at"] == "SourcePassage" for b in broken):
        broken.append({
            "at": "SourcePassage", "iri": None,
            "why": "这条结论的链上没有任何可逐字引用的出处，"
                   "无法用 /adjudicate/citations 核验。"
                   + ("无出处的风险规则产出 Hit 但不计入 tier，"
                      "见 51-risk-stratification.rq 信号 5。"
                      if kind in ("RiskFactorHit", "RiskStratification") else "")})

    return {
        "iri": iri,
        "kind": kind,
        "assertedTypes": sorted(short),
        "patient": patient,
        "chain": [dict(c, step=i + 1) for i, c in enumerate(chain)],
        "evidence": evidence,
        "sqlRows": sql,
        # 断链与走通的环节同等重要 —— 只报走通的那部分是在暗示「有出处」
        "brokenLinks": broken or None,
        "graphVersion": pidx.graph_version,
        "nextHops": (
            [{"rel": "adjudicate", "endpoint": "POST /adjudicate/citations",
              "why": "拿链上的 quote / sha256 核对外部结论的引用"}]
            + ([{"rel": "patient", "endpoint": f"GET /patients/{patient['patientId']}",
                 "why": "这个患者的完整返回体"}] if patient else [])),
        "disclaimer": _disclaimer(),
    }


def _disclaimer() -> str:
    from ..query.hybrid import DISCLAIMER

    return DISCLAIMER


def _patient(rows: list[dict[str, str]]) -> dict[str, str] | None:
    pid = _first(rows, "pid")
    return {"patientId": pid} if pid else None


def _trace_assessment(client, iri):
    from ..query.hybrid import _interval

    rows = client.sparql_csv(_Q_ASSESSMENT.format(iri=iri))
    if not rows:
        return [], [], [], [{"at": "Assessment", "iri": iri,
                             "why": "断言成 Assessment，但取不到 conclusion。"}], None
    r = rows[0]
    chain = [{"role": "conclusion", "kind": "Assessment", "iri": iri, "detail": {
        "conclusion": r.get("conclusion"), "ruleId": r.get("ruleId"),
        "ruleVersion": r.get("ruleVersion"), "applicableContext": r.get("context"),
        "caveat": r.get("caveat") or None}}]
    broken = []
    th = _first(rows, "th")
    if th:
        chain.append({"role": "appliesThreshold", "kind": "DiagnosticThreshold",
                      "iri": th, "detail": {
                          "thresholdId": _first(rows, "thresholdId"),
                          "interval": _interval({
                              "lo": r.get("lo"), "loOp": r.get("loOp"),
                              "up": r.get("up"), "upOp": r.get("upOp"),
                              "boundUnit": r.get("boundUnit") or ""}),
                          # 单次落在区间内 ≠ 确诊。这一句必须在链上出现。
                          "confirmationRequired": _first(rows, "confirm") == "true"}})
    else:
        broken.append({"at": "DiagnosticThreshold", "iri": None,
                       "why": "这条 Assessment 没挂 appliesThreshold，无法追到阈值与出处。"})
    res = _first(rows, "res")
    if res:
        chain.append({"role": "basedOnLabResult", "kind": "LabResult", "iri": res,
                      "detail": {"value": r.get("resultValue"), "unit": r.get("resultUnit"),
                                 "collectedAt": r.get("collectedAt") or None}})
    return chain, _distinct(rows, "psg"), ([res] if res else []), broken, _patient(rows)


def _trace_diagnosis(client, iri):
    rows = client.sparql_csv(_Q_DIAGNOSIS.format(iri=iri))
    if not rows:
        return [], [], [], [{"at": "Diagnosis", "iri": iri,
                             "why": "断言成 Diagnosis，但取不到 diagnosisKind。"}], None
    r = rows[0]
    verification = r.get("verification")
    chain = [{"role": "conclusion", "kind": "Diagnosis", "iri": iri, "detail": {
        "diagnosisKind": r.get("kind"), "verificationStatus": verification,
        "clinicalStatus": r.get("status"), "factOrigin": r.get("origin"),
        "externalCode": r.get("code") or None, "caveat": r.get("caveat") or None,
        "note": ("Provisional ≠ 确诊：所用诊断切点 confirmationRequired=true 而采样日不足两天，"
                 "见 30-diagnosis-from-assessment.rq。"
                 if verification == "Provisional" else None)}}]
    broken = []
    supports = _distinct(rows, "support")
    for sup in supports:
        srow = next(x for x in rows if x.get("support") == sup)
        chain.append({"role": "supportedBy", "kind": "Assessment", "iri": sup,
                      "detail": {"conclusion": srow.get("supportConclusion"),
                                 "thresholdId": srow.get("supportThresholdId"),
                                 "traceFurther": f"GET /graph/provenance?iri={sup}"}})
    if not supports:
        broken.append({"at": "Assessment", "iri": None,
                       "why": "没有 Assessment 通过 supportsDiagnosis 支撑它 —— "
                              "多半是上游直接断言的诊断（factOrigin=ehr-legacy），"
                              "不是本系统推出来的。"})
    # 用节点 IRI —— 业务号由 _fact_ids() 从图里翻，不在这里手拼。
    return chain, [], [iri], broken, _patient(rows)


def _trace_risk_hit(client, iri):
    rows = client.sparql_csv(_Q_RISK_HIT.format(iri=iri))
    if not rows:
        return [], [], [], [{"at": "RiskFactorHit", "iri": iri,
                             "why": "断言成 RiskFactorHit，但取不到 hitsRiskRule。"}], None
    r = rows[0]
    psgs = _distinct(rows, "psg")
    chain = [
        {"role": "conclusion", "kind": "RiskFactorHit", "iri": iri, "detail": {
            "triggerBasis": r.get("basis"),
            # 命中 ≠ 参与判定
            "countsInTier": bool(psgs),
            "note": None if psgs else
            "这条规则没有可逐字引用的出处，产出 Hit 但**不计入 tier**"
            "（51-risk-stratification.rq 信号 5）。"}},
        {"role": "hitsRiskRule", "kind": "RiskRule", "iri": r["rule"], "detail": {
            "riskRuleId": _first(rows, "riskRuleId"),
            "label": _first(rows, "ruleLabel"),
            "externalStandardNote": _first(rows, "externalNote")}},
    ]
    rf = _first(rows, "riskFactor")
    if rf:
        chain.append({"role": "hitRiskFactor", "kind": "RiskFactor", "iri": rf,
                      "detail": {"label": _first(rows, "riskFactorLabel"),
                                 "riskCategory": _first(rows, "category")}})
    return chain, psgs, _distinct(rows, "fact"), [], _patient(rows)


def _trace_flag(client, iri):
    rows = client.sparql_csv(_Q_FLAG.format(iri=iri))
    if not rows:
        return [], [], [], [{"at": "ContraindicationFlag", "iri": iri,
                             "why": "断言成 ContraindicationFlag，但取不到 flagSeverity。"}], None
    r = rows[0]
    chain = [{"role": "conclusion", "kind": "ContraindicationFlag", "iri": iri, "detail": {
        "severity": r.get("severity"), "rationale": r.get("rationale"),
        # 本仓库任何路径都不输出剂量，禁忌只到三级信号
        "note": "只给信号级别与原文依据，不给任何用药剂量或替代方案。"}}]
    mu = _first(rows, "mu")
    if mu:
        chain.append({"role": "flagMedicationUse", "kind": "MedicationUse", "iri": mu,
                      "detail": {"medication": _first(rows, "medLabel"),
                                 "medicationIri": _first(rows, "med")}})
    cond = _first(rows, "cond")
    if cond:
        chain.append({"role": "flagCondition", "kind": "Condition", "iri": cond,
                      "detail": {"label": _first(rows, "condLabel")}})
    broken = [{"at": "SourcePassage", "iri": None,
               "why": "禁忌的 rationale 是抽取产物里的 evidenceQuote 字符串，"
                      "不是带 contentHash 的 SourcePassage —— 无法用 "
                      "/adjudicate/citations 逐字核验。"}]
    return chain, [], [mu] if mu else [], broken, _patient(rows)


def _trace_stratification(client, iri):
    rows = client.sparql_csv(_Q_STRATIFICATION.format(iri=iri))
    if not rows:
        return [], [], [], [{"at": "RiskStratification", "iri": iri,
                             "why": "断言成 RiskStratification，但取不到 riskTier。"}], None
    r = rows[0]
    chain = [{"role": "conclusion", "kind": "RiskStratification", "iri": iri, "detail": {
        "tier": r.get("tier"), "ruleId": r.get("ruleId"),
        "ruleVersion": r.get("ruleVersion"),
        "insufficientReason": r.get("reason") or None,
        "monitoringGap": r.get("gap") or None, "caveat": r.get("caveat") or None,
        # 这一句在返回体里必须出现，不能靠调用方自己记住
        "note": "规则式定性分层，tier 是有序枚举，不是分数；不含概率、不含时间窗。"}}]
    chain += [{"role": "hasRiskFactorHit", "kind": "RiskFactorHit", "iri": h,
               "detail": {"traceFurther": f"GET /graph/provenance?iri={h}"}}
              for h in _distinct(rows, "hit")]
    return chain, [], [], [], _patient(rows)


__all__ = ["ExploreError", "trace"]
