"""结论裁决 —— 拿本体去核对**别人已经给出的结论**。

与 `query/` 的区别是提问方向反过来了：
    query      「这个患者什么情况」          → 本体产出结论
    adjudicate 「有人说了这句话，对不对」    → 本体核对结论

三条贯穿本包的口径，改任何一条之前先读 docs/ADJUDICATE-EXPLORE-API-PLAN.md §0：

  1. **裁决结果永远是枚举，永远不是布尔。** 返回 `{"reasonable": true}` 等于给外部
     系统发一枚「已通过本体校验」的印章 —— 本仓库 50 份语料覆盖的是很窄的一片，
     「没查到反驳证据」不等于「合理」。
  2. **`not-adjudicable` 是常见返回值，不是异常。** 与 `/risk` 上
     `Insufficient-Evidence` 才是常态同一条诚实标准。
  3. **谁说的不影响对不对。** `assertedBy` 只记账，绝不参与判定。
"""

from __future__ import annotations

from .citations import CitationError, check_citations
from .claim import adjudicate_claim
from .scope import describe as describe_scope

__all__ = ["CitationError", "adjudicate_claim", "check_citations", "describe_scope"]
