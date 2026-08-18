"""喂给智能体的 schema 上下文 —— 三块：RDF 侧、SQL 侧、两侧的桥接表。

[DESIGN.md](../../../docs/DESIGN.md) 原则 3：**schema 注入而非数据注入**。
类层次与属性签名进上下文，实例数据一律走工具取。这个端点就是那份 schema 的来源。

## 桥接表为什么用 AST 抽，不新造一份常量

`rdf/emit.py` 是 SQL 列名 ↔ RDF 谓词的**唯一权威对照**，但它以命令式代码存在
（140 行 `_add(g, node, DMO.resultValue, r["result_value"])`）。

[AGENT-INVESTIGATE-PLAN.md](../../../docs/AGENT-INVESTIGATE-PLAN.md) §4 的方案是加一个
声明式常量 `COLUMN_PREDICATE_MAP` 再让 `emit()` 消费它。这里改成**直接用 `ast` 静态
解析 emit.py**，理由是后者更强：

  * 不动正在跑的同步代码，`dmo sync all` 的行为一个字节都不变；
  * 对照表**不可能与发射逻辑分叉** —— 它就是从发射逻辑里读出来的，
    而常量方案要靠「改了 emit 记得改常量」的自觉。

代价是抽取依赖 `_add(...)` / `g.add((...))` 这两种写法。写法变了会静默少抽，
所以 `tests/test_graph_explore.py` 里有一条断言钉住若干已知的列↔谓词对与最少条数。
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from ..config import Config

ROOT = Path(__file__).resolve().parents[3]
ER_JSON = ROOT / "ontology" / "graph" / "diabetes-ontology-v2.json"
EMIT_PY = ROOT / "src" / "dmo" / "rdf" / "emit.py"

# 只在规则产物里出现、ER JSON 里没有的三个类。不补上，agent 会以为查询层没有它们。
RULE_OUTPUT_CLASSES = (
    {"name": "dmo:Assessment", "producedBy": "20-lab-assessment.rq",
     "note": "只回答「这次检验落在哪个区间」，**不下诊断**。"},
    {"name": "dmo:Diagnosis（推断的那部分）", "producedBy": "30-diagnosis-from-assessment.rq",
     "note": "confirmationRequired=true 且只有单个采样日 ⟹ Provisional 而非 Confirmed。"},
    {"name": "dmo:ContraindicationFlag", "producedBy": "40-contraindication-flag.rq",
     "note": "Absolute / Relative / Caution 三级信号，**不含剂量与替代方案**。"},
    {"name": "dmo:RiskFactorHit", "producedBy": "50-risk-factor-hit.rq",
     "note": "命中 ≠ 参与判定：无 riskRuleCitesPassage 的规则不计入 tier。"},
    {"name": "dmo:RiskStratification", "producedBy": "51-risk-stratification.rq",
     "note": "规则式定性分层，tier 是有序枚举；不含概率、不含时间窗。"},
)

# 三条铁律，与 query/templates.py、GRAPHDB-USAGE.md 同源。写进 schema 卡片是因为
# agent 只读一次上下文，不会回头翻文档。
GRAPH_RULES = (
    (
    "患者事实侧：写 `GRAPH ?pg` 并**必须**带 "
    '`FILTER(STRSTARTS(STR(?pg), "urn:dmo:patient:"))`。'
    "不加会扫到 urn:dmo:data 里 6 例**故意造错的反例夹具**。"
    ),
    (
    "知识侧（阈值 / 规则 / 出处 / 类层次）：**一律不写 GRAPH**。"
    "owl2-rl 的物化三元组不在任何用户命名图里，写死具名图会**静默少返** —— "
    "查询不报错，只是答案少一半。"
    ),
    (
    "不要拿 `?x a <类>` 当「声明了这个类」用。prp-dom 会顺着谓词的 rdfs:domain 反推类型："
    "`?r a dmo:RiskRule` 查出 73 条，真规则只有 12 条。以声明标记"
    "（thresholdId / riskRuleId / targetId）为准。"
    ),
)

# 编排铁律，照 query/hybrid.py 开头。
ORCHESTRATION = (
    "有多少 / 哪些患者 / 分页        → SQL",
    "为什么 / 凭什么 / 依据哪条指南  → SPARQL（患者集合先用 SQL 收敛，再用 VALUES ?pat 注入）",
    "原始那一行长什么样              → SQL，按 source_table + source_pk 回查",
    "这个术语认不认识 / 为什么查不到  → SQL 的 map_* 表，或 GET /terms/explain",
)

SQL_TABLE_RE = ("core_", "pred_", "map_")

_Q_SQL_SCHEMA = """
SELECT c.relname AS tbl, obj_description(c.oid) AS tbl_comment,
       a.attname AS col, format_type(a.atttypid, a.atttypmod) AS typ,
       col_description(c.oid, a.attnum) AS col_comment, a.attnum
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid
WHERE n.nspname = 'diabetes' AND c.relkind = 'r'
  AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY c.relname, a.attnum
"""


def _rdf_side() -> dict[str, Any]:
    if not ER_JSON.exists():
        return {"error": f"缺 {ER_JSON}"}
    er = json.loads(ER_JSON.read_text(encoding="utf-8"))
    return {
        "source": str(ER_JSON.relative_to(ROOT)),
        "entityTypes": er.get("entityTypes", []),
        "relationships": er.get("relationships", []),
        "ruleOutputClasses": list(RULE_OUTPUT_CLASSES),
        "namedGraphs": {
            "urn:dmo:tbox": "手写公理 + 生成的类/属性骨架",
            "urn:dmo:seed": "阈值 / 血糖目标 / 风险规则 / LabTest / SourcePassage —— 人工策展，可信度最高",
            "urn:dmo:sources": "source registry（指南文档元数据）",
            "urn:dmo:extract:<sid>": "LLM 抽取产物，每份文档一图，**质量参差**",
            "urn:dmo:inferred": "规则层物化结果",
            "urn:dmo:data": "⚠️ **故意造错的反例夹具**，不是真实患者",
            "urn:dmo:patient:<uuid>": "真实患者，每患者一图",
        },
        "graphRules": list(GRAPH_RULES),
    }


def _sql_side(cfg: Config) -> dict[str, Any]:
    """DDL 里的中文 COMMENT ON 信息密度极高，但此前没有任何代码读过它们。

    这个 dumper 走 onto_conn 读 pg_catalog —— 禁 pg_catalog 的是**给 agent 生成的 SQL**
    定的规矩，不是仓库自己的代码。
    """
    from ..db.engine import onto_conn

    tables: dict[str, dict[str, Any]] = {}
    with onto_conn(cfg) as conn:
        for r in conn.fetchall(_Q_SQL_SCHEMA):
            if not r["tbl"].startswith(SQL_TABLE_RE):
                continue
            t = tables.setdefault(r["tbl"], {
                "table": f"diabetes.{r['tbl']}", "comment": r["tbl_comment"],
                "columns": []})
            t["columns"].append({"name": r["col"], "type": r["typ"],
                                 "comment": r["col_comment"]})
    return {
        "tables": list(tables.values()),
        "note": "只给 core_* / pred_* / map_*。stg_* 是上游只读快照，sys_* 是内部账本。",
    }


def _bridge() -> dict[str, Any]:
    """从 emit.py 的 AST 里读出 SQL 列 ↔ RDF 谓词的对照。"""
    if not EMIT_PY.exists():
        return {"error": f"缺 {EMIT_PY}"}
    tree = ast.parse(EMIT_PY.read_text(encoding="utf-8"))
    pairs: list[dict[str, str]] = []

    def pred_of(node: ast.AST) -> str | None:
        # DMO.resultValue → "dmo:resultValue"
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id == "DMO":
            return f"dmo:{node.attr}"
        return None

    def col_of(node: ast.AST) -> str | None:
        # r["result_value"]，也认 URIRef(r["lab_test_iri"]) 这一层包裹
        if isinstance(node, ast.Call) and node.args:
            return col_of(node.args[0])
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) \
                and isinstance(node.slice.value, str):
            return node.slice.value
        return None

    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        args = list(n.args)
        # _add(g, subj, DMO.pred, r["col"], dt?)
        if isinstance(n.func, ast.Name) and n.func.id == "_add" and len(args) >= 4:
            p, c = pred_of(args[2]), col_of(args[3])
        # g.add((subj, DMO.pred, URIRef(r["col"])))
        elif isinstance(n.func, ast.Attribute) and n.func.attr == "add" and args \
                and isinstance(args[0], ast.Tuple) and len(args[0].elts) == 3:
            p, c = pred_of(args[0].elts[1]), col_of(args[0].elts[2])
        else:
            continue
        if p and c:
            entry = {"sqlColumn": c, "rdfPredicate": p}
            if entry not in pairs:
                pairs.append(entry)

    return {
        "source": "由 src/dmo/rdf/emit.py 的 AST 静态解析得到 —— 不可能与发射逻辑分叉",
        "pairs": sorted(pairs, key=lambda e: (e["sqlColumn"], e["rdfPredicate"])),
        "valueTransforms": [
            {"sqlColumn": "sex", "rdfPredicate": "dmo:sex",
             "transform": "M → Male，F → Female，其余 → Unknown。"
                          "**RDF 侧看不到 M/F**，按 M 查会一条不返。"},
            {"sqlColumn": "result_value", "rdfPredicate": "dmo:resultValue",
             "transform": "单位换算在 ETL（terms/units.py）做完，进图的一律是规范单位；"
                          "原值保留在 dmo:sourceValue / dmo:sourceUnit。"},
        ],
        "orchestration": list(ORCHESTRATION),
    }


def card(cfg: Config, *, section: str | None = None) -> dict[str, Any]:
    from ..terms.concepts import graph_version

    parts = {"rdf": _rdf_side, "bridge": _bridge}
    if section and section not in ("rdf", "sql", "bridge"):
        raise ValueError("section 只能是 rdf / sql / bridge，或不给（全部）。")
    out: dict[str, Any] = {"graphVersion": graph_version()}
    if section in (None, "rdf"):
        out["rdf"] = parts["rdf"]()
    if section in (None, "sql"):
        out["sql"] = _sql_side(cfg)
    if section in (None, "bridge"):
        out["bridge"] = parts["bridge"]()
    return out
