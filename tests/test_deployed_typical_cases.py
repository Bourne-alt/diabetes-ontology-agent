"""部署后典型场景回归测试。

这些用例来自 GraphDB 中现有的 P900xx 演示患者，但预期值是独立写死的业务契约，
不是运行时从图库反查后再与图库自身比较。这样才能发现患者图漏同步、规则未物化、
接口字段漏返回等部署问题。

默认跳过，避免普通 ``pytest`` 意外访问外部服务。显式指定部署地址后运行：

    DMO_TEST_BASE_URL=http://124.223.18.44:8100 \
      uv run pytest tests/test_deployed_typical_cases.py -q
"""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

import pytest

BASE_URL = os.getenv("DMO_TEST_BASE_URL", "").rstrip("/")
OPENER = build_opener(ProxyHandler({}))
pytestmark = pytest.mark.skipif(
    not BASE_URL,
    reason="设置 DMO_TEST_BASE_URL 后才运行部署环境回归测试",
)


def _request(path: str, body: dict | list | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    try:
        # 部署探测必须直连显式给出的目标；继承开发机代理会把测试变成代理探测。
        with OPENER.open(request, timeout=30) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def _get(path: str) -> dict:
    status, body = _request(path)
    assert status == 200, body
    return body


def _inferred(body: dict, fact_type: str) -> list[dict]:
    return [fact for fact in body["inferredFacts"] if fact["type"] == fact_type]


def test_health_is_backed_by_patient_graphs():
    """总三元组数非零还不够，必须真的能读到患者命名图。"""
    health = _get("/health")
    assert health["ok"] is True
    assert health["patients"] >= 430

    patient = _get("/patients/P90002")
    assert patient["careChain"], "SQL 有患者但 careChain 为空：患者图可能未同步"
    assert any(row["kind"] == "LabResult" for row in patient["careChain"])


@pytest.mark.parametrize(
    "pid,expected_conclusion,expected_verification",
    [
        ("P90002", "DiabetesRange", "Provisional"),
        ("P90003", "DiabetesRange", "Confirmed"),
        ("P90010", "Prediabetes", None),
        ("P90017", "Prediabetes", None),  # A1C 5.7：闭下界
        ("P90018", "Prediabetes", None),  # A1C 6.4：闭上界
        ("P90019", "DiabetesRange", "Provisional"),  # A1C 6.5：闭下界
    ],
)
def test_diagnostic_threshold_typical_cases(
    pid: str,
    expected_conclusion: str,
    expected_verification: str | None,
):
    body = _get(f"/patients/{pid}/assessment")
    conclusions = {fact["conclusion"] for fact in _inferred(body, "dmo:Assessment")}
    assert expected_conclusion in conclusions

    if expected_verification:
        derived = [
            fact for fact in _inferred(body, "dmo:Diagnosis")
            if fact["factOrigin"] == "derived"
        ]
        assert expected_verification in {fact["verificationStatus"] for fact in derived}


def test_verified_unit_conversion_is_visible_in_care_chain():
    """P90012 的 7.8 mmol/L 应换算为约 140.54 mg/dL。"""
    body = _get("/patients/P90012")
    fpg = [
        row for row in body["careChain"]
        if row["kind"] == "LabResult" and row["label"] == "FPG"
    ]
    assert len(fpg) == 1
    assert fpg[0]["unit"] == "mg-per-dL"
    assert float(fpg[0]["value"]) == pytest.approx(140.54, abs=0.01)


def test_unverified_value_does_not_drive_assessment():
    """P90026 的 A1C 9.1% 为 Unverified，不得参与阈值判定。"""
    body = _get("/patients/P90026/assessment")
    assert not _inferred(body, "dmo:Assessment")
    assert body["dataQualityNotice"]


def test_absolute_contraindication_is_exposed_by_safety_endpoint():
    """P90008（肾衰竭 + 恩格列净）必须暴露 Absolute 标记及依据。"""
    body = _get("/patients/P90008/safety")
    safety = body.get("safety", [])
    assert any(item["severity"] == "Absolute" for item in safety)
    assert any("severe kidney problems" in item["rationale"] for item in safety)


def test_negative_safety_control_has_no_absolute_flag():
    """P90009（肾衰竭 + 二甲双胍）是反例，不得凭空升级为 Absolute。"""
    body = _get("/patients/P90009/safety")
    assert all(item["severity"] != "Absolute" for item in body.get("safety", []))


@pytest.mark.parametrize(
    "pid,expected_tier",
    [
        ("P90008", "High"),
        ("P90023", "High"),
        ("P90025", "Moderate"),
        ("P90024", "Low"),
        ("P90022", "Insufficient-Evidence"),
    ],
)
def test_risk_stratification_typical_cases(pid: str, expected_tier: str):
    body = _get(f"/patients/{pid}/risk")
    assert body["riskStratification"]["tier"] == expected_tier


def test_simulation_promotes_second_day_to_confirmed():
    """P90002 补另一天 A1C 复测，只改变沙箱结论，不污染真实患者图。"""
    status, body = _request(
        "/patients/P90002/simulate",
        {"assume": [{
            "term": "A1C",
            "value": 7.9,
            "unit": "percent",
            "date": "2026-02-20",
        }]},
    )
    assert status == 200, body
    changed = [
        item for item in body["delta"]
        if item["change"] == "changed" and item["type"] == "Diagnosis"
    ]
    assert changed
    verification = changed[0]["fields"]["verificationStatus"]
    assert verification == {"before": "Provisional", "after": "Confirmed"}
    assert all(fact["hypothetical"] is True for fact in body["hypotheticalFacts"])


def test_unknown_patient_is_404():
    status, _ = _request("/patients/P99999")
    assert status == 404
