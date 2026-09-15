"""Point-in-time filtering and reproducible untrained scenario arithmetic.

No database writes, external model calls, or imports from the existing simulate service.
The randomly initialized coefficient has no learned pharmacological meaning.
"""

import hashlib
import json
from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException

from ..domain import ONTOLOGY_SHA256
from ..domain.generated import ClinicalObservation, LabResult, MedicationUse
from .contracts import ForecastRequest
from .model import InitializedResponseModel

MODEL_VERSION = InitializedResponseModel.version
NOTICE = (
    "未经训练的初始化模型；数值仅用于验证模拟流程，不代表药物疗效、"
    "患者真实预后或医疗建议。未执行临床适用性或禁忌校验。"
)


def forecast(patient_id: str, request: ForecastRequest, *, trace=None) -> dict:
    snap = request.snapshot
    if any(e.patient_id != patient_id for e in snap.events):
        raise HTTPException(422, "snapshot contains a different patient")
    payload = request.model_dump(mode="json")
    payload["snapshot"]["events"].sort(key=lambda e: e["event_id"])
    fingerprint = hashlib.sha256(
        json.dumps(
            [patient_id, payload, MODEL_VERSION, ONTOLOGY_SHA256],
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    out = {
        "status": "ok",
        "prediction_kind": "untrained_demo",
        "trained": False,
        "clinically_validated": False,
        "model_version": MODEL_VERSION,
        "ontology_sha256": ONTOLOGY_SHA256,
        "run_hash": fingerprint,
        "clinical_as_of": snap.clinical_as_of.isoformat(),
        "knowledge_cutoff": snap.knowledge_cutoff.isoformat(),
        "action": request.action.model_dump(mode="json"),
        "comparator": {"operation": "continue_existing_care"},
        "predictions": [],
        "estimated_treatment_effect": None,
        "explanations": [],
        "disclaimer": NOTICE,
    }
    reasons = out["explanations"]
    versions = {}
    for e in sorted(snap.events, key=lambda event: event.event_id):
        if e.available_at > snap.knowledge_cutoff or e.ingested_at > snap.knowledge_cutoff:
            reasons.append(
                {
                    "code": "NOT_YET_KNOWN",
                    "event_ids": [e.event_id],
                    "statement": "报告或入库时间晚于知识截点，排除。",
                }
            )
            continue
        key = (e.source, e.record_id)
        if key not in versions or e.revision > versions[key].revision:
            versions[key] = e
    visible = []
    for e in versions.values():
        if e.status != "final" or e.event_time > snap.clinical_as_of:
            reasons.append(
                {
                    "code": "NOT_USABLE",
                    "event_ids": [e.event_id],
                    "statement": "撤回、初步报告或未来事件不作为观测输入。",
                }
            )
        else:
            visible.append(e)
    visible.sort(key=lambda e: (e.event_time, e.event_id))
    out["snapshot_event_ids"] = [e.event_id for e in visible]
    # Materialize ontology projections; metadata and provenance stay in the event envelope.
    entities = []
    for e in visible:
        if e.source == "lis":
            entity = LabResult(
                iri="urn:event:" + e.event_id,
                lab_result_id=e.record_id,
                collected_at=e.event_time,
                result_unit=e.unit,
                result_value=Decimal(str(e.value)) if e.value is not None else None,
            )
        elif e.source == "medication":
            entity = MedicationUse(iri="urn:event:" + e.event_id, medication_use_id=e.record_id)
        else:
            entity = ClinicalObservation(
                iri="urn:event:" + e.event_id,
                observation_id=e.record_id,
                observed_at=e.event_time,
                value_text=e.text,
            )
        entities.append({"event_id": e.event_id, "class_iri": entity.ontology_iri})
    out["mapped_entities"] = entities
    out["unused_event_ids"] = [e.event_id for e in visible if e.source != "lis"]
    reasons.append(
        {
            "code": "MODEL_SCOPE",
            "statement": (
                "初始化模型只使用同口径空腹血糖基线。PACS/其他事件仅保留出处，"
                "未参与数值计算；随机参数没有药品特异性，也不能解释病因。"
            ),
        }
    )
    if not request.action.medication_code:
        out["status"] = "needs_clarification"
        reasons.append({"code": "MEDICATION_REQUIRED", "statement": "请提供明确的药品编码。"})
        return out
    if request.action.operation != "start":
        out["status"] = "unsupported_scenario"
        reasons.append({"code": "UNSUPPORTED_ACTION", "statement": "当前推演仅支持 start。"})
        return out
    candidates = [
        e
        for e in visible
        if e.source == "lis"
        and e.metric == request.target.metric
        and e.unit == request.target.unit
        and e.value is not None
        and e.value > 0
        and snap.clinical_as_of - e.event_time
        <= timedelta(days=request.target.max_baseline_age_days)
    ]
    if not candidates:
        out["status"] = "insufficient_data"
        reasons.append(
            {
                "code": "NO_RECENT_COMPARABLE_BASELINE",
                "statement": "没有有效窗口内、单位为 mmol/L 的正值 FPG 最终报告。",
            }
        )
        return out
    baseline = candidates[-1]
    # Zero drift at initialization; a random untrained action coefficient can raise or lower Y.
    model = InitializedResponseModel.initialize(request.seed)
    coefficient = model.coefficient
    out["baseline"] = {
        "value": baseline.value,
        "unit": baseline.unit,
        "event_id": baseline.event_id,
        "event_time": baseline.event_time.isoformat(),
    }
    reasons.append(
        {
            "code": "INITIALIZED_PARAMETER",
            "event_ids": [baseline.event_id],
            "statement": "以该基线乘以初始化响应函数；符号和幅度由种子决定，非学习结果。",
            "coefficient": coefficient,
            "seed": request.seed,
            "formula": "baseline * (1 + coefficient * (1 - exp(-elapsed_days/14)))",
        }
    )
    offset = (request.action.start_at - snap.clinical_as_of).total_seconds() / 86400
    if trace is not None:
        trace.record("initialization", "初始化数值模型", "基线通过检查后初始化随机系数；没有训练或药物特异参数。", {
            "trained": False, "seed": request.seed, "coefficient": coefficient,
            "baseline": out["baseline"], "explanations": list(reasons),
        })
    for h in sorted(request.target.horizons_days):
        elapsed = max(0.0, h - offset)
        calculation = model.components(baseline.value, elapsed)
        value = calculation["value"]
        out["predictions"].append(
            {
                "horizon_days": h,
                "calculation": calculation,
                "predicted_at": (snap.clinical_as_of + timedelta(days=h)).isoformat(),
                "metric": request.target.metric,
                "unit": request.target.unit,
                "simulated_value": round(value, 6),
                "change_from_baseline": round(value - baseline.value, 6),
                "reduction_from_baseline": round(baseline.value - value, 6),
                "comparator_simulated_value": baseline.value,
                "prediction_interval": None,
                "estimated_treatment_effect": None,
            }
        )
        if trace is not None:
            trace.record("horizon_" + str(h), f"计算第 {h} 天", "实际执行的指数响应算式与中间数值。", out["predictions"][-1])
    return out
