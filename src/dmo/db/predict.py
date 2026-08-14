"""把 GraphDB 里算好的风险分层抄进 pred_*。

**不做任何判定** —— 逻辑只在 ontology/rules/51-risk-stratification.rq 里有一份。
这里只是搬运 + 补上出处（quote / sha256 / externalStandardNote），
让 API 不必为了展示一条因子的依据而现跑 SPARQL。

跑之前必须先 `python3 ontology/tools/load_graphdb.py --rules`。
"""

from __future__ import annotations

from ..config import Config
from ..graph.client import GraphDBClient
from .engine import onto_conn

STRAT_Q = """
PREFIX dmo: <https://example.org/dmo#>
SELECT ?pid ?tier ?ruleId ?ruleVer ?reason ?gap ?n ?caveat WHERE {
  GRAPH ?g { ?p dmo:patientId ?pid }
  FILTER(STRSTARTS(STR(?g), "urn:dmo:patient:"))
  ?p dmo:hasRiskStratification ?s .
  ?s dmo:riskTier ?tier ; dmo:ruleId ?ruleId ; dmo:ruleVersion ?ruleVer ;
     dmo:caveat ?caveat .
  OPTIONAL { ?s dmo:insufficientReason ?reason }
  OPTIONAL { ?s dmo:monitoringGap ?gap }
  OPTIONAL { ?s dmo:contributingFactorCount ?n }
}
"""

# 每个命中带上它所引原文。没有出处的规则一样出现在结果里（?quote 为空），
# counted_in_tier 会是 false —— 缺口要可见。
HIT_Q = """
PREFIX dmo:  <https://example.org/dmo#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?hid ?pid ?rid ?rf (SAMPLE(?rfLabel_) AS ?rfLabel) (SAMPLE(?cat_) AS ?cat)
       ?basis ?fact (SAMPLE(?quote_) AS ?quote) (SAMPLE(?hash_) AS ?hash)
       (SAMPLE(?src_) AS ?src) (SAMPLE(?note_) AS ?note)
       (COUNT(DISTINCT ?p5) AS ?nPassage)
WHERE {
  GRAPH ?g { ?p dmo:patientId ?pid }
  FILTER(STRSTARTS(STR(?g), "urn:dmo:patient:"))
  ?p dmo:hasRiskFactorHit ?h .
  ?h dmo:hitId ?hid ; dmo:hitsRiskRule ?r ; dmo:hitRiskFactor ?rf ;
     dmo:triggerBasis ?basis .
  ?r dmo:riskRuleId ?rid .
  OPTIONAL { ?h dmo:hitFromFact ?fact }
  OPTIONAL { ?rf rdfs:label ?rfLabel_ }
  OPTIONAL { ?rf dmo:riskCategory ?cat_ }
  OPTIONAL { ?r dmo:externalStandardNote ?note_ }
  OPTIONAL {
    ?r dmo:riskRuleCitesPassage ?p5 .
    ?p5 dmo:quote ?quote_ ; dmo:contentHash ?hash_ .
    OPTIONAL { ?srcNode dmo:hasPassage ?p5 BIND(STR(?srcNode) AS ?src_) }
  }
}
GROUP BY ?hid ?pid ?rid ?rf ?basis ?fact
"""


def run(cfg: Config, *, patient: str | None = None) -> int:
    client = GraphDBClient(cfg)
    strats = client.sparql_csv(STRAT_Q)
    hits = client.sparql_csv(HIT_Q)
    if patient:
        strats = [r for r in strats if r["pid"] == patient]
        hits = [r for r in hits if r["pid"] == patient]

    if not strats:
        print("• GraphDB 里没有 RiskStratification。先跑："
              "\n    python3 ontology/tools/load_graphdb.py --rules")
        return 1

    with onto_conn(cfg) as conn:
        if patient:
            conn.execute(
                "DELETE FROM diabetes.pred_risk_stratification WHERE patientid = %s",
                (patient,))
            conn.execute("DELETE FROM diabetes.pred_factor_hit WHERE patientid = %s",
                         (patient,))
        else:
            conn.execute("DELETE FROM diabetes.pred_risk_stratification")
            conn.execute("DELETE FROM diabetes.pred_factor_hit")

        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO diabetes.pred_risk_stratification (patientid, tier, rule_id,"
                " rule_version, insufficient_reason, monitoring_gap, factor_count, caveat)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                [(r["pid"], r["tier"], r["ruleId"], r["ruleVer"],
                  (r.get("reason") or "").strip() or None,
                  (r.get("gap") or "").strip() or None,
                  int(r.get("n") or 0), r["caveat"]) for r in strats],
            )
            cur.executemany(
                "INSERT INTO diabetes.pred_factor_hit (hit_id, patientid, risk_rule_id,"
                " risk_factor_iri, risk_factor_label, risk_category, trigger_basis,"
                " counted_in_tier, from_fact_iri, source_id, quote, sha256, external_note)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                " ON CONFLICT (hit_id) DO NOTHING",
                [(r["hid"], r["pid"], r["rid"], r["rf"], r.get("rfLabel") or None,
                  r.get("cat") or None, r["basis"],
                  # 计入 tier 的三个条件：有出处、可改变、有哈希。
                  # 与 51 号规则的过滤条件必须一致 —— 不一致的话，
                  # 返回体展示的因子和实际参与判定的因子就对不上了。
                  int(r.get("nPassage") or 0) > 0 and r.get("cat") == "Modifiable",
                  r.get("fact") or None, r.get("src") or None,
                  r.get("quote") or None, r.get("hash") or None,
                  r.get("note") or None) for r in hits],
            )
        conn.commit()

        dist = conn.fetchall(
            "SELECT tier, count(*) n FROM diabetes.pred_risk_stratification "
            "GROUP BY 1 ORDER BY 1")
        bad = conn.scalar(
            "SELECT count(*) FROM diabetes.pred_factor_hit "
            "WHERE counted_in_tier AND (sha256 IS NULL OR sha256 = '')")

    print(f"✓ 物化 {len(strats)} 条分层 / {len(hits)} 条因子命中")
    for r in dist:
        print(f"    {r['tier']:<24} {r['n']}")
    if bad:
        print(f"\n✗ 有 {bad} 条计入 tier 的因子没有 sha256 出处 —— "
              "「列不出出处的因子不参与判定」被破坏了。")
        return 1
    print("  ✓ 所有计入 tier 的因子都有 sha256 出处")
    return 0
