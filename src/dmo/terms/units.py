"""单位换算。**唯一**允许做换算的地方。

三条硬规则（plan §二）：

  1. 换算只在 ETL 做，SPARQL 里一次都不做。
     换算系数是 analyte-specific 的：葡萄糖 mmol/L→mg/dL 要 ×18.0182，
     肌酐 µmol/L→mg/dL 要 ÷88.4。写进 SPARQL 就必须在查询里判断"这是哪个分析物"，
     判断错一次，结论就错，而且错得看不出来。

  2. 原始值必须保留（source_value / source_unit）。

  3. **推断不出来就不换算。** 系数存在 map_lab_term.conv_factor，
     而那一列有 CHECK：只有 verify_status='verified' 的行才准填。
     从参考范围反推单位是推断不是断言，人工确认前不生效。

这个模块刻意**不内置任何换算表**。所有系数都来自 map_lab_term ——
硬编码一张表，就等于把"哪些换算被人工核实过"这件事从数据挪进了代码。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Conversion:
    """一条已核实的换算规则。target=None 表示不换算，原样通过。"""

    source_unit: str | None
    target_unit: str | None
    factor: Decimal | None
    offset: Decimal = Decimal(0)

    @property
    def is_identity(self) -> bool:
        return self.factor is None


@dataclass(frozen=True)
class Converted:
    value: Decimal
    unit: str
    source_value: Decimal | None
    source_unit: str | None
    converted: bool


class UnitError(ValueError):
    """单位缺失或不匹配。调用方必须处理 —— 不能默默当作"就用原值"。"""


def convert(raw: Decimal, raw_unit: str | None, conv: Conversion) -> Converted:
    """按已核实的规则换算。

    raw_unit 为空时**抛异常**而不是猜：缺单位的数值在临床上没有意义，
    148 是 mg/dL 还是 mmol/L，结论天差地别（合成夹具 P005 就是这一例）。
    """
    if raw_unit is None or not raw_unit.strip():
        raise UnitError("结果缺单位，拒绝判定")

    if conv.is_identity:
        # 不换算：目标单位就是原单位。这不是"失败"，是很多项目的正常状态
        # （肌酐/血小板等本来就没有诊断切点，换算也没有阈值可比）。
        return Converted(raw, raw_unit, None, None, converted=False)

    if conv.source_unit and raw_unit != conv.source_unit:
        raise UnitError(
            f"单位 {raw_unit!r} 与映射登记的 {conv.source_unit!r} 不符，拒绝换算"
        )
    assert conv.factor is not None
    target = conv.target_unit or raw_unit
    return Converted(
        value=raw * conv.factor + conv.offset,
        unit=target,
        source_value=raw,
        source_unit=raw_unit,
        converted=True,
    )
