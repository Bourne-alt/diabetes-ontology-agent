"""L0 快照：hospital_zd.patient_analysis → onto_db.diabetes.stg_*

两个库不在一个 database 上，PG 不能跨库 join，所以走应用层搬运。
读连接是 `upstream_conn`（会话只读），写连接是 `onto_conn`，两条连接从头到尾
不共享事务 —— 也就没有任何一条语句有机会写到上游去。

**全量重建**而不是增量：表最大 1600 行，全量能保证 stg 与上游逐行一致，
增量则要处理删除，而上游没有软删除标记，处理不了。等数据量上去了再说。

姓名与身份证号从**列白名单**里就排除了，不是拉进来再过滤 —— 见 002_stg.sql 的说明。
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from psycopg import sql

from ..config import Config
from .engine import onto_conn, upstream_conn


@dataclass(frozen=True)
class PullSpec:
    upstream: str
    """patient_analysis 下的表名。"""
    target: str
    """diabetes 下的目标表名。"""
    columns: tuple[str, ...]
    """要拉的列。**白名单**——不在这里的列永远进不来。"""
    pk_parts: tuple[str, ...]
    """拼 source_pk 的列。已实测在上游唯一。"""


SPECS: tuple[PullSpec, ...] = (
    PullSpec(
        "patient_basic_info", "stg_patient_basic",
        # ⚠️ 刻意排除：name / idenno / hometel / linkmanname / linkmantel /
        #    monthername / home。脱敏做在入口，不做在出口。
        ("patientid", "sexcode", "birthday", "nationcode", "vipflag", "mari",
         "relacode", "istreatment", "lregdate", "lihosdate", "louthosdate",
         "councode", "province", "city", "area", "profcode", "pactcode",
         "pactname", "paykindcode"),
        ("patientid",),
    ),
    PullSpec(
        "diagnose_query", "stg_diagnose",
        ("patientid", "clinicno", "diseaseid", "diseasetype", "diseasetypecode",
         "icd10code", "icd10name", "createdtime"),
        ("patientid", "clinicno", "diseaseid"),
    ),
    PullSpec(
        "cdr_lis_detail", "stg_lis_detail",
        ("patientid", "visitedid", "itemcode", "itemname", "ordsn",
         "sampletype", "specimename", "inspectiondate", "testcode"),
        ("testcode",),
    ),
    PullSpec(
        "cdr_lis_result", "stg_lis_result",
        ("testcode", "itemcode", "itemname", "ordsn", "inspectionresult",
         "inspectionresultrange", "resultstateclass"),
        ("testcode", "itemcode"),
    ),
    PullSpec(
        "op_order_query", "stg_op_order",
        ("patientid", "clinicno", "canceldate", "termclass", "termclassname",
         "termid", "termname", "costref", "modate", "combono"),
        ("patientid", "clinicno", "termid"),
    ),
    PullSpec(
        "patient_finoprreglist", "stg_outpatient_reg",
        ("patientid", "clinicno", "add_flag", "bgn_time", "book_type", "branch_no",
         "cancel_date", "dept_code", "dept_name", "dept_address", "is_emergency",
         "own_cost", "pay_cost", "pub_cost", "reg_level_code", "reg_level_name",
         "regdate"),
        ("patientid", "clinicno"),
    ),
)

BY_TARGET = {s.target: s for s in SPECS}


def _batch_id() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def pull_one(cfg: Config, spec: PullSpec, batch: str) -> int:
    """拉一张表。全量替换，单事务。"""
    select = sql.SQL("SELECT {cols} FROM {schema}.{table}").format(
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in spec.columns),
        schema=sql.Identifier("patient_analysis"),
        table=sql.Identifier(spec.upstream),
    )
    with upstream_conn(cfg) as up, up.cursor() as cur:
        cur.execute(select)
        rows = cur.fetchall()

    pk_idx = [spec.columns.index(p) for p in spec.pk_parts]
    target_cols = (*spec.columns, "source_pk", "pull_batch")
    insert = sql.SQL("INSERT INTO diabetes.{t} ({cols}) VALUES ({ph})").format(
        t=sql.Identifier(spec.target),
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in target_cols),
        ph=sql.SQL(", ").join(sql.Placeholder() * len(target_cols)),
    )

    payload = []
    for r in rows:
        vals = [r[c] for c in spec.columns]
        # source_pk 用 '|' 拼。上游这几列都不含 '|'（实测），不然要换分隔符或转义。
        pk = "|".join("" if vals[i] is None else str(vals[i]) for i in pk_idx)
        payload.append((*vals, pk, batch))

    with onto_conn(cfg) as conn:
        conn.execute(
            sql.SQL("TRUNCATE TABLE diabetes.{t}").format(t=sql.Identifier(spec.target))
        )
        with conn.cursor() as cur:
            cur.executemany(insert, payload)
        conn.commit()
    return len(payload)


def run(cfg: Config, *, only: str | None = None) -> int:
    specs = SPECS
    if only:
        if only not in BY_TARGET:
            raise SystemExit(
                f"没有这张目标表：{only}\n可选：{', '.join(sorted(BY_TARGET))}"
            )
        specs = (BY_TARGET[only],)

    batch = _batch_id()
    print(f"批次 {batch}")
    total = 0
    for spec in specs:
        n = pull_one(cfg, spec, batch)
        total += n
        print(f"  ✓ {spec.upstream:<28} → diabetes.{spec.target:<22} {n:>5} 行")

    # 拉完立刻核对：stg 行数必须等于上游行数。不等就是白名单或 PK 拼错了。
    problems = []
    with upstream_conn(cfg) as up, onto_conn(cfg) as conn:
        for spec in specs:
            src = up.scalar(
                sql.SQL("SELECT count(*) FROM patient_analysis.{t}").format(
                    t=sql.Identifier(spec.upstream))
            )
            dst = conn.scalar(
                sql.SQL("SELECT count(*) FROM diabetes.{t}").format(
                    t=sql.Identifier(spec.target))
            )
            if src != dst:
                problems.append(f"{spec.upstream}: 上游 {src} 行，落地 {dst} 行")
    if problems:
        print("\n✗ 行数对不上：")
        for p in problems:
            print(f"    {p}")
        print("  最可能的原因：source_pk 在上游不唯一，主键冲突把行吃掉了。")
        return 1

    print(f"\n✓ 共 {total} 行，逐表行数与上游一致")
    return 0
