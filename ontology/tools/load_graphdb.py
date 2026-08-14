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
from pathlib import Path

# HTTP 原语抽到 graphdb_http.py，与 src/dmo/graph/client.py 共用。
# 这里 import 而不是各留一份 —— PUT 的 URL 拼法、SPARQL 的 Accept 头这些坑
# 已经踩平了，复制一份意味着以后要改两处。
from graphdb_http import merge as _merge
from graphdb_http import (
    append_graph,
    clear_graph,
    put_graph,
    repo_exists,
    request,
    sparql,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENDPOINT = "http://124.223.18.44:7200"
REPO_ID = "dmo"
VOCAB = "https://example.org/dmo#"

# 命名图 → 源文件列表。多个文件先合并再整图 PUT。
GRAPH_SOURCES: dict[str, list[Path]] = {
    "urn:dmo:tbox": [
        ROOT / "ontology" / "dist" / "tbox-v2.ttl",
        ROOT / "ontology" / "src" / "dmo-axioms.ttl",
    ],
    "urn:dmo:seed": [
        ROOT / "ontology" / "src" / "dmo-threshold-seed.ttl",
        # 风险因子桥。放 seed 而不是单开一图：它和阈值一样是「人工策展的高危常量」，
        # 查询侧一律按「知识层不写 GRAPH」来写，多一个图只会多一次记错图名的机会。
        ROOT / "ontology" / "src" / "dmo-risk-map.ttl",
    ],
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
# request / repo_exists / put_graph / sparql / merge 见 graphdb_http.py


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


# ─────────────────────────── 装载 ────────────────────────────────────


def collect() -> dict[str, list[Path]]:
    """命名图 → 存在的源文件。抽取图按 dist/extract/<sid>/<sid>.ttl 约定发现。

    ⚠️ 缺文件**显式 WARN**，不静默跳过。上一次 `ontology/data/` 被误删时，
    这里的 `.exists()` 静默过滤让装载"成功"了，而 GraphDB 里 `urn:dmo:data`
    的 77 条其实是上一轮的残留 —— 图看着是对的，实际已经和磁盘脱节。
    """
    plan: dict[str, list[Path]] = {}
    for g, ps in GRAPH_SOURCES.items():
        present = [p for p in ps if p.exists()]
        for p in ps:
            if not p.exists():
                print(f"⚠️  {g} 的源文件缺失，已跳过：{p.relative_to(ROOT)}", file=sys.stderr)
        if present:
            plan[g] = present
        else:
            print(f"⚠️  {g} 无任何可用源文件，该图本次不会被更新（可能残留旧数据）",
                  file=sys.stderr)

    if EXTRACT_DIR.is_dir():
        for d in sorted(EXTRACT_DIR.iterdir()):
            if not d.is_dir():
                continue
            f = d / f"{d.name}.ttl"
            if f.exists():
                plan[f"urn:dmo:extract:{d.name}"] = [f]
            else:
                print(f"⚠️  抽取目录 {d.name} 下没有 {d.name}.ttl，跳过", file=sys.stderr)
    else:
        print(f"⚠️  抽取目录不存在：{EXTRACT_DIR.relative_to(ROOT)}", file=sys.stderr)
    return plan


def merge(paths: list[Path]) -> str:
    return _merge(paths, ROOT)


def run_rules(endpoint: str, repo_id: str, dry: bool, include_unreliable: bool = False) -> None:
    """依次跑 rules/*.rq 的 CONSTRUCT，结果整图 PUT 进 urn:dmo:inferred。

    整图替换而非追加：规则改了重跑，不会留下上一版的残渣。

    ⚠️ `*-unreliable.rq` **默认不跑**。它们处理 valueTrustLevel="Unverified" 的
    上游随机值，结论强制 Indeterminate。默认跑的话，1300+ 条随机检验会在
    urn:dmo:inferred 里生成同样多的 Assessment —— 淹没真正有意义的结论，
    而且让「不可信值默认不参与判定」这条设计在图层面失效。
    要看它们能推出什么，显式加 --include-unreliable。
    """
    all_rqs = sorted(RULES_DIR.glob("*.rq")) if RULES_DIR.is_dir() else []
    rqs = [p for p in all_rqs
           if include_unreliable or not p.stem.endswith("-unreliable")]
    skipped = [p.name for p in all_rqs if p not in rqs]
    if skipped:
        print(f"• 跳过（需 --include-unreliable）：{', '.join(skipped)}")
    if not rqs:
        print("• 没有 rules/*.rq，跳过")
        return

    if dry:
        for rq in rqs:
            print(f"[dry-run] 将执行 {rq.name}")
        return

    # ⚠️ 规则之间**有依赖**，必须逐条物化，不能攒到最后一起 PUT。
    #   30-diagnosis 读 20-lab-assessment 产出的 Assessment；
    #   51-risk-stratification 读 40 与 50 的产出。
    #   攒到最后 PUT 的话，30 查到的是**上一轮**的推断图 —— 首次跑必然空，
    #   而且不报任何错，只是"这条规则没推出东西"。数字前缀在这里必须真的生效。
    #
    #   做法：先清空整图，然后每跑完一条就 POST 追加。先清空保证幂等
    #   （不会留上一版残渣），逐条追加保证后面的规则看得见前面的结果。
    clear_graph(endpoint, repo_id, INFERRED_GRAPH)
    total = 0
    for rq in rqs:
        ttl = sparql(endpoint, repo_id, rq.read_text(encoding="utf-8"), accept="text/turtle")
        n = sum(1 for line in ttl.splitlines() if line.strip().endswith("."))
        total += n
        print(f"  {rq.name}: CONSTRUCT 出 ~{n} 条")
        if n:
            append_graph(endpoint, repo_id, INFERRED_GRAPH, ttl)
    print(f"✓ {INFERRED_GRAPH} 共 ~{total} 条（逐条物化，后续规则可见前序结果）")


# ─────────────────────────── 验收 ────────────────────────────────────

PREFIXES = "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "

# 每项：(标题, 查询, 说明[, 断言])
#   断言 = (变量名, 期望整数)。给了就必须相等，否则计入失败。
#   不给就只打印结果 —— 用于「看一眼」型的检查（如各图三元组数）。
# ASK 查询不需要断言：期望值由标题是否以「⚠️ 反例」开头决定。
CHECKS: list[tuple] = [
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
        # ⚠️ V2 改写：V1 的 takesMedication / hasComplication 已被 care-chain 取代。
        # 沿用旧谓词的话这条查询永远返回空 —— 而空结果看起来和「没有违规」一模一样，
        # 是最危险的一种静默失败。
        "S6 验收：用了绝对禁忌药物的患者（V2 七跳）",
        "PREFIX dmo: <https://example.org/dmo#> "
        "SELECT ?pid ?drug ?cond WHERE { "
        " ?p dmo:patientId ?pid ; dmo:hasMedicationUse ?mu ; dmo:hasDiagnosis ?dx . "
        " ?mu dmo:usesMedication ?m . "
        " ?m dmo:belongsToDrugClass ?c . "
        " ?c dmo:hasContraindication ?k ; rdfs:label ?drug . "
        " ?k dmo:severity 'Absolute' ; dmo:triggeredByCondition ?cond . "
        " ?dx dmo:clinicalStatus 'Active' ; dmo:diagnosisComplication ?cond } ",
        "语料里唯一可自动判定的禁令：SGLT2i + 重度肾病/透析。"
        "二甲双胍的 eGFR<30 无出处未采纳；bromocriptine+哺乳有原文但触发条件是生理状态，"
        "schema 表达不了，故不在此列",
    ),
    (
        "⚠️ 反例：Prediabetes ⋢ Diabetes（应为 false）",
        "PREFIX dmo: <https://example.org/dmo#> "
        "PREFIX dmoid: <https://example.org/dmo/id/> "
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
        "ASK { dmoid:Prediabetes rdfs:subClassOf dmo:Diabetes }",
        "推出 true 说明本体已不一致（见 §2.5 的 hasKey 事故）",
    ),
    # ── V2 切换后新增的三条 ──────────────────────────────────────────
    (
        "V2 care-chain 五类是否齐全（应为 5）",
        "PREFIX owl: <http://www.w3.org/2002/07/owl#> "
        "PREFIX dmo: <https://example.org/dmo#> "
        "SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE { "
        " VALUES ?c { dmo:Assessment dmo:Diagnosis dmo:MedicationUse "
        "             dmo:ClinicalObservation dmo:SourcePassage } "
        " GRAPH <urn:dmo:tbox> { ?c a owl:Class } }",
        "少于 5 说明装的还是 V1 TBox，患者事实无处落地",
        ("n", 5),
    ),
    (
        "每条诊断阈值都有出处片段（缺出处的应为 0）",
        "PREFIX dmo: <https://example.org/dmo#> "
        "SELECT (COUNT(DISTINCT ?t) AS ?n_missing) WHERE { "
        " ?t a dmo:DiagnosticThreshold . "
        " FILTER NOT EXISTS { ?t dmo:thresholdCitesPassage ?p . ?p dmo:contentHash ?h } }",
        "非 0 说明有阈值的出处链断了 —— 这类阈值不该参与任何判定",
        ("n_missing", 0),
    ),
    (
        "⚠️ 风险规则指向的抽取个体是否都还在（悬空的应为 0）",
        "PREFIX dmo: <https://example.org/dmo#> "
        "SELECT (COUNT(*) AS ?n_dangling) WHERE { "
        " ?r a dmo:RiskRule ; dmo:mapsToRiskFactor ?rf . "
        " FILTER NOT EXISTS { ?rf a dmo:RiskFactor } }",
        "dmo-risk-map.ttl 跨图引用 urn:dmo:extract:* 的 IRI。抽取产物重跑后 IRI 会变，"
        "悬空引用不报错、只是规则静默失效 —— 这条检查就是盯这个",
        ("n_dangling", 0),
    ),
]


def verify(endpoint: str, repo_id: str) -> int:
    failed = 0
    for check in CHECKS:
        title, q, note = check[0], check[1], check[2]
        assertion = check[3] if len(check) > 3 else None
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
        elif assertion:
            # 有断言的 SELECT：结果必须等于期望值，否则算失败。
            # 之前所有 SELECT 都只打印，于是「数量对不对」这类检查形同虚设。
            var, want = assertion
            raw = sparql(endpoint, repo_id, q, accept="application/sparql-results+json")
            bindings = json.loads(raw).get("results", {}).get("bindings", [])
            got = int(bindings[0][var]["value"]) if bindings and var in bindings[0] else 0
            ok = got == want
            failed += 0 if ok else 1
            print(f"  {'✓' if ok else '✗'} {title} → {var}={got}（期望 {want}）")
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
    ap.add_argument("--include-unreliable", action="store_true",
                    help="连 *-unreliable.rq 一起跑（处理 Unverified 值，结论强制 Indeterminate）")
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
        # 缺文件已在 collect() 里逐条 WARN 到 stderr，这里不再重复列一遍。

    if args.rules:
        print("\n跑规则层：")
        run_rules(args.endpoint, args.repo, args.dry_run, args.include_unreliable)

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
