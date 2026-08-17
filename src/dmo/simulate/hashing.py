"""derivationHash —— 确定性的机器可证明形式。

「本体推演是确定性的」这句话，靠嘴说没人信。这个哈希把它变成可当场验证的事实：
同一个问题问 5 遍，5 个哈希完全相同；同一个问题问 LLM 5 遍，答案会飘。

哈希覆盖推演结果的**全部输入**，缺一个都会让"同哈希不同结果"成为可能：

  pid            哪个患者
  graphVersion   本体源文件的内容哈希（terms/concepts.py）
  knowledgeSha   实际用到的知识层快照（防「源文件没改但库里被手工灌过」）
  rulesSha       规则集内容哈希（改一条规则，哈希必须变）
  hypotheses     假设事实的规范形式，排序后拼接

⚠️ 不含时间戳、不含请求 ID、不含随机数。含了就失去意义。
"""

from __future__ import annotations

import hashlib

from .hypothesis import Hypothesis


def derivation_hash(
    *,
    pid: str,
    graph_version: str,
    knowledge_sha: str,
    rules_sha: str,
    hypotheses: list[Hypothesis],
) -> str:
    h = hashlib.sha256()
    # 每段前缀字段名并用 \x1f 分隔 —— 防止字段边界歧义
    # （"ab"+"c" 与 "a"+"bc" 必须得到不同的哈希）。
    for label, value in (
        ("pid", pid),
        ("graphVersion", graph_version),
        ("knowledgeSha", knowledge_sha),
        ("rulesSha", rules_sha),
    ):
        h.update(f"{label}\x1f{value}\x1e".encode())
    # 假设事实排序后拼接：注入顺序不该影响结论，因此也不该影响哈希。
    for fp in sorted(x.fingerprint() for x in hypotheses):
        h.update(f"hypothesis\x1f{fp}\x1e".encode())
    return h.hexdigest()
