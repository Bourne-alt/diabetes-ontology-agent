"""Deterministic claims with explicit premises, separate from patient diagnoses."""

from decimal import Decimal

from .contracts import AssessmentEvent, TreatmentAssessmentRequest
from .evidence import DMO, KnowledgeStore
from .snapshot import PatientState, digest, recent


def fact_id(scope: str, event: AssessmentEvent) -> str:
    return "F-" + digest([scope, event.event_id])[:20]


class ClaimBuilder:
    def __init__(self):
        self.claims: list[dict] = []

    def add(
        self,
        domain: str,
        kind: str,
        statement: str,
        *,
        refs=(),
        scope="baseline",
        rule=None,
        severity="info",
        missing=(),
        data=None,
        action_id=None,
    ):
        value = {
            "domain": domain,
            "kind": kind,
            "statement": statement,
            "evidence_ids": sorted(set(refs)),
            "time_scope": scope,
            "rule_id": rule,
            "severity": severity,
            "missing_premises": list(missing),
            "data": data or {},
            "action_id": action_id,
            "support_status": "insufficient" if missing or kind == "data_gap" else "supported",
        }
        value["claim_id"] = "C-" + digest(value)[:20]
        if not any(c["claim_id"] == value["claim_id"] for c in self.claims):
            self.claims.append(value)
        return value


def select_latest(events: list[AssessmentEvent]):
    groups = {}
    for e in events:
        if e.source == "lis" and e.value is not None and e.metric and e.unit:
            key = (e.metric, e.unit, e.context)
            groups.setdefault(key, []).append(e)
    out = {}
    conflicts = []
    for key, group in groups.items():
        timestamp = max(e.event_time for e in group)
        newest = [e for e in group if e.event_time == timestamp]
        if len({e.value for e in newest}) > 1:
            conflicts.extend(newest)
        else:
            out[key] = max(newest, key=lambda e: e.event_id)
    return out, conflicts


def evaluate_state(
    state: PatientState,
    scope: str,
    request: TreatmentAssessmentRequest,
    knowledge: KnowledgeStore,
    builder: ClaimBuilder,
):
    events = recent(state, request.max_fact_age_days)
    latest, conflicts = select_latest(events)
    for e in conflicts:
        builder.add(
            e.domain,
            "data_gap",
            f"{e.metric} 同一时刻有冲突结果，暂停阈值和趋势判断。",
            refs=[fact_id(scope, e)],
            scope=scope,
            severity="review",
            missing=["resolve_conflicting_measurements"],
        )
    for e in state.events:
        if e.domain not in request.assessment_domains:
            continue
        if e.source == "lis" and e.value is not None:
            statement = f"记录 {e.metric or '未命名指标'}：{e.value:g} {e.unit or '单位缺失'}。"
        else:
            statement = (
                f"{e.source} 记录（{e.verification} / {e.assertion}）："
                f"{e.text or e.concept_code or '未提供正文'}"
            )
        builder.add(
            e.domain,
            "observed_fact",
            statement,
            refs=[fact_id(scope, e)],
            scope=scope,
            data={
                "metric": e.metric,
                "value": e.value,
                "unit": e.unit,
                "event_time": e.event_time.isoformat(),
                "assertion": e.assertion,
                "verification": e.verification,
                "value_trust": e.value_trust,
            },
        )
        if e not in events:
            builder.add(
                e.domain,
                "data_gap",
                "该记录超出本次评估配置的时间窗口，仅列入历史。",
                refs=[fact_id(scope, e)],
                scope=scope,
                missing=["recent_record"],
            )
    for e in latest.values():
        if e.domain not in request.assessment_domains:
            continue
        if e.value_trust != "verified":
            builder.add(
                e.domain,
                "data_gap",
                f"{e.metric} 数值尚未核验，不参与临床阈值判断。",
                refs=[fact_id(scope, e)],
                scope=scope,
                missing=["verified_value"],
            )
            continue
        if e.value < 0:
            builder.add(
                e.domain,
                "data_gap",
                f"{e.metric} 为负值，不参与此临床阈值判断。",
                refs=[fact_id(scope, e)],
                scope=scope,
                missing=["valid_measurement"],
            )
            continue
        matched = False
        for threshold in knowledge.thresholds(e.metric, e.unit, e.population_context):
            if not in_interval(Decimal(str(e.value)), threshold):
                continue
            matched = True
            builder.add(
                e.domain,
                "rule_conclusion",
                f"{e.metric} 落在本地知识定义的 {threshold['classification']} 区间；"
                "这是测量区间判定，不能单独用于确诊或判断治疗成功。",
                refs=[fact_id(scope, e), *threshold["evidence_ids"]],
                scope=scope,
                rule=threshold["id"],
                data={
                    "threshold_iri": threshold["iri"],
                    "context": e.context,
                    "classification": threshold["classification"],
                },
            )
        if not matched:
            builder.add(
                e.domain,
                "data_gap",
                f"{e.metric} 未匹配可核验且语境适用的阈值。",
                refs=[fact_id(scope, e)],
                scope=scope,
                missing=["applicable_threshold_or_context"],
            )
    return latest


def in_interval(value: Decimal, threshold: dict) -> bool:
    operations = {
        "GTE": lambda a, b: a >= b,
        "GT": lambda a, b: a > b,
        "LTE": lambda a, b: a <= b,
        "LT": lambda a, b: a < b,
    }
    for side in ("lower", "upper"):
        operator = threshold[side + "_operator"]
        if operator == "None":
            continue
        if operator not in operations or threshold[side] is None:
            return False
        if not operations[operator](value, Decimal(str(threshold[side]))):
            return False
    return True


def evaluate_actions(
    state: PatientState,
    scope: str,
    request: TreatmentAssessmentRequest,
    knowledge: KnowledgeStore,
    builder: ClaimBuilder,
):
    g = knowledge.graph
    events = recent(state, request.max_fact_age_days)
    conditions = {}
    for e in events:
        if e.concept_code and e.source != "medication":
            conditions.setdefault(e.concept_code, []).append(e)
    condition_events = []
    for group in conditions.values():
        latest_time = max(e.event_time for e in group)
        latest = [e for e in group if e.event_time == latest_time]
        if len({(e.assertion, e.verification, e.clinical_status) for e in latest}) > 1:
            builder.add(
                "safety",
                "data_gap",
                "同一问题的当前状态互相冲突，不能据此确认触发条件。",
                refs=[fact_id(scope, e) for e in latest],
                scope=scope,
                missing=["resolve_condition_conflict"],
                severity="review",
            )
        else:
            condition_events.extend(latest)
    for action in request.interventions:
        action_ref = "A-" + action.action_id
        builder.add(
            "safety",
            "observed_fact",
            f"措施 {action.code or '未明确'}：{action.operation}；"
            f"实施状态为 {action.execution_status}。",
            refs=[action_ref],
            scope="intervention",
            action_id=action.action_id,
        )
        if not action.code:
            builder.add(
                "safety",
                "data_gap",
                "措施编码不明确，无法评估其特异作用。",
                refs=[action_ref],
                missing=["intervention_code"],
                action_id=action.action_id,
            )
            continue
        if request.mode == "follow_up":
            exposure = [
                e
                for e in events
                if e.event_id in action.supporting_event_ids
                and e.source == "medication"
                and e.action_id == action.action_id
                and e.concept_code == action.code
                and e.execution_status == "administered"
                and e.event_time >= action.start_at
            ]
            if not exposure:
                builder.add(
                    "lifestyle",
                    "data_gap",
                    "没有可核验的实际实施事件；医嘱和自述不等同给药。",
                    refs=[action_ref],
                    scope=scope,
                    missing=["administration_evidence"],
                    action_id=action.action_id,
                )
        med = knowledge.medication(action.code) if action.kind == "medication" else None
        if med is None:
            builder.add(
                "safety",
                "data_gap",
                f"本地规则库未覆盖措施 {action.code}。",
                refs=[action_ref],
                missing=["intervention_knowledge"],
                action_id=action.action_id,
            )
            continue
        if action.operation == "stop":
            builder.add(
                "safety",
                "data_gap",
                "停用措施的整体影响未建模，不能反转启用时的作用结论。",
                refs=[action_ref],
                missing=["withdrawal_model"],
                action_id=action.action_id,
            )
            continue
        section = knowledge.drug_section(action.code)
        if section:
            key, quote = section
            mechanism = quote.split("\n", 1)[0]
            builder.add(
                "glycemic",
                "knowledge_expectation",
                f"{action.code} 所在类别的资料说明：{mechanism} "
                "这是一般机制信息；患者适用性、实际响应及下降幅度尚未确定。",
                refs=[action_ref, key],
                scope="scenario",
                action_id=action.action_id,
                data={"personal_response": None, "applicability": "not_established"},
            )
        for cls in g.objects(med, DMO.belongsToDrugClass):
            for contra in sorted(g.objects(cls, DMO.hasContraindication), key=str):
                quote = str(g.value(contra, DMO.rationale) or "")
                # A quote somewhere else in the source is not enough: it must be in this drug section.
                if not section or collapse_text(quote) not in collapse_text(section[1]):
                    continue
                key = knowledge.quote(
                    "fda-diabetes-drug-classes",
                    quote,
                    locator=f"medication:{action.code}; rule:{contra}",
                )
                if not key:
                    continue
                target = g.value(contra, DMO.triggeredByCondition)
                matched = [
                    e
                    for e in condition_events
                    if target is not None
                    and e.concept_code
                    and e.verification == "confirmed"
                    and e.assertion == "present"
                    and e.clinical_status == "active"
                    and knowledge.condition_matches(e.concept_code, target)
                ]
                rule_id = str(g.value(contra, DMO.contraCode) or contra)
                severity = str(g.value(contra, DMO.severity) or "Unknown")
                builder.add(
                    "safety",
                    "rule_conclusion" if matched else "knowledge_expectation",
                    (
                        f"本地规则 {rule_id} 的条件与已确认问题匹配。"
                        if matched
                        else f"资料列出 {action.code} 的条件性注意事项，患者触发条件尚未证实。"
                    )
                    + f"原文：{quote} 本地等级 {severity}；资料时效需复核。",
                    refs=[action_ref, key, *[fact_id(scope, e) for e in matched]],
                    scope=scope if matched and request.mode == "follow_up" else "scenario",
                    rule=rule_id,
                    severity="review",
                    action_id=action.action_id,
                    missing=[] if matched else ["confirmed_trigger_condition"],
                    data={"local_severity": severity, "triggered": bool(matched)},
                )
        if section:
            for sentence in section[1].splitlines():
                if sentence.startswith("Talk to your doctor about your kidney health"):
                    key = knowledge.quote(
                        "fda-diabetes-drug-classes", sentence, locator=f"medication:{action.code}"
                    )
                    builder.add(
                        "renal",
                        "knowledge_expectation",
                        "来源建议在开始和使用该类措施期间讨论肾脏健康；本条没有给出固定复查间隔。",
                        refs=[action_ref, key],
                        scope="scenario",
                        rule="SOURCE-MONITORING",
                        action_id=action.action_id,
                        data={"interval_days": None},
                    )
    builder.add(
        "safety",
        "data_gap",
        "本次未完整覆盖药物相互作用、剂量、过敏及个体适用性；未命中规则不代表安全。",
        missing=["complete_safety_review"],
        severity="review",
    )
    if len(request.interventions) > 1:
        builder.add(
            "safety",
            "data_gap",
            "多项措施的联合作用尚未建模，不能将获益或风险直接相加。",
            missing=["combined_intervention_evidence"],
            severity="review",
        )


def collapse_text(text):
    return " ".join(text.split())
