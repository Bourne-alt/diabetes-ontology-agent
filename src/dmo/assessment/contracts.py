from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from ..forecast.contracts import Event, StrictModel

Domain = Literal["glycemic", "renal", "cardiovascular", "hepatic", "safety", "lifestyle"]
DOMAINS = ("glycemic", "renal", "cardiovascular", "hepatic", "safety", "lifestyle")
LABELS = {
    "glycemic": "糖代谢",
    "renal": "肾脏",
    "cardiovascular": "心血管",
    "hepatic": "肝脏",
    "safety": "治疗安全性",
    "lifestyle": "生活方式与实施情况",
}


class AssessmentEvent(Event):
    event_time_known: bool = True
    fact_origin: str | None = None
    source_table: str | None = None
    source_pk: str | None = None
    text: str | None = Field(default=None, max_length=6000)
    metric: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=80)
    domain: Domain = "glycemic"
    context: str = Field(default="unspecified", max_length=100)
    population_context: Literal["NonPregnant", "Pregnant", "unknown"] = "unknown"
    concept_code: str | None = Field(default=None, max_length=150)
    verification: Literal["confirmed", "provisional", "unknown"] = "unknown"
    assertion: Literal["present", "absent", "uncertain"] = "uncertain"
    clinical_status: Literal["active", "resolved", "unknown"] = "unknown"
    value_trust: Literal["verified", "unverified"] = "unverified"
    # Unambiguous treatment exposure evidence, not an order or a report mention.
    action_id: str | None = None
    execution_status: Literal["planned", "ordered", "administered", "self_reported", "unknown"] = (
        "unknown"
    )


class AssessmentSnapshot(StrictModel):
    patient_context: dict[str, str] = Field(default_factory=dict)
    clinical_as_of: AwareDatetime
    knowledge_cutoff: AwareDatetime
    events: list[AssessmentEvent] = Field(max_length=1000)
    source_coverage: dict[Literal["lis", "pacs", "emr", "medication"], str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_snapshot(self):
        ids = [e.event_id for e in self.events]
        versions = [(e.source, e.record_id, e.revision) for e in self.events]
        if len(set(ids)) != len(ids) or len(set(versions)) != len(versions):
            raise ValueError("duplicate event ID or record revision")
        if self.knowledge_cutoff > self.clinical_as_of:
            raise ValueError("knowledge_cutoff must not exceed clinical_as_of")
        return self


class Intervention(StrictModel):
    action_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    kind: Literal["medication", "lifestyle", "device", "other"] = "medication"
    operation: Literal["start", "continue", "stop", "change"] = "start"
    code: str | None = Field(default=None, min_length=1, max_length=150)
    previous_code: str | None = Field(default=None, max_length=150)
    start_at: AwareDatetime
    execution_status: Literal["planned", "ordered", "administered", "self_reported", "unknown"] = (
        "planned"
    )
    supporting_event_ids: list[str] = Field(default_factory=list, max_length=30)
    regimen_reference: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def change_requires_previous(self):
        if self.operation == "change" and not self.previous_code:
            raise ValueError("change requires previous_code")
        return self


class TreatmentAssessmentRequest(StrictModel):
    mode: Literal["prospective", "follow_up"] = "prospective"
    baseline_snapshot: AssessmentSnapshot
    follow_up_snapshot: AssessmentSnapshot | None = None
    interventions: list[Intervention] = Field(default_factory=list, max_length=10)
    assessment_domains: list[Domain] = Field(default_factory=lambda: list(DOMAINS), min_length=1)
    composer: Literal["auto", "template", "llm"] = "auto"
    knowledge_mode: Literal["current", "historical"] = "current"
    max_fact_age_days: int = Field(default=90, ge=1, le=365)
    include_demo_appendix: bool = False
    extract_pacs: bool = False
    language: Literal["zh-CN"] = "zh-CN"

    @model_validator(mode="after")
    def validate_timeline(self):
        if len(set(self.assessment_domains)) != len(self.assessment_domains):
            raise ValueError("duplicate assessment domains")
        ids = [a.action_id for a in self.interventions]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate action_id")
        base = self.baseline_snapshot
        if self.mode == "prospective":
            if self.follow_up_snapshot is not None:
                raise ValueError("prospective must not include follow_up_snapshot")
            if any(
                a.start_at < base.clinical_as_of
                or a.execution_status in {"administered", "self_reported"}
                for a in self.interventions
            ):
                raise ValueError("prospective actions must be future plans or orders")
        else:
            follow = self.follow_up_snapshot
            if follow is None or follow.clinical_as_of <= base.clinical_as_of:
                raise ValueError("follow_up requires a later snapshot")
            if follow.knowledge_cutoff < base.knowledge_cutoff:
                raise ValueError("follow_up knowledge cutoff must not precede baseline")
            if any(
                not base.clinical_as_of <= a.start_at <= follow.clinical_as_of
                for a in self.interventions
            ):
                raise ValueError("action must fall between baseline and follow_up")
            old = {e.event_id: e for e in base.events}
            for e in follow.events:
                if e.event_id in old and e != old[e.event_id]:
                    raise ValueError("event IDs are immutable across snapshots")
            revisions = {(e.source, e.record_id, e.revision): e for e in base.events}
            for e in follow.events:
                key = (e.source, e.record_id, e.revision)
                if key in revisions and e != revisions[key]:
                    raise ValueError("record revisions are immutable across snapshots")
        return self


class NarrativeItem(StrictModel):
    text: str = Field(min_length=1, max_length=1200)
    claim_ids: list[str] = Field(min_length=1, max_length=15)


class Narrative(StrictModel):
    items: list[NarrativeItem] = Field(min_length=1, max_length=20)


class Entailment(StrictModel):
    supported: bool
    # The second pass must explicitly account for every item; no generic yes.
    item_indices: list[int]


class ExtractedFinding(StrictModel):
    event_id: str
    exact_quote: str = Field(min_length=2, max_length=500)
    assertion: Literal["present", "absent", "uncertain"]


class Findings(StrictModel):
    findings: list[ExtractedFinding] = Field(max_length=20)
