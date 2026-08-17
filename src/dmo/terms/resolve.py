"""映射表的装载、未命中扫描与查询。

三条口径贯穿本模块：

  1. **未命中只记账，绝不猜。** 没有编辑距离、没有 trigram 相似度、没有 embedding。
     猜错一个术语，下游所有结论都是错的，而且错得看起来很像对的
     —— `semantic_link` 把「尿蛋白 10.4」链到两个互斥疾病、confidence 都写 0.9，
     就是猜出来的。
  2. **CSV 是人工决策的载体。** 映射不是算出来的，是人定的；CSV 可读可 diff 可 review，
     `verified_by` 记谁定的。
  3. **verify_status 决定能不能用**，不是「有没有」。concept_iri 填了但状态是
     candidate 的行，投影层一样跳过。
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..config import Config
from ..db.engine import onto_conn

SEED_DIR = Path(__file__).resolve().parents[1] / "db" / "seed"

# verify_status ∈ 这一组时才真的参与投影。其余全部跳过并计数。
USABLE = ("verified",)


def _rows(name: str) -> list[dict[str, str]]:
    path = SEED_DIR / name
    if not path.exists():
        raise SystemExit(f"缺种子文件：{path}")
    with path.open(encoding="utf-8", newline="") as f:
        return [
            {k: (v.strip() if isinstance(v, str) else v) for k, v in r.items()}
            for r in csv.DictReader(f)
        ]


def _null(v: str | None) -> str | None:
    return v if v else None


def load_terms(cfg: Config) -> int:
    """把映射 CSV 幂等 UPSERT 进库。"""
    lab = _rows("lab_term_map.csv")
    icd = _rows("icd10_map.csv")
    drug = _rows("drug_term_map.csv")
    units = _rows("unit_conversion.csv")

    with onto_conn(cfg) as conn:
        known = {r["iri"] for r in conn.fetchall("SELECT iri FROM diabetes.map_concept_ref")}

        # 外键指向 map_concept_ref。CSV 里写了一个图里不存在的 IRI 时，
        # 与其让 PG 抛外键错误（消息里只有 IRI，看不出是哪一行），不如先自己检出来。
        dangling = []
        for name, rows, cols in (
            ("lab_term_map.csv", lab, ("concept_iri",)),
            ("icd10_map.csv", icd, ("concept_iri",)),
            ("drug_term_map.csv", drug, ("medication_iri", "drug_class_iri")),
            ("unit_conversion.csv", units, ("concept_iri",)),
        ):
            for r in rows:
                for c in cols:
                    iri = r.get(c) or ""
                    if iri and iri not in known:
                        key = r.get("src_name") or r.get("icd10code") or "?"
                        dangling.append(f"{name}: {key} 的 {c} = {iri}")
        if dangling:
            print("✗ 这些 IRI 在 map_concept_ref 里不存在：")
            for d in dangling:
                print(f"    {d}")
            print("\n  先跑 `dmo map sync-concepts`；仍然缺就是本体里真的没有这个概念，"
                  "\n  该改 CSV 或补本体，不要把 IRI 编出来。")
            return 1

        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO diabetes.map_lab_term
                    (src_name, src_ref_range, concept_iri, unit_src, unit_target,
                     conv_factor, value_kind, trust_default, verify_status, verified_by,
                     note, verified_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                        CASE WHEN %s <> '' THEN now() END)
                ON CONFLICT (src_name, src_ref_range) DO UPDATE SET
                    concept_iri=EXCLUDED.concept_iri, unit_src=EXCLUDED.unit_src,
                    unit_target=EXCLUDED.unit_target, conv_factor=EXCLUDED.conv_factor,
                    value_kind=EXCLUDED.value_kind, trust_default=EXCLUDED.trust_default,
                    verify_status=EXCLUDED.verify_status, verified_by=EXCLUDED.verified_by,
                    note=EXCLUDED.note, verified_at=EXCLUDED.verified_at
                """,
                [
                    (r["src_name"], _null(r["src_ref_range"]), _null(r["concept_iri"]),
                     _null(r["unit_src"]), _null(r["unit_target"]),
                     _null(r["conv_factor"]), r["value_kind"], r["trust_default"],
                     r["verify_status"], _null(r["verified_by"]), _null(r["note"]),
                     r["verified_by"])
                    for r in lab
                ],
            )
            cur.executemany(
                """
                INSERT INTO diabetes.map_icd10
                    (icd10code, icd10name, concept_iri, concept_kind, verify_status, note)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (icd10code) DO UPDATE SET
                    icd10name=EXCLUDED.icd10name, concept_iri=EXCLUDED.concept_iri,
                    concept_kind=EXCLUDED.concept_kind,
                    verify_status=EXCLUDED.verify_status, note=EXCLUDED.note
                """,
                [(r["icd10code"], _null(r["icd10name"]), _null(r["concept_iri"]),
                  r["concept_kind"], r["verify_status"], _null(r["note"])) for r in icd],
            )
            cur.executemany(
                """
                INSERT INTO diabetes.map_drug_term
                    (src_name, medication_iri, drug_class_iri, is_antidiabetic,
                     verify_status, note)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (src_name) DO UPDATE SET
                    medication_iri=EXCLUDED.medication_iri,
                    drug_class_iri=EXCLUDED.drug_class_iri,
                    is_antidiabetic=EXCLUDED.is_antidiabetic,
                    verify_status=EXCLUDED.verify_status, note=EXCLUDED.note
                """,
                [(r["src_name"], _null(r["medication_iri"]), _null(r["drug_class_iri"]),
                  r["is_antidiabetic"].lower() == "true", r["verify_status"],
                  _null(r["note"])) for r in drug],
            )
            cur.executemany(
                """
                INSERT INTO diabetes.map_unit_conversion
                    (concept_iri, unit_src, unit_target, conv_factor, conv_offset,
                     verified_by, note)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (concept_iri, unit_src) DO UPDATE SET
                    unit_target=EXCLUDED.unit_target, conv_factor=EXCLUDED.conv_factor,
                    conv_offset=EXCLUDED.conv_offset, verified_by=EXCLUDED.verified_by,
                    note=EXCLUDED.note
                """,
                [(r["concept_iri"], r["unit_src"], r["unit_target"], r["conv_factor"],
                  r["conv_offset"] or "0", r["verified_by"], _null(r["note"]))
                 for r in units],
            )
        conn.commit()
    print(f"✓ 装载映射：检验 {len(lab)} 行 / ICD-10 {len(icd)} 行 / "
          f"药名 {len(drug)} 行 / 单位换算 {len(units)} 行")
    return 0


def sync_risk_rules(cfg: Config) -> int:
    """把 GraphDB 里的 RiskRule 投影一份到 SQL，供 API 解释用。判定仍在 SPARQL。"""
    from ..graph.client import GraphDBClient
    from .concepts import graph_version

    # ⚠️ 只按规则本身 GROUP BY，其余一律 SAMPLE。
    #    把 ?rfLabel / ?cat 放进 GROUP BY 会炸：mapsToRiskFactor 指向的抽取个体
    #    在多个 extract 图里各有一份 rdfs:label / riskCategory，笛卡尔积下来
    #    一条规则会出好几行，插进主键唯一的表就是 UniqueViolation。
    q = """
PREFIX dmo:  <https://example.org/dmo#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?id
       (SAMPLE(?label_) AS ?label)   (SAMPLE(?kind_) AS ?kind)
       (SAMPLE(?code_) AS ?code)     (SAMPLE(?match_) AS ?match)
       (SAMPLE(?lo_) AS ?lo)         (SAMPLE(?loOp_) AS ?loOp)
       (SAMPLE(?up_) AS ?up)         (SAMPLE(?upOp_) AS ?upOp)
       (SAMPLE(?rf) AS ?rf)          (SAMPLE(?rfLabel_) AS ?rfLabel)
       (SAMPLE(?cat_) AS ?cat)       (SAMPLE(?basis_) AS ?basis)
       (SAMPLE(?note_) AS ?note)
       (COUNT(DISTINCT ?p) AS ?nPassage)
WHERE {
  ?r a dmo:RiskRule ; dmo:riskRuleId ?id ; dmo:observedKind ?kind_ ;
     dmo:triggerBasis ?basis_ ; dmo:mapsToRiskFactor ?rf .
  OPTIONAL { ?r rdfs:label ?label_ }
  OPTIONAL { ?r dmo:observedCode ?code_ }
  OPTIONAL { ?r dmo:matchValue ?match_ }
  OPTIONAL { ?r dmo:ruleLowerBound ?lo_ }   OPTIONAL { ?r dmo:ruleLowerOperator ?loOp_ }
  OPTIONAL { ?r dmo:ruleUpperBound ?up_ }   OPTIONAL { ?r dmo:ruleUpperOperator ?upOp_ }
  OPTIONAL { ?r dmo:externalStandardNote ?note_ }
  OPTIONAL { ?r dmo:riskRuleCitesPassage ?p }
  OPTIONAL { ?rf rdfs:label ?rfLabel_ }
  OPTIONAL { ?rf dmo:riskCategory ?cat_ }
}
GROUP BY ?id
"""
    rows = GraphDBClient(cfg).sparql_csv(q)
    version = graph_version()
    with onto_conn(cfg) as conn:
        conn.execute("DELETE FROM diabetes.map_risk_rule")
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO diabetes.map_risk_rule
                  (risk_rule_id, label, observed_kind, observed_code, match_value,
                   lower_bound, lower_operator, upper_bound, upper_operator,
                   risk_factor_iri, risk_factor_label, risk_category,
                   trigger_basis, external_note, has_passage, graph_version)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                [(r["id"], _null(r.get("label")), r["kind"], _null(r.get("code")),
                  _null(r.get("match")), _null(r.get("lo")), _null(r.get("loOp")),
                  _null(r.get("up")), _null(r.get("upOp")), r["rf"],
                  _null(r.get("rfLabel")), _null(r.get("cat")), r["basis"],
                  _null(r.get("note")), int(r.get("nPassage") or 0) > 0, version)
                 for r in rows],
            )
        conn.commit()
    no_passage = [r["id"] for r in rows if int(r.get("nPassage") or 0) == 0]
    print(f"✓ 同步 {len(rows)} 条风险规则")
    if no_passage:
        print(f"  ⚠️  其中 {len(no_passage)} 条没有可逐字引用的出处，**不参与 tier 判定**：")
        for rid in sorted(no_passage):
            print(f"      {rid}")
    return 0


def scan_unmapped(cfg: Config) -> int:
    """扫上游快照里出现过、但映射表里没有可用条目的术语，记进 map_unmapped_term。"""
    with onto_conn(cfg) as conn:
        conn.execute("UPDATE diabetes.map_unmapped_term SET hit_count = 0")
        # 检验子项名：以 (名称, 参考范围) 为准，和 map_lab_term 的唯一键一致
        conn.execute(
            """
            INSERT INTO diabetes.map_unmapped_term (term_kind, term, context, hit_count)
            SELECT 'lab_analyte', s.itemname,
                   'ref_range=' || coalesce(s.inspectionresultrange, ''), count(*)
            FROM diabetes.stg_lis_result s
            LEFT JOIN diabetes.map_lab_term m
              ON m.src_name = s.itemname
             AND coalesce(m.src_ref_range,'') = coalesce(s.inspectionresultrange,'')
            WHERE m.id IS NULL
            GROUP BY 1,2,3
            ON CONFLICT (term_kind, term) DO UPDATE
              SET hit_count = EXCLUDED.hit_count, context = EXCLUDED.context,
                  last_seen = now()
            """
        )
        conn.execute(
            """
            INSERT INTO diabetes.map_unmapped_term (term_kind, term, context, hit_count)
            SELECT 'icd10', s.icd10code, s.icd10name, count(*)
            FROM diabetes.stg_diagnose s
            LEFT JOIN diabetes.map_icd10 m ON m.icd10code = s.icd10code
            WHERE m.icd10code IS NULL
            GROUP BY 1,2,3
            ON CONFLICT (term_kind, term) DO UPDATE
              SET hit_count = EXCLUDED.hit_count, last_seen = now()
            """
        )
        conn.execute(
            """
            INSERT INTO diabetes.map_unmapped_term (term_kind, term, context, hit_count)
            SELECT 'drug', s.termname, s.termclassname, count(*)
            FROM diabetes.stg_op_order s
            LEFT JOIN diabetes.map_drug_term m ON m.src_name = s.termname
            WHERE m.src_name IS NULL
            GROUP BY 1,2,3
            ON CONFLICT (term_kind, term) DO UPDATE
              SET hit_count = EXCLUDED.hit_count, last_seen = now()
            """
        )
        conn.execute("DELETE FROM diabetes.map_unmapped_term WHERE hit_count = 0")
        conn.commit()
    return 0


def report(cfg: Config) -> int:
    """`dmo map list-unmapped` 的输出。分四类，每类都要有明确归宿。"""
    scan_unmapped(cfg)
    with onto_conn(cfg) as conn:
        print("═══ 上游检验子项名的归宿（12 种，必须 100% 有归宿）═══")
        for r in conn.fetchall(
            """
            SELECT DISTINCT s.itemname, s.inspectionresultrange AS rng,
                   m.verify_status, m.value_kind, m.unit_src, m.unit_target,
                   m.conv_factor, c.label AS concept
            FROM diabetes.stg_lis_result s
            LEFT JOIN diabetes.map_lab_term m
              ON m.src_name = s.itemname
             AND coalesce(m.src_ref_range,'') = coalesce(s.inspectionresultrange,'')
            LEFT JOIN diabetes.map_concept_ref c ON c.iri = m.concept_iri
            ORDER BY s.itemname
            """
        ):
            st = r["verify_status"] or "**未映射**"
            mark = "✓" if st in USABLE else ("·" if r["verify_status"] else "✗")
            conv = f"  ×{r['conv_factor']}" if r["conv_factor"] else ""
            unit = f"  {r['unit_src'] or '?'}→{r['unit_target'] or '(不换算)'}"
            print(f"  {mark} {r['itemname']:<8} [{r['rng'] or '':<9}] {st:<15} "
                  f"{r['value_kind'] or '':<13}{unit}{conv}")

        print("\n═══ 本体里有、上游全库没有数据的（no-source-data）═══")
        rows = conn.fetchall(
            "SELECT src_name, note FROM diabetes.map_lab_term "
            "WHERE verify_status = 'no-source-data' ORDER BY src_name"
        )
        for r in rows:
            print(f"  · {r['src_name']}")
        print("  ↑ explain_gap() 会拿这几条如实回答『为什么查不到』，而不是返回空集。")

        print("\n═══ 完全未命中（已记账，绝不猜）═══")
        rows = conn.fetchall(
            "SELECT term_kind, term, context, hit_count FROM diabetes.map_unmapped_term "
            "ORDER BY term_kind, hit_count DESC"
        )
        if not rows:
            print("  （无）")
        for r in rows:
            print(f"  [{r['term_kind']:<12}] {r['term']:<24} ×{r['hit_count']}  {r['context'] or ''}")

        print("\n═══ 汇总 ═══")
        for kind, tbl, col in (("检验项", "map_lab_term", "src_name"),
                               ("ICD-10", "map_icd10", "icd10code"),
                               ("药名", "map_drug_term", "src_name")):
            stats = conn.fetchall(
                f"SELECT verify_status, count(*) n FROM diabetes.{tbl} "
                "GROUP BY 1 ORDER BY 2 DESC"
            )
            detail = "  ".join(f"{s['verify_status']}={s['n']}" for s in stats)
            print(f"  {kind:<8} {detail}")
    return 0
