#!/usr/bin/env python3
"""把 ontology/graph/diabetes-ontology.json 编译成 Ontology Playground / Fabric IQ
可导入的 RDF/XML，并顺带跑一遍 Playground 自己的校验规则。

输出格式严格对齐 Ontology-Playground 的 src/lib/rdf/serializer.ts，
校验规则对齐 src/store/designerStore.ts 的 validateOntology()，
这样文件在 Designer 里「Edit RDF → 粘贴 → Load into Designer」能无损往返。

用法：
    python3 ontology/tools/build_playground_rdf.py
    python3 ontology/tools/build_playground_rdf.py --check   # 只校验不写文件
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SRC = ROOT / "ontology" / "graph" / "diabetes-ontology.json"
DEFAULT_OUT = ROOT / "ontology" / "graph" / "diabetes-ontology.rdf"

# Fabric IQ 命名规则：1-26 字符，字母数字加连字符下划线，首尾必须是字母数字
FABRIC_IQ_NAME_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9_-]{0,24}[A-Za-z0-9])?$")

XSD_TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "decimal": "decimal",
    "double": "double",
    "date": "date",
    "datetime": "dateTime",
    "boolean": "boolean",
    "enum": "string",
}

VALID_CARDINALITIES = {"one-to-one", "one-to-many", "many-to-one", "many-to-many"}


def escape_xml(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def capitalize(text: str) -> str:
    return text[:1].upper() + text[1:]


def derive_base_uri(name: str) -> str:
    slug = re.sub(r"[^a-z0-9\s-]", "", name.lower())
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return f"http://example.org/ontology/{slug or 'unnamed'}/"


def validate(ontology: dict) -> list[str]:
    """复刻 designerStore.validateOntology()，外加几条本项目自己的约束。"""
    errors: list[str] = []
    entity_ids: set[str] = set()
    prop_types: dict[str, tuple[str, str]] = {}

    if not ontology.get("entityTypes"):
        errors.append("至少需要一个实体类型。")

    for e in ontology.get("entityTypes", []):
        label = e.get("name") or "Unnamed entity"
        eid = e.get("id")
        if not eid:
            errors.append(f'"{label}" 缺少 id。')
        elif eid in entity_ids:
            errors.append(f'实体 id 重复："{eid}"。')
        else:
            entity_ids.add(eid)

        if not FABRIC_IQ_NAME_RE.match(e.get("name", "")):
            errors.append(f'实体名 "{label}" 不符合 Fabric IQ 命名规则（≤26 字符、无空格）。')

        props = e.get("properties", [])
        if not any(p.get("isIdentifier") for p in props):
            errors.append(f'"{label}" 没有标识属性（isIdentifier）。')

        for p in props:
            pname, ptype = p.get("name", ""), p.get("type", "")
            if p.get("isIdentifier") and ptype not in ("string", "integer"):
                errors.append(f'"{label}.{pname}" 作为标识属性必须是 string 或 integer。')
            if ptype not in XSD_TYPE_MAP:
                errors.append(f'"{label}.{pname}" 的类型 "{ptype}" 非法。')
            if not FABRIC_IQ_NAME_RE.match(pname):
                errors.append(f'属性名 "{pname}"（{label}）不符合 Fabric IQ 命名规则。')
            if ptype == "enum" and not p.get("values"):
                errors.append(f'"{label}.{pname}" 是 enum 但没有给 values。')
            prev = prop_types.get(pname)
            if prev and prev[0] != ptype:
                errors.append(
                    f'属性名 "{pname}" 在 "{label}" 是 {ptype}，在 "{prev[1]}" 是 {prev[0]}；'
                    "Fabric IQ 要求同名属性跨实体类型一致。"
                )
            elif not prev:
                prop_types[pname] = (ptype, label)

    rel_ids: set[str] = set()
    for r in ontology.get("relationships", []):
        label = r.get("name") or "Unnamed relationship"
        rid = r.get("id")
        if not rid:
            errors.append(f'"{label}" 缺少 id。')
        elif rid in rel_ids:
            errors.append(f'关系 id 重复："{rid}"。')
        else:
            rel_ids.add(rid)
        if r.get("from") not in entity_ids:
            errors.append(f'"{label}" 的 from="{r.get("from")}" 不存在。')
        if r.get("to") not in entity_ids:
            errors.append(f'"{label}" 的 to="{r.get("to")}" 不存在。')
        if r.get("cardinality") not in VALID_CARDINALITIES:
            errors.append(f'"{label}" 的 cardinality="{r.get("cardinality")}" 非法。')

    return errors


def serialize(ontology: dict) -> str:
    base = derive_base_uri(ontology["name"])
    out: list[str] = ['<?xml version="1.0" encoding="UTF-8"?>']
    out.append("<rdf:RDF")
    out.append(f'    xml:base="{base}"')
    out.append('    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"')
    out.append('    xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"')
    out.append('    xmlns:owl="http://www.w3.org/2002/07/owl#"')
    out.append('    xmlns:xsd="http://www.w3.org/2001/XMLSchema#"')
    out.append(f'    xmlns:ont="{base}">')
    out.append("")

    out.append(f'    <owl:Ontology rdf:about="{base}">')
    out.append(f'        <rdfs:label>{escape_xml(ontology["name"])}</rdfs:label>')
    if ontology.get("description"):
        out.append(f'        <rdfs:comment>{escape_xml(ontology["description"])}</rdfs:comment>')
    out.append("    </owl:Ontology>")
    out.append("")

    out.append("    <!-- ===================== -->")
    out.append("    <!-- Entity Types (Classes) -->")
    out.append("    <!-- ===================== -->")
    out.append("")
    for e in ontology["entityTypes"]:
        cls = capitalize(e["id"])
        out.append(f'    <owl:Class rdf:about="{base}{cls}">')
        out.append(f'        <rdfs:label>{escape_xml(e["name"])}</rdfs:label>')
        if e.get("description"):
            out.append(f'        <rdfs:comment>{escape_xml(e["description"])}</rdfs:comment>')
        out.append(f'        <ont:icon>{escape_xml(e["icon"])}</ont:icon>')
        out.append(f'        <ont:color>{escape_xml(e["color"])}</ont:color>')
        out.append("    </owl:Class>")
        out.append("")

    out.append("    <!-- ================ -->")
    out.append("    <!-- Data Properties -->")
    out.append("    <!-- ================ -->")
    out.append("")
    for e in ontology["entityTypes"]:
        cls = capitalize(e["id"])
        for p in e["properties"]:
            xsd_local = XSD_TYPE_MAP[p["type"]]
            out.append(f'    <owl:DatatypeProperty rdf:about="{base}{e["id"]}_{p["name"]}">')
            out.append(f'        <rdfs:label>{escape_xml(p["name"])}</rdfs:label>')
            out.append(f'        <rdfs:domain rdf:resource="{base}{cls}"/>')
            out.append(
                f'        <rdfs:range rdf:resource="http://www.w3.org/2001/XMLSchema#{xsd_local}"/>'
            )
            if p.get("description"):
                out.append(f'        <rdfs:comment>{escape_xml(p["description"])}</rdfs:comment>')
            if p.get("isIdentifier"):
                out.append(
                    '        <ont:isIdentifier rdf:datatype='
                    '"http://www.w3.org/2001/XMLSchema#boolean">true</ont:isIdentifier>'
                )
            if p.get("unit"):
                out.append(f'        <ont:unit>{escape_xml(p["unit"])}</ont:unit>')
            if p.get("values"):
                out.append(f'        <ont:enumValues>{escape_xml(",".join(p["values"]))}</ont:enumValues>')
            out.append(f'        <ont:propertyType>{escape_xml(p["type"])}</ont:propertyType>')
            out.append("    </owl:DatatypeProperty>")
            out.append("")

    out.append("    <!-- ================== -->")
    out.append("    <!-- Object Properties -->")
    out.append("    <!-- ================== -->")
    out.append("")
    for r in ontology["relationships"]:
        out.append(f'    <owl:ObjectProperty rdf:about="{base}{r["id"]}">')
        out.append(f'        <rdfs:label>{escape_xml(r["name"])}</rdfs:label>')
        out.append(f'        <rdfs:domain rdf:resource="{base}{capitalize(r["from"])}"/>')
        out.append(f'        <rdfs:range rdf:resource="{base}{capitalize(r["to"])}"/>')
        if r.get("description"):
            out.append(f'        <rdfs:comment>{escape_xml(r["description"])}</rdfs:comment>')
        out.append(f'        <ont:cardinality>{escape_xml(r["cardinality"])}</ont:cardinality>')
        out.append(f'        <ont:fromEntityId>{escape_xml(r["from"])}</ont:fromEntityId>')
        out.append(f'        <ont:toEntityId>{escape_xml(r["to"])}</ont:toEntityId>')
        out.append("    </owl:ObjectProperty>")
        out.append("")
        for attr in r.get("attributes", []):
            out.append(f'    <owl:DatatypeProperty rdf:about="{base}{r["id"]}_{attr["name"]}">')
            out.append(f'        <rdfs:label>{escape_xml(attr["name"])}</rdfs:label>')
            out.append(
                f'        <rdfs:comment>Relationship attribute for {escape_xml(r["name"])}</rdfs:comment>'
            )
            out.append(f'        <ont:relationshipAttributeOf>{escape_xml(r["id"])}</ont:relationshipAttributeOf>')
            out.append(f'        <ont:attributeType>{escape_xml(attr["type"])}</ont:attributeType>')
            out.append("    </owl:DatatypeProperty>")
            out.append("")

    out.append("</rdf:RDF>")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只校验，不写文件")
    parser.add_argument(
        "--src",
        type=Path,
        default=DEFAULT_SRC,
        help="设计源 JSON（相对路径按仓库根目录解析）",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="输出 RDF/XML（相对路径按仓库根目录解析）",
    )
    args = parser.parse_args()

    src = args.src if args.src.is_absolute() else ROOT / args.src
    out = args.out if args.out.is_absolute() else ROOT / args.out
    ontology = json.loads(src.read_text(encoding="utf-8"))
    errors = validate(ontology)
    if errors:
        print(f"✗ 校验失败（{len(errors)} 条）：", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    n_ent = len(ontology["entityTypes"])
    n_prop = sum(len(e["properties"]) for e in ontology["entityTypes"])
    n_rel = len(ontology["relationships"])
    print(f"✓ 校验通过：{n_ent} 个实体类型 / {n_prop} 个属性 / {n_rel} 条关系")

    if args.check:
        return 0

    out.write_text(serialize(ontology), encoding="utf-8")
    try:
        display_out = out.relative_to(ROOT)
    except ValueError:
        display_out = out
    print(f"✓ 已写出 {display_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
