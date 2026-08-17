"""推演编排 —— 跑两遍规则链，diff 出结论变化。

    基线：患者图原样            → run_rules → before
    假设：患者图 + 假设事实副本 → run_rules → after
    delta = diff(before, after)

两遍各自用**全新的 Dataset**（Snapshot.dataset() 每次新建）。共用一个的话，
基线跑出的结论会留在 default graph 里，第二遍的 30 号规则会把它们当成
本轮证据 —— 单次检验凭空变成"两个日期"，Provisional 直接变 Confirmed。
这类错误不报错，只是结论悄悄错了。

跑基线而不是直接读 `/patients/{pid}`：那个端点读的是 GraphDB 里
`urn:dmo:inferred` 的**上一次**规则运行结果，与本次沙箱用的规则版本、
知识快照可能不是同一份。before/after 必须来自同一次运行的同一套输入，
否则 diff 出来的差异里混着"规则改过了"这种与假设无关的变化。
"""

from __future__ import annotations

from typing import Any

from rdflib import URIRef

from ..config import Config
from ..query.hybrid import DISCLAIMER
from . import engine, hypothesis, sandbox, tree
from .hashing import derivation_hash

# 推演结论的固定尾注。与 hybrid.DISCLAIMER 并列出现 —— 那一条讲的是
# "本系统不是医疗器械"，这一条讲的是"以下结论建立在假设之上"。
HYPOTHETICAL_NOTE = (
    "⚠️ 以下结论建立在**假设事实**之上，不是该患者的实际情况。"
    "假设值由调用方显式给出，本系统不生成、不推荐、不外推任何数值——"
    "这是条件推演（若 X 则 Y），不是病程预测。"
)


def simulate(
    cfg: Config,
    pid: str,
    assume: list[dict[str, Any]],
    *,
    include_unreliable: bool = False,
    refresh: bool = False,
) -> dict[str, Any]:
    from ..terms.concepts import graph_version

    snap = sandbox.load(cfg, pid, refresh=refresh)

    # ── 基线 ──────────────────────────────────────────────────────────
    ds_before = snap.dataset()
    engine.run_rules(ds_before, include_unreliable=include_unreliable)
    before = engine.collect(ds_before)

    # 可推演项目表只依赖知识层，跑没跑规则都一样，复用基线 Dataset 省一次解析。
    hyps = hypothesis.parse(cfg, ds_before, assume)

    # ── 假设后 ────────────────────────────────────────────────────────
    ds_after = snap.dataset()
    injected = hypothesis.to_graph(hyps, snap.patient_iri)
    pg = ds_after.graph(URIRef(snap.patient_graph))
    for triple in injected:
        pg.add(triple)
    engine.run_rules(ds_after, include_unreliable=include_unreliable)
    after = engine.collect(ds_after)

    delta = engine.diff(before, after)
    version = graph_version()

    return {
        "patientId": pid,
        "patientGraph": snap.patient_graph,
        "derivationHash": derivation_hash(
            pid=pid,
            graph_version=version,
            knowledge_sha=snap.knowledge_sha,
            rules_sha=engine.rules_fingerprint(include_unreliable=include_unreliable),
            hypotheses=hyps,
        ),
        "graphVersion": version[:16],
        "rulesApplied": [p.name for p in engine.rule_files(
            include_unreliable=include_unreliable)],
        "hypotheticalFacts": [h.as_dict() for h in hyps],
        "injectedTriples": len(injected),
        "delta": delta,
        "unchanged": not delta,
        "before": _summary(before),
        "after": _summary(after),
        "derivationTree": tree.build(ds_after, after, hyps),
        "hypotheticalNote": HYPOTHETICAL_NOTE,
        "disclaimer": DISCLAIMER,
    }


def _summary(c: engine.Conclusions) -> dict[str, Any]:
    """精简快照。完整证据链在 derivationTree 里，这里只给"结论长什么样"。"""
    return {
        "assessments": [
            {"conclusion": v["conclusion"], "thresholdId": v["thresholdId"],
             "value": v["value"], "unit": v["unit"], "collectedDate": v["collectedDate"],
             "fromHypothesis": v["fromHypothesis"]}
            for v in sorted(c.assessments.values(),
                            key=lambda x: (x["collectedDate"] or "", x["thresholdId"] or ""))
        ],
        "diagnoses": [
            {"diagnosisKind": v["diagnosisKind"],
             "verificationStatus": v["verificationStatus"],
             "factOrigin": v["factOrigin"], "caveat": v["caveat"]}
            for v in sorted(c.diagnoses.values(),
                            key=lambda x: x["diagnosisIri"] or "")
        ],
        "riskTier": next(iter(c.risk.values()), None),
        "contraindications": list(c.safety.values()),
    }
