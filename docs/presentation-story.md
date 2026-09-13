# Presentation Story

## Deck Strategy

### Communication Job

By the end, **技术大会观众、架构评审者与产品技术决策者** should **理解并认可该项目的差异化不在于“又做了一个医疗问答 Agent”，而在于把知识构建、患者事实、确定性推理和证据边界连成了一套可验证的工程系统**。

### Core Narrative Arc

```text
真实数据无法支撑可靠回答
        ↓
字符串匹配与纯 LLM 会制造“看似合理的确定性”
        ↓
项目选择先工程化“知道自己不知道”
        ↓
构建可重建、可审计的糖尿病本体知识库
        ↓
将知识层与患者事实层通过确定性规则连接
        ↓
用真实案例证明单位、上下文、复测与来源会改变结论
        ↓
把推演、溯源和裁决开放给外部 Agent
        ↓
诚实说明已经证明什么、还没有证明什么
```

### Recommended Length

17 页。适合约 20–30 分钟的技术项目汇报；若需要压缩到 12 页，可合并 Slide 7/8、10/11、12/13、15/16，并删除 Slide 9 的独立数据流页。

---

## Slide 01

### 页面标题

**当医疗数据不足以回答时，系统能否诚实地停下来？**

### 这一页要回答的问题

为什么这个项目值得听众花时间了解？

### 核心观点

项目追求的不是“回答所有问题”，而是让每个回答都知道自己的证据边界：能判断时给出规则和来源，不能判断时明确说出缺什么、为什么缺。

建议页面副标题：

> Diabetes Ontology Agent：可构建、可推理、可追溯的糖尿病语义证据系统

### 为什么这一页必须存在

技术项目汇报需要先建立一个有张力的核心问题。若从 OWL、GraphDB 或代码规模开场，非本体领域观众会立刻失去上下文。

### 与上一页的逻辑关系

开场页，无上一页。它提出整个汇报最后需要回答的中心问题。

### 推荐表现形式

**Hero Statement**。极简画面：左侧一个看似明确的医疗结论，右侧一个醒目的“Evidence Insufficient”，中间用断裂的证据链表达风险。不要放技术栈清单。

---

## Slide 02

### 页面标题

**真实世界的数据，首先暴露的不是答案，而是缺口**

### 这一页要回答的问题

项目面对的真实数据到底有多难用？

### 核心观点

仓库记录的上游实测揭示了系统必须面对的现实：

- 400 名患者中只有 15 个 E11，且几乎没有纵向随访；
- 全库没有可用 HbA1c 数值；
- 1600 条检验值缺单位且数值可信度不足；
- 329/400 个生日落在未来；
- 每位患者恰好一条诊断，几乎无法形成共病证据。

这些不是清洗后可以轻易忽略的“小瑕疵”，而是直接决定系统能否下结论的证据条件。

代码/仓库证据：`README.md`、`docs/PATIENT-GRAPH-FUSION-PLAN.md`、`src/dmo/db/seed/lab_term_map.csv`、`tests/test_scenarios.py::test_real_ehr_patients_are_all_insufficient_evidence`。

### 为什么这一页必须存在

它把项目从“技术爱好”变成“真实问题驱动”。后续所有关于可信度、单位、未映射状态和 `Insufficient-Evidence` 的设计，都由这一页自然产生。

### 与上一页的逻辑关系

上一页提出“系统何时应该停下来”；这一页说明，真实医疗数据中需要停下来的情况远比想象中多。

### 推荐表现形式

**Data Visualization**。用一个大数字“400 patients”作为底图，叠加 4 个缺口标注；重点突出“0 usable HbA1c”和“1600 results without units”。页脚小字注明这些为仓库记录的历史实测，本次汇报未重新连接外部数据库复测。

---

## Slide 03

### 页面标题

**传统方案最危险的错误，是给出一个看起来合理的答案**

### 这一页要回答的问题

为什么字符串匹配、普通规则或纯 LLM 不够？

### 核心观点

普通实现容易忽略四类“不会报错的错误”：

- 名称相似，却不是同一个检验概念；
- 数值存在，却没有可比较的单位；
- 阈值命中，却忽略人群上下文与复测要求；
- 引用听起来像指南，却无法逐字回到来源。

仓库中的典型反例是“尿蛋白 10.4”：既有字符串方案把它同时连到两个互斥疾病，confidence 都是 0.9；本项目则识别它是定性项目、缺少有效单位和 UACR 语义，因此拒绝数值判定。

### 为什么这一页必须存在

只有先解释“普通做法错在哪里”，观众才会理解为什么项目需要 OWL、SPARQL、SHACL 和来源哈希这些看似较重的技术。

### 与上一页的逻辑关系

上一页说明数据有缺口；这一页进一步指出，现有方案会把缺口掩盖成确定性答案。

### 推荐表现形式

**Comparison / Before–After**。左侧“字符串/LLM：尿蛋白 10.4 → 两个疾病，confidence 0.9”；右侧“本项目：qualitative + unmappable → 不参与判定；需要 UACR”。避免代码截图。

---

## Slide 04

### 页面标题

**我们的设计反转：先把“不知道”变成系统能力**

### 这一页要回答的问题

项目的核心产品理念是什么？

### 核心观点

系统不把所有失败都处理成空结果，而是将证据不足细分为机器可读状态：

- `Unverified`：值存在但不可信；
- `unmappable`：数据结构上无法用于判定；
- `no-source-data`：知识存在但患者数据不存在；
- `Provisional`：已命中阈值但确认条件不足；
- `Insufficient-Evidence`：不能分层，不等于低风险；
- `unsupported` / `not-adjudicable`：无证据与超出能力边界。

一句话：**不确定性不是免责声明里的小字，而是数据模型和 API 契约的一部分。**

### 为什么这一页必须存在

它是从 Problem 到 Solution 的转折页，也是全套故事的价值主张。后续技术页都应该被理解为实现这一原则的机制，而非技术堆砌。

### 与上一页的逻辑关系

上一页揭示“伪确定性”的风险；这一页给出项目应对风险的核心原则。

### 推荐表现形式

**Hero Statement + State Spectrum**。中央放一句大字“Unknown is a first-class result”，下方用从 `verified` 到 `not-adjudicable` 的状态光谱；不要做密集卡片墙。

---

## Slide 05

### 页面标题

**解决方案不是一个模型，而是一条可信证据链**

### 这一页要回答的问题

项目的总体想法是什么？

### 核心观点

系统由四个连续能力组成：

```text
可审计知识库构建
        → 标准化患者事实
        → 确定性语义推理
        → 可核查 API / 外部 Agent
```

模型只在离线知识抽取的受控环节出现；正式患者推理由版本化知识、规则和事实执行产生。

### 为什么这一页必须存在

观众在进入构建流水线和架构细节前，需要一张简单的心智地图，明确项目不是“LLM + GraphDB”的松散组合。

### 与上一页的逻辑关系

上一页定义了必须实现的原则；这一页给出承载原则的整体方案。

### 推荐表现形式

**Process Diagram**。四个阶段横向推进，每阶段只放一个动词和一个结果。把“LLM”画成知识构建阶段内的一个受限工具，而不是系统中心。

---

## Slide 06

### 页面标题

**本体不是手工成品，而是可持续构建的知识库工程制品**

### 这一页要回答的问题

糖尿病本体知识库是怎样搭建出来的？

### 核心观点

`ontology/tools/` 构成了一条完整知识库生产线：

```text
领域图模型 JSON ──build_tbox──> OWL TBox
TXT / PDF 指南 ──registry + extract──> sources / extract graphs
人工高危 seed ───────────────────────> thresholds / risk maps
                 ↓
       SHACL + passage verification
                 ↓
        GraphDB named graphs + rules
```

核心不是工具数量，而是知识库可以重建、版本化、装载、校验和追责。

代码证据：`ontology/tools/build_tbox.py`、`source_registry.py`、`semantic_extract.py`、`load_graphdb.py`、`validate_shacl.py`、`verify_passages.py`。

### 为什么这一页必须存在

这是项目的重要差异化亮点。如果只展示运行时推理，观众会追问“知识图从哪里来、怎么保证不是模型编的”。这一页正面回答来源问题。

### 与上一页的逻辑关系

上一页给出四阶段方案；这一页展开第一个、也是后续可信度的源头——知识库构建。

### 推荐表现形式

**Flow Diagram / Build Pipeline**。以“原料—加工—门禁—制品”的工业流水线视觉表达。可在每个产物旁标出文件类型：JSON、TXT/PDF、TTL、RQ、SHACL。避免展示 Python 文件列表。

---

## Slide 07

### 页面标题

**高风险知识不交给 LLM 猜，边界被写进构建流程**

### 这一页要回答的问题

知识抽取使用 LLM，如何避免它生成危险的临床规则？

### 核心观点

`semantic_extract.py` 使用 policy 将知识类型分流：

- `llm`：适合做 span-anchored 的实体与关系抽取；
- `manual`：诊断阈值、管理目标等高危数值由人工 seed 管理；
- `registry`：指南来源身份和文件哈希由程序机械生成；
- 确定性阶段：校验、对齐、发射、哈希和报告可以从 raw 输出重跑。

这意味着“不要幻觉”不是 prompt 提醒，而是模型根本拿不到某些高风险写入权限。

### 为什么这一页必须存在

它把“负责任使用 LLM”从抽象原则落到架构决策，也让非开发者理解为什么项目的知识库比“让模型读 PDF 后生成三元组”更可靠。

### 与上一页的逻辑关系

上一页展示知识库生产线；这一页聚焦生产线上最容易被质疑的环节——LLM 抽取的控制边界。

### 推荐表现形式

**Decision Flow**。一个知识类型进入分流器，走向 LLM、人工 seed 或机械 registry 三条路径。用红色禁止线强调 `DiagnosticThreshold → LLM` 不可达。

---

## Slide 08

### 页面标题

**知识与患者数据分开治理，在推理时才汇合**

### 这一页要回答的问题

系统整体架构如何让知识、患者事实和推断保持边界？

### 核心观点

- PostgreSQL 上游库只读，规范库负责 staging、映射、core facts 和结果投影；
- GraphDB 将 TBox、seed、sources、extract、patient 和 inferred 分成不同命名图；
- 每位患者拥有独立命名图，推断结论进入独立 inferred 图；
- FastAPI/CLI 统一提供查询、探索、推演、溯源和裁决；
- 外部 Agent 通过 `/agent/manifest` 和 skills 使用这些确定性能力。

边界的意义是能够区分：**上游记录了什么、知识库声明了什么、系统推导了什么。**

### 为什么这一页必须存在

这是唯一需要展示全局组件关系的架构页。它解释为什么系统可追溯、为何假设不会污染事实、以及为什么 PostgreSQL 与图数据库同时存在。

### 与上一页的逻辑关系

前两页解释知识如何被可靠构建；这一页把知识层与患者数据层接入同一个运行系统。

### 推荐表现形式

**Architecture Diagram**。采用上下双流汇合：上方知识构建流，下方患者事实流，中间在 GraphDB 推理层汇合，右侧输出 API/Agent。最多 8 个节点，避免画全部数据库表。

---

## Slide 09

### 页面标题

**一次回答，要穿过数据、语义、规则和来源四道关**

### 这一页要回答的问题

用户查询发生时，数据具体如何流动？

### 核心观点

以患者评估请求为例：

1. SQL 先确认患者并收敛候选集合；
2. GraphDB 查询患者命名图和语义结论；
3. SPARQL 规则检查单位、可信度、上下文、区间和确认要求；
4. 结果通过业务主键拼回 SQL 原始行；
5. 响应同时返回 asserted facts、inferred facts、sources、unmapped 和 data quality notice。

系统输出的不只是一句答案，而是一个带事实来源和失败原因的证据包。

### 为什么这一页必须存在

架构图说明“有哪些组件”，这一页说明“组件如何共同完成一次任务”，避免观众只看到静态盒子。

### 与上一页的逻辑关系

上一页是静态架构；这一页沿着一条实际请求把架构激活。

### 推荐表现形式

**Sequence / Flow Diagram**。用户请求从左到右依次经过 API、PostgreSQL、GraphDB/Rules、Provenance Assembler，最后形成分层响应。突出四次判定门，而非网络协议。

---

## Slide 10

### 页面标题

**A1C 7.4% 落入糖尿病区间，但单次异常仍不是确诊**

### 这一页要回答的问题

本体和规则真正改变了什么结论？

### 核心观点

P90002 的 A1C 7.4% 会命中 `[6.5, +∞)` 区间，但阈值带有 `confirmationRequired=true`，当前只有一个检测日期，因此系统输出 `Provisional`，而不是 `Confirmed`。

P90003 有两个不同日期的异常结果，才升级为 `Confirmed`。规则计算的是 `COUNT(DISTINCT day)`，同日重复检测不能冒充复测。

代码证据：`ontology/rules/20-lab-assessment.rq`、`30-diagnosis-from-assessment.rq`、`tests/test_scenarios.py`。

### 为什么这一页必须存在

这是最容易被观众理解、也最能证明“语义规则不是概念装饰”的案例：同一个阈值，因证据结构不同得出不同诊断状态。

### 与上一页的逻辑关系

上一页解释请求如何流动；这一页展示这条数据流产生的第一个关键业务差异。

### 推荐表现形式

**Before / After Comparison**。左侧“一天：7.4% → Provisional”，右侧“两天：7.1% + 7.3% → Confirmed”；中间突出 `distinct dates`，下方附一行规则证据，避免大段 SPARQL。

---

## Slide 11

### 页面标题

**单位不是展示字段，而是会让结论翻转的业务语义**

### 这一页要回答的问题

为什么标准化和单位治理值得单独展示？

### 核心观点

P90012 的空腹血糖为 7.8 mmol/L。通过经过核实的 analyte-specific 系数 `×18.0182`，规范值约为 140.54 mg/dL，并命中 FPG 糖尿病区间。

如果把 7.8 直接当作 mg/dL，结果会落入完全不同的区间。系统因此同时保留 source value/unit 和 normalized value/unit；缺单位或无核实换算时拒绝判定。

代码证据：`src/dmo/db/seed/unit_conversion.csv`、`src/dmo/terms/units.py`、`src/dmo/db/projection.py`、`tests/test_scenarios.py::test_s11_unit_conversion_changes_the_conclusion`。

### 为什么这一页必须存在

它让非开发者直观看到“数据治理”并非后台清洗工作，而是直接影响推理正确性的产品能力。

### 与上一页的逻辑关系

上一页证明时间结构会改变结论；这一页证明同一个数字的单位语义也会改变结论。

### 推荐表现形式

**Transformation Visualization**。用大数字表达 `7.8 mmol/L × 18.0182 = 140.54 mg/dL`，下面分叉为“正确换算 → DiabetesRange”和“错误直读 → Wrong conclusion”。

---

## Slide 12

### 页面标题

**系统不仅能回答“现在怎样”，还能安全回答“如果怎样”**

### 这一页要回答的问题

项目如何做条件推演，又如何避免把假设当事实？

### 核心观点

`POST /simulate` 对同一患者运行两轮相同规则：

```text
真实患者图 → before
真实患者图 + 显式假设事实 → after
delta = after - before
```

假设只能由调用方明确给出；系统不生成预测值。两轮使用独立内存 Dataset，假设事实标记为 `simulated/hypothetical`，GraphDB 不被写入。

### 为什么这一页必须存在

它把本体从静态查询提升为可解释的决策实验环境，同时守住“不预测、不污染、不冒充事实”的边界。

### 与上一页的逻辑关系

前两页展示当前事实如何被判断；这一页把同一套规则用于受控的未来条件实验。

### 推荐表现形式

**Before / After Flow**。一条真实事实流复制成上下两支，下支加入醒目的“Hypothesis”，最终汇合为 delta。不要把它画成时间序列预测图。

---

## Slide 13

### 页面标题

**同一假设可以复现，但“可复现”不等于“临床正确”**

### 这一页要回答的问题

如何证明推演是确定性的，同时避免过度宣传？

### 核心观点

`derivationHash` 覆盖：

- patient ID；
- graph version；
- knowledge snapshot hash；
- rules fingerprint；
- 规范化并排序后的 hypotheses。

相同输入和版本应得到相同哈希，不同规则或知识版本必须产生不同哈希。这个哈希证明的是“输入与执行版本可复现”，不是医学正确性、模型准确率或临床背书。

代码证据：`src/dmo/simulate/hashing.py::derivation_hash`、`tests/test_simulate.py::test_derivation_hash_is_stable`。

### 为什么这一页必须存在

它提供一个技术大会上有记忆点的确定性机制，也主动限定其含义，体现项目对可信声明的克制。

### 与上一页的逻辑关系

上一页解释推演流程；这一页回答“怎么证明两次推演是在同一条件下发生的”。

### 推荐表现形式

**Hash Composition Diagram / Code Evidence**。五个输入合成一个 64 位哈希；旁边仅放 6–8 行精简代码截图。底部用对照语句：“Reproducible ≠ Clinically validated”。

---

## Slide 14

### 页面标题

**每条结论都可以反向走回规则、原文和原始数据**

### 这一页要回答的问题

系统所说的“可解释、可追溯”具体意味着什么？

### 核心观点

`GET /graph/provenance` 能从 Assessment、Diagnosis、RiskFactorHit、ContraindicationFlag 或 RiskStratification 反向展开：

```text
Conclusion
  → Supporting Assessment / Fact
  → Applied Threshold / Rule
  → SourcePassage quote + SHA-256
  → patient RDF IRI
  → source_table + source_pk
  → SQL row
```

如果链条中断，响应通过 `brokenLinks` 明确报告，而不是只展示成功走通的部分。

### 为什么这一页必须存在

这是知识构建、本体推理和患者数据真正汇合的一页，也是项目相对普通 RAG 最具差异化的能力之一。

### 与上一页的逻辑关系

上一页证明推演过程可复现；这一页证明结论依据可核查。

### 推荐表现形式

**Knowledge Graph / Provenance Chain**。中心放一条 Diagnosis，向左回到 LabResult/SQL，向右回到 Threshold/SourcePassage。节点控制在 6–7 个，并给 quote/hash 节点独特视觉强调。

---

## Slide 15

### 页面标题

**可信不是口号：哪些能力已经被代码证明，哪些还没有**

### 这一页要回答的问题

当前项目的证据强度到底如何？

### 核心观点

已直接验证或有强代码证据：

- 31/31 条可信 `SourcePassage` 逐字命中本地语料且哈希一致；
- 19 个不依赖外部服务的 SPARQL guard 测试通过；
- 上游双 DSN、session read-only、schema guard 和内容基线已实现；
- 每患者命名图、整图 PUT、内容哈希和内存推演均有实现。

当前不能宣称：

- 全量测试通过：本次有 155 项因 PG/GraphDB 不可用而跳过；
- SHACL 全绿：本次发现 2 条新增违规；
- ontology agent 优于纯 LLM：仓库没有可执行 baseline 评测 harness；
- 已有内置 Agent：没有 ReAct loop、`src/dmo/agent/` 或 `dmo ask`。

### 为什么这一页必须存在

技术汇报最容易因演示效果而过度承诺。这一页用事实分层建立可信度，也提前化解评审者对“是否真正验证”的质疑。

### 与上一页的逻辑关系

上一页展示了最强能力；这一页给这些能力加上准确的证据等级和适用边界。

### 推荐表现形式

**Evidence Matrix**。左侧“Proven”，右侧“Not Yet Proven”，中间用清晰分界线。不要使用绿色全勾导致“项目已完成”的错觉；SHACL 新增违规应作为诚实的黄色警示。

---

## Slide 16

### 页面标题

**项目的价值，是把医疗 AI 的风险从“相信模型”转成“检查证据”**

### 这一页要回答的问题

这套系统对不同角色产生什么价值？

### 核心观点

- 对知识工程师：知识库可重建、可版本化，来源和抽取缺陷可定位；
- 对数据工程师：脏数据不会静默进入临床判定，未映射与不可信状态可运营；
- 对 Agent 开发者：通过稳定 API、manifest 和 skills 复用确定性推理能力；
- 对技术治理者：每个结论可以核查版本、规则、来源和原始数据边界。

真正的战略价值不是替代医生，而是为医疗 AI 增加一层 **可验证的语义控制面**。

### 为什么这一页必须存在

前面证明了技术成立，这一页把技术翻译成产品与组织价值，避免汇报停留在工程炫技。

### 与上一页的逻辑关系

上一页界定已证明的能力；这一页解释这些已证明能力为什么值得继续投入。

### 推荐表现形式

**Value Chain**。从“Knowledge Governance → Data Quality → Deterministic Reasoning → Agent Trust”横向展开，每阶段标一个受益角色。不要做四象限功能清单。

---

## Slide 17

### 页面标题

**下一阶段：从可信推理底座，走向可评测、可运营、可临床治理的系统**

### 这一页要回答的问题

项目下一步应该做什么，整场故事如何收束？

### 核心观点

建议按证据优先级推进三步：

1. **先补验证闭环**：修复 2 条新增 SHACL 违规，建立强制 PG/GraphDB 集成测试 job，避免“155 skipped 仍绿”。
2. **再补 Agent 与评测**：实现明确受控的 Agent loop 和真实 baseline harness，用同一测试集比较无工具 LLM、ontology-backed Agent，而不是引用静态 demo 百分比。
3. **最后补生产治理**：认证授权、患者级访问控制、审计、限流、可观测性、知识版本审批和人工复核流程。

收束句：

> 这不是一个已经完成的医疗 Agent，而是一套已经证明“如何让医疗 Agent 不轻易说错话”的工程底座。

### 为什么这一页必须存在

结尾必须回应开场提出的问题，并给出可信的下一步，而不是停在某个技术细节或泛泛的“未来可期”。

### 与上一页的逻辑关系

上一页说明继续投入的价值；这一页将价值转化为有优先级的实施路线，并回答开场问题。

### 推荐表现形式

**Roadmap + Closing Hero Statement**。三段式路线从“验证”到“Agent/评测”再到“生产治理”；右下角回扣 Slide 01 的 `Evidence Insufficient`，将其转化为系统成熟度的标志而非失败。

---

## Narrative in One Sentence

面对无法支撑可靠回答的真实医疗数据，这个项目先构建一套可重建、可审计的糖尿病本体知识库，再用确定性规则、证据溯源和显式未知状态，让外部 Agent 从“生成一个答案”升级为“给出一个可核查、知道边界的结论”。

## Three Things Audience Should Remember

1. **本体知识库不是一份静态 Turtle，而是一条对 schema、语料、LLM 抽取、高危规则和质量门禁进行分级治理的工程流水线。**
2. **系统最重要的差异化不是回答更多，而是把 `Unverified`、`Provisional`、`Insufficient-Evidence` 和溯源断链变成可执行、可测试的产品能力。**
3. **当前项目已经形成可信语义推理后端，但内置 Agent、真实 baseline 评测和生产临床治理仍属于下一阶段，不能用静态 Demo 代替证据。**
