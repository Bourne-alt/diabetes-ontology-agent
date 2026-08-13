# 本体构建与语义抽取工具

这两个脚本读取同一张 ER 图，但负责语义层的不同部分：

| 脚本 | 职责 | 输入 | 主要输出 |
|---|---|---|---|
| `build_tbox.py` | 把 graph 中的实体、属性和关系编译成 **TBox（模式/词汇层）** | ER 图 JSON | `ontology/dist/tbox-generated.ttl` |
| `semantic_extract.py` | 按 graph 的 schema 从文档抽取 **ABox（实例/事实层）** | 同一张 ER 图 + 文档 | `ontology/dist/extract/<source-id>/<source-id>.ttl` 及审计报告 |

可以把它们理解为：`build_tbox.py` 定义“允许有哪些类和属性”，
`semantic_extract.py` 产生“具体有哪些实例和事实”。两者**不会互相调用**，但生成的 RDF
通过同一个 `https://example.org/dmo#` 词汇命名空间衔接；如果使用了不同版本的 graph，
ABox 可能引用 TBox 中不存在或含义已经变化的类/属性，查询通常只会静默漏结果。

## 一、`build_tbox.py` 怎么使用

在仓库根目录运行：

```bash
# 使用默认 graph，写入默认位置 ontology/dist/tbox-generated.ttl
python3 ontology/tools/build_tbox.py

# 指定 graph 和输出位置
python3 ontology/tools/build_tbox.py \
    --src ontology/graph/diabetes-ontology-v2.json \
    --out ontology/dist/tbox-v2.ttl

# 只在内存中生成并打印统计，不写文件
python3 ontology/tools/build_tbox.py --check
```

参数说明：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--src` | `ontology/graph/diabetes-ontology.json` | 输入 ER 图 JSON |
| `--out` | `ontology/dist/tbox-generated.ttl` | 输出 Turtle 文件 |
| `--check` | 关闭 | 生成并统计，但不写盘；它不是“与已有文件做 diff” |
| `--with-haskey` | 关闭 | 额外生成 `owl:hasKey`，仅供更换推理器后验证 |

脚本会机械生成：

- `entityTypes` → `owl:Class`；
- 实体的 `properties` → `owl:DatatypeProperty`，包括 domain、range、单位；
- `relationships` → `owl:ObjectProperty`，并根据基数生成函数性/反函数性；
- `enum` 值 → SKOS ConceptScheme/Concept；
- `tbox.route` → `class`（OWL 2 punning）、`skos` 或普通个体路线所需的骨架。

它不会生成 ER 图中无法表达的领域公理，例如 `rdfs:subClassOf`、`owl:disjointWith`、
`owl:equivalentClass` 和属性链。这些内容维护在
[`../src/dmo-axioms.ttl`](../src/dmo-axioms.ttl)，装载时与生成骨架合并到
`urn:dmo:tbox`。`tbox-generated.ttl` 是可重复生成的产物，**不要手改**。

> 不建议日常使用 `--with-haskey`。仓库注释记录了 `owlrl` 的 `prp-key` 会错误合并
> 键值不同的同类实例，进而造成不一致；默认 URI 已按标识属性确定性生成，不依赖它去重。

## 二、它和 `semantic_extract.py` 的关系

两者的共同契约是 graph，但读取的关注点不同：

| graph 内容 | `build_tbox.py` | `semantic_extract.py` |
|---|:---:|:---:|
| `entityTypes` / `properties` / `relationships` | 生成类和属性定义 | 生成 structured-output schema、校验字段和解析关系 |
| `tbox.route` | 决定 class / SKOS / individual 的 TBox 表达 | 不负责定义该路线 |
| `extraction.policy` | 不影响 TBox；所有类型都要定义 | 决定哪些类型交给 LLM，哪些跳过或机械生成 |
| 标识属性 `isIdentifier` | 可选生成 `owl:hasKey` | 用于实体识别；实例 URI 本身按规范确定性铸造 |

因此推荐顺序是：

```text
同一张 graph
   ├─ build_tbox.py       → TBox 骨架 ─┐
   └─ semantic_extract.py → ABox 事实 ─┼─ load_graphdb.py → 查询/推理
手写 dmo-axioms.ttl       → 领域公理 ─┘
```

`semantic_extract.py` 在文件生成阶段不要求 TBox 已经装入 GraphDB，因此技术上可单独运行；
但要让抽取结果得到类、domain/range、OWL 公理和推理语义，最终必须同时装载 TBox。

推荐的端到端流程：

```bash
# 1. graph 改动后重建 TBox
python3 ontology/tools/build_tbox.py \
    --src ontology/graph/diabetes-ontology.json

# 2. 先离线检查抽取计划（不需要 API key）
python3 ontology/tools/semantic_extract.py \
    --graph ontology/graph/diabetes-ontology.json \
    --doc ontology/knowledges/fda-diabetes-drug-classes.txt \
    --out ontology/dist/extract \
    --dry-run

# 3. 配好模型后执行真实抽取
python3 ontology/tools/semantic_extract.py \
    --graph ontology/graph/diabetes-ontology.json \
    --doc ontology/knowledges/fda-diabetes-drug-classes.txt \
    --out ontology/dist/extract

# 4. 查看将装载的命名图；确认后去掉 --dry-run 执行 PUT
python3 ontology/tools/load_graphdb.py --load --dry-run
python3 ontology/tools/load_graphdb.py --load
```

其中 `load_graphdb.py` 会把 `tbox-generated.ttl` 与 `dmo-axioms.ttl` 合并装入
`urn:dmo:tbox`，并自动发现 `ontology/dist/extract/<source-id>/<source-id>.ttl`，
把每篇文档装入独立的 `urn:dmo:extract:<source-id>` 命名图。

## 三、`semantic_extract.py` 快速使用

```bash
python3 ontology/tools/semantic_extract.py \
    --graph ontology/graph/diabetes-ontology.json \
    --doc   ontology/knowledges/VADOD-Diabetes-CPG-Patient-Summary_final_508.pdf \
    --out   ontology/dist/extract
```

**输入**：一张 ER 图（schema）+ 一个 UTF-8 TXT/PDF 文档路径（也可传目录，混合扫描两种格式）
**输出**：带出处、通过逐字校验的 Turtle + 一份可量化的质量报告

工作流由 graph 驱动，不含领域硬编码——换一张 graph、换一批文档，代码不用改。

PDF 使用 `pypdf` 提取文本。文本型 PDF 可直接处理；纯图片扫描件没有可校验的字符文本，
脚本会明确报错，需先用 OCR 工具生成带文本层的 PDF。安装抽取依赖：

```bash
uv sync --extra extract
```

目录模式会读取目录第一层中扩展名不区分大小写的 `.txt` 和 `.pdf` 文件：

```bash
python3 ontology/tools/semantic_extract.py \
    --graph ontology/graph/diabetes-ontology.json \
    --doc ontology/knowledges \
    --out ontology/dist/extract \
    --dry-run
```

目录模式遇到扫描件、加密 PDF 或非 UTF-8 TXT 时会打印警告并跳过，最后汇总跳过数量；
CI 如需任一文档不可读就失败，增加 `--strict-docs`。传入单个不可读文件时始终直接失败。

---

## 四、语义抽取产物

每篇文档一个目录 `<out>/<source-id>/`：

| 文件 | 内容 |
|---|---|
| `<source-id>.ttl` | **语义文件**。实例 + 关系 + PROV-O 出处，对应一个 named graph |
| `raw.jsonl` | LLM 原始输出，未校验。改校验规则后可用 `--from-raw` 重跑，不烧 token |
| `raw-links.jsonl` | 第二遍连边的原始候选；启用 link 且完成真实调用时生成 |
| `rejected.jsonl` | 被丢弃的记录 + 原因码。**这是审计入口，不是垃圾桶** |
| `report.json` / `report.md` | 质量指标 |
| `plan.json` | 仅 `--dry-run`：将发出的 schema、prompt、调用次数 |

## 五、语义抽取阶段

| # | 阶段 | 用 LLM | 说明 |
|---|---|:---:|---|
| 1 | load | ✗ | 读 graph，按 `extraction.policy` 决定哪些类型参与抽取 |
| 2 | register | ✗ | TXT 读取/PDF 文本提取；文档 → `GuidelineSource`（含 sha256），零幻觉 |
| 3 | chunk | ✗ | 对提取文本切块并保留字符偏移，尽量切在段落边界 |
| 4 | extract | ✓ | 每个 (chunk × entityType) 一次 structured output 调用 |
| 5 | verify | ✗ | quote 逐字校验 + enum/类型/属性名/谓词校验 |
| 6 | resolve | ✗ | 跨 chunk 实体消解、URI 铸造、关系连边 |
| 6b | link | ✓ | 把已解析实体作为候选，第二遍调用模型连边；`--no-link` 可跳过 |
| 7 | emit | ✗ | Turtle + PROV-O |
| 8 | report | ✗ | 质量指标，可卡成 CI 门禁 |

实体抽取和可选的第二遍连边会使用 LLM，其余阶段是确定性的，因此无 API key 仍能用
`--dry-run` 检查前置流程，或用 `--from-raw` 重放校验与生成流程。

## 六、四道防线

抽取的风险全在「模型编东西」。四道防线按成本从低到高排列：

**1. policy 分级——高危字段根本不让 LLM 碰**

在 graph JSON 的实体上标注 `extraction.policy`：

| policy | 行为 | 本项目适用 |
|---|---|---|
| `llm`（默认） | 正常 span-anchored 抽取 | 14 类 |
| `manual` | **直接跳过**。高危常量手写 seed，LLM 只可反向验证 | `DiagnosticThreshold`、`GlycemicTarget` |
| `registry` | 机械生成，不走 LLM | `GuidelineSource` |
| `derived` | 实例来自业务数据而非文档 | `Patient`、`ClinicalEncounter`、`LabResult` |

诊断切点错一个数字，整个 agent 就废。**这类常量声明成 `manual`，是把安全约束写进 schema 而不是写进 prompt。**

**2. schema 收窄——模型只能填图里有的槽**

tool schema 从 graph 现生成：enum 带 `enum` 约束、数值带 `type`、`additionalProperties: false`、**标识属性不给模型**（由 slug 确定性铸造，保证可重放）。

**3. quote 逐字校验——核心安全阀**

每个实例必须附带 `quote`：从原文逐字复制的片段。校验时做 Unicode NFKC + 空白归一 + 花体引号/破折号归一，然后要求 `quote in document`。对不上的**整条丢弃**并记入 `rejected.jsonl`。

quote 短于 24 字符也丢——太短容易蒙对，等于没校验。

**4. 冲突与悬空记账——不静默吞掉矛盾**

同一实体在不同 chunk 给出不同属性值时，先到先得但**记录冲突**；关系指向不存在的实体时记为**悬空**。两者都进报告，不悄悄抹平。

## 七、「高质量」的定义

不是形容词，是四个可测量的数：

| 指标 | 含义 | 异常时说明 |
|---|---|---|
| **quoteHitRate** | 通过逐字校验的比例 | 偏低 = 模型在编，或分块把句子劈开了 |
| **schemaSlotCoverage** | 图里定义的字段有多少真被填上 | 偏低 = 图设计过度，定义了文档根本不提供的字段 |
| **danglingRelationRate** | 指向不存在实体的关系占比 | 偏高 = 抽取顺序或分块有问题 |
| **avgMentionsPerEntity** | 每个实体被多少条记录支持 | 接近 1 = 消解没起作用，或实体确实只出现一次 |

CI 门禁：

```bash
python3 ontology/tools/semantic_extract.py \
    --graph ontology/graph/diabetes-ontology.json \
    --doc ontology/knowledges --out ontology/dist/extract \
    --min-quote-hit-rate 0.85
```

命中率低于阈值时非零退出。**这条是让它成为「工作流」而不是「脚本」的关键。**

## 八、离线模式

| 场景 | 命令 |
|---|---|
| 看会发多少次调用、prompt 长什么样 | `--dry-run` |
| 改了校验规则，重跑第 5–8 阶段 | `--from-raw <path>/raw.jsonl` |
| 只抽某几类 | `--only drugClass medication contraindication` |
| 节省第二遍连边调用 | `--no-link` |
| 目录中任一文档不可读即失败 | `--strict-docs` |

`--dry-run` 会汇总调用次数，超过 200 次时提示收窄。

换模型或端点可用 `--model`、`--base-url`，默认配置见“九、模型配置”。

TXT 的第 1–3、5–8 阶段只用标准库；PDF 的离线阶段也需要 `pypdf`。真实 LLM 调用需要完整的
`extract` 依赖：

```bash
uv sync --extra extract   # 或 pip install -r requirements.txt
```

## 九、模型配置

走 **OpenAI 兼容接口**，配置全部从仓库根目录的 `.env` 读（SiliconFlow / vLLM / Ollama 通用）：

| 变量 | 说明 |
|---|---|
| `OPENAI_API_KEY` | 密钥 |
| `OPENAI_BASE_URL` | 端点，如 `https://api.siliconflow.cn/v1` |
| `OPENAI_MODEL_TEXT` | 模型 ID |

命令行可覆盖：`--model`、`--base-url`、`--temperature`（默认 `0`——抽取是确定性任务，
调高只会提高编造 quote 的概率）。真实环境变量优先于 `.env`，方便 CI 用 secrets 覆盖。

`--dry-run` 和 `--from-raw` 不读取任何凭据。

> ⚠️ `.env` 已加入 `.gitignore`。不要提交它。

## 十、装载 GraphDB

生成的 `.ttl` 头部自带装载命令。按 named graph 幂等替换（`PUT` 不是 `POST`）：

```bash
curl -X PUT -H 'Content-Type: text/turtle' \
  --data-binary @ontology/dist/extract/fda-diabetes-drug-classes/fda-diabetes-drug-classes.ttl \
  'http://localhost:7200/repositories/dmo/rdf-graphs/service?graph=urn:dmo:extract:fda-diabetes-drug-classes'
```

一篇文档一个图，重抽只动一个图。详见 [docs/SEMANTIC-LAYER-PLAN.md](../../docs/SEMANTIC-LAYER-PLAN.md) §4。

---

## 十一、已知局限（别当成完成品）

1. **调用量是笨办法。** 每个 chunk × 每个实体类型各调一次；全量 26 篇 × 14 类 = **826 次调用**。
   多数分块并不包含多数类型，绝大部分调用会返回空数组。
   → 优化方向：先跑一次 router 调用筛出该分块含哪些类型，再定向抽取（1 + k 次而非 14 次）。
   代价是 router 漏判会直接变成召回损失，需要用 `--from-raw` 做 A/B 对比后再决定。当前用 `--only` 手动收窄。

2. **实体消解只做到 slug 精确匹配。** "SGLT2 Inhibitors" 和 "SGLT-2 inhibitors" 会被当成两个实体。
   → 需要别名表 / 外部术语（MONDO、ATC）对齐，属于 `imports_fetch.py` 的范围。

3. **quote 校验证明「原文有这句话」，不证明「这句话支持这个结论」。**
   模型可以引用一句真实的话，然后挂上一个与之无关的属性值。
   → 现有 `propertyEvidence` 是可选字段，应改为对关键属性强制；更彻底的做法是加一轮独立的 entailment 校验。**这是当前最大的残余风险。**

4. **跨 chunk 的关系抽不到。** 关系 target 用 canonicalName 匹配，若目标实体只出现在别的 chunk 且未被抽出，就是悬空。overlap 只能缓解不能消除。

5. **PDF 只处理文本层，不做 OCR，也不理解版面图像。** 多栏排版、表格和页眉页脚的读取顺序
   取决于 PDF 内部结构；扫描件需先 OCR。prompt 与 quote 校验共用同一份提取文本，因此不会因
   两套提取器不一致而静默误判，但复杂表格仍可能丢失结构语义。

6. **关系依赖第二遍模型连边。** 第一遍按单一实体类型调用，看不到其他类型已解析出的
   候选实例，关系召回天然较弱；当前实现已增加第二遍 `link`，把全文和已消解实体清单交给模型，
   并对谓词、端点和证据 quote 再校验。它提高了可连性，但增加调用成本，且仍可能漏掉隐含或跨文档关系；
   使用 `--no-link` 时关系边很可能仍为 0。

7. **类型边界模糊。** 同一个概念会被塞进多个类型（如 Microalbuminuria 同时进 `symptom` 和
   `complicationStage`）。加了「不要同时塞进多个类型」的 prompt 约束后有改善（riskFactor 从 3 降到 1，
   剔掉了明显不对的），但没根治；第一遍单类型调用仍看不到全局类型分配。
