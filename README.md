# diabetes-ontology-agent

基于 OWL 本体的糖尿病领域智能体 —— 技术验证 / 学习项目。

两层结构：

1. **语义层**：糖尿病领域的 OWL/RDF 本体，复用 MONDO / LOINC / ATC / HPO 等开源标准术语，配 SPARQL 规则层和 SHACL 约束层。
2. **Agent Harness**：手写 tool-calling 运行时骨架 + 可量化的评测 harness。

核心产出不是本体本身，而是一份 **纯 LLM baseline vs 本体 agent 的对比评测报告** —— 用数据回答"ontology 到底给 LLM 带来了什么"。

📄 完整设计方案见 [docs/DESIGN.md](docs/DESIGN.md)

演示页面位于 [`demo/`](demo/)，与正式的本体及 Agent 实现隔离。

---

> ⚠️ 本项目仅用于技术学习，不是医疗器械，不构成任何医疗建议。所有输出均不包含具体用药剂量。
