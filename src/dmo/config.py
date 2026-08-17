"""配置：两个 PostgreSQL DSN + 一个 GraphDB 端点。

刻意分成**两个 DSN**而不是一个 DSN 加 schema 参数 —— 上游 `hospital_zd` 与我们独占的
`onto_db` 是两个 database，PG 本来就不能跨库 join。分开之后「只读」这件事变成
**物理性质**：写路径的连接字符串根本不指向 hospital_zd，比任何语句守卫都硬。

`.env` 读取只用标准库，不引入 python-dotenv —— 构建层保持零额外依赖的惯例延续到这里。
环境变量优先于 `.env`，方便 CI 覆盖。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"

# 上游患者库里我们唯一关心的 schema。
UPSTREAM_SCHEMA = "patient_analysis"
# 我们独占、且是唯一允许写入的 schema。engine.py 的守卫按这个值校验。
ONTO_SCHEMA = "diabetes"


def _parse_env_file(path: Path) -> dict[str, str]:
    """极简 .env 解析：KEY=VALUE，支持 # 注释与两侧引号。

    不支持变量插值与多行值 —— 真需要了再说，现在多写的每一行都是要维护的债。
    """
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def _get(env: dict[str, str], *names: str, default: str | None = None) -> str | None:
    """按顺序找第一个有值的键。环境变量优先于 .env。"""
    for name in names:
        val = os.environ.get(name) or env.get(name)
        if val:
            return val
    return default


def _swap_database(dsn: str, database: str) -> str:
    """把 DSN 的库名换成另一个，其余（用户/密码/主机/端口/参数）原样保留。

    只在没有显式配 DMO_ONTO_DSN 时兜底用 —— 两个库在同一实例上是本项目的实情，
    但这是**便利默认值**不是假设，显式配置永远优先。
    """
    parts = urlsplit(dsn)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def redact(dsn: str) -> str:
    """日志里出现 DSN 时抹掉密码。任何打印 DSN 的地方都必须过这一层。"""
    return re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", dsn)


@dataclass(frozen=True)
class Config:
    upstream_dsn: str
    """hospital_zd —— 只读。engine.upstream_conn() 会强制会话只读。"""

    onto_dsn: str
    """onto_db —— 唯一可写目标。"""

    graphdb_endpoint: str
    """GraphDB 根地址，如 http://localhost:7200（不含 /repositories/xxx）。"""

    graphdb_repository: str
    graphdb_timeout: int

    @property
    def sparql_endpoint(self) -> str:
        return f"{self.graphdb_endpoint}/repositories/{self.graphdb_repository}"

    def describe(self) -> str:
        return (
            f"  upstream : {redact(self.upstream_dsn)}  (schema {UPSTREAM_SCHEMA}, 只读)\n"
            f"  onto     : {redact(self.onto_dsn)}  (schema {ONTO_SCHEMA}, 可写)\n"
            f"  graphdb  : {self.sparql_endpoint}  (timeout {self.graphdb_timeout}s)"
        )


def load(env_file: Path | None = None) -> Config:
    env = _parse_env_file(env_file or ENV_FILE)

    upstream = _get(env, "DMO_UPSTREAM_DSN", "AGENT_PATIENT_PG_DSN", "PG_DSN")
    if not upstream:
        raise SystemExit(
            "缺少上游患者库 DSN。请在 .env 里设 PG_DSN（或 DMO_UPSTREAM_DSN）。"
        )

    onto = _get(env, "DMO_ONTO_DSN")
    if not onto:
        # 兜底：与上游同实例、库名换成 onto_db。
        onto = _swap_database(upstream, "onto_db")

    endpoint = _get(env, "DMO_GRAPHDB_ENDPOINT")
    repo = _get(env, "DMO_GRAPHDB_REPOSITORY")
    if not endpoint or not repo:
        # 兼容既有的 GRAPHDB_SPARQL_ENDPOINT=http://host:7200/repositories/<repo>
        legacy = _get(env, "DMO_GRAPHDB_ENDPOINT", default="http://localhost:7200/repositories/dmo")
        assert legacy is not None
        base, _, tail = legacy.partition("/repositories/")
        endpoint = endpoint or base
        repo = repo or (tail.strip("/") or "dmo")

    timeout_raw = _get(env, "DMO_GRAPHDB_TIMEOUT", default="30")
    assert timeout_raw is not None

    return Config(
        upstream_dsn=upstream,
        onto_dsn=onto,
        graphdb_endpoint=endpoint.rstrip("/"),
        graphdb_repository=repo,
        graphdb_timeout=int(timeout_raw),
    )
