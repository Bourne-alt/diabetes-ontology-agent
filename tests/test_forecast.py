import runpy
from copy import deepcopy
from dataclasses import is_dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from dmo.api import app
from dmo.domain import ENTITY_TYPES

client = TestClient(app)


def sample():
    return {
        "snapshot": {
            "clinical_as_of": "2026-09-13T10:00:00+08:00",
            "knowledge_cutoff": "2026-09-13T10:00:00+08:00",
            "events": [
                {
                    "event_id": "e1",
                    "patient_id": "P1",
                    "source": "lis",
                    "record_id": "r1",
                    "revision": 1,
                    "event_time": "2026-09-13T08:00:00+08:00",
                    "available_at": "2026-09-13T09:00:00+08:00",
                    "ingested_at": "2026-09-13T09:01:00+08:00",
                    "metric": "FPG",
                    "value": 9.0,
                    "unit": "mmol/L",
                }
            ],
        },
        "action": {
            "start_at": "2026-09-13T10:00:00+08:00",
            "medication_code": "external-demo-drug",
        },
    }


def post(body):
    return client.post("/patients/P1/forecasts", json=body)


def test_reproducible_explicit_demo():
    a = post(sample())
    assert a.status_code == 200, a.text
    result = a.json()
    assert result == post(sample()).json()
    assert not result["trained"] and not result["clinically_validated"]
    assert result["estimated_treatment_effect"] is None
    assert len(result["predictions"]) == 3
    assert result["predictions"][0]["prediction_interval"] is None


def test_late_correction_does_not_replace_known_revision():
    body = sample()
    revised = deepcopy(body["snapshot"]["events"][0])
    revised.update(
        event_id="e2",
        revision=2,
        value=15,
        available_at="2026-09-13T11:00:00+08:00",
        ingested_at="2026-09-13T11:01:00+08:00",
    )
    body["snapshot"]["events"].append(revised)
    assert post(body).json()["baseline"]["value"] == 9
    body["snapshot"]["clinical_as_of"] = "2026-09-13T12:00:00+08:00"
    body["snapshot"]["knowledge_cutoff"] = "2026-09-13T12:00:00+08:00"
    body["action"]["start_at"] = "2026-09-13T12:00:00+08:00"
    assert post(body).json()["baseline"]["value"] == 15
    revised["status"] = "retracted"
    assert post(body).json()["status"] == "insufficient_data"


def test_no_leak_or_patient_mix():
    body = sample()
    e = body["snapshot"]["events"][0]
    e["ingested_at"] = "2026-09-13T11:00:00+08:00"
    assert post(body).json()["status"] == "insufficient_data"
    e["patient_id"] = "P2"
    assert post(body).status_code == 422


def test_time_and_duplicate_validation():
    body = sample()
    body["snapshot"]["events"][0]["event_time"] = "2026-09-13T08:00:00"
    assert post(body).status_code == 422
    body = sample()
    body["snapshot"]["events"] *= 2
    assert post(body).status_code == 422


def test_clarification_and_future_action():
    body = sample()
    del body["action"]["medication_code"]
    assert post(body).json()["status"] == "needs_clarification"
    body = sample()
    body["action"]["start_at"] = "2026-10-13T10:00:00+08:00"
    assert all(p["change_from_baseline"] == 0 for p in post(body).json()["predictions"])


def test_pacs_does_not_become_glucose():
    body = sample()
    body["snapshot"]["events"][0]["source"] = "pacs"
    assert post(body).json()["status"] == "insufficient_data"


def test_stale_and_noncomparable():
    body = sample()
    body["snapshot"]["events"][0]["unit"] = "mg/dL"
    assert post(body).json()["status"] == "insufficient_data"
    body = sample()
    body["snapshot"]["events"][0]["event_time"] = "2026-08-01T00:00:00+08:00"
    assert post(body).json()["status"] == "insufficient_data"


def test_mapping_is_complete_and_generated():
    assert len(ENTITY_TYPES) == 25
    assert all(is_dataclass(cls) for cls in ENTITY_TYPES.values())
    root = Path(__file__).resolve().parents[1]
    generator = runpy.run_path(str(root / "scripts/generate_domain.py"))
    assert generator["generate"]() == (root / "src/dmo/domain/generated.py").read_text()


def test_simulate_routes_still_delegate_unchanged(monkeypatch):
    from dmo import api

    calls = []
    monkeypatch.setattr(
        api, "_simulate", lambda pid, body: calls.append((pid, body)) or {"ok": True}
    )
    assert client.post("/simulate", json={"patientId": "P1", "assume": []}).json() == {"ok": True}
    assert client.post("/patients/P1/simulate", json={"assume": []}).json() == {"ok": True}
    assert len(calls) == 2 and all(c[0] == "P1" for c in calls)


def test_event_order_has_same_hash_and_result():
    body = sample()
    extra = deepcopy(body['snapshot']['events'][0])
    extra.update(event_id='pacs1', record_id='pacs1', source='pacs', text='No finding')
    body['snapshot']['events'].append(extra)
    first = post(body).json()
    body['snapshot']['events'].reverse()
    assert post(body).json() == first
