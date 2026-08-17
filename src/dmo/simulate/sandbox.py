"""推演沙箱 —— 把患者图与知识层拉进**内存** rdflib Dataset。

## 为什么不在 GraphDB 里建临时图

最直觉的做法是 `urn:dmo:sandbox:<uuid>` 建图、跑规则、删图。三个理由否掉了它：

  1. **规则读不到。** 所有规则的患者侧都写死 `STRSTARTS(STR(?pg), "urn:dmo:patient:")`
     （见 rules/20-lab-assessment.rq:60）。sandbox 图想被规则看见，就得叫
     `urn:dmo:patient:*` —— 那它同时会被 predict.py 的全库扫描、被
     templates.py 的 PG_GUARD 全部扫到，假设数据当场变成"真患者"。
  2. **删除失败是永久污染。** 建了再删依赖清理一定成功。进程被 kill、
     网络断在中间，假设事实就永远留在真实图里，而且长得和真事实一模一样。
  3. 与本仓库既有的隔离哲学不一致 —— 写保护做成**物理性质**（写连接的 DSN
     根本不指向 hospital_zd），而不是"记得清理"。

内存方案没有写路径：GraphDB 连接全程只发 CONSTRUCT。推演跑多少次，
库里三元组数一条都不会变（tests/test_simulate.py 有断言盯着）。

## 知识层快照为什么是「全库 − 患者图 − inferred 图」

减患者图：患者事实按 pid 单独拉，全拉进来就是 430 个患者互相串味。

减 inferred 图：sandbox 要**自己重跑**规则链。带着上一轮的结论进去，
diff 出来的"新增结论"里会混进旧结果，而且 30 号规则会把上一轮的
Assessment 当成本轮证据 —— 单次检验会凭空变成"两个日期"。

减 `urn:dmo:data`：那是 synthetic-patients.ttl 的**反例夹具**（P001 肾衰竭+SGLT2i、
P005 缺单位、P006 单位写错），故意造错的数据。它不带 `urn:dmo:patient:` 前缀，
不显式排除就会混进知识层，把 6 个夹具患者的诊断算进每一次推演的结论集里。
templates.py 的 PG_GUARD 防的是同一件事。

不减物化边：owl2-rl 物化的 2.8 万条三元组不属于任何命名图。
规则的知识侧**刻意不写 GRAPH** 就是为了吃到它们（rules/20 的 ⚠️ 第二条）。
所以快照必须从 default union graph 取，而不是逐个命名图拼。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from rdflib import Dataset, URIRef

from ..config import Config
from ..graph.client import GraphDBClient, GraphDBError
from ..rdf import iri as I

# 推演产物落在这个图里。名字**刻意不带** "urn:dmo:patient:" 前缀 ——
# 它是结论不是事实，混进患者图会被下一轮规则当成断言事实读走。
INFERRED_GRAPH = URIRef("urn:dmo:inferred")

CACHE_DIR = Path(__file__).resolve().parents[3] / "ontology" / "dist" / ".sandbox-cache"

_KNOWLEDGE_Q = """
CONSTRUCT { ?s ?p ?o }
WHERE {
  ?s ?p ?o
  FILTER NOT EXISTS {
    GRAPH ?g { ?s ?p ?o }
    FILTER(STRSTARTS(STR(?g), "urn:dmo:patient:")
           || STR(?g) = "urn:dmo:inferred"
           || STR(?g) = "urn:dmo:data")
  }
}
"""

_PATIENT_Q = "CONSTRUCT {{ ?s ?p ?o }} WHERE {{ GRAPH <{pg}> {{ ?s ?p ?o }} }}"

_PID_Q = """
PREFIX dmo: <https://example.org/dmo#>
SELECT ?g WHERE {{
  GRAPH ?g {{ ?p dmo:patientId "{pid}" }}
  FILTER(STRSTARTS(STR(?g), "urn:dmo:patient:"))
}}
"""


class SandboxError(RuntimeError):
    """沙箱构建失败。与 GraphDBError 区别开 —— 这一层的失败都是可解释的业务失败。"""


@dataclass(frozen=True)
class Snapshot:
    """一次推演的全部输入。**不可变** —— derivationHash 依赖它逐字节稳定。"""

    pid: str
    patient_iri: str
    patient_graph: str
    patient_ttl: str
    knowledge_ttl: str
    knowledge_sha: str

    def dataset(self) -> Dataset:
        """每次调用**新建**一个 Dataset。绝不复用 —— 基线与假设后必须互不可见。

        `default_union=True` 是复刻 GraphDB 语义的关键，不是性能开关：
        规则的知识侧**刻意不写 GRAPH**，在 GraphDB 里那匹配的是 default union
        graph（所有命名图 + owl2-rl 物化边）。rdflib 默认 `default_union=False`，
        不带 GRAPH 的模式只匹配 default graph —— 于是 `?test dmo:hasThreshold ?th`
        之类的知识侧模式照常命中，而 `?pat dmo:patientId ?pid` 这种落在患者
        命名图里的断言全部匹配不上，规则链静默推出空集。
        """
        ds = Dataset(default_union=True)
        ds.graph(URIRef(self.patient_graph)).parse(
            data=self.patient_ttl, format="turtle")
        ds.default_graph.parse(data=self.knowledge_ttl, format="turtle")
        return ds


def _cache_path(version: str) -> Path:
    return CACHE_DIR / f"knowledge-{version[:16]}.ttl"


def knowledge_snapshot(cfg: Config, *, version: str, refresh: bool = False) -> str:
    """知识层快照。按 graphVersion 缓存 —— 5.6MB / 1.6s，每次推演都拉太浪费。

    缓存键用 graphVersion（知识层源文件的内容哈希）：本体改了就自动失效。
    ⚠️ 它盯的是**源文件**，不是 GraphDB 里的内容。手工往库里灌过东西的话，
    用 refresh=True 强制重取。
    """
    path = _cache_path(version)
    if not refresh and path.exists():
        return path.read_text(encoding="utf-8")
    try:
        ttl = GraphDBClient(cfg).construct_ttl(_KNOWLEDGE_Q)
    except GraphDBError as e:
        raise SandboxError(f"拉知识层快照失败：{e}") from e
    if not ttl.strip():
        raise SandboxError(
            "知识层快照是空的。GraphDB 里可能还没装载本体 —— "
            "先跑 python3 ontology/tools/load_graphdb.py --load")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(ttl, encoding="utf-8")
    return ttl


def resolve_patient_graph(cfg: Config, pid: str) -> tuple[str, str]:
    """pid → (患者 IRI, 命名图名)。

    IRI 本可以由 iri.patient_iri(pid) 直接铸出来，但这里**先查一次库**：
    铸得出 IRI 不代表图里真有这个患者。查不到就当场报错，
    而不是让后面的规则在空图上跑出一个"什么都没推出来"的假结论。
    """
    try:
        rows = GraphDBClient(cfg).sparql_csv(_PID_Q.format(pid=pid))
    except GraphDBError as e:
        raise SandboxError(f"解析患者图失败：{e}") from e
    if not rows:
        expected = I.patient_graph(pid)
        raise SandboxError(
            f"GraphDB 里没有患者 {pid}（期望命名图 {expected}）。"
            f"先跑 uv run dmo sync --patient {pid}")
    if len(rows) > 1:
        graphs = ", ".join(r["g"] for r in rows)
        raise SandboxError(
            f"患者 {pid} 出现在 {len(rows)} 个命名图里：{graphs}。"
            "每患者一图的约定被破坏了，推演结果无法归因，拒绝继续。")
    return I.patient_iri(pid), rows[0]["g"]


def load(cfg: Config, pid: str, *, refresh: bool = False) -> Snapshot:
    """组装一次推演所需的全部输入。只发 CONSTRUCT，**不写 GraphDB 一个字节**。"""
    from ..terms.concepts import graph_version

    version = graph_version()
    patient_iri, pg = resolve_patient_graph(cfg, pid)
    try:
        patient_ttl = GraphDBClient(cfg).construct_ttl(_PATIENT_Q.format(pg=pg))
    except GraphDBError as e:
        raise SandboxError(f"拉患者图失败：{e}") from e
    if not patient_ttl.strip():
        raise SandboxError(f"患者 {pid} 的命名图 {pg} 是空的，没有可推演的事实。")

    knowledge_ttl = knowledge_snapshot(cfg, version=version, refresh=refresh)
    return Snapshot(
        pid=pid,
        patient_iri=patient_iri,
        patient_graph=pg,
        patient_ttl=patient_ttl,
        knowledge_ttl=knowledge_ttl,
        knowledge_sha=hashlib.sha256(knowledge_ttl.encode("utf-8")).hexdigest(),
    )
