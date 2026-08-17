#!/usr/bin/env python3
"""S6 构建层校验：pyshacl 跑闭世界约束，违规则非零退出。

    python3 ontology/tools/validate_shacl.py
    python3 ontology/tools/validate_shacl.py --update-baseline   # 接受当前违规为已知

**这是 CI 的门禁**，纯 Python 无 Java，不依赖 GraphDB 在跑。
GraphDB 的 shapes graph 是服务层的增量保护（拦截未来写入），两者职责不同：
这里做全量体检，那里做入口检查。

⚠️ 为什么用基线文件而不是 `--allow N`
  违规里有两类东西混在一起：
    * 夹具的**刻意违规**（P001 触发禁忌、R005 缺单位、R006 单位不一致）——它们
      本来就该报，报不出来才是 bug；
    * 抽取产物的**真实缺陷**（模型抽出的 Contraindication 没带 rationale）。
  `--allow 7` 会把两类一起埋掉：以后新增一条真缺陷、同时修好一条夹具，
  总数还是 7，CI 全绿，问题却溜进去了。
  基线按「focusNode + 消息」逐条比对，新增的违规一定会亮，已修的会提示删基线。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = [
    ROOT / "ontology/dist/tbox-v2.ttl",   # V2；V1 的 tbox-generated.ttl 已不参与构建
    ROOT / "ontology/src/dmo-axioms.ttl",
    ROOT / "ontology/src/dmo-threshold-seed.ttl",
    ROOT / "ontology/src/dmo-risk-map.ttl",
    ROOT / "ontology/dist/sources.ttl",
    ROOT / "ontology/data/synthetic-patients.ttl",
]
SHAPES_DIR = ROOT / "ontology/shapes"
EXTRACT_DIR = ROOT / "ontology/dist/extract"
# 同步管线本地导出的患者图（R5 起产生），供 CI 在没有 GraphDB 时也能体检。
PATIENTS_DIR = ROOT / "ontology/dist/patients"


BASELINE = ROOT / "ontology/shapes/known-violations.tsv"


def load_baseline() -> set[tuple[str, str]]:
    if not BASELINE.exists():
        return set()
    out = set()
    for line in BASELINE.read_text(encoding="utf-8").splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        focus, _, msg = line.partition("\t")
        out.add((focus.strip(), msg.strip()))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="SHACL 全量校验（构建层门禁）")
    ap.add_argument("--allow", type=int, default=0,
                    help="（兼容旧用法）容忍的违规条数上限。优先用基线文件")
    ap.add_argument("--update-baseline", action="store_true",
                    help="把当前全部违规写进 known-violations.tsv。⚠️ 每条都要人工确认是刻意的")
    args = ap.parse_args()
    try:
        import pyshacl
        import rdflib
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
    if PATIENTS_DIR.is_dir():
        for f in sorted(PATIENTS_DIR.glob("*.ttl")):
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
    if args.update_baseline:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(f"{f}\t{m}" for f, m in rows)
        BASELINE.write_text(
            "# SHACL 已知违规基线。每行 focusNode<TAB>消息。\n"
            "# ⚠️ 加进来之前必须回答：这条是**刻意造的反例**，还是**真缺陷**？\n"
            "#    真缺陷不该进基线，该修数据或修抽取。\n"
            "# 用 `validate_shacl.py --update-baseline` 重新生成。\n"
            + body + "\n",
            encoding="utf-8",
        )
        print(f"✓ 已把 {len(rows)} 条违规写入 {BASELINE.relative_to(ROOT)}")
        return 0

    baseline = load_baseline()
    current = set(rows)
    new = sorted(current - baseline)
    fixed = sorted(baseline - current)

    if rows:
        print(f"\n违规 {len(rows)} 条（基线已知 {len(current & baseline)}）：")
        for focus, msg in rows:
            mark = " " if (focus, msg) in baseline else "★"
            print(f"  {mark} [{focus}] {msg}")
    if fixed:
        print(f"\n• 基线里有 {len(fixed)} 条已不再出现，可从 {BASELINE.name} 删掉：")
        for focus, msg in fixed:
            print(f"    [{focus}] {msg[:70]}")
    if not new:
        print("\n✓ 无新增违规（★ 标记为新增，本次 0 条）")
        return 0
    # 旧的 --allow 仍然生效，方便还没建基线的场景
    if len(rows) <= args.allow:
        print(f"\n• 在 --allow {args.allow} 容忍范围内，通过")
        return 0
    print(f"\n✗ 新增 {len(new)} 条违规（上面 ★ 标记的）", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
