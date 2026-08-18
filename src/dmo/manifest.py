"""`GET /agent/manifest` —— 让能力可发现，而不是让语言更自由。

「辅助智能体自主规划」的正解不是给它一门查询语言，是**让它知道自己有什么、
按什么顺序用、什么不许做**。端点清单硬编在 prompt 里的话，每加一个端点都要改 prompt，
而且必然漏改。

所以清单从 `app.routes` **现场生成**：新增端点自动出现，删掉的自动消失，
不可能与实际服务分叉。语义（铁律、禁令、确定性）是手写的常量 —— 那部分本来就该人定。
"""

from __future__ import annotations

from typing import Any

# 调用顺序。照 query/hybrid.py 开头的职责边界，一字不改。
ORDER = (
    (
    "1. 不知道准确 IRI 就先 GET /graph/concepts?q=<中文/编码>。**本仓库不猜术语** —— "
    "拼错的 IRI 查出来是空集，和「没有数据」长得一模一样。"
    ),
    "2. 需要患者集合：GET /patients（SQL 侧分页与筛选），不要在图里扫患者。",
    "3. 需要现成结论：GET /patients/{pid}/{assessment|risk|safety|care-chain}。",
    (
    "4. 需要开放探查：GET /graph/{node,neighbors,taxonomy,path} 逐跳走，"
    "每个返回体的 nextHops 直接给了下一跳的 URL。"
    ),
    "5. 需要「凭什么」：GET /graph/provenance?iri=<结论 IRI>，一路到原文与 SQL 原始行。",
    (
    "6. 需要核对别人的结论/引用：POST /adjudicate/{claim,citations}；"
    "调之前先读 GET /adjudicate/scope。"
    ),
    (
    "7. 需要「若 X 则 Y」：POST /patients/{pid}/simulate。**假设值必须由调用方显式给出**，"
    "系统不生成、不推荐、不外推任何数值。"
    ),
)

# 硬禁令。照 README「明确不做的事」五条。
PROHIBITIONS = (
    "不输出任何用药剂量 —— schema 层面就没有剂量字段。",
    "不输出概率、百分比、时间窗。风险分层是规则式定性分层，tier 是有序枚举不是分数。",
    "不猜术语。未命中只记账，没有编辑距离、没有 embedding。",
    (
    "不编造出处。只有 urn:dmo:seed 里那批经 verify_passages.py 逐字回原文校验过的 "
    "SourcePassage 算数；抽取图里的 evidenceQuote 裸字符串不算。"
    ),
    (
    "不把 Provisional 当确诊。诊断级切点 confirmationRequired=true 时，"
    "单次落在区间内 ≠ 确诊。"
    ),
    "不把假设推演的结论当实际情况。/simulate 回答的是「若 X 则 Y」。",
    "不写上游库一个字节；本 API 全部端点只读。",
)

# 哪些端点确定、哪些不确定。调用方据此决定能不能把结果当结论用。
DETERMINISM = {
    "deterministic": {
        "endpoints": ["/patients/*", "/query/*", "/graph/*", "/adjudicate/*",
                      "/simulate", "/terms/*"],
        "means": "同一输入 + 同一 graphVersion（+ rulesFingerprint）⟹ 逐字节相同的输出。"
                 "/simulate 有 derivationHash、/adjudicate/claim 有 adjudicationHash "
                 "可当场核验。",
    },
    "nondeterministic": {
        "endpoints": [],
        "means": "当前没有任何由大模型规划路径的端点。若将来加入（见 "
                 "docs/AGENT-INVESTIGATE-PLAN.md 的 /investigate），返回体必须带 "
                 "nondeterminismNotice。",
    },
}



def _ontology_overview(cfg: Any, ridx: Any) -> dict[str, Any]:
    """本体覆盖面概览 —— 让调用方**提前**知道这个库判得了什么。

    没有这一段时，问「血酮高不高」的正确路径是 /graph/concepts → 查到概念 →
    /patients/{pid}/assessment → 空集 → /terms/explain，四轮才知道「判不了」。
    先给出可判定检验项白名单，一轮就能说清楚。

    **只给边界和量级，不给本体内容。** 类层次、属性、IRI 命名规则一概不进返回体：
    调用方看见 IRI 样例就会开始照着拼，而拼错的 IRI 查出来是空集，
    和「没有数据」长得一模一样。要 IRI 只有一条路 —— GET /graph/concepts。
    """
    tests: dict[str, dict[str, Any]] = {}
    for rule in ridx.rules:
        if rule.kind != "threshold":
            continue
        for code in rule.fields.get("measuredByTest") or []:
            entry = tests.setdefault(code, {
                "test": code, "thresholds": 0, "units": [],
                "confirmationRequired": False, "executable": False,
            })
            entry["thresholds"] += 1
            unit = rule.fields.get("boundUnit")
            if unit and unit not in entry["units"]:
                entry["units"].append(unit)
            entry["confirmationRequired"] |= bool(rule.fields.get("confirmationRequired"))
            entry["executable"] |= bool(rule.executable)

    overview: dict[str, Any] = {
        "assessableLabTests": [tests[k] for k in sorted(tests)],
        "assessableNote": (
            "这张表就是可判定边界：挂了 dmo:hasThreshold 的检验项才有阈值可判，"
            "**也正是 POST /patients/{pid}/simulate 接受的全部检验项**。"
            "不在表里的检验项，本库判不了 —— 直接说明判不了并给出 GET /terms/explain 的理由，"
            "不要逐个去试 /graph/concepts + /patients/{pid}/assessment。"
            "confirmationRequired=true 表示单次落在区间内只能出 Provisional，不是确诊。"
        ),
    }

    # 概念计数与术语缺口在 SQL 侧。PG 挂了不该把整个能力清单一起拖垮 ——
    # 端点、调用顺序、禁令这些是常量，没有它们调用方连怎么问都不知道。
    try:
        from .db.engine import onto_conn

        with onto_conn(cfg) as conn:
            kinds = conn.fetchall(
                "SELECT concept_kind, count(*) AS n FROM diabetes.map_concept_ref "
                "GROUP BY concept_kind ORDER BY concept_kind"
            )
            gaps = conn.fetchall(
                "SELECT (SELECT count(*) FROM diabetes.map_unmapped_term) AS unmapped, "
                "(SELECT count(*) FROM diabetes.map_lab_term "
                " WHERE verify_status <> 'verified') AS not_usable"
            )[0]
        overview["conceptKinds"] = {r["concept_kind"]: r["n"] for r in kinds}
        overview["terminologyGaps"] = {
            "unmappedTerms": gaps["unmapped"],
            "labTermsNotUsable": gaps["not_usable"],
            "note": ("查得到 ≠ 判得了：verify_status <> 'verified' 的映射存在但不参与判定。"
                     "明细见 GET /terms/unmapped，单个术语的原因见 GET /terms/explain。"),
        }
    except Exception as e:  # noqa: BLE001 —— 降级要说清楚缺了哪一段，不能静默省略
        overview["conceptKinds"] = None
        overview["terminologyGaps"] = None
        overview["degraded"] = (
            f"概念计数与术语缺口不可用（{type(e).__name__}）：PostgreSQL 侧读取失败。"
            "assessableLabTests 来自 GraphDB，仍然有效。"
        )
    return overview

def build(app: Any, cfg: Any) -> dict[str, Any]:
    from .graph.passages import load as load_passages
    from .graph.rules import counts
    from .graph.rules import load as load_rules
    from .query.hybrid import DISCLAIMER
    from .query.templates import TEMPLATES
    from .simulate.engine import rules_fingerprint
    from .terms.concepts import graph_version

    endpoints = []
    for r in app.routes:
        path = getattr(r, "path", None)
        methods = sorted((getattr(r, "methods", None) or set()) - {"HEAD", "OPTIONS"})
        if not path or not methods or path.startswith(("/openapi", "/docs", "/redoc")):
            continue
        doc = (getattr(r, "endpoint", None).__doc__ or "").strip()
        endpoints.append({
            "method": methods[0], "path": path,
            "summary": doc.splitlines()[0] if doc else None,
            # 参数名直接给出来 —— 让 agent 猜 query string 是浪费一轮
            "params": sorted({p.name for p in getattr(r, "dependant", None).query_params}
                             | {p.name for p in getattr(r, "dependant", None).path_params})
            if getattr(r, "dependant", None) else [],
        })
    endpoints.sort(key=lambda e: (e["path"], e["method"]))

    ridx = load_rules(cfg)
    return {
        "service": "糖尿病本体 × 患者事实库 融合查询",
        "endpoints": endpoints,
        "callOrder": list(ORDER),
        "graphRules": list(__import__(
            "dmo.graph.schema_card", fromlist=["GRAPH_RULES"]).GRAPH_RULES),
        "prohibitions": list(PROHIBITIONS),
        "determinism": DETERMINISM,
        "coverage": {
            "citablePassages": len(load_passages(cfg).passages),
            "rules": counts(ridx),
            "sparqlTemplates": sorted(TEMPLATES),
            # 覆盖面必须和端点清单一起给。只给能力不给边界，等于鼓励越界使用。
            "boundaries": "GET /adjudicate/scope 给出可裁决与不可裁决的完整清单。",
            "ontology": _ontology_overview(cfg, ridx),
        },
        "graphVersion": graph_version(),
        "rulesFingerprint": rules_fingerprint(),
        "disclaimer": DISCLAIMER,
    }
