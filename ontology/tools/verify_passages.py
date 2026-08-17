#!/usr/bin/env python3
"""校验每条 dmo:SourcePassage 的 quote 在语料里**逐字存在**，且 contentHash 对得上。

    python3 ontology/tools/verify_passages.py
    python3 ontology/tools/verify_passages.py --fix-hash   # 只重算哈希，不改 quote

这是「LLM 在高危层只做反向验证」那条原则的可执行版本：不让模型去原文里找数字，
而是拿着已写好的 quote 回原文核对。方向反过来，风险就从「编造」降级成「找不到」。

三类失败：
  MISSING  quote 在语料里找不到 —— 出处是编的，或者语料换版本了。**最严重**。
  HASH     quote 找到了但哈希对不上 —— 有人改了 quote 忘了重算哈希。
  NOSOURCE passage 没挂到任何 GuidelineSource 上 —— 追溯链断了。

匹配口径：两边都做 `collapse_ws(strip())` 后子串包含。刻意**不做**模糊匹配 ——
出处这一层，漏报（说找不到）远比误报（说找到了）安全。
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

import rdflib

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGES = ROOT / "ontology" / "knowledges"
SEED = ROOT / "ontology" / "src" / "dmo-threshold-seed.ttl"
AXIOMS = ROOT / "ontology" / "src" / "dmo-axioms.ttl"
RISK_MAP = ROOT / "ontology" / "src" / "dmo-risk-map.ttl"
DEFAULT_SOURCES = [SEED, AXIOMS, RISK_MAP]
DMO = rdflib.Namespace("https://example.org/dmo#")


def collapse(s: str) -> str:
    """规范化：strip + 内部连续空白折成单空格。与 src/dmo/rdf/canonical.py 逐字一致。"""
    return re.sub(r"\s+", " ", s.strip())


def passage_hash(quote: str) -> str:
    return hashlib.sha256(collapse(quote).encode("utf-8")).hexdigest()


def load_corpus() -> dict[str, str]:
    """sourceId → 规范化后的全文。sourceId 取自文件名（与 source_registry.py 一致）。"""
    return {
        p.stem: collapse(p.read_text(encoding="utf-8", errors="replace"))
        for p in sorted(KNOWLEDGES.glob("*.txt"))
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="SourcePassage 逐字性与哈希校验")
    ap.add_argument("--src", type=Path, action="append", default=None,
                    help="要检查的 TTL，可多次给。默认 seed + axioms + risk-map")
    ap.add_argument("--fix-hash", action="store_true",
                    help="按当前 quote 重算 contentHash 并回写。⚠️ 只有在你确认 quote 本身正确时才用")
    args = ap.parse_args()

    sources = args.src or DEFAULT_SOURCES
    g = rdflib.Graph()
    for p in sources:
        if p.exists():
            g.parse(p, format="turtle")

    corpus = load_corpus()
    if not corpus:
        print(f"✗ 语料目录为空：{KNOWLEDGES}", file=sys.stderr)
        return 1

    # passage → 它归属的 sourceId（通过 GuidelineSource dmo:hasPassage）
    owner: dict[rdflib.term.Node, str] = {}
    for src, _, psg in g.triples((None, DMO.hasPassage, None)):
        owner[psg] = str(src).rsplit("/", 1)[-1]

    problems: list[tuple[str, str, str]] = []
    fixes: list[tuple[str, str, str]] = []
    ok = 0

    passages = sorted(g.subjects(rdflib.RDF.type, DMO.SourcePassage), key=str)
    for psg in passages:
        pid = str(g.value(psg, DMO.passageId) or psg)
        quote = str(g.value(psg, DMO.quote) or "")
        stored = str(g.value(psg, DMO.contentHash) or "")
        if not quote:
            problems.append(("MISSING", pid, "没有 quote"))
            continue

        actual = passage_hash(quote)
        if stored != actual:
            if args.fix_hash:
                fixes.append((pid, stored, actual))
            else:
                problems.append(("HASH", pid, f"存 {stored[:16]}… 实际 {actual[:16]}…"))

        sid = owner.get(psg)
        if sid is None:
            problems.append(("NOSOURCE", pid, "没有 GuidelineSource 通过 hasPassage 认领"))
            continue
        if sid not in corpus:
            problems.append(("NOSOURCE", pid, f"来源 {sid} 在 knowledges/ 里没有对应 .txt"))
            continue
        if collapse(quote) not in corpus[sid]:
            problems.append(("MISSING", pid, f"在 {sid}.txt 里找不到这段原文"))
            continue
        ok += 1

    if args.fix_hash and fixes:
        text = SEED.read_text(encoding="utf-8")
        for pid, old, new in fixes:
            if old and old in text:
                text = text.replace(old, new)
        SEED.write_text(text, encoding="utf-8")
        print(f"✓ 重算了 {len(fixes)} 条 contentHash")

    print(f"检查 {len(passages)} 条 SourcePassage，{ok} 条逐字命中语料")
    if problems:
        print(f"\n✗ {len(problems)} 条有问题：", file=sys.stderr)
        for kind, pid, detail in problems:
            print(f"  [{kind:8}] {pid}: {detail}", file=sys.stderr)
        return 1
    print("✓ 全部 quote 逐字可回溯，哈希一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
