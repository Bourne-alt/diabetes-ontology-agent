"""FastAPI —— 融合查询的 HTTP 门面。

端点很薄：所有逻辑在 query/hybrid.py，这里只做参数校验与 HTTP 语义。
薄是刻意的 —— CLI 与 API 必须走同一条代码路径，否则两边的答案会慢慢分叉，
而演示时用的是哪一条谁也说不清。

    uv run dmo serve --port 8000
    curl 'http://localhost:8000/patients?icd10=E11&size=5'
    curl 'http://localhost:8000/patients/P90002/assessment'
    curl 'http://localhost:8000/patients/P90008/safety'
    curl 'http://localhost:8000/patients/P00016/risk'
    curl 'http://localhost:8000/terms/explain?term=糖化血红蛋白'
    curl 'http://localhost:8000/demo/compare?term=尿蛋白'
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


def serve(port: int = 8000) -> int:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
    return 0
