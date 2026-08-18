"""裁决族测试。

第 1 步只有出处裁决，但它是整个裁决族里**唯一完全确定的**一环 ——
不碰患者、不碰 PG、不跑规则链，只拿 31 条已逐字核验过的 SourcePassage 比对。
所以这里的断言可以写得很硬：五个判定值两两不相交，同一输入永远同一结果。

连不上 GraphDB 就 skip 整个模块（照 conftest 的口径）—— 环境没起来不等于代码错了。
"""

from __future__ import annotations

import pytest

# 真实存在的一条：niddk-tests-diagnosis 诊断表 A1C 列 Diabetes 行
REAL_QUOTE = "6.5% or above"
REAL_HASH = "96495c7d996a92b5bee7132029744f08e5154be98dd1be7e177399320d7d1447"
OTHER_HASH = "1ef96abbe78d2ee560afcd343ed877de87e84036b7f0a31401bc45f20a92b668"  # FPG-DIABETES-Q


@pytest.fixture(scope="module")
def client(graph):
    from fastapi.testclient import TestClient

    from dmo.api import app

    return TestClient(app)


def _check(client, citations, **kw):
    r = client.post("/adjudicate/citations", json={"citations": citations, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def _verdicts(body):
    return [x["verdict"] for x in body["results"]]


# ───────────────────────── 五个判定值 ─────────────────────────


def test_verbatim(client):
    b = _check(client, [{"quote": REAL_QUOTE, "sha256": REAL_HASH}])
    assert _verdicts(b) == ["verbatim"]
    assert b["results"][0]["matched"][0]["passageId"] == "A1C-DIABETES-Q"


def test_verbatim_without_hash_computes_one(client):
    """只给引文时系统自己算哈希 —— 不能因为调用方懒就判不了。"""
    b = _check(client, [{"quote": REAL_QUOTE}])
    assert _verdicts(b) == ["verbatim"]
    assert b["results"][0]["sha256Computed"] == REAL_HASH


def test_rewritten_quote_is_caught(client):
    """★ 最该抓的一类：哈希是真的，引文在转述中被改写了。

    纯字符串比对抓不到（引文与库里任何一条都不相同），纯哈希比对也抓不到
    （哈希确实存在）。必须两条线一起看才能发现。
    """
    b = _check(client, [{"quote": "6.5 percent or higher", "sha256": REAL_HASH}])
    assert _verdicts(b) == ["hash-only"]
    assert "改写" in b["results"][0]["reason"]


def test_fabricated_sha256_is_caught(client):
    b = _check(client, [{"quote": REAL_QUOTE, "sha256": "de" * 32}])
    assert _verdicts(b) == ["quote-only"]
    assert "不存在" in b["results"][0]["reason"]


def test_hash_pointing_to_another_passage_is_named(client):
    """哈希指向另一条真实出处时，必须说出是哪一条 —— 这是张冠李戴的信号。"""
    b = _check(client, [{"quote": REAL_QUOTE, "sha256": OTHER_HASH}])
    assert _verdicts(b) == ["quote-only"]
    assert "FPG-DIABETES-Q" in b["results"][0]["reason"]
    assert b["results"][0]["hashPointsTo"][0]["passageId"] == "FPG-DIABETES-Q"


def test_hash_only_without_quote_says_so(client):
    """只给哈希时不能假装核对过逐字性。"""
    b = _check(client, [{"sha256": REAL_HASH}])
    assert _verdicts(b) == ["hash-only"]
    assert "无从核对" in b["results"][0]["reason"]


def test_truncation_and_padding_are_not_verbatim(client):
    """截取与加话都不是逐字引用，但也不是凭空编造 —— 必须与 fabricated 分开。"""
    b = _check(client, [
        {"quote": "The guideline says 126 mg/dL or above indicates diabetes."},
        {"quote": "your blood sugar is 250 mg/dL or above"},
    ])
    assert _verdicts(b) == ["not-verbatim", "not-verbatim"]
    rels = {x["nearest"][0]["relation"] for x in b["results"]}
    assert rels == {"citation-contains-passage", "citation-is-fragment-of-passage"}


def test_fabricated(client):
    b = _check(client, [{"quote": "根据指南，通常认为血糖偏高即可诊断糖尿病"}])
    assert _verdicts(b) == ["fabricated"]
    # 措辞不能是道德指控：本库没有 ≠ 对方造假
    assert "不等于指控伪造" in b["results"][0]["reason"]


# ───────────────────────── 硬性口径 ─────────────────────────


def test_hash_collision_returns_all_matches(client):
    """contentHash = sha256(quote)，引文相同的两条哈希必然相同。

    OGTT2H-DIABETES-Q 与 RPG-DIABETES-Q 的引文都是 "200 mg/dL or above"。
    索引写成 hash → 单条的话会**静默丢一条**，citedBy 少一半而不报错。
    """
    b = _check(client, [{"quote": "200 mg/dL or above"}])
    ids = {p["passageId"] for p in b["results"][0]["matched"]}
    assert ids == {"OGTT2H-DIABETES-Q", "RPG-DIABETES-Q"}


def test_verdict_is_never_boolean(client):
    """返回体里不许出现「通过校验」式的布尔字段。理由见 PLAN §0.1。"""
    import json

    b = _check(client, [{"quote": REAL_QUOTE}])
    banned = ("reasonable", "valid", "isValid", "passed", "ok", "approved")
    stack = [b]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for k, v in node.items():
                assert k not in banned, f"出现了布尔式字段 {k}：{json.dumps(b, ensure_ascii=False)[:200]}"
                stack.append(v)
        elif isinstance(node, list):
            stack.extend(node)


def test_is_deterministic(client):
    """同一批输入、同一版知识层 → 永远同一结果。这是相对 LLM 最硬的一条差异。"""
    payload = [
        {"quote": REAL_QUOTE, "sha256": REAL_HASH},
        {"quote": "6.5 percent or higher", "sha256": REAL_HASH},
        {"quote": "凭空编的一句话，本库没有"},
    ]
    runs = [_check(client, payload) for _ in range(3)]
    assert all(r["results"] == runs[0]["results"] for r in runs)
    assert all(r["graphVersion"] == runs[0]["graphVersion"] for r in runs)


def test_asserted_by_does_not_change_verdict(client):
    """谁说的不影响对不对。"""
    a = _check(client, [{"quote": REAL_QUOTE}], assertedBy="external-llm/A")
    c = _check(client, [{"quote": REAL_QUOTE}], assertedBy="某三甲医院主任")
    assert a["results"] == c["results"]
    assert a["assertedBy"] != c["assertedBy"]


def test_bad_input_is_400_not_500(client):
    for bad in ({}, {"citations": []}, {"citations": [{}]}, {"citations": ["x"]}):
        r = client.post("/adjudicate/citations", json=bad)
        assert r.status_code == 400, (bad, r.status_code)
        assert r.json()["detail"]


def test_does_not_write_to_graphdb(client, graph):
    before = graph.size()
    _check(client, [{"quote": REAL_QUOTE}, {"quote": "编的"}])
    client.get("/graph/passages", params={"q": "or above"})
    assert graph.size() == before


# ───────────────────────── /adjudicate/scope ─────────────────────────


def test_scope_status_matches_what_is_actually_wired(client):
    """把还没实现的裁决类型标成 available，是这个端点最不能犯的错。

    所以不写死清单，而是拿 scope 声称的 available 去和代码里真正接线的
    `adjudicate.claim.ADJUDICABLE` 对齐 —— 以后加类型忘了改 scope，这里会亮。
    """
    from dmo.adjudicate.claim import ADJUDICABLE

    b = client.get("/adjudicate/scope").json()
    avail = {a["claimType"] for a in b["adjudicable"] if a["status"] == "available"}
    assert avail == {"Citation", *ADJUDICABLE}, f"scope 与实际接线不符：{avail}"
    assert all(a["status"] in ("available", "planned") for a in b["adjudicable"])
    assert all("endpoint" in a for a in b["adjudicable"] if a["status"] == "available")


def test_scope_states_what_it_cannot_do(client):
    b = client.get("/adjudicate/scope").json()
    topics = " ".join(x["topic"] for x in b["notAdjudicable"])
    for must in ("剂量", "概率", "时间窗"):
        assert must in topics, f"notAdjudicable 里必须点名「{must}」"
    assert b["neverReturns"]


def test_scope_does_not_inflate_coverage(client):
    """收录份数 ≠ 覆盖面。两个数字都要在，且必须能看出差距。"""
    c = client.get("/adjudicate/scope").json()["corpus"]
    assert c["citablePassages"] == 31
    assert c["sourcesWithCitablePassages"] < c["guidelineSources"]
    assert c["coverageCaveat"]


# ───────────────────────── /adjudicate/claim ─────────────────────────
#
# 这一族要 PG（患者事实层），所以单独一个 fixture —— 出处裁决刻意不依赖 PG，
# 不该因为 PG 没起来就一起 skip。


@pytest.fixture(scope="module")
def client_db(db, graph):
    from fastapi.testclient import TestClient

    from dmo.api import app

    return TestClient(app)


def _claim(client_db, pid, ctype, value, **kw):
    r = client_db.post("/adjudicate/claim",
                       json={"patientId": pid, "claim": {"type": ctype, "value": value}, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_single_sample_day_cannot_be_confirmed(client_db):
    """★ 本端点最有说服力的一条。

    A1C 落在糖尿病区间，纯 LLM 会说「是糖尿病」。但诊断切点
    confirmationRequired=true，只有一个采样日 ⟹ Provisional 而非 Confirmed。
    """
    b = _claim(client_db, "P90002", "Diagnosis",
               {"kind": "Diabetes", "verificationStatus": "Confirmed"})
    assert b["verdict"] == "contradicted"
    diffs = b["comparison"]["conflicts"][0]["diffs"]
    assert {"field": "verificationStatus", "claimed": "Confirmed",
            "system": "Provisional"} in diffs
    need = b["missingEvidence"][0]
    assert "复测" in need["need"]
    assert need["wouldChangeVerdictTo"] == "supported"
    # 缺什么可以说，值不能猜
    assert "不生成任何数值" in need["howToTest"]


def test_provisional_is_supported(client_db):
    b = _claim(client_db, "P90002", "Diagnosis",
               {"kind": "Diabetes", "verificationStatus": "Provisional"})
    assert b["verdict"] == "supported"
    assert "不是任何形式的诊疗背书" in b["supportedMeans"]


def test_misattributed_citation_is_caught(client_db):
    """★ 比 fabricated 更难也更值钱：引文逐字属实，但支撑的不是这件事。

    纯字符串比对抓不到（引文是真的），纯哈希比对也抓不到（哈希是真的）——
    要靠 thresholdCitesPassage 的边反查它到底支撑了什么。
    """
    b = _claim(client_db, "P90002", "Assessment",
               {"conclusion": "DiabetesRange", "thresholdId": "A1C-DIABETES-NONPREG"},
               citations=[{"quote": "126 mg/dL or above"},   # FPG 的切点，不是这条
                          {"quote": "6.5% or above"}])       # 正是支撑这条的
    assert b["verdict"] == "supported"
    assert b["citationCheck"]["misattributed"] == 1
    bad = [r for r in b["citationCheck"]["results"] if r.get("misattributed")]
    assert bad[0]["verdict"] == "verbatim", "引文本身是真的 —— 错的是用处"
    assert "引对了话，用错了地方" in bad[0]["misattributionReason"]


def test_no_evidence_is_unsupported_not_contradicted(client_db):
    """证据不足与「判定为错」是两回事。"""
    b = _claim(client_db, "P00016", "Assessment", {"conclusion": "Diabetes"})
    assert b["verdict"] == "unsupported"
    assert "证据不足与「判定为错」是两回事" in b["verdictReason"]
    assert b["missingEvidence"][0]["because"]


def test_out_of_scope_types_are_not_adjudicable(client_db):
    for ctype, must in (("Dosage", "不输出剂量"), ("Probability", "不是分数"),
                        ("Prognosis", "时间窗")):
        b = _claim(client_db, "P90002", ctype, {"x": 1})
        assert b["verdict"] == "not-adjudicable", ctype
        assert must in b["whyNotAdjudicable"], ctype


def test_unknown_types_do_not_pretend_to_be_adjudicated(client_db):
    """没接线的类型必须说「判不了」，不能返回一个看着像「没问题」的结果。"""
    b = _claim(client_db, "P90002", "SomeFutureClaimType", {"x": 1})
    assert b["verdict"] == "not-adjudicable"
    assert "planned" in b["whyNotAdjudicable"], "要提醒调用方去看 scope 的 status"


def test_adjudication_hash_is_stable(client_db):
    """同一条断言 + 同一版知识层与规则集 ⟹ 同一个哈希。simulate 的承诺在这里的对应物。"""
    args = ("P90002", "Diagnosis", {"kind": "Diabetes", "verificationStatus": "Confirmed"})
    hashes = {_claim(client_db, *args)["adjudicationHash"] for _ in range(3)}
    assert len(hashes) == 1


def test_who_said_it_does_not_change_the_hash_or_the_verdict(client_db):
    """谁说的、引了什么，都不改变本体自己推出来的那条结论。"""
    args = ("P90002", "Diagnosis", {"kind": "Diabetes", "verificationStatus": "Confirmed"})
    base = _claim(client_db, *args)
    other = _claim(client_db, *args, assertedBy="某三甲医院主任",
                   citations=[{"quote": "6.5% or above"}])
    assert other["adjudicationHash"] == base["adjudicationHash"]
    assert other["verdict"] == base["verdict"]


def test_claim_never_returns_a_boolean_verdict(client_db):
    import json

    b = _claim(client_db, "P90002", "Diagnosis",
               {"kind": "Diabetes", "verificationStatus": "Provisional"})
    txt = json.dumps(b, ensure_ascii=False)
    for banned in ('"reasonable"', '"valid"', '"passed"', '"approved"', '"isValid"'):
        assert banned not in txt


def test_claim_input_errors(client_db):
    assert client_db.post("/adjudicate/claim", json={}).status_code == 400
    assert client_db.post("/adjudicate/claim",
                          json={"patientId": "P90002"}).status_code == 400
    assert client_db.post("/adjudicate/claim", json={
        "patientId": "P90002", "claim": {"type": "Diagnosis"}}).status_code == 400
    assert client_db.post("/adjudicate/claim", json={
        "patientId": "NOPE",
        "claim": {"type": "Diagnosis", "value": {"kind": "x"}}}).status_code == 404


# ─────────────── claim：诊断切点 vs 管理目标 / 分层 / 用药安全 ───────────────


def test_diagnostic_threshold_and_management_target_are_adjudicated_apart(client_db):
    """★ 两类结论都是 dmo:Assessment，都进同一个模板，**只有 ruleId 能区分**。

    21-target-attainment.rq 开头写着：一个 A1C 6.8% 的患者，按诊断切点是超标、
    按管理目标是达标 —— 同一个数，两个相反的结论。不按 ruleId 收敛就会拿一类的
    断言去和另一类的结论比，判出来的对错是随机的。
    """
    target = _claim(client_db, "P90003", "TargetAttainment", {"conclusion": "High"})
    assert target["verdict"] == "supported"
    assert all(c["ruleId"] == "TARGET-ATTAINMENT" for c in target["systemConclusions"])

    diag = _claim(client_db, "P90003", "Assessment", {"conclusion": "High"})
    assert diag["verdict"] == "contradicted", "「High」是管理目标的词，不是诊断切点的"
    assert all(c["ruleId"] == "LAB-THRESHOLD-MATCH" for c in diag["systemConclusions"])


def test_risk_tier_claim(client_db):
    ok = _claim(client_db, "P00016", "RiskTier", {"tier": "Insufficient-Evidence"})
    assert ok["verdict"] == "supported"
    sysc = ok["systemConclusions"][0]
    # 命中 ≠ 计分，两个数字都得给
    assert sysc["factorsCounted"] <= sysc["factorsHit"]
    assert "_quotes" not in sysc, "内部字段不该漏进返回体"

    bad = _claim(client_db, "P00016", "RiskTier", {"tier": "High"})
    assert bad["verdict"] == "contradicted"


def test_medication_safety_claim(client_db):
    ok = _claim(client_db, "P90008", "MedicationSafety",
                {"medication": "empagliflozin", "severity": "Absolute"})
    assert ok["verdict"] == "supported"

    downgraded = _claim(client_db, "P90008", "MedicationSafety",
                        {"medication": "empagliflozin", "severity": "Caution"})
    assert downgraded["verdict"] == "contradicted", "把绝对禁忌说成「需谨慎」必须判错"


def test_scope_now_advertises_all_five_claim_types(client_db):
    avail = {a["claimType"] for a in client_db.get("/adjudicate/scope").json()["adjudicable"]
             if a["status"] == "available"}
    assert avail == {"Citation", "Assessment", "TargetAttainment", "Diagnosis",
                     "RiskTier", "MedicationSafety"}
