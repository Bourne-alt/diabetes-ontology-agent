"""Small typed query tools mapped to src/dmo/api.py's read-only contract."""

import asyncio
import json
from typing import Annotated, Literal
from urllib.parse import quote

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from .backend import DmoBackend
from .database import Database, FactStore

Limit = Annotated[int, Field(ge=1, le=100)]


class Assumption(BaseModel):
    """一条假设检验结果。四个字段都必填 —— 服务端不猜术语、不默认单位、不补日期。"""

    term: str = Field(
        description="检验项代码，如 A1C / FPG。必须是本体里挂了诊断阈值的项目；不做模糊匹配。"
    )
    value: float = Field(
        description="假设数值。只能来自用户明确给出的数字，不得自行生成、推荐或外推。"
    )
    unit: str = Field(
        description="单位，如 percent / mmol-per-L。缺单位或单位不符会被直接拒绝判定。"
    )
    date: str = Field(
        description="采集日期 YYYY-MM-DD。不能省：30 天规则按不同日期区分 Provisional 与 Confirmed。"
    )


def build_tools(backend: DmoBackend, facts: FactStore):
    @tool
    async def report_plan(steps: list[str]) -> dict:
        """查询前公布简短行动计划；只写要查的数据与目的，不写内部推理。"""
        if not 1 <= len(steps) <= 6 or any(len(s) > 200 for s in steps):
            raise ValueError("计划需要 1..6 个短步骤，每步最多 200 字。")
        return {"steps": steps}

    @tool
    async def ontology_status(kind: Literal["health", "manifest", "schema"] = "manifest"):
        """读取能力边界/服务状态/schema；首次业务查询先看 manifest。"""
        return await backend.request(
            {"health": "/health", "manifest": "/agent/manifest", "schema": "/graph/schema"}[kind]
        )

    @tool
    async def search_concepts(q: str, kind: str | None = None, limit: Limit = 10):
        """图查询第一步：把中文、编码或英文解析成真实 IRI，检查 usable；不得猜 IRI。"""
        return await backend.request("/graph/concepts", {"q": q, "kind": kind, "limit": limit})

    @tool
    async def explore_concept(
        iri: str,
        action: Literal["node", "neighbors", "taxonomy", "provenance"] = "node",
        predicate: str | None = None,
        direction: Literal["out", "in", "up", "down"] = "out",
        limit: Limit = 20,
        depth: Annotated[int, Field(ge=1, le=3)] = 2,
    ):
        """使用已解析 IRI 查看节点、邻居、层次或出处链；保留推理标记与 brokenLinks。"""
        params = {"iri": iri}
        if action == "neighbors":
            if direction not in ("in", "out"):
                raise ValueError("neighbors 的 direction 必须是 in/out")
            params.update(predicate=predicate, direction=direction, limit=limit)
        elif action == "taxonomy":
            params.update(direction="up" if direction == "out" else direction, depth=depth)
        return await backend.request(f"/graph/{action}", params)

    @tool
    async def find_graph_path(
        source: str, target: str, max_hops: Annotated[int, Field(ge=1, le=3)] = 3
    ):
        """查看两个已解析 IRI 间的受控图路径；只能转述返回的真实节点和边。"""
        return await backend.request(
            "/graph/path", {"from": source, "to": target, "maxHops": max_hops}
        )

    @tool
    async def search_rules(
        q: str | None = None,
        concept: str | None = None,
        kind: Literal["threshold", "target", "risk"] | None = None,
        rule_id: str | None = None,
        limit: Limit = 10,
    ):
        """查本体阈值/目标/风险规则；给 rule_id 可展开逐字出处和哈希，禁止自行造阈值。"""
        if rule_id:
            return await backend.request("/graph/rules/" + quote(rule_id, safe=""))
        return await backend.request(
            "/graph/rules", {"q": q, "concept": concept, "kind": kind, "limit": limit}
        )

    @tool
    async def search_passages(
        q: str | None = None,
        sha256: str | None = None,
        cited_by: str | None = None,
        limit: Limit = 10,
    ):
        """按原文子串、哈希或规则号查询证据；引用必须原样复制 quote 和完整 sha256。"""
        return await backend.request(
            "/graph/passages", {"q": q, "sha256": sha256, "citedBy": cited_by, "limit": limit}
        )

    @tool
    async def explain_term(term: str):
        """解释术语映射、不可用原因；查无映射不等于患者没有疾病。"""
        return await backend.request("/terms/explain", {"term": term})

    @tool
    async def find_patients(
        icd10: str | None = None,
        origin: Literal["ehr-legacy", "derived", "demo-cohort"] = "ehr-legacy",
        tier: str | None = None,
        page: Annotated[int, Field(ge=1)] = 1,
        size: Limit = 10,
    ):
        """先收敛患者集合并分页；默认真实患者，合成队列必须单独明确查询。"""
        return await backend.request(
            "/patients",
            {"icd10": icd10, "origin": origin, "tier": tier, "page": page, "size": size},
        )

    @tool
    async def patient_evidence(
        patient_id: str,
        section: Literal[
            "care-chain", "assessment", "risk", "safety", "recommendations", "monitoring-due"
        ] = "care-chain",
    ):
        """患者本体判定及证据。需要结论用此工具，不能通过 SQL 数值自行判定。"""
        return await backend.request(f"/patients/{quote(patient_id, safe='')}/{section}")

    @tool
    async def simulate_patient_course(
        patient_id: str,
        assume: Annotated[list[Assumption], Field(min_length=1, max_length=10)],
        include_unreliable: bool = False,
        refresh: bool = False,
    ):
        """确定性条件推演（若 X 则 Y）：注入用户给出的假设检验值，看结论怎么变与推导树。

        只读：全程在内存计算，对图库只发 CONSTRUCT，一条三元组都不会写入。
        假设值必须来自用户原话；模型不得自行编造、推荐或外推数值，也不得替用户设想情景。
        返回的是假设情景下的结论，必须与该患者的实际情况分开表述，不能当作已经发生。
        服务端提示快照可能损坏时，才用 refresh=true 重取。
        """
        payload: dict = {
            "assume": [a.model_dump() if hasattr(a, "model_dump") else dict(a) for a in assume]
        }
        if include_unreliable:
            payload["includeUnreliable"] = True
        if refresh:
            payload["refresh"] = True
        return await backend.request(
            f"/patients/{quote(patient_id, safe='')}/simulate", body=payload
        )

    @tool
    async def assess_patient_treatment(pid: str):
        """按患者 ID 读取内部患者镜像，生成当前治疗措施的多维证据评估报告。"""
        from langchain_core.callbacks.manager import adispatch_custom_event

        async def publish(report):
            await adispatch_custom_event("harness_assessment_report", {"patient_id": pid, "report": report})

        return await backend.request(
            f"/patients/{quote(pid, safe='')}/treatment-assessments", body={}, assessment_observer=publish
        )

    @tool
    async def run_prediction_demo(pid: str):
        """运行合成患者的预测演示，返回 7/14/28 天数值及计算过程。

        用户说“预测演示”或“数值推演”即可调用，无需额外限定词。
        仅支持本模块合成患者；结果是演示算法输出，不是实际疗效预测。
        """
        return await backend.request(
            f"/patients/{quote(pid, safe='')}/prediction-demo", body={}
        )

    @tool
    async def inspect_fact_schema(database: Database, table: str | None = None):
        """读取 original 原始库或 ontology 本体关系库的可查表、列、类型与注释。"""
        return await asyncio.to_thread(facts.catalog, database, table)

    @tool
    async def query_patient_facts(
        database: Database,
        table: str,
        columns: list[str],
        filters: dict[str, str | int | float | bool | None],
        limit: Limit = 20,
        offset: Annotated[int, Field(ge=0, le=10000)] = 0,
    ):
        """schema 确认后查询事实：显式列名、AND 等值筛选、分页。禁 SQL/表达式/跨库 join。

        原始患者表按 patientid 查；cdr_lis_result 按先查到的 testcode 查。
        原始行仅供溯源。临床判断优先 patient_evidence；零行不是正常。
        """
        result = await asyncio.to_thread(
            facts.query, database, table, columns, filters, limit, offset
        )
        return json.loads(json.dumps(result, ensure_ascii=False, default=str))

    return [
        report_plan,
        ontology_status,
        search_concepts,
        explore_concept,
        find_graph_path,
        search_rules,
        search_passages,
        explain_term,
        find_patients,
        patient_evidence,
        simulate_patient_course,
        assess_patient_treatment,
        run_prediction_demo,
        inspect_fact_schema,
        query_patient_facts,
    ]
