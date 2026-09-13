# Project Analysis

> 分析日期：2026-08-21  
> 分析范围：当前仓库内的 README、设计/计划/API 文档、Python 后端、CLI、SQL DDL、RDF/OWL/Turtle、本体构建与抽取工具、SPARQL 规则、SHACL shapes、Prompt、Codex skills、测试、Docker/Compose、部署样例、种子数据，以及被 `.gitignore` 排除但存在于工作区的 `demo/`。  
> 证据口径：优先采用可执行代码、数据模型、规则和实测结果；只有文档或注释、没有对应实现的内容单独标记。  
> 安全定位：这是技术验证/学习项目，不是医疗器械，不构成诊断、治疗或用药建议。

## 1. Executive Summary

该项目是一个以糖尿病为领域载体的、可解释且强调证据边界的语义推理后端。它把医院关系型患者事实、人工策展的术语映射、OWL/RDF 领域模型、SPARQL 规则、SHACL 约束和指南原文出处组织成一条可复现的数据与推理链，并通过 CLI 和 FastAPI 暴露给人或外部 Agent 使用。

项目真正成熟的部分不是“聊天机器人”，而是 **Ontology Build Pipeline + Ontology/Graph + Patient Facts + Deterministic Reasoning + Provenance API**：

- `ontology/tools/` 把图模型、TXT/PDF 语料和人工 seed 编译、抽取、校验并装载为可运行的本体知识库。
- PostgreSQL 负责上游快照、患者筛选、术语映射、标准化事实和推理结果投影。
- GraphDB 负责知识图、每患者命名图、OWL-RL 物化结果与 SPARQL 规则产物。
- FastAPI/CLI 负责提供固定查询、图探索、出处核验、结论裁决和条件推演。
- `src/skills/` 和 `/agent/manifest` 为外部 Agent 提供调用规范与边界。

仓库名称中虽然有 “agent”，但当前仓库 **没有内置运行时 LLM Agent**：不存在 `src/dmo/agent/`、ReAct/tool loop、`dmo ask` 或“纯 LLM vs ontology agent”评测运行器。正式运行时 `src/dmo/` 中没有模型调用；唯一的 OpenAI 兼容调用位于离线知识抽取工具 `ontology/tools/semantic_extract.py`。因此更准确的产品表述是：

> **一个面向外部 Agent 的糖尿病语义推理与证据服务，而不是一个已经内置对话 Agent 的成品。**

最有价值的工程主张是“知道自己不知道”：不可信数值被可信度门禁隔离；缺单位、未知术语、无来源规则、单次异常、无患者事实和查询空集分别进入不同的显式状态，而不是被统一包装成一个看似确定的答案。

### 当前验证状态

本次在当前工作区实际执行：

| 检查 | 结果 | 可得结论 |
|---|---:|---|
| `.venv/bin/python -m pytest -q` | `19 passed, 155 skipped` | SPARQL guard 的无外部依赖单测通过；大量 API/GraphDB/PG/推演集成测试因服务不可用而跳过，不能宣称全量测试通过 |
| `demo` Node 测试 | `1 passed` | 只能证明静态演示页文件与交互骨架存在，不证明演示数据或指标真实 |
| `verify_passages.py` | 31/31 逐字命中且哈希一致 | 31 条 `SourcePassage` 的逐字出处链有直接可执行证据 |
| `validate_shacl.py` | 失败：12 条违规，10 条已知、2 条新增 | SHACL 门禁已实现，但当前数据集并非全绿 |
| `ruff check` | 43 个问题 | 当前代码质量门禁并非全绿；多数为格式/可执行位/现代化规则，但仍应如实披露 |

## 2. Problem

### 2.1 业务问题

医院患者数据与指南知识之间存在结构和语义断层：

1. 关系型数据里只有本地中文项目名、编码和业务主键，指南知识使用标准概念、阈值、上下文和来源。
2. 医疗数据可能缺单位、错单位、主子表语义错位、值不可信或关键指标完全缺失。
3. 单纯字符串匹配能“连上”概念，却无法证明数值是否可比、阈值是否适用、结论是否需要复测、来源是否真实。
4. 纯生成式回答容易把“未知”说成“没有”、把单次异常说成确诊、把规则式分层说成概率，或引用并不存在的指南原话。

仓库记录的真实上游现状包括：400 名患者、1600 条检验，只有 15 个 E11 患者；全库没有可用 HbA1c 数值；检验值集中在 0–25 且无单位列；329/400 个生日在未来；每个患者恰好一条诊断。对应证据主要来自 `README.md`、`docs/PATIENT-GRAPH-FUSION-PLAN.md`、映射 CSV，以及 `tests/test_scenarios.py::test_real_ehr_patients_are_all_insufficient_evidence`。这些计数依赖曾经连接的外部数据库，本次未能重新连接验证，属于“仓库记录的实测结果”，不是本地独立复测结果。

### 2.2 技术问题

项目试图解决的不是通用医学问答，而是以下可判定问题：

- 某次可信且单位规范的检验值落在哪个开/闭区间？
- 单次异常是否只能形成 `Provisional`，何时能升级为 `Confirmed`？
- 患者事实是否命中明确建模的用药安全条件或风险规则？
- 结论使用了哪条规则、哪个患者事实、哪个 SQL 行和哪段逐字来源？
- 如果调用方明确注入一个假设检验值，结论会发生什么确定性变化？
- 外部报告中的引用和结构化结论是否与本仓库当前知识版本一致？

项目明确不解决：概率预测、自然病程外推、剂量推荐、临床合理性背书、通用诊疗决策、自动补齐未知术语和无限知识覆盖。

## 3. Target Users

从代码与文档可以推断出四类主要用户：

1. **医疗知识工程师/本体工程师**：维护 OWL、Turtle、SPARQL 规则、SHACL 和来源片段；主要入口为 `ontology/src/`、`ontology/rules/`、`ontology/shapes/`、`ontology/tools/`。
2. **医疗数据工程师/平台工程师**：负责医院库只读接入、ETL、术语映射、SQL-to-RDF 投影、GraphDB 同步和部署；主要入口为 `src/dmo/db/`、`src/dmo/rdf/`、CLI 和 Compose。
3. **Agent/应用开发者**：通过 `/agent/manifest`、患者 API、图探索 API、裁决 API 和 `src/skills/` 把确定性语义能力接入外部 Agent。
4. **技术评审者、学习者与演示观众**：观察“普通字符串匹配/生成式回答”和“带规则、边界、出处的语义推理”之间的差别。

最终临床医生或患者并不是当前可直接部署的主要用户。仓库没有认证、患者授权、审计日志、临床工作流集成、监管合规或人机复核闭环，且项目明确声明不是医疗器械。

## 4. Core Use Cases

### 4.1 本体知识库搭建与持续校验

`ontology/tools/` 不是零散脚本集合，而是一条从“领域 schema + 指南语料”到“可装载、可推理、可审计知识库”的构建流水线：

1. `build_tbox.py` 读取 `ontology/graph/diabetes-ontology-v2.json`，生成 OWL TBox，避免图设计文件与运行时 schema 靠人工重复维护。
2. `source_registry.py` 扫描本地知识文件，机械计算文件 SHA-256、发布机构、年份和正文状态，生成 `ontology/dist/sources.ttl`；这一阶段不调用 LLM，也不猜不存在的来源 URL。
3. `semantic_extract.py` 把 TXT/PDF 切分后按 schema 做结构化抽取，保留 raw、validated、report 等中间产物；只有实体/关系抽取阶段使用 OpenAI-compatible tool calling。
4. 抽取 policy 把 `DiagnosticThreshold`、`GlycemicTarget` 等高危数值常量设为 `manual`，把 `GuidelineSource` 设为 `registry`，避免让 LLM 自由生成临床切点和来源身份。
5. `build_playground_rdf.py` 生成可供外部 Ontology Playground/Fabric IQ 使用的 RDF/XML，并执行对应的结构校验。
6. `load_graphdb.py` 创建 GraphDB 仓库、按命名图幂等 PUT TBox/seed/sources/extract 图、按顺序运行 SPARQL CONSTRUCT 规则，并执行验收查询。
7. `validate_shacl.py` 汇总 TBox、seed、抽取图和患者图执行闭世界校验，并以 `known-violations.tsv` 的“focusNode + message”基线识别新增缺陷。
8. `verify_passages.py` 将可信 `SourcePassage.quote` 逐字回查本地原文并复算 SHA-256；本次实际验证 31/31 条通过。

这条流水线的关键价值是：**知识库不是一次性手工画出来的静态图，而是可以重建、版本化、质量门禁和追责的工程制品。**

代码证据：`ontology/tools/*.py`、`ontology/tools/README.md`、`ontology/graph/diabetes-ontology-v2.json`、`ontology/src/*.ttl`、`ontology/rules/*.rq`、`ontology/shapes/*.ttl`。

### 4.2 患者事实融合查询

- `GET /patients` 在 PostgreSQL 中按 ICD-10、事实来源、演示场景、风险档位分页筛选。
- `GET /patients/{pid}` 返回 care chain、风险分层、断言事实、推断事实、来源、未映射项、数据质量通知和免责声明。
- 分段端点包括 `/care-chain`、`/assessment`、`/risk`、`/safety`、`/recommendations` 和 `/monitoring-due`。

代码证据：`src/dmo/api.py`，`src/dmo/query/hybrid.py::find_patients/patient_bundle`，`src/dmo/query/guidance.py`。

### 4.3 阈值、诊断与上下文规则

- 可信检验值与 `DiagnosticThreshold` 做单位、上下文和开闭区间匹配。
- `confirmationRequired=true` 时按不同日期计数，单日为 `Provisional`，至少两日才为 `Confirmed`。
- 妊娠与非妊娠阈值分离；无法取得妊娠记录时显式标注 `NonPregnant(assumed)`。
- 诊断切点与管理目标分开，避免把 A1C 诊断阈值当作治疗目标。

代码证据：`ontology/rules/20-lab-assessment.rq`、`21-target-attainment.rq`、`30-diagnosis-from-assessment.rq`、`ontology/src/dmo-threshold-seed.ttl`、`tests/test_scenarios.py`。

### 4.4 确定性条件推演

调用方显式提交 `{term, value, unit, date}`；服务在内存 RDF Dataset 中分别运行“原患者图”和“患者图 + 假设事实”，返回 before/after、结论级 delta、推导树和 `derivationHash`。

代码证据：

- API：`POST /simulate`、`POST /patients/{pid}/simulate`。
- 编排：`src/dmo/simulate/runner.py::simulate`。
- 沙箱：`src/dmo/simulate/sandbox.py`。
- 规则执行与 diff：`src/dmo/simulate/engine.py::run_rules/collect/diff`。
- 可复现哈希：`src/dmo/simulate/hashing.py::derivation_hash`。
- 假设/实测分离：`src/dmo/simulate/tree.py`。

这是条件蕴含“若 X 则 Y”，不是预测“X 将发生”。系统不生成假设数值。

### 4.5 图探索与反向溯源

API 提供概念检索、节点摘要、一跳邻居、分类层级、有限跳数路径、schema card、规则内省、出处检索和结论反向溯源。

关键函数：

- `src/dmo/graph/explore.py::search_concepts/node/neighbors/taxonomy/path`
- `src/dmo/graph/provenance.py::trace`
- `src/dmo/graph/schema_card.py::card`
- `src/dmo/graph/rules.py::search/get`
- `src/dmo/graph/passages.py::search`

### 4.6 外部引用与结论裁决

- `POST /adjudicate/citations` 把引用分成 `verbatim`、`hash-only`、`quote-only`、`not-verbatim`、`fabricated`。
- `POST /adjudicate/claim` 把结构化结论分成 `supported`、`contradicted`、`unsupported`、`not-adjudicable`。
- `GET /adjudicate/scope` 显式声明可以和不可以裁决的范围。

代码证据：`src/dmo/adjudicate/citations.py::check_citations`、`claim.py::adjudicate_claim`、`scope.py::describe_scope`。

“supported”仅表示与当前仓库规则一致，不表示临床正确或适用于具体患者。

### 4.7 术语缺口解释和普通实现对照

- `GET /terms/explain`/`dmo explain` 区分 `verified`、`candidate`、`unmappable`、`no-source-data`。
- `GET /demo/compare`/`dmo demo compare` 对比 `semantic_link` 的字符串匹配与本项目的单位/阈值/出处约束。

代码证据：`src/dmo/query/hybrid.py::explain_gap`、`src/dmo/terms/wfs.py::compare`、`src/dmo/db/seed/lab_term_map.csv`。

## 5. System Architecture

### 5.1 逻辑架构

```text
领域图模型 diabetes-ontology-v2.json       本地 TXT/PDF 指南语料
        │ build_tbox.py                         │ source_registry.py
        │                                       │ semantic_extract.py
        └───────────────┬───────────────────────┘
                        ▼
             OWL TBox + seed + sources + extract 图
                        │ SHACL / passage hash / GraphDB verify
                        ▼
                  GraphDB 知识层
                        ▲
                        │
医院 PostgreSQL hospital_zd / patient_analysis（只读）
        │ 6 张白名单表、会话 READ ONLY、基线指纹
        ▼
PostgreSQL onto_db / diabetes
  stg_* ──映射/单位换算/可信度──> core_*
    ▲                                  │
    └──── sim_* 演示队列 ──────────────┘
                                       │ SQL-to-RDF
                                       ▼
GraphDB
  urn:dmo:tbox / seed / sources / extract:*
  urn:dmo:patient:*（每患者一命名图）
  urn:dmo:inferred（SPARQL 规则产物）
                                       │
              ┌────────────────────────┴─────────────────────┐
              ▼                                              ▼
       FastAPI / CLI                                 内存推演沙箱
  固定模板、图探索、溯源、裁决                 知识快照 + 患者图 + 假设事实
              │                                              │
              └────────────── 外部 Agent / 应用 ──────────────┘
                         `/agent/manifest` + `src/skills/`
```

### 5.2 数据存储职责

| 存储 | 职责 | 证据 |
|---|---|---|
| `hospital_zd.patient_analysis` | 原始医院事实，只读 | `src/dmo/config.py::Config.upstream_dsn`、`db/engine.py::upstream_conn` |
| `onto_db.diabetes` | staging、映射、演示数据、规范事实、预测投影、同步状态 | `src/dmo/db/ddl/*.sql`，共 30 张表 |
| GraphDB | TBox、seed、来源、抽取图、患者命名图、推断图 | `ontology/tools/load_graphdb.py`、`src/dmo/rdf/sync.py` |
| 内存 `rdflib.Dataset` | 条件推演，避免假设污染 GraphDB | `src/dmo/simulate/sandbox.py`、`runner.py` |

### 5.3 知识层分工

- **OWL/RDFS**：类层级、对象关系、函数性/互斥性和 OWL-RL 可物化关系；主要文件为 `ontology/dist/tbox-v2.ttl` 与 `ontology/src/dmo-axioms.ttl`。
- **SPARQL CONSTRUCT**：数值区间、复测确认、风险命中、风险分层、用药安全、推荐匹配和监测到期；共 10 个规则文件。
- **SHACL**：闭世界数据质量和临床安全约束；`ontology/shapes/data-quality.shacl.ttl` 与 `clinical-safety.shacl.ttl`。
- **人工 seed**：高风险阈值、目标、风险映射与可引用原文；`dmo-threshold-seed.ttl`、`dmo-risk-map.ttl`。
- **离线抽取**：从 TXT/PDF 做 schema-guided LLM 抽取，但阈值/目标等高危常量按 policy 排除在 LLM 生成之外；`ontology/tools/semantic_extract.py`。

### 5.4 对外接口

`src/dmo/api.py` 中有 33 条业务路由（含不进入 OpenAPI 的 `/`）：患者、推演、模板、Agent manifest、图探索、规则/出处、指南分歧、裁决、术语和对照演示。API 控制层刻意很薄，CLI 与 HTTP 复用底层模块。

## 6. Core Modules

| 模块 | 主要职责 | 核心证据 |
|---|---|---|
| 本体 schema 编译 | ER/图模型 JSON 编译为 OWL TBox 与 Playground RDF | `ontology/tools/build_tbox.py`、`build_playground_rdf.py` |
| 知识来源注册 | 对语料文件做哈希、机构/年份/正文状态登记，机械生成来源图 | `ontology/tools/source_registry.py` |
| schema-guided 语义抽取 | TXT/PDF 分段、结构化 LLM 抽取、span 校验、关系补全与审计产物 | `ontology/tools/semantic_extract.py` |
| 知识库装载与门禁 | 命名图 PUT、规则物化、验收查询、SHACL、逐字出处校验 | `ontology/tools/load_graphdb.py`、`validate_shacl.py`、`verify_passages.py` |
| 配置与连接守卫 | 双 DSN、密码脱敏、只读会话、schema 守卫、超时 | `src/dmo/config.py`；`db/engine.py::{GuardedConnection,upstream_conn,onto_conn}` |
| ETL 与基线 | 白名单全量快照、逐表行数核对、上游内容 MD5 基线 | `db/etl.py::{SPECS,pull_one,run}`；`db/baseline.py` |
| 术语映射 | GraphDB 概念投影、本地中文/ICD/药品映射、未映射记账、单位换算 | `terms/concepts.py`、`terms/resolve.py`、`terms/units.py`、seed CSV |
| 规范事实投影 | `stg_* + sim_* -> core_*`，按可信度和映射状态决定进入 LabResult 或 observation/unmapped | `db/projection.py` |
| SQL-to-RDF | 确定性 IRI、无空节点、PHI 字段不进入 RDF、每患者整图 | `rdf/iri.py`、`rdf/emit.py::build`、`rdf/canonical.py` |
| 图同步 | 内容哈希去重、GSP PUT 整图替换、单患者失败隔离、受限 prune | `rdf/sync.py::run` |
| 规则执行 | GraphDB 和 rdflib 两套执行路径，按数字前缀串联 | `ontology/tools/load_graphdb.py::run_rules`、`simulate/engine.py::rule_files/run_rules` |
| 融合查询 | SQL 收敛患者 + SPARQL 语义结论 + SQL 原始行/未映射/质量通知拼装 | `query/hybrid.py::patient_bundle` |
| 查询模板 | 8 个参数化 SPARQL 模板 | `query/templates.py`：`care_chain`、`assessment_evidence`、`diagnosis_evidence`、`medication_safety`、`risk_stratification`、`latest_lab_result`、`recommendation_match`、`monitoring_due` |
| 图探索与溯源 | 受控图原语、规则/出处索引、SQL 行回查、断链显式报告 | `graph/*.py` |
| SPARQL guard | 写操作拒绝、患者图守卫、知识图误用拒绝、LIMIT 改写、全库扫描告警、零结果探针 | `graph/guard.py`、`tests/test_guard.py` |
| 条件推演 | 知识快照、假设解析、两轮规则、结论 diff、推导树、确定性哈希 | `simulate/*.py` |
| 裁决 | 引文双线核对、结构化 claim 比对、能力边界 | `adjudicate/*.py` |
| API 与 CLI | 统一门面和运维命令 | `api.py`、`cli.py` |
| Agent 使用契约 | 外部 Agent 的调用顺序、报告契约和禁令 | `src/skills/*`、`src/prompts/query_execution_plan.md`、`manifest.py` |
| 本体工具链 | TBox 构建、来源注册、语义抽取、GraphDB 装载、SHACL 校验、出处核验 | `ontology/tools/*.py` |

## 7. Data Flow

### 7.1 从领域模型与指南语料到本体知识库

1. 领域设计以 `ontology/graph/diabetes-ontology-v2.json` 表达实体、属性、关系、枚举和基数。
2. `build_tbox.py` 将其编译为 `ontology/dist/tbox-v2.ttl`，再叠加人工维护的 `dmo-axioms.ttl`、阈值 seed 和风险映射。
3. `source_registry.py` 为语料文件生成内容哈希和来源元数据；知识文件变化因此具有明确的重建触发条件。
4. `semantic_extract.py` 读取 TXT/PDF，执行 prepare → chunk → plan → extract → validate → link → emit/report。LLM 原始结果与校验后结果分开保存，可用 `--from-raw` 在不重复消耗模型调用的情况下重跑确定性阶段。
5. 高风险类型由 schema policy 分流：临床阈值/目标走人工 seed，来源走机械 registry，只有适合抽取的实体/关系进入 LLM 阶段。
6. `verify_passages.py` 对可信引文执行逐字和哈希校验；`validate_shacl.py` 对合并知识图执行闭世界约束并比较违规基线。
7. `load_graphdb.py` 将 TBox、seed、sources 和每份文档的 extract 结果写入不同命名图，再执行规则并把产物写入 `urn:dmo:inferred`。
8. GraphDB 验收查询检查类数量、OWL-RL 推理探针、V1 废弃谓词、阈值出处完整性、抽取空壳图、悬空风险映射和规则产物。

最终产物既包含“知识是什么”，也包含“来自哪个文件、哪次抽取、哪条原文、通过了哪些校验”。

### 7.2 从医院库到可查询患者图

1. `config.load()` 读取上游 PostgreSQL、ontology PostgreSQL 和 GraphDB 配置。
2. `db.engine.upstream_conn()` 把上游连接设置为 `READ ONLY`，并限定 `patient_analysis` search path。
3. `db.etl.run()` 只读取 `SPECS` 白名单中的 6 张表，去掉 PHI 未列入的字段，完整重建 `stg_*`。
4. ETL 后逐表核对上游/目标行数；`db.baseline.check()` 用整行排序 MD5 检测上游是否变化。
5. `terms.resolve` 装载人工映射；`db.projection.run()` 把 `stg_*` 与 `sim_*` 投影到 `core_*`，执行单位换算、可信度门禁和未映射记账。
6. `rdf.emit.build()` 为每个患者生成无 blank node 的事实图；不会发射姓名、身份证、电话或推断结论。
7. `rdf.sync.run()` 计算规范图哈希；未变化则跳过，变化后用 Graph Store Protocol `PUT` 替换该患者命名图。
8. `load_graphdb.py --rules` 按序执行 SPARQL CONSTRUCT，将规则产物整体写入 `urn:dmo:inferred`。
9. `db.predict.run()` 把风险分层/因子命中投影回 PostgreSQL，服务查询无需每次重新跑整套 SPARQL。

### 7.3 一次典型患者请求

以 `GET /patients/{pid}` 为例：

1. `api.full()` 调用 `_bundle()`。
2. `hybrid.patient_bundle()` 先在 `core_patient` 确认患者存在。
3. 对 care chain、assessment、diagnosis、safety、risk 等语义段，调用 `GraphDBClient.sparql_csv()` 执行白名单模板。
4. 同时从 PostgreSQL 读取 `core_*` 的 asserted facts、`map_unmapped_term` 和数据质量说明。
5. 按患者业务号和 RDF IRI 把关系事实、推断结论、出处片段、风险投影和原始/规范值拼装为统一返回体。
6. 返回体保留 `factOrigin`、`valueTrustLevel`、`sourceValue/sourceUnit`、规则版本、逐字 quote/hash、未映射原因、质量通知和 disclaimer。

### 7.4 一次条件推演请求

1. API 校验 `assume` 是非空列表并调用 `simulate.runner.simulate()`。
2. `sandbox.load()` 从 GraphDB 只读 CONSTRUCT 患者图与知识层快照，并缓存知识层。
3. 创建新的 Dataset，运行规则链得到 `before`。
4. `hypothesis.parse()` 只接受知识层已有阈值的测试项；未知术语、缺单位、无核实换算或重复假设直接拒绝。
5. 在另一份全新 Dataset 的患者命名图中加入 `hypothetical=true`、`factOrigin=simulated` 的事实。
6. 再运行同一规则链得到 `after`，按语义键计算 `added/removed/changed`。
7. 用患者、graphVersion、知识快照、规则集和排序后的假设计算 `derivationHash`。
8. 返回 delta、推导树、before/after、假设尾注和医疗免责声明；GraphDB 不发生写入。

### 7.5 一次外部引用/结论裁决请求

1. `/adjudicate/citations` 从可信 seed 图加载 passage index，分别核对规范化 quote 与 SHA-256，避免“哈希存在但引文被改写”的漏检。
2. `/adjudicate/claim` 要求结构化 claim；按 claim 类型读取系统结论，使用语义键比对一致、冲突或无证据。
3. 返回 `graphVersion`、`rulesFingerprint`、`adjudicationHash` 和严格限定的 verdict 含义。

## 8. Technology Stack

| 层 | 技术 | 仓库证据 |
|---|---|---|
| 语言/包管理 | Python 3.11+，`uv`，Hatchling | `pyproject.toml`、`uv.lock` |
| Web API | FastAPI、Uvicorn | `src/dmo/api.py`、`pyproject.toml[serve]` |
| 关系数据库 | PostgreSQL、psycopg 3、手写 SQL DDL，无 ORM | `db/`、`pyproject.toml[db]` |
| RDF/OWL | RDFLib 7.6、Turtle/RDF/XML、OWL-RL | `pyproject.toml`、`ontology/` |
| 图数据库 | Ontotext GraphDB，SPARQL 1.1，Graph Store Protocol | `graph/client.py`、`ontology/tools/graphdb_http.py` |
| 规则 | SPARQL CONSTRUCT | `ontology/rules/*.rq` |
| 数据约束 | SHACL、pySHACL | `ontology/shapes/`、`validate_shacl.py` |
| 可选 DL 推理 | Owlready2/HermiT，需要 Java 17 | `pyproject.toml[dl]`；仓库中未找到默认流程已运行的充分证据 |
| 离线知识抽取 | OpenAI-compatible chat completions/tool calling、pypdf | `semantic_extract.py`、`pyproject.toml[extract]` |
| API/部署 | Docker、Compose、Nginx 反代样例 | `Dockerfile`、`compose.yml`、`deploy/` |
| 测试/质量 | pytest、ruff、Node built-in test | `tests/`、`demo/tests/` |
| 演示前端 | 原生 HTML/CSS/JS + Node 静态服务器 | `demo/`；被 `.gitignore` 排除且与正式运行时隔离 |

依赖设计有明显分层：默认依赖只有 RDF/OWL/SHACL；`extract`、`net`、`db`、`serve`、`eval`、`dl`、`dev` 均为 optional extras。`requirements.txt` 是 `--all-extras` 锁定结果，不等于默认运行时全部依赖。

## 9. Key Technical Features

### 9.1 “不知道”被建模为一等结果，而不是异常或空白

项目区分了至少以下状态：

- `Insufficient-Evidence`：患者事实不足，不能等价成低风险。
- `Unverified`：值存在但不参与默认阈值判定。
- `candidate`：术语/单位候选尚未人工核实。
- `unmappable`：结构上无法数值判定，例如定性尿蛋白。
- `no-source-data`：本体有概念和阈值，但上游无数据，例如 A1C。
- `Provisional`：阈值命中但复测条件不足。
- `unsupported`：系统既不能支持也不能反驳外部 claim。
- `not-adjudicable`：能力边界之外。
- `emptyReason`/`brokenLinks`：空集原因和溯源断链显式返回。

这比普通 CRUD + LLM 的最大差异是：失败语义进入数据契约，可被测试、展示和下游处理。

### 9.2 分层推理：OWL、SPARQL、SHACL 各司其职

- OWL 处理开放世界下的类型和关系推理。
- SPARQL 处理 OWL-RL 不擅长的数值区间、默认上下文、计数和规则产物。
- SHACL 处理闭世界必填、单位一致性、诊断分型冲突和绝对禁忌违规。

这不是把所有逻辑塞入一种技术，而是针对形式化能力边界拆分职责。证据见 `docs/DESIGN.md`，并在 `ontology/rules/` 与 `ontology/shapes/` 中有实际实现。

### 9.3 可复现、无污染的条件推演

两份全新 Dataset、固定规则顺序、确定性 IRI、规则/知识/假设哈希和 GraphDB 只读快照共同保证相同输入可得到相同推演标识。`derivationHash` 不是结论正确性的证明，但可以证明输入版本一致和结果可复现。

### 9.4 端到端 provenance 与引用核验

项目不仅返回 quote，还返回 `contentHash`、passage、规则、阈值、患者 RDF 事实和 SQL 原始行；`/graph/provenance` 把链条反向展开，并明确报告 `brokenLinks`。本次实际运行 `verify_passages.py` 证明 31/31 条可引用片段逐字存在于本地语料且哈希一致。

需要限定：这 31 条只是 seed 中被提升为可信 `SourcePassage` 的狭窄子集，不代表所有离线抽取的 recommendation/contraindication 都有同等级出处。

### 9.5 安全的自由 SPARQL 逃生口

项目从早期“只允许模板”演进为“模板/受控原语优先，自由 SPARQL 最后使用”。`graph.guard.check()` 对患者图变量、知识图写法、反例夹具、写操作、LIMIT 和全库扫描做静态检查；零行时运行探针，降低“查询写错但误以为没有数据”的风险。

本次不依赖服务的 19 个 guard 测试全部通过，是目前自动验证证据最强的一块。

### 9.6 可重建、可审计的本体知识库工程流水线

本体构建同时采用“编译、人工策展、受约束抽取、规则物化、质量门禁”五种机制，而不是把模型抽取结果直接灌进图数据库：

- schema JSON 编译为 TBox，使本体结构可 diff、可重复生成；
- 原始语料文件和生成图都有内容哈希，知识变更可追踪；
- 高风险临床常量从 LLM 抽取路径中物理分流；
- 原始模型输出可以离线重放确定性校验阶段；
- TBox、seed、sources、extract、patient、inferred 使用不同命名图，来源和产物边界清晰；
- SHACL、GraphDB 验收查询和逐字 passage 校验形成三类互补门禁。

这使项目的亮点从“有一个糖尿病本体”升级为“有一套能持续生产和治理糖尿病本体知识库的工具链”。当前 SHACL 有 2 条新增违规，说明门禁确实能暴露知识缺陷，但也说明当前构建产物尚未全绿。

## 10. Innovation

### 10.1 与普通字符串匹配的差异

普通实现常见流程是“名称相似 -> 建边 -> confidence”。本项目要求同时满足：

- 表面词经过人工映射或精确规范化；不使用编辑距离或 embedding 猜测。
- 单位必须存在且可核实；换算系数按 analyte 区分。
- 检验上下文必须匹配，例如 FPG 不能从未标明空腹的“血糖”推断。
- 阈值必须带开闭算子、人群上下文和可引用出处。
- 事实可信度决定能否参与判定。
- “落在糖尿病区间”与“确诊糖尿病”是两级结论。

`src/dmo/db/seed/lab_term_map.csv` 对“尿蛋白”将其标为 `qualitative + unmappable`，与前序系统把“尿蛋白 10.4”连到两个互斥疾病形成了可展示对照。

### 10.2 与普通 RAG/LLM 的差异

- 结论由规则与数据执行产生，不由生成模型自由编写。
- 规则输出带版本、确定性 IRI 和来源。
- 假设必须由用户显式提供，模型不能补一个“合理值”。
- 引用不仅做向量相似，还做逐字与哈希双重核对。
- 能力边界通过 `/adjudicate/scope` 和 `/agent/manifest` 变成机器可读接口。

但不能宣称仓库已证明“比纯 LLM 更准确”：仓库没有实现可执行的 LLM baseline、Agent loop 或完整评测 harness；`demo/` 中的 56 用例和百分比是硬编码演示数据。

### 10.3 与普通 ETL/知识图谱的差异

- 上游只读不是一句规范，而是双 DSN + session read-only + schema guard + 内容基线。
- RDF 同步使用整图 PUT，而非追加 POST，删除事实后不会遗留旧三元组。
- 内容哈希让第二次同步可跳过网络写入。
- 患者事实、知识图和推断图分开，能区分 asserted 与 inferred。
- 溯源不仅停在 RDF，还能回到 SQL 业务行。

### 10.4 与一次性手工建本体的差异

普通 PoC 往往直接维护一份 Turtle 或从 LLM 输出三元组后装库；本项目把知识库搭建拆成可复现阶段，并保留输入、原始输出、校验结果和版本哈希。尤其是“阈值不让 LLM 生成、来源不让 LLM 猜、可信引文必须逐字回原文”三条边界，把知识工程的风险控制落实到了构建流程，而不只是 prompt 提醒。

## 11. Repository Evidence

### 11.1 可以从代码直接证明的能力

| 结论 | 直接证据 |
|---|---|
| 图模型可编译为 OWL TBox | `ontology/tools/build_tbox.py` 读取 V2 JSON 并生成 `ontology/dist/tbox-v2.ttl` |
| 语料来源登记不依赖 LLM | `ontology/tools/source_registry.py::profile/emit` |
| 高危知识类型被排除出 LLM 抽取 | `ontology/tools/semantic_extract.py` 的 `POLICY_MANUAL/POLICY_REGISTRY` 与 schema policy |
| 抽取流程保留原始输出并支持离线重校验 | `semantic_extract.py` 的 `raw.jsonl`、`--from-raw`、validate/emit/report 阶段 |
| 知识图按 TBox/seed/sources/extract/inferred 分图装载 | `ontology/tools/load_graphdb.py::collect/run_rules` |
| 本体质量有 SHACL 新增违规门禁 | `ontology/tools/validate_shacl.py`、`ontology/shapes/known-violations.tsv`；本次实际检出 2 条新增违规 |
| 上游连接被设置为会话只读 | `src/dmo/db/engine.py::upstream_conn` 执行 `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY` |
| 写库与上游库使用不同 DSN | `src/dmo/config.py::Config`、`load()` |
| ETL 只读取白名单表并核对行数 | `src/dmo/db/etl.py::SPECS/run` |
| 上游内容变化可被指纹发现 | `src/dmo/db/baseline.py::fingerprint/check` |
| 数据库有 staging/map/sim/core/pred/sys 分层 | `src/dmo/db/ddl/*.sql`，30 张表 |
| PHI 字段不进入 RDF 发射函数 | `src/dmo/rdf/emit.py::build` 只读取规范患者/事实字段；staging DDL 也未定义姓名、证件、电话 |
| 每患者一命名图，哈希不变跳过 PUT | `src/dmo/rdf/sync.py::run` |
| 检验单位、可信度、上下文和开闭区间参与规则 | `ontology/rules/20-lab-assessment.rq` |
| 单次异常不会自动确诊 | `30-diagnosis-from-assessment.rq` 中 `COUNT(DISTINCT ?day)` 与 `Provisional/Confirmed` |
| 诊断阈值与管理目标分开 | `20-lab-assessment.rq` 与 `21-target-attainment.rq` |
| 风险 tier 是定性枚举，不输出概率/时间窗 | `51-risk-stratification.rq`、`db/predict.py`、测试断言 |
| 条件推演不需要写 GraphDB | `simulate/sandbox.py` 只加载，`runner.py` 在内存 Dataset 注入 |
| 相同推演输入可生成确定性哈希 | `simulate/hashing.py` |
| 自由 SPARQL 有静态守卫 | `graph/guard.py`；本次 19 个相关测试通过 |
| 31 条引用可逐字回溯 | `ontology/tools/verify_passages.py`；本次实测 31/31 通过 |
| 引用与结论裁决不是布尔值 | `adjudicate/citations.py`、`claim.py` |
| API 能力清单从 live routes 生成 | `src/dmo/manifest.py::build` |
| 部署镜像以非 root 用户运行并启用健康检查 | `Dockerfile`、`compose.yml` |

### 11.2 只有文档/注释声明，或证据不足的内容

| 声明 | 事实判断 |
|---|---|
| 仓库包含完整 LLM Agent/ReAct loop | **仓库中未找到充分证据。** `src/dmo/agent/` 不存在，`src/dmo/` 无模型调用 |
| 有 `dmo ask` 自然语言问答命令 | **仓库中未找到充分证据。** `cli.py::build_parser()` 没有 `ask` |
| 已实现“纯 LLM vs ontology agent vs RAG”评测 | **仓库中未找到充分证据。** 只有设计文档、测试问题清单和静态 demo 数字 |
| `demo/` 的 1,284 triples、42 concepts、18 rules、56 cases 和提升百分比是真实测量 | **仓库中未找到充分证据。** 数字硬编码在 `demo/index.html`，无评测产物或计算脚本 |
| demo 的 eGFR<30 二甲双胍禁忌来自正式规则 | **没有代码证据，且正式知识层明确不采纳该规则。** `load_graphdb.py` 注释说明二甲双胍 eGFR<30 因无出处未采纳；demo 与正式实现矛盾 |
| 已接入 MONDO/LOINC/ATC/HPO 的完整标准术语体系 | 只有少量 `skos:exactMatch/closeMatch` 和文档声明；**仓库中未找到完整导入、版本锁定或覆盖率证据** |
| HermiT/DL 推理已经在默认流水线验证 | 只是 optional extra 和设计说明；**仓库中未找到充分运行证据** |
| 全量测试已通过 | 事实相反：本次 155 个测试跳过，SHACL 还有 2 条新增违规 |
| 所有 API 输出绝不含剂量 | 正式患者 schema/返回体没有剂量字段，有代码证据；但被忽略的 `demo/` 硬编码 `1000mg bid`。只能对正式后端成立，不能对整个工作区页面成立 |
| 所有输出 100% 可追溯 | 只能对 31 条可信 passage 和部分规则链成立。抽取产物仍有裸 `evidenceQuote`、缺 rationale/强度等 SHACL 违规 |
| 生产可用/临床可用 | **仓库中未找到充分证据。** 项目自称技术验证/学习项目，缺生产级安全和合规能力 |

### 11.3 文档时效性与矛盾

- `docs/DESIGN.md` 开头仍写“仓库目前是空的”，显然已经过时。
- 同一文档设计了 `anthropic` SDK、`src/dmo/agent/loop.py`、`dmo ask` 和 eval harness，但实际实现没有这些目录或命令。
- `docs/AGENT-INVESTIGATE-PLAN.md` 记录早期 `/graph/sparql` 不存在；当前 `api.py` 已有该端点和 guard，说明计划文档部分状态已过时。
- `docs/RELATIONAL-GRAPH-INTEGRATION-PLAN.md` 中若干命令名（如 `db upgrade/downgrade`）与当前 CLI 的 `db migrate` 不一致。
- `docs/DOCKER.md` 说 Compose 默认只绑定 `127.0.0.1:8100`，当前 `compose.yml` 实际映射为 `0.0.0.0:8100:8100`；部署暴露面应以代码为准。
- `src/skills/` 中存在 localhost、`124.223.18.44:8100` 和甚至错误的 `:7200` API base 示例，部署文档/skill 配置不完全一致。

## 12. Limitations

### 12.1 产品与 Agent 能力

1. **没有内置对话 Agent**：没有自然语言规划、tool loop、会话状态、模型选择或响应生成；项目是工具后端和 skills 契约。
2. **没有可执行 baseline 评测**：不能用当前仓库证明 ontology agent 优于纯 LLM。
3. **前端不是正式产品界面**：`demo/` 是静态、硬编码、与后端隔离的展示页，且包含正式后端明确禁止/不支持的剂量和 eGFR-二甲双胍结论。
4. **目标用户工作流未闭环**：没有病例审核、人工签署、反馈、纠错、版本审批或临床责任边界界面。

### 12.2 数据与知识覆盖

1. 真实数据极弱：关键指标缺失、单位缺失、数值不可信、队列小、无纵向随访/共病，因此真实 E11 患者主要得到 `Insufficient-Evidence`。
2. 只有 31 条 seed passage 达到逐字 + hash 的可信引用标准；推荐和禁忌抽取覆盖远大于可验证出处覆盖。
3. `source_registry.py --report` 本次识别 26 个 TXT，其中 2 个是正文空壳、4 个未解析到年份；`sourceUrl` 全部刻意留空。
4. 规则覆盖有限：17 条诊断阈值、10 条管理目标、12 条声明风险规则（其中 10 条计入 tier）是仓库自报且可从 seed/规则索引设计核对的量级，不是全面糖尿病知识库。
5. 开放世界下“无记录”不等于“没有”；代码对非妊娠等场景使用了显式标注的闭世界近似。
6. 无 embedding/模糊匹配降低误映射风险，也意味着召回率依赖人工词表和精确归一化。

### 12.3 当前质量状态

1. 本次 pytest 只有 19 项真正执行，155 项因 PostgreSQL/GraphDB 不可用而跳过。集成能力大多有测试代码，但本次没有运行证据。
2. SHACL 全量校验失败：12 条违规中 2 条不在已知基线，分别涉及 LMWH 禁忌缺出处原话、heart-failure 禁忌缺强度。
3. Ruff 返回 43 个问题，包括脚本带 shebang 但不可执行、导入排序和代码风格问题。
4. 测试策略把外部服务不可用处理成 `skip`，容易在 CI 中出现“大量跳过但总体退出 0”；应增加最低执行数或强制集成环境 job。
5. `ontology/dist/patients/` 当前包含 440 个导出患者图且约 2.9 MB，但被 gitignore；本地 SHACL 结果会受工作区生成物影响，复现时需明确数据快照版本。

### 12.4 API、安全与运维

1. API 没有认证、授权、租户隔离、患者级访问控制、审计日志或速率限制。
2. `compose.yml` 把 8100 绑定到 `0.0.0.0`，若云安全组直接开放会暴露患者查询、自由 SPARQL 和推演接口。
3. 自由 SPARQL guard 是正则/静态扫描而非完整语法树和查询成本估计；能降低已知错误，不等于安全沙箱。
4. API 多数输入/输出使用 `dict[str, Any]`，缺少 Pydantic 请求/响应模型、稳定 schema 和字段级验证。
5. FastAPI 路由是同步函数，底层 psycopg/HTTP 也是同步；多 worker 可缓解，但没有连接池、缓存策略、熔断、追踪或指标采集。
6. GraphDB 和 PostgreSQL 之间没有事务一致性、outbox/CDC 或自动增量推理；执行顺序依赖 CLI 运维流程。
7. Docker 镜像安装默认 RDF/SHACL 依赖和 `serve,db` extras，也复制 `ontology/`；但 `.dockerignore` 排除了原始语料和患者图导出，因此容器内无法复现本次包含 440 个本地患者图的同一份全量 SHACL 输入。
8. Nginx 只有最小反代样例，没有 TLS、认证或 rate limiting 配置。

### 12.5 医疗安全边界

1. 规则命中不等于临床建议；仓库没有临床验证、前瞻性研究或监管证据。
2. `supported` 只代表内部一致，不能替代指南适用性判断或临床判断。
3. 指南推荐分级体系互不可比；代码选择“不排序、不选最佳”，下游仍需要人工判断 population scope。
4. 风险 tier 是规则式定性枚举，不含概率或时间窗。
5. 正式 schema 不含剂量字段，但静态 demo 仍含剂量文字，演示时必须避免把 demo 当正式能力。

## 13. Best Content for Presentation

### 13.1 最值得现场展示的 5 个片段

1. **从指南文件到可运行知识库的构建流水线**  
   展示 `diabetes-ontology-v2.json -> build_tbox.py -> tbox-v2.ttl`，以及 `TXT/PDF -> source_registry/semantic_extract -> extract 图 -> SHACL/逐字校验 -> GraphDB`。核心信息：亮点不只是本体内容，更是一套可重建、可审计、对高危知识分级治理的知识库工厂。

2. **单次 A1C -> Provisional；补另一天 -> Confirmed，并产生稳定哈希**  
   展示 `30-diagnosis-from-assessment.rq`、P90002/P90003 和 `/simulate` 的 delta、`derivationHash`。核心信息：阈值命中不等于确诊，条件推演可以复现且不污染事实图。

3. **7.8 mmol/L FPG 必须先换算成约 140.54 mg/dL**  
   展示 `unit_conversion.csv`、`projection.py`/`hypothesis.py`、P90012。核心信息：缺失或错误单位会让结论翻转。

4. **“尿蛋白 10.4”对照：字符串 confidence 0.9 vs `unmappable`**  
   展示 `lab_term_map.csv` 和 `/demo/compare`。核心信息：宁可拒绝判定，也不把定性项目伪装成定量证据。

5. **一条结论反向走到规则、阈值、逐字原文和 SQL 行**  
   展示 `/graph/provenance`、`/graph/passages` 和 `/adjudicate/citations`。核心信息：可解释不只是解释文字，而是可核对证据链。

### 13.2 建议的技术故事线

1. 先展示本体知识库如何从 schema 与原始语料经过受控流水线构建出来，而不是把 Turtle 当作来历不明的成品。
2. 再进入真实脏数据，说明为什么字符串匹配/纯 LLM 会在单位、上下文、复测、来源上犯“看不见的错”。
3. 展示 PostgreSQL、OWL、SPARQL、SHACL 各自承担的职责，以及知识构建层与患者事实层如何汇合。
4. 用 P90002/P90012/尿蛋白三个小案例证明系统如何拒绝越界。
5. 最后展示 provenance、裁决和确定性哈希，把“可信”落到可验证机制。

### 13.3 PPT 中不应使用的素材/表述

- 不要使用 `demo/index.html` 中的 94.7%、89.3%、100% 等数字作为项目评测结果。
- 不要声称已有完整 LLM Agent、ReAct loop 或 `dmo ask`。
- 不要声称所有 50 份指南内容都能逐字引用；可信 `SourcePassage` 当前只有 31 条。
- 不要声称当前 SHACL/测试/代码质量全绿。
- 不要展示 demo 的“二甲双胍 1000mg bid”或 eGFR<30 禁忌结论为正式系统输出。
- 不要把 `Insufficient-Evidence` 翻译成“低风险”。
- 不要把规则式 tier 翻译成概率、评分或未来时间窗。

### Top 5 Presentation Messages

1. **项目不仅有糖尿病本体，还具备从 schema 与指南语料持续构建、装载和治理本体知识库的工程流水线。**
2. **这个项目最重要的运行时能力不是回答更多，而是能工程化地说明“为什么现在不能回答”。**
3. **患者事实、语义规则和逐字出处被连接成一条可反查到 SQL 原始行的证据链。**
4. **单次异常、单位换算、妊娠上下文和条件推演都由确定性规则处理，假设与实测严格分离。**
5. **当前成果是可供外部 Agent 调用的语义推理后端；内置 LLM Agent、可信评测和生产临床化仍是下一阶段，而不是已经完成的能力。**
