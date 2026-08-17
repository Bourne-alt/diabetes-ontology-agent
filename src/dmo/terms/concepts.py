"""GraphDB 概念 → diabetes.map_concept_ref 的幂等重建。

为什么要把概念抄一份到 SQL：`search_concept` 必须能对**中文表面形式**做模糊查找。
本体里的中文都在 `skos:altLabel` 上，SPARQL 能查，但：
  * 查中文子串要用 CONTAINS()，GraphDB 上没有索引，全图扫；
  * 真正的并集是「本体的 altLabel ∪ map_lab_term.src_name ∪ map_icd10.icd10name
    ∪ map_drug_term.src_name」—— 后三者只在 SQL 里，跨库 join 不了。
所以概念下沉到 SQL，做一次并集查询。这是投影不是副本：`sync-concepts` 全量重建。

graph_version 用**本地知识层文件的内容哈希**，不是 GraphDB 里算的：
本体是从这些文件装载进去的，文件哈希才是"这批映射对齐的是哪一版"的真答案。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..config import Config
from ..db.engine import onto_conn
from ..graph.client import GraphDBClient

ROOT = Path(__file__).resolve().parents[3]

# 决定 graph_version 的文件。改任何一个，映射就该被重新审视。
VERSIONED_FILES = (
    ROOT / "ontology/dist/tbox-v2.ttl",
    ROOT / "ontology/src/dmo-axioms.ttl",
    ROOT / "ontology/src/dmo-threshold-seed.ttl",
    ROOT / "ontology/src/dmo-risk-map.ttl",
)

PREFIXES = """
PREFIX dmo:  <https://example.org/dmo#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
"""

# concept_kind → (类, 编码谓词, 单位谓词)
KINDS: tuple[tuple[str, str, str | None, str | None], ...] = (
    ("LabTest", "dmo:LabTest", "dmo:labTestCode", "dmo:unitOfMeasure"),
    ("DiabetesType", "dmo:DiabetesType", "dmo:diabetesTypeCode", None),
    ("Complication", "dmo:Complication", "dmo:complicationCode", None),
    ("ComplicationStage", "dmo:ComplicationStage", "dmo:stageCode", None),
    ("DrugClass", "dmo:DrugClass", "dmo:drugClassCode", None),
    ("Medication", "dmo:Medication", "dmo:medicationCode", None),
    ("RiskFactor", "dmo:RiskFactor", None, None),
    ("Symptom", "dmo:Symptom", "dmo:symptomCode", None),
    ("LifestyleIntervention", "dmo:LifestyleIntervention", None, None),
)


def graph_version() -> str:
    h = hashlib.sha256()
    for f in VERSIONED_FILES:
        h.update(f.name.encode())
        h.update(f.read_bytes() if f.exists() else b"<missing>")
    return h.hexdigest()


# altLabel 里有逗号、分号、竖线（"Type 2 Diabetes, Adult Onset"），
# 常见分隔符全不安全。用 ASCII 单元分隔符 0x1F —— 自然语言里不可能出现。
ALT_SEP = "\x1f"


def _query(cls: str, code_pred: str | None, unit_pred: str | None) -> str:
    code = f"OPTIONAL {{ ?iri {code_pred} ?code }}" if code_pred else ""
    unit = f"OPTIONAL {{ ?iri {unit_pred} ?unit }}" if unit_pred else ""
    return f"""{PREFIXES}
SELECT ?iri ?label ?code ?unit (GROUP_CONCAT(DISTINCT ?alt; separator="\\u001F") AS ?alts)
WHERE {{
  ?iri a {cls} .
  # 只要有 IRI 的具名概念。空节点进不来 —— 它们的 skolem ID 每次装载都变。
  FILTER(!isBlank(?iri))
  OPTIONAL {{ ?iri rdfs:label ?label }}
  OPTIONAL {{ ?iri skos:altLabel ?alt }}
  {code}
  {unit}
}}
GROUP BY ?iri ?label ?code ?unit
"""


def sync(cfg: Config) -> int:
    client = GraphDBClient(cfg)
    version = graph_version()
    rows: list[tuple] = []
    per_kind: dict[str, int] = {}

    for kind, cls, code_pred, unit_pred in KINDS:
        got = client.sparql_csv(_query(cls, code_pred, unit_pred))
        per_kind[kind] = len(got)
        for r in got:
            alts = [a for a in (r.get("alts") or "").split(ALT_SEP) if a]
            rows.append((
                r["iri"], kind, r.get("code") or None, r.get("label") or None,
                alts, r.get("unit") or None, version,
            ))

    # 全量重建。`DELETE` 而不是 `TRUNCATE`：map_lab_term 等表有外键指过来，
    # TRUNCATE 会连带清掉人工核实过的映射 —— 那些是最贵的数据。
    # 用 upsert + 删除已消失的概念，保住引用完整性。
    with onto_conn(cfg) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO diabetes.map_concept_ref
                    (iri, concept_kind, code, label, alt_labels, unit_canonical, graph_version)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (iri) DO UPDATE SET
                    concept_kind = EXCLUDED.concept_kind,
                    code = EXCLUDED.code,
                    label = EXCLUDED.label,
                    alt_labels = EXCLUDED.alt_labels,
                    unit_canonical = EXCLUDED.unit_canonical,
                    graph_version = EXCLUDED.graph_version,
                    synced_at = now()
                """,
                rows,
            )
        stale = conn.fetchall(
            "SELECT iri, concept_kind, label FROM diabetes.map_concept_ref "
            "WHERE graph_version <> %s ORDER BY iri",
            (version,),
        )
        conn.commit()

    total = sum(per_kind.values())
    print(f"✓ 同步 {total} 个概念（graph_version={version[:12]}…）")
    for kind, n in sorted(per_kind.items(), key=lambda kv: -kv[1]):
        print(f"    {kind:<24} {n}")

    if stale:
        print(f"\n⚠️  {len(stale)} 个概念在本版知识层里已不存在，但仍留在索引里：")
        for r in stale[:15]:
            print(f"    [{r['concept_kind']}] {r['label'] or r['iri']}")
        if len(stale) > 15:
            print(f"    …… 另外 {len(stale) - 15} 个")
        print("  没有自动删除：可能有人工核实过的映射指着它们。")
        print("  逐条确认后手工 DELETE，或修好本体让它们回来。")
    return 0
