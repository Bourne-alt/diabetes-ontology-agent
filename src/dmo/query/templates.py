"""参数化 SPARQL 模板白名单。

**不让 LLM 自由写 SPARQL。** 三个理由，按严重程度排：

  1. 写错 GRAPH 子句会**静默少结果** —— 知识侧写 `GRAPH <urn:dmo:seed>` 就吃不到
     owl2-rl 的物化边，查询不报错，只是答案少一半。这类错误没法靠看输出发现。
  2. 患者侧不加 `STRSTARTS(?pg,"urn:dmo:patient:")` 会扫到 synthetic-patients
     那 6 例反例夹具 —— 它们是**故意造错的数据**。
  3. 全库扫描患者图（430 个）在 30 个患者的演示里看不出问题，上量就是灾难。

所以：`search_concept` 拿到准确 IRI → 套模板 → 参数用 VALUES 注入。
逃生口是 `raw_sparql`，带写操作黑名单 + 行数上限，且返回体会标注"未经模板校验"。

每个模板的 `{{patients}}` 会被替换成 `VALUES ?pat { <iri> <iri> … }`。
"""

from __future__ import annotations

from dataclasses import dataclass

PREFIXES = """
PREFIX dmo:  <https://example.org/dmo#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""

# 患者图前缀守卫。每个碰患者事实的模板都必须带上。
PG_GUARD = 'FILTER(STRSTARTS(STR(?pg), "urn:dmo:patient:"))'


@dataclass(frozen=True)
class Template:
    name: str
    description: str
    body: str
    """`{{patients}}` 是必填占位符。"""


def _t(name: str, desc: str, body: str) -> Template:
    return Template(name, desc, PREFIXES + body)


TEMPLATES: dict[str, Template] = {}


def register(t: Template) -> Template:
    TEMPLATES[t.name] = t
    return t


register(_t(
    "care_chain",
    "患者的 V2 全链：就诊 → 检验/观察 → 诊断 → 用药",
    """
SELECT ?pid ?kind ?node ?label ?value ?unit ?at WHERE {
  {{patients}}
  GRAPH ?pg { ?pat dmo:patientId ?pid }
  """ + PG_GUARD + """
  {
    GRAPH ?pg { ?pat dmo:hasEncounter ?node . ?node dmo:encounterDate ?at }
    OPTIONAL { GRAPH ?pg { ?node dmo:encounterType ?label } }
    BIND("Encounter" AS ?kind)
  } UNION {
    GRAPH ?pg { ?pat dmo:hasEncounter ?e . ?e dmo:producesLabResult ?node .
                ?node dmo:resultValue ?value ; dmo:resultUnit ?unit ;
                      dmo:measuredByTest ?test }
    OPTIONAL { GRAPH ?pg { ?node dmo:collectedAt ?at } }
    OPTIONAL { ?test dmo:labTestCode ?label }
    BIND("LabResult" AS ?kind)
  } UNION {
    GRAPH ?pg { ?pat dmo:hasClinicalObservation ?node .
                ?node dmo:observationType ?label ; dmo:observedAt ?at }
    OPTIONAL { GRAPH ?pg { ?node dmo:valueDecimal ?value } }
    OPTIONAL { GRAPH ?pg { ?node dmo:unitCode ?unit } }
    BIND("Observation" AS ?kind)
  } UNION {
    GRAPH ?pg { ?pat dmo:hasDiagnosis ?node . ?node dmo:diagnosisKind ?label }
    OPTIONAL { GRAPH ?pg { ?node dmo:diagnosedDate ?at } }
    BIND("Diagnosis" AS ?kind)
  } UNION {
    GRAPH ?pg { ?pat dmo:hasMedicationUse ?node }
    OPTIONAL { GRAPH ?pg { ?node dmo:startDate ?at } }
    OPTIONAL { GRAPH ?pg { ?node dmo:usesMedication ?med } ?med rdfs:label ?label }
    BIND("MedicationUse" AS ?kind)
  }
}
ORDER BY ?pid ?kind ?at
"""))

register(_t(
    "assessment_evidence",
    "阈值判定结论 + 所用阈值 + 逐字出处 + 内容哈希",
    """
SELECT ?pid ?conclusion ?ruleId ?ruleVersion ?context ?thresholdId
       ?lo ?loOp ?up ?upOp ?boundUnit ?confirm
       ?resultValue ?resultUnit ?sourceValue ?sourceUnit ?collectedAt
       ?quote ?sha256 ?caveat ?resultId
WHERE {
  {{patients}}
  GRAPH ?pg { ?pat dmo:patientId ?pid }
  """ + PG_GUARD + """
  ?pat dmo:hasAssessment ?a .
  ?a dmo:conclusion ?conclusion ; dmo:ruleId ?ruleId ; dmo:ruleVersion ?ruleVersion ;
     dmo:applicableContext ?context ; dmo:basedOnLabResult ?res .
  OPTIONAL { ?a dmo:caveat ?caveat }
  OPTIONAL { ?a dmo:appliesThreshold ?th .
             ?th dmo:thresholdId ?thresholdId ; dmo:boundUnit ?boundUnit ;
                 dmo:lowerOperator ?loOp ; dmo:upperOperator ?upOp ;
                 dmo:confirmationRequired ?confirm .
             OPTIONAL { ?th dmo:lowerBound ?lo }
             OPTIONAL { ?th dmo:upperBound ?up }
             OPTIONAL { ?th dmo:thresholdCitesPassage ?psg .
                        ?psg dmo:quote ?quote ; dmo:contentHash ?sha256 } }
  GRAPH ?pg { ?res dmo:labResultId ?resultId ;
                   dmo:resultValue ?resultValue ; dmo:resultUnit ?resultUnit .
              OPTIONAL { ?res dmo:sourceValue ?sourceValue }
              OPTIONAL { ?res dmo:sourceUnit ?sourceUnit }
              OPTIONAL { ?res dmo:collectedAt ?collectedAt } }
}
ORDER BY ?pid ?thresholdId
"""))

register(_t(
    "diagnosis_evidence",
    "诊断记录 + 是断言的还是推出来的 + 支撑它的评估",
    """
SELECT ?pid ?diagnosisId ?kind ?status ?verification ?origin ?code ?type ?caveat
       ?supportedBy ?supportConclusion ?supportRuleId ?supportRuleVersion
WHERE {
  {{patients}}
  GRAPH ?pg { ?pat dmo:patientId ?pid }
  """ + PG_GUARD + """
  ?pat dmo:hasDiagnosis ?dx .
  ?dx dmo:diagnosisKind ?kind ; dmo:verificationStatus ?verification .
  OPTIONAL { ?dx dmo:diagnosisId ?diagnosisId }
  OPTIONAL { ?dx dmo:clinicalStatus ?status }
  OPTIONAL { ?dx dmo:factOrigin ?origin }
  OPTIONAL { ?dx dmo:externalCode ?code }
  OPTIONAL { ?dx dmo:diagnosisType ?type }
  OPTIONAL { ?dx dmo:caveat ?caveat }
  # verificationStatus 是强结论，光给 conclusion 不够 —— 支撑它的 Assessment
  # 用的是哪条规则、哪个版本，必须跟着一起出来，否则调用方无从核验。
  OPTIONAL { ?supportedBy dmo:supportsDiagnosis ?dx ;
                          dmo:conclusion ?supportConclusion .
             OPTIONAL { ?supportedBy dmo:ruleId ?supportRuleId }
             OPTIONAL { ?supportedBy dmo:ruleVersion ?supportRuleVersion } }
}
ORDER BY ?pid ?diagnosisId
"""))

register(_t(
    "medication_safety",
    "用药安全信号：绝对禁忌 / 相对禁忌 / 需谨慎。⚠️ rationale 是抽取产物的裸字符串，"
    "**不是可逐字核验的出处**（无 contentHash，/adjudicate/citations 核不了）",
    """
SELECT ?pid ?severity ?rationale ?medication ?drugClass ?condition ?muStatus
WHERE {
  {{patients}}
  GRAPH ?pg { ?pat dmo:patientId ?pid }
  """ + PG_GUARD + """
  ?pat dmo:hasContraindicationFlag ?f .
  ?f dmo:flagSeverity ?severity ; dmo:rationale ?rationale ;
     dmo:flagMedicationUse ?mu ; dmo:flagCondition ?cond .
  GRAPH ?pg { ?mu dmo:usesMedication ?med . OPTIONAL { ?mu dmo:status ?muStatus } }
  OPTIONAL { ?med rdfs:label ?medication }
  OPTIONAL { ?med dmo:belongsToDrugClass ?cls . ?cls rdfs:label ?drugClass }
  OPTIONAL { ?cond rdfs:label ?condition }
}
ORDER BY ?pid ?severity
"""))

register(_t(
    "risk_stratification",
    "风险分层结论 + 每个参与判定的因子及其出处",
    """
SELECT ?pid ?tier ?ruleId ?ruleVersion ?reason ?gap ?caveat
       ?factorRule ?factorLabel ?category ?basis ?quote ?sha256 ?externalNote ?counted
WHERE {
  {{patients}}
  GRAPH ?pg { ?pat dmo:patientId ?pid }
  """ + PG_GUARD + """
  ?pat dmo:hasRiskStratification ?s .
  ?s dmo:riskTier ?tier ; dmo:ruleId ?ruleId ; dmo:ruleVersion ?ruleVersion ;
     dmo:caveat ?caveat .
  OPTIONAL { ?s dmo:insufficientReason ?reason }
  OPTIONAL { ?s dmo:monitoringGap ?gap }
  OPTIONAL {
    ?pat dmo:hasRiskFactorHit ?h .
    ?h dmo:hitsRiskRule ?r ; dmo:hitRiskFactor ?rf ; dmo:triggerBasis ?basis .
    ?r dmo:riskRuleId ?factorRule .
    OPTIONAL { ?rf rdfs:label ?factorLabel }
    OPTIONAL { ?rf dmo:riskCategory ?category }
    OPTIONAL { ?r dmo:externalStandardNote ?externalNote }
    OPTIONAL { ?r dmo:riskRuleCitesPassage ?p .
               ?p dmo:quote ?quote ; dmo:contentHash ?sha256 }
    BIND(EXISTS { ?r dmo:riskRuleCitesPassage ?any } AS ?counted)
  }
}
ORDER BY ?pid ?factorRule
"""))

register(_t(
    "latest_lab_result",
    "每个患者每个检验项目的最新一次结果",
    """
SELECT ?pid ?testCode ?value ?unit ?at WHERE {
  {
    SELECT ?pat ?test (MAX(?t) AS ?at) WHERE {
      {{patients}}
      GRAPH ?pg { ?pat dmo:hasEncounter ?e . ?e dmo:producesLabResult ?r .
                  ?r dmo:collectedAt ?t ; dmo:measuredByTest ?test }
      """ + PG_GUARD + """
    }
    GROUP BY ?pat ?test
  }
  GRAPH ?pg2 { ?pat dmo:patientId ?pid ; dmo:hasEncounter ?e2 .
               ?e2 dmo:producesLabResult ?res .
               ?res dmo:collectedAt ?at ; dmo:resultValue ?value ;
                    dmo:resultUnit ?unit ; dmo:measuredByTest ?test }
  FILTER(STRSTARTS(STR(?pg2), "urn:dmo:patient:"))
  OPTIONAL { ?test dmo:labTestCode ?testCode }
}
ORDER BY ?pid ?testCode
"""))


register(_t(
    "recommendation_match",
    "患者诊断命中的指南推荐条目 + 命中路径 + 该推荐的原文出处。"
    "⚠️ **不排序**：语料的 gradingSystem 跨五套互不可比的体系（VA-DoD / KDIGO / ADA / "
    "GRADE / NICE），且 2615 条里 555 条未标注。按 recommendationType 分组由人取舍",
    """
SELECT ?pid ?via ?verification ?recType ?strength ?grade ?gradingSystem
       ?scope ?statement ?quote ?src WHERE {
  {{patients}}
  GRAPH ?pg { ?pat dmo:patientId ?pid }
  """ + PG_GUARD + """
  ?pat dmo:hasRecommendationMatch ?m .
  ?m dmo:matchesRecommendation ?rec ;
     dmo:matchVia ?via ;
     dmo:matchVerification ?verification .
  OPTIONAL { ?rec dmo:recommendationType     ?recType }
  OPTIONAL { ?rec dmo:recommendationStrength ?strength }
  OPTIONAL { ?rec dmo:nativeEvidenceGrade    ?grade }
  OPTIONAL { ?rec dmo:gradingSystem          ?gradingSystem }
  OPTIONAL { ?rec dmo:populationScope        ?scope }
  OPTIONAL { ?rec dmo:statement              ?statement }
  OPTIONAL { ?rec dmo:evidenceQuote          ?quote }
  OPTIONAL { ?rec <http://www.w3.org/ns/prov#wasDerivedFrom> ?src }
}
ORDER BY ?pid ?recType
"""))


register(_t(
    "monitoring_due",
    "按指南频率推出的下次检验到期日。"
    "⚠️ 三种 dueStatus 含义不同，**不要合并成一个告警**："
    "scheduled=有末次记录、算得出到期日；never-recorded=从没做过（不是逾期）；"
    "frequency-unusable=语料没写频率（181 条监测计划里有 77 条如此）。"
    "逾期天数不在图里，由调用方拿 dueNextDueAt 与当前时刻相减 —— "
    "那是查询时刻的算术，物化进图第二天就是错的",
    """
SELECT ?pid ?testLabel ?freqMonths ?dueStatus ?lastCollectedAt ?nextDueAt
       ?recLabel ?scope ?quote WHERE {
  {{patients}}
  GRAPH ?pg { ?pat dmo:patientId ?pid }
  """ + PG_GUARD + """
  ?pat dmo:hasMonitoringDue ?d .
  ?d dmo:dueForTest ?test ;
     dmo:dueFrequencyMonths ?freqMonths ;
     dmo:dueStatus ?dueStatus ;
     dmo:dueViaRecommendation ?rec .
  OPTIONAL { ?d dmo:dueLastCollectedAt ?lastCollectedAt }
  OPTIONAL { ?d dmo:dueNextDueAt       ?nextDueAt }
  OPTIONAL { ?test rdfs:label ?testLabel }
  OPTIONAL { ?rec  rdfs:label ?recLabel }
  OPTIONAL { ?rec  dmo:populationScope ?scope }
  OPTIONAL { ?rec  dmo:evidenceQuote   ?quote }
}
ORDER BY ?pid ?testLabel ?freqMonths
"""))


def render(name: str, patient_iris: list[str]) -> str:
    if name not in TEMPLATES:
        raise KeyError(
            f"没有模板 {name!r}。可用：{', '.join(sorted(TEMPLATES))}"
        )
    if not patient_iris:
        # 空 VALUES 在 SPARQL 里合法，但会静默返回空集 —— 和"这个患者没数据"
        # 长得一模一样。宁可当场报错。
        raise ValueError("患者集合为空。先用 SQL 收敛出患者，再套模板。")
    values = "VALUES ?pat { " + " ".join(f"<{i}>" for i in patient_iris) + " }"
    return TEMPLATES[name].body.replace("{{patients}}", values)
