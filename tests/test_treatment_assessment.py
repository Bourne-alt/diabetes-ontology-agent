import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from dmo.api import app
from dmo.assessment.composer import ProviderError, safe_claims
from dmo.assessment.contracts import Narrative, TreatmentAssessmentRequest
from dmo.assessment.evidence import KnowledgeStore
from dmo.assessment.service import assess
from dmo.assessment.settings import ModelSettings
from dmo.assessment.snapshot import build_state
from dmo.assessment.storage import archive
from dmo.assessment.validators import NarrativeError, validate_narrative
from dmo.rdf.canonical import passage_hash


def event(event_id="lab1", **changes):
    data = {
        "event_id": event_id,
        "patient_id": "SYNTHETIC",
        "record_id": event_id,
        "revision": 1,
        "source": "lis",
        "domain": "glycemic",
        "event_time": "2026-09-01T08:00:00+08:00",
        "available_at": "2026-09-01T09:00:00+08:00",
        "ingested_at": "2026-09-01T09:01:00+08:00",
        "metric": "A1C",
        "value": 8.0,
        "unit": "percent",
        "context": "routine",
        "population_context": "NonPregnant",
        "value_trust": "verified",
    }
    data.update(changes)
    return data


def sample():
    return {
        "composer": "template",
        "baseline_snapshot": {
            "clinical_as_of": "2026-09-01T10:00:00+08:00",
            "knowledge_cutoff": "2026-09-01T10:00:00+08:00",
            "events": [
                event(),
                event(
                    "dx",
                    source="emr",
                    domain="renal",
                    value=None,
                    metric=None,
                    unit=None,
                    concept_code="CKD",
                    verification="confirmed",
                    assertion="present",
                    clinical_status="active",
                ),
            ],
        },
        "interventions": [
            {"action_id": "new-med", "code": "metformin", "start_at": "2026-09-01T10:00:00+08:00"}
        ],
    }


@pytest.fixture
def knowledge(tmp_path):
    # Deliberately synthetic source text; portable tests need no ignored clinical corpus.
    src = tmp_path / "ontology/src"
    docs = tmp_path / "ontology/knowledges"
    src.mkdir(parents=True)
    docs.mkdir()
    quote = "Synthetic threshold 6.5 or above"
    docs.joinpath("test-source.txt").write_text(quote)
    docs.joinpath("fda-diabetes-drug-classes.txt").write_text(
        "Synthetic test fixture\nHow do they work? Synthetic mechanism.\n"
        "Test\tmetformin\nSynthetic kidney caution.\n"
        "Talk to your doctor about your kidney health in this synthetic fixture.\n"
        "Check the FDA website\n"
    )
    src.joinpath("dmo-threshold-seed.ttl").write_text(
        '''
@prefix d: <https://example.org/dmo#> .
@prefix i: <https://example.org/dmo/id/> .
i:test d:labTestCode "A1C"; d:hasThreshold i:threshold .
i:threshold d:thresholdId "TEST-A1C"; d:classification "Diabetes";
  d:lowerBound 6.5; d:lowerOperator "GTE"; d:upperOperator "None";
  d:populationContext "NonPregnant"; d:boundUnit "percent";
  d:thresholdCitesPassage i:passage .
i:passage d:quote "'''
        + quote
        + '''"; d:contentHash "'''
        + passage_hash(quote)
        + """" .
<https://example.org/dmo/id/source/test-source> d:hasPassage i:passage .
"""
    )
    src.joinpath("dmo-axioms.ttl").write_text("""
@prefix d: <https://example.org/dmo#> .
@prefix i: <https://example.org/dmo/id/> .
i:metformin a d:Medication; d:medicationCode "metformin"; d:belongsToDrugClass i:biguanide .
i:biguanide d:hasContraindication i:caution .
i:caution d:contraCode "TEST-RENAL"; d:severity "Caution";
  d:triggeredByCondition i:CKD; d:rationale "Synthetic kidney caution." .
""")
    return KnowledgeStore(tmp_path)


def run(body, knowledge, **kwargs):
    return assess(
        "SYNTHETIC", TreatmentAssessmentRequest.model_validate(body), knowledge=knowledge, **kwargs
    )


def test_multidomain_report_evidence_and_mapping(knowledge):
    report = run(sample(), knowledge)
    rules = [c for c in report["claims"] if c["kind"] == "rule_conclusion"]
    assert {c["rule_id"] for c in rules} == {"TEST-A1C", "TEST-RENAL"}
    evidence = {e["evidence_id"]: e for e in report["evidence"]}
    for claim in report["claims"]:
        assert all(ref in evidence for ref in claim["evidence_ids"])
    assert report["monitoring"] and report["demo_appendix"] == []
    assert any(d["status"] == "unknown" for d in report["domains"])
    assert "综合评估报告" in report["rendered_markdown"]
    assert all("entity" in entity for entity in report["mapped_entities"])


def test_late_revision_and_retraction(knowledge):
    body = sample()
    revised = event(
        "correction",
        record_id="lab1",
        revision=2,
        value=4.0,
        available_at="2026-09-01T11:00:00+08:00",
        ingested_at="2026-09-01T11:01:00+08:00",
    )
    body["baseline_snapshot"]["events"].append(revised)
    assert any(c["rule_id"] == "TEST-A1C" for c in run(body, knowledge)["claims"])
    revised.update(
        available_at="2026-09-01T09:30:00+08:00",
        ingested_at="2026-09-01T09:31:00+08:00",
        status="retracted",
    )
    report = run(body, knowledge)
    assert not any(c["rule_id"] == "TEST-A1C" for c in report["claims"])
    assert len(report["snapshot_refs"]["baseline"]["excluded"]) == 2


@pytest.mark.parametrize(
    "field,value",
    [("assertion", "absent"), ("verification", "provisional"), ("clinical_status", "resolved")],
)
def test_no_confirmed_risk_from_negation_or_provisional(knowledge, field, value):
    body = sample()
    body["baseline_snapshot"]["events"][1][field] = value
    report = run(body, knowledge)
    assert not any(
        c["rule_id"] == "TEST-RENAL" and c["kind"] == "rule_conclusion" for c in report["claims"]
    )


def test_pacs_quote_preserved_and_not_promoted_to_diagnosis(knowledge):
    body = sample()
    body["baseline_snapshot"]["events"].append(
        event(
            "pacs1",
            source="pacs",
            domain="cardiovascular",
            value=None,
            text="未见心脏扩大，局部发现性质待定。",
            assertion="uncertain",
        )
    )
    report = run(body, knowledge)
    claims = [c for c in report["claims"] if "未见心脏扩大" in c["statement"]]
    assert claims[0]["kind"] == "observed_fact"
    evidence = {e["evidence_id"]: e for e in report["evidence"]}
    assert not any(
        "未见心脏扩大" in c["statement"] for c in safe_claims(report["claims"], evidence)
    )


def test_follow_up_observed_change_requires_new_measurement(knowledge):
    body = sample()
    body["mode"] = "follow_up"
    body["follow_up_snapshot"] = {
        "clinical_as_of": "2026-09-20T10:00:00+08:00",
        "knowledge_cutoff": "2026-09-20T10:00:00+08:00",
        "events": [
            event(
                "after",
                value=7.0,
                event_time="2026-09-20T08:00:00+08:00",
                available_at="2026-09-20T09:00:00+08:00",
                ingested_at="2026-09-20T09:01:00+08:00",
            )
        ],
    }
    report = run(body, knowledge)
    delta = [c for c in report["claims"] if c["kind"] == "observed_change"]
    assert delta[0]["data"]["change"] == -1
    assert delta[0]["data"]["causal_effect"] is None
    assert any("administration_evidence" in c["missing_premises"] for c in report["claims"])
    body["follow_up_snapshot"]["events"][0]["event_time"] = "2026-09-01T08:00:00+08:00"
    assert not any(c["kind"] == "observed_change" for c in run(body, knowledge)["claims"])


def test_snapshot_contract_is_immutable_and_patient_isolated():
    body = sample()
    body["baseline_snapshot"]["events"][0]["patient_id"] = "OTHER"
    with pytest.raises(ValueError, match="different patient"):
        build_state("SYNTHETIC", TreatmentAssessmentRequest.model_validate(body).baseline_snapshot)
    body = sample()
    body["baseline_snapshot"]["events"].append(deepcopy(body["baseline_snapshot"]["events"][0]))
    with pytest.raises(ValidationError):
        TreatmentAssessmentRequest.model_validate(body)


def test_unknown_population_and_unverified_value_do_not_trigger(knowledge):
    body = sample()
    body["baseline_snapshot"]["events"][0]["population_context"] = "unknown"
    assert not any(c["rule_id"] == "TEST-A1C" for c in run(body, knowledge)["claims"])
    body = sample()
    body["baseline_snapshot"]["events"][0]["value_trust"] = "unverified"
    assert not any(c["rule_id"] == "TEST-A1C" for c in run(body, knowledge)["claims"])


def test_fake_quote_does_not_become_evidence(knowledge):
    assert knowledge.quote("test-source", "Fabricated quotation") is None
    assert knowledge.quote("../test-source", "Anything") is None
    knowledge.documents["test-source"] = "Changed original source"
    report = run(sample(), knowledge)
    assert not any(c["rule_id"] == "TEST-A1C" for c in report["claims"])


def test_conflicting_measurements_not_silently_selected(knowledge):
    body = sample()
    body["baseline_snapshot"]["events"].append(event("other-lab", value=4.0))
    report = run(body, knowledge)
    assert not any(c["rule_id"] == "TEST-A1C" for c in report["claims"])
    assert any(
        "resolve_conflicting_measurements" in c["missing_premises"] for c in report["claims"]
    )


class FakeClient:
    settings = ModelSettings(api_key="test", model="test-model")

    def __init__(self, failure=None, invalid=False):
        self.failure, self.invalid = failure, invalid
        self.trace_ids = []

    def resolve(self):
        if self.failure:
            raise ProviderError(self.failure)
        return "test-model"

    def chat(self, system, data):
        if "report" in data:
            return {"supported": not self.invalid, "item_indices": [0]}
        claim = data["claims"][0]
        return {"items": [{"text": claim["statement"], "claim_ids": [claim["claim_id"]]}]}


def test_llm_success_and_semantic_failure_fallback(knowledge):
    body = sample()
    body["composer"] = "llm"
    report = run(body, knowledge, client=FakeClient())
    assert report["generation_metadata"]["composer"] == "llm"
    report = run(body, knowledge, client=FakeClient(invalid=True))
    assert report["generation_metadata"]["composer"] == "template"
    assert report["generation_metadata"]["attempts"] == 2
    assert report["claims"] and report["rendered_markdown"]


def test_provider_402_keeps_report_and_reason(knowledge):
    body = sample()
    body["composer"] = "llm"
    report = run(body, knowledge, client=FakeClient(failure="MODEL_HTTP_402"))
    assert report["generation_metadata"]["fallback_reason"] == "MODEL_HTTP_402"
    assert report["status"] == "partial" and report["claims"]


def test_unknown_refs_numbers_and_demo_rejected():
    claim = {"claim_id": "C1", "kind": "observed_fact", "statement": "数值为 8。"}
    for text, refs in [("正常", ["FAKE"]), ("数值为 5。", ["C1"])]:
        with pytest.raises(NarrativeError):
            validate_narrative(Narrative(items=[{"text": text, "claim_ids": refs}]), [claim])
    claim["kind"] = "demo"
    with pytest.raises(NarrativeError):
        validate_narrative(Narrative(items=[{"text": "数值为 8。", "claim_ids": ["C1"]}]), [claim])


def test_historical_mode_never_uses_current_rules(knowledge):
    body = sample()
    body["knowledge_mode"] = "historical"
    report = run(body, knowledge)
    assert not any(c["kind"] == "rule_conclusion" for c in report["claims"])
    assert any(
        "HISTORICAL_KNOWLEDGE_VERSION_UNAVAILABLE" in c["missing_premises"]
        for c in report["claims"]
    )


def test_archive_can_be_replayed_without_llm(knowledge, tmp_path):
    report = run(sample(), knowledge)
    archive(report, tmp_path / "reports")
    path = tmp_path / "reports" / (report["report_id"] + ".json")
    assert json.loads(path.read_text()) == report
    assert path.stat().st_mode & 0o777 == 0o600


def test_new_route_and_old_routes_remain_separate(monkeypatch, knowledge):
    from dmo.assessment import mirror, service

    monkeypatch.setattr(service, "KnowledgeStore", lambda: knowledge)
    monkeypatch.setattr(
        mirror, "build_request", lambda cfg, pid, **kwargs: TreatmentAssessmentRequest.model_validate(sample())
    )
    with TestClient(app) as client:
        response = client.post("/patients/SYNTHETIC/treatment-assessments")
        assert response.status_code == 200, response.text
        assert response.json()["claims"]
    routes = app.openapi()["paths"]
    assert "/simulate" in routes and "/patients/{pid}/forecasts" in routes


def test_patient_mirror_builds_snapshot_and_current_treatment(monkeypatch):
    from datetime import UTC, datetime

    from dmo.assessment import mirror

    class Connection:
        def fetchone(self, query, params):
            assert params == ("P1",)
            return {"patientid": "P1", "fact_origin": "demo-cohort", "projected_at": None}

        def fetchall(self, query, params):
            assert params == ("P1",)
            if "core_lab_result" in query:
                return [
                    {
                        "lab_result_id": "L1",
                        "lab_test_code": "A1C",
                        "result_value": 7.2,
                        "result_unit": "percent",
                        "collected_at": datetime(2026, 9, 1, 8, tzinfo=UTC),
                        "trust_level": "Curated",
                    }
                ]
            if "core_observation" in query:
                return []
            if "core_diagnosis" in query:
                return [
                    {
                        "diagnosis_id": "D1",
                        "diagnosis_kind": "Complication",
                        "clinical_status": "Active",
                        "verification_status": "Confirmed",
                        "external_code": None,
                        "type_iri": None,
                        "complication_iri": "https://example.org/dmo/id/CKD",
                        "diagnosed_date": None,
                    }
                ]
            return [
                {
                    "medication_use_id": "P1|M1",
                    "medication_iri": "https://example.org/dmo/id/medication/metformin",
                    "medication_name": "二甲双胍",
                    "start_date": None,
                    "end_date": None,
                    "status": "Active",
                }
            ]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    monkeypatch.setattr(mirror, "onto_conn", lambda cfg: Connection())
    request = mirror.build_request(object(), "P1")
    events = {e.record_id: e for e in request.baseline_snapshot.events}

    assert request.mode == "prospective"
    assert events["L1"].event_time == datetime(2026, 9, 1, 8, tzinfo=UTC)
    assert events["L1"].value_trust == "verified"
    assert events["diagnosis:D1"].concept_code == "CKD"
    assert not events["diagnosis:D1"].event_time_known
    assert request.interventions[0].code == "metformin"
    assert "|" not in request.interventions[0].action_id


def test_missing_mirror_patient_returns_404(monkeypatch):
    from dmo.assessment import mirror

    def missing(cfg, pid, **kwargs):
        raise KeyError(pid)

    monkeypatch.setattr(mirror, "build_request", missing)
    with TestClient(app) as client:
        assert client.post("/patients/MISSING/treatment-assessments").status_code == 404
    operation = app.openapi()["paths"]["/patients/{pid}/treatment-assessments"]["post"]
    assert "requestBody" not in operation


def test_unknown_event_time_cannot_trigger_recent_threshold(knowledge):
    body = sample()
    body["baseline_snapshot"]["events"][0]["event_time_known"] = False
    report = run(body, knowledge)
    assert not any(c["rule_id"] == "TEST-A1C" for c in report["claims"])
    assert any("event_time" in c["missing_premises"] for c in report["claims"])


def test_missing_treatment_is_a_gap_not_an_invented_action(knowledge):
    body = sample()
    body["interventions"] = []
    report = run(body, knowledge)
    assert report["interventions"] == []
    assert any("current_intervention" in c["missing_premises"] for c in report["claims"])


def test_mirror_population_ignores_future_unverified_and_conflicting_records():
    from datetime import UTC, datetime, timedelta

    from dmo.assessment.mirror import _population_context

    now = datetime(2026, 9, 1, tzinfo=UTC)
    row = {"observation_type": "PregnancyStatus", "observed_at": now,
           "trust_level": "Curated", "status": "Final", "value_text": None,
           "value_decimal": 0}
    assert _population_context([row], now) == "NonPregnant"
    assert _population_context([{**row, "observed_at": now + timedelta(days=1)}], now) == "unknown"
    assert _population_context([{**row, "trust_level": "Unverified"}], now) == "unknown"
    assert _population_context([row, {**row, "value_decimal": 1}], now) == "unknown"


def test_pacs_extraction_restores_omitted_negation(knowledge):
    class ExtractClient(FakeClient):
        def chat(self, system, data):
            if "reports" in data:
                return {
                    "findings": [
                        {"event_id": "report-0", "exact_quote": "心脏扩大", "assertion": "present"}
                    ]
                }
            return super().chat(system, data)

    body = sample()
    body.update(extract_pacs=True, composer="llm")
    body["baseline_snapshot"]["events"].append(
        event("pacs", source="pacs", domain="cardiovascular", value=None, text="未见心脏扩大。")
    )
    report = run(body, knowledge, client=ExtractClient())
    finding = report["generation_metadata"]["pacs_extraction"]["findings"][0]
    assert finding["assertion"] == "absent"
    assert finding["exact_quote"] == "未见心脏扩大"
    assert not any(
        c["kind"] == "rule_conclusion" and c["domain"] == "cardiovascular" for c in report["claims"]
    )


def test_invalid_late_pacs_span_does_not_publish_partial_claims(knowledge):
    class ExtractClient(FakeClient):
        def chat(self, system, data):
            if "reports" in data:
                return {
                    "findings": [
                        {"event_id": "report-0", "exact_quote": "未见异常", "assertion": "absent"},
                        {"event_id": "report-0", "exact_quote": "完全编造", "assertion": "present"},
                    ]
                }
            return super().chat(system, data)

    body = sample()
    body.update(extract_pacs=True, composer="llm")
    body["baseline_snapshot"]["events"].append(
        event("pacs", source="pacs", domain="cardiovascular", value=None, text="未见异常。")
    )
    report = run(body, knowledge, client=ExtractClient())
    assert not any(c["kind"] == "extracted_finding" for c in report["claims"])
    assert report["generation_metadata"]["pacs_extraction"]["status"] == "unavailable_or_invalid"


def test_conflicting_diagnosis_cannot_trigger_safety_rule(knowledge):
    body = sample()
    other = deepcopy(body["baseline_snapshot"]["events"][1])
    other.update(event_id="negative", record_id="negative", assertion="absent")
    body["baseline_snapshot"]["events"].append(other)
    report = run(body, knowledge)
    assert any("resolve_condition_conflict" in c["missing_premises"] for c in report["claims"])
    assert not any(
        c["rule_id"] == "TEST-RENAL" and c["kind"] == "rule_conclusion" for c in report["claims"]
    )


def test_historical_request_does_not_mutate_shared_knowledge(knowledge):
    body = sample()
    body["knowledge_mode"] = "historical"
    run(body, knowledge)
    assert any(c["rule_id"] == "TEST-A1C" for c in run(sample(), knowledge)["claims"])


def test_demo_remains_in_separate_appendix(knowledge):
    body = sample()
    body["include_demo_appendix"] = True
    body["baseline_snapshot"]["events"].append(event("fpg", metric="FPG", value=9, unit="mmol/L"))
    report = run(body, knowledge)
    assert report["demo_appendix"][0]["result"]["predictions"]
    assert not any(c["kind"] in {"demo", "model_prediction"} for c in report["claims"])
