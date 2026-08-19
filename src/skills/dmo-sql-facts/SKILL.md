---
name: dmo-sql-facts
description: 在患者事实库（PostgreSQL `diabetes` schema，30 张表）上写只读 SQL 取原始事实行。当用户问「有多少患者 / 哪些患者 / 按某维度筛」「某患者最近一次某检验的原始值」「某个术语系统认不认识」「跨患者统计多少人命中某因子、多少人判不了」「这条结论背后的原始行长什么样」，而现成的语义端点与参数化模板都表达不了这个维度时使用。本 skill 规定了六大表族的选表决策、关键列的解释口径（fact_origin / trust_level / counted_in_tier / insufficient_reason / birth_year=NULL）、八条 SQL 硬约束，以及零行结果的三种可能。Use when the answer requires ad-hoc SQL over the diabetes patient fact database rather than a semantic endpoint.
license: 与本仓库同许可
compatibility: 需要一个能对患者事实库提交只读 SQL 的工具（外部平台注册的数据库查询工具，或本机 psql + .env 的 PG_DSN）。凭据由服务端持有，本 skill 不含也不需要 DSN。
allowed-tools: Bash(psql:*) Bash(curl:*) Bash(uv:*) Read
metadata:
  repo: diabetes-ontology-agent
  version: "1.0"
---

# 患者事实库的动态 SQL 查询

## 这个 skill 在优化什么

**SQL 取到的是事实行，不是有出处的结论。**

这是全仓库最容易毁掉核心卖点的一层。语义端点的返回体带 `ruleId`、`ruleVersion`、
逐字 `quote` 和 `sha256`；你自己 `WHERE result_value >= 7.0` 比出来的大小关系一样都没有。
两个数字看起来一模一样，但一个能被追责，另一个不能。

所以本 skill 的第一条不是"怎么写 SQL"，是**"什么时候不许写 SQL"**。

## 先判断：这个问题该不该用 SQL

| 用户在问 | 走哪里 | 为什么 |
|---|---|---|
| 某患者的阈值判定 / 风险档位 / 用药安全信号 | **不写 SQL** → `/patients/{pid}/assessment` `/risk` `/safety` | SQL 里没有出处、没有 ruleId、没有逐字引文 |
| 这条结论凭什么 | **不写 SQL** → `/graph/provenance`（skill: dmo-provenance-trace） | 溯源链要走图，SQL 只到 `stg_*` 那一行为止 |
| 某个术语为什么查不到 | **先** `/terms/explain` | 它已经把四类归宿分好了，SQL 只在需要看 `hit_count` 之类明细时补充 |
| 有哪些患者 / 按 ICD-10、性别、年份筛 | **先** `GET /patients` | 它表达不了的维度才落到 SQL |
| 跨患者对照、最新检验、诊断证据、照护链明细 | **先** `POST /query/{template}` 六个白名单模板 | 模板走的是同一份 `hybrid.py`，答案必然一致 |
| 以上都表达不了的计数、筛选、分组、原始行 | ✅ 本 skill | 这才是动态 SQL 该补的空白 |

> 判据一句话：**问「是什么」用 SQL，问「凭什么」不用 SQL。**

## 调用约定

服务基址 `http://localhost:8100`（`uv run dmo serve --port 8100` 启动，只绑 127.0.0.1）。
**本 skill 不带封装脚本** —— 下面每条都是可直接粘贴的完整 curl，因此这四件事由你自己负责：

1. **连不上 ≠ 没有数据。** curl 报 `Connection refused` ⟹ 服务没起，先启动它，或全程
   改用 `uv run dmo …` CLI（**与 API 走同一份 `query/hybrid.py`，答案必然一致**）。
   **绝不因为够不着服务就改用常识作答。**
2. **必须看 HTTP 状态码**，别把 `{"detail":"…"}` 当数据读。排查时加
   `-w '\n-- HTTP %{http_code} --\n'`。
3. **POST 必须带 `-H 'Content-Type: application/json'`**，body 形状见各阶段示例。
4. 状态码分支：

   | 码 | 含义与处置 |
   |---|---|
   | **400 / 422** | 参数或 body 形状不对。模板端点要**非空**患者编号数组 |
   | **404** | 患者或模板不存在，不要猜另一个 ID |
   | **503 / 500** | 依赖不可用。此时 SQL 侧可能仍可查，但**语义层结论一律停** |

   SQL 工具本身报错时：**原样说明错在哪并修正 SQL，不要把失败的查询当成"查无此数据"。**

## 库与访问方式

患者事实库（业务上称 `patient_db`）是 PostgreSQL，患者数据全部在 **`diabetes` schema** 下，
共 30 张表。连接凭据由服务端持有 —— 你既拿不到也不需要 DSN，直接通过数据库查询工具提交 SQL。

**所有表名必须写全限定形式 `diabetes.<表名>`。** 不要依赖 `search_path`。

## 阶段 1 · 先探 schema，再写 SQL（不可跳过）

你对这个库没有先验知识。**任何一次动态查询之前，先确认表和列真实存在。**

- 列名猜错 → 报错，至少你知道错了；
- **取值猜错**（比如以为 `fact_origin` 里有 `'real'`）→ **空集**，而空集和"没有这个患者"长得一模一样。

第二种才是危险的那种。三个可复制的探查模板：

```sql
-- ① 列名与类型
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'diabetes' AND table_name = 'core_lab_result'
ORDER BY ordinal_position
LIMIT 60;

-- ② 表与列的中文注释 ★ 信息密度远高于列名本身
SELECT c.relname AS tbl,
       a.attname AS col,
       obj_description(c.oid)               AS table_comment,
       col_description(c.oid, a.attnum)     AS column_comment
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0
WHERE n.nspname = 'diabetes' AND c.relname = 'core_lab_result'
LIMIT 60;

-- ③ 陌生列的取值域
SELECT DISTINCT fact_origin FROM diabetes.core_patient LIMIT 20;
```

**② 是这一步的重点。** 这个库的注释里写了大量判定口径 —— 进表门槛、单位约定、
NULL 的含义、哪些行不参与判定 —— 先读注释再解释数据。

schema 探查是**唯一**允许碰 `information_schema` / `pg_catalog` 的场景。
取业务事实时不许再碰它们。

## 阶段 2 · 表族地图 —— 先选族，再选表

30 张表分六族。**筛表的第一步是判断问题落在哪一族**，不要一上来就扫全部表。

| 前缀 | 表 | 装什么 | 能不能当结论依据 |
|---|---|---|---|
| `core_` | `core_patient` `core_encounter` `core_lab_result` `core_observation` `core_diagnosis` `core_medication_use` | 规范化后的患者事实。已过术语映射与单位换算 | **可以**。回答患者事实问题的默认主力 |
| `map_` | `map_concept_ref` `map_lab_term` `map_icd10` `map_drug_term` `map_unit_conversion` `map_unmapped_term` `map_risk_rule` | 术语映射与未映射记账 | **可以**，用于"这个词认不认识 / 为什么查不到"。`verify_status`、`value_kind`、`has_passage` 决定它可不可用于判定 |
| `pred_` | `pred_factor_hit` `pred_risk_stratification` | 规则层产物：因子命中、风险分层 | **可以**，但必须连 `rule_id`/`rule_version`/`counted_in_tier`/`insufficient_reason` 一起读，不许只取 `tier` |
| `sim_` | `sim_patient` `sim_encounter` `sim_lab_result` `sim_observation` `sim_diagnosis` `sim_medication_use` | **演示队列，30 例，不是真实患者**。结构与 `core_*` 平行，极易误当真实数据 | 只能在明确标注"演示数据"的前提下用。**默认不查** |
| `stg_` | `stg_patient_basic` `stg_outpatient_reg` `stg_lis_result` `stg_lis_detail` `stg_diagnose` `stg_op_order` | 上游原始暂存行，**未过质量门槛** | **不能**当判定依据。只用于回答"原始那一行长什么样" |
| `sys_` | `sys_migration` `sys_rdf_sync_state` `sys_upstream_baseline` | 运维元数据 | **不查**。没有任何临床含义 |

### 选表决策

| 用户在问 | 查哪里 |
|---|---|
| 某患者最近一次某项检验的值 | `core_lab_result`（数值项）；查不到再看 `core_observation`（定性项、缺单位项、未映射项都落在这里） |
| 某项检验为什么没有数值判定 | `map_lab_term` 的 `value_kind` / `verify_status` / `unit_target` |
| 某个术语系统认不认识 | `map_concept_ref`、`map_icd10`、`map_drug_term`；查不到看 `map_unmapped_term` 的 `hit_count` |
| 跨患者统计（多少人命中某因子、多少人判不了） | `pred_factor_hit`、`pred_risk_stratification`，按 `counted_in_tier`、`insufficient_reason` 分组 |
| 这条结论背后的原始行 | 先从 `core_*` 取 `source_table` + `source_pk`，再回查对应 `stg_*` |

## 阶段 3 · 关键列语义

按下面的口径解释，**不要按字面直觉**：

| 列 | 口径 |
|---|---|
| `fact_origin` | `ehr-legacy`（真实上游）/ `derived`（投影生成）/ `demo-cohort`（演示）。**判断数据真假只看这一列，不看患者编号长什么样。** 值为 `demo-cohort` 时回答里必须标注"演示数据" |
| `demo_scenario` | 非空即说明这行是为演示构造的 |
| `trust_level` | `Unverified` 的数值**不得用于临床推断，也不得当作可信测量值复述**，只能说明这是数据质量限制 |
| `verification_status` | `Provisional` **不是确诊**。单次检验落入诊断区间 ≠ `Confirmed` |
| `caveat` | 非空必须原样带进回答，不得省略、不得改写 |
| `counted_in_tier`（`pred_factor_hit`） | `false` = 命中了但不参与档位计算，因为找不到可逐字引用的指南原文。可列为已观察因子，但必须说明它不计入 tier 及其出处缺口 |
| `quote` / `sha256`（`pred_factor_hit`） | 出处只能从这两列**原样取**。`counted_in_tier=true` 而 `sha256` 为空是异常，要如实报告 |
| `insufficient_reason`（`pred_risk_stratification`） | `tier=Insufficient-Evidence` 时必须同时说明这一列。它不是 Low、不是无风险、不是系统故障 |
| `monitoring_gap` | 单独列出，不能藏在总结里 |
| `source_value` / `source_unit`（`core_lab_result`） | 非空时必须同时说明原始值/单位与换算后的值/单位 |
| `source_table` / `source_pk` | 溯源到 `stg_*` 原始行的唯一途径 |
| `birth_year`（`core_patient`） | 可以为 NULL，表示上游生日不可信而被主动置空（400 人里 329 人生日落在未来）。**NULL 不等于"没有这个患者"，也不许据此推算年龄** |

## 阶段 4 · 写 SQL 的八条硬约束

1. **只读。** 只提交 `SELECT`。`INSERT`/`UPDATE`/`DELETE`/DDL 一律不行，包括"先建个临时表"这类想法。
2. **不写 `SELECT *`。** 显式列出你要的列 —— 你得为每一列的解释负责，取回来解释不了的列只会制造幻觉。
3. **必须带 `LIMIT`。** 探查类 `LIMIT 20` 起步；聚合查询也要限制分组数。
4. **必须带 `WHERE`。** 除非用户明确要全库计数，否则不做无条件全表扫描。
5. **不跨 schema。** 只碰 `diabetes`；出现其它 schema 前缀说明这条 SQL 写错了。
6. **`core_*` 与 `sim_*` 不 UNION、不 JOIN、不放进同一个聚合。** 真实患者和演示患者混进一个数字里，这个数字就作废了。
7. **不用 SQL 复现规则层。** 不写 `WHERE result_value >= 7.0` 之类的自制切点。阈值来自本体，判定来自规则层。
8. **查询失败照实报。** 报错就原样说明错在哪并修正，不要把失败的查询当成"查无此数据"。

## 阶段 5 · 结果的解释规则

**零行不等于"正常""没有风险""不存在"。** 先区分三种可能：

| 可能 | 怎么排除 |
|---|---|
| 条件写错了 | 去掉 `WHERE` 的一个条件重跑，或 `SELECT DISTINCT` 看取值域 |
| 术语没映射上 | 查 `map_unmapped_term` 的 `hit_count`，或调 `/terms/explain?term=X` |
| 确实没有记录 | 前两条都排除掉之后才能这么说 |

分不清就说分不清。

其余三条：

- 回答里必须交代这条事实来自哪张表 —— `core_*` / `stg_*` / `sim_*`，读者据此判断可信度。
- SQL 取到的是**事实行，不是有出处的结论**。需要"凭什么"时继续走出处层（skill: dmo-provenance-trace）。
- 跨患者统计要说明口径：过滤了哪些 `fact_origin`、是否排除了演示队列、`counted_in_tier=false` 的行算没算进去。

## 交付前自检

- [ ] 这个问题真的没有现成的语义端点或模板能答？
- [ ] 写 SQL 之前确认过表和列存在？读过列注释？
- [ ] 每条 SQL 都带 `WHERE` 和 `LIMIT`，没有 `SELECT *`？
- [ ] `core_*` 与 `sim_*` 有没有混进同一个数字？
- [ ] 有没有用 `WHERE value > X` 自制阈值判定？
- [ ] 零行有没有区分"条件写错 / 术语未映射 / 确实无记录"？
- [ ] 回答里交代了数据来自哪张表、`fact_origin` 是什么？
- [ ] `trust_level=Unverified` 的值有没有被我当成可信数值复述？

## 什么时候**不要**用这个 skill

- 需要阈值判定、风险档位、用药安全信号 → 语义层端点，见 skill `dmo-patient-graph-analysis`。
- 需要"凭什么" / 逐字出处 / 断链 → skill `dmo-provenance-trace`。
- 需要裁决别人给的引用或结论 → skill `dmo-adjudicate`。
- 需要写库、建表、跑 ETL → `uv run dmo db|etl|map|sync`，不走本 skill。
