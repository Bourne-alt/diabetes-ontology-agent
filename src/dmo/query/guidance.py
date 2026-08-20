"""指南侧的患者视图：命中的推荐条目、按频率推出的监测到期日。

薄封装：SPARQL 在 templates.py 里，这里只做分组与**逾期天数的当下算术**。

⚠️ 逾期天数刻意不进图。dueNextDueAt 是「末次采样 + 指南频率」，从指南确定性推出，
  可物化、可溯源；"今天逾期了几天"是 NOW() 的函数，物化进 urn:dmo:inferred 的那一刻
  就开始过期，而且第二天读到的错误值和正确值长得一模一样。所以在这里算。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..config import Config
from ..graph.client import GraphDBClient
from ..rdf import iri as I
from . import templates

# dueStatus 的三种含义，**不可合并成一个告警**。
_STATUS_MEANING = {
    "scheduled": "有末次记录，到期日已算出",
    "never-recorded": "该患者从无此项检验记录 —— 这不是逾期，是从没做过",
    "frequency-unusable": "语料未写明频率（frequencyMonths=0）。全库 181 条监测计划中 77 条如此，算不出到期日",
}


def _rows(cfg: Config, template: str, pid: str) -> list[dict[str, str]]:
    return GraphDBClient(cfg).sparql_csv(
        templates.render(template, [I.patient_iri(pid)])
    )


def recommendations(cfg: Config, pid: str) -> dict[str, Any]:
    """患者诊断命中的指南推荐，按 recommendationType 分组。

    **不排序、不取 top-N。** 分级体系互不可比（详见 60-recommendation-match.rq）。
    """
    rows = _rows(cfg, "recommendation_match", pid)
    by_type: dict[str, list[dict[str, Any]]] = {}
    provisional = 0
    for r in rows:
        if r.get("verification") == "Provisional":
            provisional += 1
        by_type.setdefault(r.get("recType") or "（未标注类型）", []).append({
            "statement": r.get("statement") or None,
            "populationScope": r.get("scope") or None,
            "strength": r.get("strength") or None,
            "nativeEvidenceGrade": r.get("grade") or None,
            "gradingSystem": r.get("gradingSystem") or None,
            "matchedVia": r.get("via"),
            "fromDiagnosisVerification": r.get("verification"),
            "quote": r.get("quote") or None,
            "derivedFrom": r.get("src") or None,
        })
    return {
        "patientId": pid,
        "total": len(rows),
        "byType": {k: v for k, v in sorted(by_type.items())},
        "typeCounts": {k: len(v) for k, v in sorted(by_type.items())},
        "provisionalBackedCount": provisional,
        "notices": [n for n in (
            "未按证据强度排序：语料的 gradingSystem 跨 VA-DoD / KDIGO / ADA / GRADE / NICE "
            "等互不可比的体系，且 2615 条推荐中 555 条未标注分级体系。命中即列出，取舍由人做。",
            (f"其中 {provisional} 条由 **Provisional（疑似未确诊）** 诊断带出 —— "
             "已在每条的 fromDiagnosisVerification 上标出，不要当成确诊患者的医嘱。")
            if provisional else None,
        ) if n],
    }


def monitoring_due(cfg: Config, pid: str, *, now: datetime | None = None) -> dict[str, Any]:
    """按指南频率推出的下次检验到期日 + 当下逾期天数。"""
    now = now or datetime.now(timezone.utc)
    rows = _rows(cfg, "monitoring_due", pid)

    items: list[dict[str, Any]] = []
    for r in rows:
        due_raw = r.get("nextDueAt") or ""
        overdue_days = None
        if due_raw:
            try:
                due_dt = datetime.fromisoformat(due_raw.replace("Z", "+00:00"))
                if due_dt.tzinfo is None:
                    due_dt = due_dt.replace(tzinfo=timezone.utc)
                overdue_days = (now - due_dt).days
            except ValueError:
                overdue_days = None
        items.append({
            "test": r.get("testLabel") or None,
            "frequencyMonths": int(r["freqMonths"]) if r.get("freqMonths") else None,
            "status": r.get("dueStatus"),
            "statusMeaning": _STATUS_MEANING.get(r.get("dueStatus", ""), None),
            "lastCollectedAt": r.get("lastCollectedAt") or None,
            "nextDueAt": due_raw or None,
            # 正数 = 已逾期天数；负数 = 距到期还有几天
            "overdueDays": overdue_days,
            "sourceRecommendation": r.get("recLabel") or None,
            "populationScope": r.get("scope") or None,
            "quote": r.get("quote") or None,
        })

    # 同一检验可能有多档频率（分属不同指南/人群）—— 分组呈现，不合并、不取最严。
    by_test: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        by_test.setdefault(it["test"] or "（未对齐的检验）", []).append(it)

    counts: dict[str, int] = {}
    for it in items:
        counts[it["status"] or "unknown"] = counts.get(it["status"] or "unknown", 0) + 1

    multi = sorted(t for t, v in by_test.items()
                   if len({x["frequencyMonths"] for x in v if x["frequencyMonths"]}) > 1)

    return {
        "patientId": pid,
        "evaluatedAt": now.isoformat(),
        "total": len(items),
        "statusCounts": counts,
        "byTest": by_test,
        "multiFrequencyTests": multi,
        "notices": [n for n in (
            "三种 status 含义不同，不要合并成一个告警：scheduled / never-recorded"
            "（从没做过，不是逾期）/ frequency-unusable（语料没写频率）。",
            (f"这些检验有多档频率，分属不同指南或人群，已并列不做取舍：{', '.join(multi)}。"
             "请读每条的 populationScope 判断哪一档适用。") if multi else None,
            "overdueDays 是本次查询时刻算出的，不在图里。图里只存 nextDueAt。",
        ) if n],
    }
