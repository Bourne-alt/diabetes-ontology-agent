"""确定性病程推演。

    「若给 P90002 补一条 2026-02-20 的 A1C 7.9%，结论会变成什么？」
      → Diagnosis 从 Provisional 变 Confirmed，因为 30 号规则数到了 2 个不同日期。

这是**条件推演**（若 X 则 Y），不是病程预测：假设值只能由调用方显式给出，
本包没有任何生成候选值的路径。风险分层依旧是有序枚举，不做算术、不转分数。

推演全程在内存 rdflib Dataset 里跑，对 GraphDB 只发 CONSTRUCT——
跑多少次，库里三元组数一条都不会变。理由见 sandbox.py 开头。
"""

from .hypothesis import HypothesisError
from .runner import simulate
from .sandbox import SandboxError

__all__ = ["simulate", "HypothesisError", "SandboxError"]
