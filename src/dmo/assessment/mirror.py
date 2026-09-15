"""Build the assessment input from the canonical patient tables.

The core schema is the patient mirror used by the rest of the DMO API.  It does
not preserve revision/availability timestamps, so this adapter records that
limitation in ``source_coverage`` and uses the clinical event time for all three
timestamp fields.  It never reads the upstream hospital database.
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, date, datetime, time
from urllib.parse import unquote
from zoneinfo import ZoneInfo

from ..config import Config
from ..db.engine import onto_conn
from .contracts import AssessmentSnapshot, TreatmentAssessmentRequest
from .trace import ExecutionTrace

_LAB_DOMAINS = {
    "A1C": "glycemic",
    "FPG": "glycemic",
    "OGTT2H": "glycemic",
    "RPG": "glycemic",
    "GCT1H": "glycemic",
    "GLU": "glycemic",
    "KETONE": "glycemic",
    "UACR": "renal",
    "EGFR": "renal",
    "CREAT": "renal",
    "BUN": "renal",
    "UPRO": "renal",
    "ALT": "hepatic",
    "AST": "hepatic",
    "CHOL": "cardiovascular",
    "TG": "cardiovascular",
}


def _aware(value: datetime | date | None, fallback: datetime) -> datetime:
    if value is None:
        return fallback
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, time.min)
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(os.getenv("DMO_PATIENT_TIMEZONE", "Asia/Taipei")))
    return value.astimezone(UTC)


def _code(iri: str | None, fallback: str | None = None) -> str | None:
    if not iri:
        return fallback
    return unquote(iri.rstrip("/").rsplit("/", 1)[-1])


def _status(value: str | None) -> str:
    normalized = (value or "").casefold()
    if normalized in {"preliminary", "prelim"}:
        return "preliminary"
    if normalized in {"retracted", "cancelled", "canceled"}:
        return "retracted"
    return "final"


def _domain_for_condition(code: str | None) -> str:
    value = (code or "").casefold()
    if value in {"bmi", "smokingstatus", "physicalactivityperweek"}:
        return "lifestyle"
    if any(token in value for token in ("ckd", "dkd", "kidney", "renal", "nephro", "albumin")):
        return "renal"
    if any(token in value for token in ("heart", "cardio", "cvd", "stroke", "vascular")):
        return "cardiovascular"
    if any(token in value for token in ("liver", "hepatic")):
        return "hepatic"
    return "glycemic"


def _population_context(observations: list[dict], at: datetime) -> str:
    pregnancy = [r for r in observations if r["observation_type"] == "PregnancyStatus"
                 and r["trust_level"] in {"Attested", "Curated"}
                 and r["status"] == "Final" and r["observed_at"] is not None
                 and 0 <= (at - _aware(r["observed_at"], at)).total_seconds() <= 90 * 86400]
    if not pregnancy:
        return "unknown"
    latest = max(
        pregnancy,
        key=lambda r: _aware(r["observed_at"], datetime.min.replace(tzinfo=UTC)),
    )
    same_time = [r for r in pregnancy if r["observed_at"] == latest["observed_at"]]
    values = {str(r["value_text"] if r["value_text"] is not None else r["value_decimal"]).casefold()
              for r in same_time}
    if len(values) != 1:
        return "unknown"
    value = values.pop()
    if value in {"true", "yes", "pregnant", "1", "是", "孕"}:
        return "Pregnant"
    if value in {"false", "no", "not pregnant", "notpregnant", "0", "否", "未孕"}:
        return "NonPregnant"
    return "unknown"


def build_request(cfg: Config, patient_id: str, *, trace: ExecutionTrace | None = None) -> TreatmentAssessmentRequest:
    """Create a current, prospective assessment request for one mirrored patient."""
    now = datetime.now(UTC)
    with onto_conn(cfg) as conn:
        patient = conn.fetchone(
            "SELECT patientid, fact_origin, projected_at FROM diabetes.core_patient "
            "WHERE patientid = %s",
            (patient_id,),
        )
        if patient is None:
            raise KeyError(patient_id)
        labs = conn.fetchall(
            "SELECT lab_result_id, lab_test_code, result_value, result_unit, collected_at, "
            "trust_level, fact_origin, source_table, source_pk "
            "FROM diabetes.core_lab_result WHERE patientid = %s ORDER BY lab_result_id",
            (patient_id,),
        )
        observations = conn.fetchall(
            "SELECT observation_id, observation_type, value_decimal, value_text, unit_code, "
            "observed_at, status, trust_level, fact_origin, source_table, source_pk "
            "FROM diabetes.core_observation WHERE patientid = %s ORDER BY observation_id",
            (patient_id,),
        )
        diagnoses = conn.fetchall(
            "SELECT diagnosis_id, diagnosis_kind, clinical_status, verification_status, "
            "external_code, type_iri, complication_iri, diagnosed_date, "
            "fact_origin, source_table, source_pk FROM "
            "diabetes.core_diagnosis WHERE patientid = %s ORDER BY diagnosis_id",
            (patient_id,),
        )
        medications = conn.fetchall(
            "SELECT medication_use_id, medication_iri, medication_name, start_date, end_date, "
            "status, fact_origin, source_table, source_pk FROM diabetes.core_medication_use "
            "WHERE patientid = %s ORDER BY medication_use_id",
            (patient_id,),
        )
    if trace:
        trace.record("mirror_read", "读取患者镜像", "按患者编号读取规范事实表。", {
            "patient_id": patient_id, "fact_origin": patient["fact_origin"],
            "tables": {"core_lab_result": len(labs), "core_observation": len(observations),
                       "core_diagnosis": len(diagnoses), "core_medication_use": len(medications)},
        })

    # Population context must be known at each measurement, not borrowed from a later record.
    events: list[dict] = []
    for row in labs:
        occurred = _aware(row["collected_at"], now)
        metric = row["lab_test_code"]
        events.append(
            {
                "event_id": "lis:" + row["lab_result_id"],
                "patient_id": patient_id,
                "source": "lis",
                "record_id": row["lab_result_id"],
                "revision": 1,
                "event_time": occurred,
                **_metadata(row, row["collected_at"]),
                "available_at": occurred,
                "ingested_at": occurred,
                "metric": metric,
                "value": float(row["result_value"]),
                "unit": row["result_unit"],
                "domain": _LAB_DOMAINS.get(metric, "safety"),
                "context": "fasting" if metric == "FPG" else "unspecified",
                "population_context": _population_context(observations, occurred),
                "value_trust": (
                    "verified" if row["trust_level"] in {"Attested", "Curated"} else "unverified"
                ),
            }
        )
    for row in observations:
        occurred = _aware(row["observed_at"], now)
        kind = row["observation_type"]
        events.append(
            {
                "event_id": "emr-observation:" + row["observation_id"],
                "patient_id": patient_id,
                "source": "emr",
                "record_id": "observation:" + row["observation_id"],
                "revision": 1,
                "event_time": occurred,
                **_metadata(row, row["observed_at"]),
                "available_at": occurred,
                "ingested_at": occurred,
                "status": _status(row["status"]),
                "text": row["value_text"],
                "metric": kind if row["value_decimal"] is not None else None,
                "value": float(row["value_decimal"]) if row["value_decimal"] is not None else None,
                "unit": row["unit_code"],
                "domain": _domain_for_condition(kind),
                "context": "routine",
                "population_context": "unknown",
                "concept_code": kind,
                "assertion": "uncertain",
                "value_trust": (
                    "verified" if row["trust_level"] in {"Attested", "Curated"} else "unverified"
                ),
            }
        )
    for row in diagnoses:
        occurred = _aware(row["diagnosed_date"], now)
        concept = _code(row["complication_iri"]) or _code(row["type_iri"]) or row["external_code"]
        events.append(
            {
                "event_id": "emr-diagnosis:" + row["diagnosis_id"],
                "patient_id": patient_id,
                "source": "emr",
                "record_id": "diagnosis:" + row["diagnosis_id"],
                "revision": 1,
                "event_time": occurred,
                **_metadata(row, row["diagnosed_date"]),
                "available_at": occurred,
                "ingested_at": occurred,
                "domain": _domain_for_condition(concept),
                "context": "routine",
                "population_context": "unknown",
                "concept_code": concept,
                "text": row["external_code"] or row["diagnosis_kind"],
                "verification": (
                    {"confirmed": "confirmed", "provisional": "provisional"}.get(
                        str(row["verification_status"]).casefold(), "unknown")
                ),
                "assertion": "present",
                "clinical_status": (
                    {"active": "active", "resolved": "resolved"}.get(
                        str(row["clinical_status"]).casefold(), "unknown")
                ),
                "value_trust": "verified",
            }
        )

    interventions = []
    for row in medications:
        code = _code(row["medication_iri"], row["medication_name"])
        event_id = "medication:" + row["medication_use_id"]
        action_id = "MED-" + hashlib.sha256(row["medication_use_id"].encode()).hexdigest()[:20]
        occurred = _aware(row["start_date"], now)
        events.append(
            {
                "event_id": event_id,
                "patient_id": patient_id,
                "source": "medication",
                "record_id": event_id,
                "revision": 1,
                "event_time": occurred,
                **_metadata(row, row["start_date"]),
                "available_at": occurred,
                "ingested_at": occurred,
                "domain": "safety",
                "context": "current-treatment",
                "population_context": "unknown",
                "concept_code": code,
                "action_id": action_id,
                "execution_status": "unknown",
                "text": row["medication_name"] + "；记录状态：" + row["status"],
                "assertion": "present",
                "clinical_status": "unknown",
                "value_trust": "verified",
            }
        )
        if (str(row["status"]).casefold() != "active" or occurred > now
                or (row["end_date"] is not None and _aware(row["end_date"], now) < now)):
            continue
        interventions.append(
            {
                "action_id": action_id,
                "kind": "medication",
                "operation": "continue",
                "code": code,
                "start_at": now,
                "execution_status": "unknown",
                "supporting_event_ids": [event_id],
            }
        )

    snapshot = AssessmentSnapshot.model_validate(
        {
            "clinical_as_of": now,
            "knowledge_cutoff": now,
            "events": events,
            "patient_context": {"patient_id": patient_id, "fact_origin": patient["fact_origin"]},
            "source_coverage": {
                "lis": "core_lab_result patient mirror; availability/revision metadata unavailable",
                "medication": "core_medication_use：仅 Active 且未过期记录用于继续措施的条件评估，非继续用药建议；实际实施未知",
                "pacs": "not represented in the current core patient mirror",
                "emr": "core_observation/core_diagnosis：缺失发生时间以镜像读取时点占位，不参与时序判断；无修订/发布历史；无时区时间按 DMO_PATIENT_TIMEZONE（默认 Asia/Taipei）解释",
            },
        }
    )
    request = TreatmentAssessmentRequest(
        mode="prospective",
        baseline_snapshot=snapshot,
        interventions=interventions,
        composer="template",
    )
    if trace:
        trace.record("mirror_map", "组装时序事件与措施", "保留单位、可信度、来源和时间缺口；仅提取当前 Active 用药。", {
            "events": [e.model_dump(mode="json") for e in snapshot.events],
            "interventions": [a.model_dump(mode="json") for a in request.interventions],
            "source_coverage": snapshot.source_coverage,
        })
    return request


def _metadata(row: dict, timestamp) -> dict:
    return {
        "event_time_known": timestamp is not None,
        "fact_origin": row.get("fact_origin"),
        "source_table": row.get("source_table"),
        "source_pk": row.get("source_pk"),
    }
