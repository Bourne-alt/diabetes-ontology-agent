"""core_* 的一个患者 → 一张 rdflib.Graph。

只发 V2 care-chain 的事实三元组，不发任何推断结论 —— 推断是 rules/*.rq 的活，
产物进 urn:dmo:inferred。两者混在一起，就分不清「上游这么记的」和「我们这么推的」。

**不发姓名、身份证、电话**：它们从 stg_* 就不存在（002_stg.sql 的列白名单），
这里连能发的机会都没有。脱敏做在入口，不是靠出口每个函数都记得过滤。

`hasAssessment` 这条边不在这里发 —— 它连的是推断出来的 Assessment，由规则层补。
"""

from __future__ import annotations

from decimal import Decimal

import rdflib
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, XSD

from . import iri as I
from .canonical import assert_no_bnodes

DMO = rdflib.Namespace(I.VOCAB)


def _lit(v, dt=None) -> Literal | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, Decimal):
        return Literal(str(v), datatype=XSD.decimal)
    return Literal(v, datatype=dt) if dt else Literal(v)


def _add(g: rdflib.Graph, s: URIRef, p, v, dt=None) -> None:
    lit = _lit(v, dt)
    if lit is not None:
        g.add((s, p, lit))


def build(patient: dict, facts: dict[str, list[dict]]) -> rdflib.Graph:
    g = rdflib.Graph()
    g.bind("dmo", DMO)

    pid = patient["patientid"]
    p = URIRef(I.patient_iri(pid))
    g.add((p, RDF.type, DMO.Patient))
    _add(g, p, DMO.patientId, pid)
    _add(g, p, DMO.sex, {"M": "Male", "F": "Female"}.get(patient["sex"] or "", "Unknown"))
    _add(g, p, DMO.birthYear, patient["birth_year"], XSD.integer)
    _add(g, p, DMO.factOrigin, patient["fact_origin"])
    _add(g, p, DMO.demoScenario, patient["demo_scenario"])

    for r in facts["encounters"]:
        e = URIRef(I.encounter_iri(r["encounter_id"]))
        g.add((e, RDF.type, DMO.ClinicalEncounter))
        g.add((p, DMO.hasEncounter, e))
        _add(g, e, DMO.encounterId, r["encounter_id"])
        _add(g, e, DMO.encounterDate, r["encounter_date"], XSD.date)
        _add(g, e, DMO.encounterType, r["encounter_type"])
        _add(g, e, DMO.gestationalWeek, r["gestational_week"], XSD.integer)
        _add(g, e, DMO.factOrigin, r["fact_origin"])

    for r in facts["labs"]:
        node = URIRef(I.lab_result_iri(r["lab_result_id"]))
        g.add((node, RDF.type, DMO.LabResult))
        _add(g, node, DMO.labResultId, r["lab_result_id"])
        _add(g, node, DMO.resultValue, r["result_value"], XSD.decimal)
        _add(g, node, DMO.resultUnit, r["result_unit"])
        # 换算前的原始值全程保留：演示时当场展示「7.8 mmol/L → 140.5 mg/dL，
        # 不换算会被误判 Normal」，靠的就是这两个字段。
        _add(g, node, DMO.sourceValue, r["source_value"], XSD.decimal)
        _add(g, node, DMO.sourceUnit, r["source_unit"])
        _add(g, node, DMO.collectedAt, r["collected_at"], XSD.dateTime)
        _add(g, node, DMO.valueTrustLevel, r["trust_level"])
        _add(g, node, DMO.factOrigin, r["fact_origin"])
        _add(g, node, DMO.demoScenario, r["demo_scenario"])
        g.add((node, DMO.measuredByTest, URIRef(r["lab_test_iri"])))
        if r["encounter_id"]:
            g.add((URIRef(I.encounter_iri(r["encounter_id"])), DMO.producesLabResult, node))

    for r in facts["observations"]:
        node = URIRef(I.observation_iri(r["observation_id"]))
        g.add((node, RDF.type, DMO.ClinicalObservation))
        g.add((p, DMO.hasClinicalObservation, node))
        _add(g, node, DMO.observationId, r["observation_id"])
        _add(g, node, DMO.observationType, r["observation_type"])
        _add(g, node, DMO.valueDecimal, r["value_decimal"], XSD.decimal)
        _add(g, node, DMO.valueText, r["value_text"])
        _add(g, node, DMO.unitCode, r["unit_code"])
        _add(g, node, DMO.observedAt, r["observed_at"], XSD.dateTime)
        _add(g, node, DMO.status, r["status"])
        _add(g, node, DMO.valueTrustLevel, r["trust_level"])
        _add(g, node, DMO.factOrigin, r["fact_origin"])
        _add(g, node, DMO.demoScenario, r["demo_scenario"])
        if r["encounter_id"]:
            g.add((node, DMO.observationRecordedAt,
                   URIRef(I.encounter_iri(r["encounter_id"]))))

    for r in facts["diagnoses"]:
        node = URIRef(I.diagnosis_iri(r["diagnosis_id"]))
        g.add((node, RDF.type, DMO.Diagnosis))
        g.add((p, DMO.hasDiagnosis, node))
        _add(g, node, DMO.diagnosisId, r["diagnosis_id"])
        _add(g, node, DMO.diagnosisKind, r["diagnosis_kind"])
        _add(g, node, DMO.clinicalStatus, r["clinical_status"])
        _add(g, node, DMO.verificationStatus, r["verification_status"])
        _add(g, node, DMO.codeSystem, r["code_system"])
        _add(g, node, DMO.externalCode, r["external_code"])
        _add(g, node, DMO.diagnosedDate, r["diagnosed_date"], XSD.date)
        _add(g, node, DMO.caveat, r["caveat"])
        _add(g, node, DMO.factOrigin, r["fact_origin"])
        _add(g, node, DMO.demoScenario, r["demo_scenario"])
        # ⚠️ 至多一个 diagnosisType。它是 FunctionalProperty，两个会推出 sameAs，
        #    与 AllDisjointClasses 冲突 —— core_diagnosis.type_iri 是单列，这里自然只发一条。
        if r["type_iri"]:
            g.add((node, DMO.diagnosisType, URIRef(r["type_iri"])))
        if r["complication_iri"]:
            g.add((node, DMO.diagnosisComplication, URIRef(r["complication_iri"])))
        if r["encounter_id"]:
            g.add((node, DMO.diagnosedAt, URIRef(I.encounter_iri(r["encounter_id"]))))

    for r in facts["medications"]:
        node = URIRef(I.medication_use_iri(r["medication_use_id"]))
        g.add((node, RDF.type, DMO.MedicationUse))
        g.add((p, DMO.hasMedicationUse, node))
        _add(g, node, DMO.medicationUseId, r["medication_use_id"])
        _add(g, node, DMO.startDate, r["start_date"], XSD.date)
        _add(g, node, DMO.endDate, r["end_date"], XSD.date)
        _add(g, node, DMO.status, r["status"])
        # regimenRole 只记角色，**没有任何剂量字段** —— schema 层面堵死越界输出
        _add(g, node, DMO.regimenRole, r["regimen_role"])
        _add(g, node, DMO.factOrigin, r["fact_origin"])
        _add(g, node, DMO.demoScenario, r["demo_scenario"])
        if r["medication_iri"]:
            g.add((node, DMO.usesMedication, URIRef(r["medication_iri"])))
        for dx in r["treats_diagnosis"] or []:
            g.add((node, DMO.treatsDiagnosis, URIRef(I.diagnosis_iri(dx))))

    assert_no_bnodes(g)
    return g
