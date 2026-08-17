"""GraphDB 客户端 —— 复用构建层的 HTTP 原语，只改错误处理策略。

构建层（`ontology/tools/`）是一次性脚本，出错就 `SystemExit` 最省事。
同步层不行：`dmo sync all` 跑 30 个患者，第 7 个失败必须记账后继续，
最后汇总非零退出，而不是当场把进程炸掉。所以这里做两件事：

  1. 把 `SystemExit` 翻译成 `GraphDBError`（可 catch 的普通异常）；
  2. 超时可配（构建层写死 120s）。

除此之外**一行请求逻辑都不重写** —— PUT 的 URL 拼法、SPARQL 的 Accept 头这些
坑已经在 load_graphdb.py 里踩平了，复制一份意味着以后要改两处。
"""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

from ..config import Config

# ontology/tools 不是包，按路径挂进 sys.path。
_TOOLS = Path(__file__).resolve().parents[3] / "ontology" / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import graphdb_http as _http


class GraphDBError(RuntimeError):
    """GraphDB 请求失败。与构建层的 SystemExit 区别开，便于 sync all 继续跑。"""


class GraphDBClient:
    def __init__(self, cfg: Config) -> None:
        self.endpoint = cfg.graphdb_endpoint
        self.repo = cfg.graphdb_repository
        self.timeout = cfg.graphdb_timeout

    def _wrap(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except SystemExit as e:  # 构建层的失败风格
            raise GraphDBError(str(e)) from e

    def exists(self) -> bool:
        return bool(self._wrap(_http.repo_exists, self.endpoint, self.repo))

    def size(self) -> int:
        code, body = self._wrap(
            _http.request, "GET", f"{self.endpoint}/repositories/{self.repo}/size",
            timeout=self.timeout,
        )
        if code != 200:
            raise GraphDBError(f"取仓库大小失败 HTTP {code}：{body[:200]}")
        return int(body.strip())

    def put_graph(self, graph_uri: str, ttl: str) -> None:
        self._wrap(_http.put_graph, self.endpoint, self.repo, graph_uri, ttl, False,
                   timeout=self.timeout)

    def drop_graph(self, graph_uri: str) -> None:
        self._wrap(_http.drop_graph, self.endpoint, self.repo, graph_uri, timeout=self.timeout)

    def sparql_csv(self, query: str) -> list[dict[str, str]]:
        raw = self._wrap(_http.sparql, self.endpoint, self.repo, query,
                         accept="text/csv", timeout=self.timeout)
        return list(csv.DictReader(io.StringIO(raw)))

    def sparql_json(self, query: str) -> dict:
        raw = self._wrap(_http.sparql, self.endpoint, self.repo, query,
                         accept="application/sparql-results+json", timeout=self.timeout)
        return json.loads(raw)

    def ask(self, query: str) -> bool:
        return bool(self.sparql_json(query).get("boolean"))

    def construct_ttl(self, query: str) -> str:
        return self._wrap(_http.sparql, self.endpoint, self.repo, query,
                          accept="text/turtle", timeout=self.timeout)

    def named_graphs(self) -> list[dict[str, str]]:
        return self.sparql_csv(
            "SELECT ?g (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } } "
            "GROUP BY ?g ORDER BY DESC(?n)"
        )
