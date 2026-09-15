from datetime import date

import pytest

from dmo.assessment.demo import SCENARIOS, rows_for_scenario
from dmo.assessment.trace import ExecutionTrace
from dmo.forecast.model import InitializedResponseModel


def test_synthetic_scenarios_keep_conflicts_trust_age_and_medication_status():
    rows = {s['pid']: rows_for_scenario(s, date(2026, 9, 15)) for s in SCENARIOS}
    assert len(rows) == 8
    for pid, batch in rows.items():
        assert batch['core_patient'][0]['fact_origin'] == 'demo-cohort'
        assert all(r['patientid'] == pid for records in batch.values() for r in records)
    conflict = rows['P91004']['core_lab_result']
    assert len(conflict) == 2
    assert len({r['result_value'] for r in conflict}) == 2
    assert rows['P91005']['core_lab_result'][0]['trust_level'] == 'Unverified'
    assert not rows['P91006']['core_lab_result']
    assert rows['P91008']['core_medication_use'][0]['status'] == 'OnHold'


def test_trace_is_explicit_replay_with_monotonic_timing():
    trace = ExecutionTrace()
    trace.record('read', '读取', '完成', {'rows': 3})
    trace.record('rules', '核验', '发现缺口', {'missing': ['unit']})
    result = trace.export()
    assert result['presentation'] == 'replay'
    assert [s['key'] for s in result['steps']] == ['read', 'rules']
    assert result['steps'][1]['elapsed_ms'] >= result['steps'][0]['elapsed_ms']
    assert result['steps'][1]['details']['missing'] == ['unit']


def test_displayed_model_calculation_equals_prediction():
    model = InitializedResponseModel.initialize(seed=42)
    for day in (7, 14, 28):
        calculation = model.components(9, day)
        assert calculation['value'] == model.predict(9, day)
        assert calculation['value'] == pytest.approx(9 * calculation['multiplier'])
