"""dmo CLI —— pyproject 的 `dmo` 入口。

子命令按数据流向组织，与 plan 的里程碑一一对应：

    db      骨架、迁移、演示队列、守卫自测、基线      R0/R2/R4
    etl     hospital_zd → onto_db.diabetes.stg_*      R2
    map     术语对齐                                   R3
    project stg_ + sim_ → core_                        R5
    sync    core_ → GraphDB 每患者一命名图             R5
    graph   仓库状态 / 装载 / 规则                      R1/R6
    predict 规则结果 → pred_*                          R6
    query   参数化模板                                  R7
    ask     agent 编排                                  R7
    serve   FastAPI                                     R7

未实现的子命令**显式报错并说明属于哪个里程碑**，不假装成功。
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from . import config as config_mod


class NotYetImplemented(SystemExit):
    def __init__(self, milestone: str, what: str) -> None:
        super().__init__(f"『{what}』属于 {milestone}，尚未实现。")


# ─────────────────────────── db ──────────────────────────────────────


def cmd_db_status(args: argparse.Namespace) -> int:
    from .db import engine

    cfg = config_mod.load()
    print("配置：")
    print(cfg.describe())

    info = engine.ping(cfg)
    print("\n上游 hospital_zd：")
    print(f"  {info['upstream_version'].split(' on ')[0]}")
    print(f"  会话只读：{'✓ 是' if info['upstream_readonly'] else '✗ 否 —— 守卫失效！'}")
    tables = info["upstream_tables"]
    no_select = [t["table_name"] for t in tables if not t["can_select"]]
    print(f"  {config_mod.UPSTREAM_SCHEMA}: {len(tables)} 张表"
          f"，{'全部可 SELECT' if not no_select else '无 SELECT 权限: ' + ', '.join(no_select)}")

    print("\n目标 onto_db：")
    print(f"  {config_mod.ONTO_SCHEMA} schema CREATE 权限：{'✓' if info['onto_can_create'] else '✗'}")
    onto_tables = info["onto_tables"]
    if onto_tables:
        for t in onto_tables:
            print(f"    {t['table_name']:<32} ~{t['est_rows']} 行")
    else:
        print("    （空 —— 还没跑 dmo db migrate）")

    print("\nGraphDB：")
    from .graph.client import GraphDBClient, GraphDBError

    client = GraphDBClient(cfg)
    try:
        if not client.exists():
            print(f"  ✗ 仓库 {cfg.graphdb_repository} 不存在")
            return 1
        print(f"  ✓ 仓库 {cfg.graphdb_repository}，{client.size()} 三元组")
        for row in client.named_graphs():
            print(f"    {row['g']:<48} {row['n']}")
    except GraphDBError as e:
        print(f"  ✗ {e}")
        return 1
    return 0


def cmd_db_guard_test(args: argparse.Namespace) -> int:
    """守卫自测 —— 三道锁里前两道的可执行证明。

    这不是单元测试的替代品，是**上手第一件事**：换了库、换了账号、改了 DSN 之后
    先跑这个，确认「写不进上游」仍然成立。
    """
    from psycopg.errors import ReadOnlySqlTransaction

    from .db import engine

    cfg = config_mod.load()
    checks: list[tuple[str, bool, str]] = []

    # 1 只读连接上发 UPDATE —— 必须被我们的守卫拦下
    with engine.upstream_conn(cfg) as up:
        try:
            up.execute(
                f"UPDATE {config_mod.UPSTREAM_SCHEMA}.patient_basic_info "
                "SET vipflag = vipflag WHERE false"
            )
            checks.append(("守卫拦截上游 UPDATE", False, "语句竟然通过了 —— 守卫失效"))
        except engine.ReadOnlyViolation as e:
            checks.append(("守卫拦截上游 UPDATE", True, str(e).split("。")[0]))

        # 2 绕过守卫直发 —— PG 自己的只读会话必须也拦下（双保险）
        try:
            up.raw.execute(
                f"UPDATE {config_mod.UPSTREAM_SCHEMA}.patient_basic_info "
                "SET vipflag = vipflag WHERE false"
            )
            checks.append(("PG 会话只读兜底", False, "绕过守卫后竟然写成功了 —— 会话不是只读"))
        except ReadOnlySqlTransaction:
            checks.append(("PG 会话只读兜底", True, "read-only transaction"))

    # 3 onto 连接上引用上游 schema —— 必须被守卫拦下
    with engine.onto_conn(cfg) as onto:
        try:
            onto.execute(f"SELECT 1 FROM {config_mod.UPSTREAM_SCHEMA}.patient_basic_info LIMIT 1")
            checks.append(("守卫拦截跨库 schema 引用", False, "语句竟然通过了"))
        except engine.GuardViolation:
            checks.append(("守卫拦截跨库 schema 引用", True, "GuardViolation"))

        # 4 onto 连接可以正常写自己的 schema
        try:
            onto.execute("CREATE TEMP TABLE _dmo_guard_probe (x int)")
            onto.execute("DROP TABLE _dmo_guard_probe")
            checks.append(("onto 连接可写自己的 schema", True, "temp table 建删成功"))
        except Exception as e:  # noqa: BLE001
            checks.append(("onto 连接可写自己的 schema", False, str(e)[:120]))

    failed = 0
    for title, ok, detail in checks:
        print(f"  {'✓' if ok else '✗'} {title} —— {detail}")
        failed += 0 if ok else 1
    if failed:
        print(f"\n✗ {failed} 项守卫未通过。在修好之前不要跑任何写操作。", file=sys.stderr)
        return 1
    print("\n✓ 守卫全部生效：上游写不进，跨库引用拦得住，本库写得动。")
    return 0


def cmd_db_migrate(args: argparse.Namespace) -> int:
    from .db import migrate

    return migrate.run(config_mod.load(), dry=args.dry_run)


def cmd_db_seed(args: argparse.Namespace) -> int:
    from .db import cohort

    return cohort.load(config_mod.load())


def cmd_db_baseline(args: argparse.Namespace) -> int:
    from .db import baseline

    cfg = config_mod.load()
    return baseline.check(cfg) if args.check else baseline.capture(cfg)


def cmd_etl_pull(args: argparse.Namespace) -> int:
    from .db import baseline, etl

    cfg = config_mod.load()
    # 上游变了就别拉 —— 拿着和基线对不上的数据往下走，后面每一层都白算。
    # --force 是给「已经确认变化是预期的、但还没来得及重记基线」留的口子。
    if not args.force and baseline.check(cfg, quiet=True) != 0:
        baseline.check(cfg)
        print("\n  确认无误后用 `dmo db baseline` 重记，或 `dmo etl pull --force` 强拉。")
        return 1
    return etl.run(cfg, only=args.table)


# ─────────────────────────── map ─────────────────────────────────────


def cmd_map_sync_concepts(args: argparse.Namespace) -> int:
    from .terms import concepts, resolve

    cfg = config_mod.load()
    rc = concepts.sync(cfg)
    return rc or resolve.sync_risk_rules(cfg)


def cmd_map_load_terms(args: argparse.Namespace) -> int:
    from .terms import resolve

    return resolve.load_terms(config_mod.load())


def cmd_map_list_unmapped(args: argparse.Namespace) -> int:
    from .terms import resolve

    return resolve.report(config_mod.load())


def cmd_map_import_wfs(args: argparse.Namespace) -> int:
    from .terms import wfs

    return wfs.import_candidates(config_mod.load())


# ─────────────────────────── project / sync ──────────────────────────


def cmd_project_run(args: argparse.Namespace) -> int:
    from .db import projection

    return projection.run(config_mod.load())


def cmd_predict_run(args: argparse.Namespace) -> int:
    from .db import predict

    return predict.run(config_mod.load(), patient=args.patient)


def cmd_sync(args: argparse.Namespace) -> int:
    from .rdf import sync

    return sync.run(
        config_mod.load(),
        patient=getattr(args, "patient", None),
        prune=getattr(args, "prune", False),
        export=not getattr(args, "no_export", False),
    )


# ─────────────────────────── 查询与展示 ──────────────────────────────


def _dump(obj) -> None:
    import json

    def fallback(o):
        return str(o)

    print(json.dumps(obj, ensure_ascii=False, indent=2, default=fallback))


def cmd_query(args: argparse.Namespace) -> int:
    from .graph.client import GraphDBClient
    from .query import templates
    from .rdf import iri as iri_mod

    if not args.template:
        for t in sorted(templates.TEMPLATES.values(), key=lambda x: x.name):
            print(f"  {t.name:<24} {t.description}")
        return 0
    if not args.patient:
        raise SystemExit("必须给 --patient —— 模板不做全库扫描（见 query/templates.py）")
    cfg = config_mod.load()
    iris = [iri_mod.patient_iri(p) for p in args.patient]
    rows = GraphDBClient(cfg).sparql_csv(templates.render(args.template, iris))
    _dump(rows)
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    from .query import hybrid

    out = hybrid.explain_gap(config_mod.load(), args.term)
    print(f"═══ 「{args.term}」为什么查不到 ═══")
    for v in out["verdicts"]:
        print(f"  · {v}")
    print(f"\n  上游 cdr_lis_result 中同名子项行数：{out['upstreamResultRows']}")
    if out["upstreamParentItemOnly"]:
        print("  ⚠️ 但它作为**检验大项名**出现过：",
              ", ".join(f"{p['itemname']}×{p['n']}" for p in out["upstreamParentItemOnly"]))
    if out["candidateConcepts"]:
        print("\n  本体里的相关概念：")
        for c in out["candidateConcepts"][:6]:
            print(f"    [{c['concept_kind']}] {c['label']}（{c['code'] or '无编码'}）")
    print(f"\n{out['disclaimer']}")
    return 0


def cmd_adjudicate(args: argparse.Namespace) -> int:
    """裁决引用是不是逐字成立。人能读的一屏 —— 演示时看的就是这个。

    与 POST /adjudicate/citations 走同一条代码路径。
    """
    from .adjudicate import CitationError, check_citations

    citations = [
        {"quote": q, "sha256": h}
        for q, h in ((c[0], c[1] if len(c) > 1 else None) for c in (args.cite or []))
    ]
    try:
        out = check_citations(config_mod.load(), citations, asserted_by=args.asserted_by)
    except CitationError as e:
        raise SystemExit(f"✗ {e}") from None

    if args.json:
        _dump(out)
        return 0

    mark = {"verbatim": "✓", "hash-only": "✗", "quote-only": "✗",
            "not-verbatim": "·", "fabricated": "✗"}
    print(f"═══ 对着 {out['checkedAgainst']['passages']} 条逐字核验过的出处裁决 ═══")
    for r in out["results"]:
        print(f"\n  {mark.get(r['verdict'], '?')} [{r['verdict']}] {r['quote'] or '(只给了哈希)'}")
        print(f"      {r['reason']}")
        for m in r.get("matched", []):
            print(f"      ↳ {m['passageId']}  {m['sourceId']}  «{m['quote']}»")
        for n in r.get("nearest", []):
            print(f"      ≈ {n['relation']}  {n['passage']['passageId']}  «{n['passage']['quote']}»")
    print("\n  " + "  ".join(f"{k}={v}" for k, v in sorted(out["summary"].items())))
    print(f"\n{out['disclaimer']}")
    return 0 if out["summary"].get("verbatim", 0) == len(out["results"]) else 1


def cmd_rules(args: argparse.Namespace) -> int:
    """规则内省。默认打印三个落差 —— 那才是这条命令最该被看到的东西。"""
    from .graph import rules

    cfg = config_mod.load()
    if args.rule_id:
        _dump(rules.get(cfg, args.rule_id))
        return 0
    out = rules.search(cfg, kind=args.kind, q=args.q, limit=args.limit)
    if args.json:
        _dump(out)
        return 0
    c = out["counts"]
    print("═══ 规则覆盖 ═══")
    print(f"  诊断阈值      {c['threshold']['total']:>3} 条，可执行 {c['threshold']['executable']}")
    print(f"  管理目标      {c['target']['total']:>3} 条 —— {c['target']['note']}")
    print(f"  风险规则      {c['risk']['declared']:>3} 条声明，"
          f"可执行 {c['risk']['executable']}，计入 tier {c['risk']['countsInTier']}")
    print(f"  ⚠️ {c['risk']['classAssertionCaveat']}")
    print(f"\n═══ 清单（{out['total']} 条）═══")
    for r in out["rules"]:
        flag = "✓" if r.get("countsInTier", r["executable"]) else "·"
        print(f"  {flag} [{r['kind']:<9}] {r['ruleId'] or r['iri']:<28} "
              f"{r.get('interval') or r.get('observedCode') or r.get('matchValue') or ''}")
        if r["notExecutableReason"]:
            print(f"        ↳ {r['notExecutableReason']}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    from .query import hybrid

    try:
        _dump(hybrid.patient_bundle(config_mod.load(), args.patient))
    except KeyError:
        raise SystemExit(f"core_patient 里没有 {args.patient}") from None
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    """确定性病程推演。输出刻意做成人能读的报告 —— 演示时看的就是这一屏。"""
    from .simulate import HypothesisError, SandboxError, simulate

    assume = [
        {"term": t, "value": v, "unit": u, "date": d}
        for t, v, u, d in (args.assume or [])
    ]
    if not assume:
        raise SystemExit(
            "至少给一条 --assume TERM VALUE UNIT DATE，例如：\n"
            "    uv run dmo simulate P90002 --assume A1C 7.9 percent 2026-02-20")
    try:
        out = simulate(config_mod.load(), args.patient, assume, refresh=args.refresh)
    except (HypothesisError, SandboxError) as e:
        raise SystemExit(f"✗ {e}") from None

    if args.json:
        _dump(out)
        return 0

    print(f"═══ 推演 {out['patientId']} ═══")
    print(f"  derivationHash {out['derivationHash'][:32]}")
    print(f"  graphVersion   {out['graphVersion']}   规则 {len(out['rulesApplied'])} 条")

    print("\n【假设事实】（由调用方给出，系统不生成任何数值）")
    for h in out["hypotheticalFacts"]:
        line = f"  + {h['test']} {h['value']} {h['unit']} @{h['collectedDate']}"
        if h.get("conversionNote"):
            line += f"\n      换算：{h['conversionNote']}"
        print(line)

    if out["unchanged"]:
        print("\n【结论变化】无。假设事实没有改变任何结论 —— "
              "这本身是结论，不是故障。")
    else:
        print("\n【结论变化】")
        for d in out["delta"]:
            if d["change"] == "changed":
                for f, ba in d["fields"].items():
                    if f == "caveat":
                        continue
                    print(f"  ~ {d['type']}.{f}: {ba['before']} → {ba['after']}")
                if "caveat" in d["fields"]:
                    print(f"      变更后 caveat：{d['fields']['caveat']['after']}")
            elif d["change"] == "added":
                a = d["after"]
                print(f"  + {d['type']} {a.get('conclusion') or a.get('tier') or ''} "
                      f"{a.get('thresholdId') or ''}".rstrip())
            else:
                b = d["before"]
                print(f"  - {d['type']} {b.get('conclusion') or b.get('tier') or ''}".rstrip())

    print("\n【推理依据】")
    _print_tree(out["derivationTree"], 1)

    print(f"\n{out['hypotheticalNote']}")
    print(out["disclaimer"])
    return 0


def _print_tree(nodes: list, depth: int) -> None:
    """推导树。[实测]/[假设] 必须一眼可分 —— 这是整个推演最不能含糊的一处。"""
    pad = "  " * depth
    for n in nodes:
        kind = n["node"]
        if kind == "Diagnosis":
            print(f"{pad}◆ Diagnosis {n['diagnosisKind']} / {n['verificationStatus']} "
                  f"（{n['supportedByCount']} 条评估支撑）")
            if n.get("gapToConfirmed"):
                print(f"{pad}  ⤷ 差什么：{n['gapToConfirmed']}")
        elif kind == "Assessment":
            print(f"{pad}▸ Assessment {n['conclusion']}  [{n['rule']}]  "
                  f"上下文 {n['applicableContext']}")
        elif kind == "DiagnosticThreshold":
            confirm = "，需另一日复测确认" if n["confirmationRequired"] else ""
            print(f"{pad}· 阈值 {n['thresholdId']}  区间 {n['interval']}{confirm}")
            for s in n["sources"]:
                print(f"{pad}    出处「{s['quote']}」 sha256 {s['sha256'][:8]}")
            if n.get("sourceWarning"):
                print(f"{pad}    ⚠️ {n['sourceWarning']}")
        elif kind == "LabResult":
            tag = "[假设]" if n["provenance"] == "hypothetical" else "[实测]"
            print(f"{pad}· {tag} {n['value']} {n['unit']} @{n['collectedDate']}")
        for child in n.get("children", []):
            _print_tree([child], depth + 1)


def cmd_demo_compare(args: argparse.Namespace) -> int:
    from .terms import wfs

    out = wfs.compare(config_mod.load(), args.term)
    print(f"═══ 同一条「{args.term}」，两种做法 ═══\n")
    print("上游原始行：")
    for s in out["upstreamSamples"]:
        print(f"    {s['source_pk']}  {s['itemname']} = {s['inspectionresult']}"
              f"（参考范围 {s['inspectionresultrange']}，上游判读 {s['resultstateclass']}）")
    b = out["baseline"]
    print(f"\n【左栏】{b['approach']}")
    for link in b["links"]:
        print(f"    → {link['label']}  confidence={link['confidence']}  "
              f"verified={link['verified']}")
    print(f"    单位：{'有' if b['hasUnit'] else '无'}   "
          f"阈值：{'有' if b['hasThreshold'] else '无'}   "
          f"出处：{'有' if b['hasProvenance'] else '无'}")
    print(f"\n【右栏】{out['ontology']['approach']}")
    for m in out["ontology"]["mappings"]:
        print(f"    → 概念 {m['concept_label'] or '(未指定)'}")
        print(f"      value_kind={m['value_kind']}  verify_status={m['verify_status']}")
        print(f"      单位 {m['unit_src'] or '无'} → {m['unit_target'] or '不换算'}"
              f"{'  ×' + str(m['conv_factor']) if m['conv_factor'] else ''}")
        if m["note"]:
            print(f"      {m['note']}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .api import serve

    return serve(args.port)


# ─────────────────────────── 其余里程碑占位 ──────────────────────────


def _todo(milestone: str, what: str) -> Callable[[argparse.Namespace], int]:
    def run(args: argparse.Namespace) -> int:
        raise NotYetImplemented(milestone, what)

    return run


def cmd_graph_status(args: argparse.Namespace) -> int:
    from .graph.client import GraphDBClient, GraphDBError

    cfg = config_mod.load()
    client = GraphDBClient(cfg)
    try:
        if not client.exists():
            print(f"✗ 仓库 {cfg.graphdb_repository} 不存在。先跑："
                  f"\n  python3 ontology/tools/load_graphdb.py --create")
            return 1
        print(f"✓ {cfg.sparql_endpoint}  共 {client.size()} 三元组")
        for row in client.named_graphs():
            print(f"  {row['g']:<48} {row['n']}")
        # V2 切换是否完成：这 5 个类是 care-chain 的地基
        v2 = ["Assessment", "Diagnosis", "MedicationUse", "ClinicalObservation", "SourcePassage"]
        present = client.sparql_csv(
            "PREFIX owl: <http://www.w3.org/2002/07/owl#> "
            "SELECT ?c WHERE { GRAPH <urn:dmo:tbox> { ?c a owl:Class } }"
        )
        names = {r["c"].rsplit("#", 1)[-1] for r in present}
        missing = [c for c in v2 if c not in names]
        if missing:
            print(f"\n⚠️  TBox 里缺 V2 care-chain 类：{', '.join(missing)}")
            print("   说明装的还是 V1。R1 未完成之前，患者事实无处落地。")
        else:
            print("\n✓ V2 care-chain 五类齐全")
    except GraphDBError as e:
        print(f"✗ {e}")
        return 1
    return 0


# ─────────────────────────── 解析 ────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="dmo",
        description="糖尿病本体 × 患者事实库 融合查询层"
        "（⚠️ 技术验证用途，不是医疗器械，不构成医疗建议）",
    )
    sub = ap.add_subparsers(dest="group", required=True)

    # db
    db = sub.add_parser("db", help="骨架、迁移、演示队列、守卫自测").add_subparsers(
        dest="action", required=True
    )
    db.add_parser("status", help="两库 + GraphDB 连通性与权限").set_defaults(fn=cmd_db_status)
    db.add_parser("guard-test", help="只读守卫自测（写上游必须失败）").set_defaults(
        fn=cmd_db_guard_test
    )
    p = db.add_parser("migrate", help="建 diabetes schema 下的表")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_db_migrate)
    db.add_parser("seed", help="演示队列幂等 UPSERT").set_defaults(fn=cmd_db_seed)
    p = db.add_parser("baseline", help="上游基线快照 / 比对")
    p.add_argument("--check", action="store_true", help="只比对，不重记")
    p.set_defaults(fn=cmd_db_baseline)

    # etl
    etl = sub.add_parser("etl", help="上游只读快照").add_subparsers(dest="action", required=True)
    p = etl.add_parser("pull", help="hospital_zd → stg_*（全量重建）")
    p.add_argument("--table", help="只拉这一张目标表，如 stg_lis_result")
    p.add_argument("--force", action="store_true", help="上游与基线不一致时仍然拉")
    p.set_defaults(fn=cmd_etl_pull)

    # map
    mp = sub.add_parser("map", help="术语对齐").add_subparsers(dest="action", required=True)
    mp.add_parser("sync-concepts", help="GraphDB 概念 + 风险规则 → SQL 索引").set_defaults(
        fn=cmd_map_sync_concepts
    )
    mp.add_parser("load-terms", help="装载人工策展的三张映射 CSV").set_defaults(
        fn=cmd_map_load_terms
    )
    mp.add_parser("import-wfs", help="从 semantic_link 导入候选（只读，刻意丢弃其 IRI）").set_defaults(
        fn=cmd_map_import_wfs
    )
    mp.add_parser("list-unmapped", help="术语归宿报告").set_defaults(fn=cmd_map_list_unmapped)

    # project / sync
    pj = sub.add_parser("project", help="stg_+sim_ → core_").add_subparsers(
        dest="action", required=True
    )
    pj.add_parser("run", help="投影成 V2 care-chain").set_defaults(fn=cmd_project_run)

    sy = sub.add_parser("sync", help="core_ → GraphDB").add_subparsers(dest="action", required=True)
    p = sy.add_parser("patient", help="同步单个患者的命名图")
    p.add_argument("--patient", required=True)
    p.set_defaults(fn=cmd_sync)
    p = sy.add_parser("all", help="同步全部患者")
    p.add_argument("--prune", action="store_true",
                   help="删除已登记但 core_patient 里已不存在的患者图")
    p.add_argument("--no-export", action="store_true", help="不导出本地 TTL 副本")
    p.set_defaults(fn=cmd_sync)

    # graph
    gr = sub.add_parser("graph", help="GraphDB 状态与装载").add_subparsers(
        dest="action", required=True
    )
    gr.add_parser("status", help="仓库状态 + V2 切换进度").set_defaults(fn=cmd_graph_status)

    # predict / query / ask / serve
    pr = sub.add_parser("predict", help="风险分层").add_subparsers(dest="action", required=True)
    p = pr.add_parser("run", help="把 GraphDB 的分层结论物化进 pred_*")
    p.add_argument("--patient")
    p.set_defaults(fn=cmd_predict_run)

    p = sub.add_parser("query", help="参数化模板（白名单，不接受自由 SPARQL）")
    p.add_argument("template", nargs="?", help="留空则列出全部模板")
    p.add_argument("--patient", action="append", default=[], help="可多次给")
    p.set_defaults(fn=cmd_query)

    p = sub.add_parser("explain", help="诚实回答「为什么查不到某个术语」")
    p.add_argument("term")
    p.set_defaults(fn=cmd_explain)

    p = sub.add_parser("show", help="一个患者的完整返回体（七段）")
    p.add_argument("patient")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser(
        "simulate",
        help="确定性病程推演：注入假设检验，看结论怎么变",
        description="若 X 则 Y 的条件推演，不是预测。假设值必须显式给出，"
                    "系统不生成候选值。全程内存运算，不写 GraphDB。")
    p.add_argument("patient")
    p.add_argument("--assume", nargs=4, action="append",
                   metavar=("TERM", "VALUE", "UNIT", "DATE"),
                   help="可多次给，如：--assume A1C 7.9 percent 2026-02-20")
    p.add_argument("--json", action="store_true", help="输出原始返回体")
    p.add_argument("--refresh", action="store_true", help="强制重取知识层快照")
    p.set_defaults(fn=cmd_simulate)

    p = sub.add_parser(
        "adjudicate",
        help="裁决引用是不是逐字成立（≈ POST /adjudicate/citations）",
        description="用本库 31 条逐字核验过的出处，核对别人给出的引用。\n"
                    "永远不返回「通过 / 合理」，只给五个判定值之一。")
    p.add_argument("--cite", nargs="+", action="append", metavar=("QUOTE", "SHA256"),
                   help="引文 [哈希]，可多次给")
    p.add_argument("--asserted-by", help="谁说的。只记账，绝不参与判定")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_adjudicate)

    p = sub.add_parser("rules", help="规则内省（≈ GET /graph/rules）")
    p.add_argument("rule_id", nargs="?", help="给了就打印单条全貌 + 展开的出处")
    p.add_argument("--kind", choices=("threshold", "target", "risk"))
    p.add_argument("--q", help="子串筛选")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_rules)

    d = sub.add_parser("demo", help="对照演示").add_subparsers(dest="action", required=True)
    p = d.add_parser("compare", help="同一术语：字符串匹配 vs 本体")
    p.add_argument("--term", default="尿蛋白")
    p.set_defaults(fn=cmd_demo_compare)

    p = sub.add_parser("serve", help="FastAPI")
    p.add_argument("--port", type=int, default=8100)
    p.set_defaults(fn=cmd_serve)

    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
