"""每患者一命名图，内容哈希驱动的幂等 GSP PUT。

**PUT（整图替换）而不是 POST（追加）**：追加的话，患者删掉一条检验后，
图里那条三元组永远不会消失 —— 图会单调增长且没人发现。

流程：
    core_* 取一个患者的全部事实
      → emit.build() 出一张图（断言无空节点）
      → canonical.graph_hash()
      → 与 sys_rdf_sync_state.content_hash 比对
      → 相同则**跳过**，不同才 PUT
      → 单个患者失败不中断，最后汇总，有失败非零退出

`--prune` 只删「登记过但 core_patient 里已不存在」的 `urn:dmo:patient:*`，
绝不碰 tbox / seed / sources / extract / inferred。
"""

from __future__ import annotations

from pathlib import Path

from ..config import Config
from ..db.engine import onto_conn
from ..graph.client import GraphDBClient, GraphDBError
from . import emit
from . import iri as I
from .canonical import graph_hash

EXPORT_DIR = Path(__file__).resolve().parents[3] / "ontology" / "dist" / "patients"

FACT_QUERIES: dict[str, str] = {
    "encounters": "SELECT * FROM diabetes.core_encounter WHERE patientid = %s"
                  " ORDER BY encounter_id",
    "labs": "SELECT * FROM diabetes.core_lab_result WHERE patientid = %s"
            " ORDER BY lab_result_id",
    "observations": "SELECT * FROM diabetes.core_observation WHERE patientid = %s"
                    " ORDER BY observation_id",
    "diagnoses": "SELECT * FROM diabetes.core_diagnosis WHERE patientid = %s"
                 " ORDER BY diagnosis_id",
    "medications": "SELECT * FROM diabetes.core_medication_use WHERE patientid = %s"
                   " ORDER BY medication_use_id",
}


def _facts(conn, pid: str) -> dict[str, list[dict]]:
    return {k: conn.fetchall(q, (pid,)) for k, q in FACT_QUERIES.items()}


def run(
    cfg: Config,
    *,
    patient: str | None = None,
    prune: bool = False,
    export: bool = True,
) -> int:
    client = GraphDBClient(cfg)
    put = skipped = failed = 0
    errors: list[str] = []

    with onto_conn(cfg) as conn:
        if patient:
            patients = conn.fetchall(
                "SELECT * FROM diabetes.core_patient WHERE patientid = %s", (patient,)
            )
            if not patients:
                raise SystemExit(f"core_patient 里没有 {patient}。先跑 `dmo project run`。")
        else:
            patients = conn.fetchall("SELECT * FROM diabetes.core_patient ORDER BY patientid")

        state = {
            r["patientid"]: r["content_hash"]
            for r in conn.fetchall(
                "SELECT patientid, content_hash FROM diabetes.sys_rdf_sync_state"
            )
        }

        if export:
            EXPORT_DIR.mkdir(parents=True, exist_ok=True)

        for p in patients:
            pid = p["patientid"]
            graph_uri = I.patient_graph(pid)
            try:
                g = emit.build(p, _facts(conn, pid))
                h = graph_hash(g)
                if export:
                    # 本地导出一份，给没有 GraphDB 的 CI 跑 validate_shacl.py 用。
                    (EXPORT_DIR / f"{pid}.ttl").write_text(
                        g.serialize(format="turtle"), encoding="utf-8"
                    )
                if state.get(pid) == h:
                    skipped += 1
                    continue
                client.put_graph(graph_uri, g.serialize(format="turtle"))
                conn.execute(
                    """
                    INSERT INTO diabetes.sys_rdf_sync_state
                        (patientid, graph_uri, content_hash, triple_count, synced_at)
                    VALUES (%s,%s,%s,%s, now())
                    ON CONFLICT (patientid) DO UPDATE SET
                        graph_uri = EXCLUDED.graph_uri,
                        content_hash = EXCLUDED.content_hash,
                        triple_count = EXCLUDED.triple_count,
                        synced_at = now()
                    """,
                    (pid, graph_uri, h, len(g)),
                )
                conn.commit()
                put += 1
            except (GraphDBError, AssertionError) as e:
                # 单个患者失败不中断整批 —— 30 个患者里第 7 个挂了，
                # 剩下 23 个仍该同步，最后汇总非零退出。
                failed += 1
                errors.append(f"{pid}: {e}")
                conn.rollback()

        pruned = 0
        if prune:
            alive = {r["patientid"] for r in patients} if not patient else None
            rows = conn.fetchall(
                "SELECT patientid, graph_uri FROM diabetes.sys_rdf_sync_state"
            )
            live_ids = {r["patientid"] for r in conn.fetchall(
                "SELECT patientid FROM diabetes.core_patient")}
            for r in rows:
                if r["patientid"] in live_ids:
                    continue
                # 只删患者图。图名前缀是硬约束 —— 一个手滑就可能把 tbox 删了。
                if not r["graph_uri"].startswith("urn:dmo:patient:"):
                    errors.append(f"拒绝删除非患者图：{r['graph_uri']}")
                    failed += 1
                    continue
                client.drop_graph(r["graph_uri"])
                conn.execute(
                    "DELETE FROM diabetes.sys_rdf_sync_state WHERE patientid = %s",
                    (r["patientid"],),
                )
                pruned += 1
            conn.commit()
            _ = alive

    print(f"✓ PUT {put} 图 / 跳过 {skipped} 图（内容哈希未变）"
          + (f" / 清理 {pruned} 图" if prune else ""))
    if export:
        print(f"  本地导出：{EXPORT_DIR.relative_to(EXPORT_DIR.parents[3])}/*.ttl")
    if failed:
        print(f"\n✗ {failed} 个失败：")
        for e in errors[:10]:
            print(f"    {e}")
        return 1
    return 0
