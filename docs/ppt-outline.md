# **Slide 01 — 医疗 AI，也应该学会说“我还不能确定”**

### **Purpose**

让普通观众立即理解项目关注的核心问题：AI 不应在证据不足时给出看似肯定的医疗结论。

### **Key Message**

真正可信的医疗 AI，不是每次都回答，而是知道什么时候应该停下来。

### **Content**

**Diabetes Ontology Agent**

让系统回答三个问题：

- 我看到了什么？
- 我为什么这样判断？
- 还缺少什么证据？

**技术验证项目｜不构成医疗建议**

### **Visual**

Hero Statement。画面中央是一条通向“结论”的证据链；证据完整的一条顺利到达，证据缺失的一条停在“还不能确定”。不出现技术栈图标。

### **Repository Evidence**

- `README.md`：项目定位与“知道自己不知道”的主张。
- `src/dmo/query/hybrid.py::DISCLAIMER`：服务免责声明。
- `src/dmo/manifest.py::PROHIBITIONS`：禁止无依据结论、剂量建议等能力边界。

### **Speaker Notes**

先提出一个直观问题：如果一份检验没有单位、关键指标不存在，AI 还应该给出一个听起来很专业的答案吗？

这个项目的选择是“不”。它尝试让系统不仅能给结论，还能说明证据是否足够、判断依据是什么、缺口在哪里。糖尿病是验证场景，真正要展示的是一种更负责任的 AI 工作方式。

需要明确：这是技术验证与学习项目，不是医疗器械，也不替代医生。

---

# **Slide 02 — 医疗数据“有记录”，不代表“能判断”**

### **Purpose**

让观众理解医疗数据为什么不能直接交给 AI 得出结论。

### **Key Message**

一个数字只有在名称、单位、时间和来源都清楚时，才可能成为可靠证据。

### **Content**

常见的数据缺口：

**名称不清**　到底是哪一种检查？

**单位缺失**　7.8 是 mmol/L，还是 mg/dL？

**时间不足**　一次异常，还是多次复查？

**来源不明**　判断依据来自哪里？

> 有数据 ≠ 有证据

### **Visual**

一张“检验单”逐层被放大检查：名称、数字、单位、日期、来源五个位置。缺失项用留白或断点表示，不使用统计图。

### **Repository Evidence**

- `src/dmo/db/seed/lab_term_map.csv`：检验名称映射、可信状态、无来源数据状态。
- `src/dmo/db/projection.py`：生日、检验、单位与可信度的投影逻辑。
- `tests/test_scenarios.py::test_real_ehr_patients_are_all_insufficient_evidence`：真实 EHR 场景预期返回证据不足。
- `docs/PATIENT-GRAPH-FUSION-PLAN.md`：历史上游数据质量记录。

### **Speaker Notes**

普通人看到“7.8”容易以为这是一个明确事实，但系统还需要知道：它是什么检查、什么单位、什么时候测的、数据是否可信。

医疗判断依赖上下文。缺一个单位，数值可能差十几倍；只有一次异常，也不一定满足确认条件。这个项目把这些问题放在推理之前，而不是在答案生成后用免责声明补救。

---

# **Slide 03 — 最危险的不是系统报错，而是它自信地答错**

### **Purpose**

用一个具体案例说明“词语相似”和“答案流畅”为什么都不等于判断正确。

### **Key Message**

能认出一个医学名词，不代表已经理解它能否用于判断。

### **Content**

**输入：尿蛋白 10.4**

普通匹配：

“名字相似” → 同时连到两个互斥疾病

本项目：

“这是定性项目，单位也不适合数值比较”

→ **不参与判断**

真正需要的是：**尿白蛋白/肌酐比值（UACR，mg/g）**

### **Visual**

Before / After。左侧是一条输入被错误地分叉到两个疾病；右侧输入经过“检查类型”和“检查单位”两道门后被安全拦截，并提示需要的正确检查。

### **Repository Evidence**

- `src/dmo/db/seed/lab_term_map.csv`：尿蛋白被标记为 `qualitative`、`unmappable`。
- `ontology/src/dmo-threshold-seed.ttl`：尿蛋白不挂数值阈值；UACR 是不同检验。
- `src/dmo/terms/wfs.py::compare`：与字符串匹配方案的对照。
- `src/dmo/api.py::demo_compare`：`GET /demo/compare`。

### **Speaker Notes**

这里的重点不是批评大模型或字符串匹配。它们很适合找候选，但不应该直接承担医疗判定。

“尿蛋白”听起来与肾脏疾病有关，但仓库中的上游项目属于定性检查，参考范围是“阴性”。把 10.4 当作可直接比较的定量值，第一步就错了。

本项目的价值是：即使认识这个词，也会承认它目前不能用于数值判断。

---

# **Slide 04 — 我们的想法：给每个答案附上一张“证据收据”**

### **Purpose**

用非技术语言解释项目的总体解决方案。

### **Key Message**

系统不仅给出结果，还要同时交付依据、来源和缺失信息。

### **Content**

一张完整的“证据收据”包含：

1. **事实**：患者原始记录是什么
2. **规则**：系统用了哪条判断条件
3. **来源**：规则来自哪段资料
4. **状态**：确定、暂定，还是证据不足

> 结论可以被检查，而不是只能被相信。

### **Visual**

用收据或登机牌式的单一纵向视觉结构，依次列出事实、规则、来源、状态。避免做四张独立卡片。

### **Repository Evidence**

- `src/dmo/query/hybrid.py::patient_bundle`：整合患者事实与图谱结论。
- `src/dmo/graph/provenance.py::trace`：反向追踪证据链。
- `src/dmo/adjudicate/claim.py::adjudicate_claim`：支持、反驳、证据不足与不可裁决状态。
- `src/dmo/graph/guard.py::zero_result_reason`：解释为什么没有结果。

### **Speaker Notes**

把项目理解成一台“结论打印机”并不准确。更好的比喻是：它打印的是一张证据收据。

这张收据告诉我们，患者数据原本是什么、系统用了哪条规则、规则从哪里来，以及现在能得出多确定的结论。缺证据不是空白或报错，而是正式结果的一部分。

---

# **Slide 05 — 第一步，是先造一本机器能读懂的“医学规则书”**

### **Purpose**

让观众理解“本体知识库”是什么，以及为什么本体知识库搭建是项目亮点。

### **Key Message**

本体知识库把医学概念、关系、判断条件和出处整理成机器可以执行的规则书。

### **Content**

**原料**

医学概念模型 · 指南资料 · 人工确认的高风险阈值

↓

**加工**

整理概念 · 连接关系 · 标记出处

↓

**质检**

结构检查 · 引文核对 · 装载验证

↓

**成品**

可重建、可更新、可追踪的知识库

### **Visual**

“原料—加工—质检—成品”的知识工厂流水线。成品以一个简洁的节点关系图表示。主画面不出现 Python 脚本名称。

### **Repository Evidence**

- `ontology/graph/diabetes-ontology-v2.json`：领域概念模型输入。
- `ontology/tools/build_tbox.py::main`：将模型构建为 OWL 本体。
- `ontology/tools/source_registry.py`：来源文件登记与哈希。
- `ontology/tools/semantic_extract.py::main`：按 schema 抽取知识。
- `ontology/tools/validate_shacl.py::main`：结构与约束检查。
- `ontology/tools/verify_passages.py::main`：引文与 SHA-256 核对。
- `ontology/tools/load_graphdb.py::main`：知识装载、规则执行与验收。

### **Speaker Notes**

“本体”可以简单理解成一本机器能读懂的医学规则书。它不仅列出“血糖”“检查”“诊断”这些词，还说明它们之间是什么关系、判断需要什么条件、依据来自哪里。

这个仓库的重要亮点是：知识库不是一份手工维护的静态文件，而是有完整搭建工具。领域模型、指南资料和人工确认内容经过构建、检查和装载，最终成为可运行的知识库。这样才能持续更新，也能追查某条知识是怎样进入系统的。

---

# **Slide 06 — 大模型可以帮忙整理资料，但不能擅自写诊断标准**

### **Purpose**

让观众理解项目如何使用大模型，同时控制高风险知识。

### **Key Message**

不同知识采用不同录入方式，风险越高，人工控制越严格。

### **Content**

**大模型协助**

从原文中寻找概念、关系和候选内容

**人工确认**

诊断阈值、管理目标等高风险知识

**程序自动完成**

来源登记、文件指纹、格式检查和报告

> 大模型是助手，不是规则制定者。

### **Visual**

三路分流图。知识进入后分别流向“大模型协助”“人工确认”“程序自动完成”，再统一经过质量检查。诊断阈值通往大模型的路径用明确的禁止符号拦截。

### **Repository Evidence**

- `ontology/tools/semantic_extract.py`：`POLICY_LLM`、`POLICY_MANUAL`、`POLICY_REGISTRY`、`POLICY_DERIVED`。
- `ontology/tools/semantic_extract.py::SchemaGraph.extractable`：只允许指定类型由模型抽取。
- `ontology/tools/README.md`：知识类型分级策略。
- `ontology/src/dmo-threshold-seed.ttl`：人工维护的诊断阈值。
- `ontology/tools/source_registry.py`：不经过模型的来源登记。

### **Speaker Notes**

很多人会担心：如果知识库由大模型参与构建，会不会把模型的幻觉写进规则？这个项目的处理方式不是简单地提示模型“小心”，而是先划定权限。

模型可以帮助从原文中找候选概念和关系，但诊断阈值、管理目标等高风险知识被指定为人工维护。文件身份和指纹由程序生成，也不让模型猜。风险边界因此进入了构建流程本身。

---

# **Slide 07 — 系统把“医学规则”和“患者记录”分开保管**

### **Purpose**

用直观方式解释系统架构，而不要求观众理解数据库技术。

### **Key Message**

规则、患者原始记录和系统推导结果分开保存，才能看清每个结论从哪里来。

### **Content**

**医学规则库**

概念 · 条件 · 来源

　　　　　　↘

　　　　　　 **判断引擎** → 证据收据

　　　　　　↗

**患者事实库**

检查 · 日期 · 单位 · 原始编号

> 原始记录与推导结论，不混在一起。

### **Visual**

极简三层架构图。左上“医学规则库”、左下“患者事实库”，在中间“判断引擎”汇合，右侧输出“证据收据”。页脚以小字标注 PostgreSQL、GraphDB、FastAPI，不放在主视觉中。

### **Repository Evidence**

- `src/dmo/config.py::Config`：关系数据库与图数据库配置。
- `src/dmo/db/ddl/*.sql`：患者事实分层表。
- `src/dmo/rdf/emit.py::build`：把规范患者事实转换为图数据。
- `src/dmo/rdf/sync.py::run`：按患者同步独立命名图。
- `ontology/tools/load_graphdb.py::collect`：知识图分层装载。
- `src/dmo/api.py`：服务访问层。

### **Speaker Notes**

这一页只解释职责，不讲技术细节。

一边是医学规则书，保存概念、判断条件和来源；另一边是患者事实，保存检查结果、日期、单位和原始记录编号。二者只有在判断时才相遇。系统生成的结论又单独保存。

这种分开保管的方式，让我们能区分三件事：医院原本记录了什么、知识库写了什么、系统后来推导出了什么。

---

# **Slide 08 — 一次回答，要先通过四道检查**

### **Purpose**

让观众看懂一次请求从输入到输出的完整过程。

### **Key Message**

系统不会直接生成答案，而是依次检查事实、含义、规则和来源。

### **Content**

**1 找到事实**

确认患者和原始记录

**2 看懂含义**

检查项目、单位、日期和可信度

**3 执行规则**

判断区间、适用人群和复查条件

**4 打包证据**

返回结论、依据、出处和缺口

### **Visual**

四道安检门式横向流程。每一道门只保留一个动词和一个问题，最后输出一张“证据收据”。

### **Repository Evidence**

- `src/dmo/api.py::_bundle/full/assessment/risk/safety`：患者请求入口。
- `src/dmo/query/hybrid.py::find_patients/patient_bundle`：关系数据与图数据的联合编排。
- `src/dmo/query/templates.py`：参数化图查询模板。
- `ontology/rules/*.rq`：确定性判断规则。
- `src/dmo/graph/provenance.py::_sql_rows`：从结论回查原始数据行。

### **Speaker Notes**

可以把整个请求想象成通过四道安检。

第一道确认找对了人和记录；第二道确认这条数据到底是什么意思、能不能比较；第三道执行明确规则；第四道把结果和证据一起打包。

这与让大模型看一段患者资料后自由生成回答有本质区别：每一步都有明确职责，也有可以停止的条件。

---

# **Slide 09 — 一次异常，只能说明“需要继续确认”**

### **Purpose**

用 A1C 案例证明系统会区分“达到某个范围”和“已经确认”。

### **Key Message**

同样超过阈值，一次检查和两次不同日期的检查，会得到不同状态。

### **Content**

**患者 A**

A1C 7.4% · 只有一个检测日期

→ 达到糖尿病范围

→ **暂定，需要确认**

**患者 B**

A1C 7.1% + 7.3% · 两个不同日期

→ **满足确认条件**

### **Visual**

左右时间线对比。左侧只有一个日期点，停在“暂定”；右侧有两个不同日期点，连接到“确认”。阈值作为共同底线。

### **Repository Evidence**

- `ontology/src/dmo-threshold-seed.ttl`：A1C 阈值与 `confirmationRequired true`。
- `ontology/rules/20-lab-assessment.rq`：检验结果与阈值形成区间判断。
- `ontology/rules/30-diagnosis-from-assessment.rq`：按不同检测日期数量区分暂定与确认。
- `src/dmo/db/seed/cohort_patient.csv`、`cohort_lab_result.csv`：P90002、P90003 示例数据。
- `tests/test_scenarios.py::test_s02_single_abnormal_is_provisional_not_confirmed`。
- `tests/test_scenarios.py::test_s03_two_distinct_days_confirms`。

### **Speaker Notes**

先区分两句话：“这次 A1C 落入糖尿病范围”和“这个人已经满足系统建模的确认条件”。它们不是同一句话。

第一位患者只有一个检测日期，系统给出“暂定”；第二位患者有两个不同日期的异常结果，才升级状态。同一天重复两次也不算，因为规则看的是不同日期。

这是一个规则行为演示，不是对真实患者的诊断建议。完整集成测试需要 PostgreSQL 与 GraphDB 环境；正式现场演示前应重新执行。

`Evidence Needed`：目标演示环境重新运行 P90002/P90003 集成测试。

---

# **Slide 10 — 同一个数字，单位不同，意思可能完全不同**

### **Purpose**

用人人都能理解的单位换算案例说明语义检查的必要性。

### **Key Message**

单位不是数字旁边的小字，而是决定数字能否用于判断的关键信息。

### **Content**

**原始记录**

空腹血糖 = 7.8 mmol/L

**经过核实的换算**

7.8 × 18.0182

**用于比较的数值**

140.54 mg/dL

> 没有单位，或没有可靠换算：停止判断。

### **Visual**

以“7.8 → 140.54”为画面焦点，中间显示单位和换算桥梁。下方用断裂路径展示“7.8，单位缺失 → 无法比较”。

### **Repository Evidence**

- `src/dmo/db/seed/unit_conversion.csv`：葡萄糖单位换算系数 18.0182。
- `src/dmo/terms/units.py::convert`：换算与拒绝逻辑。
- `src/dmo/db/projection.py::_conversion`：规范化投影。
- `src/dmo/rdf/emit.py::build`：同时保留原始值和规范值。
- `tests/test_scenarios.py::test_s11_unit_conversion_changes_the_conclusion`。
- `tests/test_simulate.py::test_verified_conversion_keeps_source_value`。

### **Speaker Notes**

这一页可以类比温度：30 摄氏度和 30 华氏度显然不是同一回事。血糖单位也是如此。

系统只使用经过核实的换算关系，而且同时保留原始值和换算后的值。这样既能正确比较，也能回头检查换算是否合理。没有单位或没有可靠换算时，系统宁可停止，也不猜测。

---

# **Slide 11 — “如果再补一条记录，会发生什么？”可以在沙盒里试**

### **Purpose**

让观众理解条件推演能力，以及它与预测的区别。

### **Key Message**

系统可以计算一个明确假设会怎样改变结论，但不会预测未来，也不会改动真实数据。

### **Content**

**现在**

读取真实患者事实和当前规则

**假设**

调用方明确提供数值、单位和日期

**沙盒重算**

比较结论增加了什么、减少了什么

**真实记录**

保持不变

> 条件推演 ≠ 未来预测

### **Visual**

透明沙盒视觉。真实患者记录在沙盒外保持锁定；沙盒内放入一张黄色“假设记录”，重算后输出 Before / After 差异。

### **Repository Evidence**

- `src/dmo/api.py::_simulate/simulate_body/simulate_patient`：推演接口。
- `src/dmo/simulate/runner.py::simulate`：两轮规则计算。
- `src/dmo/simulate/sandbox.py`：内存沙盒与知识快照。
- `src/dmo/simulate/hypothesis.py::parse/to_graph`：假设输入校验。
- `src/dmo/simulate/engine.py::diff`：结论差异计算。
- `tests/test_simulate.py::test_simulation_never_writes_to_graphdb`。

### **Speaker Notes**

例如，我们可以问：“如果患者在另一个日期补充了一条 A1C 记录，系统状态会怎样变化？”假设内容必须由调用方明确给出，系统不会自己编造未来数值。

推演发生在内存沙盒中，比较前后结论差异，不写回真实图数据库。因此它更像电子表格里的“假设分析”，而不是预测患者未来。

完整的零写入集成验证仍需要目标数据库环境。

`Evidence Needed`：在完整环境执行推演前后 GraphDB 不变的集成测试。

---

# **Slide 12 — 任何结论，都能沿着证据链走回原点**

### **Purpose**

让观众具体理解“可追溯”意味着什么。

### **Key Message**

系统可以从结论回到患者原始记录，也可以回到规则所引用的原文。

### **Content**

**结论**

↓ 用了哪条规则？

**判断条件**

↓ 来自哪段资料？

**原文与文件指纹**

↓ 患者事实来自哪里？

**原始表与记录编号**

**31 / 31 条可信引文已通过逐字核对**

### **Visual**

Knowledge Graph 式证据链。中心为结论，左边连接患者检查和原始记录，右边连接规则、原文和文件指纹。断链用醒目的缺口显示“链路不完整”。

### **Repository Evidence**

- `src/dmo/api.py::graph_provenance`：`GET /graph/provenance`。
- `src/dmo/graph/provenance.py::trace`：规则、证据、SQL 行与断链追踪。
- `src/dmo/graph/passages.py::PassageIndex`：可信出处索引。
- `ontology/src/dmo-threshold-seed.ttl`、`ontology/src/dmo-risk-map.ttl`：引文与内容哈希。
- `ontology/tools/verify_passages.py::main`：逐字原文和 SHA-256 核对。
- 本地验证记录：31 条 SourcePassage，31 条逐字命中且哈希一致。

### **Speaker Notes**

“可解释”不只是让模型写一段听起来合理的说明。这里的证据链是机器可查询的。

向左可以追到患者的原始数据表和记录编号；向右可以追到判断规则、引用原文和文件指纹。如果某一环断了，系统也会报告断链，而不是只展示成功部分。

31/31 是本地实际运行引文核对工具的结果。它证明当前被标记为可信的 31 条引文可以逐字回到本地语料，但不代表整个医学知识库已经完成临床验证。

---

# **Slide 13 — 已经证明的能力，与尚未证明的能力，要分开说**

### **Purpose**

以透明方式说明当前项目的完成度和证据边界。

### **Key Message**

项目已经证明了知识构建、规则控制和证据追踪机制，但还不是可直接投入临床的完整产品。

### **Content**

**已经有直接证据**

- 知识库可以构建、装载和检查
- 31 / 31 条可信引文通过核对
- 19 个基础规则保护测试通过
- 患者事实、推导结果和假设数据分开处理

**仍需补足证据**

- 完整数据库集成测试尚未在本次环境运行
- 结构检查仍有 2 条新增问题
- 没有真实效果对比和临床验证
- 没有成品对话式 AI 助手

### **Visual**

一条清晰的“已证明 / 尚待证明”分界线。左侧采用稳定蓝色，右侧采用中性黄色。避免红色叉号和密集表格。

### **Repository Evidence**

- 本地测试记录：`19 passed, 155 skipped`。
- `tests/test_guard.py`：19 个无需外部服务的规则保护测试。
- `ontology/tools/verify_passages.py`：31/31 引文核对通过。
- `ontology/tools/validate_shacl.py`：10 条已知基线违规之外还有 2 条新增违规。
- `ontology/shapes/known-violations.tsv`：已知违规清单。
- `src/dmo/agent/`：仓库中不存在。
- `src/dmo/cli.py::build_parser`：没有对话式 `ask` 命令。
- `demo/index.html`：百分比为静态展示，不能作为评测结果。

### **Speaker Notes**

这一页是建立信任的重要部分。

可以直接证明的是：知识库工具链已经存在；31 条可信引文全部通过逐字核对；19 个基础保护测试通过；代码实现了事实、推断和假设的隔离。

不能夸大的部分也要清楚说：155 个依赖 PostgreSQL 或 GraphDB 的测试在本次环境被跳过；SHACL 检查仍有 2 条新增问题；仓库没有真实模型对比、临床效果数据和成品对话 Agent。

静态演示页面里的百分比没有评测程序支持，不应放进正式汇报。

---

# **Slide 14 — 它的价值，是把“相信 AI”变成“检查证据”**

### **Purpose**

把技术能力翻译为普通观众可以理解的实际价值。

### **Key Message**

项目为未来的医疗 AI 增加了一层可检查的安全与证据基础。

### **Content**

**对医生和审核者**

看得见依据，也看得见缺口

**对知识维护者**

知道规则来自哪里、何时变化

**对系统开发者**

可以调用明确能力，不必让模型自由猜测

**对治理者**

能够检查版本、边界和责任链

> 少一点无依据的生成，多一点可核查的证据。

### **Visual**

以“证据层”为中央桥梁，连接医生/审核者、知识维护者、系统开发者和治理者。不要使用四张 UI 卡片；用四个人群围绕一条共同证据链。

### **Repository Evidence**

- `ontology/tools/`：知识构建、来源登记与质量门禁。
- `src/dmo/db/seed/*.csv`、`src/dmo/terms/resolve.py`：数据映射与质量治理。
- `ontology/rules/*.rq`、`ontology/shapes/*.ttl`：可执行规则与约束。
- `src/dmo/manifest.py::build`：生成机器可读的能力清单。
- `src/dmo/manifest.py::ORDER/PROHIBITIONS/DETERMINISM`：调用顺序、禁令与确定性说明。
- `src/dmo/adjudicate/scope.py::describe_scope`：系统可裁决范围。

### **Speaker Notes**

这个项目不应该被介绍成“替代医生的糖尿病 AI”。更准确的定位是：它给未来的医疗 AI 增加一层证据和规则基础。

医生和审核者能看到依据与缺口；知识维护者能追踪规则来源；开发者可以调用明确的能力；治理者可以检查版本和边界。

因此项目最重要的价值不是让 AI 说得更多，而是让人能够检查它为什么这样说。

---

# **Slide 15 — 下一步：先把证据闭环补完整，再让系统更智能**

### **Purpose**

给出诚实、有优先级的后续路线，并回扣开场问题。

### **Key Message**

项目下一阶段应先完成验证与治理，再建设对话 Agent 和真实效果评测。

### **Content**

**现在：补齐验证**

修复 2 条结构问题 · 跑通全部集成测试

**下一步：接入受控 AI 助手**

让 AI 助手只能在明确能力和证据边界内工作

**再下一步：真实评测与生产治理**

统一测试集 · 权限 · 审计 · 人工复核

> 先知道边界，再扩大能力。

### **Visual**

三阶段单向路线图。第一阶段“证据闭环”视觉权重最高，第二阶段为受控 Agent，第三阶段为评测与生产治理。结尾回到开场的“还不能确定”，把它转化为一种负责任的系统能力。

### **Repository Evidence**

- `ontology/tools/validate_shacl.py`：当前有 2 条新增结构违规待修复。
- `tests/conftest.py`：外部服务不可用时集成测试会跳过。
- `docs/AGENT-INVESTIGATE-PLAN.md`：Agent 调查能力属于设计计划，尚未实现。
- `docs/DESIGN.md`：评测设计存在，但仓库未找到可执行评测器。
- `compose.yml`、`deploy/nginx.conf.example`：当前仅有基础部署配置。
- 仓库中未找到认证、RBAC、完整审计、限流或完整可观测性实现。

### **Speaker Notes**

路线图的顺序很重要。第一步不是接入更强的模型，而是修复当前结构问题，让 PostgreSQL 和 GraphDB 集成测试在目标环境完整运行，并避免“大量测试跳过但结果仍显示绿色”。

第二步才是受控 Agent。它应通过系统提供的能力清单和证据接口工作，而不是自由拼接医疗结论。

第三步是统一测试集上的真实评测，以及权限、审计、人工复核等生产治理。

最后回扣开场：这个项目还不是完整医疗产品，但它已经展示了一条重要方向——先让 AI 学会尊重证据边界，再扩大它的能力。

---

## **Narrative in One Sentence**

面对不完整、容易被误读的医疗数据，这个项目先建立一本机器能读懂、来源可查的医学规则书，再让每个结论都附带事实、规则、来源和缺口，把“相信 AI”变成“检查证据”。

## **Three Things Audience Should Remember**

1. **医疗数据有数字，不代表已经具备判断条件；名称、单位、日期和来源都很重要。**
2. **项目的核心亮点是可持续搭建的本体知识库，以及每个结论都能回到原始证据。**
3. **系统最有价值的能力不是回答所有问题，而是在证据不足时明确说“还不能确定”。**
