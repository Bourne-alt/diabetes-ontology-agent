# **PPT Visual Plan**

## **Overall Visual Direction**

### **Communication Job**

让技术大会、架构评审和产品治理受众理解：这个项目的核心价值不是“让模型生成更多医疗答案”，而是通过可构建本体、确定性规则和证据链，为外部 Agent 提供一个可检查边界的语义控制面。

### **Visual Language**

- 主视觉隐喻：**证据链、门禁、分层、断点、指纹**。
- 主色：深蓝黑用于事实和基础设施；青绿色用于已验证能力；琥珀色用于 provisional、unknown 与 Evidence Needed；红色只用于禁止路径或真实失败。
- 线条语义：实线表示确定性数据流；虚线表示假设或未来能力；断线表示证据不足；双线边框表示命名图或隔离沙箱。
- 节点语义：圆角矩形表示系统/处理步骤；圆形表示事实或概念；六边形表示规则；文档形表示来源；指纹形表示哈希。
- 页面原则：每页只保留一个主视觉，不采用仪表盘式卡片墙，不使用医疗图库、医生照片、AI 大脑、发光芯片等无证据装饰。
- 字体层级：标题不小于 35 pt；关键数字 44–64 pt；节点标签 18–22 pt；图中说明不小于 16 pt。

---

# **Slide 01 — 当医疗数据不足以回答时，系统能否诚实地停下来？**

### **Primary Visual Type**

**Typography + Diagram**

### **Composition**

左侧约 55% 放 Hero Statement；右侧约 45% 放一条极简证据链。页面不使用产品截图，不展示技术栈。

### **Nodes**

- `Patient Fact`
- `Semantic Check`
- `Rule`
- `Conclusion`
- `Evidence Insufficient`

### **Relationships**

- 完整事实经过语义检查与规则，到达结论。
- 缺单位或缺出处的事实，在语义检查处转入 `Evidence Insufficient`。

### **Direction**

从左上向右下，形成一条成功链和一条中断链。

### **Hierarchy**

1. 最大层级：`知道什么时候不能回答`
2. 第二层级：完整链与中断链的差异
3. 最低层级：`Technical Validation · Not a Medical Device`

### **Highlight**

突出中断点，而不是最终 Conclusion。`Evidence Insufficient` 使用琥珀色，成为开场的视觉记忆点。

### **Production Notes**

- 使用 PowerPoint 原生形状即可，连接线先于节点绘制。
- 不需要外部图片。
- 中断链可用一小段缺口表达，不使用红色错误叉号。

---

# **Slide 02 — 真实世界的数据，首先暴露的不是答案，而是缺口**

### **Primary Visual Type**

**Chart + Typography**

### **Chart Design**

采用“患者母体 + 数据缺口”图，不使用普通柱状图，因为 400、15、1,600、329 的统计口径不同。

### **Nodes**

- 主体圆：`400 patients`
- 小型筛选圈：`15 coded E11`
- 缺口 1：`0 usable HbA1c`
- 缺口 2：`1,600 labs · unit/value issues`
- 缺口 3：`329 future birthdays`

### **Relationships**

- 所有缺口都从 400 名患者的历史数据审查中暴露。
- 不把这些数字画成互斥分组或可相加的组成部分。

### **Direction**

中心向外辐射；视觉阅读顺序从 `400` 到 `0 usable HbA1c`，再到其他缺口。

### **Hierarchy**

1. `0 usable HbA1c` 为最大数字
2. `400 patients` 为上下文
3. 其余两项作为支持证据
4. 页脚显示 `Historical observation · Evidence Needed`

### **Highlight**

重点不是患者数量，而是“有记录不等于有可用于推理的证据”。

### **Data Integrity Notes**

- 每个数字必须带独立口径标签，不画统一坐标轴。
- 必须保留 `Evidence Needed`，并注明公开汇报前需重新连接原始数据库复核。
- 不将历史观察描述为当前实时环境结果。

---

# **Slide 03 — 最危险的错误，是给出一个看起来合理的答案**

### **Primary Visual Type**

**Comparison + Flowchart**

### **Nodes**

左侧“普通字符串匹配”：

- `尿蛋白 10.4`
- `Disease A · confidence 0.9`
- `Disease B · confidence 0.9`

右侧“本项目”：

- `尿蛋白 10.4`
- `Test type? qualitative`
- `Valid unit? no`
- `Applicable threshold? no`
- `unmappable`
- `Required concept: UACR (mg/g)`

### **Relationships**

- 左侧输入直接连接到两个互斥结果，显示错误确定性。
- 右侧输入依次经过项目类型、单位和阈值三道检查；任一不成立便停止数值判定。
- `unmappable` 再指向“真正需要的数据”，而不是指向疾病。

### **Direction**

左右并列；两侧内部均为自上而下。

### **Hierarchy**

1. 左右两种处理方式
2. 右侧三道门禁
3. 最终差异：`0.9 / 0.9` 对 `unmappable`

### **Highlight**

突出 `Recognized ≠ Adjudicable`。右侧的“停下来”应比左侧错误结果更醒目。

### **Production Notes**

- 左侧错误连线使用低饱和红；右侧门禁使用青绿，停止状态使用琥珀。
- 不展示既有系统品牌或虚构产品 UI。

---

# **Slide 04 — 我们先把“不知道”变成系统能力**

### **Primary Visual Type**

**Flowchart + Typography**

### **Nodes**

- `Fact Availability`
  - `Unverified`
  - `unmappable`
  - `no-source-data`
- `Evidence Closure`
  - `Provisional`
  - `Insufficient-Evidence`
- `Capability Boundary`
  - `unsupported`
  - `not-adjudicable`
- `Trace Integrity`
  - `emptyReason`
  - `brokenLinks`
- 终点：`Answerable with Evidence`

### **Relationships**

每一层是一次不同的资格检查；未通过时输出明确状态，通过时进入下一层。

### **Direction**

从上到下的收敛漏斗；停止状态从漏斗侧面分流。

### **Hierarchy**

1. 四级检查流程
2. 每级最有代表性的状态
3. 页尾主张：`Unknown is a first-class result.`

### **Highlight**

不要把九个状态做成九张同权卡片。突出它们属于不同层次，回答不同问题。

### **Production Notes**

- 正常路径用实线；停止输出用短横向箭头。
- 每层最多显示两个主状态，其他状态可作为小号补充标签。

---

# **Slide 05 — 解决方案不是一个模型，而是一条可信证据链**

### **Primary Visual Type**

**Flowchart**

### **Nodes**

- `01 Build` → `Auditable Knowledge`
- `02 Ground` → `Normalized Patient Facts`
- `03 Reason` → `Deterministic Conclusions`
- `04 Verify` → `Evidence Package`
- 受限支路：`LLM Extraction`

### **Relationships**

- 四阶段首尾相连。
- `LLM Extraction` 只进入 Build 阶段，不连接 Patient Facts、Reason 或最终 Conclusion。

### **Direction**

从左到右，单一路径；LLM 从 Build 下方垂直汇入。

### **Hierarchy**

1. 四个动词是主标签
2. 四个产物是次标签
3. LLM policy 是局部说明

### **Highlight**

最醒目的不是 LLM，而是完整的 `Build → Ground → Reason → Verify` 证据链。

### **Production Notes**

- 使用四个大号序号形成节奏。
- LLM 节点面积不超过任一主阶段的 40%，避免被误解为总控大脑。
- 图中不出现目录名或脚本名。

---

# **Slide 06 — 本体不是手工成品，而是可持续构建的知识库工程制品**

### **Primary Visual Type**

**Flowchart + Architecture**

### **Nodes**

输入：

- `Domain Schema · JSON`
- `Guidelines · TXT/PDF`
- `Manual High-risk Seed`

处理：

- `TBox Compiler`
- `Source Registry + SHA-256`
- `Schema-guided Extraction`
- `Deterministic Alignment`

质量门禁：

- `SHACL Validation`
- `Passage Verification`
- `GraphDB Acceptance Queries`

产物：

- `Named Graphs`
- `Executable Rules`
- `Build Report`

### **Relationships**

- JSON 只进入 TBox Compiler。
- TXT/PDF 同时进入 Source Registry 和抽取流程。
- Manual Seed 绕过 LLM，但仍经过全部确定性门禁。
- 所有分支在装载计划处汇合，再依次通过三个质量门禁。

### **Direction**

从左到右：原料 → 构建 → 门禁 → 运行时知识库。

### **Hierarchy**

1. 三类原料
2. 可重建处理链
3. 三道门禁
4. GraphDB 运行时产物

### **Highlight**

用加粗外框突出“质量门禁”，说明本体价值不仅是生成 Turtle，而是能够阻止不合格知识进入运行时。

### **Production Notes**

- 这是全稿最重要的工程流水线图之一，优先使用原生形状；若连线过多则使用 Graphviz 生成 SVG。
- Source Registry 节点附一个小型指纹符号，SHACL 和 Passage Verification 使用不同门禁图形。
- 可在图下角标注当前状态：`Passages 31/31 · SHACL has 2 new violations`，不要写成全绿流水线。

---

# **Slide 07 — 高风险知识不交给 LLM 猜**

### **Primary Visual Type**

**Flowchart + Comparison**

### **Nodes**

- `Knowledge Type`
- `LLM Policy`
  - entities
  - relations
  - quote-anchored candidates
- `Manual Policy`
  - DiagnosticThreshold
  - GlycemicTarget
- `Registry Policy`
  - source identity
  - file hash
- `Derived Policy`
- `Deterministic Validation`
- `Runtime Knowledge`

### **Relationships**

- Knowledge Type 依据 policy 分流到四条路径。
- 所有允许产物最终进入确定性校验。
- `DiagnosticThreshold → LLM` 画一条被明确阻断的虚线。

### **Direction**

从上到下分流，再从下方汇合。

### **Hierarchy**

1. Policy 分流
2. 高风险概念归入 Manual
3. 共同的确定性校验

### **Highlight**

红色禁止路径 `DiagnosticThreshold ✕ LLM` 是本页唯一强色；其余保持中性。

### **Code Option**

图右下角可放 5 行真实代码，不超过主画面的 20%：

```python
POLICY_LLM, POLICY_MANUAL, POLICY_REGISTRY, POLICY_DERIVED = (
    "llm", "manual", "registry", "derived"
)

def extractable(self) -> list[str]:
    return [eid for eid in self.entities if self.policy(eid) == POLICY_LLM]
```

代码来源：`ontology/tools/semantic_extract.py`。正式制作时应截取源码并保留文件名，不重新排成伪代码。

---

# **Slide 08 — 知识与患者数据分开治理，在推理时才汇合**

### **Primary Visual Type**

**Architecture**

### **Nodes**

知识平面：

- `JSON Schema / Guidelines / Manual Seed`
- `Ontology Build Tools`
- `Knowledge Named Graphs`

患者平面：

- `Read-only Upstream PG`
- `Staging / Mapping / Core`
- `urn:dmo:patient:{pid}`

推理平面：

- `GraphDB Dataset`
- `OWL-RL`
- `SPARQL Rules`
- `urn:dmo:inferred`
- `SHACL`

访问平面：

- `FastAPI`
- `CLI`
- `External Agent`

隔离平面：

- `In-memory Simulation Dataset`

### **Relationships**

- 知识平面将版本化命名图装载到 GraphDB。
- 患者平面将 core facts 发射到每患者命名图。
- GraphDB 规则读取知识图与患者图，写入 inferred 图。
- FastAPI/CLI 查询事实、推断与 provenance。
- Simulation 只读取知识和患者快照，在内存中推理，不写回 GraphDB。

### **Direction**

知识流从左上进入中部 GraphDB；患者流从左下进入中部 GraphDB；结果向右进入访问层；模拟沙箱位于 GraphDB 下方，以虚线只读箭头取得快照。

### **Hierarchy**

1. 中心：GraphDB Dataset 及三类命名图
2. 左侧：知识流与患者流
3. 右侧：访问层
4. 下方：隔离模拟沙箱

### **Highlight**

在中心用明显分区表现 `Asserted Patient Facts` 与 `Inferred Conclusions` 不在同一图中。

### **Production Notes**

- 使用架构图，不画云厂商或容器部署拓扑。
- PostgreSQL 与 GraphDB 用标准数据库符号；命名图以嵌套画布表达。
- External Agent 使用虚线边框，说明它是调用方而非仓库内置实现。

---

# **Slide 09 — 一次回答，要穿过数据、语义、规则和来源四道关**

### **Primary Visual Type**

**Flowchart / Sequence Diagram**

### **Nodes**

参与者：

- `Caller`
- `FastAPI`
- `PostgreSQL`
- `GraphDB + Rules`
- `Evidence Assembler`

消息：

- `patient request`
- `find patient / source rows`
- `query patient graph`
- `interpret term + unit + trust`
- `run/read assessments`
- `trace rules + passages`
- `assemble response`
- `asserted / inferred / sources / gaps`

### **Relationships**

- API 先向 PostgreSQL 收敛患者与原始事实。
- API 再向 GraphDB 读取语义事实和规则结果。
- Evidence Assembler 将两侧结果按确定性 IRI 和 source PK 对齐。
- 最终返回四部分证据包。

### **Direction**

参与者从左到右；时间从上到下。

### **Hierarchy**

1. 四个动词：Find、Interpret、Reason、Prove
2. 数据库交互
3. 最终响应四层结构

### **Highlight**

突出最后的 `Response Envelope`，表明输出不是单一答案字符串。

### **Production Notes**

- 控制在 7–9 条消息，不展示完整函数调用栈。
- `Interpret` 和 `Reason` 可以在 GraphDB 泳道内用两个阶段标签表示。
- 不展示完整 JSON；只显示四个顶层字段。

---

# **Slide 10 — A1C 7.4% 落入糖尿病区间，但单次异常仍不是确诊**

### **Primary Visual Type**

**Comparison + Timeline**

### **Nodes**

共同规则底座：

- `A1C threshold ≥ 6.5%`
- `confirmationRequired = true`

左侧 P90002：

- `Day 1 · A1C 7.4%`
- `Assessment: DiabetesRange`
- `Diagnosis: Provisional`

右侧 P90003：

- `Day 1 · A1C 7.1%`
- `Day 2 · A1C 7.3%`
- `2 distinct dates`
- `Diagnosis: Confirmed`

### **Relationships**

- 每个 A1C 结果先与阈值形成 Assessment。
- Diagnosis 状态取决于不同检测日期数量，而不是结果条数。

### **Direction**

左右对照；每侧自上而下。右侧两点沿水平时间线排列。

### **Hierarchy**

1. Provisional 与 Confirmed 的对比
2. 不同日期数量
3. 共同阈值规则

### **Highlight**

在左右之间放大显示：`COUNT(DISTINCT day): 1 → 2`。

### **Screenshot Plan**

- 目标截图：完整环境下调用 `/patients/P90002/assessment` 与 `/patients/P90003/assessment` 的响应，或 Swagger/OpenAPI 中这两个请求的 Response body。
- 截图重点：患者 ID、A1C Assessment、Diagnosis status、distinct date evidence。
- 裁剪：只保留响应中的 assessment、diagnosis、evidence 字段，移除浏览器 chrome、无关 JSON 和请求头。
- Annotation：用两处框线分别标 `Provisional`、`Confirmed`；用箭头标出不同日期。
- 当前状态：`MANUAL / Evidence Needed`，必须在 PostgreSQL + GraphDB 完整环境重新执行后取得，不能使用静态 Demo 页面替代。

---

# **Slide 11 — 单位不是展示字段，而是会让结论翻转的业务语义**

### **Primary Visual Type**

**Typography + Flowchart + Comparison**

### **Nodes**

正确路径：

- `7.8 mmol/L`
- `verified factor × 18.0182`
- `140.54 mg/dL`
- `FPG DiabetesRange`

错误路径：

- `7.8` without valid unit
- `comparison blocked`

审计信息：

- `sourceValue/sourceUnit`
- `normalizedValue/normalizedUnit`

### **Relationships**

- 原始值经过已核实的项目专属换算到规范值。
- 规范值与相同单位的阈值比较。
- 原始值与规范值同时保留用于追踪。
- 缺单位或换算未核实时停止判定。

### **Direction**

主路径从左到右；拒绝路径位于主路径下方，在 conversion gate 处中断。

### **Hierarchy**

1. 大号公式 `7.8 × 18.0182 = 140.54`
2. 源值与规范值双保留
3. 拒绝判定边界

### **Highlight**

突出“单位参与业务结论”，而非仅突出数学换算。

### **Screenshot Plan**

- 目标截图：完整环境中 P90012 或对应场景的患者 bundle/assessment JSON。
- 截图重点：source value、source unit、normalized value、normalized unit、最终 range。
- 裁剪：保留一条 LabResult 和对应 Assessment；其他患者字段全部裁掉。
- Annotation：用同色连线连接 source 与 normalized 字段；框出 `conversion factor` 和 `DiabetesRange`。
- 当前状态：`MANUAL / Evidence Needed`，需重跑集成场景后取得。

---

# **Slide 12 — 系统不仅能回答“现在怎样”，还能安全回答“如果怎样”**

### **Primary Visual Type**

**Flowchart / Before–After Diagram**

### **Nodes**

共同输入：

- `Knowledge Snapshot`
- `Patient Graph Snapshot`
- `Rules Fingerprint`

Before 轨：

- `Fresh Dataset A`
- `Current Facts`
- `Before Conclusions`

After 轨：

- `Fresh Dataset B`
- `Current Facts + Hypothesis`
- `hypothetical=true`
- `After Conclusions`

输出：

- `Diff: added / removed / changed`
- `Derivation Tree`
- `GraphDB writes = 0`

### **Relationships**

- 两条轨道读取同一个知识与患者快照。
- Hypothesis 只注入 After 轨。
- 两组结论进入 diff engine。
- GraphDB 仅提供快照，不接收写入箭头。

### **Direction**

从左到右的上下双轨；最终在右侧合并为 Delta。

### **Hierarchy**

1. Before/After 双轨
2. 黄色 Hypothesis 节点
3. Delta 结果
4. `Simulation ≠ Prediction` 限定语

### **Highlight**

突出“调用方显式提供假设”和“0 writes”，避免被理解为模型预测未来。

### **Screenshot Plan**

- 可选目标：完整环境调用 `POST /patients/{pid}/simulate` 后的 delta JSON。
- 截图重点：hypotheses、before、after、delta、derivationHash。
- 裁剪：只保留一条 added/changed 结论及假设，避免整页 JSON。
- Annotation：给 hypothesis 加黄色标注，给 delta 加青绿色标注。
- 当前状态：`MANUAL / Evidence Needed`，需同时保留运行前后 GraphDB 无写入的测试记录。

---

# **Slide 13 — 同一假设可以复现，但“可复现”不等于“临床正确”**

### **Primary Visual Type**

**Diagram + Code**

### **Nodes**

- `patient ID`
- `graph version`
- `knowledge snapshot SHA`
- `rules SHA`
- `sorted hypotheses`
- `SHA-256`
- `derivationHash`

### **Relationships**

五类规范化输入汇入 SHA-256；任何输入变化都会形成新哈希，相同输入产生相同哈希。

### **Direction**

左侧五条输入向中心汇聚，右侧输出单一指纹。

### **Hierarchy**

1. `derivationHash`
2. 五个覆盖字段
3. 右下角代码证据
4. `Reproducible ≠ Clinically Validated`

### **Highlight**

把最后一句作为本页最强限定，防止观众把确定性误认为医学有效性。

### **Code Snippet**

推荐使用以下 10 行真实源码，保留语法高亮和文件名：

```python
h = hashlib.sha256()
for label, value in (
    ("pid", pid),
    ("graphVersion", graph_version),
    ("knowledgeSha", knowledge_sha),
    ("rulesSha", rules_sha),
):
    h.update(f"{label}\x1f{value}\x1e".encode())
for fp in sorted(x.fingerprint() for x in hypotheses):
    h.update(f"hypothesis\x1f{fp}\x1e".encode())
```

来源：`src/dmo/simulate/hashing.py::derivation_hash`。

### **Screenshot Plan**

- 可选目标：终端连续执行同一推演 5 次的哈希输出。
- 截图重点：五行完全相同的哈希；旁边补一行改变假设值后的不同哈希。
- 裁剪：只保留命令摘要和哈希，不显示本地用户名、绝对路径或敏感连接信息。
- Annotation：同值用一条括号归组，变化值用另一种颜色。
- 当前状态：`MANUAL / Evidence Needed`。

---

# **Slide 14 — 每条结论都可以反向走回规则、原文和原始数据**

### **Primary Visual Type**

**Knowledge Graph + Screenshot**

### **Nodes**

中心结论：

- `Diagnosis` 或 `Assessment`

患者证据支路：

- `LabResult`
- `source table`
- `source PK`
- `sourceValue/sourceUnit`

知识证据支路：

- `Threshold`
- `Rule`
- `SourcePassage`
- `verbatim quote`
- `contentHash`
- `source document`

完整性状态：

- `brokenLinks[]`

### **Relationships**

- Diagnosis 由 Assessment/Fact 支撑。
- Assessment 使用 Threshold，并由 Rule 产生。
- Threshold/Rule 连接 SourcePassage。
- SourcePassage 连接逐字 quote、hash 与文档。
- LabResult 通过 source table + PK 回查 SQL 行。
- 任一缺失边进入 `brokenLinks[]`。

### **Direction**

从中心向左右展开：左边追患者原始数据，右边追知识来源；也可按阅读顺序从 SQL Row → Fact → Assessment → Rule → Passage。

### **Hierarchy**

1. 中心结论
2. 两条 provenance 支路
3. 逐字 quote 与 source PK 两个最终锚点
4. 断链状态

### **Highlight**

同时突出“回到原始 SQL 行”和“回到指南逐字原文”，这是与普通自然语言解释的关键差异。

### **Screenshot Plan**

- 主截图：本地运行 `ontology/tools/verify_passages.py` 的终端结果，显示 `31/31`。
- 辅助截图：`GET /graph/provenance?iri=...` 的精简响应，显示 evidence、sqlRows、brokenLinks。
- 裁剪：终端截图只留汇总与 2–3 条代表项；API 响应只保留 provenance 关键字段。
- Annotation：框出 quote/hash 校验结果、source table/PK、`brokenLinks`。
- `31/31` 终端结果可以从仓库当前环境重新执行生成，标记为 `AUTO`。
- provenance API 截图依赖完整服务环境，标记为 `MANUAL`。

### **Production Notes**

- Knowledge Graph 应使用 Graphviz 生成 SVG，避免手工节点错位。
- 图中节点数量控制在 10–12 个，不能展示完整 ontology。

---

# **Slide 15 — 可信不是口号：哪些已经证明，哪些还没有**

### **Primary Visual Type**

**Comparison + Chart + Screenshot**

### **Chart Design**

使用左右证据矩阵，不使用完成率圆环或总分，因为通过、跳过、违规和未实现不属于同一分母。

左侧 `Proven / Implemented`：

- `31 / 31 passage verification`
- `19 guard tests passed`
- `read-only protections implemented`
- `named graph PUT + in-memory simulation implemented`

右侧 `Not Yet Proven`：

- `155 integration tests skipped`
- `2 new SHACL violations`
- `no executable baseline harness`
- `no built-in Agent loop`

### **Hierarchy**

1. 左右边界对照
2. 四个可引用数字：31/31、19、155、2
3. 页尾：`No unsupported benchmark numbers`

### **Highlight**

重点突出“证据边界透明”，不是把左侧包装成项目完成度。

### **Screenshot Plan**

- 截图 A：`.venv/bin/python -m pytest -q` 汇总 `19 passed, 155 skipped`。
- 截图 B：`verify_passages.py` 汇总 `31/31`。
- 截图 C：`validate_shacl.py` 汇总，显示 12 条违规、10 条已知基线、2 条新增。
- 裁剪：每张只保留最后 3–6 行；组合为一条横向“证据带”，不显示大段终端日志。
- Annotation：分别使用青绿、琥珀、琥珀框出数字；不要把 skipped 画成 passed。
- 以上均可由当前仓库命令重新生成，标记为 `AUTO`。

### **Do Not Use**

- 禁止截取 `demo/index.html` 中 94.7%、89.3%、100% 等静态评测数字。
- 禁止制作总体准确率、医疗效果或 benchmark 提升图。

---

# **Slide 16 — 项目的价值，是把“相信模型”转成“检查证据”**

### **Primary Visual Type**

**Diagram + Icons**

### **Nodes**

- `Knowledge Governance`
  - rebuildable
  - versioned
  - defect-locatable
- `Data Governance`
  - mapping
  - units
  - trust state
- `Reasoning Governance`
  - rules
  - context
  - boundaries
- `Agent Governance`
  - manifest
  - prohibitions
  - evidence contract
- 终点：`Verifiable Semantic Control Plane`
- 角色：Knowledge Engineer、Data Engineer、Agent Developer、Technical Governance

### **Relationships**

- 四类治理能力按证据生命周期串联，而非组织架构层级。
- 每类治理能力对应一类主要使用者。
- 四类能力共同支撑语义控制面。

### **Direction**

从左到右的价值链，最终收束到右侧大号结论。

### **Hierarchy**

1. `Verifiable Semantic Control Plane`
2. 四类治理能力
3. 对应角色

### **Highlight**

让 `Generate less. Verify more.` 成为视觉收束；图标只用于快速区分角色，不作为装饰。

### **Icon Guidance**

- Knowledge：书页 + 节点
- Data：数据库 + 校验标记
- Reasoning：规则六边形
- Agent：接口括号或 manifest 文档
- 不使用机器人头像、医生头像或拟人化 AI。

---

# **Slide 17 — 下一阶段：从可信推理底座，走向可评测、可运营的系统**

### **Primary Visual Type**

**Timeline**

### **Nodes**

- `NOW · Validation Closure`
  - fix 2 new SHACL violations
  - mandatory PG + GraphDB integration tests
- `NEXT · Agent + Evaluation`
  - controlled Agent loop
  - reproducible baseline harness
- `LATER · Production Governance`
  - auth / audit / rate limit / observability
  - knowledge approval / human review
- 收束：`Evidence-aware before autonomous.`

### **Relationships**

- NOW 是 NEXT 的前置条件：证据闭环未完成，不应先扩大 Agent 自主性。
- NEXT 是 LATER 的前置条件：没有可重复评测，就不能证明生产价值。
- 三阶段均为未来工作，不与当前已实现能力混在一起。

### **Direction**

从左到右的三阶段时间线；每阶段之间使用依赖箭头，而不是装饰性进度条。

### **Hierarchy**

1. NOW / NEXT / LATER
2. 每阶段两个交付物
3. 最终原则 `Evidence-aware before autonomous.`

### **Highlight**

NOW 使用最强色，强调近期优先级是补齐验证闭环，而不是立即接入更强模型。

### **Production Notes**

- 所有未来节点使用虚线边框，并统一标注 `Evidence Needed / Planned`。
- 不给路线图添加未经仓库支持的日期、季度、负责人或完成百分比。

---

## **Screenshot and Code Safety Rules**

- 截图前移除数据库连接串、Token、用户名、绝对用户目录和患者敏感信息。
- 合成终端截图时只允许裁剪与 annotation，不得修改命令结果文本。
- 运行环境缺失导致跳过的测试必须原样显示 `skipped`。
- `demo/index.html` 可以作为 UI 原型素材参考，但不可作为性能、准确率、用户案例或已实现 Agent loop 的证据。
- 代码截图必须来自仓库当前版本，并显示文件名；每段 5–12 行，最多突出 2–3 行。
- 图中的医疗阈值、单位和状态必须来自仓库 ontology/rule/seed，不手工补充外部医疗知识。

---

## **Asset Checklist**

### **Architecture Diagrams**

- `AUTO` Slide 08：知识平面、患者平面、GraphDB 推理平面、访问层与模拟沙箱架构图。
- `AUTO` Slide 06：本体知识库构建与质量门禁架构图。

### **Flow Diagrams**

- `AUTO` Slide 01：完整证据链与 Evidence Insufficient 中断链。
- `AUTO` Slide 03：尿蛋白普通匹配 vs 语义门禁对比流程。
- `AUTO` Slide 04：Unknown 状态分层漏斗。
- `AUTO` Slide 05：Build → Ground → Reason → Verify 总体链路。
- `AUTO` Slide 07：LLM / Manual / Registry / Derived policy 分流图。
- `AUTO` Slide 09：单次请求序列图。
- `AUTO` Slide 10：A1C Provisional vs Confirmed 时间线。
- `AUTO` Slide 11：FPG 单位换算与拒绝路径。
- `AUTO` Slide 12：模拟 Before/After 双轨与 Delta。
- `AUTO` Slide 13：derivationHash 输入合成图。
- `AUTO` Slide 16：四类治理价值链。
- `AUTO` Slide 17：NOW / NEXT / LATER 路线图。

### **Ontology / Knowledge Graph Diagrams**

- `AUTO` Slide 14：Conclusion → Fact/Assessment → Rule/Threshold → SourcePassage → quote/hash，以及 SQL Row 支路的 provenance 图。
- `AUTO` Slide 08：`urn:dmo:patient:*`、知识命名图与 `urn:dmo:inferred` 的图层分区。

### **Screenshots**

- `MANUAL` Slide 10：完整 PG + GraphDB 环境下 P90002/P90003 assessment 响应截图；`Evidence Needed`。
- `MANUAL` Slide 11：单位换算场景的 source/normalized/assessment 响应截图；`Evidence Needed`。
- `MANUAL` Slide 12：simulation delta 与零写入验证截图；`Evidence Needed`。
- `MANUAL` Slide 13：同一请求 5 次相同 derivationHash 的终端截图；`Evidence Needed`。
- `AUTO` Slide 14：`verify_passages.py` 的 31/31 汇总截图。
- `MANUAL` Slide 14：`/graph/provenance` 精简响应截图，需要完整服务环境。
- `AUTO` Slide 15：pytest、passage verifier、SHACL validator 三段终端证据截图。

### **Charts**

- `MANUAL` Slide 02：历史患者数据缺口图；必须先重新连接原始数据库复核数字，`Evidence Needed`。
- `AUTO` Slide 15：基于真实命令输出生成的证据矩阵；不是 benchmark 图。

### **Code Snippets**

- `AUTO` Slide 07：`semantic_extract.py` 的 policy 常量与 `extractable()`，5–7 行。
- `AUTO` Slide 13：`hashing.py::derivation_hash` 的字段哈希与假设排序，10 行。
- `AUTO` 可选备用：`graph/provenance.py::trace` 中 brokenLinks 返回逻辑，仅在 Slide 14 图空间不足以证明断链状态时使用，控制在 5–10 行。

### **Icons**

- `AUTO` 一套统一线性图标：database、document/hash、rule、API、external Agent、validation gate、warning/unknown、sandbox。
- `AUTO` Slide 16 四个角色/治理类型图标。
- 图标应来自同一开源图标集或使用 PowerPoint 内置图标，并在最终 Speaker Notes 记录来源。

### **Logo and Brand Assets**

- `MANUAL` 项目正式 Logo；仓库当前未发现可证明为正式品牌资产的 Logo 文件。
- `AUTO` 若无正式 Logo，使用纯文字字标 `DMO · Diabetes Ontology Agent`，不得自行创造机构 Logo。
- `MANUAL` 主办方、团队或公司 Logo，仅在用户提供并确认使用权限后加入。

### **Do Not Prepare**

- 不准备医生、患者、医院或 AI 大脑图库。
- 不准备静态 Demo 中的 94.7%、89.3%、100% 指标图。
- 不准备准确率、用户数量、医疗效果、客户案例或性能 benchmark 图。
- 不使用完整 `demo/index.html` 推理控制台作为已实现系统截图；其内容含硬编码指标和当前仓库未实现的 Agent Trace 表达。
