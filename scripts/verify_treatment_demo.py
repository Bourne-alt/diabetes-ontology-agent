"""Read-only integration verification of the seeded treatment scenarios."""
import asyncio
import json

from fastapi.testclient import TestClient

from agent.backend import DmoBackend
from dmo.api import app
from dmo.assessment.demo import SCENARIOS


def main():
    reports = {}
    with TestClient(app) as client:
        for s in SCENARIOS:
            response = client.post(f"/patients/{s['pid']}/treatment-assessments")
            assert response.status_code == 200, (s["pid"], response.status_code)
            report = response.json()
            reports[s["pid"]] = report
            assert len(report["execution_trace"]["steps"]) == 11
            assert report["snapshot_refs"]["baseline"]["patient_context"]["fact_origin"] == "demo-cohort"
            print(json.dumps({"pid": s["pid"], "claims": len(report["claims"]),
                              "rule_ids": [c["rule_id"] for c in report["claims"] if c["kind"] == "rule_conclusion"],
                              "steps": len(report["execution_trace"]["steps"])}, ensure_ascii=False), flush=True)
        for pid, expected in {"P91003": "combined_intervention_evidence", "P91004": "resolve_conflicting_measurements",
                              "P91005": "verified_value", "P91007": "recent_record", "P91008": "current_intervention"}.items():
            assert any(expected in c["missing_premises"] for c in reports[pid]["claims"]), (pid, expected)
        assert any(c["kind"] == "rule_conclusion" for c in reports["P91001"]["claims"])
        assert not reports["P91008"]["interventions"]
        for pid in ("P91004", "P91005", "P91006", "P91007"):
            assert not any(c["kind"] == "rule_conclusion" and c["domain"] == "glycemic" for c in reports[pid]["claims"])
        prediction = client.post("/patients/P91001/prediction-demo")
        assert prediction.status_code == 200, prediction.text
        prediction = prediction.json()
        assert prediction["status"] == "ok", prediction["explanations"]
        assert len(prediction["predictions"]) == 3
        assert prediction["trained"] is False
        assert all(p["calculation"]["value"] > 0 for p in prediction["predictions"])
        assert client.post("/patients/P00001/prediction-demo").status_code == 400
        print(json.dumps({"prediction_status": prediction["status"], "baseline": prediction["baseline"]["value"],
                          "horizons": [p["horizon_days"] for p in prediction["predictions"]]}), flush=True)
    async def check_tool():
        for s in SCENARIOS:
            result = await DmoBackend(app).request(f"/patients/{s['pid']}/treatment-assessments", body={})
            assert result["ok"], (s["pid"], result)
    asyncio.run(check_tool())
    print("PASS: all eight live scenarios, trace, prediction guard and agent context budget")


if __name__ == "__main__":
    main()
