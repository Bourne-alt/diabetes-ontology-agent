#!/usr/bin/env python3
"""S1：把 ER 图编译成 OWL TBox 骨架。

    python3 ontology/tools/build_tbox.py
    python3 ontology/tools/build_tbox.py --src ontology/graph/diabetes-ontology-v2.json

产物 `ontology/dist/tbox-generated.ttl` **不手改**，每次幂等重生成。
手写公理在 `ontology/src/dmo-axioms.ttl`，两者在构建时合并。

映射规则见 docs/SEMANTIC-LAYER-PLAN.md §2.1。只做「可机械生成」的那一半；
subClassOf / disjointWith / equivalentClass / propertyChain 等必须手写，
因为 ER 图里根本没有这些信息。

§2.3 双轨制由图上的 `tbox.route` 标注驱动：
    class      方案 B —— OWL 2 punning，实例同时是 owl:Class（分型、并发症、分期）
    skos       方案 A —— 实例是 skos:Concept，挂在该类型的 ConceptScheme 下
    individual 默认 —— 实例是普通个体（患者、阈值、推荐……）
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SRC = ROOT / "ontology" / "graph" / "diabetes-ontology.json"
DEFAULT_OUT = ROOT / "ontology" / "dist" / "tbox-generated.ttl"

# 必须与 semantic_extract.py 的 VOCAB_URI / docs/DESIGN.md 完全一致。
# 对不上 = TBox 和 ABox 各说各话，SPARQL 静默返回空集。
VOCAB = "https://example.org/dmo#"

XSD = {
    "string": "xsd:string",
    "integer": "xsd:integer",
    "decimal": "xsd:decimal",
    "double": "xsd:double",
    "date": "xsd:date",
    "datetime": "xsd:dateTime",
    "boolean": "xsd:boolean",
    "enum": "xsd:string",  # 取值域由配套的 skos:ConceptScheme 表达
}

ROUTE_CLASS, ROUTE_SKOS, ROUTE_INDIVIDUAL = "class", "skos", "individual"


def cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def esc(s: str) -> str:
    return (
        str(s)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def route_of(entity: dict[str, Any]) -> str:
    return (entity.get("tbox") or {}).get("route", ROUTE_INDIVIDUAL)


def build(graph: dict[str, Any], src_name: str, with_haskey: bool = False) -> tuple[str, dict[str, int]]:
    entities = graph["entityTypes"]
    rels = graph.get("relationships", [])
    by_id = {e["id"]: e for e in entities}

    # 同名属性可能挂在多个实体上。OWL 里多条 rdfs:domain 是**交集**，
    # 直接写会推出「凡有 name 者既是 Patient 又是 LabTest」——必须用 owl:unionOf。
    prop_domains: dict[str, list[str]] = defaultdict(list)
    prop_def: dict[str, dict[str, Any]] = {}
    enum_values: dict[str, list[str]] = {}
    enum_conflicts: list[str] = []

    for e in entities:
        for p in e["properties"]:
            name = p["name"]
            prop_domains[name].append(e["id"])
            prev = prop_def.get(name)
            if prev is None:
                prop_def[name] = p
            elif prev["type"] != p["type"]:
                raise SystemExit(f"属性 {name} 类型冲突：{prev['type']} vs {p['type']}")
            if p["type"] == "enum":
                vals = list(p.get("values") or [])
                if name in enum_values and enum_values[name] != vals:
                    enum_conflicts.append(
                        f"{name}：{enum_values[name]} vs {vals}（已取并集）"
                    )
                    enum_values[name] = sorted(set(enum_values[name]) | set(vals))
                else:
                    enum_values[name] = vals

    L: list[str] = []
    a = L.append

    a(f"# 由 build_tbox.py 从 {src_name} 生成，不要手改。")
    a("# 手写公理见 ontology/src/dmo-axioms.ttl。")
    a("")
    a(f"@prefix dmo:  <{VOCAB}> .")
    a("@prefix owl:  <http://www.w3.org/2002/07/owl#> .")
    a("@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .")
    a("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .")
    a("@prefix skos: <http://www.w3.org/2004/02/skos/core#> .")
    a("@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .")
    a("")
    a(f"<{VOCAB.rstrip('#')}> a owl:Ontology ;")
    a(f'    rdfs:label "{esc(graph["name"])} — TBox 骨架" ;')
    a('    rdfs:comment "机械生成部分。公理层见 dmo-axioms.ttl。" .')
    a("")

    a("# ─── 标注属性 ────────────────────────────────────────────────")
    for ap, comment in (
        ("unit", "属性取值的计量单位"),
        ("evidenceQuote", "支持该断言的原文逐字片段"),
        ("tboxRoute", "该类型走 §2.3 的哪条路线：class / skos / individual"),
    ):
        a(f"dmo:{ap} a owl:AnnotationProperty ;")
        a(f'    rdfs:comment "{esc(comment)}" .')
    a("")

    # ── 类 ──────────────────────────────────────────────────────────
    a("# ─── 实体类型 → owl:Class ────────────────────────────────────")
    n_scheme = 0
    for e in entities:
        cls = cap(e["id"])
        route = route_of(e)
        a(f"dmo:{cls} a owl:Class ;")
        a(f'    rdfs:label "{esc(e["name"])}" ;')
        if e.get("description"):
            a(f'    rdfs:comment "{esc(e["description"])}" ;')
        a(f'    dmo:tboxRoute "{route}" ;')
        ident = next((p["name"] for p in e["properties"] if p.get("isIdentifier")), None)
        if ident and with_haskey:
            # ⚠️ 默认关闭。SEMANTIC-LAYER-PLAN §2.1 原本要求 isIdentifier → owl:hasKey，
            # 但实测 owlrl 的 prp-key 会把同类实例**无视键值差异**全部折叠成 owl:sameAs：
            # CKD-G1 与 CKD-G5 的 stageCode 明明不同，仍被判为 sameAs（202 对）。
            # 叠加 disjointWith 后整个本体不一致（T1DM ⊑ T2DM）。
            # 我们的 ABox URI 本来就由标识属性确定性铸造，hasKey 没有额外收益，
            # 因此改为 --with-haskey 显式开启，留给日后换 HermiT 时验证。
            a(f"    owl:hasKey ( dmo:{ident} ) ;")
        a("    .")
        if route == ROUTE_CLASS:
            a(f"# ↑ 方案 B（punning）：{cls} 的实例同时被断言为 owl:Class，")
            a(f"#   子类层次与 disjointWith 在 dmo-axioms.ttl 手写。")
        elif route == ROUTE_SKOS:
            a(f"dmo:{cls}Scheme a skos:ConceptScheme ;")
            a(f'    rdfs:label "{esc(e["name"])} 术语表" .')
            n_scheme += 1
        a("")

    # ── 数据属性 ────────────────────────────────────────────────────
    a("# ─── 属性 → owl:DatatypeProperty ─────────────────────────────")
    for name in sorted(prop_def):
        p = prop_def[name]
        doms = sorted({cap(d) for d in prop_domains[name]})
        a(f"dmo:{name} a owl:DatatypeProperty ;")
        a(f'    rdfs:label "{esc(name)}" ;')
        if len(doms) == 1:
            a(f"    rdfs:domain dmo:{doms[0]} ;")
        else:
            # 多个 domain 必须写成并集，否则 OWL 语义是交集
            union = " ".join(f"dmo:{d}" for d in doms)
            a(f"    rdfs:domain [ a owl:Class ; owl:unionOf ( {union} ) ] ;")
        a(f"    rdfs:range {XSD[p['type']]} ;")
        if p.get("description"):
            a(f'    rdfs:comment "{esc(p["description"])}" ;')
        if p.get("unit"):
            a(f'    dmo:unit "{esc(p["unit"])}" ;')
        a("    .")
    a("")

    # ── 枚举 → SKOS ────────────────────────────────────────────────
    a("# ─── enum 取值 → skos:ConceptScheme ──────────────────────────")
    n_concept = 0
    for name in sorted(enum_values):
        vals = enum_values[name]
        if not vals:
            continue
        scheme = f"dmo:{name}Scheme"
        a(f"{scheme} a skos:ConceptScheme ;")
        a(f'    rdfs:label "{esc(name)} 取值域" .')
        for v in vals:
            slug = "".join(ch if ch.isalnum() else "-" for ch in v).strip("-")
            a(f"dmo:{name}-{slug} a skos:Concept ;")
            a(f"    skos:inScheme {scheme} ;")
            a(f'    skos:prefLabel "{esc(v)}" .')
            n_concept += 1
        a("")

    # ── 对象属性 ────────────────────────────────────────────────────
    a("# ─── 关系 → owl:ObjectProperty ───────────────────────────────")
    n_func = n_inv = 0
    for r in rels:
        types = ["owl:ObjectProperty"]
        card = r["cardinality"]
        # many-to-one：每个主体至多一个客体 → 函数性
        # one-to-many：每个客体至多属于一个主体 → 反函数性
        if card == "many-to-one":
            types.append("owl:FunctionalProperty")
            n_func += 1
        elif card == "one-to-many":
            types.append("owl:InverseFunctionalProperty")
            n_inv += 1
        elif card == "one-to-one":
            types += ["owl:FunctionalProperty", "owl:InverseFunctionalProperty"]
            n_func += 1
            n_inv += 1
        a(f"dmo:{r['id']} a {', '.join(types)} ;")
        a(f'    rdfs:label "{esc(r["name"])}" ;')
        a(f"    rdfs:domain dmo:{cap(r['from'])} ;")
        a(f"    rdfs:range dmo:{cap(r['to'])} ;")
        if r.get("description"):
            a(f'    rdfs:comment "{esc(r["description"])}" ;')
        a("    .")
        for attr in r.get("attributes", []):
            a(f"dmo:{r['id']}-{attr['name']} a owl:DatatypeProperty ;")
            a(f'    rdfs:label "{esc(attr["name"])}" ;')
            a(f'    rdfs:comment "{esc(r["name"])} 的关系属性" ;')
            a("    .")
    a("")

    stats = {
        "classes": len(entities),
        "datatypeProperties": len(prop_def),
        "objectProperties": len(rels),
        "functional": n_func,
        "inverseFunctional": n_inv,
        "conceptSchemes": n_scheme + len([v for v in enum_values.values() if v]),
        "concepts": n_concept,
        "multiDomainProps": sum(1 for n in prop_domains if len(set(prop_domains[n])) > 1),
        "hasKey": sum(1 for e in entities if with_haskey and any(p.get("isIdentifier") for p in e["properties"])),
        "routeClass": sum(1 for e in entities if route_of(e) == ROUTE_CLASS),
        "routeSkos": sum(1 for e in entities if route_of(e) == ROUTE_SKOS),
    }
    if enum_conflicts:
        print("⚠ enum 取值冲突（已取并集，建议在图里统一）：", file=sys.stderr)
        for c in enum_conflicts:
            print(f"    {c}", file=sys.stderr)
    _ = by_id
    return "\n".join(L) + "\n", stats


def main() -> int:
    ap = argparse.ArgumentParser(description="ER 图 → OWL TBox 骨架（幂等）")
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true", help="只生成不写盘")
    ap.add_argument("--with-haskey", action="store_true",
                    help="发出 owl:hasKey。⚠️ owlrl 的 prp-key 有 bug，会导致本体不一致，仅供换 HermiT 后验证")
    args = ap.parse_args()

    graph = json.loads(args.src.read_text(encoding="utf-8"))
    ttl, stats = build(graph, args.src.name, with_haskey=args.with_haskey)

    print(f"✓ 从 {args.src.name} 生成 TBox 骨架")
    for k, v in stats.items():
        print(f"    {k:22} {v}")

    if args.check:
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(ttl, encoding="utf-8")
    # --out 传相对路径时 relative_to(ROOT) 会抛 ValueError，
    # 而文件其实已经写出去了 —— 退出码非零但产物存在，最容易误判成没生成。
    try:
        shown = args.out.resolve().relative_to(ROOT)
    except ValueError:
        shown = args.out
    print(f"✓ 已写出 {shown}（{len(ttl)} 字符）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
