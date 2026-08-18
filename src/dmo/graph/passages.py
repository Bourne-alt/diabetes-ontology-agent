"""可引用出处（`dmo:SourcePassage`）的底表加载与索引。

`GET /graph/passages` 与 `POST /adjudicate/citations` **共用这一份**。分成两份的话，
「查得到的出处」和「裁决时认的出处」会慢慢分叉，而分叉的那一天没有任何报错。

## 为什么这层能当基准真值

`urn:dmo:seed` 里的 31 条 passage 全部经 `ontology/tools/verify_passages.py` 校验过：
quote 逐字出现在 `ontology/knowledges/*.txt` 里，contentHash 与 `passage_hash(quote)` 相等。
换句话说**这批数据本身已经被机械证明过**，拿它裁决别人的引用才站得住。

抽取图（`urn:dmo:extract:*`）里的证据是 `dmo:evidenceQuote` 裸字符串，不是
`SourcePassage`，压根进不了这张表 —— 那些没人逐字核过，不能当基准。
真要有 SourcePassage 从别的图混进来，`graph` 字段会如实标出，`trusted` 置 false。

## ⚠️ contentHash 不唯一

`contentHash = sha256(collapse(quote))`，所以**引文相同的两条 passage 哈希必然相同**：
OGTT2H-DIABETES-Q 与 RPG-DIABETES-Q 的 quote 都是 "200 mg/dL or above"。
索引因此是 `hash → list[Passage]`，不是 `hash → Passage`。写成后者会静默丢一条，
`citedBy` 少一半而不报错 —— 正是本仓库最怕的那类失败。

## 知识侧不写 GRAPH

出处、阈值、风险规则全在知识侧。包进 `GRAPH <urn:dmo:seed>` 就吃不到 owl2-rl
的物化边，查询不报错、答案少一半（[GRAPHDB-USAGE.md](../../../docs/GRAPHDB-USAGE.md)）。
唯一的例外是最后那个 `OPTIONAL { GRAPH ?graph { … } }`：它只用来回答「这条来自哪个图」，
是**额外**信息，拿不到也不影响主模式。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import Config
from ..rdf.canonical import collapse

# 人工策展 + 逐字核验过的那一个图。只有它算基准真值。
TRUSTED_GRAPH = "urn:dmo:seed"

PREFIXES = """
PREFIX dmo:  <https://example.org/dmo#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""

_Q_PASSAGES = PREFIXES + """
SELECT ?psg ?passageId ?locator ?quote ?contentHash ?sourceId ?publisher ?graph
WHERE {
  ?psg a dmo:SourcePassage ; dmo:quote ?quote .
  OPTIONAL { ?psg dmo:passageId ?passageId }
  OPTIONAL { ?psg dmo:locator ?locator }
  OPTIONAL { ?psg dmo:contentHash ?contentHash }
  OPTIONAL { ?src dmo:hasPassage ?psg .
             OPTIONAL { ?src dmo:sourceId ?sourceId }
             OPTIONAL { ?src dmo:publisher ?publisher } }
  OPTIONAL { GRAPH ?graph { ?psg a dmo:SourcePassage } }
}
"""

# 谁引用了这条出处。这是 citationCheck 判「张冠李戴」的原料：
# 引文真实存在、但它支撑的根本不是调用方声称的那件事。
_Q_CITERS = PREFIXES + """
SELECT ?psg ?citerKind ?citer ?citerId ?citerLabel
WHERE {
  { ?citer dmo:thresholdCitesPassage ?psg ; dmo:thresholdId ?citerId .
    BIND("DiagnosticThreshold" AS ?citerKind) }
  UNION
  { ?citer dmo:riskRuleCitesPassage ?psg ; dmo:riskRuleId ?citerId .
    OPTIONAL { ?citer rdfs:label ?citerLabel }
    BIND("RiskRule" AS ?citerKind) }
}
"""


@dataclass
class Passage:
    iri: str
    passage_id: str
    locator: str | None
    quote: str
    content_hash: str
    source_id: str | None
    publisher: str | None
    graph: str | None
    cited_by: list[dict[str, str]] = field(default_factory=list)

    @property
    def norm(self) -> str:
        """规范化引文。逐字比对一律在这上面做，与 verify_passages.py 同一口径。"""
        return collapse(self.quote)

    @property
    def trusted(self) -> bool:
        return self.graph == TRUSTED_GRAPH

    def as_dict(self) -> dict[str, Any]:
        return {
            "iri": self.iri,
            "passageId": self.passage_id,
            "locator": self.locator,
            "quote": self.quote,
            "sha256": self.content_hash,
            "sourceId": self.source_id,
            "publisher": self.publisher,
            "graph": self.graph,
            "trusted": self.trusted,
            "citedBy": self.cited_by,
        }


@dataclass
class PassageIndex:
    passages: list[Passage]
    by_hash: dict[str, list[Passage]]
    by_id: dict[str, Passage]
    graph_version: str

    def lookup_hash(self, sha256: str | None) -> list[Passage]:
        if not sha256:
            return []
        return self.by_hash.get(sha256.strip().lower(), [])

    def lookup_quote(self, quote: str | None) -> list[Passage]:
        """逐字命中。

        `contentHash` 就是 `sha256(collapse(quote))`，所以「引文逐字相同」等价于
        「算出来的哈希在索引里」—— 不必再遍历一遍做字符串比较。
        """
        if not quote or not quote.strip():
            return []
        from ..rdf.canonical import passage_hash

        return self.by_hash.get(passage_hash(quote), [])


_CACHE: tuple[str, PassageIndex] | None = None


def load(cfg: Config, *, refresh: bool = False) -> PassageIndex:
    """装载并索引全部 SourcePassage。按 graph_version 缓存。

    31 条数据，两次 SPARQL。缓存不是为了性能，是为了**同一次裁决里的所有条目
    对着同一份快照判**：知识层在一次批量裁决中途被重载的话，前后条目的判据不同，
    而返回体里的 graphVersion 只有一个 —— 那就是在说谎。
    """
    global _CACHE
    from ..graph.client import GraphDBClient
    from ..terms.concepts import graph_version

    version = graph_version()
    if not refresh and _CACHE is not None and _CACHE[0] == version:
        return _CACHE[1]

    client = GraphDBClient(cfg)
    by_iri: dict[str, Passage] = {}
    for r in client.sparql_csv(_Q_PASSAGES):
        iri = r["psg"]
        p = by_iri.get(iri)
        if p is None:
            p = Passage(
                iri=iri,
                passage_id=r.get("passageId") or iri.rsplit("/", 1)[-1],
                locator=r.get("locator") or None,
                quote=r.get("quote") or "",
                content_hash=(r.get("contentHash") or "").strip().lower(),
                source_id=r.get("sourceId") or None,
                publisher=r.get("publisher") or None,
                graph=r.get("graph") or None,
            )
            by_iri[iri] = p
        else:
            # 一条 passage 被多个来源 hasPassage 认领时会多行。保留第一个非空的，
            # 但把图名收敛到可信图 —— 混装时不能因为行序不同得出不同的 trusted。
            p.source_id = p.source_id or (r.get("sourceId") or None)
            p.publisher = p.publisher or (r.get("publisher") or None)
            if r.get("graph") == TRUSTED_GRAPH:
                p.graph = TRUSTED_GRAPH

    for r in client.sparql_csv(_Q_CITERS):
        p = by_iri.get(r["psg"])
        if p is None:
            continue
        entry = {"kind": r["citerKind"], "id": r["citerId"], "iri": r["citer"]}
        if r.get("citerLabel"):
            entry["label"] = r["citerLabel"]
        if entry not in p.cited_by:
            p.cited_by.append(entry)
    for p in by_iri.values():
        p.cited_by.sort(key=lambda e: (e["kind"], e["id"]))

    by_hash: dict[str, list[Passage]] = {}
    for p in by_iri.values():
        if p.content_hash:
            by_hash.setdefault(p.content_hash, []).append(p)

    index = PassageIndex(
        passages=sorted(by_iri.values(), key=lambda p: p.passage_id),
        by_hash=by_hash,
        by_id={p.passage_id: p for p in by_iri.values()},
        graph_version=version,
    )
    _CACHE = (version, index)
    return index


def search(cfg: Config, *, sha256: str | None = None, q: str | None = None,
           passage_id: str | None = None, cited_by: str | None = None,
           limit: int = 50) -> dict[str, Any]:
    """`GET /graph/passages` 的实现。图探索族的第一个原语。

    四个筛选条件是**与**关系，全空则返回全部（31 条，本来就不多）。
    `q` 走规范化后的大小写不敏感子串 —— 这里是检索不是裁决，宽松无害；
    真要判引用成不成立请用 `/adjudicate/citations`，那边只认逐字。
    """
    index = load(cfg)
    rows = index.passages
    applied: dict[str, str] = {}

    if sha256:
        applied["sha256"] = sha256
        want = sha256.strip().lower()
        rows = [p for p in rows if p.content_hash == want]
    if passage_id:
        applied["passageId"] = passage_id
        rows = [p for p in rows if p.passage_id == passage_id]
    if q:
        applied["q"] = q
        needle = collapse(q).lower()
        rows = [p for p in rows if needle in p.norm.lower()]
    if cited_by:
        applied["citedBy"] = cited_by
        rows = [p for p in rows
                if any(c["id"] == cited_by for c in p.cited_by)]

    limit = max(1, min(limit, 200))
    total = len(rows)
    page = rows[:limit]

    return {
        "passages": [p.as_dict() for p in page],
        "total": total,
        "limit": limit,
        "filters": applied or None,
        # 空集与「没查到」是两回事 —— 必须说清是哪一种。
        "emptyReason": _empty_reason(index, applied) if total == 0 else None,
        "nextHops": _next_hops(page),
        "graphVersion": index.graph_version,
        "corpus": {
            "passages": len(index.passages),
            "graph": TRUSTED_GRAPH,
            "note": "抽取图里的证据是 dmo:evidenceQuote 裸字符串，不是 SourcePassage，"
                    "没人逐字核过，因此不在这张表里。",
        },
    }


def _empty_reason(index: PassageIndex, applied: dict[str, str]) -> str:
    n = len(index.passages)
    if not applied:
        return (f"本库一条 SourcePassage 都没有 —— 预期 31 条。"
                f"多半是 {TRUSTED_GRAPH} 没装载，跑 "
                "`python3 ontology/tools/load_graphdb.py`。")
    if "sha256" in applied:
        return (f"这个 sha256 在本库 {n} 条出处里不存在。若它来自某个模型的回答，"
                "那就是编出来的 —— 用 POST /adjudicate/citations 可以拿到逐条判定。")
    if "citedBy" in applied:
        return (f"没有出处被 {applied['citedBy']} 引用。要么这个 id 不存在，"
                "要么它确实没有可逐字引用的出处 —— 后者在风险规则里很常见，"
                "且**这类规则不参与 tier 计分**。用 GET /graph/rules 可以看全。")
    return (f"本库 {n} 条出处里没有包含这段文字的。检索走的是规范化子串匹配，"
            "不做模糊匹配 —— 出处这一层，漏报远比误报安全。")


def _next_hops(page: list[Passage]) -> list[dict[str, str]]:
    """可继续展开的下一跳。agent 不该靠猜谓词名和 URL 拼法。"""
    hops = [{
        "rel": "adjudicate",
        "endpoint": "POST /adjudicate/citations",
        "why": "拿这些出处逐条裁决某个模型给出的引用是否逐字成立",
    }]
    citers = sorted({(c["kind"], c["id"]) for p in page for c in p.cited_by})
    hops += [{
        "rel": "citedBy",
        "endpoint": f"GET /graph/passages?citedBy={cid}",
        "why": f"{kind} {cid} 引用的全部出处",
    } for kind, cid in citers[:10]]
    return hops
