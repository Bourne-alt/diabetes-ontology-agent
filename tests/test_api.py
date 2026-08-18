"""API 层测试。用 fastapi.testclient 直接跑 app，不起真的 uvicorn。

重点断言两件事：
  1. 返回体**七段齐全** —— 尤其 unmapped 与 dataQualityNotice，
     它们是"答不出来的部分必须说出来"这条承诺的载体；
  2. 全链路**零剂量数字、零概率数字**。
"""

from __future__ import annotations

import re

import pytest

REQUIRED_SECTIONS = (
    "patient", "careChain", "riskStratification", "assertedFacts",
    "inferredFacts", "sources", "unmapped", "dataQualityNotice", "disclaimer",
)


@pytest.fixture(scope="module")
def client(db, graph):
    from fastapi.testclient import TestClient

    from dmo.api import app

    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True, body
    assert body["patients"] > 0 and body["graphdbTriples"] > 0


def test_root_is_service_entrypoint(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {
        "name": "糖尿病本体 × 患者事实库 融合查询",
        "version": "0.1.0",
        "status": "running",
        "health": "/health",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


def test_list_patients_filters_and_paginates(client):
    r = client.get("/patients", params={"icd10": "E11", "size": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 15, "上游至少有 15 个 E11"
    assert len(body["patients"]) <= 5


def test_list_by_tier(client):
    r = client.get("/patients", params={"tier": "Insufficient-Evidence", "size": 100})
    assert r.status_code == 200
    pids = [p["patientid"] for p in r.json()["patients"]]
    assert any(p.startswith("P00") for p in pids), "真实患者应落在 Insufficient-Evidence"


def test_bundle_has_all_seven_sections(client):
    body = client.get("/patients/P90002").json()
    missing = [k for k in REQUIRED_SECTIONS if k not in body]
    assert not missing, f"返回体缺段：{missing}"
    assert body["disclaimer"], "免责声明不能为空"


def test_unknown_patient_is_404(client):
    assert client.get("/patients/P99999").status_code == 404


def test_assessment_carries_verbatim_source_and_hash(client):
    body = client.get("/patients/P90002/assessment").json()
    srcs = body["sources"]
    assert srcs, "阈值判定必须带出处"
    a1c = [s for s in srcs if "6.5% or above" in s["quote"]]
    assert a1c, f"应引用 A1C 诊断切点原文，实际 {[s['quote'] for s in srcs]}"
    assert re.fullmatch(r"[0-9a-f]{64}", a1c[0]["sha256"]), "出处必须带 sha256"


def test_risk_response_labels_external_standards(client):
    """BMI≥25 的边界来自 WHO，不是本仓库语料 —— 返回体必须说出来。"""
    body = client.get("/patients/P90020/risk").json()
    factors = body["riskStratification"]["contributingFactors"]
    ext = [f for f in factors if f["triggerBasis"] == "external-standard"]
    assert ext, "P90020 有 BMI 类因子，应为 external-standard"
    assert all(f["externalStandardNote"] for f in ext), \
        "external-standard 的因子必须说明边界从哪来"


def test_insufficient_evidence_explains_itself(client):
    """判不了的时候必须说清为什么，而不是返回空。"""
    body = client.get("/patients/P00016/risk").json()
    strat = body["riskStratification"]
    assert strat["tier"] == "Insufficient-Evidence"
    assert strat["insufficientReason"], "Insufficient-Evidence 必须给出理由"
    assert body["dataQualityNotice"], "涉及不可信值时必须给数据质量提示"


def test_explain_gap_is_honest_about_missing_a1c(client):
    body = client.get("/terms/explain", params={"term": "糖化血红蛋白"}).json()
    assert body["upstreamResultRows"] == 0
    assert body["upstreamParentItemOnly"], "它只作为大项名存在，这一点必须报出来"
    joined = " ".join(body["verdicts"])
    assert "没有这个检验的数值" in joined or "语义错位" in joined


def test_templates_reject_free_sparql(client):
    assert client.get("/query/templates").status_code == 200
    r = client.post("/query/does_not_exist", json=["P90002"])
    assert r.status_code == 404
    r = client.post("/query/care_chain", json=[])
    assert r.status_code == 400, "空患者集合必须报错，不能静默返回空"


def test_demo_compare_shows_both_approaches(client):
    body = client.get("/demo/compare", params={"term": "尿蛋白"}).json()
    assert body["baseline"]["links"], "对照组应有链接结果"
    assert body["baseline"]["hasProvenance"] is False
    assert body["ontology"]["mappings"], "本方案应有映射记录"
    assert any(m["verify_status"] == "unmappable" for m in body["ontology"]["mappings"]), \
        "尿蛋白在本方案里应判为 unmappable"


# ── 全链路的硬约束 ──────────────────────────────────────────────────

DOSE = re.compile(r"\d+\s*(mg|g|ml|IU|单位|片|粒)\b(?!/)", re.IGNORECASE)

# ⚠️ 不能简单地禁掉所有百分号。A1C 的单位就是 percent，
#   「6.5% or above」是**逐字的指南原文**，TIR 目标也带 %。
#   要禁的是把数字当**发生概率或时间窗**来讲，所以必须带上下文词。
PROB = re.compile(
    r"(概率|风险|possibility|probability|risk\s*score|发生率|incidence)"
    r"[^。\n]{0,12}\d+(\.\d+)?\s*%"          # 风险 23%
    r"|\d+(\.\d+)?\s*%[^。\n]{0,12}(概率|风险|发生)"   # 23% 的风险
    r"|\d+\s*年(内|后)"                      # 5 年内
    r"|\d+(\.\d+)?\s*倍(风险|危险)"           # 2.3 倍风险
    r"|(probability|risk\s*score)\s*[:=]\s*\d",
    re.IGNORECASE)


@pytest.mark.parametrize("pid", ["P90002", "P90008", "P90020", "P00016"])
def test_no_dosage_and_no_probability_in_any_response(client, pid):
    """schema 层面已经堵死剂量字段，这里再从输出侧兜一道。

    ⚠️ 单位如 mg/dL、mg/g 是**检验单位**不是剂量，正则用 (?!/) 排除。
    """
    import json

    text = json.dumps(client.get(f"/patients/{pid}").json(), ensure_ascii=False)
    dose = DOSE.findall(text)
    prob = PROB.findall(text)
    assert not dose, f"{pid} 的返回体里出现疑似剂量：{dose[:3]}"
    assert not prob, f"{pid} 的返回体里出现概率/时间窗：{prob[:3]}"
