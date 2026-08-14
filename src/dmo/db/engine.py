"""连接工厂 —— 「不动原数据」的三道锁里的前两道。

第一道 · 物理隔离
    `upstream_conn()` 用 `hospital_zd` 的 DSN，连上立刻把会话置为 READ ONLY；
    `onto_conn()` 用 `onto_db` 的 DSN。**写路径的连接字符串根本不指向 hospital_zd**，
    所以「写错库」这个失败模式在这一层就不存在了，不需要靠代码审查兜。

第二道 · 语句守卫
    `onto_conn()` 返回的连接把 search_path 钉死在 `diabetes`，并对执行的 SQL 做
    schema 白名单校验：出现 `patient_analysis.` / `semantic_link.` 这类跨库残留写法
    直接抛异常。这一道防的不是"连错库"（第一道已经防住了），而是**从上游表名复制粘贴
    DDL 时把 schema 前缀一起带过来**。

第三道（基线校验）在 baseline.py。

⚠️ 只读会话不是万能的：它挡得住 INSERT/UPDATE/DELETE/DDL，挡不住 `SELECT
pg_sleep(3600)` 这类资源占用。真实生产该用独立的只读角色；本项目用的是超级用户，
所以这层守卫是**自律不是强制**，README 里必须写明这一点。
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from ..config import ONTO_SCHEMA, UPSTREAM_SCHEMA, Config

# onto 连接允许触碰的 schema。除此之外一律拒绝。
WRITABLE_SCHEMAS = frozenset({ONTO_SCHEMA, "public", "pg_temp"})

# 出现在 SQL 里就说明这条语句走错了连接。
FORBIDDEN_SCHEMA_RE = re.compile(
    r"\b(patient_analysis|semantic_link|decision_support|lingshub_ontology)\s*\.",
    re.IGNORECASE,
)

# 注释与字符串字面量里的内容不是引用。DDL 的 COMMENT ON 里写上游表名是**正常且必要**的
# （说明这一列的数据从哪来），不该被守卫拦下。
_SQL_NOISE_RE = re.compile(
    r"--[^\n]*"                 # 行注释
    r"|/\*.*?\*/"               # 块注释
    r"|'(?:[^']|'')*'"          # 单引号字符串（含 '' 转义）
    r"|\$(\w*)\$.*?\$\1\$",     # 美元引用
    re.DOTALL,
)


def strip_sql_noise(query: str) -> str:
    """去掉注释与字符串字面量，只留可能是标识符的部分。"""
    return _SQL_NOISE_RE.sub(" ", query)


class GuardViolation(RuntimeError):
    """SQL 触碰了这个连接不该碰的 schema。"""


class ReadOnlyViolation(RuntimeError):
    """在只读连接上试图写。"""


# 只读会话上一律不许出现的动词。psycopg 本身不拦，PG 会拦，但我们要更早、更清楚地报错。
_WRITE_VERBS = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|TRUNCATE|DROP|ALTER|CREATE|GRANT|REVOKE|COPY\s+\S+\s+FROM)\b",
    re.IGNORECASE,
)


class GuardedCursor:
    """游标代理。psycopg 的 Cursor 是 C 扩展，`cur.execute = ...` 会 AttributeError，
    所以守卫只能靠组合而不是打补丁。副作用是白名单语义：这里没转发的方法就用不了。
    """

    def __init__(self, cur: psycopg.Cursor, check) -> None:  # type: ignore[no-untyped-def]
        self._cur = cur
        self._check = check

    def execute(self, query, params=None, **kw):  # type: ignore[no-untyped-def]
        self._check(query if isinstance(query, str) else query.as_string(self._cur))
        return self._cur.execute(query, params, **kw)

    def executemany(self, query, params_seq, **kw):  # type: ignore[no-untyped-def]
        self._check(query if isinstance(query, str) else query.as_string(self._cur))
        return self._cur.executemany(query, params_seq, **kw)

    def copy(self, statement, *a, **kw):  # type: ignore[no-untyped-def]
        self._check(statement if isinstance(statement, str) else statement.as_string(self._cur))
        return self._cur.copy(statement, *a, **kw)

    def fetchone(self):  # type: ignore[no-untyped-def]
        return self._cur.fetchone()

    def fetchall(self):  # type: ignore[no-untyped-def]
        return self._cur.fetchall()

    def fetchmany(self, size: int = 0):  # type: ignore[no-untyped-def]
        return self._cur.fetchmany(size)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._cur)

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount

    @property
    def description(self):  # type: ignore[no-untyped-def]
        return self._cur.description


class GuardedConnection:
    """psycopg 连接的薄包装，在 execute 之前跑守卫。

    刻意不继承 `psycopg.Connection` —— 继承会把几十个我们没审过的入口一并暴露出去，
    组合则是白名单：只有这里显式转发的方法可用。
    """

    def __init__(self, conn: psycopg.Connection, *, readonly: bool, label: str) -> None:
        self._conn = conn
        self._readonly = readonly
        self._label = label

    # ── 守卫 ────────────────────────────────────────────────────────
    def _check(self, query: str) -> None:
        code = strip_sql_noise(query)
        if self._readonly and _WRITE_VERBS.match(code):
            verb = code.strip().split()[0].upper()
            raise ReadOnlyViolation(
                f"{self._label} 是只读连接，拒绝执行 {verb}。"
                f"要写 {ONTO_SCHEMA} 请用 onto_conn()。"
            )
        if not self._readonly:
            hit = FORBIDDEN_SCHEMA_RE.search(code)
            if hit:
                raise GuardViolation(
                    f"{self._label} 连接的是 onto_db，SQL 里出现了 `{hit.group(1)}.` —— "
                    f"那个 schema 在 hospital_zd，跨库引用不成立。"
                    f"上游数据请先用 `dmo etl pull` 拉进 {ONTO_SCHEMA}.stg_*。"
                )

    # ── 转发 ────────────────────────────────────────────────────────
    def execute(self, query: str | sql.Composed, params: Any = None) -> psycopg.Cursor:
        self._check(query if isinstance(query, str) else query.as_string(self._conn))
        return self._conn.execute(query, params)

    def fetchall(self, query: str | sql.Composed, params: Any = None) -> list[dict]:
        with self.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def fetchone(self, query: str | sql.Composed, params: Any = None) -> dict | None:
        with self.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()

    def scalar(self, query: str | sql.Composed, params: Any = None) -> Any:
        row = self.fetchone(query, params)
        return None if row is None else next(iter(row.values()))

    @contextmanager
    def cursor(self) -> Iterator[GuardedCursor]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            yield GuardedCursor(cur, self._check)

    def commit(self) -> None:
        if self._readonly:
            return  # 只读会话 commit 是无害的 no-op，但不要让调用方以为写成功了
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    @property
    def raw(self) -> psycopg.Connection:
        """逃生口。用它就绕过了守卫 —— 只在 etl.py 的 COPY 快路径里用，且必须注释理由。"""
        return self._conn


@contextmanager
def upstream_conn(cfg: Config) -> Iterator[GuardedConnection]:
    """连 hospital_zd。会话级只读，读 patient_analysis 的代码只能拿这个。"""
    with psycopg.connect(cfg.upstream_dsn, autocommit=True) as conn:
        # autocommit + SESSION CHARACTERISTICS：之后每个隐式事务都是只读的。
        conn.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
        conn.execute("SET statement_timeout = '120s'")
        conn.execute(sql.SQL("SET search_path = {}, public").format(sql.Identifier(UPSTREAM_SCHEMA)))
        yield GuardedConnection(conn, readonly=True, label="upstream(hospital_zd)")


@contextmanager
def onto_conn(cfg: Config, *, autocommit: bool = False) -> Iterator[GuardedConnection]:
    """连 onto_db。唯一可写路径，search_path 钉死在 diabetes。"""
    with psycopg.connect(cfg.onto_dsn, autocommit=autocommit) as conn:
        conn.execute("SET statement_timeout = '300s'")
        conn.execute(sql.SQL("SET search_path = {}, public").format(sql.Identifier(ONTO_SCHEMA)))
        yield GuardedConnection(conn, readonly=False, label="onto(onto_db)")


def ping(cfg: Config) -> dict[str, Any]:
    """两库连通性 + 权限探测。`dmo db status` 的数据来源。"""
    out: dict[str, Any] = {}
    with upstream_conn(cfg) as up:
        out["upstream_version"] = up.scalar("SELECT version()")
        out["upstream_readonly"] = up.scalar("SHOW transaction_read_only") == "on"
        out["upstream_tables"] = up.fetchall(
            """
            SELECT c.relname AS table_name,
                   has_table_privilege(current_user, c.oid, 'SELECT') AS can_select,
                   c.reltuples::bigint AS est_rows
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relkind = 'r'
            ORDER BY c.relname
            """,
            (UPSTREAM_SCHEMA,),
        )
    with onto_conn(cfg) as onto:
        out["onto_version"] = onto.scalar("SELECT version()")
        out["onto_can_create"] = onto.scalar(
            "SELECT has_schema_privilege(current_user, %s, 'CREATE')", (ONTO_SCHEMA,)
        )
        out["onto_tables"] = onto.fetchall(
            """
            SELECT c.relname AS table_name, c.reltuples::bigint AS est_rows
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relkind = 'r'
            ORDER BY c.relname
            """,
            (ONTO_SCHEMA,),
        )
    return out
