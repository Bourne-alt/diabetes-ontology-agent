"""对照组 `semantic_link.analyte_concept_map` 的只读读取。

这个 schema 是 2026-07-17 前人在同一个库上做的一次尝试（wfs 项目，命名空间
`https://example.org/wfs/`）。**不迁移、不复用、不修改**：

  * 命名空间与 `https://example.org/dmo#` 不是一套（它把中文 URL 编码进了 IRI）；
  * 89 行全部 `verified=false`；
  * `relation` 与 `disease_iri` 混在一张表，粒度对不上；
  * 最要命的是判断口径：纯字符串名称匹配，把「尿蛋白」同时链到
    「1型糖尿病的糖尿病肾病」和「2型糖尿病的糖尿病肾病」两个互斥概念，
    confidence 都写 0.9，无单位、无阈值、无出处。

它是本方案**最好的对照组**，所以原样保留、只读、不动。

这里做两件事：
  1. `import_candidates()` —— 取它的 analyte_norm 去重，写进 map_lab_term 时
     **刻意丢弃它的 IRI**（concept_iri=NULL, verify_status='candidate'），
     只当作「有人觉得这个词值得映射」的线索，人工填 IRI 才生效。
  2. `compare()` —— 给 `/demo/compare` 用，把同一个术语两种做法并排摆出来。
"""

from __future__ import annotations

from ..config import Config
from ..db.engine import onto_conn, upstream_conn


def read_wfs(cfg: Config) -> list[dict]:
    """只读。semantic_link 与 patient_analysis 在同一个 database，走上游只读连接。"""
    with upstream_conn(cfg) as up:
        exists = up.scalar(
            "SELECT to_regclass('semantic_link.analyte_concept_map') IS NOT NULL"
        )
        if not exists:
            return []
        return up.fetchall(
            """
            SELECT domain, analyte_norm, concept_iri, concept_label, relation,
                   confidence, source, verified
            FROM semantic_link.analyte_concept_map
            ORDER BY analyte_norm, confidence DESC
            """
        )


def import_candidates(cfg: Config) -> int:
    rows = read_wfs(cfg)
    if not rows:
        print("• semantic_link.analyte_concept_map 不存在或为空，跳过")
        return 0

    by_term: dict[str, list[dict]] = {}
    for r in rows:
        by_term.setdefault(r["analyte_norm"], []).append(r)

    with onto_conn(cfg) as conn:
        existing = {
            r["src_name"]
            for r in conn.fetchall("SELECT DISTINCT src_name FROM diabetes.map_lab_term")
        }
        new = [t for t in by_term if t not in existing]
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO diabetes.map_lab_term
                    (src_name, src_ref_range, concept_iri, value_kind,
                     trust_default, verify_status, note)
                VALUES (%s, NULL, NULL, 'unusable', 'Unverified', 'candidate', %s)
                ON CONFLICT (src_name, src_ref_range) DO NOTHING
                """,
                [
                    (t,
                     (f"来自 semantic_link 的候选线索（{len(by_term[t])} 条）。"
                      "**其 IRI 已刻意丢弃**：命名空间是 wfs 不是 dmo，"
                      "且原表 verified 全为 false。人工填 concept_iri 并置 verified 才生效。"))
                    for t in new
                ],
            )
        conn.commit()

    print(f"✓ 读取 {len(rows)} 行 / {len(by_term)} 个去重术语，新增候选 {len(new)} 条")
    if new:
        print(f"    {', '.join(sorted(new))}")

    multi = {t: v for t, v in by_term.items() if len({r["concept_iri"] for r in v}) > 1}
    if multi:
        print(f"\n⚠️  其中 {len(multi)} 个术语在对照组里被链到了**多个**概念：")
        for t, v in sorted(multi.items())[:6]:
            print(f"    {t} → {len({r['concept_iri'] for r in v})} 个概念，"
                  f"confidence {min(float(x['confidence']) for x in v)}"
                  f"~{max(float(x['confidence']) for x in v)}")
        print("  这正是纯字符串匹配的失败模式：一个术语链到互斥的多个疾病，")
        print("  却给出同样高的 confidence。本方案的做法见 map_lab_term。")
    return 0


def compare(cfg: Config, term: str) -> dict:
    """同一个术语，两种做法并排。`/demo/compare` 与 `dmo demo compare` 的数据源。"""
    wfs_rows = [r for r in read_wfs(cfg) if r["analyte_norm"] == term]
    with onto_conn(cfg) as conn:
        ours = conn.fetchall(
            """
            SELECT m.src_name, m.src_ref_range, m.value_kind, m.verify_status,
                   m.unit_src, m.unit_target, m.conv_factor, m.note,
                   c.iri AS concept_iri, c.label AS concept_label
            FROM diabetes.map_lab_term m
            LEFT JOIN diabetes.map_concept_ref c ON c.iri = m.concept_iri
            WHERE m.src_name = %s
            """,
            (term,),
        )
        samples = conn.fetchall(
            """
            SELECT source_pk, itemname, inspectionresult, inspectionresultrange,
                   resultstateclass
            FROM diabetes.stg_lis_result WHERE itemname = %s
            ORDER BY source_pk LIMIT 3
            """,
            (term,),
        )
    return {
        "term": term,
        "upstreamSamples": samples,
        "baseline": {
            "approach": "semantic_link：字符串名称匹配",
            "links": [
                {"iri": r["concept_iri"], "label": r["concept_label"],
                 "relation": r["relation"], "confidence": float(r["confidence"]),
                 "verified": r["verified"]}
                for r in wfs_rows
            ],
            "hasUnit": False,
            "hasThreshold": False,
            "hasProvenance": False,
        },
        "ontology": {
            "approach": "本方案：概念 + 单位 + 可用性判定 + 出处",
            "mappings": ours,
        },
    }
