"""FastAPI —— 融合查询的 HTTP 门面。

端点很薄：所有逻辑在 query/hybrid.py，这里只做参数校验与 HTTP 语义。
薄是刻意的 —— CLI 与 API 必须走同一条代码路径，否则两边的答案会慢慢分叉，
而演示时用的是哪一条谁也说不清。

    uv run dmo serve --port 8100
    curl 'http://localhost:8100/patients?icd10=E11&size=5'
    curl 'http://localhost:8100/patients/P90002/assessment'
    curl 'http://localhost:8100/patients/P90008/safety'
    curl 'http://localhost:8100/patients/P00016/risk'
    curl 'http://localhost:8100/terms/explain?term=糖化血红蛋白'
    curl -X POST localhost:8100/simulate -d '{"patientId":"P90002","assume":[]}'
    curl 'http://localhost:8100/demo/compare?term=尿蛋白'
    curl 'http://localhost:8100/graph/passages?q=6.5%25'
    curl -X POST localhost:8100/adjudicate/citations -d '{"citations":[{"quote":"6.5% or above"}]}'
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query

from . import config as config_mod
from .query import hybrid, templates

app = FastAPI(
    title="糖尿病本体 × 患者事实库 融合查询",
    description=hybrid.DISCLAIMER,
    version="0.1.0",
)


def _cfg():
    return config_mod.load()


@app.get("/", include_in_schema=False)
def root() -> dict[str, Any]:
    """轻量服务入口；不访问 PostgreSQL 或 GraphDB。"""
    return {
        "name": app.title,
        "version": app.version,
        "status": "running",
        "health": "/health",
        "docs": "/docs",
        "openapi": app.openapi_url,
    }


@app.exception_handler(Exception)
def _graphdb_unavailable(request, exc):
    """GraphDB 连不上时给 503，不给 500 + 堆栈。

    500 的含义是「本服务出错了」，会让调用方去查自己的请求；连不上上游是
    **依赖不可用**，是运维问题。这个区分对排障值几十分钟 —— 实测远端
    GraphDB 会间歇性 502，不分开的话每次都要翻堆栈才知道不是代码的锅。
    """
    from fastapi.responses import JSONResponse

    from .graph.client import GraphDBError

    if isinstance(exc, GraphDBError):
        return JSONResponse(status_code=503, content={
            "detail": f"GraphDB 暂时不可用：{str(exc)[:300]}",
            "hint": "检查 DMO_GRAPHDB_ENDPOINT（只填根地址，不带 /repositories）"
                    "与仓库是否在跑；GET /health 会同时探两库。"})
    raise exc


@app.get("/health")
def health() -> dict[str, Any]:
    from .db.engine import onto_conn
    from .graph.client import GraphDBClient, GraphDBError
    from .terms.concepts import graph_version

    out: dict[str, Any] = {"ok": True, "graphVersion": graph_version()[:16]}
    try:
        with onto_conn(_cfg()) as conn:
            out["patients"] = conn.scalar("SELECT count(*) FROM diabetes.core_patient")
            out["labResults"] = conn.scalar("SELECT count(*) FROM diabetes.core_lab_result")
            out["stratified"] = conn.scalar(
                "SELECT count(*) FROM diabetes.pred_risk_stratification")
    except Exception as e:  # noqa: BLE001
        out["ok"] = False
        out["postgres"] = str(e)[:200]
    try:
        out["graphdbTriples"] = GraphDBClient(_cfg()).size()
    except GraphDBError as e:
        out["ok"] = False
        out["graphdb"] = str(e)[:200]
    return out


@app.get("/patients")
def list_patients(
    icd10: str | None = None,
    origin: str | None = Query(None, description="ehr-legacy / derived / demo-cohort"),
    scenario: str | None = None,
    tier: str | None = Query(None, description="High / Moderate / Low / Insufficient-Evidence"),
    page: int = 1,
    size: int = 20,
) -> dict[str, Any]:
    """SQL 侧检索。分页与筛选都在这里做完 —— SPARQL 只处理收敛后的小集合。"""
    return hybrid.find_patients(
        _cfg(), icd10=icd10, origin=origin, scenario=scenario, tier=tier,
        page=page, size=size)


def _bundle(pid: str, sections: tuple[str, ...]) -> dict[str, Any]:
    try:
        return hybrid.patient_bundle(_cfg(), pid, sections=sections)
    except KeyError:
        raise HTTPException(404, f"core_patient 里没有 {pid}") from None


@app.get("/patients/{pid}/care-chain")
def care_chain(pid: str) -> dict[str, Any]:
    return _bundle(pid, ("care_chain",))


@app.get("/patients/{pid}/assessment")
def assessment(pid: str) -> dict[str, Any]:
    """阈值判定 + 所用阈值区间 + 逐字出处 + sha256。"""
    return _bundle(pid, ("assessment",))


@app.get("/patients/{pid}/risk")
def risk(pid: str) -> dict[str, Any]:
    """风险分层。⚠️ 规则式定性分层，不含概率、不含时间窗。"""
    return _bundle(pid, ("risk",))


@app.get("/patients/{pid}/safety")
def safety(pid: str) -> dict[str, Any]:
    return _bundle(pid, ("safety",))


@app.get("/patients/{pid}")
def full(pid: str) -> dict[str, Any]:
    return _bundle(pid, ())


def _simulate(pid: str, body: dict[str, Any]) -> dict[str, Any]:
    """确定性病程推演：注入假设检验结果，看结论怎么变、每一步凭什么。

    ⚠️ 这是**条件推演**（若 X 则 Y），不是预测：假设值必须由调用方显式给出，
    系统不生成、不推荐、不外推任何数值。

    推演全程在内存里跑，对 GraphDB 只发 CONSTRUCT —— 调多少次，
    库里三元组数一条都不会变。
    """
    from .simulate import HypothesisError, SandboxError, simulate

    assume = body.get("assume")
    if not isinstance(assume, list):
        raise HTTPException(
            400, "body 必须含 \"assume\": [{term, value, unit, date}, ...]")
    try:
        return simulate(
            _cfg(), pid, assume,
            include_unreliable=bool(body.get("includeUnreliable")),
            refresh=bool(body.get("refresh")),
        )
    except HypothesisError as e:
        # 400 而不是 422：这些拒绝都是**有意的业务判断**（不猜术语、不默认单位），
        # 消息本身就是给用户看的答案，不是参数格式错误。
        raise HTTPException(400, str(e)) from None
    except SandboxError as e:
        raise HTTPException(404, str(e)) from None


@app.post("/simulate")
def simulate_body(body: dict[str, Any]) -> dict[str, Any]:
    """患者号走 body、路径写死 —— 给只能配静态 URL 的调用方（如 MCP）用。

        curl -X POST localhost:8100/simulate \\
             -H 'Content-Type: application/json' \\
             -d '{"patientId":"P90002",
                  "assume":[{"term":"A1C","value":7.9,"unit":"percent","date":"2026-02-20"}]}'

    与 /patients/{pid}/simulate 同一条代码路径，同一个 derivationHash。
    """
    pid = body.get("patientId") or body.get("pid")
    if not isinstance(pid, str) or not pid.strip():
        raise HTTPException(400, 'body 必须含 "patientId"，如 {"patientId": "P90002", ...}')
    return _simulate(pid.strip(), body)


@app.post("/patients/{pid}/simulate")
def simulate_patient(pid: str, body: dict[str, Any]) -> dict[str, Any]:
    """同上，患者号走路径。保留给既有调用方（CLI 文档、skills 脚本、部署测试）。

        curl -X POST localhost:8100/patients/P90002/simulate \\
             -H 'Content-Type: application/json' \\
             -d '{"assume":[{"term":"A1C","value":7.9,"unit":"percent","date":"2026-02-20"}]}'
    """
    return _simulate(pid, body)


@app.get("/query/templates")
def list_templates() -> list[dict[str, str]]:
    return [{"name": t.name, "description": t.description}
            for t in sorted(templates.TEMPLATES.values(), key=lambda x: x.name)]


@app.post("/query/{template}")
def run_template(template: str, patients: list[str]) -> dict[str, Any]:
    """参数化模板白名单。**不接受自由 SPARQL** —— 理由见 query/templates.py。"""
    if template not in templates.TEMPLATES:
        raise HTTPException(
            404, f"没有模板 {template}。可用：{sorted(templates.TEMPLATES)}")
    if not patients:
        raise HTTPException(400, "必须给患者列表 —— 模板不做全库扫描")
    from .graph.client import GraphDBClient
    from .rdf import iri as I

    iris = [I.patient_iri(p) for p in patients]
    rows = GraphDBClient(_cfg()).sparql_csv(templates.render(template, iris))
    return {"template": template, "rows": rows, "disclaimer": hybrid.DISCLAIMER}


@app.get("/agent/manifest")
def agent_manifest() -> dict[str, Any]:
    """给智能体的能力清单：端点 + 调用顺序 + 图层铁律 + 硬禁令 + 覆盖面。

    端点清单从 app.routes 现场生成，不可能与实际服务分叉。
    """
    from .manifest import build

    return build(app, _cfg())


@app.get("/graph/concepts")
def graph_concepts(
    q: str = Query(..., description="中文表面形式 / 编码 / 英文 label"),
    kind: str | None = Query(None, description="LabTest / Medication / RiskFactor …"),
    limit: int = 20,
) -> dict[str, Any]:
    """中文表面形式 → 准确 IRI。**所有图探索的唯一入口。**

    并集是核心：本体的 label/altLabel ∪ 三张人工映射表里的上游中文名。
    返回体的 `usable` 字段说明这个映射到底参不参与判定 —— 查得到 ≠ 判得了。
    """
    from .graph import explore

    try:
        return explore.search_concepts(_cfg(), q=q, kind=kind, limit=limit)
    except explore.ExploreError as e:
        raise HTTPException(400, str(e)) from None


@app.get("/graph/node")
def graph_node(iri: str) -> dict[str, Any]:
    """节点邻接摘要：类型（标出哪些是推理机推的）、所在图、出边/入边 + 计数。

    ⚠️ 拒绝 `urn:dmo:data` 里的反例夹具，并说明原因 —— 悄悄过滤等于静默少返。
    """
    from .graph import explore

    try:
        return explore.node(_cfg(), iri)
    except explore.ExploreError as e:
        raise HTTPException(400, str(e)) from None


@app.get("/graph/neighbors")
def graph_neighbors(
    iri: str,
    predicate: str | None = None,
    direction: str = Query("out", description="out 取对象 / in 取主语"),
    limit: int = 50,
) -> dict[str, Any]:
    from .graph import explore

    try:
        return explore.neighbors(_cfg(), iri, predicate=predicate,
                                 direction=direction, limit=limit)
    except explore.ExploreError as e:
        raise HTTPException(400, str(e)) from None


@app.get("/graph/taxonomy")
def graph_taxonomy(
    iri: str,
    direction: str = Query("up", description="up 上位 / down 下位"),
    depth: int = 3,
) -> dict[str, Any]:
    """类层次 —— 同时是 owl2-rl 推理产物的展示面。

    `inferenceNotice` 会指出哪几条边不在任何文件里写着、是推出来的。
    """
    from .graph import explore

    try:
        return explore.taxonomy(_cfg(), iri, direction=direction, depth=depth)
    except explore.ExploreError as e:
        raise HTTPException(400, str(e)) from None


@app.get("/graph/path")
def graph_path(
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
    maxHops: int = 3,
) -> dict[str, Any]:
    """两个节点之间怎么连上的。服务端做双向受控 BFS，不放任意长度属性路径出去。"""
    from .graph import explore

    try:
        return explore.path(_cfg(), source=from_, target=to, max_hops=maxHops)
    except explore.ExploreError as e:
        raise HTTPException(400, str(e)) from None


@app.get("/graph/schema")
def graph_schema(
    section: str | None = Query(None, description="rdf / sql / bridge，不给则全给"),
) -> dict[str, Any]:
    """schema 卡片：RDF 侧 + SQL 侧 + 两侧的列↔谓词桥接表。

    桥接表由 `rdf/emit.py` 的 AST 静态解析得到 —— 不可能与实际发射逻辑分叉。
    """
    from .graph import schema_card

    try:
        return schema_card.card(_cfg(), section=section)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@app.get("/graph/provenance")
def graph_provenance(iri: str) -> dict[str, Any]:
    """反向溯源：推断产物 → 支撑链 → 指南原文 → SQL 原始行。

    「推理」与「可核查」两个亮点在这里合流。`brokenLinks` 与 `chain` 同等重要 ——
    只报走通的环节等于在暗示「这条结论有出处」。
    """
    from .graph import provenance

    try:
        return provenance.trace(_cfg(), iri)
    except provenance.ExploreError as e:
        raise HTTPException(400, str(e)) from None


@app.post("/graph/sparql")
def graph_sparql(body: dict[str, Any]) -> dict[str, Any]:
    """自由 SPARQL 逃生口 —— 静态检查通过才执行，0 行会自动跑降级探针。

    ⚠️ **这是第 13 个工具，不是第 1 个。** `/graph/{concepts,node,neighbors,taxonomy,
    path,provenance}` 能答的别自己拼图模式：那一族的 GRAPH 子句由服务端拼，
    永远不会踩「知识侧写具名图 → 静默少返」和「患者侧缺守卫 → 扫到反例夹具」这两脚。
    """
    from .graph import guard
    from .graph.client import GraphDBClient

    q = body.get("query")
    verdict = guard.check(q)
    if not verdict.ok:
        # 400 而不是 422：这些拒绝是有意的业务判断，消息本身就是给调用方看的答案。
        raise HTTPException(400, {"detail": "查询未通过静态检查。",
                                  "guard": verdict.as_dict()})

    client = GraphDBClient(_cfg())
    rows = client.sparql_csv(verdict.query) if verdict.form != "ASK" else None
    out: dict[str, Any] = {
        "guard": verdict.as_dict(),
        "queryExecuted": verdict.query,
        "disclaimer": hybrid.DISCLAIMER,
    }
    if rows is None:
        out["boolean"] = client.ask(verdict.query)
        return out
    out["rows"] = rows
    out["rowCount"] = len(rows)
    if not rows:
        out["emptyReason"] = guard.zero_result_reason(client, verdict.query)
    return out


@app.get("/graph/passages")
def graph_passages(
    sha256: str | None = Query(None, description="按内容哈希精确查"),
    q: str | None = Query(None, description="引文子串（规范化后、大小写不敏感）"),
    passageId: str | None = None,
    citedBy: str | None = Query(None, description="thresholdId 或 riskRuleId"),
    limit: int = 50,
) -> dict[str, Any]:
    """可引用出处检索。图探索族的第一个原语，与 /adjudicate/citations 共用底表。

    返回体带 nextHops（可继续展开的端点）与 emptyReason（空集是哪一种空）。
    """
    from .graph import passages

    return passages.search(_cfg(), sha256=sha256, q=q, passage_id=passageId,
                           cited_by=citedBy, limit=limit)


@app.get("/graph/rules")
def graph_rules(
    kind: str | None = Query(None, description="threshold / target / risk"),
    q: str | None = None,
    executable: bool | None = Query(None, description="规则链的 WHERE 真的匹配得上吗"),
    countsInTier: bool | None = Query(None, description="风险规则：有逐字出处、真正计分吗"),
    concept: str | None = Query(None, description="按检验项/指标筛，如 A1C / FPG"),
    context: str | None = Query(None, description="人群语境：NonPregnant / Pregnant / Any"),
    limit: int = 50,
) -> dict[str, Any]:
    """规则内省 —— 先读懂规则，再决定查什么。

    `counts` 段如实报出三个落差（阈值 17/17、风险规则 73→12→10）。
    藏起来就等于夸大覆盖面。
    """
    from .graph import rules

    try:
        return rules.search(_cfg(), kind=kind, q=q, executable=executable,
                            counts_in_tier=countsInTier, concept=concept,
                            context=context, limit=limit)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@app.get("/graph/rules/{rule_id}")
def graph_rule(rule_id: str) -> dict[str, Any]:
    """单条规则全貌，出处展开成完整 passage（含 quote 与 sha256）。"""
    from .graph import rules

    try:
        return rules.get(_cfg(), rule_id)
    except KeyError:
        raise HTTPException(404, f"没有 id 为 {rule_id} 的规则。用 GET /graph/rules 看全量清单。") from None


@app.post("/adjudicate/claim")
def adjudicate_claim_endpoint(body: dict[str, Any]) -> dict[str, Any]:
    """裁决一条**已经给出的结论**：和本体自己推出来的那条并排比对。

        curl -X POST localhost:8100/adjudicate/claim \\
             -H 'Content-Type: application/json' \\
             -d '{"patientId":"P90002",
                  "claim":{"type":"Diagnosis",
                           "value":{"kind":"Diabetes","verificationStatus":"Confirmed"}},
                  "assertedBy":"external-llm/some-model"}'

    四个判定值：supported / contradicted / unsupported / not-adjudicable。
    ⚠️ 永远不返回布尔。`supported` 的含义严格限定为「与本仓库当前版本知识层的规则和
    阈值一致」，不是任何形式的诊疗背书。
    """
    from .adjudicate import CitationError, adjudicate_claim

    try:
        return adjudicate_claim(_cfg(), body)
    except CitationError as e:
        raise HTTPException(400, str(e)) from None
    except KeyError as e:
        raise HTTPException(404, f"core_patient 里没有 {e.args[0]}") from None


@app.get("/adjudicate/scope")
def adjudicate_scope() -> dict[str, Any]:
    """我能裁决什么、不能裁决什么。**调用裁决族之前先读这个。**"""
    from .adjudicate import describe_scope

    return describe_scope(_cfg())


@app.post("/adjudicate/citations")
def adjudicate_citations(body: dict[str, Any]) -> dict[str, Any]:
    """裁决一批引用是否逐字成立。**不需要患者，完全确定性。**

        curl -X POST localhost:8100/adjudicate/citations \\
             -H 'Content-Type: application/json' \\
             -d '{"citations":[{"quote":"6.5% or above",
                                "sha256":"96495c7d996a92b5bee7132029744f08e5154be98dd1be7e177399320d7d1447"}]}'

    五个判定值：verbatim / hash-only / quote-only / not-verbatim / fabricated。
    ⚠️ 永远不返回布尔 —— 「通过校验」这种印章本系统不发，理由见
    docs/ADJUDICATE-EXPLORE-API-PLAN.md §0.1。
    """
    from .adjudicate import CitationError, check_citations

    try:
        return check_citations(
            _cfg(), body.get("citations"),
            asserted_by=body.get("assertedBy"),
            refresh=bool(body.get("refresh")),
        )
    except CitationError as e:
        # 400 而不是 422：与 /simulate 同一条口径 —— 这些拒绝是有意的业务判断，
        # 消息本身就是给调用方看的答案。
        raise HTTPException(400, str(e)) from None


@app.get("/terms/unmapped")
def unmapped() -> dict[str, Any]:
    from .db.engine import onto_conn

    with onto_conn(_cfg()) as conn:
        return {
            "unmapped": conn.fetchall(
                "SELECT * FROM diabetes.map_unmapped_term ORDER BY term_kind, hit_count DESC"),
            "notUsable": conn.fetchall(
                "SELECT src_name, verify_status, value_kind, note FROM diabetes.map_lab_term "
                "WHERE verify_status <> 'verified' ORDER BY verify_status, src_name"),
        }


@app.get("/terms/explain")
def explain(term: str) -> dict[str, Any]:
    """诚实回答「为什么查不到」。返回空集与「有但判不了」是两回事。"""
    return hybrid.explain_gap(_cfg(), term)


@app.get("/demo/compare")
def demo_compare(term: str = "尿蛋白") -> dict[str, Any]:
    """同一个术语，字符串匹配 vs 本体两种做法并排。"""
    from .terms import wfs

    out = wfs.compare(_cfg(), term)
    out["disclaimer"] = hybrid.DISCLAIMER
    return out


def serve(port: int = 8100) -> int:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
    return 0
