# diabetes-ontology-agent

基于 OWL 本体的糖尿病领域智能体 —— 技术验证 / 学习项目。

三层结构：

1. **语义层**：糖尿病领域的 OWL/RDF 本体（V2 care-chain），配 SPARQL 规则层和 SHACL 约束层。
2. **患者事实层**：`hospital_zd.patient_analysis`（只读）→ `onto_db.diabetes`（可写）→ GraphDB 每患者一命名图。
3. **融合查询层**：SQL 收敛患者集合 → SPARQL 取语义结论 → 按 `source_pk` 拼回原始行，CLI + FastAPI 暴露。

核心产出不是本体本身，而是**「知道自己不知道」这件事能不能被工程化**。

📄 设计见 [docs/DESIGN.md](docs/DESIGN.md)，**API 使用说明见 [docs/API.md](docs/API.md)**。
演示页面在 [`demo/`](demo/)，与正式实现隔离。

---

## 这个项目实际证明了什么

接的是一个真实的医院库（400 患者 / 1600 条检验）。实测下来上游数据大面积不可用：

| 实测 | 后果 |
|---|---|
| 15 个 E11，每人 1 次检验、4 条结果 | 队列极小，无纵向随访 |
| 全库 **无 HbA1c 数值**（12 种子项名不含它） | 糖尿病管理最核心的指标缺失 |
| 检验值是 0~25 的随机数（血小板 15.3 而参考范围 100-300 却标"正常"） | 数值不可信 |
| `cdr_lis_result` **无单位列** | 数值无法与阈值比对 |
| `itemname='糖化血红蛋白'` 的检验单下挂的子项是 AST/尿蛋白/血小板/尿素氮 | 主子表语义错位 |
| `birthday` 有 329/400 落在未来（最晚 2063-09-14） | 年龄推不出来 |
| 每个患者恰好一条诊断 | 零共病 |

于是 15 个 E11 患者的风险分层结论**全部是 `Insufficient-Evidence`**，并说清三个具体原因。

同一个库的 `semantic_link` schema 里有一次前人的尝试（纯字符串匹配）：把「尿蛋白 10.4」
同时链到两个互斥疾病，confidence 都写 0.9，无单位、无阈值、无出处。它保留只读，作对照组。

```bash
uv run dmo demo compare --term 尿蛋白      # 两种做法并排
uv run dmo explain 糖化血红蛋白             # 诚实回答"为什么查不到"
uv run dmo show P00016                     # 真实患者的完整返回体
uv run dmo show P90002                     # 单次 A1C 7.4% ⟹ Provisional 而非 Confirmed
```

## 明确不做的事

- **不训练任何预测模型**，不输出概率、百分比、时间窗。风险分层是规则式定性分层，
  `tier` 是有序枚举不是分数 —— 这一点有测试断言兜底（`test_no_probability_or_time_window_anywhere`）。
- **不写上游库一个字节**。物理隔离（写连接的 DSN 根本不指向 `hospital_zd`）+ 语句守卫 + 内容指纹基线，
  三道锁，`dmo db guard-test` 可自证。
- **不输出任何用药剂量**。schema 层面就没有剂量字段。
- **不猜术语**。未命中只记账，没有编辑距离、没有 embedding。
- **不编造出处**。31 条 `SourcePassage` 的 quote 全部由 `verify_passages.py` 逐字回原文校验 + sha256。

---

## 端到端复现

前置：PostgreSQL 可达、GraphDB 在 `localhost:7200` 跑着、`.env` 配好 `PG_DSN` / `DMO_ONTO_DSN`。

```bash
uv sync --extra dev --extra serve --extra db

# ── 本体层（纯本地）────────────────────────────────────────────────
python3 ontology/tools/build_tbox.py           # ER 图 → OWL TBox
python3 ontology/tools/source_registry.py      # knowledges/ → GuidelineSource
python3 ontology/tools/verify_passages.py      # 每条 quote 逐字回原文校验
python3 ontology/tools/load_graphdb.py --create --load

# ── 患者事实层 ────────────────────────────────────────────────────
uv run dmo db status                 # 两库 + GraphDB 连通性与权限
uv run dmo db guard-test             # 只读守卫自证：写上游必须失败
uv run dmo db migrate
uv run dmo etl pull                  # hospital_zd → diabetes.stg_*（全量重建）
uv run dmo db baseline               # 记上游内容指纹
uv run dmo map sync-concepts         # GraphDB 概念 + 风险规则 → SQL 索引
uv run dmo map load-terms            # 人工策展的映射 CSV
uv run dmo map list-unmapped         # 术语归宿报告（12 个子项名必须 100% 有归宿）
uv run dmo db seed                   # 30 例场景队列
uv run dmo project run               # stg_ + sim_ → core_（V2 care-chain）
uv run dmo sync all                  # core_ → GraphDB 每患者一命名图

# ── 规则层与预测层 ────────────────────────────────────────────────
python3 ontology/tools/load_graphdb.py --rules --verify
uv run dmo predict run               # 分层结论物化进 pred_*
python3 ontology/tools/validate_shacl.py

# ── 验收与服务 ────────────────────────────────────────────────────
uv run pytest
uv run dmo serve --port 8100
```

幂等性可自证：`dmo etl pull`、`dmo db seed`、`dmo sync all` 跑两遍，
第二遍应当是 **零 PUT / 行数不变**。

## CLI

```
dmo db      status | guard-test | migrate | seed | baseline [--check]
dmo etl     pull [--table T] [--force]
dmo map     sync-concepts | load-terms | import-wfs | list-unmapped
dmo project run
dmo sync    patient --patient P90002 | all [--prune]
dmo graph   status
dmo predict run [--patient P]
dmo query   [template] --patient P …          # 白名单模板，不接受自由 SPARQL
dmo explain <术语>                             # 为什么查不到
dmo show    <患者号>                            # 完整返回体（七段）
dmo demo    compare [--term 尿蛋白]
dmo serve   [--port 8100]
```

## HTTP

`GET /health` · `GET /patients` · `GET /patients/{id}`（及 `/care-chain` `/assessment` `/risk` `/safety`）
· `GET /query/templates` · `POST /query/{template}` · `GET /terms/unmapped` · `GET /terms/explain`
· `GET /demo/compare`

返回体固定七段：`careChain` / `riskStratification` / `assertedFacts` / `inferredFacts` /
`sources` / `unmapped` / `dataQualityNotice`，外加 `disclaimer`。
后两段是「答不出来的部分必须说出来」这条承诺的载体。

---

> ⚠️ 本项目仅用于技术学习，不是医疗器械，不构成任何医疗建议。
> 所有输出均不包含具体用药剂量；风险分层为规则式定性分层，非概率预测。
