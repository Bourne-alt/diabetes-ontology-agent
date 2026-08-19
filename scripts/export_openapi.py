"""Export an integration-friendly OpenAPI document from the FastAPI app.

FastAPI is kept as the source of truth for routes and query parameters.  This
exporter only adds the richer request contracts and integration metadata that
are documented in docs/API.md but are intentionally not represented by the
runtime's loose ``dict[str, Any]`` request annotations.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from dmo.api import app

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "openapi.json"
HTTP_EXAMPLES_OUTPUT = ROOT / "docs" / "api-examples.http"


# Every public operation has one executable happy-path request. Values come
# from the deterministic demo cohort, ontology seed, and regression tests.
REQUEST_EXAMPLES: dict[tuple[str, str], dict[str, Any]] = {
    ("get", "/"): {"title": "服务入口"},
    ("get", "/health"): {"title": "检查两侧依赖与数据量"},
    ("get", "/patients"): {
        "title": "检索 E11 患者并返回前两条",
        "query": {"icd10": "E11", "page": 1, "size": 2},
    },
    ("get", "/patients/{pid}/care-chain"): {
        "title": "查询 P90002 的照护链",
        "path": {"pid": "P90002"},
    },
    ("get", "/patients/{pid}/assessment"): {
        "title": "查询单次 A1C 7.4% 的阈值判定",
        "path": {"pid": "P90002"},
    },
    ("get", "/patients/{pid}/risk"): {
        "title": "查询有多个可改变风险因子的患者",
        "path": {"pid": "P90020"},
    },
    ("get", "/patients/{pid}/safety"): {
        "title": "查询 ESRD 加恩格列净的绝对禁忌信号",
        "path": {"pid": "P90008"},
    },
    ("get", "/patients/{pid}"): {
        "title": "查询 P90002 的全景数据返回体",
        "path": {"pid": "P90002"},
    },
    ("post", "/simulate"): {
        "title": "通过静态路径执行确定性复测推演",
        "body": {
            "patientId": "P90002",
            "assume": [{"term": "A1C", "value": 7.9, "unit": "percent", "date": "2026-02-20"}],
        },
    },
    ("post", "/patients/{pid}/simulate"): {
        "title": "通过患者路径执行确定性复测推演",
        "path": {"pid": "P90002"},
        "body": {
            "assume": [{"term": "A1C", "value": 7.9, "unit": "percent", "date": "2026-02-20"}],
        },
    },
    ("get", "/query/templates"): {"title": "列出查询模板白名单"},
    ("post", "/query/{template}"): {
        "title": "运行照护链模板",
        "path": {"template": "care_chain"},
        "body": ["P90002"],
    },
    ("get", "/agent/manifest"): {"title": "获取智能体能力清单"},
    ("get", "/graph/concepts"): {
        "title": "把中文表面形式解析为准确 IRI",
        "query": {"q": "糖化血红蛋白", "kind": "LabTest", "limit": 5},
    },
    ("get", "/graph/node"): {
        "title": "查看 A1C 糖尿病阈值节点",
        "query": {"iri": "https://example.org/dmo/id/threshold/A1C-DIABETES"},
    },
    ("get", "/graph/neighbors"): {
        "title": "展开阈值指向的逐字出处",
        "query": {
            "iri": "https://example.org/dmo/id/threshold/A1C-DIABETES",
            "predicate": "https://example.org/dmo#thresholdCitesPassage",
            "direction": "out",
            "limit": 10,
        },
    },
    ("get", "/graph/taxonomy"): {
        "title": "查看 CKD 的上位概念与推理边",
        "query": {"iri": "https://example.org/dmo/id/CKD", "direction": "up", "depth": 2},
    },
    ("get", "/graph/path"): {
        "title": "查找检验结果到指南出处的支撑路径",
        "query": {
            "from": "https://example.org/dmo/id/labResult/L90002-A1C",
            "to": "https://example.org/dmo/id/sourcePassage/A1C-DIABETES-Q",
            "maxHops": 4,
        },
    },
    ("get", "/graph/schema"): {
        "title": "获取 SQL 列到 RDF 谓词的桥接表",
        "query": {"section": "bridge"},
    },
    ("get", "/graph/provenance"): {
        "title": "追踪 P90002 的 A1C 评估至指南原文和 SQL 行",
        "query": {
            "iri": "https://example.org/dmo/id/assessment/72d5c0144bdb81cd7d6bc88dd20f121742f9f9bd"
        },
    },
    ("post", "/graph/sparql"): {
        "title": "执行通过 guard 的只读阈值查询",
        "body": {
            "query": (
                "PREFIX dmo: <https://example.org/dmo#>\n"
                "SELECT ?id WHERE { ?threshold dmo:thresholdId ?id } LIMIT 20"
            )
        },
    },
    ("get", "/graph/passages"): {
        "title": "查询 A1C 糖尿病阈值引用的出处",
        "query": {"citedBy": "A1C-DIABETES-NONPREG", "limit": 10},
    },
    ("get", "/graph/rules"): {
        "title": "列出不参与 tier 计分的风险规则",
        "query": {"kind": "risk", "countsInTier": False, "limit": 20},
    },
    ("get", "/graph/rules/{rule_id}"): {
        "title": "查看 A1C 糖尿病阈值规则及出处",
        "path": {"rule_id": "A1C-DIABETES-NONPREG"},
    },
    ("post", "/adjudicate/claim"): {
        "title": "裁决单次 A1C 是否足以确诊",
        "body": {
            "patientId": "P90002",
            "claim": {
                "type": "Diagnosis",
                "value": {"kind": "Diabetes", "verificationStatus": "Confirmed"},
            },
            "assertedBy": "api-debug-example",
        },
    },
    ("get", "/adjudicate/scope"): {"title": "查询系统可裁决范围"},
    ("post", "/adjudicate/citations"): {
        "title": "核对真实 A1C 逐字引文及哈希",
        "body": {
            "citations": [
                {
                    "quote": "6.5% or above",
                    "sha256": "96495c7d996a92b5bee7132029744f08e5154be98dd1be7e177399320d7d1447",
                }
            ],
            "assertedBy": "api-debug-example",
        },
    },
    ("get", "/terms/unmapped"): {"title": "列出所有未映射与不可用术语"},
    ("get", "/terms/explain"): {
        "title": "解释糖化血红蛋白为何不可用于上游判定",
        "query": {"term": "糖化血红蛋白"},
    },
    ("get", "/demo/compare"): {
        "title": "比较尿蛋白的字符串匹配与本体结果",
        "query": {"term": "尿蛋白"},
    },
}


PARAMETER_DESCRIPTIONS: dict[tuple[str, str], str] = {
    ("/patients", "icd10"): "按 ICD-10 外部诊断编码前缀筛选，例如 E11。可不传。",
    ("/patients", "origin"): (
        "按事实来源筛选：ehr-legacy 为真实上游数据，derived 为规则推导数据，"
        "demo-cohort 为演示队列。可不传。"
    ),
    ("/patients", "scenario"): "按演示场景编号筛选，例如 S02；主要用于调试演示队列。可不传。",
    ("/patients", "tier"): "按规则式风险档位筛选；档位是有序枚举，不是概率或分数。可不传。",
    ("/patients", "page"): "页码，从 1 开始。",
    ("/patients", "size"): "每页记录数，范围 1–200。",
    ("/patients/{pid}/care-chain", "pid"): "患者业务编号，例如 P90002。",
    ("/patients/{pid}/assessment", "pid"): "患者业务编号，例如 P90002。",
    ("/patients/{pid}/risk", "pid"): "患者业务编号，例如 P90020。",
    ("/patients/{pid}/safety", "pid"): "患者业务编号，例如 P90008。",
    ("/patients/{pid}", "pid"): "患者业务编号，例如 P90002。",
    ("/patients/{pid}/simulate", "pid"): "要执行条件推演的患者业务编号，例如 P90002。",
    ("/query/{template}", "template"): (
        "参数化查询模板名称。可用值通过 GET /query/templates 获取；"
        "例如 care_chain、assessment_evidence。"
    ),
    ("/graph/concepts", "q"): "待解析的中文表面形式、规范编码或英文标签，例如“糖化血红蛋白”。",
    ("/graph/concepts", "kind"): "可选的概念类型过滤，例如 LabTest、Medication、RiskFactor。",
    ("/graph/concepts", "limit"): "最多返回的候选概念数。",
    ("/graph/node", "iri"): (
        "要查看的完整节点 IRI；必须先通过 /graph/concepts 获得准确 IRI，不接受自然语言术语。"
    ),
    ("/graph/neighbors", "iri"): "作为一跳展开起点的完整节点 IRI。",
    ("/graph/neighbors", "predicate"): "可选的完整 RDF 谓词 IRI；传入后只返回该关系。",
    ("/graph/neighbors", "direction"): "遍历方向：out 返回当前节点指向的对象，in 返回指向当前节点的主语。",
    ("/graph/neighbors", "limit"): "最多返回的一跳邻居数。",
    ("/graph/taxonomy", "iri"): "要查询类层次的完整概念 IRI。",
    ("/graph/taxonomy", "direction"): "层次方向：up 查询上位类，down 查询下位类。",
    ("/graph/taxonomy", "depth"): "最大层次深度；服务端会限制可接受范围。",
    ("/graph/path", "from"): "路径起点的完整节点 IRI。",
    ("/graph/path", "to"): "路径终点的完整节点 IRI。",
    ("/graph/path", "maxHops"): "受控 BFS 的最大跳数；用于限制图遍历开销。",
    ("/graph/schema", "section"): "只返回指定 schema 区段：rdf、sql 或 bridge；不传则返回全部。",
    ("/graph/provenance", "iri"): (
        "要反向溯源的推断结论完整 IRI，例如 Assessment、Diagnosis 或 RiskFactorHit 的 IRI。"
    ),
    ("/graph/passages", "sha256"): "按 64 位十六进制内容哈希精确查找出处。可不传。",
    ("/graph/passages", "q"): "按规范化后的引文子串进行大小写不敏感检索。可不传。",
    ("/graph/passages", "passageId"): "按出处业务编号精确筛选，例如 A1C-DIABETES-Q。可不传。",
    ("/graph/passages", "citedBy"): "筛选被指定 thresholdId 或 riskRuleId 引用的出处。可不传。",
    ("/graph/passages", "limit"): "最多返回的出处数量。",
    ("/graph/rules", "kind"): "按规则类别筛选：threshold、target 或 risk。可不传。",
    ("/graph/rules", "q"): "按规则编号或标签关键字检索。可不传。",
    ("/graph/rules", "executable"): "筛选规则链 WHERE 是否能够实际匹配；true 只返回可执行规则。",
    ("/graph/rules", "countsInTier"): "风险规则过滤条件：是否有逐字出处并实际参与 tier 计算。",
    ("/graph/rules", "concept"): "按检验项或指标筛选，例如 A1C、FPG。可不传。",
    ("/graph/rules", "context"): "按适用人群语境筛选，例如 NonPregnant、Pregnant、Any。可不传。",
    ("/graph/rules", "limit"): "最多返回的规则数量。",
    ("/graph/rules/{rule_id}", "rule_id"): (
        "规则业务编号，例如 A1C-DIABETES-NONPREG；可先通过 GET /graph/rules 查询。"
    ),
    ("/terms/explain", "term"): "需要解释映射状态或不可判定原因的原始术语。",
    ("/demo/compare", "term"): "用于比较字符串匹配与本体映射结果的原始术语，例如“尿蛋白”。",
}


REQUEST_BODY_DESCRIPTIONS = {
    ("post", "/simulate"): "患者编号和假设检验事实；适用于只能配置静态 URL 的调用方。",
    ("post", "/patients/{pid}/simulate"): "要注入内存沙箱的假设检验事实列表。",
    ("post", "/query/{template}"): "非空患者业务编号数组；模板不会执行无患者约束的全库扫描。",
    ("post", "/graph/sparql"): "只读 SPARQL 查询对象；执行前必须通过静态安全检查。",
    ("post", "/adjudicate/claim"): "需要裁决的患者、结构化断言及可选引用。",
    ("post", "/adjudicate/citations"): "需要逐字核对的一组引文或内容哈希。",
}


SCHEMAS: dict[str, Any] = {
    "Error": {
        "type": "object",
        "description": "标准错误响应。400 也可能表示有意的业务拒绝。",
        "required": ["detail"],
        "properties": {
            "detail": {
                "description": "错误或业务拒绝原因。部分端点可能返回结构化对象。",
                "oneOf": [{"type": "string"}, {"type": "object", "additionalProperties": True}],
            },
            "hint": {"type": "string", "description": "可选的排障建议。"},
        },
    },
    "Hypothesis": {
        "type": "object",
        "required": ["term", "value", "unit", "date"],
        "properties": {
            "term": {
                "type": "string",
                "enum": ["A1C", "FPG", "GCT1H", "GLU", "OGTT2H", "RPG", "UACR"],
                "description": "只接受已挂接阈值的规范术语，不做模糊匹配。",
            },
            "value": {"type": "number", "description": "由调用方显式提供的假设数值。"},
            "unit": {"type": "string", "description": "单位必填；仅接受规范单位或已核实换算。"},
            "date": {"type": "string", "format": "date", "description": "假设检验日期。"},
        },
        "additionalProperties": False,
    },
    "SimulationRequest": {
        "type": "object",
        "required": ["assume"],
        "properties": {
            "assume": {
                "type": "array",
                "minItems": 1,
                "maxItems": 10,
                "items": {"$ref": "#/components/schemas/Hypothesis"},
                "description": "要注入内存沙箱的假设检验事实，至少 1 条、最多 10 条。",
            },
            "includeUnreliable": {
                "type": "boolean",
                "default": False,
                "description": "是否把 trust=Unverified 的既有患者事实纳入推演基线。",
            },
            "refresh": {
                "type": "boolean",
                "default": False,
                "description": "是否绕过知识快照缓存并重新从 GraphDB 读取。",
            },
        },
        "additionalProperties": False,
    },
    "StaticSimulationRequest": {
        "type": "object",
        "required": ["assume"],
        "anyOf": [{"required": ["patientId"]}, {"required": ["pid"]}],
        "properties": {
            "patientId": {
                "type": "string",
                "description": "要执行条件推演的患者业务编号。",
                "example": "P90002",
            },
            "pid": {
                "type": "string",
                "deprecated": True,
                "description": "patientId 的兼容别名。",
            },
            "assume": {
                "type": "array",
                "minItems": 1,
                "maxItems": 10,
                "items": {"$ref": "#/components/schemas/Hypothesis"},
                "description": "要注入内存沙箱的假设检验事实，至少 1 条、最多 10 条。",
            },
            "includeUnreliable": {
                "type": "boolean",
                "default": False,
                "description": "是否把 trust=Unverified 的既有患者事实纳入推演基线。",
            },
            "refresh": {
                "type": "boolean",
                "default": False,
                "description": "是否绕过知识快照缓存并重新从 GraphDB 读取。",
            },
        },
        "additionalProperties": False,
    },
    "SparqlRequest": {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {
                "type": "string",
                "description": "只读 SELECT / ASK / CONSTRUCT / DESCRIBE；执行前经过静态检查。",
            }
        },
        "additionalProperties": False,
    },
    "CitationInput": {
        "type": "object",
        "description": "quote 与 sha256 至少提供一项。",
        "properties": {
            "quote": {"type": "string", "description": "调用方声称逐字引用的原文。"},
            "sha256": {
                "type": "string",
                "pattern": "^[0-9a-fA-F]{64}$",
                "description": "调用方声称的引文内容哈希。",
            },
            "contentHash": {
                "type": "string",
                "pattern": "^[0-9a-fA-F]{64}$",
                "deprecated": True,
                "description": "sha256 的兼容别名。",
            },
        },
        "anyOf": [
            {"required": ["quote"]},
            {"required": ["sha256"]},
            {"required": ["contentHash"]},
        ],
        "additionalProperties": False,
    },
    "CitationsRequest": {
        "type": "object",
        "required": ["citations"],
        "properties": {
            "citations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 200,
                "items": {"$ref": "#/components/schemas/CitationInput"},
                "description": "待核对的引文列表，至少 1 条、最多 200 条。",
            },
            "assertedBy": {"type": "string", "description": "仅记账，不参与判定。"},
            "refresh": {
                "type": "boolean",
                "default": False,
                "description": "是否绕过出处索引缓存并重新从 GraphDB 读取。",
            },
        },
        "additionalProperties": False,
    },
    "Claim": {
        "type": "object",
        "required": ["type", "value"],
        "properties": {
            "type": {
                "type": "string",
                "description": "结构化断言类型；不同类型对应不同的 value 语义键。",
                "enum": [
                    "Assessment",
                    "TargetAttainment",
                    "Diagnosis",
                    "RiskTier",
                    "MedicationSafety",
                ],
            },
            "value": {
                "type": "object",
                "description": "随 claim.type 变化的结构化断言；不接受自然语言断言。",
                "additionalProperties": True,
            },
        },
        "additionalProperties": False,
    },
    "ClaimAdjudicationRequest": {
        "type": "object",
        "required": ["patientId", "claim"],
        "properties": {
            "patientId": {
                "type": "string",
                "description": "断言所针对的患者业务编号。",
                "example": "P90002",
            },
            "claim": {"$ref": "#/components/schemas/Claim"},
            "assertedBy": {"type": "string", "description": "仅记账，不参与判定。"},
            "citations": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/CitationInput"},
                "description": "可选的支撑引文；用于检查引文是否真实且是否张冠李戴。",
            },
        },
        "additionalProperties": False,
    },
}


TAG_BY_PREFIX = {
    "/health": "Service",
    "/patients": "Patients",
    "/simulate": "Simulation",
    "/query": "Query templates",
    "/agent": "Agent discovery",
    "/graph": "Graph exploration",
    "/adjudicate": "Adjudication",
    "/terms": "Terminology",
    "/demo": "Demo",
}


SUMMARIES = {
    ("get", "/"): "服务信息与关键入口导航",
    ("get", "/health"): "检查 PostgreSQL 与 GraphDB 连通性",
    ("get", "/patients"): "检索并分页列出患者",
    ("get", "/patients/{pid}"): "获取患者全景数据返回体",
    ("get", "/patients/{pid}/care-chain"): "获取患者完整照护链",
    ("get", "/patients/{pid}/assessment"): "获取阈值判定与逐字出处",
    ("get", "/patients/{pid}/risk"): "获取规则式定性风险分层",
    ("get", "/patients/{pid}/safety"): "获取用药安全信号",
    ("post", "/patients/{pid}/simulate"): "按路径患者号执行确定性病程推演",
    ("post", "/simulate"): "按请求体患者号执行确定性病程推演",
    ("get", "/query/templates"): "列出参数化查询模板白名单",
    ("post", "/query/{template}"): "对指定患者运行参数化模板",
    ("get", "/agent/manifest"): "获取智能体能力清单与调用顺序",
    ("get", "/graph/concepts"): "将表面形式解析为准确 IRI",
    ("get", "/graph/node"): "获取图节点邻接摘要",
    ("get", "/graph/neighbors"): "展开图节点一跳邻居",
    ("get", "/graph/taxonomy"): "查询概念的上位或下位层次",
    ("get", "/graph/path"): "在两个节点间执行受控 BFS",
    ("get", "/graph/schema"): "获取 RDF、SQL 与桥接 schema 卡片",
    ("get", "/graph/provenance"): "反向追踪结论的支撑链与原始行",
    ("post", "/graph/sparql"): "执行通过静态检查的只读 SPARQL",
    ("get", "/graph/passages"): "检索可逐字引用的出处",
    ("get", "/graph/rules"): "检索并内省规则",
    ("get", "/graph/rules/{rule_id}"): "获取单条规则及完整出处",
    ("get", "/adjudicate/scope"): "获取可裁决与不可裁决范围",
    ("post", "/adjudicate/citations"): "裁决引用是否逐字成立",
    ("post", "/adjudicate/claim"): "裁决结构化患者结论",
    ("get", "/terms/unmapped"): "列出未映射或不可用术语",
    ("get", "/terms/explain"): "解释术语为何查不到或不可判定",
    ("get", "/demo/compare"): "比较字符串匹配与本体方法",
}


# 工具面描述。这里的文本是**工具注册的唯一说明来源** —— 大量注册平台在把工具交给模型
# 之前先按「名称 + description」做一轮检索，system prompt 在那一步是看不见的。
# 所以工具之间的边界必须写在这里，而不是只写在 docs/AGENT-PROMPT.md 里。
#
# 三段式约定：正文说「什么时候用」，【不要用于】划掉相邻工具的地盘，【前置】点名必须先调谁。
# 患者族 5 个和图探索族 4 个语义高度相邻，是选错工具的主要失分点，必须逐个写清负向边界。
#
# 有值即覆盖运行时 docstring 生成的 description；docstring 面向读代码的人，这里面向模型。
DESCRIPTIONS: dict[tuple[str, str], str] = {
    ("get", "/"): (
        "服务入口导航：服务名、版本和关键端点。\n\n"
        "【不要用于】查两侧依赖是否连通（用「检查 PostgreSQL 与 GraphDB 连通性」）；"
        "查有哪些能力、按什么顺序调用、什么不许做（用「获取智能体能力清单与调用顺序」）。"
    ),
    ("get", "/health"): (
        "PostgreSQL 与 GraphDB 连通性、两侧数据量、当前 graphVersion。\n\n"
        "会话内第一次做业务分析前先调一次。`ok=false` 时停止依赖故障侧的分析，"
        "如实报出是 postgres 还是 graphdb 出错，**不要用常识生成替代结论**。\n"
        "同一会话内 graphVersion 若发生变化，此前拿到的术语映射、规则和结论全部作废，必须重查。\n\n"
        "【不要用于】查端点清单、调用顺序与禁令（用「获取智能体能力清单与调用顺序」）。"
    ),
    ("get", "/patients"): (
        "SQL 侧检索。分页与筛选都在这里做完 —— SPARQL 只处理收敛后的小集合。\n\n"
        "【用于】不知道患者编号，或需要按 ICD-10、事实来源、风险档位筛选和分页。\n"
        "【不要用于】在图里扫患者；已知单个编号问病情（直接用患者族对应工具）。"
    ),
    ("get", "/patients/{pid}"): (
        "患者全景数据返回体：患者与事实来源、数据质量提示、断言事实、推断事实、"
        "逐字出处、未映射术语、风险分层与照护链。\n\n"
        "【用于】用户问「整体情况」「这个患者怎么样」，且不确定需要哪一段。\n"
        "【不要用于】只问时间线（用「获取患者完整照护链」）、只问阈值判定或诊断依据"
        "（用「获取阈值判定与逐字出处」）、只问风险档位（用「获取规则式定性风险分层」）、"
        "只问用药安全（用「获取用药安全信号」）—— 本工具返回体积最大，会淹没重点。\n"
        "【前置】需要患者业务编号；不知道编号先用「检索并分页列出患者」。"
    ),
    ("get", "/patients/{pid}/care-chain"): (
        "单个患者的照护链：就诊 → 检验 → 诊断 → 用药的时间线与关联关系。\n\n"
        "【用于】「这个患者经历了什么」「什么时候查的」「在用什么药」。\n"
        "【不要用于】阈值判定（用「获取阈值判定与逐字出处」）、风险档位"
        "（用「获取规则式定性风险分层」）、用药安全信号（用「获取用药安全信号」）。\n"
        "【前置】需要患者业务编号；不知道编号先用「检索并分页列出患者」。"
    ),
    ("get", "/patients/{pid}/assessment"): (
        "阈值判定 + 所用阈值区间 + 逐字出处 + sha256。\n\n"
        "⚠️ 诊断级切点 `confirmationRequired=true` 时，单次检验落在区间内 **≠ 确诊**；"
        "`verificationStatus=\"Provisional\"` 和 `caveat` 必须原样保留，不得升级成确诊。\n"
        "【不要用于】风险档位（用「获取规则式定性风险分层」）、时间线（用「获取患者完整照护链」）。\n"
        "【前置】需要患者业务编号；不知道编号先用「检索并分页列出患者」。"
    ),
    ("get", "/patients/{pid}/risk"): (
        "风险分层。⚠️ 规则式定性分层，不含概率、不含发生率、不含时间窗；"
        "`tier` 是有序枚举，不是分数，也不是模型置信度。\n\n"
        "`Insufficient-Evidence` 既不是 Low，也不是「无风险」，更不是系统故障 —— "
        "必须连同 `insufficientReason` 一起说明。`countedInTier=false` 的因子可以列出，"
        "但要讲明它不参与档位计算及其出处缺口。\n"
        "【不要用于】阈值判定或诊断依据（用「获取阈值判定与逐字出处」）、"
        "用药安全（用「获取用药安全信号」）。\n"
        "【前置】需要患者业务编号；不知道编号先用「检索并分页列出患者」。"
    ),
    ("get", "/patients/{pid}/safety"): (
        "用药安全信号：禁忌、肾功能相关警示等，附规则号与逐字出处。\n\n"
        "⚠️ 只输出信号，**不输出剂量、不推荐药物、不做个体化治疗决策** —— "
        "schema 层面就没有剂量字段。\n"
        "【不要用于】回答「该用什么药」「用多少」（本服务不回答）；"
        "阈值判定（用「获取阈值判定与逐字出处」）。\n"
        "【前置】需要患者业务编号；不知道编号先用「检索并分页列出患者」。"
    ),
    ("get", "/query/templates"): (
        "参数化查询模板白名单。\n\n"
        "【前置】执行模板前必须先读本清单 —— **不要猜模板名**，不在白名单内的模板会被拒绝。\n"
        "【用于】跨患者对照、最新检验、诊断证据、风险因子、照护链明细等行级结构化查询的前一步。"
    ),
    ("get", "/graph/node"): (
        "节点邻接摘要：类型（标出哪些是推理机推的）、所在图、出边/入边 + 计数。\n\n"
        "⚠️ 拒绝 `urn:dmo:data` 里的反例夹具，并说明原因 —— 悄悄过滤等于静默少返。\n"
        "【用于】拿到 IRI 之后的第一跳：看清类型和有哪些谓词可走，再决定下一步。\n"
        "【不要用于】展开某个具体关系的全部邻居（用「展开图节点一跳邻居」）、"
        "查上位/下位类（用「查询概念的上位或下位层次」）。\n"
        "【前置】必须已有准确 IRI —— 先用「将表面形式解析为准确 IRI」，**不要自己拼 IRI**。"
    ),
    ("get", "/graph/neighbors"): (
        "沿一个明确谓词展开一跳邻居，可指定方向 out/in。\n\n"
        "【不要用于】查上位/下位类（用「查询概念的上位或下位层次」）、"
        "查两个节点如何连通（用「在两个节点间执行受控 BFS」）、"
        "只想看节点类型和邻接概览（用「获取图节点邻接摘要」，更省）。\n"
        "【前置】必须已有准确 IRI —— 先用「将表面形式解析为准确 IRI」；"
        "不接受自然语言术语，**不要自己拼 IRI**（拼错查出来是空集，和「没有数据」长得一模一样）。"
    ),
    ("get", "/graph/taxonomy"): (
        "类层次 —— 同时是 owl2-rl 推理产物的展示面。\n\n"
        "`inferenceNotice` 会指出哪几条边不在任何文件里写着、是推出来的。\n"
        "【不要用于】展开非层次关系（用「展开图节点一跳邻居」）、"
        "任意两点之间的连通性（用「在两个节点间执行受控 BFS」）。\n"
        "【前置】必须已有准确 IRI —— 先用「将表面形式解析为准确 IRI」。"
    ),
    ("get", "/graph/path"): (
        "两个节点之间怎么连上的。服务端做双向受控 BFS，不放任意长度属性路径出去。\n\n"
        "【不要用于】只想看某个节点周边（用「获取图节点邻接摘要」或「展开图节点一跳邻居」）；"
        "结论的证据溯源（用「反向追踪结论的支撑链与原始行」，那条路径是专用的）。\n"
        "【前置】**起点和终点都**必须是已确认的准确 IRI。"
    ),
    ("get", "/graph/provenance"): (
        "反向溯源：推断产物 → 支撑链 → 指南原文 → SQL 原始行。\n\n"
        "「推理」与「可核查」两个亮点在这里合流。`brokenLinks` 与 `chain` 同等重要 ——\n"
        "只报走通的环节等于在暗示「这条结论有出处」。\n"
        "【用于】用户追问某条结论「凭什么」。\n"
        "【前置】需要**真实的结论 IRI**（Assessment / Diagnosis / RiskFactorHit）。"
        "患者摘要接口不一定返回结论 IRI；拿不到时用「执行通过静态检查的只读 SPARQL」查出来，"
        "**绝不能根据患者号、规则号或哈希算法自行猜造 IRI**。"
    ),
    ("get", "/terms/unmapped"): (
        "全库未映射与不可用术语总表 —— 系统主动记账的覆盖面缺口，不是错误日志。\n\n"
        "【用于】盘点「哪些术语这个系统判不了」。\n"
        "【不要用于】解释某一个具体术语为什么查不到或判不了"
        "（用「解释术语为何查不到或不可判定」）。"
    ),
}


# 不注册为智能体工具的路由。端点本身照常运行、docs/API.md 照常记录，
# 只是不进 openapi.json —— 这份文档就是工具注册面，多一个等价工具就是多一次抛硬币。
AGENT_TOOL_EXCLUDED: dict[tuple[str, str], str] = {
    # 与 POST /patients/{pid}/simulate 功能完全相同，只差 patientId 在 body 还是 path。
    # 保留路径版：与患者族其余 5 个工具一致按 pid 寻址，且请求体没有 patientId/pid 别名的 anyOf。
    ("post", "/simulate"): "与 POST /patients/{pid}/simulate 等价；仅保留路径版以消除选择噪声。",
    # 方法对照演示，面向人看 demo，不是患者问答链路的一环。
    ("get", "/demo/compare"): "演示用途，不属于生产问答链路。",
}


def _request_ref(name: str) -> dict[str, Any]:
    return {
        "required": True,
        "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{name}"}}},
    }


def build_schema() -> dict[str, Any]:
    schema = deepcopy(app.openapi())
    schema["info"]["description"] = (
        "糖尿病本体与患者事实库融合查询 API。技术验证用途，不是医疗器械，"
        "不构成医疗建议。无鉴权、无限流，仅应部署在可信内网或本机。"
    )
    schema["servers"] = [
        {"url": "http://124.223.18.44:8100", "description": "远程调试服务"},
    ]
    schema["security"] = []
    schema["tags"] = [
        {"name": "Service", "description": "服务入口与健康状态。"},
        {"name": "Patients", "description": "患者检索及融合查询。"},
        {"name": "Simulation", "description": "确定性条件推演，不是概率预测。"},
        {"name": "Query templates", "description": "受控参数化 SPARQL 模板。"},
        {"name": "Agent discovery", "description": "供智能体自举的能力清单。"},
        {"name": "Graph exploration", "description": "受控图探索、规则与溯源。"},
        {"name": "Adjudication", "description": "引用和结构化结论裁决。"},
        {"name": "Terminology", "description": "术语缺口与映射状态。"},
        {"name": "Demo", "description": "方法对照演示。"},
    ]
    schema.setdefault("components", {}).setdefault("schemas", {}).update(SCHEMAS)

    # The root route is intentionally hidden from Swagger UI, but API.md documents
    # it and integration consumers benefit from discovering it.
    schema["paths"] = {
        "/": {
            "get": {
                "tags": ["Service"],
                "summary": SUMMARIES[("get", "/")],
                "operationId": "getServiceInfo",
                "responses": {
                    "200": {
                        "description": "服务名称、版本和关键入口。",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        },
        **schema["paths"],
    }

    for path, path_item in schema["paths"].items():
        tag = next((value for prefix, value in TAG_BY_PREFIX.items() if path.startswith(prefix)), None)
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            if tag:
                operation["tags"] = [tag]
            operation["summary"] = SUMMARIES.get((method, path), operation.get("summary", ""))
            description = DESCRIPTIONS.get((method, path))
            if description:
                operation["description"] = description
            for parameter in operation.get("parameters", []):
                description = PARAMETER_DESCRIPTIONS.get((path, parameter["name"]))
                if description:
                    parameter["description"] = description
            if "requestBody" in operation:
                description = REQUEST_BODY_DESCRIPTIONS.get((method, path))
                if description:
                    operation["requestBody"]["description"] = description
            responses = operation.setdefault("responses", {})
            if path.startswith(("/patients/", "/graph", "/adjudicate")) or path in {
                "/simulate",
                "/query/{template}",
            }:
                responses.setdefault("400", {
                    "description": "业务拒绝或请求不满足执行条件。",
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                })
            if (
                "{pid}" in path
                or path in {
                    "/simulate",
                    "/adjudicate/claim",
                    "/query/{template}",
                    "/graph/rules/{rule_id}",
                }
            ):
                responses.setdefault("404", {
                    "description": "患者、模板或资源不存在。",
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                })
            if path.startswith(("/graph", "/patients", "/adjudicate")):
                responses.setdefault("503", {
                    "description": "GraphDB 暂时不可用。",
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                })

    schema["paths"]["/simulate"]["post"]["tags"] = ["Simulation"]
    schema["paths"]["/patients/{pid}/simulate"]["post"]["tags"] = ["Simulation"]

    schema["paths"]["/simulate"]["post"]["requestBody"] = _request_ref("StaticSimulationRequest")
    schema["paths"]["/patients/{pid}/simulate"]["post"]["requestBody"] = _request_ref(
        "SimulationRequest"
    )
    schema["paths"]["/graph/sparql"]["post"]["requestBody"] = _request_ref("SparqlRequest")
    schema["paths"]["/adjudicate/citations"]["post"]["requestBody"] = _request_ref(
        "CitationsRequest"
    )
    schema["paths"]["/adjudicate/claim"]["post"]["requestBody"] = _request_ref(
        "ClaimAdjudicationRequest"
    )
    for (method, path), description in REQUEST_BODY_DESCRIPTIONS.items():
        schema["paths"][path][method]["requestBody"]["description"] = description

    # Constraints explicitly documented in docs/API.md.
    patients_params = schema["paths"]["/patients"]["get"]["parameters"]
    for parameter in patients_params:
        if parameter["name"] == "origin":
            parameter["schema"]["enum"] = ["ehr-legacy", "derived", "demo-cohort"]
        elif parameter["name"] == "tier":
            parameter["schema"]["enum"] = [
                "High",
                "Moderate",
                "Low",
                "Insufficient-Evidence",
            ]
        elif parameter["name"] == "page":
            parameter["schema"]["minimum"] = 1
        elif parameter["name"] == "size":
            parameter["schema"].update({"minimum": 1, "maximum": 200})

    enum_parameters = {
        ("/graph/neighbors", "direction"): ["out", "in"],
        ("/graph/taxonomy", "direction"): ["up", "down"],
        ("/graph/schema", "section"): ["rdf", "sql", "bridge"],
        ("/graph/rules", "kind"): ["threshold", "target", "risk"],
    }
    for (path, name), values in enum_parameters.items():
        for parameter in schema["paths"][path]["get"]["parameters"]:
            if parameter["name"] == name:
                parameter["schema"]["enum"] = values

    operations = {
        (method, path)
        for path, path_item in schema["paths"].items()
        for method, operation in path_item.items()
        if isinstance(operation, dict) and "responses" in operation
    }
    missing = operations - REQUEST_EXAMPLES.keys()
    stale = REQUEST_EXAMPLES.keys() - operations
    if missing or stale:
        raise RuntimeError(f"测试样例与 API 路由未对齐：missing={missing}, stale={stale}")

    undocumented_parameters = [
        (method, path, parameter["name"])
        for method, path in operations
        for parameter in schema["paths"][path][method].get("parameters", [])
        if not parameter.get("description")
    ]
    undocumented_bodies = [
        (method, path)
        for method, path in operations
        if "requestBody" in schema["paths"][path][method]
        and not schema["paths"][path][method]["requestBody"].get("description")
    ]
    if undocumented_parameters or undocumented_bodies:
        raise RuntimeError(
            "OpenAPI 参数说明不完整："
            f"parameters={undocumented_parameters}, requestBodies={undocumented_bodies}"
        )

    # 工具选择准确率主要由 description 决定：注册平台常常先按「名称 + description」检索，
    # 再把候选交给模型。summary 只有 7–27 个字，撑不起相邻工具之间的边界。
    undocumented_operations = sorted(
        (method, path)
        for method, path in operations
        if not (schema["paths"][path][method].get("description") or "").strip()
    )
    if undocumented_operations:
        raise RuntimeError(
            "以下操作缺少工具面 description，模型只能靠 summary 猜用途："
            f"{undocumented_operations}"
        )

    for (method, path), example in REQUEST_EXAMPLES.items():
        operation = schema["paths"][path][method]
        operation["x-test-example-title"] = example["title"]
        query_values = example.get("query", {})
        path_values = example.get("path", {})
        for parameter in operation.get("parameters", []):
            source = path_values if parameter["in"] == "path" else query_values
            if parameter["name"] in source:
                parameter["example"] = source[parameter["name"]]
        if "body" in example:
            operation["requestBody"]["content"]["application/json"]["example"] = example["body"]

    # 下线放在最后：上面所有对齐校验仍覆盖全部真实路由，只有最终产出的注册面变窄。
    for (method, path), reason in AGENT_TOOL_EXCLUDED.items():
        if path not in schema["paths"] or method not in schema["paths"][path]:
            raise RuntimeError(f"下线清单与实际路由不符：{method.upper()} {path}")
        del schema["paths"][path][method]
        if not schema["paths"][path]:
            del schema["paths"][path]
        print(f"excluded {method.upper()} {path} —— {reason}")

    _prune_unreferenced_schemas(schema)
    return schema


def _prune_unreferenced_schemas(schema: dict[str, Any]) -> None:
    """删除下线后不再被任何路径引用的组件，避免注册面留下悬空定义。"""
    components = schema.get("components", {}).get("schemas", {})
    while True:
        referenced = {
            ref.rsplit("/", 1)[-1]
            for ref in _iter_refs(schema["paths"])
        } | {
            ref.rsplit("/", 1)[-1]
            for name, definition in components.items()
            for ref in _iter_refs(definition)
        }
        orphans = sorted(set(components) - referenced)
        if not orphans:
            return
        for name in orphans:
            del components[name]
            print(f"pruned unreferenced schema {name}")


def _iter_refs(node: Any):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                yield value
            else:
                yield from _iter_refs(value)
    elif isinstance(node, list):
        for value in node:
            yield from _iter_refs(value)


def build_http_examples() -> str:
    lines = [
        "# API 调试样例",
        "# 可用 VS Code REST Client、JetBrains HTTP Client 或兼容工具直接执行。",
        "# 数据来自演示队列、ontology seed 和自动化回归测试。",
        "# 默认请求远程服务：http://124.223.18.44:8100",
        "",
        "@baseUrl = http://124.223.18.44:8100",
        "",
    ]
    for index, ((method, route), example) in enumerate(REQUEST_EXAMPLES.items(), start=1):
        target = route
        for name, value in example.get("path", {}).items():
            target = target.replace("{" + name + "}", str(value))
        if query := example.get("query"):
            target += "?" + urlencode(query)

        lines.extend([
            "###",
            f"# {index:02d}. {example['title']}",
            f"{method.upper()} {{{{baseUrl}}}}{target}",
            "Accept: application/json",
        ])
        if "body" in example:
            lines.extend([
                "Content-Type: application/json",
                "",
                json.dumps(example["body"], ensure_ascii=False, indent=2),
            ])
        lines.append("")
    return "\n".join(lines)


AGENT_PROMPT = ROOT / "docs" / "AGENT-PROMPT.md"


def check_agent_prompt(schema: dict[str, Any]) -> None:
    """system prompt 里出现的每个工具名都必须真实注册。

    平台按 ``summary`` 注册工具，prompt 却写 ``operationId``（或写了个已下线的工具）——
    模型会去调一个不存在的名字，然后从可用列表里挑个近似的。这类分叉不会报错，
    只会静默拉低准确率，所以在导出时就卡住。

    只查「引用的名字存不存在」，**不查 prompt 有没有列全**：工具清单由注册面本身提供，
    prompt 里再抄一份目录只会变成第二个真相源，也就是下一次分叉的起点。
    """
    import re

    if not AGENT_PROMPT.exists():
        return
    registered = {
        operation["summary"]
        for path_item in schema["paths"].values()
        for operation in path_item.values()
    }
    text = AGENT_PROMPT.read_text(encoding="utf-8")
    unknown = sorted(set(re.findall(r"「([^」]+)」", text)) - registered)
    if unknown:
        raise RuntimeError(
            f"docs/AGENT-PROMPT.md 引用了未注册的工具名：{unknown}。"
            "工具名取自 OpenAPI 的 summary 字段，改名时两边必须一起改。"
        )


def main() -> None:
    schema = build_schema()
    check_agent_prompt(schema)
    OUTPUT.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    HTTP_EXAMPLES_OUTPUT.write_text(build_http_examples(), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    print(f"wrote {HTTP_EXAMPLES_OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
