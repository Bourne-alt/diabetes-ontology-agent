"""`GET /adjudicate/scope` —— 把**能力边界本身**做成可查询的 API。

两个用途，都很实在：

  1. 让智能体在调用之前就能判断该不该调。事后返回 `not-adjudicable` 也诚实，
     但那已经浪费了一轮，而且模型很容易把「判不了」读成「没问题」。
  2. 挡住把本 API 当「权威印章」用。裁决族一旦被当成"过了就是对的"，
     覆盖面就必须自己喊出来 —— 31 条可引用出处、10 条计分风险规则，
     这个体量支撑不了任何"全面校验"的说法。

⚠️ `status` 字段必须如实标 available / planned。把还没实现的裁决类型列成能力，
是这个端点最容易犯也最不能犯的错。
"""

from __future__ import annotations

from typing import Any

from ..config import Config

# 「收录了多少份指南」和「多少份真的拿得出可逐字引用的出处」差得很远，
# 后者才是裁决族的实际弹药量。只报前者会严重夸大覆盖面。
_Q_CORPUS = """
PREFIX dmo: <https://example.org/dmo#>
SELECT (COUNT(DISTINCT ?src) AS ?sources) (COUNT(DISTINCT ?citing) AS ?withPassages)
WHERE {
  { ?src a dmo:GuidelineSource }
  UNION { ?citing dmo:hasPassage ?p }
}
"""

# 明确不做的事。照 README「明确不做的事」与 51-risk-stratification.rq 开头。
NOT_ADJUDICABLE = (
    {"topic": "用药剂量 / 给药方案",
     "why": "本仓库任何路径都不输出剂量。禁忌判定只到 Absolute/Relative/Caution 三级信号。"},
    {"topic": "发病概率 / 风险百分比 / 时间窗",
     "why": "无结局标签、无随访，训练不出预测模型；风险分层是规则式定性分层，"
            "tier 是有序枚举不是分数。"},
    {"topic": "个体化治疗决策",
     "why": "规则链只做阈值判定与安全信号，不做治疗选择，也不考虑患者偏好与合并症全貌。"},
    {"topic": "糖尿病及其并发症以外的领域",
     "why": "语料只覆盖糖尿病域，域外结论没有任何判据。"},
    {"topic": "指南原文之外的临床共识",
     "why": "只认本库 SourcePassage 的逐字出处。「临床上通常认为」这类说法无法核验。"},
)


def describe(cfg: Config) -> dict[str, Any]:
    from ..graph import passages as passages_mod
    from ..graph import rules as rules_mod
    from ..graph.client import GraphDBClient
    from ..query.hybrid import DISCLAIMER

    pidx = passages_mod.load(cfg)
    ridx = rules_mod.load(cfg)
    counts = rules_mod.counts(ridx)

    row = (GraphDBClient(cfg).sparql_csv(_Q_CORPUS) or [{}])[0]

    return {
        "adjudicable": [
            {
                "claimType": "Citation",
                "status": "available",
                "endpoint": "POST /adjudicate/citations",
                "coverage": f"{len(pidx.passages)} 条 SourcePassage，100% 带 contentHash，"
                            "全部经 verify_passages.py 逐字回原文校验",
                "verdicts": ["verbatim", "hash-only", "quote-only",
                             "not-verbatim", "fabricated"],
            },
            {
                "claimType": "Assessment",
                "status": "available",
                "endpoint": "POST /adjudicate/claim",
                "coverage": f"{counts['threshold']['executable']} 条可执行诊断阈值",
                "ruleFiles": ["20-lab-assessment.rq"],
            },
            {
                "claimType": "Diagnosis",
                "status": "available",
                "endpoint": "POST /adjudicate/claim",
                "coverage": "confirmationRequired 的复测判定；单次异常 ≠ 确诊",
                "ruleFiles": ["30-diagnosis-from-assessment.rq"],
            },
            {
                "claimType": "TargetAttainment",
                "status": "available",
                "endpoint": "POST /adjudicate/claim",
                "coverage": f"{counts['target']['total']} 条管理目标。"
                            "⚠️ 与诊断切点**严格分开裁决**：两类结论都是 dmo:Assessment，"
                            "只有 ruleId 能区分（LAB-THRESHOLD-MATCH / TARGET-ATTAINMENT）。"
                            "一个 A1C 6.8% 的患者按诊断切点是超标、按管理目标是达标",
                "ruleFiles": ["21-target-attainment.rq"],
            },
            {
                "claimType": "RiskTier",
                "status": "available",
                "endpoint": "POST /adjudicate/claim",
                "coverage": f"{counts['risk']['countsInTier']} 条计分风险规则"
                            f"（声明 {counts['risk']['declared']} 条，"
                            f"可执行 {counts['risk']['executable']} 条）。"
                            f"⚠️ `?r a dmo:RiskRule` 查出的 "
                            f"{counts['risk']['classAssertions']} 条里有 "
                            f"{counts['risk']['inferenceArtifacts']} 条是 owl2-rl "
                            "从 domain 反推出来的患者命中记录，不是规则",
                "ruleFiles": ["50-risk-factor-hit.rq", "51-risk-stratification.rq"],
            },
            {
                "claimType": "MedicationSafety",
                "status": "available",
                "endpoint": "POST /adjudicate/claim",
                "coverage": "禁忌信号三级。⚠️ 全库语料里只有两条真正的「Do not take」",
                "ruleFiles": ["40-contraindication-flag.rq"],
            },
        ],
        "notAdjudicable": list(NOT_ADJUDICABLE),
        "corpus": {
            "guidelineSources": int(row.get("sources") or 0),
            "sourcesWithCitablePassages": int(row.get("withPassages") or 0),
            "citablePassages": len(pidx.passages),
            "coverageCaveat": (
                "收录的指南份数远大于拿得出逐字出处的份数 —— 其余来源的内容以 LLM 抽取的"
                "dmo:evidenceQuote 裸字符串存在，没有 contentHash、没人逐字核过，"
                "裁决族一概不认。别拿收录份数当覆盖面。"),
            "rules": counts,
        },
        "verdictSemantics": {
            "supported": "与本仓库当前版本知识层的规则和阈值一致，且所引出处可逐字回查。"
                         "**不代表临床上正确、不代表适用于该患者、不是任何形式的诊疗背书。**",
            "contradicted": "本体推出了相反结论。",
            "unsupported": "本体没有相反结论，但也拿不出支撑 —— 证据不足。",
            "not-adjudicable": "这类断言本体压根不管。这是常见返回值，不是异常。",
        },
        "neverReturns": "布尔式的「通过 / 合理」。理由见 "
                        "docs/ADJUDICATE-EXPLORE-API-PLAN.md §0.1。",
        "graphVersion": pidx.graph_version,
        "disclaimer": DISCLAIMER,
    }
