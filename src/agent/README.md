# 糖尿病本体查询 Agent

基于 LangChain `create_agent` 的 harness：模型负责选择工具与组织回答；工具边界、数据库只读事务、调用预算、结果预算、超时和流式事件负责约束执行。复用 `src/dmo/api.py` 的语义与图查询逻辑，不在 agent 内复制本体推理规则。

HTTP 请求、SSE 事件字段、错误响应与客户端示例见 [智能体 API 文档](../../docs/AGENT-API.md)。

## 启动

```bash
uv sync --extra agent
uv run --extra agent dmo-agent --serve
```

访问 http://127.0.0.1:8200 。页面逐步显示待办清单、通俗回答、查询阶段和证据，支持停止查询。右侧“知识图谱”把成功工具结果中的真实节点和关系投影为可旋转、缩放、暂停及按事件回放的 3D 动画；“技术日志”保留原始工具参数和结果。DMO API 在进程内调用，不需要另启 8100 服务。

页面来自仓库根目录的 `frontend/`（Vite + React）。本模块只托管构建产物 `frontend/dist`；未构建时回落到包内的 `src/agent/index.html` 单文件页面，服务本身照常可用。

```bash
cd frontend && npm install && npm run build   # 产物进 frontend/dist，然后 dmo-agent --serve 即可
cd frontend && npm run dev                    # 开发期：Vite 在 5173，把 /chat 代理到 8200
```

`AGENT_ORIGIN` 可改代理目标（默认 `http://127.0.0.1:8200`）。前端只消费本文「流式契约」一节的事件：`todo_update` 整体替换清单，工具事件按 `call_id` 配对而非按到达顺序，缺 `done` 判本轮作废。证据区只渲染 `tool_end` 结果里实际存在的 `sources` / `inferredFacts` / `assertedFacts` / `unmapped` 等字段，取不到就不显示。3D 图同样只读取 `tool_end(ok=true)` 的结构化结果，不从模型回答猜测关系；模拟结果使用独立命名空间，并在界面明确标成“假设推演”。图中位置只为方便观察，不表达医学距离、因果强度或风险大小。

CLI（每行一个 JSON 事件）：

```bash
uv run --extra agent dmo-agent --json '查询糖化血红蛋白对应的本体概念与规则出处'
```

SSE：

```bash
curl -N http://127.0.0.1:8200/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"message":"查询糖化血红蛋白对应的本体概念与规则出处"}'
```

## 配置

复用仓库根目录 `.env`；环境变量优先。不把密钥写进源码或日志。

| 变量 | 用途 / 默认值 |
| --- | --- |
| `OPENAI_API_KEY` | SiliconFlow 凭据，必填 |
| `OPENAI_BASE_URL` | `https://api.siliconflow.cn/v1` |
| `OPENAI_MODEL_TEXT` | `glm-5.2`（在 SiliconFlow 自动规范为 `zai-org/GLM-5.2`） |
| `PATIENT_INFO_ORIGINAL_PG_DSN` | 患者原始库连接串 |
| `PATIENT_INFO_ORIGINAL_SCHEMA` | `patient_analysis` |
| `PATIENT_INFO_ONTOLOGY_PG_DSN` | 本体关系库连接串 |
| `PATIENT_INFO_ONTOLOGY_SCHEMA` | `diabetes` |
| `DMO_GRAPHDB_ENDPOINT` | GraphDB 根地址 |
| `DMO_GRAPHDB_REPOSITORY` | `dmo` |
| `DMO_GRAPHDB_TIMEOUT` | 30 秒 |
| `AGENT_MODEL_TIMEOUT` | 模型请求 60 秒 |
| `AGENT_RUN_TIMEOUT` | 单轮总时限 180 秒 |

两个数据库和 GraphDB 继续由 `dmo.config` 加载。Schema 在进程启动时确定，修改后需重启。现有 DMO 部分查询固定使用 diabetes，因此部署应保持本项目提供的 schema。

## Harness 边界

- 多轮会话按 `conversation_id` 隔离，状态存在图的 checkpointer 里（`build_serving_agent` 挂 `InMemorySaver`）。同一会话内模型看得到之前几轮的消息、工具结果与待办清单；不同会话之间不共享任何内容。对外一律叫 `conversation_id`，LangGraph 内部的键仍是 `configurable.thread_id`，只在提交 config 时映射一次。CLI 与测试走 `build_agent`，不挂 checkpointer，保持单轮无记忆。
- 会话只活在服务进程内存里：**重启即清空**，多副本部署时同一会话不保证落到同一进程。上限 32 个会话（`runtime.MAX_CONVERSATIONS`），超出按最近最少使用逐出并删除其 checkpoint；正在执行的会话不回收。同一会话的并发请求串行执行，排队时间计入本轮总时限。
- `AgentHarness` 是进程级单例（`create_app` 内懒构建 + 锁）。会话状态存在它持有的 checkpointer 里，**每个请求现建 harness 会让多轮上下文静默丢失**；`test_http_multi_turn_reuses_one_agent_and_keeps_context` 守这条。
- **调用预算按轮计，不按会话累计**：每一轮仍是 12 次模型调用、24 次工具调用。会话越长，单轮送进模型的 token 越多，预算不会随之放宽。
- 不提供断点续跑。
- 官方 Python `TodoListMiddleware` 提供 `write_todos` 工具，将完整待办清单存入本轮图状态。多步骤或明确要求清单的任务先规划，执行时更新 pending / in_progress / completed；简单任务可直接回答。`report_plan` 保留兼容，使用待办清单时不重复调用。任务拆解与完成判定由模型负责，不代表临床结论得到验证。
- LangChain 中间件限制每轮 12 次模型调用、24 次工具调用；总超时与图递归上限作为额外终止条件。
- 两个 PostgreSQL 连接均使用只读事务、5 秒连接超时、10 秒 SQL 超时；模型无法提交 SQL，只能选择表、列与等值筛选条件。标识符安全引用，值参数化。
- 原始库沿用 `dmo.db.etl.SPECS` 的表/列白名单，排除姓名、身份证与联系方式；检验结果按 detail 表取得的 testcode 回查。每次查询先实时验证 schema。
- 本体关系库仅开放指定 core、pred、map、stg 表，自动补回来源、质量、单位和证据字段。每次最多 100 行，offset 最多 10000；返回 hasMore/nextOffset。core 表必须指定患者或来源。
- 默认检索 ehr-legacy 患者，演示数据单独指定来源。原始结果带质量提醒，不能代替语义规则判定。
- 图工具使用 DMO 固定的只读端点；不暴露任意 URL、自由 SQL、自由 SPARQL、写入、ETL 或预测端点。
- `simulate_patient_course` 走 `POST /patients/{pid}/simulate`，但**仍然只读**：推演全程在内存跑，对 GraphDB 只发 CONSTRUCT，三元组数量不变。假设项 `{term, value, unit, date}` 四个字段在工具 schema 层就是必填，一次最多 10 条 —— 服务端不猜术语、不默认单位、不补日期（30 天规则靠日期区分 Provisional 与 Confirmed）。假设值必须由用户给出，模型不得自行生成。
- 单个工具结果超过 24000 字符会明确要求缩小查询范围，不把截断引文当完整证据。异常不输出底层连接串、凭据和患者 SQL 参数。
- 使用本地流式事件展示过程；禁用本轮 LangSmith 托管追踪，即使宿主环境已全局启用。查询所得事实仍会发送给配置的模型服务供回答使用。

## 工具

| 工具 | 功能 |
| --- | --- |
| `write_todos` | 中间件提供；创建或替换本轮待办清单 |
| `report_plan` | 兼容旧版的简短行动计划 |
| `ontology_status` | health / manifest / schema |
| `search_concepts` | 表面形式 → IRI 与 usable |
| `explore_concept` | node / neighbors / taxonomy / provenance |
| `find_graph_path` | 最多三跳路径 |
| `search_rules` | 阈值、目标、风险规则与单条详情 |
| `search_passages` | 逐字原文与完整哈希 |
| `explain_term` | 术语映射与不可用原因 |
| `find_patients` | 按诊断、来源、档位分页检索 |
| `patient_evidence` | 患者判定、风险、安全、建议、监测或照护链 |
| `simulate_patient_course` | 确定性条件推演（若 X 则 Y）+ 推导树；只读、内存计算 |
| `inspect_fact_schema` | 两库可查表、列、类型与注释 |
| `query_patient_facts` | 两库受控事实查询与分页 |

## 流式契约

每个事件含 `type`、`run_id`、递增 `seq`。工具事件用 `call_id` 配对，支持并行调用交错。SSE 的 `id` 等于 seq，但当前不实现断线重放。

请求体：`{"message": "...", "conversation_id": "..."}`。`conversation_id` 可省略 —— 省略即开新会话，服务端生成并通过 `run_start.conversation_id` 回传，客户端之后带回来即可续上。**`run_id` 每轮都不同，`conversation_id` 标记同一段对话、跨轮不变。**

`run_start → model_start → text_delta / tool_start / tool_end → … → answer → done`

- `run_start` 额外带 `conversation_id` 与 `model`。
- `tool_start.arguments` 展示实际调用参数；`tool_end.result` 展示有限大小的结果。失败通过 `tool_end.ok=false` 表示；整轮异常通过 `error` 事件表示。
- `todo_update.todos` 是已写入图状态的完整待办列表，前端整体替换清单。失败或取消不会自动将未完成项标成完成。
- `text_delta` 是模型公开文本增量，可能包含行动说明；`answer` 是最终完整回答，前端用它替换增量区域，避免重复。
- 只展示公共 text 内容，不暴露供应商 reasoning 字段。
- 初始化错误返回 HTTP 503；流启动后的错误返回 `error` 和 `done(status=failed)`，不能把 HTTP 200 当作成功。
- 取消请求向模型流传播；已开始的同步 DMO/SQL 工作可能继续到各自超时。HTTP/数据库超时限制后台工作。

服务默认绑定 127.0.0.1，面向本地使用；当前没有用户认证、患者级授权、生产审计持久化或多租户隔离，不能直接作为公开医疗数据服务部署。

## 验证

```bash
uv run --extra agent --extra dev pytest tests/test_agent.py -q
cd frontend && npm test && npm run build
```

离线测试覆盖真实 LangChain 工具循环、预算终止、SQL 参数化与白名单、只读连接、SSE、推理字段过滤、超时和异常脱敏。数据库与模型连通性需要在配置完备的环境额外验证。

设计依据：[LangChain overview](https://docs.langchain.com/oss/python/langchain/overview)、[streaming](https://docs.langchain.com/oss/python/langchain/streaming)、[middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)。采用稳定的 `astream_events(version="v2")` 适配为项目自己的事件协议。
