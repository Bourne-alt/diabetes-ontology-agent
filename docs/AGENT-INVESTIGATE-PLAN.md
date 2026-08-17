# 患者调查智能体：ReAct + 动态 SPARQL/SQL

> 配套文档：整体方案见 [DESIGN.md](DESIGN.md)，端点契约见 [API.md](API.md)，图层写法见 [GRAPHDB-USAGE.md](GRAPHDB-USAGE.md)。
> 本文落地 [DESIGN.md](DESIGN.md) 的 **M4 里程碑（Agent）**，只解决一件事：
> **让一个 ReAct 智能体自己规划执行计划、动态生成 SPARQL 与 SQL，跨 GraphDB 与 PostgreSQL 取证，回答固定端点回答不了的开放性问题。**
>
> ⚠️ 本文**推翻了 [DESIGN.md](DESIGN.md) 「关键设计原则 1：不让 LLM 自由写 SPARQL」**。
> 推翻的理由、代价、以及代价怎么补，见「[决策记录](#决策记录推翻-designmd-原则-1)」一节。不看那节不要照本文实施。
>
> 起草日期：2026-08-17。

## Context

`POST /patients/{pid}/simulate`（[api.py:109](../src/dmo/api.py)）的流程是写死的：调用方给假设值 → 跑固定规则链 → diff 前后结论。它**只能回答"若 X 则 Y"**，回答不了"这个患者到底什么情况、还差什么证据、为什么这条结论是 Provisional"这类需要多步探查、且探查路径事先无法枚举的问题。

现有全部端点（`/assessment` `/risk` `/safety` `/care-chain`）都是同一个形状：固定 section → 固定模板 → 固定返回体。好处是确定，坏处是**问题必须先被人想到，才能被回答**。

### simulate 不动，另开端点

`simulate` 的核心资产是 `derivationHash`（[simulate/hashing.py](../src/dmo/simulate/hashing.py)）—— 同一请求跑 5 遍必须同哈希，`tests/test_simulate.py::test_derivation_hash_is_stable` 专门断言这件事，注释写着"这是相对 LLM 最硬的一条差异"。把 LLM 塞进 `simulate` 等于自毁卖点。

**所以：新增 `POST /patients/{pid}/investigate`，`simulate` 一行不动。** 智能体反过来把 `simulate` 当成自己的一个工具来调。

### 现状盘点

| 项 | 状态 |
|---|---|
| `src/dmo/agent/`、`src/dmo/tools/` | **不存在**。[DESIGN.md](DESIGN.md) 写了 40 行设计，零代码 |
| `raw_sparql` 逃生口 | **不存在**。`templates.py:12`、[DESIGN.md](DESIGN.md)、[PATIENT-GRAPH-FUSION-PLAN.md](PATIENT-GRAPH-FUSION-PLAN.md) 三处提到，`src/` 下无实现 |
| `dmo ask` 子命令 | `cli.py:13` 的注释里挂着 `ask  agent 编排  R7`，`build_parser()` 里没有 |
| 运行时 LLM 调用 | **全 `src/dmo/` 零处**。唯一的模型调用是离线的 `ontology/tools/semantic_extract.py`（OpenAI 兼容接口） |
| SQL 侧只读连接 | **不存在**。`onto_conn` 是全项目唯一可写路径 |
| RDF 侧 schema 元数据 | `ontology/graph/diabetes-ontology-v2.json`，25 实体 + 48 关系，带中文描述与基数，**开箱可用** |
| SQL 侧 schema 元数据 | DDL 里有约 20 处中文 `COMMENT ON`，**没有任何代码读它们** |
| SQL 列 ↔ RDF 谓词对照 | 只以命令式代码存在于 `rdf/emit.py`，**无声明式版本** |

### 三条已定的边界

| 决策 | 选择 |
|---|---|
| 执行层给 LLM 什么 | **自由 SPARQL/SQL + 沙箱**（推翻原则 1） |
| 端点归属 | **新端点，`simulate` 不动** |
| 数值生成 | **绝不生成**。假设值必须来自用户原文，机械校验而非靠模型自觉 |

---

## 决策记录：推翻 DESIGN.md 原则 1

[DESIGN.md](DESIGN.md) 「关键设计原则」第 1 条原文：

> **不让 LLM 自由写 SPARQL**。LLM 写 SPARQL 出错率高（URI 拼错、prefix 缺失、语法错）。流程强制为 `search_concept` → 拿到准确 URI → 参数化模板。`raw_sparql` 只作逃生口。

`src/dmo/query/templates.py` 开头还有一份更详细的论证，按严重程度排了三个理由。

**本方案不再把自由查询当逃生口，而是当主力路径之一。** 这是一次有意识的取舍，不是遗忘。

### 为什么推翻

模板白名单的代价是：**问题必须先被人想到**。6 个模板覆盖的是已知问法；开放性调查（"还差什么证据""这两条结论为什么互相矛盾"）的查询形状事先无法枚举，加模板等于把 agent 退化成路由器。

### 原则 1 举的理由，哪些还成立

| 原论证 | 是否仍成立 | 本方案怎么处理 |
|---|---|---|
| URI 拼错 | ✅ 仍成立 | 保留 `search_concept` 工具，prompt 里强制"先查概念拿准确 IRI 再写查询" |
| prefix 缺失 | ❌ 不成立 | 提交前自动前置 `templates.PREFIXES`，这是纯机械问题，不该消耗模型一轮 |
| 语法错 | ❌ 不严重 | GraphDB 会报错，错误信息原样回给模型自我修正，ReAct 循环本来就吃这个 |
| **知识侧写死具名图 → 静默少返** | ✅✅ **最严重，且模型必犯** | **静态检查器规则 B**，见下 |
| **患者侧缺 `STRSTARTS` 守卫 → 扫到反例夹具** | ✅✅ **最严重，且模型必犯** | **静态检查器规则 A**，见下 |
| 全库扫描 430 个患者图 | ✅ 仍成立 | 规则 F（警告）+ 强制 `LIMIT` |

### 关键判断

> **真正的风险不是"它会搞破坏"，是"它会给出半个答案而你看不出来"。**

只读角色、`statement_timeout`、写操作黑名单对付得了删库，对付不了静默少返 —— 查询不报错、返回一个看似合理的小结果集，人工复核也发现不了。

**推翻原则 1 的前提条件是：把那两条最严重的理由从"靠人自觉"变成"机械可检测"。** 二者恰好都可以：

- 规则 A 检测 `GRAPH ?var {` 的每个变量是否被 `STRSTARTS(STR(?var),"urn:dmo:patient:")` 约束 —— 纯语法可判定
- 规则 B 检测是否出现 `GRAPH <urn:dmo:seed|tbox|sources|inferred|extract:*>` —— 纯语法可判定

**所以本方案的重心不在工具集，在 `agent/guard/`。** 实施顺序里 guard 排在 LLM 接入之前，就是这个原因：guard 挡不住的东西，后面全是白搭。

### 保留不变的三条

原则 2（每个回答必须带 provenance）和原则 3（schema 注入而非数据注入）**完全保留**，且本方案把原则 2 加强成机械校验（见「输出后置校验」）。`README.md` 「明确不做的事」五条一条不动。

---

## 架构

```
                    ┌──────────────────────────────┐
   用户问题 ───────▶ │  agent/loop.py  ReAct 主循环  │
                    └───────────┬──────────────────┘
                                │ tool_use
                    ┌───────────▼──────────────────┐
                    │  agent/tools.py  7 个工具     │
                    └──┬─────────────────────┬─────┘
             安全快路径 │                     │ 自由查询
        ┌──────────────▼───┐      ┌──────────▼──────────┐
        │ search_concept   │      │ agent/guard/sparql  │ ★
        │ patient_bundle   │      │ agent/guard/sql     │
        │ run_template     │      └──────────┬──────────┘
        │ explain_gap      │                 │ 通过才执行
        │ simulate         │      ┌──────────▼──────────┐
        └──────────────────┘      │ GraphDB (只读)      │
                                  │ onto_readonly_conn  │
                                  └──────────┬──────────┘
                    ┌──────────────────────────▼───────┐
                    │  agent/postcheck.py  输出后置校验 │
                    │  剂量 / 概率 / 伪造出处           │
                    └──────────────────────────────────┘
```

### 目录

```
src/dmo/agent/
├── __init__.py        导出 investigate / AgentError
├── loop.py            ReAct 主循环（手写 tool-calling，不用 SDK tool_runner）
├── prompt.py          system prompt 组装 + 硬禁令
├── tools.py           7 个工具的 JSON schema + dispatch
├── schema_card.py     喂给模型的 schema 上下文（RDF 侧 / SQL 侧 / 桥接表）
├── postcheck.py       输出后置校验
├── trace.py           结构化 trace
└── guard/
    ├── __init__.py
    ├── sparql.py      SPARQL 静态检查器 ★核心
    └── sql.py         SQL 静态检查器
src/dmo/llm/
├── __init__.py
└── client.py          OpenAI 兼容客户端（复用 .env 现有配置）
```

改动的现有文件：`db/engine.py`、`rdf/emit.py`、`api.py`、`cli.py`、`pyproject.toml`。

---

## 1. 只读连接

**`onto_conn` 不是只读的** —— 它是全项目唯一可写路径（`db/engine.py`）。LLM 生成的 SQL 绝不能走它。

在 `db/engine.py` 加第三个 context manager，**复用现成的 `GuardedConnection(readonly=True)`**（`_WRITE_VERBS` 拦截已写好）：

```python
@contextmanager
def onto_readonly_conn(cfg: Config) -> Iterator[GuardedConnection]:
    """连 onto_db，但会话级只读。给 agent 生成的 SQL 用。

    与 onto_conn 的差别只有两处，都是刻意的：只读 + 15s 超时。
    agent 的查询是探索性的，跑 300s 说明它写错了，不该让它跑完。
    """
    with psycopg.connect(cfg.onto_dsn, autocommit=True) as conn:
        conn.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
        conn.execute("SET statement_timeout = '15s'")
        conn.execute(sql.SQL("SET search_path = {}, public").format(sql.Identifier(ONTO_SCHEMA)))
        yield GuardedConnection(conn, readonly=True, label="onto-ro(agent)")
```

同时在 `ping()` 里补一项探测，让 `dmo db status` 能**自证这条连接确实写不进去** —— 与 `dmo db guard-test` 同一个思路：不写"应该是只读的"，而是当场证明。

---

## 2. SPARQL 静态检查器 ★

`agent/guard/sparql.py`。返回 `GuardVerdict(ok, reasons, rewritten_query, warnings)`。

**拒绝理由必须写成给模型看的话** —— 它会作为 ReAct 的 observation 回给模型自我修正，写"guard violation: rule A"等于浪费一轮。

先仿 `db/engine.py` 的 `strip_sql_noise` 写一个 `strip_sparql_noise()`（剥 `#` 注释与字符串字面量），所有规则在剥净的文本上跑 —— DDL 的 `COMMENT ON` 里写上游表名不该被拦，同理 SPARQL 注释里出现 `INSERT` 也不该。

| 规则 | 检测 | 回给模型的话 |
|---|---|---|
| **A 患者图守卫** | 抓出所有 `GRAPH ?var {`，逐个检查该变量是否出现在 `STRSTARTS(STR(?var),"urn:dmo:patient:")` 中 | "`?pg` 没有患者图守卫。不加会扫到 `urn:dmo:data` 里 6 例**故意造错的反例夹具**。请加 `FILTER(STRSTARTS(STR(?pg),\"urn:dmo:patient:\"))`" |
| **B 知识侧禁具名图** | 出现 `GRAPH <urn:dmo:seed｜tbox｜sources｜inferred｜extract:*>` | "知识侧不能写 GRAPH。GraphDB 的 owl2-rl 物化三元组不在任何命名图里，写死具名图会**静默少返** —— 查询不报错但答案少一半。请去掉 GRAPH 包裹" |
| **C 反例夹具** | 出现 `urn:dmo:data` | "那是故意造错的反例夹具，不是真实患者" |
| **D 写操作** | 非 `SELECT/ASK/CONSTRUCT/DESCRIBE` 开头，或含 `INSERT/DELETE/DROP/CLEAR/LOAD/CREATE/MOVE/COPY/ADD` | 直接拒 |
| **E 行数上限** | `SELECT` 无 `LIMIT` → 自动追加 `LIMIT 200`；已有且 >200 → 改写为 200 | 记进 `rewrites`，**不算失败** |
| **F 全库扫描** | 触及患者图但无 `VALUES ?pat` / `?pat dmo:patientId "…"` 收敛 | warning（不拒）："430 个患者图全扫，30 例演示看不出问题，上量是灾难" |

规则 A/B 的模式常量直接取自 `query/templates.py` 的 `PG_GUARD` 与 `PREFIXES`，**不抄第二份** —— 这个仓库不允许同一件事有两份定义。

### 零结果探针

静态检查抓不全所有少返情形。所以：**自由 SPARQL 返回 0 行时不把空集直接回给模型**，而是自动跑降级探针：

```sparql
ASK { GRAPH ?pg { <患者IRI> ?p ?o } FILTER(STRSTARTS(STR(?pg),"urn:dmo:patient:")) }
```

再数一次该患者图的三元组数，observation 写成：

> 你这条查询返回 0 行，**但该患者图里有 N 条三元组**。0 行大概率是你的图模式写错了（最常见：把知识侧三元组包进了 `GRAPH ?pg`），不是"数据不存在"。

这直接命中 `templates.py` 最担心的场景，成本极低。**空集与"有但判不了"是两回事** —— 这条 `explain_gap` 早就在做，这里只是把同一个诚实标准套到 agent 上。

---

## 3. SQL 静态检查器

`agent/guard/sql.py`，建在复用的 `strip_sql_noise` 之上：

- **单语句**：剥净后不得含 `;`（尾部除外）
- **必须 `SELECT` 或 `WITH` 开头**
- **表白名单**：`diabetes.core_* / pred_* / map_* / stg_*`。**禁 `sys_*`**（迁移与基线是内部账本）。`stg_*` 放行 —— 它是脱敏后的快照，姓名/身份证/电话在 `ddl/002_stg.sql` 的列白名单里就不存在
- **禁跨库与内省**：`patient_analysis.` / `semantic_link.` / `pg_catalog` / `information_schema`。前两个 `FORBIDDEN_SCHEMA_RE` 已覆盖；后两个新加 —— 防它绕过 schema card 自己爬库
- **禁危险函数**：`pg_sleep` / `pg_read_file` / `dblink` / `lo_import`。`db/engine.py` 的 docstring 已经承认"只读会话拦不住 `SELECT pg_sleep(3600)`，自律不是强制"，这里把那句话补上
- **强制 `LIMIT`**：无则追加 `LIMIT 200`

执行走 `onto_readonly_conn`。`ReadOnlyViolation` / `GuardViolation` 捕获后转成 observation。

---

## 4. Schema 上下文

`agent/schema_card.py`。三块，启动时构建一次并缓存，按 `graph_version()` 失效。

### RDF 侧 —— 几乎零成本

直接序列化 `ontology/graph/diabetes-ontology-v2.json`（25 实体 + 48 关系，每属性带中文 description、type、enum values，每关系带 cardinality）。

**需补 3 个只在规则产物里出现、ER JSON 里没有的类**：`dmo:RiskStratification`、`dmo:RiskFactorHit`、`dmo:ContraindicationFlag`（分别见 `ontology/rules/51-*.rq`、`50-*.rq`、`40-*.rq` 的 CONSTRUCT 头）。

再加命名图清单（见 [GRAPHDB-USAGE.md](GRAPHDB-USAGE.md)）与三条 GRAPH 铁律。约 6–10k token。

### SQL 侧 —— 需新造，原料齐全

DDL 里约 20 处中文 `COMMENT ON` 信息密度极高（讲清了"为什么这样设计"和"不能怎么用"），但**没有任何代码读它们**。写一个 dumper：

```sql
SELECT c.relname, a.attname, format_type(a.atttypid, a.atttypmod),
       col_description(c.oid, a.attnum), obj_description(c.oid)
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid
WHERE n.nspname = 'diabetes' AND a.attnum > 0 AND NOT a.attisdropped
```

**只喂 14 张表**：`core_*`(6) + `pred_*`(2) + `map_*`(6)。约 3–5k token。

> 这个 dumper 自己走 `onto_conn`，不受 agent 的 `pg_catalog` 禁令约束 —— 禁的是 LLM 生成的 SQL，不是仓库自己的代码。

### 桥接表 —— 目前完全缺失，最容易出错 ⚠️

`rdf/emit.py` 是 **SQL 列名 ↔ RDF 谓词的唯一权威对照**，但它以命令式代码存在。模型要同时写两种查询，必须知道 `core_lab_result.trust_level` ↔ `dmo:valueTrustLevel`、`core_patient.sex` 的 `M/F` 在 RDF 里已被映射成 `Male/Female`。

**做法**：在 `emit.py` 里加声明式常量 `COLUMN_PREDICATE_MAP`，`emit()` 改为消费它 —— 保证对照表与实际发射逻辑不会分叉。`schema_card` 读这个常量。

再加一段固定的**编排铁律**（照 `query/hybrid.py` 开头）：SQL 收敛患者集 → `patient_iri()` → SPARQL `VALUES ?pat` 注入 → 按 `source_table + source_pk` 拼回原始行。

---

## 5. 工具集

`agent/tools.py`，7 个。**优先级刻意设计**：安全快路径在前，自由查询在后，prompt 里明说"模板能答的别自己写"。

| 工具 | 实现 | 复用 |
|---|---|---|
| `search_concept(text)` | `map_concept_ref` 的 `label ILIKE / code ILIKE / %s = ANY(alt_labels)` | 照搬 `hybrid.explain_gap` 的候选概念查询 |
| `patient_bundle(pid, sections)` | 七段返回体 | `hybrid.patient_bundle` |
| `run_template(name, patients)` | 6 个白名单模板 | `templates.render` + `GraphDBClient.sparql_csv` |
| `explain_gap(term)` | "为什么查不到" | `hybrid.explain_gap` |
| `sparql_query(query)` | **自由 SPARQL** → guard → `sparql_csv` → 零结果探针 | 新建 |
| `sql_query(query)` | **自由 SELECT** → guard → `onto_readonly_conn` | 新建 |
| `simulate(pid, assume)` | 条件推演 | `simulate.simulate`，assume 需过溯源校验 |

---

## 6. 「绝不生成数值」的三道机械兜底

不靠 prompt 自觉。

**一、prompt 硬禁令**（`agent/prompt.py`）：照抄 `README.md` 「明确不做的事」五条 + `src/skills/dmo-patient-graph-analysis/SKILL.md` 的禁令。

**二、`simulate` 的 assume 溯源校验**（`tools.py`）：每个 assume 项的 `value` 与 `unit` **必须以字符串形式出现在用户原始问题里**，否则拒绝调用：

> 假设值必须由用户显式给出。`7.9` 不在用户问题里 —— 你不能自己编。若要说明缺什么证据，请描述需要哪项检验，不要给数值。

剩下的校验（术语白名单、单位、日期）`simulate/hypothesis.py` 已经做得很死（13 条 `HypothesisError`），直接让它抛 —— 那些错误信息本身就是给模型看的好 observation，`README.md` 说的"未命中只记账，不猜"在这一层已经实现了。

**三、输出后置校验**（`agent/postcheck.py`），三类扫描：

| 类别 | 判据 |
|---|---|
| 剂量 | `\d+\s*(mg\|g\|ml\|U\|IU)\b`、`\b(bid\|tid\|qd\|qn\|po)\b` |
| 概率 / 时间窗 | 概率、可能性、发生率、`风险.*\d+%`、`未来\s*\d+\s*年`。**不能简单禁百分号** —— A1C 单位就是 percent，指南原文含 `6.5% or above`；判据照 `tests/test_api.py::test_no_dosage_and_no_probability_in_any_response` 写 |
| **伪造出处** ★ | 答案里每个 `sha256` **必须能在本轮实际执行过的工具返回里找到**，每段 `quote` 必须逐字来自某次工具返回 |

命中则打回让模型重写一次；仍命中则剥离该句并在返回体里标注。

> 第三条是 `README.md` 「不编造出处」在 agent 层的对应物。31 条 `SourcePassage` 的 quote 全部由 `verify_passages.py` 逐字回原文校验过 —— LLM 一句"根据指南通常认为"就能把这份工作废掉，所以必须机械查。

---

## 7. ReAct 主循环

`agent/loop.py`，手写 tool-calling loop（[DESIGN.md](DESIGN.md) 明说不用 SDK 的 tool_runner，学习目的）：

- 循环至 `stop_reason == "end_turn"`，`max_iterations` 默认 8；超限用已有证据强制收尾并标 `truncated: true`
- 每轮把完整 assistant content append 回 messages（保留 tool_use 块）
- system prompt 挂 prompt caching —— schema card 是固定前缀，每轮都发
- `trace.py` 记录每步：工具名、入参、guard 判定、行数、耗时、token

### LLM 客户端

`src/dmo/llm/client.py`，**复用仓库已有的 OpenAI 兼容配置** —— `ontology/tools/semantic_extract.py` 的 `llm_config()` 已经在从 `.env` 读 `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL_TEXT`，且 `.env` 里已配好可用端点。把这段抽进 `llm/client.py` 供两边共用（`semantic_extract.py` 改为 import 它，消掉重复）。

> **偏离 [DESIGN.md](DESIGN.md) 的记录**：技术栈表里写的是 `anthropic` SDK + `claude-opus-5`。改用 OpenAI 兼容接口的理由是零新增配置、现有 `.env` 直接能跑，且兼容层可指向任意端点。若要改回 anthropic，只需替换 `llm/client.py` 一个文件。

`pyproject.toml` 加 `agent = ["openai>=3.0.0"]` extra，沿用 `extract` 的隔离风格 —— 默认安装不带，CI 不受影响。

---

## 8. 返回体

```jsonc
{
  "patientId": "P90002",
  "question": "……",
  "answer": "……",
  "steps": [{ "n": 1, "tool": "sparql_query", "input": {},
              "guard": { "passed": true, "rewrites": ["自动追加 LIMIT 200"], "warnings": [] },
              "rowCount": 3, "elapsedMs": 120 }],
  "queriesExecuted": [{ "lang": "sparql", "text": "……", "guardVerdict": "pass", "rows": 3 }],
  "evidence": [{ "quote": "……", "sha256": "……", "supports": "……" }],
  "postcheck": { "dosage": "clean", "probability": "clean", "provenance": "clean" },
  "graphVersion": "……",
  "model": "……",
  "truncated": false,
  "nondeterminismNotice": "本端点由大模型规划查询路径，同一问题多次调用可能给出不同路径与措辞。所有实际执行的查询与结果原样保留在 queriesExecuted，可自行复核。需要确定性结论请用 /patients/{pid}/assessment 与 /simulate。",
  "disclaimer": "⚠️ 技术验证用途，不是医疗器械……"
}
```

`nondeterminismNotice` 是**必须**的：这是全项目第一个不确定的端点，得像 `dataQualityNotice` / `hypotheticalNote` 一样把话说明白。`queriesExecuted` 原样保留全部查询串，是这个端点唯一的可复核手段 —— 它替代了 `derivationHash` 的角色，但**替代得并不完全**，这是自由查询模式的固有代价。

---

## 9. 端点与 CLI

`api.py` 新增（放在 `simulate` 之后）：

```python
@app.post("/patients/{pid}/investigate")
def investigate_patient(pid: str, body: dict[str, Any]) -> dict[str, Any]:
    """ReAct 智能体：动态规划查询路径，自由生成 SPARQL/SQL 并跨 GraphDB + PG 取证。

    ⚠️ 与本 API 其他端点不同，这个端点**不确定**：查询路径由模型规划。
    确定性结论请用 /assessment 与 /simulate。
    """
```

错误映射：`question` 缺失 → 400；`AgentError` → 400；`SandboxError` / `KeyError` → 404；**LLM 未配置 → 503**（配置缺失不是调用方的错，不能报 400）。

`cli.py` 补 `dmo ask <患者号> "<问题>" [--json] [--max-steps N] [--show-queries]`。`--show-queries` 打印每条实际执行的查询与 guard 判定，人工复核用。

---

## 10. 测试

`tests/test_agent.py`，两层。**第一层比第二层重要得多** —— 它是唯一能被 CI 稳定守住的部分。

### 层一：guard 纯单测（无需 LLM、无需数据库）

| 用例 | 期望 |
|---|---|
| `GRAPH ?pg { ?pat dmo:patientId ?pid }` 无 `STRSTARTS` | 拒，理由含"反例夹具" |
| `GRAPH <urn:dmo:seed> { ?th dmo:lowerBound ?lo }` | 拒，理由含"静默少返" |
| 触及 `urn:dmo:data` | 拒 |
| `DELETE WHERE {…}` / `INSERT DATA {…}` | 拒 |
| 注释里写 `# INSERT` 的合法 SELECT | **放行**（验证 noise 剥离，对应 `engine.py` 那个坑） |
| SELECT 无 `LIMIT` | 放行 + `rewrites` 含追加 LIMIT |
| `SELECT … ; DROP TABLE core_patient` | 拒 |
| SQL 触碰 `sys_migration` / `pg_catalog` / `patient_analysis.` | 拒 |
| `SELECT pg_sleep(3600)` | 拒 |
| 合法的 `core_lab_result JOIN core_patient` | 放行 |

postcheck 单测：伪造 sha256 必须被剥离；`A1C 6.5%` 必须放行，`未来 5 年风险 30%` 必须命中。

### 层二：端到端（照 `conftest.py` 的模式，环境或 key 缺失则 `skip` 而非 `fail`）

- `test_investigate_never_writes_to_graphdb` —— 前后 `GraphDBClient.size()` 相等（照 `test_simulate.py`）
- `test_investigate_cannot_write_pg` —— agent 提交 INSERT 必须被拒
- `test_no_dosage_and_no_probability` —— 复用 `test_api.py` 的判据
- `test_evidence_sha256_all_traceable` —— 每个 sha256 都能在 `pred_factor_hit` 或 `SourcePassage` 里找到
- `test_agent_cannot_fabricate_assume_values` —— 用户原文不含数值时，`simulate` 调用必须被拒

---

## 实施顺序

| # | 内容 | 验收 |
|---|---|---|
| 0 | 本文档 + `DESIGN.md` 原则 1 处加指回本文的一行 | 两份文档不再互相矛盾 |
| 1 | `db/engine.py` 加 `onto_readonly_conn` + `ping()` 探测 | `dmo db status` 自证写不进去 |
| 2 | `agent/guard/{sparql,sql}.py` + **层一测试** | **零 LLM 依赖，独立验收** |
| 3 | `emit.py` 抽 `COLUMN_PREDICATE_MAP` + `agent/schema_card.py` | 现有 `dmo sync all` 行为不变 |
| 4 | `llm/client.py`（`semantic_extract.py` 改为 import） | 抽取脚本仍能跑 |
| 5 | `agent/{tools,prompt,postcheck}.py` | —— |
| 6 | `agent/{loop,trace}.py` | —— |
| 7 | `api.py` 端点 + `cli.py ask` | —— |
| 8 | 层二测试 + [API.md](API.md) 补章节 | 含"这个端点为什么不确定" |

**第 2 步做完必须停下来验一次。** guard 挡不住的东西，后面全是白搭。

---

## 验证

```bash
uv run pytest tests/test_agent.py -k guard -v
uv run dmo db status
uv run dmo ask P90002 "这个患者的糖尿病诊断凭什么是 Provisional，还差什么才能确诊？" --show-queries
uv run dmo ask P00016 "这个患者被分到这个风险层，哪几条因素真正参与了计分，哪几条没有？" --show-queries
uv run pytest tests/ -v
```

跑完两条 `dmo ask` 后逐条人工复核：

1. `queriesExecuted` 里每条 SPARQL 是否都带患者图守卫，知识侧是否都没写 `GRAPH`
2. `evidence` 里的 sha256 是否都能在 `queriesExecuted` 的返回中找到（不是模型编的）
3. 答案里有没有出现任何剂量数字、概率百分比、时间窗
4. GraphDB 三元组数跑前跑后是否一致（`GET /health` 的 `graphdbTriples`）

---

## 医疗免责

本端点与本仓库其余部分适用同一条：**技术验证用途，不是医疗器械，不构成医疗建议。不输出任何用药剂量，风险分层为规则式定性分层、非概率预测。**

额外一条只属于本端点：**查询路径由大模型规划，同一问题多次调用可能得到不同路径与措辞。** 需要可复现结论请用 `/assessment` 与 `/simulate`。
