"""出处真伪裁决 —— 整个裁决族里依赖最少、最确定的一环。

不需要患者、不需要 PostgreSQL、不需要跑规则链：只拿调用方声称的 quote / sha256
去比对 `urn:dmo:seed` 里那 31 条**已被逐字核验过**的 SourcePassage
（`ontology/tools/verify_passages.py` 保证 quote 逐字出现在语料里、哈希对得上）。

## 五个判定值，两两不相交

| verdict | 判据 | 说明 |
|---|---|---|
| `verbatim`     | 引文逐字命中，且（若给了）哈希与该条相符 | 唯一一个「引用成立」 |
| `hash-only`    | 哈希命中，但引文与该条不一致（或未给引文） | ★ **引文被改写** —— 最该抓的一类 |
| `quote-only`   | 引文逐字命中，但给的哈希与该条不符       | 哈希是编的，或指向了别的出处 |
| `not-verbatim` | 引文与某条存在**包含关系**，哈希未命中     | 截取或加话，不是逐字引用 |
| `fabricated`   | 引文与哈希都无任何对应                    | 本库没有这句话 |

## 为什么只做逐字与包含，不做模糊匹配

`terms/resolve.py` 的第一条口径是「未命中只记账，绝不猜：没有编辑距离、没有 trigram、
没有 embedding」。出处这一层更严 —— `verify_passages.py` 写着「漏报（说找不到）
远比误报（说找到了）安全」。相似度 0.87 判成「引用成立」，等于用一个数字把伪造洗白。

包含关系是**纯机械可判定**的，不属于猜，所以留着；它能把「改写/截取」与
「凭空编造」分开，这个区分对调用方很有用。

## `fabricated` 不是道德判断

它的含义严格是「本库这 31 条可引用出处里没有逐字对应」。调用方引的可能是一份
本仓库根本没收录的指南 —— 那也叫 fabricated，因为**本系统无法为它背书**。
`reason` 里会把这句话说清楚，不要让调用方以为系统在指控谁造假。
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..graph import passages as passages_mod
from ..rdf.canonical import collapse, passage_hash

# 短于这个长度的引文不做包含匹配。"6.5%" 会被半数 passage 包含，
# 报出来全是噪声，还会把 fabricated 误洗成 not-verbatim。
MIN_CONTAIN_LEN = 8

MAX_CITATIONS = 200

NOT_IN_LIBRARY = (
    "本库 {n} 条可引用出处里没有逐字对应。这不等于指控伪造 —— "
    "也可能引自本仓库未收录的资料；但本系统无法为它背书。"
)


class CitationError(ValueError):
    """入参本身不成立。消息直接给调用方看，不是内部堆栈。"""


def _norm_hash(v: Any) -> str | None:
    if not isinstance(v, str) or not v.strip():
        return None
    return v.strip().lower()


def _parse(raw: Any, i: int) -> tuple[str | None, str | None]:
    if not isinstance(raw, dict):
        raise CitationError(f"第 {i + 1} 条不是对象。每条形如 "
                            '{"quote": "...", "sha256": "..."}')
    quote = raw.get("quote")
    quote = quote if isinstance(quote, str) and quote.strip() else None
    sha = _norm_hash(raw.get("sha256") or raw.get("contentHash"))
    if quote is None and sha is None:
        # 两个都空判不了，但返回 fabricated 会让人以为「查过了、没有」。
        # 没查过就是没查过。
        raise CitationError(
            f"第 {i + 1} 条既没有 quote 也没有 sha256，无从核对。"
            "至少给一个 —— 只给 sha256 时本系统只能核对哈希，无法核对引文逐字性。")
    return quote, sha


def _nearest(index: passages_mod.PassageIndex, norm: str) -> list[dict[str, Any]]:
    """包含关系的候选。纯字符串包含，不做任何相似度计算。"""
    if len(norm) < MIN_CONTAIN_LEN:
        return []
    out: list[tuple[int, dict[str, Any]]] = []
    for p in index.passages:
        pn = p.norm
        if len(pn) < MIN_CONTAIN_LEN:
            continue
        if pn in norm:
            rel, overlap = "citation-contains-passage", len(pn)
        elif norm in pn:
            rel, overlap = "citation-is-fragment-of-passage", len(norm)
        else:
            continue
        out.append((overlap, {"relation": rel, "passage": p.as_dict()}))
    # 重叠越长越可能是同一段话。
    out.sort(key=lambda t: -t[0])
    return [d for _, d in out[:3]]


def _one(index: passages_mod.PassageIndex, quote: str | None, sha: str | None,
         i: int) -> dict[str, Any]:
    norm = collapse(quote) if quote else None
    computed = passage_hash(quote) if quote else None
    by_quote = index.lookup_quote(quote)
    by_hash = index.lookup_hash(sha)

    result: dict[str, Any] = {
        "index": i,
        "quote": quote,
        "sha256Claimed": sha,
        "sha256Computed": computed,
    }

    if by_quote and sha and any(p.content_hash == sha for p in by_quote):
        matched = [p for p in by_quote if p.content_hash == sha]
        result |= {
            "verdict": "verbatim",
            "reason": "引文逐字命中，哈希相符。",
            "matched": [p.as_dict() for p in matched],
        }
    elif by_quote and not sha:
        result |= {
            "verdict": "verbatim",
            "reason": ("引文逐字命中。未提供 sha256，已按 "
                       "sha256(collapse(quote)) 自行算出，见 sha256Computed。"),
            "matched": [p.as_dict() for p in by_quote],
        }
    elif by_quote:
        # 引文对、哈希不对。哈希可能是编的，也可能指向另一条真实出处 —— 后者更值得说。
        elsewhere = by_hash
        reason = "引文逐字命中，但你给的 sha256 与它不符。"
        reason += (
            f"该哈希指向的是另一条出处：{'、'.join(p.passage_id for p in elsewhere)}。"
            if elsewhere else f"该哈希在本库不存在。这条引文的正确哈希是 {computed}。")
        result |= {
            "verdict": "quote-only",
            "reason": reason,
            "matched": [p.as_dict() for p in by_quote],
            "hashPointsTo": [p.as_dict() for p in elsewhere],
        }
    elif by_hash:
        result |= {
            "verdict": "hash-only",
            "reason": (
                "哈希命中，但未提供引文，逐字性无从核对。"
                if quote is None else
                "哈希命中，但你给的引文与该条原文不一致 —— 引文在转述中被改写过。"
                "本库的 contentHash 就是引文本身的哈希，两者对不上即说明引文变了。"),
            "matched": [p.as_dict() for p in by_hash],
        }
    else:
        near = _nearest(index, norm) if norm else []
        if near:
            result |= {
                "verdict": "not-verbatim",
                "reason": ("引文与本库某条出处存在包含关系，但不是逐字引用，哈希也未命中。"
                           "截取或加话都会让 contentHash 失效。"),
                "nearest": near,
            }
        else:
            result |= {
                "verdict": "fabricated",
                "reason": NOT_IN_LIBRARY.format(n=len(index.passages)),
            }
    return result


def check_citations(cfg: Config, citations: Any, *,
                    asserted_by: str | None = None,
                    refresh: bool = False) -> dict[str, Any]:
    """逐条裁决一批引用。**完全确定性**：同一批输入在同一版知识层下永远同一结果。"""
    from ..query.hybrid import DISCLAIMER

    if not isinstance(citations, list) or not citations:
        raise CitationError(
            'body 必须含非空的 "citations": [{"quote": "...", "sha256": "..."}, ...]')
    if len(citations) > MAX_CITATIONS:
        raise CitationError(f"一次最多 {MAX_CITATIONS} 条，收到 {len(citations)} 条。")

    parsed = [_parse(c, i) for i, c in enumerate(citations)]
    index = passages_mod.load(cfg, refresh=refresh)
    results = [_one(index, q, s, i) for i, (q, s) in enumerate(parsed)]

    summary: dict[str, int] = {}
    for r in results:
        summary[r["verdict"]] = summary.get(r["verdict"], 0) + 1

    untrusted = sorted({
        p["passageId"]
        for r in results for p in r.get("matched", []) if not p["trusted"]
    })

    return {
        "results": results,
        "summary": summary,
        "checkedAgainst": {
            "passages": len(index.passages),
            "graph": passages_mod.TRUSTED_GRAPH,
            "verifiedBy": "ontology/tools/verify_passages.py（quote 逐字回原文 + 哈希一致）",
        },
        # 判定与谁说的无关，但记账要记全 —— 批量核对外部报告时这是唯一的归属线索。
        "assertedBy": asserted_by,
        "untrustedMatches": untrusted or None,
        "graphVersion": index.graph_version,
        "note": (
            "verbatim 的含义严格限定为「与本仓库当前版本知识层的某条可引用出处逐字一致」，"
            "不代表该引用适用于调用方的结论 —— 引文用对了地方没有，属于 "
            "/adjudicate/claim 的职责。"),
        "disclaimer": DISCLAIMER,
    }
