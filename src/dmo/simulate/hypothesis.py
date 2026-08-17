"""假设事实的校验与 RDF 化。**只开 LabResult 一类。**

## 三条拒绝，比三条接受重要

1. **术语不猜。** 只接受挂了 `dmo:hasThreshold` 的检验项（实测 7 个：
   A1C/FPG/GCT1H/GLU/OGTT2H/RPG/UACR）。库里另有上百个从指南 PDF 抽出来的
   同名 LabTest（`labTest/hba1c`、`labTest/fasting-plasma-glucose` …），
   它们**没有阈值**，拿去推演只会推出空集 —— 而空集看起来和"结论没变"
   一模一样。所以宁可当场拒绝并列出可用项，也不做模糊匹配、不算编辑距离。

2. **单位不默认。** 缺单位直接拒（`units.UnitError` 的老规矩：148 是 mg/dL
   还是 mmol/L，结论天差地别）。非规范单位只在 `map_unit_conversion` 里
   有**已核实**系数时才换算，且原值原单位全程保留 —— 与 ETL 同一套规矩，
   系数同一份数据，不在这里另开一张硬编码表。

3. **值不外推。** 假设值只能由调用方显式给出。本模块没有任何"推荐值"
   "典型值"的生成路径 —— 那是预测，不是推演。

## 为什么假设事实要标 Curated

规则 20 有可信度门禁：`valueTrustLevel="Unverified"` 的值一律不参与判定。
假设值若标 Unverified，规则直接跳过，推演永远推不出东西。
所以标 `Curated`（它确实不是上游那批随机数），假设性另用
`dmo:hypothetical true` + `dmo:factOrigin "simulated"` 两个独立标记表达。

这样规则一个字都不用改，而返回体里假设与实测始终可分 —— 两件事解耦。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date as _date
from decimal import Decimal, InvalidOperation
from typing import Any

from rdflib import XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF

from ..config import Config
from ..terms.units import Conversion, Converted, UnitError, convert

DMO = Namespace("https://example.org/dmo#")
BASE = "https://example.org/dmo/id/"

# 假设事实的 factOrigin。与 ehr-legacy / derived / demo-cohort 并列的第四类，
# 且**只存在于内存沙箱**里 —— 它永远不会出现在 GraphDB 或 PG 中。
SIMULATED_ORIGIN = "simulated"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 沙箱里可推演的检验项：必须挂了阈值，否则规则 20 推不出任何东西。
_TESTS_Q = """
PREFIX dmo: <https://example.org/dmo#>
SELECT DISTINCT ?test ?code ?unit WHERE {
  ?test dmo:labTestCode ?code ; dmo:hasThreshold ?th .
  ?th dmo:boundUnit ?unit .
}
"""


class HypothesisError(ValueError):
    """假设事实不合法。消息直接面向用户 —— 必须说清楚拒绝的理由和可用选项。"""


@dataclass(frozen=True)
class TestSpec:
    """一个可推演的检验项及其规范单位。"""

    iri: str
    code: str
    units: frozenset[str]


@dataclass(frozen=True)
class Hypothesis:
    """一条已校验的假设事实。字段顺序参与 derivationHash，**不要重排**。"""

    test_code: str
    test_iri: str
    value: Decimal
    unit: str
    collected_date: str
    source_value: Decimal | None
    source_unit: str | None

    @property
    def converted(self) -> bool:
        return self.source_unit is not None

    def fingerprint(self) -> str:
        """参与 derivationHash 的规范形式。用换算**后**的值 —— 7.8 mmol/L 与
        140.5 mg/dL 是同一个假设，理应得到同一个哈希。"""
        return f"{self.test_code}|{self.value}|{self.unit}|{self.collected_date}"

    def result_id(self) -> str:
        return "SIM-" + hashlib.sha1(self.fingerprint().encode()).hexdigest()[:16]

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "kind": "LabResult",
            "test": self.test_code,
            "value": float(self.value),
            "unit": self.unit,
            "collectedDate": self.collected_date,
            "hypothetical": True,
            "factOrigin": SIMULATED_ORIGIN,
            "labResultId": self.result_id(),
        }
        if self.converted:
            out["sourceValue"] = float(self.source_value)  # type: ignore[arg-type]
            out["sourceUnit"] = self.source_unit
            out["conversionNote"] = (
                f"{self.source_value} {self.source_unit} → {self.value} {self.unit}，"
                "系数取自 map_unit_conversion 中已人工核实的行。"
            )
        return out


def available_tests(ds) -> dict[str, TestSpec]:
    """沙箱里可推演的检验项，键是大写 code。"""
    acc: dict[str, dict[str, Any]] = {}
    for row in ds.query(_TESTS_Q):
        code = str(row.code)
        entry = acc.setdefault(code, {"iri": str(row.test), "units": set()})
        entry["units"].add(str(row.unit))
    return {
        code.upper(): TestSpec(v["iri"], code, frozenset(v["units"]))
        for code, v in acc.items()
    }


def _conversion(cfg: Config, test_iri: str, raw_unit: str, target: str) -> Conversion:
    """从 map_unit_conversion 取已核实的系数。取不到就返回 identity —— 由调用方拒绝。

    ⚠️ 不内置换算表。系数只有一份，在数据库里，和 ETL 用的是同一行。
    """
    from ..db.engine import onto_conn

    with onto_conn(cfg) as conn:
        row = conn.fetchone(
            "SELECT conv_factor, conv_offset FROM diabetes.map_unit_conversion "
            "WHERE concept_iri = %s AND unit_src = %s AND unit_target = %s",
            (test_iri, raw_unit, target))
    if not row:
        return Conversion(raw_unit, None, None)
    return Conversion(raw_unit, target, Decimal(str(row["conv_factor"])),
                      Decimal(str(row["conv_offset"] or 0)))


def parse_one(cfg: Config, tests: dict[str, TestSpec], raw: dict[str, Any]) -> Hypothesis:
    """校验一条假设事实。任何一处不合法都当场抛错，**不做兜底猜测**。"""
    term = str(raw.get("term") or "").strip()
    if not term:
        raise HypothesisError("假设事实缺 term（检验项代码）。")

    spec = tests.get(term.upper())
    if spec is None:
        usable = ", ".join(sorted(tests))
        raise HypothesisError(
            f"「{term}」不是可推演的检验项。本体里挂了诊断阈值的只有：{usable}。"
            "库里另有上百个从指南抽取的同名检验项，但它们没有阈值、推不出结论，"
            "因此不做模糊匹配 —— 本系统不猜术语。")

    raw_value = raw.get("value")
    if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
        raise HypothesisError(f"{spec.code} 缺 value。假设值必须显式给出，系统不生成候选值。")
    try:
        value = Decimal(str(raw_value))
    except (InvalidOperation, ValueError):
        raise HypothesisError(f"{spec.code} 的 value {raw_value!r} 不是数值。") from None

    unit = str(raw.get("unit") or "").strip()
    if not unit:
        raise HypothesisError(
            f"{spec.code} 缺 unit，拒绝判定。规范单位：{'/'.join(sorted(spec.units))}。"
            "缺单位的数值在临床上没有意义 —— 148 是 mg/dL 还是 mmol/L，结论天差地别。")

    src_value: Decimal | None = None
    src_unit: str | None = None
    if unit not in spec.units:
        target = sorted(spec.units)[0]
        conv = _conversion(cfg, spec.iri, unit, target)
        if conv.is_identity:
            raise HypothesisError(
                f"{spec.code} 的单位应为 {'/'.join(sorted(spec.units))}，收到 {unit!r}，"
                f"且 map_unit_conversion 里没有 {unit}→{target} 的**已核实**换算系数。"
                "换算系数是 analyte-specific 的，猜一个等于制造错误。")
        try:
            done: Converted = convert(value, unit, conv)
        except UnitError as e:
            raise HypothesisError(f"{spec.code} 单位换算失败：{e}") from None
        value, unit = done.value, done.unit
        src_value, src_unit = done.source_value, done.source_unit

    day = str(raw.get("date") or "").strip()
    if not _DATE_RE.match(day):
        raise HypothesisError(
            f"{spec.code} 的 date 必须是 YYYY-MM-DD，收到 {day!r}。"
            "日期不能省 —— 30 号规则按不同日期计数来区分 Provisional 与 Confirmed。")
    try:
        _date.fromisoformat(day)
    except ValueError:
        raise HypothesisError(f"{spec.code} 的 date {day!r} 不是合法日期。") from None

    return Hypothesis(spec.code, spec.iri, value, unit, day, src_value, src_unit)


def parse(cfg: Config, ds, assume: list[dict[str, Any]]) -> list[Hypothesis]:
    if not assume:
        raise HypothesisError(
            "assume 是空的。没有假设事实的推演等同于重算基线 —— "
            "要看现有结论请用 GET /patients/{pid}。")
    if len(assume) > 10:
        raise HypothesisError(f"一次最多注入 10 条假设事实，收到 {len(assume)} 条。")
    tests = available_tests(ds)
    if not tests:
        raise HypothesisError(
            "知识层里没有任何挂了阈值的检验项。沙箱快照可能是坏的，"
            "用 refresh=true 重取。")
    out = [parse_one(cfg, tests, r) for r in assume]

    seen: set[str] = set()
    for h in out:
        if h.fingerprint() in seen:
            raise HypothesisError(
                f"重复的假设事实：{h.test_code} {h.value}{h.unit} @{h.collected_date}。"
                "同一天同一项目同一个值注入两次，在图里是同一个 IRI，第二条会被静默吞掉。")
        seen.add(h.fingerprint())
    return out


def to_graph(hypotheses: list[Hypothesis], patient_iri: str) -> Graph:
    """铸成 RDF。IRI 全程确定性 —— 同一批假设跑两次必须得到同一张图。

    每个**日期**一个 Encounter：30 号规则数的是 `SUBSTR(collectedAt,1,10)` 的
    distinct 数，同日的多条检验挂同一次就诊才符合真实语义。
    """
    g = Graph()
    pat = URIRef(patient_iri)
    by_day: dict[str, list[Hypothesis]] = {}
    for h in hypotheses:
        by_day.setdefault(h.collected_date, []).append(h)

    for day, items in sorted(by_day.items()):
        eid = "SIM-ENC-" + hashlib.sha1(f"{patient_iri}|{day}".encode()).hexdigest()[:16]
        enc = URIRef(f"{BASE}encounter/{eid}")
        g.add((enc, RDF.type, DMO.ClinicalEncounter))
        g.add((enc, DMO.encounterId, Literal(eid)))
        g.add((enc, DMO.encounterDate, Literal(day, datatype=XSD.date)))
        g.add((enc, DMO.encounterType, Literal("Simulated")))
        g.add((enc, DMO.factOrigin, Literal(SIMULATED_ORIGIN)))
        g.add((enc, DMO.hypothetical, Literal(True)))
        g.add((pat, DMO.hasEncounter, enc))

        for h in items:
            node = URIRef(f"{BASE}labResult/{h.result_id()}")
            g.add((node, RDF.type, DMO.LabResult))
            g.add((node, DMO.labResultId, Literal(h.result_id())))
            g.add((node, DMO.resultValue, Literal(h.value, datatype=XSD.decimal)))
            g.add((node, DMO.resultUnit, Literal(h.unit)))
            g.add((node, DMO.collectedAt,
                   Literal(f"{h.collected_date}T00:00:00", datatype=XSD.dateTime)))
            g.add((node, DMO.measuredByTest, URIRef(h.test_iri)))
            # 规则 20 的可信度门禁只认 Unverified 与否；假设性由下面两个标记表达。
            g.add((node, DMO.valueTrustLevel, Literal("Curated")))
            g.add((node, DMO.factOrigin, Literal(SIMULATED_ORIGIN)))
            g.add((node, DMO.hypothetical, Literal(True)))
            if h.converted:
                g.add((node, DMO.sourceValue,
                       Literal(h.source_value, datatype=XSD.decimal)))
                g.add((node, DMO.sourceUnit, Literal(h.source_unit)))
            g.add((enc, DMO.producesLabResult, node))
    return g
