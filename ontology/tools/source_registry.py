#!/usr/bin/env python3
"""S3 第 0 层：knowledges/ → dmo:GuidelineSource 实例。

    python3 ontology/tools/source_registry.py            # 生成 dist/sources.ttl
    python3 ontology/tools/source_registry.py --report   # 只看清单，不写文件

**全程不经过 LLM，因此不可能有幻觉。** 只做三件事：
  1. 算 sha256 —— 知识文件一改，所有从它抽出的三元组自动过期，重跑有明确触发条件
  2. 从文件名前缀判定发布机构，从正文用正则抠发布/审阅年份
  3. 判定这份文件到底有没有正文（§7 风险 1 的机械化）

**刻意不填 sourceUrl。** 原文里没有 URL，凭文件名猜链接就是编造出处——
而 provenance 是这个项目相对纯 RAG 的核心卖点，宁可留空也不能编。
待 imports_fetch.py 或人工回填。
"""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGES = ROOT / "ontology" / "knowledges"
DEFAULT_OUT = ROOT / "ontology" / "dist" / "sources.ttl"

VOCAB = "https://example.org/dmo#"
IDNS = "https://example.org/dmo/id/"

PUBLISHERS = {"niddk": "NIDDK", "cdc": "CDC", "fda": "FDA", "nhc": "NHC"}

YEAR_PATTERNS = [
    re.compile(r"Last Reviewed\s+[A-Za-z]+\s+(\d{4})", re.I),
    re.compile(r"^[A-Z]{3,10}\s+\d{1,2},\s*(\d{4})\s*$", re.M),
    re.compile(r"发布时间[：:\s]*(\d{4})"),
    re.compile(r"Updated\s+[A-Za-z]+\s+\d{1,2},\s*(\d{4})", re.I),
]

# 正文判定阈值：长句（>60 字符）少于这个数，基本可以断定只抓到了导航壳。
SHELL_LINE_THRESHOLD = 8


def esc(s: str) -> str:
    return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def profile(path: Path) -> dict:
    raw = path.read_bytes()
    text = raw.decode("utf-8", "replace")
    long_lines = [l for l in text.splitlines() if len(l.strip()) > 60]

    year = None
    for pat in YEAR_PATTERNS:
        m = pat.search(text)
        if m:
            year = int(m.group(1))
            break

    prefix = path.stem.split("-", 1)[0]
    return {
        "sourceId": path.stem,
        "localFile": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "byteSize": len(raw),
        "longLines": len(long_lines),
        "publisher": PUBLISHERS.get(prefix, "Other"),
        "publishedYear": year,
        "isShell": len(long_lines) < SHELL_LINE_THRESHOLD,
    }


def emit(records: list[dict]) -> str:
    L = [
        "# 由 source_registry.py 生成，不要手改。全程无 LLM 参与。",
        "# 目标 named graph：urn:dmo:sources",
        "",
        f"@prefix dmo:   <{VOCAB}> .",
        f"@prefix dmoid: <{IDNS}> .",
        "@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix xsd:   <http://www.w3.org/2001/XMLSchema#> .",
        "",
        "# publisher 是 enum 数据属性（见 graph JSON），此处按字面量写入。",
        "# sourceUrl 刻意留空 —— 原文无链接，猜链接等于编造出处。",
        "",
    ]
    for r in records:
        uri = f"dmoid:guidelineSource/{r['sourceId']}"
        L.append(f"<{IDNS}guidelineSource/{r['sourceId']}> a dmo:GuidelineSource ;")
        L.append(f'    rdfs:label "{esc(r["sourceId"])}" ;')
        L.append(f'    dmo:sourceId "{esc(r["sourceId"])}" ;')
        L.append(f'    dmo:publisher "{r["publisher"]}" ;')
        L.append(f'    dmo:localFile "{esc(r["localFile"])}" ;')
        L.append(f'    dmo:sha256 "{r["sha256"]}" ;')
        L.append(f'    dmo:byteSize "{r["byteSize"]}"^^xsd:integer ;')
        if r["publishedYear"]:
            L.append(f'    dmo:publishedYear "{r["publishedYear"]}"^^xsd:integer ;')
        if r["isShell"]:
            L.append(
                '    dmo:contentStatus "shell" ;  # ⚠️ 只抓到网页导航，无正文'
            )
            L.append(
                '    rdfs:comment "正文缺失，不参与抽取。见 SEMANTIC-LAYER-PLAN §7 风险 1。" ;'
            )
        else:
            L.append('    dmo:contentStatus "substantive" ;')
        L.append("    .")
        L.append("")
        _ = uri
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="knowledges/ → GuidelineSource 实例（零幻觉）")
    ap.add_argument("--dir", type=Path, default=KNOWLEDGES)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--report", action="store_true", help="只打印清单，不写文件")
    args = ap.parse_args()

    files = sorted(args.dir.glob("*.txt"))
    if not files:
        raise SystemExit(f"{args.dir} 下没有 .txt")
    records = [profile(f) for f in files]

    shells = [r for r in records if r["isShell"]]
    no_year = [r for r in records if not r["publishedYear"]]

    print(f"{'source-id':<40} {'机构':<6} {'年份':<6} {'长句':<5} 状态")
    print("─" * 74)
    for r in records:
        status = "⚠️ 空壳" if r["isShell"] else "正文"
        yr = r["publishedYear"] or "—"
        print(
            f"{r['sourceId']:<40} {r['publisher']:<6} {str(yr):<6} "
            f"{r['longLines']:<5} {status}"
        )
    print("─" * 74)
    print(f"共 {len(records)} 份；空壳 {len(shells)} 份；年份未抠到 {len(no_year)} 份")
    if shells:
        print("\n⚠️ 空壳文件（已标 contentStatus=shell，不参与抽取）：")
        for r in shells:
            print(f"    {r['localFile']}（长句仅 {r['longLines']} 行）")
        print("    → 补抓 PDF 正文，或从来源清单划掉。见 SEMANTIC-LAYER-PLAN §7 风险 1。")
    print("\n• sourceUrl 全部留空：原文无链接，不编造。待人工或 imports_fetch.py 回填。")

    if args.report:
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(emit(records), encoding="utf-8")
    print(f"\n✓ 已写出 {args.out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
