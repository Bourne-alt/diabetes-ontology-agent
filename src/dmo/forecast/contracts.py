from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Event(StrictModel):
    event_id: str = Field(min_length=1)
    patient_id: str = Field(min_length=1)
    source: Literal["lis", "pacs", "emr", "medication"]
    record_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    event_time: AwareDatetime
    available_at: AwareDatetime
    ingested_at: AwareDatetime
    status: Literal["final", "preliminary", "retracted"] = "final"
    metric: str | None = None
    value: float | None = None
    unit: str | None = None
    text: str | None = None

    @model_validator(mode="after")
    def times(self):
        if self.ingested_at < self.available_at:
            raise ValueError("ingested_at must not precede available_at")
        if self.source in {"lis", "pacs"} and self.available_at < self.event_time:
            raise ValueError("report availability must not precede measurement")
        return self


class Snapshot(StrictModel):
    clinical_as_of: AwareDatetime
    knowledge_cutoff: AwareDatetime
    events: list[Event] = Field(max_length=10000)

    @model_validator(mode="after")
    def unique_versions(self):
        ids = [e.event_id for e in self.events]
        keys = [(e.source, e.record_id, e.revision) for e in self.events]
        if len(set(ids)) != len(ids) or len(set(keys)) != len(keys):
            raise ValueError("duplicate event ID or record revision")
        if self.knowledge_cutoff > self.clinical_as_of:
            raise ValueError("knowledge_cutoff must not exceed prediction origin")
        return self


class Action(StrictModel):
    operation: Literal["start", "continue", "stop", "change"] = "start"
    medication_code: str | None = Field(default=None, min_length=1)
    start_at: AwareDatetime
    regimen_reference: str | None = None


class Target(StrictModel):
    metric: Literal["FPG"] = "FPG"
    unit: Literal["mmol/L"] = "mmol/L"
    horizons_days: list[int] = Field(
        default_factory=lambda: [7, 14, 28], min_length=1, max_length=10
    )
    max_baseline_age_days: int = Field(default=7, ge=1, le=90)

    @model_validator(mode="after")
    def horizons(self):
        if any(h < 1 or h > 90 for h in self.horizons_days):
            raise ValueError("demo horizons must be between 1 and 90 days")
        if len(set(self.horizons_days)) != len(self.horizons_days):
            raise ValueError("duplicate horizons")
        return self


class ForecastRequest(StrictModel):
    snapshot: Snapshot
    action: Action
    target: Target = Field(default_factory=Target)
    model: Literal["untrained_demo"] = "untrained_demo"
    seed: int = Field(default=42, ge=0, le=2147483647)

    @model_validator(mode="after")
    def action_time(self):
        if self.action.start_at < self.snapshot.clinical_as_of:
            raise ValueError("hypothetical action must start at or after clinical_as_of")
        return self
