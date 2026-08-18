"""SPARQL 静态检查器的纯单测 —— **不需要 GraphDB、不需要 PG、不需要模型**。

这是整套里唯一能被 CI 无条件守住的部分，也是「放开自由 SPARQL」这个决定成立的
全部前提：guard 挡不住的东西，后面全是白搭。所以它必须能独立验收。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dmo.graph import guard

P = "PREFIX dmo: <https://example.org/dmo#>\n"
GUARD = 'FILTER(STRSTARTS(STR(?pg), "urn:dmo:patient:"))'


def _reasons(q):
    return " ".join(guard.check(q).reasons)


# ───────────────────── 规则 A：患者图守卫 ─────────────────────


def test_missing_patient_guard_is_rejected():
    v = guard.check(P + "SELECT ?pid WHERE { GRAPH ?pg { ?p dmo:patientId ?pid } }")
    assert not v.ok
    assert "反例夹具" in " ".join(v.reasons), "理由要写给模型看，不是 'rule A violation'"
    assert "STRSTARTS" in " ".join(v.reasons), "必须直接告诉它该加哪一句"


def test_patient_guard_present_passes():
    v = guard.check(P + "SELECT ?pid WHERE { GRAPH ?pg { ?p dmo:patientId ?pid } "
                    + GUARD + " }")
    assert v.ok, v.reasons


def test_every_graph_var_needs_its_own_guard():
    """两个图变量只守住一个，另一个照样会扫到夹具。"""
    q = (P + "SELECT ?a ?b WHERE { GRAPH ?pg { ?a dmo:patientId ?x } " + GUARD
         + " GRAPH ?pg2 { ?b dmo:patientId ?y } }")
    assert "?pg2" in _reasons(q)


# ───────────────────── 规则 B：知识侧禁具名图 ★ ─────────────────────


def test_named_knowledge_graph_is_rejected():
    for g in ("urn:dmo:seed", "urn:dmo:tbox", "urn:dmo:inferred",
              "urn:dmo:extract:niddk-tests-diagnosis"):
        r = _reasons(P + f"SELECT ?lo WHERE {{ GRAPH <{g}> {{ ?th dmo:lowerBound ?lo }} }}")
        assert "静默少返" in r, g


def test_knowledge_side_without_graph_passes():
    v = guard.check(P + "SELECT ?lo WHERE { ?th dmo:thresholdId ?t ; dmo:lowerBound ?lo }")
    assert v.ok, v.reasons


# ───────────────────── 规则 C / D ─────────────────────


def test_fixture_graph_is_rejected():
    assert "反例夹具" in _reasons(P + "SELECT ?s WHERE { GRAPH <urn:dmo:data> { ?s ?p ?o } }")


def test_write_operations_are_rejected():
    for q in ("DELETE WHERE { ?s ?p ?o }",
              "INSERT DATA { <a:b> <a:c> <a:d> }",
              "DROP GRAPH <urn:dmo:seed>",
              "CLEAR ALL",
              "LOAD <http://x/y>"):
        assert not guard.check(P + q).ok, q


def test_select_ask_construct_describe_pass():
    for q in ("SELECT ?x WHERE { ?x dmo:thresholdId ?y }",
              'ASK { ?x dmo:thresholdId "A1C-DIABETES-NONPREG" }',
              "CONSTRUCT { ?x dmo:thresholdId ?y } WHERE { ?x dmo:thresholdId ?y }",
              "DESCRIBE <https://example.org/dmo/id/threshold/A1C-DIABETES>"):
        assert guard.check(P + q).ok, q


# ───────────────────── 剥噪声 ─────────────────────


def test_write_verb_inside_a_comment_is_not_a_violation():
    """SPARQL 注释里出现 INSERT 不该被拦 —— 与 db/engine.py 的 strip_sql_noise 同理。"""
    v = guard.check(P + "SELECT ?x WHERE { ?th dmo:thresholdId ?x }  # 别写 INSERT")
    assert v.ok, v.reasons


def test_forbidden_iri_inside_a_comment_is_not_a_violation():
    v = guard.check(P + "SELECT ?x WHERE { ?th dmo:thresholdId ?x } # 不要碰 urn:dmo:data")
    assert v.ok, v.reasons


def test_hash_inside_an_iri_is_not_a_comment():
    """★ 本体的词汇命名空间就是 `https://example.org/dmo#`。

    用 `re.sub(r"#[^\\n]*", "", q)` 剥注释会把 `<https://example.org/dmo#>` 的 `#>`
    一起吃掉 —— 连闭合的 `>` 都没了，整条查询被粘成一个巨大的「IRI」，
    后面所有规则都在一段面目全非的文本上跑。**而且不报错。**
    """
    stripped = guard.strip_comments(P + "SELECT ?x WHERE { ?x dmo:a ?y }")
    assert "<https://example.org/dmo#>" in stripped
    # 粘连的直接后果：守卫检不出来了
    q = (P + "SELECT ?pid WHERE { GRAPH ?pg { ?p dmo:patientId ?pid } }")
    assert not guard.check(q).ok, "prefix 被吃掉后规则 A 会失灵"


def test_hash_inside_a_string_literal_is_not_a_comment():
    v = guard.check(P + 'SELECT ?x WHERE { ?x dmo:thresholdId "A#B" . ?x dmo:a ?y }')
    assert v.ok, v.reasons


# ───────────────────── 规则 E / F ─────────────────────


def test_missing_limit_is_appended_not_rejected():
    v = guard.check(P + "SELECT ?x WHERE { ?x dmo:thresholdId ?y }")
    assert v.ok and v.rewrites
    assert v.query.rstrip().endswith(f"LIMIT {guard.MAX_ROWS}")


def test_oversized_limit_is_rewritten():
    v = guard.check(P + "SELECT ?x WHERE { ?x dmo:thresholdId ?y } LIMIT 5000")
    assert v.ok and "5000" in v.rewrites[0]
    assert f"LIMIT {guard.MAX_ROWS}" in v.query and "5000" not in v.query


def test_ask_gets_no_limit():
    """ASK 加 LIMIT 是语法错。改写不能把合法查询改坏。"""
    v = guard.check(P + 'ASK { ?x dmo:thresholdId "A1C-DIABETES-NONPREG" }')
    assert v.ok and not v.rewrites and "LIMIT" not in v.query.upper()


def test_full_patient_scan_warns_but_passes():
    q = P + "SELECT ?pid WHERE { GRAPH ?pg { ?p dmo:patientId ?pid } " + GUARD + " }"
    v = guard.check(q)
    assert v.ok and v.warnings and "上量就是灾难" in v.warnings[0]


def test_naming_one_patient_is_not_a_full_scan():
    q = (P + "SELECT ?o WHERE { GRAPH ?pg { "
         "<https://example.org/dmo/id/patient/abc-123> dmo:x ?o } " + GUARD + " }")
    v = guard.check(q)
    assert v.ok and not v.warnings, v.warnings


def test_values_injection_is_not_a_full_scan():
    q = (P + "SELECT ?pid WHERE { VALUES ?pat { <https://example.org/dmo/id/patient/a> } "
         "GRAPH ?pg { ?pat dmo:patientId ?pid } " + GUARD + " }")
    assert not guard.check(q).warnings


def test_empty_query_is_rejected():
    assert not guard.check("").ok
    assert not guard.check(None).ok
