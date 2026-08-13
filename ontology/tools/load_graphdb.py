#!/usr/bin/env python3
"""S4：建 GraphDB 仓库 + 按命名图幂等装载 + 验收查询。

    python3 ontology/tools/load_graphdb.py --create   # 建仓（已存在则跳过）
    python3 ontology/tools/load_graphdb.py --load     # 装载全部命名图
    python3 ontology/tools/load_graphdb.py --verify   # 只跑验收查询
    python3 ontology/tools/load_graphdb.py --dry-run --load

命名图布局见 docs/SEMANTIC-LAYER-PLAN.md §4.1。

两条硬规则：
  1. 用 PUT（整图替换）而不是 POST（追加）——构建必须幂等。
     推论：多个源文件指向同一个命名图时，必须**先在客户端合并再 PUT**，
     否则后一个文件会把前一个冲掉。
  2. 建仓时 validationEnabled=false。SHACL shapes 一旦进 shapes graph，
     之后每次写入都触发校验，批量导入会以一堆难读的错误炸掉。

只用标准库，不引入 httpx —— 构建层保持零额外依赖。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENDPOINT = "http://localhost:7200"
REPO_ID = "dmo"
VOCAB = "https://example.org/dmo#"

# 命名图 → 源文件列表。多个文件先合并再整图 PUT。
GRAPH_SOURCES: dict[str, list[Path]] = {
    "urn:dmo:tbox": [
        ROOT / "ontology" / "dist" / "tbox-generated.ttl",
        ROOT / "ontology" / "src" / "dmo-axioms.ttl",
    ],
    "urn:dmo:seed": [ROOT / "ontology" / "src" / "dmo-threshold-seed.ttl"],
    "urn:dmo:sources": [ROOT / "ontology" / "dist" / "sources.ttl"],
    "urn:dmo:data": [ROOT / "ontology" / "data" / "synthetic-patients.ttl"],
    # GraphDB 约定的 SHACL shapes 图。灌完数据再把 validationEnabled 打开。
    "http://rdf4j.org/schema/rdf4j#SHACLShapeGraph": [
        ROOT / "ontology" / "shapes" / "data-quality.shacl.ttl",
        ROOT / "ontology" / "shapes" / "clinical-safety.shacl.ttl",
    ],
}

EXTRACT_DIR = ROOT / "ontology" / "dist" / "extract"
RULES_DIR = ROOT / "ontology" / "rules"
INFERRED_GRAPH = "urn:dmo:inferred"


def repo_config(repo_id: str) -> dict:
    return {
        "id": repo_id,
        "title": "Diabetes Management Ontology",
        "type": "graphdb",
        # GraphDB 11 的建仓 API 要求每个参数都带 label —— 只给 name/value 会 400，
        # 而且报错文本用的是 label（"Missing parameter Default namespaces for imports"），
        # 很容易误以为是参数名写错了。
        "params": {
            # ⚠️ ruleset 建仓时定死，事后改要 reload 全部数据。一次选对。
            "ruleset": {
                "name": "ruleset",
                "label": "Ruleset",
                "value": "owl2-rl-optimized",
            },
            # 先关 SHACL，灌完数据再开（§4.2 坑 2）
            "validationEnabled": {
                "name": "validationEnabled",
                "label": "Enable the SHACL validation",
                "value": "false",
            },
            "disableSameAs": {
                "name": "disableSameAs",
                "label": "Disable owl:sameAs",
                "value": "true",
            },
            "baseURL": {"name": "baseURL", "label": "Base URL", "value": VOCAB},
            "imports": {
                "name": "imports",
                "label": "Imported RDF files(';' delimited)",
                "value": "",
            },
            "defaultNS": {
                "name": "defaultNS",
                "label": "Default namespaces for imports(';' delimited)",
                "value": "",
            },
        },
    }


# ─────────────────────────── HTTP ────────────────────────────────────


def request(
    method: str, url: str, *, data: bytes | None = None, headers: dict | None = None
) -> tuple[int, str]:
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        raise SystemExit(f"连不上 GraphDB（{url}）：{e.reason}\n先确认 GraphDB Desktop 在跑。")


def repo_exists(endpoint: str, repo_id: str) -> bool:
    code, body = request(
        "GET", f"{endpoint}/rest/repositories", headers={"Accept": "application/json"}
    )
    if code != 200:
        raise SystemExit(f"列仓库失败 HTTP {code}：{body[:200]}")
    return any(r.get("id") == repo_id for r in json.loads(body))


def create_repo(endpoint: str, repo_id: str, dry: bool) -> None:
    if repo_exists(endpoint, repo_id):
        print(f"• 仓库 {repo_id} 已存在，跳过建仓")
        return
    payload = json.dumps(repo_config(repo_id)).encode()
    if dry:
        print(f"[dry-run] POST {endpoint}/rest/repositories  ruleset=owl2-rl-optimized")
        return
    code, body = request(
        "POST",
        f"{endpoint}/rest/repositories",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    if code not in (200, 201, 204):
        raise SystemExit(f"建仓失败 HTTP {code}：{body[:400]}")
    print(f"✓ 已建仓 {repo_id}（ruleset=owl2-rl-optimized, SHACL 暂关）")


def put_graph(endpoint: str, repo_id: str, graph_uri: str, ttl: str, dry: bool) -> None:
    url = (
        f"{endpoint}/repositories/{repo_id}/rdf-graphs/service"
        f"?graph={urllib.parse.quote(graph_uri, safe='')}"
    )
    n = ttl.count("\n")
    if dry:
        print(f"[dry-run] PUT {graph_uri}  ({n} 行)")
        return
    code, body = request(
        "PUT", url, data=ttl.encode("utf-8"), headers={"Content-Type": "text/turtle"}
    )
    if code not in (200, 201, 204):
        raise SystemExit(f"PUT {graph_uri} 失败 HTTP {code}：{body[:400]}")
    print(f"✓ PUT {graph_uri}  ({n} 行)")


def sparql(endpoint: str, repo_id: str, query: str, accept: str = "text/csv") -> str:
    url = f"{endpoint}/repositories/{repo_id}"
    data = urllib.parse.urlencode({"query": query}).encode()
    code, body = request(
        "POST",
        url,
        data=data,
        headers={"Accept": accept, "Content-Type": "application/x-www-form-urlencoded"},
    )
    if code != 200:
        raise SystemExit(f"SPARQL 失败 HTTP {code}：{body[:400]}")
    return body


# ─────────────────────────── 装载 ────────────────────────────────────


def collect() -> dict[str, list[Path]]:
    """命名图 → 存在的源文件。抽取图按 dist/extract/<sid>/<sid>.ttl 约定发现。"""
    plan = {g: [p for p in ps if p.exists()] for g, ps in GRAPH_SOURCES.items()}
    if EXTRACT_DIR.is_dir():
        for d in sorted(EXTRACT_DIR.iterdir()):
            f = d / f"{d.name}.ttl"
            if f.exists():
                plan[f"urn:dmo:extract:{d.name}"] = [f]
    return {g: ps for g, ps in plan.items() if ps}


def merge(paths: list[Path]) -> str:
    """多文件合并成一个 Turtle 文档。前缀声明重复无害，Turtle 允许重复声明。"""
    parts = []
    for p in paths:
        parts.append(f"# ─── 来自 {p.relative_to(ROOT)} ───")
        parts.append(p.read_text(encoding="utf-8"))
    return "\n".join(parts)


def run_rules(endpoint: str, repo_id: str, dry: bool) -> None:
    """依次跑 rules/*.rq 的 CONSTRUCT，结果整图 PUT 进 urn:dmo:inferred。

    整图替换而非追加：规则改了重跑，不会留下上一版的残渣。
    """
    rqs = sorted(RULES_DIR.glob("*.rq")) if RULES_DIR.is_dir() else []
    if not rqs:
        print("• 没有 rules/*.rq，跳过")
        return
    chunks: list[str] = []
    for rq in rqs:
        ttl = sparql(endpoint, repo_id, rq.read_text(encoding="utf-8"), accept="text/turtle")
        n = sum(1 for line in ttl.splitlines() if line.strip().endswith("."))
        print(f"  {rq.name}: CONSTRUCT 出 ~{n} 条")
        chunks.append(f"# ─── {rq.name} ───\n{ttl}")
    merged = "\n".join(chunks)
    put_graph(endpoint, repo_id, INFERRED_GRAPH, merged, dry)


# ─────────────────────────── 验收 ────────────────────────────────────

PREFIXES = "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "

CHECKS: list[tuple[str, str, str]] = [
    (
        "各命名图三元组数",
        "SELECT ?g (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } } GROUP BY ?g ORDER BY DESC(?n)",
        "",
    ),
    (
        "TBox 类数量",
        "PREFIX owl: <http://www.w3.org/2002/07/owl#> "
        "SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE { GRAPH <urn:dmo:tbox> { ?c a owl:Class } }",
        "",
    ),
    (
        "推理机是否真的开着：传递闭包 CKD-G5 worseThan CKD-G2",
        "PREFIX dmo: <https://example.org/dmo#> "
        "PREFIX dmoid: <https://example.org/dmo/id/> "
        "ASK { dmoid:CKD-G5 dmo:worseThan dmoid:CKD-G2 }",
        "该三元组未被显式断言，只能由 owl2-rl 的 TransitiveProperty 推出",
    ),
    (
        "子类闭包 T1DM ⊑ Diabetes",
        "PREFIX dmo: <https://example.org/dmo#> "
        "PREFIX dmoid: <https://example.org/dmo/id/> "
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
        "ASK { dmoid:T1DM rdfs:subClassOf dmo:Diabetes }",
        "",
    ),
    (
        "抽取实体对齐到规范个体的条数",
        "PREFIX dmo: <https://example.org/dmo#> "
        "SELECT (COUNT(DISTINCT ?e) AS ?n) WHERE { GRAPH <urn:dmo:inferred> { ?e dmo:alignedTo ?c } }",
        "0 表示抽取图与公理图仍是孤岛（§8.1）",
    ),
    (
        "跨图连通：从抽取的 T2DM 走到公理层的 Diabetes",
        "PREFIX dmo: <https://example.org/dmo#> "
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
        "ASK { ?e dmo:alignedTo ?c . ?c rdfs:subClassOf dmo:Diabetes }",
        "对齐规则生效后，抽取产物才能吃到公理层的推理结果",
    ),
    (
        "S6 验收：用了绝对禁忌药物的患者",
        "PREFIX dmo: <https://example.org/dmo#> "
        "SELECT ?pid ?drug ?cond WHERE { "
        " ?p dmo:patientId ?pid ; dmo:takesMedication ?m ; dmo:hasComplication ?cond . "
        " ?m dmo:belongsToDrugClass ?c . ?c dmo:hasContraindication ?k . "
        " ?k dmo:severity 'Absolute' ; dmo:triggeredByCondition ?cond . "
        " ?c rdfs:label ?drug } ",
        "语料里唯一的明确禁令：SGLT2i + 重度肾病/透析。原计划的 eGFR<30 无出处，未采纳",
    ),
    (
        "⚠️ 反例：Prediabetes ⋢ Diabetes（应为 false）",
        "PREFIX dmo: <https://example.org/dmo#> "
        "PREFIX dmoid: <https://example.org/dmo/id/> "
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
        "ASK { dmoid:Prediabetes rdfs:subClassOf dmo:Diabetes }",
        "推出 true 说明本体已不一致（见 §2.5 的 hasKey 事故）",
    ),
]


def verify(endpoint: str, repo_id: str) -> int:
    failed = 0
    for title, q, note in CHECKS:
        if "PREFIX rdfs:" not in q:  # 已声明的别重复，GraphDB 会报 MALFORMED QUERY
            q = PREFIXES + q
        is_ask = "ASK" in q.upper().split()
        if is_ask:
            # ASK 返回布尔，text/csv 会被 GraphDB 拒成 406
            raw = sparql(endpoint, repo_id, q, accept="application/sparql-results+json")
            value = bool(json.loads(raw).get("boolean"))
            expected = not title.startswith("⚠️ 反例")
            ok = value is expected
            failed += 0 if ok else 1
            print(f"  {'✓' if ok else '✗'} {title} → {value}")
        else:
            print(f"  • {title}")
            for line in sparql(endpoint, repo_id, q).strip().splitlines():
                print(f"      {line}")
        if note:
            print(f"      ({note})")
    return failed


def main() -> int:
    ap = argparse.ArgumentParser(description="GraphDB 建仓 + 幂等装载 + 验收")
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--repo", default=REPO_ID)
    ap.add_argument("--create", action="store_true", help="建仓（已存在则跳过）")
    ap.add_argument("--load", action="store_true", help="按命名图整图 PUT")
    ap.add_argument("--rules", action="store_true", help="跑 rules/*.rq，结果进 urn:dmo:inferred")
    ap.add_argument("--verify", action="store_true", help="跑验收查询")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not (args.create or args.load or args.rules or args.verify):
        ap.error("至少给一个动作：--create / --load / --rules / --verify")

    if args.create:
        create_repo(args.endpoint, args.repo, args.dry_run)

    if args.load:
        plan = collect()
        if not plan:
            raise SystemExit("没有可装载的文件。先跑 build_tbox.py。")
        print(f"\n装载 {len(plan)} 个命名图：")
        for g, paths in plan.items():
            if len(paths) > 1:
                print(f"  ({len(paths)} 个文件先合并，因为 PUT 是整图替换)")
            put_graph(args.endpoint, args.repo, g, merge(paths), args.dry_run)
        missing = [
            str(p.relative_to(ROOT))
            for ps in GRAPH_SOURCES.values()
            for p in ps
            if not p.exists()
        ]
        if missing:
            print(f"\n• 尚未建、已跳过：{', '.join(missing)}")

    if args.rules:
        print("\n跑规则层：")
        run_rules(args.endpoint, args.repo, args.dry_run)

    if args.verify and not args.dry_run:
        print("\n验收查询：")
        failed = verify(args.endpoint, args.repo)
        if failed:
            print(f"\n✗ {failed} 项验收未通过", file=sys.stderr)
            return 1
        print("\n✓ 全部验收通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
