"""自由 SPARQL 的静态检查器 —— 逃生口的门。

## 为什么有这个东西

`query/templates.py` 按严重程度排了三条不让 LLM 自由写 SPARQL 的理由，最狠的一条是
**静默少返**：写错 GRAPH 子句查询不报错，只是答案少一半，看输出发现不了。

`/graph/{concepts,node,neighbors,taxonomy,path,provenance}` 那一族的做法是把 GRAPH 子句
收回服务端，让 agent 只决定「下一跳」。那覆盖了绝大多数探查，但**问题形状事先无法枚举**
的时候仍然需要一个口子。这个模块就是那个口子的门。

推翻「不让 LLM 自由写 SPARQL」的前提条件只有一条：
**把最严重的两个理由从「靠人自觉」变成「机械可检测」。** 二者恰好都可以 ——
规则 A 与规则 B 是纯语法可判定的。

## 拒绝理由写给模型看

这些消息会作为 observation 回给调用方（多半是个模型）自我修正。写
"guard violation: rule A" 等于浪费一轮 —— 直接告诉它该加哪一句。

## 剥噪声：两份文本，用途不同

  * 剥注释后的文本   → 规则 A/B/C 用。它们要看 IRI 和字符串字面量本身
                       （`STRSTARTS(STR(?pg),"urn:dmo:patient:")` 里的守卫就是字面量）。
  * 再剥字面量的文本 → 规则 D 用。SPARQL 注释或字符串里出现 `INSERT` 不该被拦，
                       与 `db/engine.py` 的 `strip_sql_noise` 同一个理由。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# 患者图前缀守卫。与 query/templates.PG_GUARD 同源 —— 这个仓库不允许同一件事有两份定义。
PATIENT_PREFIX = "urn:dmo:patient:"
FIXTURE_GRAPH = "urn:dmo:data"

# 知识侧的具名图。写死它们就吃不到 owl2-rl 的物化边。
KNOWLEDGE_GRAPHS = ("urn:dmo:seed", "urn:dmo:tbox", "urn:dmo:sources",
                    "urn:dmo:inferred", "urn:dmo:extract:")

WRITE_VERBS = ("INSERT", "DELETE", "DROP", "CLEAR", "LOAD", "CREATE",
               "MOVE", "COPY", "ADD", "WITH")
READ_FORMS = ("SELECT", "ASK", "CONSTRUCT", "DESCRIBE")

MAX_ROWS = 200

_PATIENT_IRI = re.compile(r"<(https?://[^>]*?/patient/[^>]+)>")

_GRAPH_VAR = re.compile(r"\bGRAPH\s+\?(\w+)")
_GRAPH_IRI = re.compile(r"\bGRAPH\s+<([^>]+)>")
_TRAILING_LIMIT = re.compile(r"\bLIMIT\s+(\d+)\s*$", re.IGNORECASE)


@dataclass
class Verdict:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rewrites: list[str] = field(default_factory=list)
    query: str = ""
    form: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"passed": self.ok, "form": self.form, "reasons": self.reasons,
                "warnings": self.warnings, "rewrites": self.rewrites}


def _scan(q: str, *, blank_literals: bool) -> str:
    """一次扫描剥掉注释（可选连字面量一起剥）。

    ⚠️ **不能用 `re.sub(r"#[^\n]*", "", q)`。** 本体的词汇命名空间是
    `https://example.org/dmo#`，正则会把 `<https://example.org/dmo#>` 的 `#>` 当成行注释
    吃掉 —— 连闭合的 `>` 一起 —— 于是整条查询被粘成一个巨大的「IRI」，
    后面所有规则都在一段面目全非的文本上跑。

    这个 bug 不报错：guard 照常给判定，只是判在错的输入上。**又一次静默失败。**
    所以必须逐字符扫，`#` 只有在 `<…>` 与字符串字面量之外才算注释。
    """
    out: list[str] = []
    i, n = 0, len(q)
    while i < n:
        ch = q[i]
        if ch == "#":
            j = q.find("\n", i)
            out.append(" ")
            i = n if j < 0 else j
            continue
        if ch == "<":
            j = q.find(">", i)
            # IRI 里不会有空白；有空白就不是 IRI，是小于号
            if j > i and not any(c.isspace() for c in q[i + 1:j]):
                out.append(q[i:j + 1])
                i = j + 1
                continue
        if ch in ('"', "'"):
            triple = q[i:i + 3]
            quote = triple if triple in ('"""', "'''") else ch
            j = i + len(quote)
            while j < n:
                if q[j] == "\\":
                    j += 2
                    continue
                if q.startswith(quote, j):
                    j += len(quote)
                    break
                j += 1
            out.append('""' if blank_literals else q[i:j])
            i = j
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def strip_comments(q: str) -> str:
    """只剥注释。规则 A/B/C 用 —— 它们要看 IRI 和字面量本身。"""
    return _scan(q, blank_literals=False)


def strip_noise(q: str) -> str:
    """注释与字符串字面量都剥掉。只给规则 D 用。"""
    return _scan(q, blank_literals=True)


def _form(bare: str) -> str:
    m = re.search(r"\b(SELECT|ASK|CONSTRUCT|DESCRIBE)\b", bare, re.IGNORECASE)
    return m.group(1).upper() if m else ""


def check(query: str) -> Verdict:
    if not isinstance(query, str) or not query.strip():
        return Verdict(False, ["query 不能为空。"])

    no_comment = strip_comments(query)
    bare = strip_noise(query)
    # PREFIX 段不参与判定 —— 前缀声明里出现 create/add 之类的词很正常
    body = re.sub(r"(?im)^\s*PREFIX\s+\S+\s*:\s*<[^>]*>\s*$", " ", bare)
    form = _form(body)
    v = Verdict(True, query=query, form=form)

    # ── D 写操作 ────────────────────────────────────────────────────
    if form not in READ_FORMS:
        v.ok = False
        v.reasons.append(
            "只接受 SELECT / ASK / CONSTRUCT / DESCRIBE。本 API 全部端点只读，"
            "任何写操作一律拒绝。")
    hits = [w for w in WRITE_VERBS if re.search(rf"\b{w}\b", body, re.IGNORECASE)]
    if hits:
        v.ok = False
        v.reasons.append(
            f"查询里出现写操作关键字：{'、'.join(hits)}。图库是只读的，"
            "推演请用 POST /simulate（它全程在内存里跑，对 GraphDB 只发 CONSTRUCT）。")

    # ── B 知识侧禁具名图 ★ ──────────────────────────────────────────
    named = _GRAPH_IRI.findall(no_comment)
    bad = [g for g in named if any(g.startswith(k) for k in KNOWLEDGE_GRAPHS)]
    if bad:
        v.ok = False
        v.reasons.append(
            f"知识侧不能写 GRAPH（你写了 {'、'.join(f'<{g}>' for g in sorted(set(bad)))}）。"
            "GraphDB 的 owl2-rl 物化三元组**不在任何用户命名图里**，写死具名图会"
            "**静默少返** —— 查询不报错，只是答案少一半。去掉 GRAPH 包裹，"
            "直接写 `?th dmo:lowerBound ?lo` 即可。")

    # ── C 反例夹具 ──────────────────────────────────────────────────
    if FIXTURE_GRAPH in no_comment:
        v.ok = False
        v.reasons.append(
            f"{FIXTURE_GRAPH} 里是 6 例**故意造错的反例夹具**（P001 触发禁忌、"
            "R005 缺单位、R006 单位不一致），不是真实患者。真实患者的图名以 "
            f"`{PATIENT_PREFIX}` 开头。")

    # ── A 患者图守卫 ★★ ─────────────────────────────────────────────
    for var in dict.fromkeys(_GRAPH_VAR.findall(no_comment)):
        guarded = re.search(
            rf'STRSTARTS\s*\(\s*STR\s*\(\s*\?{var}\s*\)\s*,\s*"{re.escape(PATIENT_PREFIX)}"',
            no_comment)
        if not guarded:
            v.ok = False
            v.reasons.append(
                f"`?{var}` 没有患者图守卫。不加会扫到 {FIXTURE_GRAPH} 里那 6 例"
                "**故意造错的反例夹具**，查询不报错、结果里混进假数据。请加上："
                f'`FILTER(STRSTARTS(STR(?{var}), "{PATIENT_PREFIX}"))`')

    if not v.ok:
        return v

    # ── E 行数上限（改写，不算失败）─────────────────────────────────
    if form != "ASK":
        tail = _TRAILING_LIMIT.search(no_comment.strip())
        if tail is None:
            v.query = query.rstrip().rstrip(";") + f"\nLIMIT {MAX_ROWS}"
            v.rewrites.append(f"没有 LIMIT，已追加 LIMIT {MAX_ROWS}。")
        elif int(tail.group(1)) > MAX_ROWS:
            v.query = _TRAILING_LIMIT.sub(f"LIMIT {MAX_ROWS}", query.rstrip())
            v.rewrites.append(
                f"LIMIT {tail.group(1)} 超过上限，已改写为 {MAX_ROWS}。")

    # ── F 全库扫描（警告，不拒）─────────────────────────────────────
    touches_patients = PATIENT_PREFIX in no_comment
    # 直接点名某个患者 IRI 也算收敛 —— 不然「查这一个患者」会被误警成全库扫描
    converged = (bool(re.search(r"VALUES\s+\?\w+", no_comment))
                 or bool(re.search(r"dmo:patientId\s+[\"']", no_comment))
                 or bool(_PATIENT_IRI.search(no_comment)))
    if touches_patients and not converged:
        v.warnings.append(
            "这条查询会扫全部患者图。30 个患者的演示里看不出问题，上量就是灾难。"
            "先用 GET /patients 把患者集合收敛出来，再用 "
            "`VALUES ?pat { <iri> … }` 注入。")
    return v


# ────────────────────── 零结果探针 ──────────────────────

_Q_PROBE = """
PREFIX dmo: <https://example.org/dmo#>
SELECT (COUNT(*) AS ?n) WHERE {
  GRAPH ?pg { <%s> ?p ?o }
  FILTER(STRSTARTS(STR(?pg), "urn:dmo:patient:"))
}
"""


def zero_result_reason(client, query: str) -> str:
    """0 行不能直接当「没有数据」回去。

    静态检查抓不全所有少返情形，所以真返回 0 行时自动降级探一次：该患者图里到底有没有
    三元组。**空集与「有但判不了」是两回事** —— `explain_gap` 早就在做这件事，
    这里只是把同一条诚实标准套到自由查询上。
    """
    m = _PATIENT_IRI.search(strip_comments(query))
    if m:
        try:
            n = int((client.sparql_csv(_Q_PROBE % m.group(1)) or [{}])[0].get("n") or 0)
        except Exception:  # noqa: BLE001 —— 探针失败不该盖掉主查询的结果
            n = -1
        if n > 0:
            return (f"返回 0 行，**但 {m.group(1)} 的患者图里有 {n} 条三元组**。"
                    "0 行大概率是图模式写错了 —— 最常见的是把知识侧三元组"
                    "（阈值、规则、出处）也包进了 `GRAPH ?pg`，那些三元组不在患者图里。"
                    "把知识侧的部分挪到 GRAPH 块外面再试。")
        if n == 0:
            return (f"返回 0 行，且 {m.group(1)} 的患者图里确实没有三元组 —— "
                    "这个患者可能还没同步（dmo sync patient），或者 IRI 拼错了。")
    return ("返回 0 行。空集与「没查到」不是一回事，先排除这三种："
            "①知识侧被包进了 `GRAPH ?pg`（最常见，会静默少返）；"
            "②IRI 拼错 —— 用 GET /graph/concepts 拿准确 IRI；"
            "③该项目确实判不了 —— 用 GET /terms/explain?term=… 会告诉你是哪一种。")
