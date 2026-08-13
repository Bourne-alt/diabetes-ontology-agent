# 关系数据库与糖尿病本体图集成实施计划

> 基准模型：`ontology/graph/diabetes-ontology-v2.json`  
> 目标形态：PostgreSQL + GraphDB 的可运行 MVP  
> 同步策略：批量、幂等、按患者命名图整体替换  
> 适用范围：技术验证与合成患者，不用于真实医疗决策

## 1. 目标与架构边界

本计划将 V2 care-chain 模型落到关系数据库和 RDF 图数据库中：

```text
合成数据
  -> PostgreSQL（患者临床事实的唯一来源）
  -> SQL-to-RDF 映射
  -> GraphDB 患者命名图
  -> SPARQL/OWL 推理
  -> 查询接口 / Agent
```

各层职责固定如下：

| 层 | 负责内容 | 不负责内容 |
|---|---|---|
| PostgreSQL | 患者、就诊、检验、诊断、评估、用药事件；事务、约束、时间排序 | OWL 类层次、多跳推理 |
| GraphDB | TBox、术语、指南、阈值、语义投影、推理结果和 provenance | 患者业务事务的唯一持久化 |
| SPARQL/OWL | 类层次、属性链、阈值匹配后的语义结论 | SQL 数据完整性和业务事务 |
| SHACL | RDF 结构、单位、基数和安全约束校验 | 代替数据库外键和事务约束 |
| 查询服务 | 组合 SQL 原始事实、图推理和来源 | 绕过数据权限直接暴露患者图 |

核心原则：SQL 是患者事实的 source of truth；GraphDB 中的患者数据必须能随时从 SQL 重建。

## 2. 实施阶段

### 阶段 0：项目骨架和运行配置

1. 增加 PostgreSQL 运行依赖：
   - `psycopg` 3
   - SQLAlchemy 2
   - Alembic
2. 增加数据库配置：
   - `DMO_DATABASE_URL`
   - `DMO_GRAPHDB_ENDPOINT`，默认 `http://localhost:7200`
   - `DMO_GRAPHDB_REPOSITORY`，默认 `dmo`
3. 新建 `src/dmo` 包和 CLI 入口，使 `pyproject.toml` 中现有的 `dmo = "dmo.cli:main"` 可执行。
4. 所有凭据只从环境变量读取；仓库只提供无密码的示例配置。

验收：

```bash
uv run dmo --help
uv run dmo db status
uv run dmo graph status
```

### 阶段 1：建立关系数据库模型

建立 V2 care-chain 的核心事实表：

| 表 | 关键内容 |
|---|---|
| `patient` | 患者假名化标识和稳定人口学属性 |
| `clinical_encounter` | 就诊时间锚点，外键指向 patient |
| `lab_result` | 检验值、单位、采样时间，引用 LabTest 概念 |
| `clinical_observation` | BMI、血压、妊娠状态、症状等时序观察 |
| `diagnosis` | 糖尿病分型、并发症、状态、验证状态和当前分期 |
| `assessment` | 规则结论、规则 ID/版本、适用上下文 |
| `assessment_lab_result` | Assessment 与支持它的一个或多个 LabResult |
| `medication_use` | 用药开始/结束时间、状态和角色，不包含剂量 |
| `medication_use_diagnosis` | MedicationUse 所治疗的 Diagnosis |

增加辅助关联表：

- `patient_risk_factor`
- `patient_device_use`
- `patient_intervention`

增加两个基础设施表：

```text
concept_ref
  iri             PK
  concept_kind    LabTest / DiabetesType / Complication / ...
  code
  label
  version
  UNIQUE(concept_kind, code)

rdf_sync_state
  graph_uri       PK
  patient_id      UNIQUE
  content_hash
  sync_status
  synced_at
  error_message
```

数据库约束：

- encounter 必须属于一个 patient。
- lab result 必须属于一个 encounter，并引用 `LabTest` 类型的概念。
- observation 的 `value_decimal` 和 `value_text` 至少一个有值。
- assessment 至少关联一个 lab result。
- medication use 的结束日期不得早于开始日期。
- 只有 Complication diagnosis 可以设置 `current_stage_iri`。
- Diagnosis 为 Diabetes/Prediabetes 时必须引用 DiabetesType；为 Complication/AcuteEvent 时必须引用 Complication。
- 所有患者相关表使用 UUID 主键。
- 不建立任何具体用药剂量字段。

验收：

```bash
uv run dmo db upgrade
uv run dmo db downgrade --steps 1
uv run dmo db upgrade
```

### 阶段 2：固定 SQL-to-RDF 映射契约

运行时只使用 V2 图：

```text
ontology/graph/diabetes-ontology-v2.json
ontology/graph/diabetes-ontology-v2.rdf
```

V1 文件作为历史设计保留，但不进入患者同步链路。

IRI 使用确定性模板：

| SQL 对象 | RDF IRI |
|---|---|
| Patient | `https://example.org/dmo/patient/{uuid}` |
| ClinicalEncounter | `https://example.org/dmo/encounter/{uuid}` |
| LabResult | `https://example.org/dmo/lab-result/{uuid}` |
| ClinicalObservation | `https://example.org/dmo/observation/{uuid}` |
| Diagnosis | `https://example.org/dmo/diagnosis/{uuid}` |
| Assessment | `https://example.org/dmo/assessment/{uuid}` |
| MedicationUse | `https://example.org/dmo/medication-use/{uuid}` |

映射规则：

1. 每个患者及其完整 care-chain 写入独立命名图：

   ```text
   urn:dmo:patient:{patient_uuid}
   ```

2. SQL 外键映射为 V2 ObjectProperty；普通列映射为 DatatypeProperty。
3. `NULL` 不生成三元组。
4. 日期、时间、decimal、integer 和 boolean 必须使用对应 XSD datatype。
5. 患者图只引用知识层的规范概念 IRI，不复制术语定义、指南正文和阈值节点。
6. `MedicationUse`、`Diagnosis`、`Assessment` 必须保持为独立实体，不退化成带属性的二元边。
7. 每次输出前校验：谓词属于 V2 schema、enum 合法、概念 IRI 存在、单位可识别。
8. 不使用 `owl:hasKey`，也不依赖自动 `owl:sameAs` 合并患者。

### 阶段 3：准备合成数据和术语索引

1. 从 V2 图、TBox 和 seed Turtle 读取规范概念，写入 `concept_ref`。
2. 将现有合成患者数据迁移为 PostgreSQL seed；迁移后 SQL 是患者测试事实的唯一来源。
3. seed 至少包含以下场景：
   - 正常检验结果。
   - A1C 命中糖尿病范围。
   - 妊娠上下文使用独立阈值。
   - DKD 并发症及明确分期。
   - 一次 Assessment 由多个 LabResult 支持。
   - MedicationUse 关联一个或多个 Diagnosis。
   - 能触发药物类别禁忌检查的患者。
4. seed 使用固定 UUID，确保测试和 RDF IRI 可重复。

公开命令：

```bash
uv run dmo sync concepts
uv run dmo db seed
```

### 阶段 4：实现批量幂等同步

提供命令：

```bash
uv run dmo sync patient --patient-id <uuid>
uv run dmo sync all
uv run dmo sync all --prune
```

同步流程：

1. 在一个 SQL 一致性快照中读取患者完整 care-chain。
2. 生成 RDF Graph，并对三元组做规范排序。
3. 计算 SHA-256；与 `rdf_sync_state.content_hash` 相同则跳过网络请求。
4. 不相同时，通过 Graph Store Protocol `PUT` 整体替换患者命名图。
5. PUT 成功后更新 `rdf_sync_state`；失败时记录错误并保留旧哈希。
6. `sync all` 单个患者失败后继续其他患者，最终打印成功、跳过、失败数量；存在失败时返回非零退出码。
7. `--prune` 只删除 `rdf_sync_state` 已登记、但 SQL 中患者已经不存在的 `urn:dmo:patient:*` 图。
8. 患者图同步结束后运行现有 `rules/*.rq`，整体替换 `urn:dmo:inferred`。

失败策略：

- GraphDB 不可用时不回滚 SQL 事务。
- PUT 超时或返回非 2xx 时允许安全重试。
- 未知概念、非法 enum、单位不匹配属于数据错误，不发送不完整 RDF。
- 同步日志不得输出患者姓名、原始文档内容或数据库凭据。

### 阶段 5：衔接 GraphDB 装载和查询

扩展现有 `ontology/tools/load_graphdb.py`：

1. 静态 TBox 构建默认以 V2 JSON 为输入。
2. 继续管理以下知识图：
   - `urn:dmo:tbox`
   - `urn:dmo:seed`
   - `urn:dmo:sources`
   - `urn:dmo:extract:*`
   - `urn:dmo:inferred`
3. 患者图由 `dmo sync` 管理，不混入静态装载计划。
4. `graph verify` 同时检查静态知识图、患者图和推理图。

提供参数化查询：

- `patient_care_chain(patient_iri)`：完整就诊、观察、诊断、评估和用药链。
- `latest_lab_result(patient_iri, lab_test_iri)`：最近检验及 Assessment。
- `diagnosis_evidence(diagnosis_iri)`：支持检验、阈值、规则版本和 SourcePassage。
- `medication_safety(patient_iri)`：MedicationUse、DrugClass、禁忌和触发条件。

查询边界：

- PostgreSQL 负责患者身份、权限、时间排序和分页。
- GraphDB 负责语义路径、推理结论和 provenance。
- 返回结构必须区分 `assertedFacts`、`inferredFacts` 和 `sources`。

## 3. 测试计划

### 单元测试

- 每类 SQL 实体生成正确的 RDF type、数据属性和对象关系。
- `NULL` 不生成三元组，decimal/dateTime datatype 正确。
- 相同 SQL 输入生成相同三元组集合和哈希。
- 未知概念、非法 enum、错误单位在 PUT 前被拒绝。
- Diagnosis、Assessment、MedicationUse 保持为事件实体。

### 数据库测试

- 空库可以完整 upgrade、downgrade、再次 upgrade。
- 所有外键、唯一约束和日期约束生效。
- 不合法的 Diagnosis 类型与目标组合无法写入。
- MedicationUse 结束日期早于开始日期时写入失败。

### GraphDB 集成测试

- 同一患者连续同步两次，第二次跳过 PUT。
- 修改一条 LabResult 后只更新对应患者图。
- 删除 MedicationUse 并同步后，旧三元组不残留。
- `--prune` 不会删除 TBox、seed、source 或其他患者图。
- GraphDB 超时后同步状态为 failed，恢复后可重试成功。

### 端到端验收

1. `Patient -> Encounter -> LabResult -> Assessment -> Diagnosis` 可完整查询。
2. Assessment 能返回命中的 DiagnosticThreshold 和 SourcePassage。
3. MedicationUse 能连接 Medication、DrugClass 和所治疗的 Diagnosis。
4. Complication Diagnosis 只返回患者当前 Stage，不把该并发症的所有可能分期当作患者分期。
5. SQL 原始事实、GraphDB 推理结果、规则版本和来源在响应中明确分组。
6. 所有输出保留医疗免责声明，不输出具体药物剂量。

CI 默认执行单元测试和 PostgreSQL 集成测试；GraphDB 集成测试通过环境变量显式开启。

## 4. 交付顺序与完成标准

| 里程碑 | 交付内容 | 完成标准 |
|---|---|---|
| R1 | CLI、配置、Alembic 骨架 | `dmo db status` 可运行 |
| R2 | PostgreSQL V2 schema | 迁移和约束测试通过 |
| R3 | concept_ref 与合成 seed | 固定 UUID 数据可重复载入 |
| R4 | SQL-to-RDF 映射 | 单患者 Turtle 与快照测试通过 |
| R5 | 幂等 PUT 同步 | 重跑无重复、删除无残留 |
| R6 | 推理与参数化查询 | 四类核心查询通过 |
| R7 | 端到端测试和文档 | 从空库到查询结果可一条流程复现 |

最终验收命令：

```bash
uv sync --extra dev
uv run dmo db upgrade
uv run dmo sync concepts
uv run dmo db seed
python3 ontology/tools/load_graphdb.py --create --load
uv run dmo sync all
uv run dmo graph verify
uv run pytest
```

## 5. 明确不在 MVP 范围内

- 真实患者数据和 PHI 接入。
- 多租户、RBAC、患者身份主索引和跨系统患者合并。
- CDC、transactional outbox、消息队列和增量推理。
- GraphDB 作为患者业务事实的唯一数据库。
- V1/V2 双格式患者图输出。
- 自动生成或建议具体药物剂量。
- 依赖 `owl:hasKey` 或 `owl:sameAs` 的患者合并。

上述能力应在 MVP 通过后作为生产化阶段单独设计。
