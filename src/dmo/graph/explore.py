"""图探索原语 —— 给智能体的「下一跳」，不是给它一门查询语言。

## 自由度开在哪个维度上

`query/templates.py` 拒绝让 LLM 自由写 SPARQL，最狠的理由是**静默少返**：
写错 GRAPH 子句查询不报错，只是答案少一半，看输出发现不了。这条理由到今天仍然成立。

所以这一族的做法是：**agent 自己决定下一跳查什么，GRAPH 子句由服务端拼。**
四个原语（concepts / node / neighbors / taxonomy）正交可组合，组合空间比 6 个模板
大几个数量级，而每条实际发出的图模式都是本仓库自己写的。

## 三件服务端替调用方兜住的事

1. **反例夹具**。`urn:dmo:data` 里 6 个合成患者是**故意造错的**（P001 触发禁忌、
   R005 缺单位）。它们的 IRI 长得跟真患者一样（`.../patient/P001`），agent 分不出来。
   `node()` 直接拒绝这类 IRI 并说明原因，不是悄悄过滤 —— 悄悄过滤等于又一次静默少返。

2. **断言 vs 推断**。owl2-rl 的物化三元组**不在任何用户命名图里**，所以
   `OPTIONAL { GRAPH ?g { … } }` 拿不到图名的那些就是推理机推出来的。
   这一条同时是坑和卖点：
   - 坑：`?r a dmo:RiskRule` 会连 prp-dom 反推出来的患者命中记录一起捞（见 rules.py）；
   - 卖点：`taxonomy()` 能明确指出「这几个上位类是推出来的，不在任何文件里写着」。
   两者都靠同一个 `assertedIn` 字段呈现，不需要第二套机制。

3. **空节点**。owl 限制类是空节点，skolem ID 每次装载都变（`rdf/canonical.py`）。
   一律 `FILTER(!isBlank(…))` 滤掉 —— 把 `_:node1` 报给 agent 只会诱导它去查一个下次
   就不存在的 IRI。
"""

from __future__ import annotations

from typing import Any

from ..config import Config

PREFIXES = """
PREFIX dmo:  <https://example.org/dmo#>
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
"""

FIXTURE_GRAPH = "urn:dmo:data"
PATIENT_GRAPH_PREFIX = "urn:dmo:patient:"

# owl2-rl 给每个类都物化了 `C rdfs:subClassOf owl:Thing`。真的，但对调用方毫无信息量，
# 留在层次里会让「有没有领域内的上位类」这个真问题被淹掉。单独归一类，不混进 levels。
TRIVIAL_ANCESTORS = frozenset({
    "http://www.w3.org/2002/07/owl#Thing",
    "http://www.w3.org/2002/07/owl#Nothing",
    "http://www.w3.org/2000/01/rdf-schema#Resource",
})

FIXTURE_REFUSAL = (
    "{iri} 只出现在 {g} —— 那是 6 例**故意造错的反例夹具**"
    "（P001 触发禁忌、R005 缺单位、R006 单位不一致），不是真实患者。"
    "拿它们的数据下任何结论都是错的。真实患者的图名以 "
    f"`{PATIENT_GRAPH_PREFIX}` 开头，用 GET /patients 检索。"
)


class ExploreError(ValueError):
    """入参不成立，或目标不该被探索。消息直接给调用方看。"""


def _iri_ok(iri: str) -> str:
    iri = (iri or "").strip()
    if not iri.startswith(("http://", "https://", "urn:")):
        raise ExploreError(
            f"iri 必须是完整 IRI，收到 {iri!r}。"
            "先用 GET /graph/concepts?q=<中文或编码> 拿到准确 IRI 再来 —— 本仓库不猜术语。")
    if "<" in iri or ">" in iri or '"' in iri or "\\" in iri:
        raise ExploreError("iri 含非法字符。")
    return iri


# ────────────────────────── concepts ──────────────────────────


def search_concepts(cfg: Config, *, q: str, kind: str | None = None,
                    limit: int = 20) -> dict[str, Any]:
    """中文表面形式 → 准确 IRI。**所有图探索的唯一入口。**

    并集是核心：本体的 label/altLabel **∪** 三张人工映射表里的上游中文名。
    纯 SPARQL 版本查不到「糖化血红蛋白」—— 那个字符串只存在于 `map_lab_term.src_name`。

    ⚠️ 命中一个术语不等于它能参与判定。`verify_status` 不是 `verified` 的映射，
    投影层一样跳过（`terms/resolve.USABLE`）。这里如实标 `usable`，
    不标的话 agent 会拿着一个查得到、却永远推不出结论的 IRI 反复试。
    """
    from ..db.engine import onto_conn
    from ..terms.resolve import USABLE

    q = (q or "").strip()
    if not q:
        raise ExploreError("必须给 q —— 这个端点是按表面形式找 IRI 的，不做全量列举。")
    limit = max(1, min(limit, 100))
    like = f"%{q}%"

    with onto_conn(cfg) as conn:
        params: list[Any] = [like, like, q]
        kind_clause = ""
        if kind:
            kind_clause = " AND concept_kind = %s"
            params.append(kind)
        concepts = conn.fetchall(
            f"""
            SELECT iri, concept_kind, code, label, alt_labels, unit_canonical
            FROM diabetes.map_concept_ref
            WHERE (label ILIKE %s OR code ILIKE %s OR %s = ANY(alt_labels)){kind_clause}
            ORDER BY label
            LIMIT 200
            """, tuple(params))

        surfaces = conn.fetchall(
            """
            SELECT src_name AS term, 'lab_term' AS via, concept_iri, verify_status, note
            FROM diabetes.map_lab_term WHERE src_name ILIKE %s
            UNION ALL
            SELECT coalesce(icd10name, icd10code), 'icd10', concept_iri, verify_status, note
            FROM diabetes.map_icd10 WHERE icd10name ILIKE %s OR icd10code ILIKE %s
            UNION ALL
            SELECT src_name, 'drug', coalesce(medication_iri, drug_class_iri),
                   verify_status, note
            FROM diabetes.map_drug_term WHERE src_name ILIKE %s
            """, (like, like, like, like))

        extra_iris = sorted({s["concept_iri"] for s in surfaces
                             if s["concept_iri"]} - {c["iri"] for c in concepts})
        if extra_iris:
            concepts += conn.fetchall(
                """
                SELECT iri, concept_kind, code, label, alt_labels, unit_canonical
                FROM diabetes.map_concept_ref WHERE iri = ANY(%s)
                """, (extra_iris,))

    by_iri = {c["iri"]: dict(c, surfaceForms=[]) for c in concepts}
    for s in surfaces:
        target = by_iri.get(s["concept_iri"])
        if target is None:
            continue
        entry = {
            "term": s["term"], "via": s["via"],
            "verifyStatus": s["verify_status"],
            # 这一条是关键：查得到 ≠ 判得了
            "usable": s["verify_status"] in USABLE,
            "note": (s["note"] or "")[:200] or None,
        }
        # map_lab_term 的唯一键是 (src_name, src_ref_range)，同一个中文名会有多行
        # （不同参考范围），说明文字却是同一句。去重但保序。
        if entry not in target["surfaceForms"]:
            target["surfaceForms"].append(entry)

    rows = sorted(by_iri.values(), key=lambda c: (c["concept_kind"], c["label"] or ""))
    if kind:
        rows = [c for c in rows if c["concept_kind"] == kind]
    # 上游有这个术语、但没有可用映射的，也要说出来 —— 不能只报能查到的那半边
    orphan = [
        {"term": s["term"], "via": s["via"], "verifyStatus": s["verify_status"],
         "usable": False, "reason": (s["note"] or "")[:200] or "映射表里没有可用的 concept_iri"}
        for s in surfaces if not s["concept_iri"]
    ]

    total = len(rows)
    return {
        "query": q,
        "concepts": [_concept_out(c) for c in rows[:limit]],
        "total": total,
        "limit": limit,
        "surfaceFormsWithoutConcept": orphan or None,
        "emptyReason": (
            None if total else
            f"本体与映射表里都没有能对上「{q}」的概念。未命中只记账，不猜 —— "
            "想知道为什么查不到，用 GET /terms/explain?term=… ，那里会区分"
            "「本体里没有」「有概念但上游没数据」「结构上判不了」三种情况。"),
        "nextHops": [
            {"rel": "node", "endpoint": "GET /graph/node?iri={iri}",
             "why": "看这个概念周围有什么边，决定下一跳"},
            {"rel": "taxonomy", "endpoint": "GET /graph/taxonomy?iri={iri}",
             "why": "上位/下位类，其中哪些是推理机推出来的"},
            {"rel": "explain", "endpoint": "GET /terms/explain?term={term}",
             "why": "查不到时问「为什么查不到」"},
        ],
    }


def _concept_out(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "iri": c["iri"], "kind": c["concept_kind"], "code": c["code"],
        "label": c["label"], "altLabels": c["alt_labels"],
        "unitCanonical": c["unit_canonical"],
        "surfaceForms": c["surfaceForms"] or None,
    }


# ────────────────────────── node / neighbors ──────────────────────────

_Q_GRAPHS = PREFIXES + """
SELECT ?g (COUNT(*) AS ?n) WHERE {{ GRAPH ?g {{ <{iri}> ?p ?o }} }} GROUP BY ?g
"""

# assertedIn 拿不到图名 ⟹ 这条三元组是 owl2-rl 物化出来的，不在任何文件里写着。
_Q_TYPES = PREFIXES + """
SELECT ?t ?assertedIn WHERE {{
  <{iri}> a ?t .
  FILTER(!isBlank(?t))
  OPTIONAL {{ GRAPH ?assertedIn {{ <{iri}> a ?t }} }}
}}
"""

_Q_OUT = PREFIXES + """
SELECT ?p (COUNT(DISTINCT ?o) AS ?n) (SAMPLE(?o) AS ?sample) (SAMPLE(?lbl) AS ?sampleLabel)
WHERE {{
  <{iri}> ?p ?o .
  # 排除 owl2-rl 物化的自反 sameAs（`x owl:sameAs x`）—— 纯噪声，
  # 留着会白白占掉 agent 一个 nextHop。
  FILTER(?p != rdf:type && !isBlank(?o) && !(?p = owl:sameAs && ?o = <{iri}>))
  OPTIONAL {{ ?o rdfs:label ?lbl }}
}}
GROUP BY ?p ORDER BY DESC(?n) ?p
"""

_Q_IN = PREFIXES + """
SELECT ?p (COUNT(DISTINCT ?s) AS ?n) (SAMPLE(?s) AS ?sample)
WHERE {{ ?s ?p <{iri}> .
        FILTER(!isBlank(?s) && !(?p = owl:sameAs && ?s = <{iri}>)) }}
GROUP BY ?p ORDER BY DESC(?n) ?p
"""


def _short(iri: str) -> str:
    """给人看的短名。只做显示，不参与任何判定。"""
    return iri.replace("https://example.org/dmo#", "dmo:").replace(
        "http://www.w3.org/2000/01/rdf-schema#", "rdfs:").replace(
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdf:").replace(
        "http://www.w3.org/2002/07/owl#", "owl:").replace(
        "http://www.w3.org/2004/02/skos/core#", "skos:")


def _guard_fixture(iri: str, graphs: list[dict[str, str]]) -> None:
    names = {g["g"] for g in graphs}
    if names and names <= {FIXTURE_GRAPH}:
        raise ExploreError(FIXTURE_REFUSAL.format(iri=iri, g=FIXTURE_GRAPH))


def node(cfg: Config, iri: str) -> dict[str, Any]:
    """节点的**邻接摘要** —— 不返回全部三元组。

    agent 要的是「下一跳去哪」，不是一屏 turtle。谓词 + 计数 + 一个样例，
    足够它决定下一步；真要展开某条边再调 /graph/neighbors，token 也可控。
    """
    from .client import GraphDBClient

    iri = _iri_ok(iri)
    client = GraphDBClient(cfg)

    graphs = client.sparql_csv(_Q_GRAPHS.format(iri=iri))
    _guard_fixture(iri, graphs)

    types_raw = client.sparql_csv(_Q_TYPES.format(iri=iri))
    types: dict[str, dict[str, Any]] = {}
    for r in types_raw:
        t = types.setdefault(r["t"], {"iri": r["t"], "short": _short(r["t"]),
                                      "assertedIn": [], "inferredOnly": True})
        if r.get("assertedIn"):
            t["assertedIn"].append(r["assertedIn"])
            t["inferredOnly"] = False

    out_edges = client.sparql_csv(_Q_OUT.format(iri=iri))
    in_edges = client.sparql_csv(_Q_IN.format(iri=iri))

    if not graphs and not types and not out_edges and not in_edges:
        return {"iri": iri, "exists": False, "emptyReason": (
            f"{iri} 在图里一条三元组都没有。最常见的原因是 IRI 拼错 —— "
            "用 GET /graph/concepts?q=… 拿准确 IRI，本仓库不做模糊匹配。")}

    inferred_types = [t["short"] for t in types.values() if t["inferredOnly"]]
    return {
        "iri": iri,
        "exists": True,
        "types": sorted(types.values(), key=lambda t: t["short"]),
        "graphs": [{"graph": g["g"], "triples": int(g["n"])} for g in graphs],
        "outgoing": [{"predicate": r["p"], "short": _short(r["p"]),
                      "count": int(r["n"]), "sample": r.get("sample"),
                      "sampleLabel": r.get("sampleLabel") or None}
                     for r in out_edges],
        "incoming": [{"predicate": r["p"], "short": _short(r["p"]),
                      "count": int(r["n"]), "sample": r.get("sample")}
                     for r in in_edges],
        # ★ 这一句是本端点最该被读到的东西
        "inferenceNotice": (
            f"其中 {len(inferred_types)} 个类型是推理机推出来的、不在任何文件里写着："
            f"{'、'.join(inferred_types)}。"
            "owl2-rl 的 prp-dom 会顺着谓词的 rdfs:domain 反推类型 —— "
            "**别拿 `?x a <类>` 当「声明了这个类」用**，以声明标记（thresholdId / "
            "riskRuleId / targetId）为准。"
        ) if inferred_types else None,
        "nextHops": [
            {"rel": "expand", "endpoint": f"GET /graph/neighbors?iri={iri}&predicate={r['p']}",
             "why": f"展开 {_short(r['p'])}（{r['n']} 个对象）"}
            for r in out_edges[:8]
        ] + [{"rel": "taxonomy", "endpoint": f"GET /graph/taxonomy?iri={iri}",
              "why": "上位/下位类"}],
    }


def neighbors(cfg: Config, iri: str, *, predicate: str | None = None,
              direction: str = "out", limit: int = 50) -> dict[str, Any]:
    """展开一跳。direction=out 取对象，in 取主语。"""
    from .client import GraphDBClient

    iri = _iri_ok(iri)
    if direction not in ("out", "in"):
        raise ExploreError("direction 只能是 out / in。")
    if predicate:
        predicate = _iri_ok(predicate)
    limit = max(1, min(limit, 200))

    pred = f"<{predicate}>" if predicate else "?p"
    pattern = (f"<{iri}> {pred} ?other ." if direction == "out"
               else f"?other {pred} <{iri}> .")
    q = PREFIXES + f"""
SELECT ?p ?other ?label ?g WHERE {{
  {pattern}
  FILTER(!isBlank(?other))
  OPTIONAL {{ ?other rdfs:label ?label }}
  OPTIONAL {{ GRAPH ?g {{ {pattern} }} }}
}}
LIMIT {limit + 1}
"""
    if predicate:
        q = q.replace("SELECT ?p ?other", f"SELECT (<{predicate}> AS ?p) ?other")

    client = GraphDBClient(cfg)
    rows = client.sparql_csv(q)

    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        key = (r.get("p") or predicate or "", r["other"])
        entry = seen.setdefault(key, {
            "predicate": key[0], "short": _short(key[0]), "iri": r["other"],
            "label": r.get("label") or None, "assertedIn": [], "inferredOnly": True,
        })
        if r.get("g"):
            if r["g"] not in entry["assertedIn"]:
                entry["assertedIn"].append(r["g"])
            entry["inferredOnly"] = False

    items = list(seen.values())
    fixture = [e for e in items if FIXTURE_GRAPH in e["assertedIn"]]
    items = [e for e in items if FIXTURE_GRAPH not in e["assertedIn"]]

    return {
        "iri": iri,
        "direction": direction,
        "predicate": predicate,
        "neighbors": items[:limit],
        "truncated": len(rows) > limit,
        # 过滤掉夹具**必须说出来**，悄悄少返和静默少返是一回事
        "fixtureFiltered": (
            f"另有 {len(fixture)} 个邻居只存在于 {FIXTURE_GRAPH}（故意造错的反例夹具），"
            "已排除。") if fixture else None,
        "emptyReason": (
            None if items else
            f"{iri} 在这个方向上没有邻居。换 direction，或先用 GET /graph/node?iri=… "
            "看它到底有哪些边 —— 猜谓词名是这一层最常见的错。"),
        "nextHops": [{"rel": "node", "endpoint": f"GET /graph/node?iri={e['iri']}",
                      "why": e["label"] or _short(e["iri"])} for e in items[:8]],
    }


# ────────────────────────── taxonomy ──────────────────────────

_Q_SUBCLASS = PREFIXES + """
SELECT ?child ?parent ?assertedIn ?label WHERE {{
  VALUES ?{var} {{ {values} }}
  ?child rdfs:subClassOf ?parent .
  FILTER(!isBlank(?child) && !isBlank(?parent) && ?child != ?parent)
  OPTIONAL {{ GRAPH ?assertedIn {{ ?child rdfs:subClassOf ?parent }} }}
  OPTIONAL {{ ?{other} rdfs:label ?label }}
}}
"""


def taxonomy(cfg: Config, iri: str, *, direction: str = "up",
             depth: int = 3) -> dict[str, Any]:
    """类层次 —— 也是**推理产物的展示面**。

    owl2-rl 把 `rdfs:subClassOf` 的传递闭包全物化了，所以一次就能拿到全部祖先；
    但「哪几条边是文件里写着的、哪几条是推出来的」才是这里真正值钱的信息：
    `assertedIn` 拿不到图名的就是推理机的产物。

    depth 只约束**逐层展开**的深度，闭包一律全给 —— 藏起来就看不出推理干了什么。
    """
    from .client import GraphDBClient

    iri = _iri_ok(iri)
    if direction not in ("up", "down"):
        raise ExploreError("direction 只能是 up（上位）/ down（下位）。")
    depth = max(1, min(depth, 5))
    client = GraphDBClient(cfg)

    var, other = ("child", "parent") if direction == "up" else ("parent", "child")
    frontier = [iri]
    levels: list[list[dict[str, Any]]] = []
    seen = {iri}
    trivial: list[str] = []

    for _ in range(depth):
        values = " ".join(f"<{i}>" for i in frontier)
        rows = client.sparql_csv(_Q_SUBCLASS.format(var=var, other=other, values=values))
        level: dict[str, dict[str, Any]] = {}
        for r in rows:
            target = r[other]
            if target in seen:
                continue
            if target in TRIVIAL_ANCESTORS:
                if _short(target) not in trivial:
                    trivial.append(_short(target))
                continue
            e = level.setdefault(target, {
                "iri": target, "short": _short(target), "label": r.get("label") or None,
                "from": r[var], "assertedIn": [], "inferredOnly": True,
            })
            if r.get("assertedIn"):
                if r["assertedIn"] not in e["assertedIn"]:
                    e["assertedIn"].append(r["assertedIn"])
                e["inferredOnly"] = False
        if not level:
            break
        seen.update(level)
        levels.append(sorted(level.values(), key=lambda e: e["short"]))
        frontier = list(level)

    flat = [e for lv in levels for e in lv]
    inferred_only = [e["short"] for e in flat if e["inferredOnly"]]
    return {
        "iri": iri,
        "direction": direction,
        "depth": depth,
        "levels": levels,
        "total": len(flat),
        "trivialAncestors": trivial or None,
        # ★ 推理到底干了什么，这一行说得最清楚
        "inferenceNotice": (
            None if not flat else
            f"{len(inferred_only)}/{len(flat)} 条层次关系**没有出现在任何命名图里**，"
            f"是 owl2-rl 物化出来的传递闭包：{'、'.join(inferred_only[:8])}"
            f"{' …' if len(inferred_only) > 8 else ''}。"
            "关掉推理或换掉 ruleset，这些边会全部消失。"
            if inferred_only else "全部层次关系都在文件里显式写着，没有推理产物。"),
        "emptyReason": (
            None if flat else
            (f"{iri} 只有 {'、'.join(trivial)} 这个平凡上位类"
             "（owl2-rl 给每个类都物化了它），没有领域内的上位类。" if trivial else
             f"{iri} 在这个方向上没有类层次。它可能是个体而不是类 —— "
             "个体用 GET /graph/node?iri=… 看邻接。")),
        "nextHops": [{"rel": "node", "endpoint": f"GET /graph/node?iri={e['iri']}",
                      "why": e["label"] or e["short"]} for e in flat[:8]],
    }


# ────────────────────────── path ──────────────────────────

# 遍历时跳过的谓词。它们把任意两个节点都连得上，路径查出来全是伪相关：
#   rdf:type      → A 与 B 都是 owl:Thing，两跳「连通」，毫无意义
#   owl:sameAs    → owl2-rl 物化的自反边
SKIP_PREDICATES = (
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
    "http://www.w3.org/2002/07/owl#sameAs",
)
SKIP_NODES = frozenset(TRIVIAL_ANCESTORS)

# 每跳的前沿上限。高度节点（如某个常见 LabTest）一跳就能拉出上千个邻居，
# 不封顶的话第三跳直接把库扫穿。
FRONTIER_CAP = 400

# ⚠️ `isIRI` 而不是 `!isBlank`：数据属性的对象是字面量（`dmo:labResultId "L90002-A1C"`），
#    把它当节点继续展开，下一跳拼出来的就是 `<L90002-A1C>` —— GraphDB 直接
#    `MALFORMED QUERY: Not a valid (absolute) IRI`。路径也不该穿过字面量。
_Q_HOP = PREFIXES + """
SELECT DISTINCT ?s ?p ?o WHERE {{
  {{ VALUES ?s {{ {values} }} ?s ?p ?o . FILTER(isIRI(?o)) }}
  UNION
  {{ VALUES ?o {{ {values} }} ?s ?p ?o . FILTER(isIRI(?s)) }}
  FILTER(?p NOT IN ({skip}))
  # 反例夹具的边不参与路径 —— 从夹具穿过去的「连通」是假的
  MINUS {{ GRAPH <{fixture}> {{ ?s ?p ?o }} }}
}}
LIMIT {limit}
"""


def path(cfg: Config, *, source: str, target: str, max_hops: int = 3) -> dict[str, Any]:
    """两个节点之间怎么连上的。回答「这个患者事实和那条指南结论有什么关系」。

    服务端做**双向受控 BFS**，不放 SPARQL 的任意长度属性路径出去：
    `?a (<>|!<>)* ?b` 在 10 万三元组上没有封顶，一条查询能把库拖垮，
    而且写错了不报错、只是跑很久然后超时 —— 又一种静默失败。
    """
    from .client import GraphDBClient

    source, target = _iri_ok(source), _iri_ok(target)
    if source == target:
        raise ExploreError("from 与 to 相同。")
    max_hops = max(1, min(max_hops, 4))
    client = GraphDBClient(cfg)

    skip = ", ".join(f"<{p}>" for p in SKIP_PREDICATES)
    # node → (前驱节点, 谓词, 方向)
    parent: dict[str, tuple[str, str, str] | None] = {source: None}
    frontier = [source]
    truncated = False
    hops_used = 0

    for hop in range(max_hops):
        if target in parent or not frontier:
            break
        hops_used = hop + 1
        values = " ".join(f"<{i}>" for i in frontier[:FRONTIER_CAP])
        truncated = truncated or len(frontier) > FRONTIER_CAP
        rows = client.sparql_csv(_Q_HOP.format(
            values=values, skip=skip, fixture=FIXTURE_GRAPH, limit=FRONTIER_CAP * 8))
        nxt: list[str] = []
        for r in rows:
            s, p, o = r["s"], r["p"], r["o"]
            if s in parent and o not in parent and o not in SKIP_NODES:
                parent[o] = (s, p, "out")
                nxt.append(o)
            elif o in parent and s not in parent and s not in SKIP_NODES:
                parent[s] = (o, p, "in")
                nxt.append(s)
        frontier = nxt

    if target not in parent:
        return {
            "from": source, "to": target, "maxHops": max_hops, "found": False,
            "hopsExplored": hops_used, "frontierTruncated": truncated,
            "emptyReason": (
                f"{max_hops} 跳之内没连上"
                + (f"（前沿被截断到 {FRONTIER_CAP} 个节点，可能漏了长路径）。"
                   if truncated else "。")
                + " 遍历刻意跳过 rdf:type 与 owl:sameAs —— 经它们「连通」的是伪相关"
                  "（任意两个节点都是 owl:Thing）。加大 maxHops，或先用 "
                  "GET /graph/node 看两端各自有哪些边。"),
        }

    chain: list[dict[str, str]] = []
    cur = target
    while parent[cur] is not None:
        prev, pred, direction = parent[cur]
        chain.append({"from": prev, "predicate": pred, "short": _short(pred),
                      "to": cur, "direction": direction})
        cur = prev
    chain.reverse()

    return {
        "from": source, "to": target, "maxHops": max_hops, "found": True,
        "hops": len(chain), "path": chain, "frontierTruncated": truncated,
        "note": ("最短路径之一 —— BFS 只保留每个节点第一次被访问到的前驱，"
                 "同长度的其他路径不会列出。"),
        "nextHops": [{"rel": "node", "endpoint": f"GET /graph/node?iri={e['to']}",
                      "why": _short(e["to"])} for e in chain[:6]],
    }
