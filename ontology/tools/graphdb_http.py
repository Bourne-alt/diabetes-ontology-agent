#!/usr/bin/env python3
"""GraphDB HTTP 原语 —— 构建层（load_graphdb.py）与同步层（src/dmo/graph/）共用。

从 load_graphdb.py 抽出来的，行为逐字不变，只加了两个参数：

  * `timeout` —— 原来写死 120s。患者图同步一次几十个图，需要更短的超时快速失败。
  * `drop_graph()` —— 新增。`dmo sync --prune` 要删已登记但 SQL 中已不存在的患者图。

**只用标准库**，不引入 httpx —— 构建层零额外依赖的约定延续到这里。

失败风格保持 `SystemExit`：构建层一次性脚本靠它给出人话报错。同步层不能被炸掉，
在 `src/dmo/graph/client.py` 里统一翻译成可 catch 的 `GraphDBError`。
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_TIMEOUT = 120


def request(
    method: str,
    url: str,
    *,
    data: bytes | None = None,
    headers: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[int, str]:
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        raise SystemExit(f"连不上 GraphDB（{url}）：{e.reason}\n先确认 GraphDB Desktop 在跑。")


def repo_exists(endpoint: str, repo_id: str, *, timeout: int = DEFAULT_TIMEOUT) -> bool:
    import json

    code, body = request(
        "GET",
        f"{endpoint}/rest/repositories",
        headers={"Accept": "application/json"},
        timeout=timeout,
    )
    if code != 200:
        raise SystemExit(f"列仓库失败 HTTP {code}：{body[:200]}")
    return any(r.get("id") == repo_id for r in json.loads(body))


def _graph_url(endpoint: str, repo_id: str, graph_uri: str) -> str:
    return (
        f"{endpoint}/repositories/{repo_id}/rdf-graphs/service"
        f"?graph={urllib.parse.quote(graph_uri, safe='')}"
    )


def put_graph(
    endpoint: str,
    repo_id: str,
    graph_uri: str,
    ttl: str,
    dry: bool = False,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    quiet: bool = False,
) -> None:
    """整图替换。**PUT 而不是 POST** —— 构建与同步都必须幂等。

    推论：多个源文件指向同一个命名图时，必须先在客户端 merge() 再 PUT，
    否则后一个文件会把前一个冲掉。
    """
    n = ttl.count("\n")
    if dry:
        print(f"[dry-run] PUT {graph_uri}  ({n} 行)")
        return
    code, body = request(
        "PUT",
        _graph_url(endpoint, repo_id, graph_uri),
        data=ttl.encode("utf-8"),
        headers={"Content-Type": "text/turtle"},
        timeout=timeout,
    )
    if code not in (200, 201, 204):
        raise SystemExit(f"PUT {graph_uri} 失败 HTTP {code}：{body[:400]}")
    if not quiet:
        print(f"✓ PUT {graph_uri}  ({n} 行)")


def drop_graph(
    endpoint: str, repo_id: str, graph_uri: str, *, timeout: int = DEFAULT_TIMEOUT
) -> None:
    """删整个命名图。图不存在时 GraphDB 也返回 204，视为成功（幂等）。"""
    code, body = request(
        "DELETE", _graph_url(endpoint, repo_id, graph_uri), timeout=timeout
    )
    if code not in (200, 204, 404):
        raise SystemExit(f"DELETE {graph_uri} 失败 HTTP {code}：{body[:400]}")


# clear_graph 是 drop_graph 的别名，只为让调用点读起来是"清空"而不是"删除"。
clear_graph = drop_graph


def append_graph(
    endpoint: str,
    repo_id: str,
    graph_uri: str,
    ttl: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
) -> None:
    """POST 追加到命名图。

    ⚠️ 只有一个正当用途：**规则层逐条物化**。规则之间有依赖（30 读 20 的产出、
    51 读 40/50 的产出），必须跑完一条就写进去，下一条才看得见。
    调用方负责先 clear_graph 保证幂等 —— 只追加不清空的话，图会单调增长。
    其余所有场景一律用 put_graph（整图替换）。
    """
    code, body = request(
        "POST",
        _graph_url(endpoint, repo_id, graph_uri),
        data=ttl.encode("utf-8"),
        headers={"Content-Type": "text/turtle"},
        timeout=timeout,
    )
    if code not in (200, 201, 204):
        raise SystemExit(f"POST {graph_uri} 失败 HTTP {code}：{body[:400]}")


def sparql(
    endpoint: str,
    repo_id: str,
    query: str,
    accept: str = "text/csv",
    *,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    url = f"{endpoint}/repositories/{repo_id}"
    data = urllib.parse.urlencode({"query": query}).encode()
    code, body = request(
        "POST",
        url,
        data=data,
        headers={"Accept": accept, "Content-Type": "application/x-www-form-urlencoded"},
        timeout=timeout,
    )
    if code != 200:
        raise SystemExit(f"SPARQL 失败 HTTP {code}：{body[:400]}")
    return body


def merge(paths: list[Path], root: Path | None = None) -> str:
    """多文件合并成一个 Turtle 文档。前缀声明重复无害，Turtle 允许重复声明。"""
    parts = []
    for p in paths:
        label = p.relative_to(root) if root else p.name
        parts.append(f"# ─── 来自 {label} ───")
        parts.append(p.read_text(encoding="utf-8"))
    return "\n".join(parts)
