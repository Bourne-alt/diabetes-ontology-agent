"""确定性病程推演的测试。

这些断言盯的是推演的**三条立身之本**，任何一条挂了，推演就退化成
"看起来很确定的猜测"：

  1. 边界精确 —— 开闭区间不能用 >= 近似（S16 的三个 A1C 切点）
  2. 零污染   —— 推演跑多少次，GraphDB 三元组数一条都不能变
  3. 可复现   —— 同一请求必须得到同一个 derivationHash

外加两条拒绝路径：不猜术语、不默认单位。它们和"能推出结论"同等重要 ——
本仓库的立场是判不了就说判不了，而不是给一个漂亮的错答案。
"""

from __future__ import annotations

import pytest

from dmo.simulate import HypothesisError, simulate

# 演示队列 S02：单次 A1C 7.4% ⟹ Provisional。整套推演测试都挂在它身上，
# 因为它是"差一天复测"这件事最干净的载体。
PID = "P90002"
DAY2 = "2026-02-20"


def _assume(value, unit="percent", term="A1C", date=DAY2):
    return [{"term": term, "value": value, "unit": unit, "date": date}]


@pytest.fixture(scope="module")
def sim(cfg, graph, db):
    """真打 PG + GraphDB。理由同 conftest —— 要验的就是三者合在一起的行为。"""
    def _run(assume, **kw):
        return simulate(cfg, PID, assume, **kw)
    return _run


# ── 1. 边界精确 ────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected,threshold", [
    ("5.6", "Normal", "A1C-NORMAL-NONPREG"),
    # 5.7 是 Prediabetes 的**闭**下界。用 > 近似会把它错判成 Normal。
    ("5.7", "Prediabetes", "A1C-PREDIABETES-NONPREG"),
    # 6.4 是 Prediabetes 的**闭**上界。用 < 近似会让它落空。
    ("6.4", "Prediabetes", "A1C-PREDIABETES-NONPREG"),
    ("6.5", "DiabetesRange", "A1C-DIABETES-NONPREG"),
])
def test_a1c_boundaries_are_exact(sim, value, expected, threshold):
    out = sim(_assume(value))
    added = [d for d in out["delta"]
             if d["change"] == "added" and d["type"] == "Assessment"]
    assert added, f"A1C {value}% 没推出任何评估"
    assert added[0]["after"]["conclusion"] == expected
    assert added[0]["after"]["thresholdId"] == threshold


def test_second_day_turns_provisional_into_confirmed(sim):
    """整个项目最有说服力的一条：两次结论的差别**只有测了几天**。"""
    out = sim(_assume("7.9"))
    changed = [d for d in out["delta"]
               if d["change"] == "changed" and d["type"] == "Diagnosis"]
    assert changed, "补一天复测后诊断状态没有变化"
    status = changed[0]["fields"]["verificationStatus"]
    assert status["before"] == "Provisional"
    assert status["after"] == "Confirmed"


def test_same_day_repeat_does_not_confirm(sim):
    """同一天再测一次不算复测 —— 30 号规则数的是 distinct 日期。"""
    out = sim(_assume("7.9", date="2026-01-15"))
    changed = [d for d in out["delta"]
               if d["change"] == "changed" and d["type"] == "Diagnosis"]
    assert not changed, "同日重复检验不应把 Provisional 变成 Confirmed"


# ── 2. 零污染 ──────────────────────────────────────────────────────────

def test_simulation_never_writes_to_graphdb(sim, graph):
    """沙箱**没有写路径**。这条断言是"物理隔离"的证明，不是提醒。"""
    before = graph.size()
    for v in ("5.6", "6.5", "7.9"):
        sim(_assume(v))
    assert graph.size() == before, (
        "推演改变了 GraphDB 的三元组数 —— 沙箱漏了写路径，"
        "假设事实正在污染真实图")


def test_hypothetical_facts_are_labelled(sim):
    """假设与实测必须在返回体里可分。混在一起 = 拿假设冒充事实。"""
    out = sim(_assume("7.9"))
    labs = [n for n in _walk(out["derivationTree"]) if n["node"] == "LabResult"]
    provenances = {n["provenance"] for n in labs}
    assert provenances == {"measured", "hypothetical"}
    for h in out["hypotheticalFacts"]:
        assert h["hypothetical"] is True
        assert h["factOrigin"] == "simulated"


def _walk(nodes):
    for n in nodes:
        yield n
        yield from _walk(n.get("children", []))


# ── 3. 可复现 ──────────────────────────────────────────────────────────

def test_derivation_hash_is_stable(sim):
    """同一请求跑 5 遍必须同哈希。这是相对 LLM 最硬的一条差异。"""
    hashes = {sim(_assume("7.9"))["derivationHash"] for _ in range(5)}
    assert len(hashes) == 1, f"5 次推演得到 {len(hashes)} 个不同的 derivationHash"


def test_hash_is_order_independent(sim):
    """注入顺序不该影响结论，因此也不该影响哈希。"""
    a = _assume("7.9") + _assume("140", "mg-per-dL", "FPG", "2026-03-01")
    b = list(reversed(a))
    assert sim(a)["derivationHash"] == sim(b)["derivationHash"]


def test_different_value_gives_different_hash(sim):
    """哈希必须对输入敏感 —— 否则它证明不了任何东西。"""
    assert sim(_assume("7.9"))["derivationHash"] != sim(_assume("6.5"))["derivationHash"]


# ── 4. 拒绝路径：不猜术语 ──────────────────────────────────────────────

def test_unknown_term_is_rejected_not_guessed(sim):
    with pytest.raises(HypothesisError) as e:
        sim(_assume("7.9", term="糖化血红蛋白"))
    assert "不猜术语" in str(e.value)


def test_extracted_labtest_without_threshold_is_rejected(sim):
    """`labTest/hba1c` 是从指南 PDF 抽出来的同义词，**没有阈值**。

    接受它只会推出空集，而空集看起来和"结论没变"一模一样 —— 最危险的静默失败。
    """
    with pytest.raises(HypothesisError) as e:
        sim(_assume("7.9", term="hba1c"))
    assert "A1C" in str(e.value), "拒绝时必须列出可用的检验项"


# ── 5. 拒绝路径：不默认单位 ────────────────────────────────────────────

def test_missing_unit_is_rejected(sim):
    with pytest.raises(HypothesisError) as e:
        sim(_assume("7.9", unit=""))
    assert "缺 unit" in str(e.value)


def test_unconvertible_unit_is_rejected(sim):
    """A1C 没有 percent 以外的已核实换算系数，猜一个等于制造错误。"""
    with pytest.raises(HypothesisError) as e:
        sim(_assume("53", unit="mmol-per-mol"))
    assert "已核实" in str(e.value)


def test_verified_conversion_keeps_source_value(sim):
    """S11：7.8 mmol/L 不换算会落进 FPG-NORMAL，结论完全相反。

    换算必须发生，且原值原单位必须全程保留 —— 与 ETL 同一套规矩。
    """
    out = sim(_assume("7.8", "mmol-per-L", "FPG", "2026-03-01"))
    fact = out["hypotheticalFacts"][0]
    assert fact["unit"] == "mg-per-dL"
    assert fact["sourceUnit"] == "mmol-per-L"
    assert fact["sourceValue"] == pytest.approx(7.8)
    assert fact["value"] == pytest.approx(140.54, abs=0.01)


# ── 6. 边界情形 ────────────────────────────────────────────────────────

def test_empty_assume_is_rejected(sim):
    with pytest.raises(HypothesisError):
        sim([])


def test_duplicate_hypothesis_is_rejected(sim):
    """同一天同项目同值注入两次，在图里是同一个 IRI，第二条会被静默吞掉。"""
    with pytest.raises(HypothesisError) as e:
        sim(_assume("7.9") + _assume("7.9"))
    assert "重复" in str(e.value)


def test_bad_date_is_rejected(sim):
    with pytest.raises(HypothesisError) as e:
        sim(_assume("7.9", date="2026/02/20"))
    assert "YYYY-MM-DD" in str(e.value)


def test_no_probability_or_time_window_in_simulation(sim):
    """与 test_scenarios.py 的同名断言一脉：推演也不许输出概率与时间窗。

    两条免责声明本身就在说"非概率预测"，扫描前必须先摘掉 —— 否则这条测试
    永远因为自己的免责声明而失败。
    """
    import json

    out = {k: v for k, v in sim(_assume("7.9")).items()
           if k not in ("disclaimer", "hypotheticalNote")}
    blob = json.dumps(out, ensure_ascii=False)
    for banned in ("概率", "风险评分", "预计在", "年内发生", "%的可能", "发生率"):
        assert banned not in blob, f"推演返回体里出现了 {banned}"
