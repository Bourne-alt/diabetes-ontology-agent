#!/usr/bin/env python3
"""S6 构建层校验：pyshacl 跑闭世界约束，违规则非零退出。

    python3 ontology/tools/validate_shacl.py
    python3 ontology/tools/validate_shacl.py --allow N   # 容忍 N 条已知违规

**这是 CI 的门禁**，纯 Python 无 Java，不依赖 GraphDB 在跑。
GraphDB 的 shapes graph 是服务层的增量保护（拦截未来写入），两者职责不同：
这里做全量体检，那里做入口检查。
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = [
    ROOT / "ontology/dist/tbox-generated.ttl",
    ROOT / "ontology/src/dmo-axioms.ttl",
    ROOT / "ontology/src/dmo-threshold-seed.ttl",
    ROOT / "ontology/dist/sources.ttl",
    ROOT / "ontology/data/synthetic-patients.ttl",
]
SHAPES_DIR = ROOT / "ontology/shapes"
EXTRACT_DIR = ROOT / "ontology/dist/extract"


def main() -> int:
    ap = argparse.ArgumentParser(description="SHACL 全量校验（构建层门禁）")
    ap.add_argument("--allow", type=int, default=0, help="容忍的违规条数上限")
    args = ap.parse_args()
    try:
        import rdflib, pyshacl
    except ImportError:
        raise SystemExit("需要 rdflib + pyshacl：uv sync")

    data = rdflib.Graph()
    loaded = []
    for f in DATA:
        if f.exists():
            data.parse(f, format="turtle"); loaded.append(f.name)
    if EXTRACT_DIR.is_dir():
        for d in sorted(EXTRACT_DIR.iterdir()):
            f = d / f"{d.name}.ttl"
            if f.exists():
                data.parse(f, format="turtle"); loaded.append(f.name)

    shapes = rdflib.Graph()
    for f in sorted(SHAPES_DIR.glob("*.ttl")):
        shapes.parse(f, format="turtle")

    print(f"数据 {len(data)} 三元组（{len(loaded)} 个文件） / shapes {len(shapes)} 三元组")
    conforms, rg, _ = pyshacl.validate(
        data, shacl_graph=shapes, advanced=True, inference="none", abort_on_first=False
    )
    SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
    rows = sorted(
        (str(rg.value(r, SH.focusNode) or "").split("/")[-1],
         str(rg.value(r, SH.resultMessage) or ""))
        for r in rg.subjects(rdflib.RDF.type, SH.ValidationResult)
    )
    if not rows:
        print("✓ 无违规")
        return 0
    print(f"\n违规 {len(rows)} 条：")
    for focus, msg in rows:
        print(f"  [{focus}] {msg}")
    if len(rows) <= args.allow:
        print(f"\n• 在 --allow {args.allow} 容忍范围内，通过")
        return 0
    print(f"\n✗ 违规 {len(rows)} 条 > 容忍上限 {args.allow}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
