"""「不动原数据」的第三道锁：上游内容指纹。

前两道锁（物理隔离、语句守卫）保证**我们**不写上游。这一道回答另一个问题：
**上游被别人改了没有？** 如果改了，我们基于旧快照算出来的结论就已经过期，
继续跑只会产出看起来正常、实际对不上的答案。

指纹口径：
    row_count   = count(*)
    content_md5 = md5(string_agg(整行::text, E'\\n' ORDER BY 整行::text))

用整行 `t::text` 而不是逐列拼接：列改名/加列都会让指纹变，这是想要的行为 ——
schema 变了，我们的白名单就可能漏列。ORDER BY 整行文本让指纹与物理行序无关。

⚠️ 这不是防篡改，是防意外。有权限的人可以既改数据又改基线。
   它防的是「别人跑了个 ETL 往这个库里补了 300 条，而我们毫不知情」。
"""

from __future__ import annotations

from psycopg import sql

from ..config import Config
from .engine import onto_conn, upstream_conn
from .etl import SPECS

# 除了要拉的 6 张，再盯 3 张不拉但会影响解读的表。
WATCHED: tuple[str, ...] = tuple(
    dict.fromkeys(
        [s.upstream for s in SPECS]
        + ["patientid_to_inpatientno", "ip_order_query", "patient_id"]
    )
)


def fingerprint(cfg: Config) -> dict[str, tuple[int, str]]:
    out: dict[str, tuple[int, str]] = {}
    with upstream_conn(cfg) as up:
        for t in WATCHED:
            exists = up.scalar(
                "SELECT to_regclass(%s) IS NOT NULL", (f"patient_analysis.{t}",)
            )
            if not exists:
                continue
            row = up.fetchone(
                sql.SQL(
                    "SELECT count(*) AS n, "
                    # x::text 把**整行**转成文本。列改名/加列都会让指纹变 —— 这是想要的：
                    # schema 变了，etl.py 的列白名单就可能漏列。
                    "coalesce(md5(string_agg(x::text, chr(10) ORDER BY x::text)), '') AS h "
                    "FROM patient_analysis.{t} x"
                ).format(t=sql.Identifier(t))
            )
            assert row is not None
            out[t] = (int(row["n"]), str(row["h"]))
    return out


def capture(cfg: Config) -> int:
    fp = fingerprint(cfg)
    with onto_conn(cfg) as conn:
        for t, (n, h) in fp.items():
            conn.execute(
                """
                INSERT INTO diabetes.sys_upstream_baseline (table_name, row_count, content_md5)
                VALUES (%s, %s, %s)
                ON CONFLICT (table_name) DO UPDATE
                  SET row_count = EXCLUDED.row_count,
                      content_md5 = EXCLUDED.content_md5,
                      captured_at = now()
                """,
                (t, n, h),
            )
        conn.commit()
    print(f"✓ 已记录 {len(fp)} 张上游表的基线：")
    for t, (n, h) in sorted(fp.items()):
        print(f"    {t:<28} {n:>6} 行  md5={h[:12]}…")
    return 0


def check(cfg: Config, *, quiet: bool = False) -> int:
    """比对当前指纹与基线。不一致返回 1。

    `dmo etl pull` 与 `dmo project run` 之前都会调它 —— 上游变了就拒跑，
    而不是拿着过期快照继续算。
    """
    with onto_conn(cfg) as conn:
        stored = {
            r["table_name"]: (int(r["row_count"]), r["content_md5"])
            for r in conn.fetchall(
                "SELECT table_name, row_count, content_md5 FROM diabetes.sys_upstream_baseline"
            )
        }
    if not stored:
        print("• 还没有基线。先跑 `dmo db baseline` 记一份。")
        return 1

    now = fingerprint(cfg)
    drift = []
    for t, (n, h) in sorted(now.items()):
        if t not in stored:
            drift.append(f"{t}: 基线里没有这张表（新表？）")
            continue
        sn, sh = stored[t]
        if sn != n or sh != h:
            drift.append(f"{t}: 基线 {sn} 行/{sh[:8]}… → 现在 {n} 行/{h[:8]}…")
    for t in stored:
        if t not in now:
            drift.append(f"{t}: 基线里有，上游现在查不到（表被删/改名？）")

    if drift:
        print("✗ 上游已变，与基线不一致：", *(f"    {d}" for d in drift), sep="\n")
        print("\n  确认变化是预期的之后，跑 `dmo db baseline` 重记基线，再继续。")
        return 1
    if not quiet:
        print(f"✓ 上游与基线一致（{len(now)} 张表）")
    return 0
