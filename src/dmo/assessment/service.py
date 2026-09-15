"""Build a complete report without mutating any original patient graph or endpoint."""

from copy import copy
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal

from rdflib import Graph

from ..domain.generated import ONTOLOGY_SHA256, ClinicalObservation, LabResult, MedicationUse
from .composer import ModelClient, compose
from .contracts import LABELS, TreatmentAssessmentRequest
from .evidence import KnowledgeStore
from .render import render
from .rules import ClaimBuilder, evaluate_actions, evaluate_state, fact_id
from .snapshot import build_state, digest
from .trace import ExecutionTrace
from .validators import validate_claim_references

VERSION = "treatment-assessment-v1"


def assess(
    patient_id: str,
    request: TreatmentAssessmentRequest,
    *,
    knowledge: KnowledgeStore | None = None,
    client: ModelClient | None = None,
    trace: ExecutionTrace | None = None,
) -> dict:
    trace = trace or ExecutionTrace()
    baseline = build_state(patient_id, request.baseline_snapshot)
    follow = (
        build_state(patient_id, request.follow_up_snapshot) if request.follow_up_snapshot else None
    )
    trace.record("snapshot", "筛选时点有效记录", "检查患者隔离、修订、发布截点与撤回状态。", {
        "input_count": len(request.baseline_snapshot.events), "visible_count": len(baseline.events),
        "excluded": list(baseline.excluded), "snapshot_hash": baseline.fingerprint,
        "clinical_as_of": request.baseline_snapshot.clinical_as_of.isoformat(),
    })
    knowledge = knowledge or KnowledgeStore()
    # No source publication/availability history is available in current corpus.
    # Historical mode still reports facts/deltas but never applies current knowledge to the past.
    historical = request.knowledge_mode == "historical"
    if historical:
        knowledge = copy(knowledge)
        knowledge.graph = Graph()
        knowledge.evidence = {}
        knowledge.issues = [*knowledge.issues, "HISTORICAL_KNOWLEDGE_VERSION_UNAVAILABLE"]
    builder = ClaimBuilder()
    trace.record("knowledge", "加载本地知识与出处", "读取本体规则和原文文件；保留缺失来源及版本。", {
        "knowledge_version": knowledge.version, "ontology_sha256": ONTOLOGY_SHA256,
        "triple_count": len(knowledge.graph), "files": knowledge.files, "issues": knowledge.issues,
    })
    evidence = {}
    mapped = []
    states = [("baseline", baseline)] + ([("follow_up", follow)] if follow else [])
    snapshot_refs = {}
    for scope, state in states:
        snapshot_refs[scope] = {
            "hash": state.fingerprint,
            "clinical_as_of": state.snapshot.clinical_as_of.isoformat(),
            "knowledge_cutoff": state.snapshot.knowledge_cutoff.isoformat(),
            "excluded": list(state.excluded),
            "source_coverage": state.snapshot.source_coverage,
            "patient_context": state.snapshot.patient_context,
        }
        for e in state.events:
            key = fact_id(scope, e)
            fact = e.model_dump(mode="json", exclude={"patient_id"})
            fact.update(evidence_id=key, kind="patient_fact", time_scope=scope)
            evidence[key] = fact
            if e.source == "lis":
                entity = LabResult(
                    iri="urn:event:" + key,
                    lab_result_id=e.record_id,
                    collected_at=e.event_time,
                    result_unit=e.unit,
                    result_value=Decimal(str(e.value)) if e.value is not None else None,
                )
            elif e.source == "medication":
                entity = MedicationUse(
                    iri="urn:event:" + key, medication_use_id=e.record_id, status=e.execution_status
                )
            else:
                entity = ClinicalObservation(
                    iri="urn:event:" + key,
                    observation_id=e.record_id,
                    observed_at=e.event_time,
                    value_text=e.text,
                    status=e.assertion,
                )
            mapped.append(
                {
                    "evidence_id": key,
                    "class_iri": entity.ontology_iri,
                    "entity": {
                        k: str(v) if isinstance(v, (Decimal, datetime)) else v
                        for k, v in asdict(entity).items()
                    },
                }
            )
    for action in request.interventions:
        evidence["A-" + action.action_id] = {
            "evidence_id": "A-" + action.action_id,
            "kind": "intervention",
            **action.model_dump(mode="json"),
        }
    trace.record("ontology_map", "映射本体实体", "事件映射为检验、用药或临床观察，并建立证据编号。", {
        "entities": mapped,
    })
    b_latest = evaluate_state(baseline, "baseline", request, knowledge, builder)
    if follow:
        f_latest = evaluate_state(follow, "follow_up", request, knowledge, builder)
        for key, after in f_latest.items():
            before = b_latest.get(key)
            if (
                before is None
                or after.event_time <= baseline.snapshot.clinical_as_of
                or after.value_trust != "verified"
                or before.value_trust != "verified"
                or key[2] == "unspecified"
                or after.domain not in request.assessment_domains
            ):
                continue
            change = Decimal(str(after.value)) - Decimal(str(before.value))
            builder.add(
                after.domain,
                "observed_change",
                f"{after.metric} 在相同单位和语境下从 {before.value:g} 变为 {after.value:g} "
                f"{after.unit}，差值为 {change}。这是观察到的变化，不能单独归因于治疗。",
                refs=[fact_id("baseline", before), fact_id("follow_up", after)],
                scope="follow_up",
                rule="COMPARABLE-OBSERVATION-DELTA",
                data={
                    "metric": after.metric,
                    "unit": after.unit,
                    "change": float(change),
                    "before": before.value,
                    "after": after.value,
                    "causal_effect": None,
                },
            )
        if not any(c["kind"] == "observed_change" for c in builder.claims):
            builder.add(
                "glycemic",
                "data_gap",
                "没有可比较的治疗后新测量；旧报告更正不算治疗响应。",
                scope="follow_up",
                missing=["comparable_follow_up_measurement"],
            )
    trace.record("state_rules", "逐项评估检查结果", "按时间窗口、单位、人群和可信度筛选；冲突结果暂停判断。", {
        "max_fact_age_days": request.max_fact_age_days, "claims": list(builder.claims),
        "selected_measurements": [e.model_dump(mode="json") for e in b_latest.values()],
    })
    action_start = len(builder.claims)
    evaluate_actions(
        follow or baseline, "follow_up" if follow else "baseline", request, knowledge, builder
    )
    if not request.interventions:
        builder.add(
            "safety",
            "data_gap",
            "患者镜像中没有当前治疗措施，无法进行措施特异性评估。",
            missing=["current_intervention"],
            severity="review",
        )
    trace.record("treatment_rules", "关联治疗措施与条件规则", "检查药物知识覆盖、已确认条件及联合措施缺口。", {
        "claims": builder.claims[action_start:],
        "interventions": [a.model_dump(mode="json") for a in request.interventions],
    })
    extraction = {"status": "disabled", "findings": []}
    if request.extract_pacs and request.composer != "template":
        from .pacs import extract

        extraction = extract(
            follow or baseline, "follow_up" if follow else "baseline", builder, client=client
        )
        if extraction["status"] == "unavailable_or_invalid":
            builder.add(
                "safety",
                "data_gap",
                "影像文本抽取不可用或未通过校验，保留原始报告。",
                missing=["verified_pacs_extraction"],
            )
    for domain in request.assessment_domains:
        active = follow or baseline
        if not any(e.domain == domain for e in active.events):
            builder.add(
                domain,
                "data_gap",
                f"快照中缺少{LABELS[domain]}的患者资料，不能判断正常或改善。",
                missing=["domain_patient_data"],
            )
    for issue in knowledge.issues:
        builder.add("safety", "data_gap", "知识覆盖缺口：" + issue, missing=[issue])
    builder.add(
        "safety",
        "data_gap",
        "本地来源的原文已核验，但其时效性和患者适用性需复核。",
        missing=["current_patient_applicable_guidance"],
    )
    # Safety is always retained even when a caller narrows other assessment domains.
    domains = list(dict.fromkeys([*request.assessment_domains, "safety"]))
    claims = [c for c in builder.claims if c["domain"] in domains]
    trace.record("coverage", "检查六个维度的缺口", "缺少资料不视为正常，未命中规则不代表安全。", {
        "domains": [{"domain": d, "status": domain_status(d, claims)} for d in domains],
        "gaps": [c for c in claims if c["kind"] == "data_gap"],
    })
    evidence.update(knowledge.evidence)
    validate_claim_references(claims, evidence)
    trace.record("validate", "核验结论与证据引用", "每条结论的引用必须存在于证据索引。", {
        "claim_count": len(claims), "evidence_count": len(evidence),
        "references": [{"claim_id": c["claim_id"], "evidence_ids": c["evidence_ids"]} for c in claims],
        "knowledge_evidence": list(knowledge.evidence.values()),
    })
    generation = compose(
        claims, evidence, mode=request.composer, client=client, allow_pacs=request.extract_pacs
    )
    generation["pacs_extraction"] = extraction
    trace.record("compose", "组织报告内容", "记录实际生成器与校验结果。", {
        "composer": generation["composer"], "attempts": generation["attempts"],
        "fallback_reason": generation.get("fallback_reason"),
        "machine_learning_prediction_executed": False,
    })
    gaps = [c for c in claims if c["kind"] == "data_gap"]
    report = {
        "report_id": "",
        "status": "partial" if gaps or generation.get("fallback_reason") else "ok",
        "mode": request.mode,
        "service_version": VERSION,
        "ontology_sha256": ONTOLOGY_SHA256,
        "knowledge_mode": request.knowledge_mode,
        "knowledge_version": knowledge.version,
        "snapshot_refs": snapshot_refs,
        "interventions": [a.model_dump(mode="json") for a in request.interventions],
        "claims": claims,
        "evidence": sorted(evidence.values(), key=lambda e: e["evidence_id"]),
        "mapped_entities": mapped,
        "domains": [
            {
                "domain": d,
                "status": domain_status(d, claims),
                "claim_ids": [c["claim_id"] for c in claims if c["domain"] == d],
            }
            for d in domains
        ],
        "unresolved_questions": [
            {
                "claim_id": c["claim_id"],
                "statement": c["statement"],
                "missing": c["missing_premises"],
            }
            for c in gaps
        ],
        "monitoring": [c for c in claims if c["rule_id"] == "SOURCE-MONITORING"],
        "coverage": {
            "full_clinical_assessment": False,
            "quantitative_prediction": False,
            "pacs": "verbatim_record_with_caller_assertion_not_automated_diagnosis",
            "historical_knowledge_available": False,
            "llm_egress": (
                "structured_claims_and_opted_in_pacs_text"
                if request.extract_pacs
                else "structured_claims_only_no_raw_emr_or_pacs_notes"
            ),
        },
        "generation_metadata": generation,
        "demo_appendix": [],
    }
    if request.include_demo_appendix:
        report["demo_appendix"] = demo_appendix(request)
    report["rendered_markdown"] = render(report)
    report["report_id"] = "TA-" + digest(report)[:32]
    report["generated_at"] = datetime.now(UTC).isoformat()
    trace.record("report", "生成完整报告", "输出结构化结论、来源和可保存的 Markdown。", {
        "report_id": report["report_id"], "status": report["status"],
        "claim_count": len(claims), "gap_count": len(gaps),
    })
    report["execution_trace"] = trace.export()
    return report


def domain_status(domain, claims):
    selected = [c for c in claims if c["domain"] == domain]
    if not any(c["kind"] != "data_gap" for c in selected):
        return "unknown"
    if any(c["kind"] == "data_gap" or c["missing_premises"] for c in selected):
        return "partial"
    # Having notes alone is not a completed clinical assessment.
    if not any(c["kind"] in {"rule_conclusion", "observed_change"} for c in selected):
        return "partial"
    return "assessed"


def demo_appendix(request):
    from ..forecast.contracts import ForecastRequest
    from ..forecast.service import forecast

    if request.mode != "prospective":
        return [{"status": "unsupported_scenario", "reason": "demo supports prospective only"}]
    baseline = request.baseline_snapshot
    results = []
    for action in request.interventions:
        if action.kind != "medication" or action.operation != "start":
            continue
        events = [
            e.model_dump(
                include={
                    "event_id",
                    "patient_id",
                    "source",
                    "record_id",
                    "revision",
                    "event_time",
                    "available_at",
                    "ingested_at",
                    "status",
                    "metric",
                    "value",
                    "unit",
                    "text",
                }
            )
            for e in baseline.events
        ]
        pid = events[0]["patient_id"] if events else "demo"
        item = ForecastRequest.model_validate(
            {
                "snapshot": {
                    "clinical_as_of": baseline.clinical_as_of,
                    "knowledge_cutoff": baseline.knowledge_cutoff,
                    "events": events,
                },
                "action": {"medication_code": action.code, "start_at": action.start_at},
            }
        )
        results.append({"action_id": action.action_id, "result": forecast(pid, item)})
    return results
