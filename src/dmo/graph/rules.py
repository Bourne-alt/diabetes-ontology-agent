"""规则内省 —— 让调用方（尤其是智能体）**先读懂规则，再决定查什么**。

`/patients/{pid}/assessment` 回答「这个患者判成什么」，本模块回答「判定是按什么判的、
哪些规则根本判不了、哪些命中了也不计分」。后者是自主规划的前提：不知道有哪些规则，
agent 只能把问题瞎试一遍。

## ⚠️ `?r a dmo:RiskRule` 会查出 73 条，其中只有 12 条是规则

这是本模块存在的最强理由，也是 owl2-rl 最容易坑人的一脚。

`dmo:triggerBasis` 的 `rdfs:domain` 是 `dmo:RiskRule`（dmo-risk-map.ttl:98），而
`50-risk-factor-hit.rq` 产出的每个 `RiskFactorHit` 都带 `dmo:triggerBasis`。
OWL-RL 的 **prp-dom** 规则于是顺着 domain 反推：**每个患者命中记录都被判定成一条
「风险规则」**。同理 `dmo:ruleId` 的 domain 是 `dmo:Assessment`，这些 Hit 又同时
是 Assessment（`?a a dmo:Assessment` 当前查出 143 条，同样掺了 Hit）。

    ?r a dmo:RiskRule                  → 73 条（12 条真规则 + 61 条患者命中记录）
    ?r a dmo:RiskRule ; dmo:riskRuleId → 12 条  ← 真正被规则链消费的

dmo-risk-map.ttl:75-81 早就用注释记下了这个现象。它不报错、不告警，
查询照常返回，只是数字大了六倍 —— **正是本仓库最怕的那类失败**。
所以本模块一律以 `dmo:riskRuleId` 这个声明标记为准，不以 `rdf:type` 为准，
并把 73 与 12 的差额当作一等公民报进 `counts`：agent 自己写 SPARQL 时
八成会踩这一脚，返回体里说破它比事后解释便宜得多。

## 其余两个落差

    DiagnosticThreshold   17 条，17 条可执行（以 dmo:thresholdId 为准，同样不看 rdf:type）
    GlycemicTarget        10 条，出处只是 rdfs:comment 里的原文串，**不是可核验的 SourcePassage**
    RiskRule              12 条声明 → 12 条可执行 → 10 条计入 tier

12 → 10 是因为 `51-risk-stratification.rq` 只数有 `riskRuleCitesPassage` 的规则
（该文件 §信号 5）：拿不出逐字出处的规则产出 Hit 但不计入 tier。

## 为什么读图不读 `map_risk_rule`

SQL 里那份投影是 `terms/resolve.py` 为解释用途做的，只收得下可执行的那 12 条，
看不到类断言与声明的落差；而落差恰恰是本模块要报的东西。图才是判定的权威来源。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import Config

PREFIXES = """
PREFIX dmo:  <https://example.org/dmo#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""

# 知识侧一律不写 GRAPH —— 写了就吃不到 owl2-rl 物化边，静默少返。
_Q_THRESHOLDS = PREFIXES + """
SELECT ?iri ?ruleId ?classification ?context ?boundUnit ?lo ?loOp ?up ?upOp
       ?confirm ?testCode ?testLabel ?psgId ?sourceId
WHERE {
  ?iri a dmo:DiagnosticThreshold ; dmo:thresholdId ?ruleId .
  OPTIONAL { ?iri dmo:classification ?classification }
  OPTIONAL { ?iri dmo:populationContext ?context }
  OPTIONAL { ?iri dmo:boundUnit ?boundUnit }
  OPTIONAL { ?iri dmo:lowerBound ?lo }   OPTIONAL { ?iri dmo:lowerOperator ?loOp }
  OPTIONAL { ?iri dmo:upperBound ?up }   OPTIONAL { ?iri dmo:upperOperator ?upOp }
  OPTIONAL { ?iri dmo:confirmationRequired ?confirm }
  OPTIONAL { ?test dmo:hasThreshold ?iri .
             OPTIONAL { ?test dmo:labTestCode ?testCode }
             OPTIONAL { ?test rdfs:label ?testLabel } }
  OPTIONAL { ?iri dmo:thresholdCitesPassage ?psg . ?psg dmo:passageId ?psgId }
  OPTIONAL { ?iri dmo:thresholdCitedFrom ?src . ?src dmo:sourceId ?sourceId }
}
"""

_Q_TARGETS = PREFIXES + """
SELECT ?iri ?ruleId ?metric ?up ?boundUnit ?population ?context ?testCode ?comment
WHERE {
  ?iri a dmo:GlycemicTarget ; dmo:targetId ?ruleId .
  OPTIONAL { ?iri dmo:targetMetric ?metric }
  OPTIONAL { ?iri dmo:targetHigh ?up }
  OPTIONAL { ?iri dmo:targetUnit ?boundUnit }
  OPTIONAL { ?iri dmo:targetPopulation ?population }
  OPTIONAL { ?iri dmo:targetPopulationContext ?context }
  OPTIONAL { ?iri rdfs:comment ?comment }
  OPTIONAL { ?iri dmo:targetMeasuredBy ?test . OPTIONAL { ?test dmo:labTestCode ?testCode } }
}
"""

# ⚠️ 不按规则 GROUP BY 再 SAMPLE（`terms/resolve.py` 那样）—— 这里要的正是全部取值：
# 抽取个体在多个 extract 图里各有一份 label，SAMPLE 掉就看不出规则来自哪儿。
# 行的笛卡尔积在 Python 里按 iri 收敛。
_Q_RISK_RULES = PREFIXES + """
SELECT ?iri ?ruleId ?label ?observedKind ?observedCode ?matchValue
       ?lo ?loOp ?up ?upOp ?basis ?externalNote
       ?riskFactor ?riskFactorLabel ?riskCategory ?psgId
WHERE {
  # 以 riskRuleId 这个**声明标记**为准。写 `?iri a dmo:RiskRule` 会连
  # owl2-rl 从 triggerBasis 的 domain 反推出来的 61 条患者命中记录一起捞进来。
  ?iri a dmo:RiskRule ; dmo:riskRuleId ?ruleId .
  OPTIONAL { ?iri rdfs:label ?label }
  OPTIONAL { ?iri dmo:observedKind ?observedKind }
  OPTIONAL { ?iri dmo:observedCode ?observedCode }
  OPTIONAL { ?iri dmo:matchValue ?matchValue }
  OPTIONAL { ?iri dmo:ruleLowerBound ?lo }  OPTIONAL { ?iri dmo:ruleLowerOperator ?loOp }
  OPTIONAL { ?iri dmo:ruleUpperBound ?up }  OPTIONAL { ?iri dmo:ruleUpperOperator ?upOp }
  OPTIONAL { ?iri dmo:triggerBasis ?basis }
  OPTIONAL { ?iri dmo:externalStandardNote ?externalNote }
  OPTIONAL { ?iri dmo:mapsToRiskFactor ?riskFactor .
             OPTIONAL { ?riskFactor rdfs:label ?riskFactorLabel }
             OPTIONAL { ?riskFactor dmo:riskCategory ?riskCategory } }
  OPTIONAL { ?iri dmo:riskRuleCitesPassage ?psg . ?psg dmo:passageId ?psgId }
}
"""


# 专门用来量化 prp-dom 污染。这个数字要如实报出去，不是内部调试用的。
_Q_RISK_CLASS_ASSERTIONS = PREFIXES + """
SELECT (COUNT(DISTINCT ?any) AS ?classAssertions) (COUNT(DISTINCT ?hit) AS ?alsoRiskFactorHit)
WHERE {
  { ?any a dmo:RiskRule }
  UNION { ?hit a dmo:RiskRule , dmo:RiskFactorHit }
}
"""


@dataclass
class Rule:
    kind: str                     # threshold | target | risk
    iri: str
    rule_id: str | None
    label: str | None
    fields: dict[str, Any]
    passage_ids: list[str] = field(default_factory=list)
    consumed_by: tuple[str, ...] = ()
    executable: bool = False
    counts_in_tier: bool | None = None   # 只有 risk 有意义
    not_executable_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "kind": self.kind,
            "iri": self.iri,
            "ruleId": self.rule_id,
            "label": self.label,
            "executable": self.executable,
            "notExecutableReason": self.not_executable_reason,
            "consumedBy": list(self.consumed_by),
            "citesPassages": self.passage_ids,
            **self.fields,
        }
        if self.counts_in_tier is not None:
            out["countsInTier"] = self.counts_in_tier
        return out


@dataclass
class RuleIndex:
    rules: list[Rule]
    by_id: dict[str, Rule]
    graph_version: str
    risk_class_assertions: int = 0
    risk_inference_artifacts: int = 0


def _interval(lo: str | None, lo_op: str | None, up: str | None,
              up_op: str | None, unit: str | None) -> str | None:
    """复用 hybrid 的区间还原 —— 同一件事不允许有第二份定义。

    ⚠️ 只补一件 hybrid 不需要管的事：**风险规则的两个 operator 都是 OPTIONAL**
    （`50-risk-factor-hit.rq` 用 `!BOUND(?loOp) || ?loOp = "None"` 判定），
    而阈值的 lowerOperator/upperOperator 是必填。缺失即无界，不补上会渲染成
    `[35, )` 这种半截区间 —— 看着像数据坏了，其实是「35 岁及以上」。
    """
    from ..query.hybrid import _interval as render

    if not lo_op and not up_op:
        return None
    return render({"lo": lo, "loOp": lo_op or "None", "up": up,
                   "upOp": up_op or "None", "boundUnit": unit or ""})


def _add(seq: list[str], v: str | None) -> None:
    if v and v not in seq:
        seq.append(v)


_CACHE: tuple[str, RuleIndex] | None = None


def load(cfg: Config, *, refresh: bool = False) -> RuleIndex:
    global _CACHE
    from ..terms.concepts import graph_version
    from .client import GraphDBClient

    version = graph_version()
    if not refresh and _CACHE is not None and _CACHE[0] == version:
        return _CACHE[1]

    client = GraphDBClient(cfg)
    rules: dict[str, Rule] = {}

    for r in client.sparql_csv(_Q_THRESHOLDS):
        iri = r["iri"]
        rule = rules.get(iri)
        if rule is None:
            rule = Rule(
                kind="threshold", iri=iri, rule_id=r.get("ruleId") or None,
                label=r.get("classification") or None,
                fields={
                    "classification": r.get("classification") or None,
                    "populationContext": r.get("context") or None,
                    "interval": _interval(r.get("lo"), r.get("loOp"), r.get("up"),
                                          r.get("upOp"), r.get("boundUnit")),
                    "boundUnit": r.get("boundUnit") or None,
                    # 诊断级切点：单次落在区间内 ≠ 确诊，见 30-diagnosis-from-assessment.rq
                    "confirmationRequired": (r.get("confirm") or "") == "true",
                    "measuredByTest": [],
                    "citedFromSources": [],
                },
                consumed_by=("20-lab-assessment.rq", "30-diagnosis-from-assessment.rq"),
            )
            rules[iri] = rule
        _add(rule.fields["measuredByTest"], r.get("testCode") or r.get("testLabel"))
        _add(rule.fields["citedFromSources"], r.get("sourceId"))
        _add(rule.passage_ids, r.get("psgId"))

    for r in client.sparql_csv(_Q_TARGETS):
        iri = r["iri"]
        if iri in rules:
            continue
        rules[iri] = Rule(
            kind="target", iri=iri, rule_id=r.get("ruleId") or None,
            label=r.get("metric") or None,
            fields={
                "metric": r.get("metric") or None,
                "interval": _interval(None, "None", r.get("up"), "LT", r.get("boundUnit")),
                "boundUnit": r.get("boundUnit") or None,
                "population": r.get("population") or None,
                "populationContext": r.get("context") or None,
                "measuredByTest": [t for t in [r.get("testCode")] if t],
                # ⚠️ 管理目标的出处只是 rdfs:comment 里的原文串，没有 contentHash，
                #    /adjudicate/citations 核不了它。这一句必须出现在返回体里。
                "sourceComment": r.get("comment") or None,
                "citationCaveat": (
                    "管理目标的原文存在 rdfs:comment 里，不是 SourcePassage，"
                    "没有 contentHash，无法用 /adjudicate/citations 逐字核验。"),
            },
            consumed_by=("21-target-attainment.rq",),
            executable=True,
        )

    for r in client.sparql_csv(_Q_RISK_RULES):
        iri = r["iri"]
        rule = rules.get(iri)
        if rule is None:
            rule = Rule(
                kind="risk", iri=iri, rule_id=r.get("ruleId") or None,
                label=r.get("label") or None,
                fields={
                    "observedKind": r.get("observedKind") or None,
                    "observedCode": r.get("observedCode") or None,
                    "matchValue": r.get("matchValue") or None,
                    "interval": _interval(r.get("lo"), r.get("loOp"), r.get("up"),
                                          r.get("upOp"), None),
                    "triggerBasis": r.get("basis") or None,
                    # 数值边界不是本仓库语料说的时，这一句必须出现在返回体里
                    "externalStandardNote": r.get("externalNote") or None,
                    "riskFactor": r.get("riskFactor") or None,
                    "riskFactorLabels": [],
                    "riskCategories": [],
                },
                consumed_by=("50-risk-factor-hit.rq", "51-risk-stratification.rq"),
            )
            rules[iri] = rule
        _add(rule.fields["riskFactorLabels"], r.get("riskFactorLabel"))
        _add(rule.fields["riskCategories"], r.get("riskCategory"))
        _add(rule.passage_ids, r.get("psgId"))
        if r.get("riskFactor") and not rule.fields.get("riskFactor"):
            rule.fields["riskFactor"] = r["riskFactor"]

    for rule in rules.values():
        if rule.kind == "threshold":
            missing = [k for k in ("classification", "populationContext", "boundUnit")
                       if not rule.fields.get(k)]
            rule.executable = bool(rule.rule_id) and not missing and bool(
                rule.fields["measuredByTest"])
            if not rule.executable:
                rule.not_executable_reason = (
                    "20-lab-assessment.rq 要求 thresholdId + boundUnit + classification "
                    "+ populationContext + 上挂到某个 LabTest；缺："
                    + "、".join(missing or ["hasThreshold 到 LabTest 的边"]))
        elif rule.kind == "risk":
            missing = [k for k, v in (("observedKind", rule.fields["observedKind"]),
                                      ("triggerBasis", rule.fields["triggerBasis"]),
                                      ("mapsToRiskFactor", rule.fields["riskFactor"]))
                       if not v]
            rule.executable = not missing
            rule.counts_in_tier = rule.executable and bool(rule.passage_ids)
            if not rule.executable:
                rule.not_executable_reason = (
                    "声明了 riskRuleId，但 50-risk-factor-hit.rq 的 WHERE 匹配不上它，缺："
                    + "、".join(missing) + "。它存在于图里，但对判定没有任何影响。")
            elif not rule.counts_in_tier:
                rule.not_executable_reason = (
                    "可执行，但没有 riskRuleCitesPassage，"
                    "51-risk-stratification.rq 的信号 5 会把它过滤掉 —— 产出 Hit 但不计入 tier。")

    contamination = (client.sparql_csv(_Q_RISK_CLASS_ASSERTIONS) or [{}])[0]
    ordered = sorted(rules.values(), key=lambda r: (r.kind, r.rule_id or r.iri))
    index = RuleIndex(
        rules=ordered,
        by_id={r.rule_id: r for r in ordered if r.rule_id},
        graph_version=version,
        risk_class_assertions=int(contamination.get("classAssertions") or 0),
        risk_inference_artifacts=int(contamination.get("alsoRiskFactorHit") or 0),
    )
    _CACHE = (version, index)
    return index


def counts(index: RuleIndex) -> dict[str, Any]:
    """三个落差的汇总。藏起来就等于夸大覆盖面。"""
    out: dict[str, Any] = {}
    for kind in ("threshold", "target", "risk"):
        sub = [r for r in index.rules if r.kind == kind]
        entry: dict[str, Any] = {"total": len(sub),
                                 "executable": sum(1 for r in sub if r.executable)}
        if kind == "risk":
            entry["declared"] = entry.pop("total")
            entry["total"] = entry["declared"]
            entry["countsInTier"] = sum(1 for r in sub if r.counts_in_tier)
            # ★ 这三行是本模块最该被读到的东西
            entry["classAssertions"] = index.risk_class_assertions
            entry["inferenceArtifacts"] = index.risk_inference_artifacts
            entry["classAssertionCaveat"] = (
                f"`?r a dmo:RiskRule` 会查出 {index.risk_class_assertions} 条，"
                f"其中 {index.risk_inference_artifacts} 条是患者命中记录 —— "
                "owl2-rl 的 prp-dom 顺着 dmo:triggerBasis 的 rdfs:domain 反推出来的，"
                "不是规则。以 dmo:riskRuleId 为准。dmo:Assessment 同样被这样掺过。")
            entry["note"] = (
                "declared − countsInTier 的差额是拿不出逐字出处的规则："
                "产出 RiskFactorHit 但不计入 tier（51-risk-stratification.rq 信号 5）。")
        if kind == "target":
            entry["note"] = "管理目标回答「管得好不好」，与诊断切点回答的不是同一个问题。"
        out[kind] = entry
    return out


def search(cfg: Config, *, kind: str | None = None, q: str | None = None,
           executable: bool | None = None, counts_in_tier: bool | None = None,
           concept: str | None = None, context: str | None = None,
           limit: int = 50) -> dict[str, Any]:
    """规则检索。

    ⚠️ **计划里的 `GET /graph/thresholds` 合并到了这里**（`?kind=threshold&concept=&context=`）。
    单开一个端点意味着「按概念筛阈值」这件事有两份实现，而这个仓库不允许同一件事
    有两份定义 —— 阈值、管理目标、风险规则本来就共用同一份索引和同一套落差口径。
    """
    index = load(cfg)
    rows = index.rules
    applied: dict[str, Any] = {}

    if kind:
        if kind not in ("threshold", "target", "risk"):
            raise ValueError(f"kind 只能是 threshold / target / risk，收到 {kind!r}")
        applied["kind"] = kind
        rows = [r for r in rows if r.kind == kind]
    if executable is not None:
        applied["executable"] = executable
        rows = [r for r in rows if r.executable is executable]
    if counts_in_tier is not None:
        applied["countsInTier"] = counts_in_tier
        rows = [r for r in rows if bool(r.counts_in_tier) is counts_in_tier]
    if concept:
        # 按检验项/指标筛：A1C、FPG、BloodPressure…
        applied["concept"] = concept
        needle = concept.strip().lower()
        rows = [r for r in rows
                if needle in " ".join(
                    str(v) for v in ((r.fields.get("measuredByTest") or [])
                                     + [r.fields.get("metric") or "",
                                        r.fields.get("observedKind") or ""])).lower()]
    if context:
        # 按人群语境筛：NonPregnant / Pregnant / Any。
        # 妊娠与非妊娠的切点不同，混用是最容易出错的一处（S04/S04b 专测这一条）。
        applied["context"] = context
        rows = [r for r in rows
                if (r.fields.get("populationContext") or "").lower() == context.lower()]
    if q:
        applied["q"] = q
        needle = q.strip().lower()
        rows = [r for r in rows
                if needle in " ".join(
                    str(v) for v in (r.rule_id, r.label, r.iri,
                                     *r.fields.values())).lower()]

    limit = max(1, min(limit, 200))
    total = len(rows)
    return {
        "rules": [r.as_dict() for r in rows[:limit]],
        "total": total,
        "limit": limit,
        "filters": applied or None,
        "counts": counts(index),
        "emptyReason": _empty_reason(index, applied) if total == 0 else None,
        "nextHops": [
            {"rel": "passages", "endpoint": "GET /graph/passages?citedBy={ruleId}",
             "why": "取这条规则引用的逐字出处"},
            {"rel": "adjudicate", "endpoint": "POST /adjudicate/citations",
             "why": "核对别人引用这些出处时有没有改写"},
            {"rel": "scope", "endpoint": "GET /adjudicate/scope",
             "why": "这些规则对应的可裁决范围"},
        ],
        "graphVersion": index.graph_version,
    }


def get(cfg: Config, rule_id: str) -> dict[str, Any]:
    """单条规则全貌，出处展开成完整 passage（含 quote 与 sha256）。"""
    index = load(cfg)
    rule = index.by_id.get(rule_id)
    if rule is None:
        raise KeyError(rule_id)

    from . import passages as passages_mod

    pidx = passages_mod.load(cfg)
    return {
        "rule": rule.as_dict(),
        "passages": [pidx.by_id[p].as_dict() for p in rule.passage_ids
                     if p in pidx.by_id],
        "nextHops": [
            {"rel": "adjudicate", "endpoint": "POST /adjudicate/citations",
             "why": "把这些 quote / sha256 拿去核对外部结论的引用"},
        ],
        "graphVersion": index.graph_version,
    }


def _empty_reason(index: RuleIndex, applied: dict[str, Any]) -> str:
    c = counts(index)
    if applied.get("countsInTier") is True:
        return (f"没有符合条件的计分规则。全库只有 {c['risk']['countsInTier']} 条风险规则"
                "有逐字出处、真正计入 tier。")
    if applied.get("executable") is True:
        return ("没有符合条件的可执行规则。可执行的定义是「规则链的 WHERE 真的匹配得上」，"
                f"当前：阈值 {c['threshold']['executable']} 条、"
                f"风险规则 {c['risk']['executable']} 条。")
    return ("没有匹配的规则。检索走朴素子串，不做模糊匹配 —— "
            "先用 GET /graph/rules?kind=risk 看全量清单再筛。")
