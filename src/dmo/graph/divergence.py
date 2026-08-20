"""跨指南分歧地图 —— 同一件事，不同指南怎么说。

这是本仓库最独特的资产：50 部指南同时在一个库里，同一个检验项被 6 个来源提到
（UACR 6 / eGFR 5 / HbA1c 5 / Insulin 15）。临床上"KDIGO 说 6 个月、NIDDK 说 3 个月"
这种分歧现在只能靠人翻 PDF。

⚠️ **只呈现分歧，不裁决分歧。** 这不是能力不足，是刻意的：
  gradingSystem 在 2615 条推荐里有 493 条 "Unspecified"、62 条 "Not specified"，
  其余分属 VA-DoD / KDIGO / ADA / GRADE / NICE / USPSTF 等互不可比的体系。
  把它们归一化打分再排序，得出的"最佳答案"是**凭空造的**，而且会因为看起来
  有理有据而比"我不知道"更危险。

⚠️ 频率不同 ≠ 冲突。绝大多数是**人群不同**：糖尿病前期 12 个月、确诊糖尿病 3 个月、
  检验正常者 36 个月 —— 这是分层不是矛盾。所以每条都必须带 populationScope 原文，
  由读的人判断哪一条适用。真正的冲突要人群重叠才算，本模块把判断材料摆齐，
  不替人下这个判断。
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from .client import GraphDBClient

_PREFIX = """
PREFIX dmo:  <https://example.org/dmo#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
"""

# 检验项的监测频率分歧。走 alignedTo 收敛到规范 LabTest，
# 所以 "A1C" / "A1C Test" / "HbA1c" / "Hemoglobin A1c" 会被认成同一项。
_FREQ_Q = _PREFIX + """
SELECT ?canonLabel ?extLabel ?freqMonths ?scope ?recLabel ?statement ?quote ?graph WHERE {
  GRAPH ?graph {
    ?rec dmo:definesSchedule ?sched ; rdfs:label ?recLabel .
    ?sched dmo:frequencyMonths ?freqMonths ; dmo:schedulesTest ?extTest .
    OPTIONAL { ?rec dmo:populationScope ?scope }
    OPTIONAL { ?rec dmo:statement       ?statement }
    OPTIONAL { ?rec dmo:evidenceQuote   ?quote }
  }
  FILTER(STRSTARTS(STR(?graph), "urn:dmo:extract:"))
  ?extTest rdfs:label ?extLabel .
  OPTIONAL { ?extTest dmo:alignedTo ?canon . ?canon rdfs:label ?canonLabel }
  # 缩写通常只在规范侧的 altLabel 上（"UACR" / "HbA1c" / "eGFR"），
  # 抽取侧写的是全称。不查 altLabel 的话，按缩写搜必然零结果 —— 而临床上
  # 人就是按缩写搜的。
  OPTIONAL { ?canon skos:altLabel ?canonAlt }
  FILTER(%s)
}
ORDER BY ?freqMonths
"""

# 推荐层面的多来源覆盖：同一概念被几部指南分别推荐了什么。
_REC_Q = _PREFIX + """
SELECT ?recLabel ?recType ?strength ?grade ?gradingSystem ?scope ?statement ?quote ?graph WHERE {
  GRAPH ?graph {
    ?rec a dmo:Recommendation ; rdfs:label ?recLabel .
    OPTIONAL { ?rec dmo:recommendationType     ?recType }
    OPTIONAL { ?rec dmo:recommendationStrength ?strength }
    OPTIONAL { ?rec dmo:nativeEvidenceGrade    ?grade }
    OPTIONAL { ?rec dmo:gradingSystem          ?gradingSystem }
    OPTIONAL { ?rec dmo:populationScope        ?scope }
    OPTIONAL { ?rec dmo:statement              ?statement }
    OPTIONAL { ?rec dmo:evidenceQuote          ?quote }
  }
  FILTER(STRSTARTS(STR(?graph), "urn:dmo:extract:"))
  FILTER(%s)
}
LIMIT %d
"""


def _src(graph_uri: str) -> str:
    return graph_uri.replace("urn:dmo:extract:", "")


def _match(term: str, *vars_: str) -> str:
    """大小写无关的子串匹配，注入前先转义引号。"""
    safe = term.replace("\\", "\\\\").replace('"', '\\"').lower()
    return " || ".join(
        f'CONTAINS(LCASE(STR({v})), "{safe}")' for v in vars_
    )


def explain(cfg: Config, term: str, *, limit: int = 40) -> dict[str, Any]:
    """给一个术语，摊开它在各部指南里的说法。"""
    if not term or not term.strip():
        raise ValueError("term 不能为空。例：A1C / UACR / eGFR / metformin")
    term = term.strip()
    gc = GraphDBClient(cfg)

    freq_rows = gc.sparql_csv(
        _FREQ_Q % _match(term, "?extLabel", "?canonLabel", "?canonAlt")
    )
    rec_rows = gc.sparql_csv(_REC_Q % (_match(term, "?recLabel", "?statement"), limit))

    # 按频率分档聚合 —— 同一档可能有多个来源独立支持，那是**佐证**不是分歧。
    by_freq: dict[str, dict[str, Any]] = {}
    for r in freq_rows:
        f = r.get("freqMonths") or ""
        b = by_freq.setdefault(f, {"frequencyMonths": f, "sources": [], "entries": []})
        src = _src(r.get("graph", ""))
        if src and src not in b["sources"]:
            b["sources"].append(src)
        b["entries"].append({
            "recommendation": r.get("recLabel"),
            "populationScope": r.get("scope") or None,
            "testLabelInSource": r.get("extLabel"),
            "source": src,
            "quote": r.get("quote") or None,
        })

    tiers = sorted(by_freq.values(), key=lambda d: int(d["frequencyMonths"] or 0))
    usable = [t for t in tiers if int(t["frequencyMonths"] or 0) > 0]
    unusable = [t for t in tiers if int(t["frequencyMonths"] or 0) == 0]

    rec_sources = sorted({_src(r.get("graph", "")) for r in rec_rows if r.get("graph")})

    return {
        "term": term,
        "monitoringFrequency": {
            "tiers": usable,
            "distinctTierCount": len(usable),
            "unusableTiers": unusable,
            "notice": (
                f"检出 {len(usable)} 档不同频率。**频率不同通常是人群不同，不是矛盾** —— "
                "请逐条读 populationScope 判断哪一条适用。只有人群重叠时才构成真冲突。"
                if len(usable) > 1 else None
            ),
            "unusableNotice": (
                f"另有 {len(unusable)} 档 frequencyMonths=0，那不是『每 0 个月一次』，"
                "是抽取时频率没抽出来的默认填充。全库 181 条监测计划里有 77 条如此。"
                if unusable else None
            ),
        },
        "recommendations": {
            "count": len(rec_rows),
            "sourceCount": len(rec_sources),
            "sources": rec_sources,
            "items": [
                {
                    "recommendation": r.get("recLabel"),
                    "type": r.get("recType") or None,
                    "strength": r.get("strength") or None,
                    "nativeEvidenceGrade": r.get("grade") or None,
                    "gradingSystem": r.get("gradingSystem") or None,
                    "populationScope": r.get("scope") or None,
                    "statement": r.get("statement") or None,
                    "quote": r.get("quote") or None,
                    "source": _src(r.get("graph", "")),
                }
                for r in rec_rows
            ],
            "truncated": len(rec_rows) >= limit,
        },
        "disclaimer": (
            "本端点**只呈现分歧，不裁决分歧**。各来源的 nativeEvidenceGrade 分属互不可比的"
            "分级体系（VA-DoD / KDIGO / ADA / GRADE / NICE …），且 2615 条推荐中 555 条未标注"
            "分级体系，因此不做归一化、不排序、不推荐『最佳答案』。"
        ),
    }
