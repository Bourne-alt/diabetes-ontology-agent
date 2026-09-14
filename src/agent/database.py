"""Bounded, structured SELECTs. The model never supplies executable SQL."""

from contextlib import contextmanager
from typing import Literal

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from dmo.config import ONTO_SCHEMA, UPSTREAM_SCHEMA, Config
from dmo.db.etl import SPECS

Database = Literal["original", "ontology"]
ORIGINAL = {spec.upstream: spec.columns for spec in SPECS}
ONTOLOGY_TABLES = frozenset(
    {
        "core_patient",
        "core_encounter",
        "core_lab_result",
        "core_observation",
        "core_diagnosis",
        "core_medication_use",
        "pred_risk_stratification",
        "pred_factor_hit",
        "map_concept_ref",
        "map_icd10",
        "map_drug_term",
        "map_unmapped_term",
        *(spec.target for spec in SPECS),
    }
)
# Always include interpretation/provenance fields when available.
CONTEXT_COLUMNS = {
    "patientid",
    "fact_origin",
    "trust_level",
    "verification_status",
    "caveat",
    "source_table",
    "source_pk",
    "source_value",
    "source_unit",
    "result_unit",
    "demo_scenario",
    "counted_in_tier",
    "quote",
    "sha256",
    "insufficient_reason",
    "monitoring_gap",
    "rule_id",
    "rule_version",
    "external_note",
}


class FactStore:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    @contextmanager
    def connection(self, database: Database):
        if database not in ("original", "ontology"):
            raise ValueError("database 必须是 original 或 ontology")
        dsn = self.cfg.upstream_dsn if database == "original" else self.cfg.onto_dsn
        with psycopg.connect(
            dsn,
            connect_timeout=5,
            row_factory=dict_row,
            options="-c default_transaction_read_only=on -c statement_timeout=10000 "
            "-c lock_timeout=2000 -c idle_in_transaction_session_timeout=15000",
        ) as conn:
            # Set on the transaction as well, regardless of DSN options.
            conn.execute("SET TRANSACTION READ ONLY")
            yield conn

    def catalog(self, database: Database, table: str | None = None):
        schema = UPSTREAM_SCHEMA if database == "original" else ONTO_SCHEMA
        allowed = set(ORIGINAL) if database == "original" else ONTOLOGY_TABLES
        if table is not None and table not in allowed:
            raise ValueError("表不在查询白名单中；先调用 inspect_fact_schema。")
        with self.connection(database) as conn:
            rows = conn.execute(
                """
                SELECT c.table_name, c.column_name, c.data_type,
                       col_description(pc.oid, a.attnum) AS description
                FROM information_schema.columns c
                JOIN pg_namespace pn ON pn.nspname = c.table_schema
                JOIN pg_class pc ON pc.relnamespace = pn.oid AND pc.relname = c.table_name
                JOIN pg_attribute a ON a.attrelid = pc.oid AND a.attname = c.column_name
                WHERE c.table_schema = %s AND c.table_name = ANY(%s)
                ORDER BY c.table_name, c.ordinal_position
                LIMIT 1000
            """,
                (schema, [table] if table else sorted(allowed)),
            ).fetchall()
        if database == "original":
            rows = [r for r in rows if r["column_name"] in ORIGINAL[r["table_name"]]]
        return {"database": database, "schema": schema, "columns": rows}

    def query(
        self,
        database: Database,
        table: str,
        columns: list[str],
        filters: dict,
        limit: int = 20,
        offset: int = 0,
    ):
        if not columns or len(columns) > 40 or not filters or len(filters) > 8:
            raise ValueError("需要显式列名和等值筛选条件（最多 40 列 / 8 个条件）。")
        if not 1 <= limit <= 100 or not 0 <= offset <= 10000:
            raise ValueError("limit 应为 1..100；offset 应为 0..10000。")
        card = self.catalog(database, table)
        available = {r["column_name"] for r in card["columns"]}
        if not set(columns) | set(filters) <= available:
            raise ValueError("列不存在或不在白名单中；先检查 schema，禁止 SQL 表达式。")
        if any(not isinstance(v, (str, int, float, bool, type(None))) for v in filters.values()):
            raise ValueError("筛选值只能是标量或 null。")
        if table.startswith("core_") and not {"patientid", "fact_origin"} & filters.keys():
            raise ValueError("core_* 查询必须按 patientid 或 fact_origin 收敛，避免混合来源。")
        selected = sorted(set(columns) | (CONTEXT_COLUMNS & available))
        conditions, values = [], []
        for column, value in filters.items():
            if value is None:
                conditions.append(sql.SQL("{} IS NULL").format(sql.Identifier(column)))
            else:
                conditions.append(sql.SQL("{} = %s").format(sql.Identifier(column)))
                values.append(value)
        statement = sql.SQL(
            "SELECT {cols} FROM {schema}.{table} WHERE {where} ORDER BY {order} LIMIT %s OFFSET %s"
        ).format(
            cols=sql.SQL(", ").join(map(sql.Identifier, selected)),
            schema=sql.Identifier(card["schema"]),
            table=sql.Identifier(table),
            where=sql.SQL(" AND ").join(conditions),
            order=sql.SQL(", ").join(map(sql.Identifier, selected)),
        )
        with self.connection(database) as conn:
            rows = conn.execute(statement, [*values, limit + 1, offset]).fetchall()
        raw = database == "original" or table.startswith("stg_")
        return {
            "database": database,
            "schema": card["schema"],
            "table": table,
            "columns": selected,
            "filters": filters,
            "rows": rows[:limit],
            "rowCount": len(rows[:limit]),
            "hasMore": len(rows) > limit,
            "nextOffset": offset + limit if len(rows) > limit else None,
            "notice": "原始事实未过质量门槛，仅供溯源，不可直接用于临床推断。"
            if raw
            else "按每行 fact_origin/trust_level 区分来源与可信度；零行不等于正常。",
        }
