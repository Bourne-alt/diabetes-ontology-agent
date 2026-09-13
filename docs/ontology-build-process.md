# 本体搭建的过程

> 依据 `ontology/tools/` 下 8 个脚本的实际实现整理，不是设计意图的复述。
> 配图：[ontology-build-flow.png](./ontology-build-flow.png)（源文件 `ontology-build-flow.svg`）

## 一句话概括

**一张 ER 图是唯一契约，模式层（TBox）和事实层（ABox）都从它机械生成；
凡是机器能算出来的绝不手写，凡是错了会出人命的常量绝不交给 LLM；
每一层都有一道会让 CI 非零退出的门禁，而不是一份"仅供参考"的报告。**

---

## ① 契约层：一张图定住所有下游

`ontology/graph/diabetes-ontology-v2.json` 是全流程的单一事实源。它不只是画给人看的 ER 图，
里面三个字段直接决定了后面所有脚本的行为：

| 字段 | 谁在读 | 决定什么 |
|---|---|---|
| `entityTypes` / `properties` / `relationships` | build_tbox + semantic_extract | 生成什么类和属性；抽取时给模型什么 schema |
| `tbox.route` | build_tbox | 这个类型的实例在 OWL 里是 `owl:Class`（punning）、`skos:Concept` 还是普通个体 |
| `extraction.policy` | semantic_extract | 这个类型交给 LLM 抽（`llm`）、机械生成（`registry`）、来自业务库（`derived`），还是**根本不许模型碰**（`manual`） |

同一层还有三类**不由图生成、必须人写**的输入：

- `ontology/src/dmo-axioms.ttl` —— `rdfs:subClassOf`、`owl:disjointWith`、`owl:equivalentClass`、
  属性链。**ER 图里根本没有这些信息**，所以 `build_tbox.py` 也不假装能生成它们。
- `ontology/src/dmo-threshold-seed.ttl`、`dmo-risk-map.ttl` —— 诊断切点、控制目标、风险因子桥。
  这些是策展常量，policy 一律标 `manual`。
- `ontology/shapes/*.shacl.ttl`（2 份）、`ontology/rules/*.rq`（10 条）。

语料侧是 `ontology/knowledges/`，52 份指南与说明书原文（TXT / PDF）。

---

## ② 生成层：三条互不调用的支线

三个脚本读同一张图，但关注点不同，彼此**不互相调用**，只靠命名空间
`https://example.org/dmo#` 对齐。这条约定是硬的：TBox 和 ABox 用了不同版本的图，
SPARQL 不会报错，只会静默返回空集。

### 2.1 `build_tbox.py` —— 图 → OWL TBox 骨架

只做"可机械生成的那一半"：

- `entityTypes` → `owl:Class`
- `properties` → `owl:DatatypeProperty`（带 domain / range / 单位）
- `relationships` → `owl:ObjectProperty`，按基数推函数性 / 反函数性
- `enum` → SKOS `ConceptScheme` + `Concept`
- `tbox.route` → class（OWL 2 punning）/ skos / individual 三条路线的骨架

产物 `ontology/dist/tbox-v2.ttl` **幂等重生成、禁止手改**，装载时才和手写的 `dmo-axioms.ttl`
合并进同一个命名图。默认输出路径刻意等于装载脚本读的那个文件——早期两者不一致时，
双方可以各自陈旧而互不报错。

### 2.2 `source_registry.py` —— 语料 → 出处登记（零 LLM）

`knowledges/` 每份文件生成一个 `dmo:GuidelineSource`，全程不经过模型，因此**不可能有幻觉**。
只做四件事：

1. 算 **sha256**：语料一改，所有从它抽出的三元组自动过期，重跑有明确触发条件；
2. 文件名前缀 → 发布机构（NIDDK / CDC / FDA / NHC）；
3. 正则从正文抠发布 / 审阅年份；
4. 用"长句计数"判定这份文件到底有没有正文，还是只抓到了导航壳。

**刻意不填 `sourceUrl`**：原文里没有 URL，凭文件名猜链接就是编造出处，而 provenance 是这个项目
相对纯 RAG 的核心卖点，宁可留空。

### 2.3 `semantic_extract.py` —— 语料 → ABox 事实（八阶段，只有两步用模型）

```
load → register → chunk → ✦extract → verify → resolve → ✦link → emit → report
```

只有 `extract`（每个 chunk × 每个实体类型一次 structured output）和第二遍的 `link`（连边）
调用 LLM，其余全是确定性的——所以无 API key 也能 `--dry-run` 查前置流程，
改了校验规则可以 `--from-raw` 零 token 重放 5–8 阶段。

**四道防线**（按成本从低到高）：

1. **policy 分级**——高危字段根本不进 prompt。诊断切点错一个数字整个 agent 就废，
   所以把安全约束写进 schema，而不是写进 prompt。
2. **schema 收窄**——tool schema 由图现生成：enum 带 `enum` 约束、`additionalProperties: false`、
   标识属性**不给模型**（由 slug 确定性铸造，保证可重放）。
3. **quote 逐字校验**——每个实例必须附原文逐字片段，做 NFKC + 空白 + 引号归一后要求
   `quote in document`；对不上**整条丢弃**并记进 `rejected.jsonl`；短于 24 字符也丢（太短容易蒙对）。
4. **冲突与悬空记账**——同一实体跨 chunk 给出不同值时先到先得但**记录冲突**；
   关系指向不存在的实体记为**悬空**。两者都进报告，不静默抹平。

产物一篇文档一个目录：语义 TTL、`raw.jsonl`（原始输出）、`rejected.jsonl`（**审计入口，不是垃圾桶**）、
`report.json` / `report.md`。

### 2.4 `build_playground_rdf.py` —— 旁支

把图编成对齐 Fabric IQ 命名规范的 RDF/XML，供 Ontology Playground 设计器
"Edit RDF → 粘贴 → Load into Designer"无损往返，并顺带跑一遍 Playground 自己的校验规则。
不参与主构建链。

---

## ③ 门禁层：红了就停，不是发报告

| 脚本 | 检查什么 | 失败形态 |
|---|---|---|
| `verify_passages.py` | 拿人已写好的 quote **回语料逐字核对** + contentHash 复算 | `MISSING`（出处是编的）/ `HASH`（改了 quote 没重算）/ `NOSOURCE`（追溯链断） |
| `validate_shacl.py` | pyshacl 全量体检，纯 Python，不依赖 GraphDB 在跑 | 对基线 `known-violations.tsv` 逐条比对，★ 新增即非零退出 |
| `semantic_extract.py --min-quote-hit-rate` | quote 命中率 | 低于阈值非零退出 |

两个设计上的要点：

- **`verify_passages.py` 的方向是反的**：不让模型去原文里找数字，而是拿着已写好的 quote
  回原文核对。方向一反，风险就从"编造"降级成"找不到"。
- **SHACL 用基线文件而不是 `--allow N`**：违规里混着夹具的刻意违规（该报，报不出来才是 bug）
  和抽取产物的真缺陷。`--allow 7` 会把两类一起埋掉——新增一条真缺陷、同时修好一条夹具，
  总数还是 7，CI 全绿而问题溜进去了。基线按 focusNode + 消息逐条比对。

---

## ④ 装载层：`load_graphdb.py`

```bash
python3 ontology/tools/load_graphdb.py --create   # ruleset=owl2-rl-optimized，建仓时定死
python3 ontology/tools/load_graphdb.py --load     # 按命名图整图 PUT
python3 ontology/tools/load_graphdb.py --rules    # rules/*.rq 物化进 urn:dmo:inferred
python3 ontology/tools/load_graphdb.py --verify   # 验收查询
```

命名图布局：

| 命名图 | 内容 |
|---|---|
| `urn:dmo:tbox` | `tbox-v2.ttl` + `dmo-axioms.ttl`（先在客户端合并再 PUT） |
| `urn:dmo:seed` | 阈值 + 风险因子桥 |
| `urn:dmo:sources` | GuidelineSource |
| `urn:dmo:data` | 患者事实 |
| `urn:dmo:extract:<sid>` | 一篇文档一个图，重抽只动一个图 |
| `urn:dmo:inferred` | 规则物化结果 |
| `…#SHACLShapeGraph` | **必须最后装载** |

四条从踩坑里长出来的硬规则：

1. **用 PUT 不用 POST**——构建必须幂等。推论：多个源文件指向同一命名图时必须先在客户端合并，
   否则后一个文件会把前一个冲掉。
2. **ruleset 建仓时定死**，事后改要全量 reload；脚本建完会**回读校验**，不符直接退出——
   否则你会得到一个推理能力不符预期、但看起来一切正常的库。
3. **shapes 图强制排到最后**。GraphDB 11 实测忽略建仓时的 `validationEnabled=false`
   （建完读回来仍是 `true`，事后 PUT 改也纹丝不动）。改用不依赖开关的办法：
   SHACL 只在 shapes 图非空时才触发，所以把它排到装载序列末尾，前面所有图写入时校验无从触发。
   **等价于"先关后开"，且不依赖任何配置项。**
4. **源文件缺失显式 WARN，不静默跳过**。曾经 `ontology/data/` 被误删，`.exists()` 静默过滤
   让装载"成功"了，GraphDB 里的数据其实是上一轮残留——图看着对，实际已和磁盘脱节。

HTTP 原语抽在 `graphdb_http.py`，纯标准库零依赖，与运行时 `src/dmo/graph/` 共用一份。

---

## 端到端命令

```bash
python3 ontology/tools/build_tbox.py                       # 图 → TBox
python3 ontology/tools/source_registry.py                  # 语料 → 出处
python3 ontology/tools/semantic_extract.py \
  --graph ontology/graph/diabetes-ontology-v2.json \
  --doc ontology/knowledges --out ontology/dist/extract \
  --min-quote-hit-rate 0.85                                # 语料 → ABox（带门禁）
python3 ontology/tools/verify_passages.py                  # 出处逐字核对
python3 ontology/tools/validate_shacl.py                   # SHACL 全量体检
python3 ontology/tools/load_graphdb.py --create --load --rules --verify
```

---

## 已知残余风险（画进流程图里，因为还没解决）

1. **quote 校验 ≠ 蕴含校验。** 只证明"原文有这句话"，不证明"这句话支持这个结论"。
   模型可以引用一句真话再挂上无关的属性值。`propertyEvidence` 目前还是可选字段——**当前最大残余风险**。
2. **实体消解只做到 slug 精确匹配。**「SGLT2 Inhibitors」和「SGLT-2 inhibitors」是两个实体，
   需要别名表 / MONDO·ATC 对齐。
3. **调用量是笨办法。** 每 chunk × 每类型各调一次，绝大部分返回空数组。
   优化方向是先跑一次 router 筛出该分块含哪些类型（1+k 次而非 14 次），代价是 router 漏判直接变成召回损失。
4. **跨 chunk 关系抽不到。** 关系 target 按 canonicalName 匹配，目标实体不在本 chunk 就是悬空，
   overlap 只能缓解不能消除。
5. **PDF 只处理文本层，不做 OCR。** 多栏、表格、页眉的读取顺序取决于 PDF 内部结构。
6. **类型边界模糊。** 同一概念被塞进多个类型；prompt 约束有改善但未根治——第一遍单类型调用看不到全局分配。
