"""图的规范化内容哈希。幂等同步的全部依据。

    sha256( "\\n".join(sorted(非空 n-triples 行)) )

n-triples 而不是 turtle：turtle 的前缀、缩写、语句顺序都不唯一，同一个图
序列化两次可能得到不同字节。n-triples 每行一条、完全展开，排序后就是规范形。

⚠️ **图里一个空节点都不许有。**
   rdflib 每次解析都会给空节点铸新的 skolem ID，`_:Nb1f3…` 下次就是 `_:N7a2c…`，
   哈希永不稳定 —— 结果是每次 `dmo sync all` 都全量 PUT，幂等彻底失效，
   而且**不会报任何错**，只是每次都"有变化"。
   emit.py 出口有断言，assert_no_bnodes() 就是这条断言。
"""

from __future__ import annotations

import hashlib
import re

import rdflib


def collapse(s: str) -> str:
    """与 ontology/tools/verify_passages.py 的 collapse() 逐字一致。改一处必须改两处。"""
    return re.sub(r"\s+", " ", s.strip())


def passage_hash(quote: str) -> str:
    """SourcePassage.contentHash 的口径。种子 TTL 里的哈希由它生成。"""
    return hashlib.sha256(collapse(quote).encode("utf-8")).hexdigest()


def assert_no_bnodes(g: rdflib.Graph) -> None:
    bnodes = {
        t for triple in g for t in triple if isinstance(t, rdflib.BNode)
    }
    if bnodes:
        raise AssertionError(
            f"患者图里有 {len(bnodes)} 个空节点，内容哈希将永不稳定，同步无法幂等。"
            f"\n  样例：{sorted(str(b) for b in bnodes)[:3]}"
            f"\n  空节点的 skolem ID 每次解析都不同 —— 必须给每个节点铸确定性 IRI。"
        )


def graph_hash(g: rdflib.Graph) -> str:
    assert_no_bnodes(g)
    lines = sorted(
        line for line in g.serialize(format="nt").splitlines() if line.strip()
    )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
