"""编号 .sql 迁移。故意做得很小。

不用 Alembic 的理由写在 001_schema_and_migration.sql 里：schema 我们独占、无 ORM，
Alembic 会让 schema 有两份定义，改一处忘一处就漂移。

三条规矩：
  1. 按文件名排序执行，已应用的跳过；
  2. 已应用文件的内容改了就**报错停下**，不是静默重跑 —— 线上 schema 和仓库里的
     SQL 不一致是最难查的一类问题，宁可当场炸；
  3. 每个文件在**一个事务**里跑完。半截的 DDL 比没跑更糟。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..config import Config
from .engine import onto_conn

DDL_DIR = Path(__file__).parent / "ddl"


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def discover() -> list[Path]:
    return sorted(DDL_DIR.glob("*.sql"))


def applied(cfg: Config) -> dict[str, str]:
    """已应用的 filename → checksum。首次运行时 sys_migration 还不存在。"""
    with onto_conn(cfg) as conn:
        exists = conn.scalar(
            "SELECT to_regclass('diabetes.sys_migration') IS NOT NULL"
        )
        if not exists:
            return {}
        return {
            r["filename"]: r["checksum"]
            for r in conn.fetchall("SELECT filename, checksum FROM diabetes.sys_migration")
        }


def run(cfg: Config, *, dry: bool = False) -> int:
    done = applied(cfg)
    files = discover()
    if not files:
        print(f"• {DDL_DIR} 下没有 .sql")
        return 0

    drift = []
    todo = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        chk = _checksum(text)
        if f.name in done:
            if done[f.name] != chk:
                drift.append(f.name)
        else:
            todo.append((f, text, chk))

    if drift:
        raise SystemExit(
            "✗ 这些迁移文件在应用之后被改过：\n"
            + "".join(f"    {n}\n" for n in drift)
            + "  线上 schema 与仓库里的 SQL 已经不一致。\n"
            "  正确做法是**新增**一个编号更大的迁移文件来改，而不是改历史文件。"
        )

    if not todo:
        print(f"✓ 已是最新（{len(done)} 个迁移全部应用过）")
        return 0

    for f, text, chk in todo:
        if dry:
            print(f"[dry-run] 将应用 {f.name}（{len(text)} 字符）")
            continue
        # 每个文件一个事务：autocommit=False 时 psycopg 隐式开事务，
        # with 块正常退出即 COMMIT，异常则 ROLLBACK。
        with onto_conn(cfg) as conn:
            conn.execute(text)
            conn.execute(
                "INSERT INTO diabetes.sys_migration (filename, checksum) VALUES (%s, %s)",
                (f.name, chk),
            )
            conn.commit()
        print(f"✓ 应用 {f.name}")
    return 0
