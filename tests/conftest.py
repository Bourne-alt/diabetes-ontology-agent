"""测试夹具。

这些测试**打真实的 PG 与 GraphDB**，不是单元测试。理由：本项目要验证的
恰恰是「本体 + 真实数据 + 推理机」三者合在一起的行为，而这三者的坑
（owl2-rl 的 domain 反推、GraphDB 不写 GRAPH 才能吃到物化边、
子查询里 OPTIONAL 导致患者丢失）**全部**只在集成层面暴露，mock 掉就全看不见了。

前置：
    uv run dmo db migrate && uv run dmo etl pull && uv run dmo db baseline
    uv run dmo map sync-concepts && uv run dmo map load-terms && uv run dmo db seed
    uv run dmo project run && uv run dmo sync all
    python3 ontology/tools/load_graphdb.py --rules
    uv run dmo predict run

连不上就 skip 整个模块，而不是失败 —— 环境没起来不等于代码错了。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dmo import config as config_mod


@pytest.fixture(scope="session")
def cfg():
    return config_mod.load()


@pytest.fixture(scope="session")
def graph(cfg):
    from dmo.graph.client import GraphDBClient, GraphDBError

    client = GraphDBClient(cfg)
    try:
        if not client.exists():
            pytest.skip(f"GraphDB 仓库 {cfg.graphdb_repository} 不存在")
    except GraphDBError as e:
        pytest.skip(f"连不上 GraphDB：{e}")
    return client


@pytest.fixture(scope="session")
def db(cfg):
    from dmo.db.engine import onto_conn

    try:
        with onto_conn(cfg) as conn:
            if not conn.scalar("SELECT to_regclass('diabetes.core_patient') IS NOT NULL"):
                pytest.skip("diabetes.core_patient 不存在，先跑 dmo db migrate + project run")
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"连不上 onto_db：{e}")
    return cfg


PREFIX = "PREFIX dmo: <https://example.org/dmo#>\n"


@pytest.fixture(scope="session")
def ask(graph):
    def _ask(body: str) -> list[dict[str, str]]:
        return graph.sparql_csv(PREFIX + body)

    return _ask
