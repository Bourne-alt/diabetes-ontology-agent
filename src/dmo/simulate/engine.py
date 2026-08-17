"""规则链执行与 before/after diff。

## 推断结果必须落在 default graph，不是 `urn:dmo:inferred`

这是移植 GraphDB 语义时最容易踩的一脚。规则的**知识侧刻意不写 GRAPH**
（rules/20 的 ⚠️ 第二条），在 GraphDB 里那是 default union graph，能同时看到
所有命名图与 owl2-rl 物化边；在 rdflib 的 Dataset 里，不带 GRAPH 的三元组模式
**只匹配 default graph**（`default_union` 默认关）。

所以 30 号规则的 `?pat dmo:hasAssessment ?a` 想读到 20 号规则的产出，
产出就必须进 default graph。放进名为 `urn:dmo:inferred` 的命名图的话，
规则链一条都串不起来 —— 而且不报错，只是 30/51 全部推出空集。

本轮推出了什么，用一个旁路 `Graph` 单独记账，不靠图名区分。

## 逐条物化，不能攒到最后

与 load_graphdb.run_rules 同一个理由：规则之间有依赖
（30 读 20 的产出，51 读 40/50 的产出）。攒到最后一起并入的话，
30 号看到的是空的推断集，首次跑必然空，且不报任何错。

## diff 为什么是结论级而不是三元组级

三元组级 diff 噪声压倒信号：Assessment 的 IRI 由
`SHA1(labResult|thresholdId|ruleVersion)` 铸成，注入一条假设检验就会多出
一整块三元组，diff 出来几十条，人读不出"结论变了没有"。

所以按语义键比对：Assessment 看 (conclusion, thresholdId)，
Diagnosis 看 (kind, verificationStatus)，分层看 tier，禁忌看 severity。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rdflib import Dataset, Graph

RULES_DIR = Path(__file__).resolve().parents[3] / "ontology" / "rules"


def rule_files(*, include_unreliable: bool = False) -> list[Path]:
    """按文件名序 —— 数字前缀就是依赖序（10→20→21→30→40→50→51）。

    `*-unreliable.rq` 默认不跑，与 load_graphdb 保持一致：它们处理
    valueTrustLevel="Unverified" 的上游随机值，结论强制 Indeterminate，
    跑了只会用 1300+ 条噪声结论淹没推演的 diff。
    """
    if not RULES_DIR.is_dir():
        raise FileNotFoundError(f"规则目录不存在：{RULES_DIR}")
    return [
        p for p in sorted(RULES_DIR.glob("*.rq"))
        if include_unreliable or not p.stem.endswith("-unreliable")
    ]


def rules_fingerprint(*, include_unreliable: bool = False) -> str:
    """规则集内容哈希。规则改一个字，derivationHash 就必须变。"""
    import hashlib

    h = hashlib.sha256()
    for p in rule_files(include_unreliable=include_unreliable):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def run_rules(ds: Dataset, *, include_unreliable: bool = False) -> Graph:
    """跑完整规则链，产出并入 ds 的 default graph，并返回本轮产出的旁路副本。"""
    produced = Graph()
    for rq in rule_files(include_unreliable=include_unreliable):
        try:
            result = ds.query(rq.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001 —— 要带上是哪条规则炸的
            raise RuntimeError(f"规则 {rq.name} 执行失败：{type(e).__name__}: {e}") from e
        for triple in result:
            # 逐条并入：后续规则必须看得见前序结果。
            ds.default_graph.add(triple)
            produced.add(triple)
    return produced


# ── 结论提取 ────────────────────────────────────────────────────────────
# 只查 default graph（推断结果所在），患者事实侧仍走 GRAPH ?pg。

_ASSESSMENT_Q = """
PREFIX dmo: <https://example.org/dmo#>
SELECT ?a ?conclusion ?tid ?ruleId ?ruleVersion ?ctx ?res ?value ?unit ?day ?hypo
WHERE {
  ?pat dmo:patientId ?pid ; dmo:hasAssessment ?a .
  ?a dmo:conclusion ?conclusion ; dmo:ruleId ?ruleId ;
     dmo:ruleVersion ?ruleVersion ; dmo:applicableContext ?ctx ;
     dmo:basedOnLabResult ?res ; dmo:appliesThreshold ?th .
  ?th dmo:thresholdId ?tid .
  GRAPH ?pg {
    ?res dmo:resultValue ?value ; dmo:resultUnit ?unit .
    OPTIONAL { ?res dmo:collectedAt ?t }
    OPTIONAL { ?res dmo:hypothetical ?hypo }
  }
  BIND(SUBSTR(STR(?t), 1, 10) AS ?day)
}
"""

_DIAGNOSIS_Q = """
PREFIX dmo: <https://example.org/dmo#>
SELECT ?dx ?kind ?status ?origin ?caveat WHERE {
  ?pat dmo:patientId ?pid ; dmo:hasDiagnosis ?dx .
  ?dx dmo:diagnosisKind ?kind ; dmo:verificationStatus ?status .
  OPTIONAL { ?dx dmo:factOrigin ?origin }
  OPTIONAL { ?dx dmo:caveat ?caveat }
}
"""

_RISK_Q = """
PREFIX dmo: <https://example.org/dmo#>
SELECT ?tier ?ruleId ?reason ?gap WHERE {
  ?pat dmo:patientId ?pid ; dmo:hasRiskStratification ?s .
  ?s dmo:riskTier ?tier ; dmo:ruleId ?ruleId .
  OPTIONAL { ?s dmo:insufficientReason ?reason }
  OPTIONAL { ?s dmo:monitoringGap ?gap }
}
"""

_SAFETY_Q = """
PREFIX dmo: <https://example.org/dmo#>
SELECT ?severity ?rationale ?med WHERE {
  ?pat dmo:patientId ?pid ; dmo:hasContraindicationFlag ?f .
  ?f dmo:flagSeverity ?severity ; dmo:rationale ?rationale ; dmo:flagMedicationUse ?mu .
  GRAPH ?pg { ?mu dmo:usesMedication ?med }
}
"""


def _s(v: Any) -> str | None:
    return None if v is None else str(v)


@dataclass
class Conclusions:
    """一轮规则跑完后的结论集。键是语义键，值是可读详情。"""

    assessments: dict[tuple, dict[str, Any]] = field(default_factory=dict)
    diagnoses: dict[tuple, dict[str, Any]] = field(default_factory=dict)
    risk: dict[tuple, dict[str, Any]] = field(default_factory=dict)
    safety: dict[tuple, dict[str, Any]] = field(default_factory=dict)

    def buckets(self) -> list[tuple[str, dict[tuple, dict[str, Any]]]]:
        return [
            ("Assessment", self.assessments),
            ("Diagnosis", self.diagnoses),
            ("RiskStratification", self.risk),
            ("ContraindicationFlag", self.safety),
        ]


def collect(ds: Dataset) -> Conclusions:
    out = Conclusions()

    for r in ds.query(_ASSESSMENT_Q):
        key = (_s(r.conclusion), _s(r.tid), _s(r.res))
        out.assessments[key] = {
            "conclusion": _s(r.conclusion),
            "thresholdId": _s(r.tid),
            "ruleId": _s(r.ruleId),
            "ruleVersion": _s(r.ruleVersion),
            "applicableContext": _s(r.ctx),
            "basedOnLabResult": _s(r.res),
            "value": _s(r.value),
            "unit": _s(r.unit),
            "collectedDate": _s(r.day),
            "fromHypothesis": bool(r.hypo),
            "assessmentIri": _s(r.a),
        }

    for r in ds.query(_DIAGNOSIS_Q):
        # 键刻意**不含 status**：Provisional→Confirmed 要显示成「变了」，
        # 而不是「消失一条、新增一条」。
        key = (_s(r.kind), _s(r.dx))
        out.diagnoses[key] = {
            "diagnosisKind": _s(r.kind),
            "verificationStatus": _s(r.status),
            "factOrigin": _s(r.origin),
            "caveat": _s(r.caveat),
            "diagnosisIri": _s(r.dx),
        }

    for r in ds.query(_RISK_Q):
        out.risk[("tier",)] = {
            "tier": _s(r.tier),
            "ruleId": _s(r.ruleId),
            "insufficientReason": _s(r.reason),
            "monitoringGap": _s(r.gap),
        }

    for r in ds.query(_SAFETY_Q):
        key = (_s(r.severity), _s(r.med))
        out.safety[key] = {
            "severity": _s(r.severity),
            "rationale": _s(r.rationale),
            "medication": _s(r.med),
        }
    return out


# 会因假设而改变、且值得单独播报的字段。
_WATCHED = ("conclusion", "verificationStatus", "tier", "severity", "caveat")


def diff(before: Conclusions, after: Conclusions) -> list[dict[str, Any]]:
    """结论级 diff。三种变化：added / removed / changed。

    `changed` 只在受关注字段上报，避免把 IRI 变动、出处补齐之类的
    内部扰动当成"结论变了"。
    """
    delta: list[dict[str, Any]] = []
    for kind, b_map in before.buckets():
        a_map = dict(after.buckets())[kind]
        for key in a_map.keys() - b_map.keys():
            delta.append({"change": "added", "type": kind, "after": a_map[key]})
        for key in b_map.keys() - a_map.keys():
            delta.append({"change": "removed", "type": kind, "before": b_map[key]})
        for key in b_map.keys() & a_map.keys():
            b, a = b_map[key], a_map[key]
            fields = {
                f: {"before": b.get(f), "after": a.get(f)}
                for f in _WATCHED
                if f in b and b.get(f) != a.get(f)
            }
            if fields:
                delta.append({"change": "changed", "type": kind,
                              "fields": fields, "before": b, "after": a})

    order = {"changed": 0, "added": 1, "removed": 2}
    delta.sort(key=lambda d: (order[d["change"]], d["type"]))
    return delta
