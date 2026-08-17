"""推导树 —— 「展示推理依据」的那一半。

七段扁平返回体回答的是"结论是什么"；推演要回答的是"这个结论**怎么来的**，
其中哪几步踩在假设上"。这两个问题的形状不同：前者是列表，后者是树。

    Diagnosis  Diabetes / Provisional          ← 规则 DIAGNOSIS-FROM-ASSESSMENT
    └─ Assessment  DiabetesRange               ← 规则 LAB-THRESHOLD-MATCH
       ├─ threshold A1C-DIABETES-NONPREG  [6.5, +∞) percent
       │  └─ 出处 "…" sha256 a3f8…
       └─ LabResult 7.4 percent @2026-01-15   [实测]
          （或 [假设] —— provenance 字段区分，前端据此上不同颜色）

每个叶子都必须能指到 quote + sha256，否则这棵树只是好看的猜测。
`provenance` 只有 measured / hypothetical 两个取值，没有第三种含糊状态。
"""

from __future__ import annotations

from typing import Any

from rdflib import Dataset

from .engine import Conclusions
from .hypothesis import Hypothesis

_SUPPORT_Q = """
PREFIX dmo: <https://example.org/dmo#>
SELECT ?a WHERE { ?a dmo:supportsDiagnosis <%s> }
"""

_THRESHOLD_Q = """
PREFIX dmo: <https://example.org/dmo#>
SELECT ?tid ?lo ?loOp ?up ?upOp ?unit ?confirm ?quote ?sha WHERE {
  <%s> dmo:appliesThreshold ?th .
  ?th dmo:thresholdId ?tid ; dmo:boundUnit ?unit ;
      dmo:lowerOperator ?loOp ; dmo:upperOperator ?upOp .
  OPTIONAL { ?th dmo:lowerBound ?lo }
  OPTIONAL { ?th dmo:upperBound ?up }
  OPTIONAL { ?th dmo:confirmationRequired ?confirm }
  OPTIONAL { ?th dmo:thresholdCitesPassage ?p . ?p dmo:quote ?quote ; dmo:contentHash ?sha }
}
"""


def interval(lo: Any, lo_op: str, up: Any, up_op: str, unit: str) -> str:
    """把 operator + bound 还原成逐字区间。

    **绝不用 >= 近似**：A1C 的三个切点是 (-∞,5.7) / [5.7,6.4] / [6.5,+∞)，
    把开区间写成闭区间会把 5.7 从 Prediabetes 错判成 Normal（S16 专测这个）。
    """
    left = "(-∞" if lo_op == "None" or lo is None else (
        f"[{lo}" if lo_op == "GTE" else f"({lo}")
    right = "+∞)" if up_op == "None" or up is None else (
        f"{up}]" if up_op == "LTE" else f"{up})")
    return f"{left}, {right} {unit}".strip()


def _threshold_node(ds: Dataset, assessment_iri: str) -> dict[str, Any] | None:
    sources: list[dict[str, str]] = []
    node: dict[str, Any] | None = None
    for r in ds.query(_THRESHOLD_Q % assessment_iri):
        if node is None:
            node = {
                "node": "DiagnosticThreshold",
                "thresholdId": str(r.tid),
                "interval": interval(r.lo, str(r.loOp), r.up, str(r.upOp), str(r.unit)),
                "confirmationRequired": bool(r.confirm),
                "sources": sources,
            }
        if r.quote is not None:
            entry = {"quote": str(r.quote), "sha256": str(r.sha or "")}
            if entry not in sources:
                sources.append(entry)
    if node is not None and not sources:
        # 出处链断了。不静默 —— 这类阈值本不该参与判定。
        node["sourceWarning"] = (
            "该阈值没有可逐字引用的出处片段，按本仓库规矩它不该参与判定，"
            "出现在这里说明知识层的出处链断了。")
    return node


def _lab_node(detail: dict[str, Any], hypo_ids: set[str]) -> dict[str, Any]:
    iri = detail.get("basedOnLabResult") or ""
    is_hypo = detail.get("fromHypothesis") or any(iri.endswith(h) for h in hypo_ids)
    return {
        "node": "LabResult",
        "value": detail.get("value"),
        "unit": detail.get("unit"),
        "collectedDate": detail.get("collectedDate"),
        "provenance": "hypothetical" if is_hypo else "measured",
        "iri": iri,
    }


def build(ds: Dataset, after: Conclusions, hyps: list[Hypothesis]) -> list[dict[str, Any]]:
    """从假设后的结论集回溯出推导树。诊断在上，没有诊断支撑的评估平铺在后。"""
    hypo_ids = {h.result_id() for h in hyps}
    by_iri = {v["assessmentIri"]: v for v in after.assessments.values()}

    def assessment_node(detail: dict[str, Any]) -> dict[str, Any]:
        children: list[dict[str, Any]] = []
        th = _threshold_node(ds, detail["assessmentIri"])
        if th:
            children.append(th)
        children.append(_lab_node(detail, hypo_ids))
        return {
            "node": "Assessment",
            "conclusion": detail["conclusion"],
            "rule": f"{detail['ruleId']}@{detail['ruleVersion']}",
            "applicableContext": detail["applicableContext"],
            "children": children,
        }

    tree: list[dict[str, Any]] = []
    used: set[str] = set()

    for dx in sorted(after.diagnoses.values(), key=lambda x: x["diagnosisIri"] or ""):
        supports: list[dict[str, Any]] = []
        for r in ds.query(_SUPPORT_Q % dx["diagnosisIri"]):
            detail = by_iri.get(str(r.a))
            if detail:
                supports.append(assessment_node(detail))
                used.add(str(r.a))
        node = {
            "node": "Diagnosis",
            "diagnosisKind": dx["diagnosisKind"],
            "verificationStatus": dx["verificationStatus"],
            "factOrigin": dx["factOrigin"],
            "caveat": dx["caveat"],
            "supportedByCount": len(supports),
            "children": supports,
        }
        if dx["verificationStatus"] == "Provisional":
            # 把「差什么」直接写进树里 —— 这是推演最有用的一句话。
            node["gapToConfirmed"] = (
                "需要另一个不同日期的同项检验落在同一阈值区间。"
                "当前支撑的不同日期数不足 2 —— 见 caveat 原文。")
        tree.append(node)

    for iri, detail in sorted(by_iri.items()):
        if iri not in used:
            tree.append(assessment_node(detail))
    return tree
