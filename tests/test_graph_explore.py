"""图探索族测试。

这一族的价值全在**服务端替调用方避开图层的坑**，所以测试要正面证明坑存在、
且端点没踩进去 —— 尤其 owl2-rl 的 prp-dom 反推（test_risk_rule_class_is_contaminated）。
连不上 GraphDB 就 skip 整个模块。
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def client(graph):
    from fastapi.testclient import TestClient

    from dmo.api import app

    return TestClient(app)


# ───────────────────────── /graph/passages ─────────────────────────


def test_passages_corpus_is_intact(client):
    b = client.get("/graph/passages").json()
    assert b["total"] == 31, "seed 图应有 31 条可引用出处"
    assert all(p["trusted"] for p in b["passages"]), "全部应来自 urn:dmo:seed"
    assert all(p["sha256"] for p in b["passages"]), "100% 带 contentHash"


def test_passages_filter_by_citer(client):
    b = client.get("/graph/passages", params={"citedBy": "A1C-DIABETES-NONPREG"}).json()
    assert [p["passageId"] for p in b["passages"]] == ["A1C-DIABETES-Q"]


def test_empty_result_always_has_reason(client):
    """空集与「没查到」是两回事 —— 每一种空都要说清是哪一种。"""
    for params in ({"sha256": "0" * 64}, {"citedBy": "NO-SUCH-RULE"}, {"q": "zzz 不存在"}):
        b = client.get("/graph/passages", params=params).json()
        assert b["total"] == 0
        assert b["emptyReason"], params


def test_next_hops_are_present(client):
    b = client.get("/graph/passages", params={"q": "or above"}).json()
    assert b["nextHops"], "agent 不该靠猜下一跳的 URL"
    assert any(h["rel"] == "adjudicate" for h in b["nextHops"])


# ───────────────────────── /graph/rules ─────────────────────────


def test_risk_rule_class_is_contaminated(ask):
    """先证明坑真的存在：`?r a dmo:RiskRule` 查出来的绝大多数不是规则。

    `dmo:triggerBasis` 的 rdfs:domain 是 dmo:RiskRule，而 50-risk-factor-hit.rq
    产出的每条 RiskFactorHit 都带 triggerBasis，OWL-RL 的 prp-dom 于是把**每个患者
    命中记录**都判成一条风险规则。查询不报错、不告警，只是数字大了六倍。

    这条断言失败（两个数字相等）说明推理机没在跑或 ruleset 被换掉了 —— 那本身就该亮。
    """
    by_class = int(ask("SELECT (COUNT(DISTINCT ?r) AS ?n) WHERE { ?r a dmo:RiskRule }")[0]["n"])
    declared = int(ask("SELECT (COUNT(DISTINCT ?r) AS ?n) WHERE "
                       "{ ?r a dmo:RiskRule ; dmo:riskRuleId ?id }")[0]["n"])
    assert by_class > declared, "prp-dom 反推没发生 —— ruleset 是不是被换成 rdfs-plus 了？"


def test_rules_endpoint_counts_declarations_not_class_assertions(client, ask):
    """端点必须以 dmo:riskRuleId 为准，且把落差如实报进 counts。"""
    b = client.get("/graph/rules", params={"kind": "risk"}).json()
    declared = int(ask("SELECT (COUNT(DISTINCT ?r) AS ?n) WHERE "
                       "{ ?r a dmo:RiskRule ; dmo:riskRuleId ?id }")[0]["n"])
    assert b["total"] == declared
    risk = b["counts"]["risk"]
    assert risk["classAssertions"] > risk["declared"]
    assert risk["inferenceArtifacts"] > 0
    assert "prp-dom" in risk["classAssertionCaveat"]


def test_counts_in_tier_is_a_strict_subset(client):
    """有出处才计分。这个落差藏起来就等于夸大覆盖面。"""
    risk = client.get("/graph/rules", params={"kind": "risk"}).json()["counts"]["risk"]
    assert risk["countsInTier"] < risk["executable"] <= risk["declared"]

    scored = client.get("/graph/rules",
                        params={"kind": "risk", "countsInTier": True}).json()
    assert scored["total"] == risk["countsInTier"]
    assert all(r["citesPassages"] for r in scored["rules"]), "计分规则必须都有逐字出处"

    unscored = client.get("/graph/rules",
                          params={"kind": "risk", "countsInTier": False}).json()
    assert all(not r["citesPassages"] for r in unscored["rules"])
    assert all("不计入 tier" in r["notExecutableReason"] for r in unscored["rules"])


def test_threshold_renders_interval_and_confirmation(client):
    """诊断级切点必须自己说出 confirmationRequired —— 单次异常 ≠ 确诊。"""
    b = client.get("/graph/rules/A1C-DIABETES-NONPREG").json()
    r = b["rule"]
    assert r["interval"] == "[6.5, +∞) percent"
    assert r["confirmationRequired"] is True
    assert "30-diagnosis-from-assessment.rq" in r["consumedBy"]
    assert b["passages"][0]["quote"] == "6.5% or above"
    assert b["passages"][0]["sha256"]


def test_target_admits_its_citation_is_not_verifiable(client):
    """管理目标的原文在 rdfs:comment 里，没有 contentHash —— 必须自己说出来。"""
    b = client.get("/graph/rules/TARGET-A1C-ADULT").json()
    assert b["rule"]["citationCaveat"]
    assert b["passages"] == [], "管理目标没有可机器核验的 SourcePassage"
    assert "21-target-attainment.rq" in b["rule"]["consumedBy"]


def test_diagnosis_threshold_and_target_are_not_conflated(client):
    """诊断切点回答「是不是糖尿病」，管理目标回答「管得好不好」，不是同一个问题。"""
    kinds = {r["kind"] for r in client.get("/graph/rules").json()["rules"]}
    assert {"threshold", "target"} <= kinds
    th = client.get("/graph/rules", params={"kind": "threshold"}).json()
    assert all(r["kind"] == "threshold" for r in th["rules"])


def test_unknown_rule_is_404_and_bad_kind_is_400(client):
    assert client.get("/graph/rules/NO-SUCH-RULE").status_code == 404
    assert client.get("/graph/rules", params={"kind": "nonsense"}).status_code == 400


def test_risk_rule_interval_is_not_half_rendered(client):
    """风险规则的两个 operator 都是 OPTIONAL，缺失即无界。

    不补默认值会渲染成 `[35, )` —— 看着像数据坏了，其实是「35 岁及以上」。
    """
    rules = {r["ruleId"]: r for r in
             client.get("/graph/rules", params={"kind": "risk"}).json()["rules"]}
    assert rules["AGE-35"]["interval"] == "[35, +∞)"
    assert rules["PHYSICAL-INACTIVITY"]["interval"] == "(-∞, 3)"
    assert rules["BMI-OVERWEIGHT"]["interval"] == "[25, 30)"


# ───────────────────── /graph/concepts 表面形式 → IRI ─────────────────────


def test_chinese_surface_form_resolves_to_iri(client):
    """纯 SPARQL 版本查不到「糖化血红蛋白」—— 那个字符串只在 map_lab_term.src_name 里。

    本体 label/altLabel ∪ 三张映射表的并集，才是这个端点存在的理由。
    """
    b = client.get("/graph/concepts", params={"q": "糖化血红蛋白"}).json()
    assert b["total"] >= 1
    c = b["concepts"][0]
    assert c["code"] == "A1C" and c["kind"] == "LabTest"
    assert c["iri"].startswith("https://")


def test_found_does_not_mean_usable(client):
    """查得到 ≠ 判得了。verify_status 不是 verified 的映射，投影层一样跳过。"""
    c = client.get("/graph/concepts", params={"q": "糖化血红蛋白"}).json()["concepts"][0]
    forms = c["surfaceForms"]
    assert forms, "中文表面形式必须回显"
    assert all(f["usable"] is False for f in forms), "A1C 上游全库没有数值，不能标成可用"
    assert all(f["verifyStatus"] == "no-source-data" for f in forms)
    assert len(forms) == len({(f["term"], f["via"], f["verifyStatus"]) for f in forms}), \
        "map_lab_term 的 (src_name, src_ref_range) 会产生重复行，必须去重"


def test_concept_miss_points_at_explain(client):
    b = client.get("/graph/concepts", params={"q": "不存在的术语zzz"}).json()
    assert b["total"] == 0
    assert "/terms/explain" in b["emptyReason"], "未命中要指路，不能只返回空集"


def test_concepts_requires_a_query(client):
    assert client.get("/graph/concepts", params={"q": "  "}).status_code == 400


# ───────────────────────── /graph/node ─────────────────────────


def test_node_refuses_the_counterexample_fixtures(client):
    """urn:dmo:data 里 6 个合成患者是故意造错的，IRI 长得跟真患者一样。

    必须**拒绝并说明**，不能悄悄过滤 —— 悄悄过滤和静默少返是一回事。
    """
    r = client.get("/graph/node",
                   params={"iri": "https://example.org/dmo/id/patient/P001"})
    assert r.status_code == 400
    assert "反例夹具" in r.json()["detail"]


def test_node_marks_inferred_types(client, ask):
    """★ 本端点最该被读到的东西：哪些类型是推理机推的。

    RiskFactorHit 断言在 urn:dmo:inferred，而 RiskRule / Assessment 拿不到图名 ——
    它们是 prp-dom 顺着 rdfs:domain 反推出来的，不是谁声明的。
    """
    hit = ask("SELECT ?h WHERE { ?h a dmo:RiskFactorHit } LIMIT 1")[0]["h"]
    b = client.get("/graph/node", params={"iri": hit}).json()
    types = {t["short"]: t for t in b["types"]}
    assert types["dmo:RiskFactorHit"]["inferredOnly"] is False
    assert types["dmo:RiskFactorHit"]["assertedIn"] == ["urn:dmo:inferred"]
    assert types["dmo:RiskRule"]["inferredOnly"] is True
    assert "prp-dom" in b["inferenceNotice"]


def test_node_drops_reflexive_sameas(client):
    """owl2-rl 物化的 `x owl:sameAs x` 是纯噪声，留着白占一个 nextHop。"""
    iri = "https://example.org/dmo/id/threshold/A1C-DIABETES"
    b = client.get("/graph/node", params={"iri": iri}).json()
    assert all(e["short"] != "owl:sameAs" for e in b["outgoing"])
    assert {e["short"] for e in b["outgoing"]} >= {"dmo:thresholdId", "dmo:lowerBound"}
    assert any(e["short"] == "dmo:appliesThreshold" for e in b["incoming"])


def test_node_typo_says_so(client):
    b = client.get("/graph/node",
                   params={"iri": "https://example.org/dmo/id/threshold/NOPE"}).json()
    assert b["exists"] is False
    assert "拼错" in b["emptyReason"]


def test_node_rejects_non_iri(client):
    """不给 IRI 就先去查概念 —— 本仓库不猜术语。"""
    r = client.get("/graph/node", params={"iri": "糖化血红蛋白"})
    assert r.status_code == 400
    assert "/graph/concepts" in r.json()["detail"]


# ───────────────────────── /graph/taxonomy ─────────────────────────


def test_taxonomy_separates_asserted_from_inferred(client):
    """CKD ⊑ ChronicComplication 是文件里写的，CKD ⊑ Complication 是推出来的。

    这一条是「推理」这个亮点最直接的展示面。
    """
    b = client.get("/graph/taxonomy",
                   params={"iri": "https://example.org/dmo/id/CKD",
                           "direction": "up", "depth": 2}).json()
    anc = {e["short"]: e for e in b["levels"][0]}
    assert anc["dmo:ChronicComplication"]["inferredOnly"] is False
    assert anc["dmo:Complication"]["inferredOnly"] is True
    assert "传递闭包" in b["inferenceNotice"]


def test_taxonomy_sidelines_owl_thing(client):
    """owl2-rl 给每个类都物化了 ⊑ owl:Thing。真，但没信息量，不能混进层次。"""
    b = client.get("/graph/taxonomy",
                   params={"iri": "https://example.org/dmo#Complication",
                           "direction": "up"}).json()
    assert b["trivialAncestors"] == ["owl:Thing"]
    assert b["total"] == 0
    assert "平凡上位类" in b["emptyReason"]


def test_taxonomy_direction_is_validated(client):
    assert client.get("/graph/taxonomy",
                      params={"iri": "https://example.org/dmo#Complication",
                              "direction": "sideways"}).status_code == 400


# ───────────────────────── 全族口径 ─────────────────────────


def test_explore_never_writes(client, graph):
    before = graph.size()
    client.get("/graph/concepts", params={"q": "A1C"})
    client.get("/graph/node", params={"iri": "https://example.org/dmo/id/CKD"})
    client.get("/graph/neighbors", params={"iri": "https://example.org/dmo/id/CKD"})
    client.get("/graph/taxonomy", params={"iri": "https://example.org/dmo/id/CKD"})
    assert graph.size() == before


def test_neighbors_direction_is_validated(client):
    r = client.get("/graph/neighbors",
                   params={"iri": "https://example.org/dmo/id/CKD", "direction": "x"})
    assert r.status_code == 400


# ───────────────────────── /graph/provenance ─────────────────────────


def _one(ask, cls, patient_only=False):
    guard = ('FILTER(STRSTARTS(STR(?g), "urn:dmo:patient:"))' if patient_only else "")
    rows = ask(f"SELECT ?x WHERE {{ GRAPH ?g {{ ?x a dmo:{cls} }} {guard} }} LIMIT 1")
    if not rows:
        import pytest

        pytest.skip(f"图里没有断言的 {cls} 实例")
    return rows[0]["x"]


def test_assessment_traces_all_the_way_to_source_and_sql(ask, client):
    """一条链从「机器推出来的结论」走到「原文哪一句」和「数据库哪一行」。"""
    b = client.get("/graph/provenance", params={"iri": _one(ask, "Assessment")}).json()
    assert b["kind"] == "Assessment"
    roles = [c["role"] for c in b["chain"]]
    assert roles[0] == "conclusion"
    for must in ("appliesThreshold", "basedOnLabResult", "citesPassage", "sqlRow"):
        assert must in roles, f"链上缺 {must}：{roles}"
    ev = b["evidence"][0]
    assert ev["quote"] and len(ev["sha256"]) == 64
    row = next(c for c in b["chain"] if c["role"] == "sqlRow")
    assert row["detail"]["sqlRow"]["table"] and row["detail"]["sqlRow"]["pk"]


def test_sql_lookup_uses_business_id_not_iri(ask, client):
    """SQL 的 `*_id` 列存业务号（`EHR-DX-P00002|C00002|D901`），不是 IRI。

    拿 IRI 直接查永远查不到，而且**查不到不报错** —— 回查那一环静默消失，
    返回体看着仍然完整。这条断言守的就是那个静默。
    """
    b = client.get("/graph/provenance",
                   params={"iri": _one(ask, "Diagnosis", patient_only=True)}).json()
    row = next(c for c in b["chain"] if c["role"] == "sqlRow")
    assert row["detail"]["factId"] != row["iri"], "业务号不该等于 IRI"
    assert row["detail"]["sqlRow"]["pk"]


def test_broken_links_are_reported(ask, client):
    """只报走通的环节，等于在暗示「这条结论有出处」。"""
    b = client.get("/graph/provenance",
                   params={"iri": _one(ask, "ContraindicationFlag")}).json()
    assert b["evidence"] == [], "禁忌的 rationale 不是带 contentHash 的 SourcePassage"
    assert b["brokenLinks"], "拿不出可核验出处时必须明说"
    assert any("contentHash" in x["why"] for x in b["brokenLinks"])


def test_risk_hit_says_whether_it_counts(ask, client):
    b = client.get("/graph/provenance", params={"iri": _one(ask, "RiskFactorHit")}).json()
    head = b["chain"][0]["detail"]
    assert "countsInTier" in head
    assert head["countsInTier"] is bool(b["evidence"]), "有出处才计分，两者必须一致"


def test_provenance_refuses_fixtures(ask, client):
    rows = ask('SELECT ?x WHERE { GRAPH <urn:dmo:data> { ?x a dmo:Diagnosis } } LIMIT 1')
    if not rows:
        import pytest

        pytest.skip("夹具图里没有 Diagnosis")
    r = client.get("/graph/provenance", params={"iri": rows[0]["x"]})
    assert r.status_code == 400 and "反例夹具" in r.json()["detail"]


def test_non_conclusion_node_is_named_not_guessed(client):
    """按 rdf:type 分派会把患者命中记录当 Assessment 溯源，查出一堆空。"""
    b = client.get("/graph/provenance",
                   params={"iri": "https://example.org/dmo/id/threshold/A1C-DIABETES"}).json()
    assert b["kind"] is None
    assert "DiagnosticThreshold" in b["emptyReason"]
    assert "prp-dom" in b["emptyReason"]


# ───────────────── /graph/path · /graph/schema · /agent/manifest ─────────────────


def test_path_connects_a_lab_result_to_the_guideline_quote(ask, client):
    """「这个患者事实和那条指南原文是怎么连上的」—— 三跳。"""
    res = ask('SELECT ?r WHERE { GRAPH ?pg { ?r a dmo:LabResult } '
              'FILTER(STRSTARTS(STR(?pg), "urn:dmo:patient:")) } LIMIT 1')[0]["r"]
    psg = "https://example.org/dmo/id/sourcePassage/A1C-DIABETES-Q"
    b = client.get("/graph/path", params={"from": res, "to": psg, "maxHops": 4}).json()
    if not b["found"]:
        pytest.skip("这条检验不是 A1C，连不到该出处")
    preds = [e["short"] for e in b["path"]]
    assert preds[-1] == "dmo:thresholdCitesPassage"
    assert "dmo:measuredByTest" in preds


def test_path_does_not_go_through_owl_thing(client):
    """rdf:type / owl:sameAs 把任意两个节点都连得上，经它们的「连通」是伪相关。"""
    b = client.get("/graph/path", params={
        "from": "https://example.org/dmo/id/threshold/A1C-DIABETES",
        "to": "https://example.org/dmo/id/target/BP", "maxHops": 2}).json()
    assert b["found"] is False
    assert "伪相关" in b["emptyReason"]


def test_path_rejects_same_endpoints(client):
    iri = "https://example.org/dmo/id/CKD"
    assert client.get("/graph/path", params={"from": iri, "to": iri}).status_code == 400


def test_schema_card_has_all_three_sides(client):
    b = client.get("/graph/schema").json()
    assert len(b["rdf"]["entityTypes"]) >= 25
    assert b["rdf"]["ruleOutputClasses"], "规则产物类不在 ER JSON 里，必须补"
    assert any("静默少返" in r for r in b["rdf"]["graphRules"])
    assert b["sql"]["tables"], "DDL 的中文 COMMENT ON 此前没有任何代码读过"


def test_bridge_table_is_extracted_from_emit_source(client):
    """SQL 列 ↔ RDF 谓词的对照由 emit.py 的 AST 抽出来 —— 不可能与发射逻辑分叉。

    写法变了会静默少抽，所以这里钉住若干已知对与最少条数。
    """
    pairs = {(p["sqlColumn"], p["rdfPredicate"])
             for p in client.get("/graph/schema",
                                 params={"section": "bridge"}).json()["bridge"]["pairs"]}
    assert len(pairs) >= 30, f"只抽到 {len(pairs)} 对，emit.py 的写法可能变了"
    for want in (("result_value", "dmo:resultValue"),
                 ("trust_level", "dmo:valueTrustLevel"),
                 ("lab_result_id", "dmo:labResultId"),
                 ("external_code", "dmo:externalCode")):
        assert want in pairs, want


def test_bridge_names_the_value_transforms(client):
    """core_patient.sex 的 M/F 在 RDF 侧已经变成 Male/Female，按 M 查一条不返。"""
    b = client.get("/graph/schema", params={"section": "bridge"}).json()
    sex = [t for t in b["bridge"]["valueTransforms"] if t["sqlColumn"] == "sex"]
    assert sex and "Male" in sex[0]["transform"]


def test_manifest_is_generated_from_live_routes(client):
    """端点清单硬编在 prompt 里，每加一个端点都要改 prompt，而且必然漏改。"""
    b = client.get("/agent/manifest").json()
    paths = {e["path"] for e in b["endpoints"]}
    for must in ("/graph/concepts", "/graph/provenance", "/adjudicate/claim",
                 "/adjudicate/scope", "/simulate"):
        assert must in paths, must
    assert any("不猜术语" in x for x in b["callOrder"])
    assert any("剂量" in x for x in b["prohibitions"])
    assert b["determinism"]["nondeterministic"]["endpoints"] == [], \
        "当前没有由模型规划路径的端点；有了必须带 nondeterminismNotice"


def test_manifest_gives_boundaries_with_capabilities(client):
    """只给能力不给边界，等于鼓励越界使用。"""
    cov = client.get("/agent/manifest").json()["coverage"]
    assert cov["citablePassages"] == 31
    assert "/adjudicate/scope" in cov["boundaries"]


# ───────────────────────── POST /graph/sparql ─────────────────────────


def test_sparql_escape_hatch_runs_valid_queries(client):
    r = client.post("/graph/sparql", json={
        "query": "PREFIX dmo: <https://example.org/dmo#>\n"
                 "SELECT ?id WHERE { ?th dmo:thresholdId ?id }"})
    assert r.status_code == 200
    b = r.json()
    assert b["rowCount"] >= 17 or b["rowCount"] == 200
    assert b["guard"]["rewrites"], "无 LIMIT 应被自动追加"


def test_sparql_escape_hatch_rejects_missing_guard(client):
    r = client.post("/graph/sparql", json={
        "query": "PREFIX dmo: <https://example.org/dmo#>\n"
                 "SELECT ?pid WHERE { GRAPH ?pg { ?p dmo:patientId ?pid } }"})
    assert r.status_code == 400
    assert "反例夹具" in " ".join(r.json()["detail"]["guard"]["reasons"])


def test_zero_result_probe_distinguishes_empty_from_wrong(client, ask):
    """★ 0 行不能直接当「没有数据」回去。

    静态检查抓不全所有少返情形，所以真返回 0 行时降级探一次：该患者图里到底有没有
    三元组。空集与「有但判不了」是两回事。
    """
    pat = ask('SELECT ?p WHERE { GRAPH ?pg { ?p a dmo:Patient } '
              'FILTER(STRSTARTS(STR(?pg), "urn:dmo:patient:")) } LIMIT 1')[0]["p"]
    r = client.post("/graph/sparql", json={
        "query": "PREFIX dmo: <https://example.org/dmo#>\n"
                 f"SELECT ?o WHERE {{ GRAPH ?pg {{ <{pat}> dmo:noSuchPredicate ?o }} "
                 'FILTER(STRSTARTS(STR(?pg), "urn:dmo:patient:")) }'})
    b = r.json()
    assert b["rowCount"] == 0
    assert "条三元组" in b["emptyReason"], "必须说出这个患者图里其实有数据"
    assert "静默少返" in b["emptyReason"] or "知识侧" in b["emptyReason"]


def test_sparql_escape_hatch_never_writes(client, graph):
    before = graph.size()
    client.post("/graph/sparql", json={"query": "INSERT DATA { <a:b> <a:c> <a:d> }"})
    client.post("/graph/sparql", json={
        "query": "PREFIX dmo: <https://example.org/dmo#>\n"
                 "SELECT ?id WHERE { ?th dmo:thresholdId ?id }"})
    assert graph.size() == before
