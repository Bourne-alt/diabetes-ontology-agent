"""结论裁决 —— 把外部给出的一条结论，和本体自己推出来的那条并排比对。

`/adjudicate/citations` 只管「这句引文是不是真的」；这里管「这个结论对不对」，
以及**更值钱的一问**：引文是真的，但它支撑的是不是调用方声称的那件事。

## 四个判定值，`not-adjudicable` 是常态不是异常

    supported        本体推出了同一条结论
    contradicted     本体推出了相反结论（语义键冲突）
    unsupported      本体没有相反结论，但也拿不出支撑 —— 证据不足
    not-adjudicable  这类断言本体压根不管（剂量、概率、域外）

`/risk` 上 `Insufficient-Evidence` 才是常态，这里同理。返回 `{"reasonable": true}`
等于给外部系统发一枚它承担不起的印章，本模块任何路径都不产生布尔判定。

## 只接受结构化断言

接受自然语言就要先用 LLM 解析，确定性当场丢光 —— 那正是 `simulate` 的
`derivationHash` 花力气守住的东西。`adjudicationHash` 是同一个承诺在这里的对应物：
同一条断言、同一版知识层与规则集，跑一百次必须同哈希。

## 按语义键比对，不按三元组

与 `simulate/engine.py` 的 diff 同一个理由：三元组级比对噪声压倒信号。
Assessment 看 `(conclusion, thresholdId)`，Diagnosis 看 `(kind, verificationStatus)` ——
「A1C 7.4% 落在糖尿病区间」和「这个人是糖尿病」根本不是同一句话，键也不该是同一个。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..config import Config
from .citations import CitationError

# 能裁决的类型。其余一律 not-adjudicable —— 不猜、不外推。
ADJUDICABLE = ("Assessment", "TargetAttainment", "Diagnosis", "RiskTier",
               "MedicationSafety")

# ⚠️ **诊断切点与管理目标必须分开裁决。**
# 21-target-attainment.rq 开头写得很清楚：一个 A1C 6.8% 的已确诊患者，按诊断切点看是
# 「超标」（≥6.5），按管理目标看是「达标」（<7%）—— 同一个数，两个相反的结论，
# 因为它们回答的根本不是同一个问题。
# 两类结论都是 dmo:Assessment，都进 assessment_evidence 模板，**只有 ruleId 能区分**。
# 不按 ruleId 收敛的话，一条「Normal」断言会去和管理目标的结论比，判出来的对错是随机的。
RULE_OF_CLAIM = {
    "Assessment": "LAB-THRESHOLD-MATCH",
    "TargetAttainment": "TARGET-ATTAINMENT",
}

# 明确不管的话题。命中就直接 not-adjudicable，连查都不查。
OUT_OF_SCOPE = {
    "Dosage": "本仓库任何路径都不输出剂量。",
    "Probability": "无结局标签、无随访；风险分层是规则式定性分层，tier 是有序枚举不是分数。",
    "Prognosis": "同上 —— 不输出概率，也不输出时间窗。",
    "Treatment": "规则链只做阈值判定与安全信号，不做治疗选择。",
}


def _canon(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _parse_claim(body: Any) -> tuple[str, str, dict[str, Any]]:
    if not isinstance(body, dict):
        raise CitationError("body 必须是对象。")
    pid = body.get("patientId") or body.get("pid")
    if not isinstance(pid, str) or not pid.strip():
        raise CitationError('body 必须含 "patientId"。')
    claim = body.get("claim")
    if not isinstance(claim, dict):
        raise CitationError(
            'body 必须含 "claim": {"type": "Assessment|Diagnosis", "value": {...}}。'
            "只接受结构化断言 —— 接受自然语言就要先用模型解析，确定性当场丢光。")
    ctype = claim.get("type")
    if not isinstance(ctype, str) or not ctype:
        raise CitationError('claim 必须含 "type"。可裁决的类型见 GET /adjudicate/scope。')
    value = claim.get("value")
    if not isinstance(value, dict) or not value:
        raise CitationError('claim 必须含非空的 "value" 对象。')
    return pid.strip(), ctype, value


def _hash(pid: str, ctype: str, value: dict[str, Any],
          graph_version: str, rules_fp: str) -> str:
    """同一条断言 + 同一版知识层与规则集 ⟹ 同一个哈希。

    ⚠️ `assertedBy` 与 `citations` **不进哈希**：谁说的、引了什么，都不改变
    本体自己推出来的那条结论。把它们混进去会让同一个判定有无数个哈希。
    """
    return hashlib.sha256(
        _canon({"patientId": pid, "type": ctype, "value": value,
                "graphVersion": graph_version, "rulesFingerprint": rules_fp}
               ).encode("utf-8")).hexdigest()


def _system_assessments(cfg: Config, pid: str,
                       rule_id: str | None = None) -> list[dict[str, Any]]:
    from ..query.hybrid import _interval, _sparql

    out = []
    for r in _sparql(cfg, "assessment_evidence", [pid]):
        if rule_id and r.get("ruleId") != rule_id:
            continue
        out.append({
            "conclusion": r.get("conclusion"),
            "thresholdId": r.get("thresholdId") or None,
            "ruleId": r.get("ruleId"), "ruleVersion": r.get("ruleVersion"),
            "applicableContext": r.get("context"),
            "interval": _interval(r),
            "confirmationRequired": r.get("confirm") == "true",
            "basedOn": {"labResultId": r.get("resultId"),
                        "value": r.get("resultValue"), "unit": r.get("resultUnit")},
            "quote": r.get("quote") or None, "sha256": r.get("sha256") or None,
            "caveat": r.get("caveat") or None,
        })
    return out


def _system_risk_tier(cfg: Config, pid: str) -> list[dict[str, Any]]:
    """风险分层。读 pred_* 物化表 —— 与 /patients/{pid}/risk 同一个来源，不另起一份。"""
    from ..db.engine import onto_conn

    with onto_conn(cfg) as conn:
        strat = conn.fetchone(
            "SELECT * FROM diabetes.pred_risk_stratification WHERE patientid = %s", (pid,))
        if strat is None:
            return []
        factors = conn.fetchall(
            "SELECT * FROM diabetes.pred_factor_hit WHERE patientid = %s "
            "ORDER BY counted_in_tier DESC, risk_rule_id", (pid,))
    return [{
        "tier": strat["tier"],
        "ruleId": strat["rule_id"], "ruleVersion": strat["rule_version"],
        "insufficientReason": strat["insufficient_reason"],
        "monitoringGap": strat["monitoring_gap"],
        "caveat": strat["caveat"],
        # 命中 ≠ 计分。两个数字都给，差额本身就是要说的话。
        "factorsHit": len(factors),
        "factorsCounted": sum(1 for f in factors if f["counted_in_tier"]),
        "quote": next((f["quote"] for f in factors if f["counted_in_tier"] and f["quote"]),
                      None),
        "sha256": next((f["sha256"] for f in factors if f["counted_in_tier"] and f["sha256"]),
                       None),
        "_quotes": [{"quote": f["quote"], "sha256": f["sha256"] or ""}
                    for f in factors if f["counted_in_tier"] and f["quote"]],
    }]


def _system_medication_safety(cfg: Config, pid: str) -> list[dict[str, Any]]:
    from ..query.hybrid import _sparql

    return [{
        "medication": r.get("medication") or None,
        "drugClass": r.get("drugClass") or None,
        "severity": r.get("severity"),
        "condition": r.get("condition") or None,
        "status": r.get("muStatus") or None,
        "rationale": r.get("rationale") or None,
        # 禁忌的依据是抽取产物的裸字符串，没有 contentHash —— 核不了逐字性
        "quote": None, "sha256": None,
    } for r in _sparql(cfg, "medication_safety", [pid])]


def _system_diagnoses(cfg: Config, pid: str) -> list[dict[str, Any]]:
    from ..query.hybrid import _sparql

    by_id: dict[str, dict[str, Any]] = {}
    for r in _sparql(cfg, "diagnosis_evidence", [pid]):
        key = r.get("diagnosisId") or r.get("kind") or ""
        d = by_id.setdefault(key, {
            "diagnosisId": r.get("diagnosisId") or None,
            "kind": r.get("kind"),
            "verificationStatus": r.get("verification"),
            "clinicalStatus": r.get("status") or None,
            "factOrigin": r.get("origin") or None,
            "externalCode": r.get("code") or None,
            "caveat": r.get("caveat") or None,
            "supportedBy": [],
        })
        if r.get("supportConclusion"):
            s = {"conclusion": r["supportConclusion"], "assessment": r.get("supportedBy")}
            if s not in d["supportedBy"]:
                d["supportedBy"].append(s)
    return list(by_id.values())


def _compare(claim: dict[str, Any], candidates: list[dict[str, Any]],
             keys: tuple[str, ...]) -> tuple[list[dict], list[dict], list[str]]:
    """按语义键比对。返回（完全一致的、键上冲突的、实际参与比对的键）。"""
    used = [k for k in keys if claim.get(k) not in (None, "")]
    matched, conflicting = [], []
    for c in candidates:
        diffs = [{"field": k, "claimed": claim[k], "system": c.get(k)}
                 for k in used if str(c.get(k)) != str(claim[k])]
        (conflicting if diffs else matched).append(
            dict(c, conflicts=diffs) if diffs else c)
    return matched, conflicting, used


def _missing_for_confirmation(candidates: list[dict[str, Any]],
                              assessments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Provisional → Confirmed 差在哪。答案是「另一日复测」，不是「再算一次」。"""
    if not any(c.get("verificationStatus") == "Provisional" for c in candidates):
        return []
    needs = sorted({a["thresholdId"] for a in assessments
                    if a["confirmationRequired"] and a["thresholdId"]})
    return [{
        "need": "另一采样日的复测（同项或另一项诊断级检验）",
        "because": ("所用诊断切点 confirmationRequired=true，单次落在区间内 ≠ 确诊"
                    f"（30-diagnosis-from-assessment.rq）。涉及阈值：{'、'.join(needs) or '—'}"),
        "wouldChangeVerdictTo": "supported",
        # 别在这里猜数值 —— 想看「若补一次会怎样」，把假设值显式交给 simulate
        "howToTest": "POST /simulate，assume 里显式给出复测的值与日期。本端点不生成任何数值。",
    }]


def _citation_check(cfg: Config, citations: Any, supporting: list[dict[str, Any]],
                    ) -> dict[str, Any] | None:
    """出处核查。★ `misattributed` 比 `fabricated` 更难也更值钱。

    引文真实存在、但支撑的不是调用方声称的那件事 —— 纯字符串比对抓不到，
    要靠 thresholdCitesPassage / riskRuleCitesPassage 的边反查。
    """
    if citations in (None, []):
        return None
    from .citations import check_citations

    out = check_citations(cfg, citations)
    supports = {s for s in (a.get("sha256") for a in supporting) if s}
    for r in out["results"]:
        if r["verdict"] != "verbatim":
            continue
        hashes = {m["sha256"] for m in r.get("matched", [])}
        if supports and not (hashes & supports):
            r["misattributed"] = True
            r["misattributionReason"] = (
                "引文逐字属实，但它不在支撑这条结论的出处里 —— "
                "本体用来判定这条结论的是："
                + "、".join(sorted(supports)[:3]) + "。引对了话，用错了地方。")
    out["misattributed"] = sum(1 for r in out["results"] if r.get("misattributed"))
    return out


def _evidence(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """出处去重但保序。RiskTier 的支撑是多条计分因子，不是一条。"""
    out: list[dict[str, str]] = []
    for r in rows:
        for e in (r.get("_quotes") or
                  ([{"quote": r["quote"], "sha256": r.get("sha256") or ""}]
                   if r.get("quote") else [])):
            if e not in out:
                out.append(e)
    return out


def adjudicate_claim(cfg: Config, body: Any) -> dict[str, Any]:
    from ..query.hybrid import DISCLAIMER
    from ..simulate.engine import rules_fingerprint
    from ..terms.concepts import graph_version

    pid, ctype, value = _parse_claim(body)
    gv, fp = graph_version(), rules_fingerprint()
    result: dict[str, Any] = {
        "patientId": pid,
        "claim": {"type": ctype, "value": value},
        # 谁说的只记账。判定与它无关。
        "assertedBy": body.get("assertedBy"),
        "adjudicationHash": _hash(pid, ctype, value, gv, fp),
        "graphVersion": gv,
        "rulesFingerprint": fp,
        "disclaimer": DISCLAIMER,
    }

    if ctype in OUT_OF_SCOPE:
        return result | {
            "verdict": "not-adjudicable",
            "whyNotAdjudicable": OUT_OF_SCOPE[ctype],
            "verdictReason": f"「{ctype}」不在可裁决范围内。",
        }
    if ctype not in ADJUDICABLE:
        return result | {
            "verdict": "not-adjudicable",
            "whyNotAdjudicable": (
                f"claim.type=「{ctype}」当前不可裁决。已落地的是："
                f"{'、'.join(ADJUDICABLE)}。完整范围见 GET /adjudicate/scope —— "
                "标着 planned 的类型还没实现，不要当成「判过了没问题」。"),
            "verdictReason": "本端点不猜、不外推。",
        }

    # 患者必须存在。查不到就是查不到，不返回一个看着像「没问题」的空结论。
    from ..db.engine import onto_conn

    with onto_conn(cfg) as conn:
        if not conn.fetchone(
                "SELECT patientid FROM diabetes.core_patient WHERE patientid = %s", (pid,)):
            raise KeyError(pid)

    assessments = _system_assessments(cfg, pid, RULE_OF_CLAIM["Assessment"])
    if ctype in RULE_OF_CLAIM:
        candidates = (assessments if ctype == "Assessment"
                      else _system_assessments(cfg, pid, RULE_OF_CLAIM[ctype]))
        keys = ("conclusion", "thresholdId")
        scope_note = ("该患者没有任何阈值判定" if ctype == "Assessment"
                      else "该患者没有任何管理目标达标判定")
    elif ctype == "Diagnosis":
        candidates = _system_diagnoses(cfg, pid)
        keys = ("kind", "verificationStatus", "clinicalStatus")
        scope_note = "该患者没有任何诊断记录"
    elif ctype == "RiskTier":
        candidates = _system_risk_tier(cfg, pid)
        keys = ("tier",)
        scope_note = "该患者没有风险分层结论"
    else:  # MedicationSafety
        candidates = _system_medication_safety(cfg, pid)
        keys = ("medication", "severity", "drugClass")
        scope_note = "该患者没有任何用药安全信号"

    # 先按调用方给的收敛条件缩小候选集，否则「A1C 判成 Diabetes」会被 FPG 的结论干扰
    narrowed = candidates
    for field_ in ("thresholdId", "kind", "medication"):
        if value.get(field_):
            hit = [c for c in narrowed if str(c.get(field_)) == str(value[field_])]
            if hit or field_ in ("thresholdId", "medication"):
                narrowed = hit

    matched, conflicting, used = _compare(value, narrowed, keys)
    supporting = matched or conflicting
    result |= {
        "systemConclusions": [{k: v for k, v in c.items() if not k.startswith("_")}
                              for c in narrowed],
        "comparison": {"semanticKey": list(keys), "keysUsed": used,
                       "matched": len(matched), "conflicts": [
                           {"systemConclusion": {k: c.get(k) for k in keys},
                            "diffs": c["conflicts"]} for c in conflicting]},
        "citationCheck": _citation_check(cfg, body.get("citations"), supporting),
    }

    if matched:
        return result | {
            "verdict": "supported",
            "verdictReason": "本体按同一套规则推出了同一条结论。",
            "basedOn": [m.get("basedOn") for m in matched if m.get("basedOn")],
            "evidence": _evidence(matched),
            "supportedMeans": (
                "严格限定为「与本仓库当前版本知识层的规则和阈值一致」。"
                "不代表临床上正确、不代表适用于该患者、不是任何形式的诊疗背书。"),
        }
    if conflicting:
        return result | {
            "verdict": "contradicted",
            "verdictReason": "本体推出的结论与该断言在语义键上冲突，详见 comparison.conflicts。",
            "missingEvidence": _missing_for_confirmation(conflicting, assessments),
            "evidence": _evidence(conflicting),
        }
    return result | {
        "verdict": "unsupported",
        "verdictReason": (
            f"{scope_note}（或给定的收敛条件下没有）—— 本体既拿不出支撑，也拿不出反驳。"
            "证据不足与「判定为错」是两回事。"),
        "missingEvidence": [{
            "need": "该项目的一次可用检验值",
            "because": ("常见原因是上游值 valueTrustLevel=Unverified，被 "
                        "20-lab-assessment.rq 挡在门外；也可能是该术语在映射表里 "
                        "verify_status 不是 verified。用 GET /terms/explain?term=… 看是哪一种。"),
            "wouldChangeVerdictTo": "supported 或 contradicted",
        }],
    }
