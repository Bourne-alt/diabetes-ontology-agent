"""Explicit, isolated untrained numerical demonstration for owned demo patients."""

from decimal import Decimal

from fastapi import HTTPException

from ..db.engine import onto_conn
from ..forecast.contracts import ForecastRequest
from ..forecast.service import forecast
from .demo import PREFIX, SCENARIOS
from .mirror import build_request
from .trace import ExecutionTrace


def run(cfg, pid):
    if pid not in {s["pid"] for s in SCENARIOS}:
        raise HTTPException(400, "数值推演仅允许本模块的合成患者")
    trace = ExecutionTrace()
    with onto_conn(cfg) as conn:
        patient = conn.fetchone("SELECT fact_origin, demo_scenario FROM diabetes.core_patient WHERE patientid = %s", (pid,))
        if not patient:
            raise HTTPException(404, "请先加载合成患者")
        if patient["fact_origin"] != "demo-cohort" or patient["demo_scenario"] != PREFIX + pid:
            raise HTTPException(400, "患者来源不是此模块的合成数据")
        conversion = conn.fetchone(
            "SELECT conv_factor, conv_offset, unit_target FROM diabetes.map_unit_conversion "
            "WHERE concept_iri = %s AND unit_src = %s",
            ("https://example.org/dmo/id/LabTest-FPG", "mmol-per-L"),
        )
    request = build_request(cfg, pid, trace=trace)
    snap = request.baseline_snapshot
    candidates = [e for e in snap.events if e.source == "lis" and e.metric == "FPG"
                  and e.value_trust == "verified" and e.event_time_known]
    events = []
    conversions = []
    for e in candidates:
        value = e.value
        if e.unit == "mg-per-dL":
            if not conversion or conversion["unit_target"] != "mg-per-dL" or not conversion["conv_factor"]:
                continue
            value = float((Decimal(str(value)) - Decimal(str(conversion["conv_offset"] or 0)))
                          / Decimal(str(conversion["conv_factor"])))
            conversions.append({"event_id": e.event_id, "original_value": e.value,
                                "original_unit": e.unit, "converted_value": value, "unit": "mmol/L",
                                "factor": str(conversion["conv_factor"]), "source": "map_unit_conversion"})
        elif e.unit not in {"mmol-per-L", "mmol/L"}:
            continue
        events.append({**e.model_dump(include={"event_id", "patient_id", "source", "record_id", "revision",
                                               "event_time", "available_at", "ingested_at", "status", "metric"}),
                       "value": value, "unit": "mmol/L"})
    trace.record("features", "筛选数值推演的基线", "只使用可信、有发生时间的 FPG；依据登记表还原单位，其他维度不进入数值模型。", {
        "candidate_count": len(candidates), "accepted_count": len(events), "conversions": conversions})
    # This is a displayed synthetic action, never extracted as a patient's actual treatment.
    result = forecast(pid, ForecastRequest.model_validate({
        "snapshot": {"clinical_as_of": snap.clinical_as_of, "knowledge_cutoff": snap.knowledge_cutoff, "events": events},
        "action": {"operation": "start", "medication_code": "external-demo-drug", "start_at": snap.clinical_as_of},
        "seed": 42,
    }), trace=trace)
    if not result["predictions"]:
        trace.record("input_check", "检查推演输入", "输入不足，未初始化模型或执行数值计算。", {
            "status": result["status"], "explanations": result["explanations"]})
    trace.record("demo_result", "输出独立数值推演", result["disclaimer"], {
        "status": result["status"], "estimated_treatment_effect": None,
        "predictions": result["predictions"], "run_hash": result["run_hash"]})
    return {**result, "execution_trace": trace.export()}
