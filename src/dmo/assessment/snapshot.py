import hashlib
import json
from dataclasses import dataclass

from .contracts import AssessmentEvent, AssessmentSnapshot


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


@dataclass(frozen=True)
class PatientState:
    snapshot: AssessmentSnapshot
    fingerprint: str
    events: tuple[AssessmentEvent, ...]
    excluded: tuple[dict, ...]


def build_state(patient_id: str, snapshot: AssessmentSnapshot) -> PatientState:
    if any(e.patient_id != patient_id for e in snapshot.events):
        raise ValueError("snapshot contains a different patient")
    payload = snapshot.model_dump(mode="json")
    payload["events"].sort(key=lambda e: e["event_id"])
    known = {}
    excluded = []
    for e in sorted(snapshot.events, key=lambda x: (x.source, x.record_id, x.revision)):
        if e.available_at > snapshot.knowledge_cutoff or e.ingested_at > snapshot.knowledge_cutoff:
            excluded.append({"event_id": e.event_id, "code": "NOT_YET_KNOWN"})
            continue
        key = (e.source, e.record_id)
        if key in known:
            excluded.append({"event_id": known[key].event_id, "code": "SUPERSEDED"})
        known[key] = e
    visible = []
    for e in known.values():
        if e.status != "final" or e.event_time > snapshot.clinical_as_of:
            excluded.append({"event_id": e.event_id, "code": "NOT_USABLE"})
        else:
            visible.append(e)
    return PatientState(
        snapshot,
        digest(payload),
        tuple(sorted(visible, key=lambda e: (e.event_time, e.event_id))),
        tuple(excluded),
    )


def recent(state: PatientState, age_days: int) -> list[AssessmentEvent]:
    return [
        e
        for e in state.events
        if e.event_time_known
        and (state.snapshot.clinical_as_of - e.event_time).total_seconds() <= age_days * 86400
    ]
