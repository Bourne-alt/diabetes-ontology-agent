-- 001 · schema 骨架、迁移登记、上游基线
--
-- 所有对象都建在 diabetes schema 下。engine.py 的守卫保证没有别的 schema 会被碰到。

CREATE SCHEMA IF NOT EXISTS diabetes;

-- ── 迁移登记 ────────────────────────────────────────────────────────
-- 不用 Alembic：schema 我们独占、无 ORM，Alembic 会让 schema 有两份定义
--（SQL 一份、迁移脚本一份），改一处忘一处就漂移。编号 .sql + 本表足够。
CREATE TABLE IF NOT EXISTS diabetes.sys_migration (
    filename    text PRIMARY KEY,
    checksum    text        NOT NULL,   -- sha256(文件内容)
    applied_at  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON COLUMN diabetes.sys_migration.checksum IS
    '已应用文件的内容哈希。改动已应用的迁移文件会被 migrate.py 拒绝 —— '
    '不然线上 schema 和仓库里的 SQL 会静默不一致。';

-- ── 上游基线 ────────────────────────────────────────────────────────
-- 「不动原数据」的第三道锁。每次 etl pull 前重算比对，不一致直接拒跑。
-- 它同时也是**上游被别人改了**的探测器：我们不写上游，但别人可能写。
CREATE TABLE IF NOT EXISTS diabetes.sys_upstream_baseline (
    table_name    text        PRIMARY KEY,
    row_count     bigint      NOT NULL,
    content_md5   text        NOT NULL,
    captured_at   timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE diabetes.sys_upstream_baseline IS
    'hospital_zd.patient_analysis 关键表的行数 + 内容指纹。'
    'content_md5 = md5(string_agg(整行文本, char(10) ORDER BY 整行文本))，'
    '与列顺序有关、与物理行序无关。';
