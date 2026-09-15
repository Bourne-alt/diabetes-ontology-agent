# 智能体 API 文档

本文描述 `src/agent` 当前实现的 HTTP API 与 SSE 事件协议，供前端、脚本和其他服务接入。接口版本：`0.1.0`。

## 1. 服务地址与启动

默认地址：`http://127.0.0.1:8200`。

```bash
uv sync --extra agent
uv run --extra agent dmo-agent --serve --port 8200
```

Agent 在进程内复用 DMO API 的业务逻辑，无需另外启动 8100 服务。PostgreSQL、GraphDB 和模型服务仍须可访问。

| 方法 | 路径 | 返回类型 | 用途 |
| --- | --- | --- | --- |
| GET | `/` | `text/html` | 本地查询页面 |
| POST | `/chat/stream` | `text/event-stream` | 发起一轮智能体查询，流式返回执行过程与回答 |
| GET | `/docs` | `text/html` | Swagger UI |
| GET | `/redoc` | `text/html` | ReDoc |
| GET | `/openapi.json` | `application/json` | 自动生成的 OpenAPI 描述 |

当前只有 `/chat/stream` 是对外的智能体业务接口。内部工具不是独立 HTTP 路由，不能请求 `/search_concepts` 等工具名。DMO 的 `/patients`、`/graph/*` 等接口也没有挂载到 Agent 的 8200 端口。

OpenAPI 可用于查看请求模型；SSE 的事件结构以本文为准，当前未逐项建模进 OpenAPI。

## 2. 发起流式查询

### 请求

```http
POST /chat/stream
Content-Type: application/json
Accept: text/event-stream
```

```json
{
  "message": "查询糖化血红蛋白对应的本体概念与一条规则出处。"
}
```

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `message` | string | 是 | 长度 1–12000 个字符，不得仅含空白字符 |

接口目前不接受有业务意义的 `history`、`session_id`、`thread_id`、`patient_id` 或 `model` 参数；患者编号、查询范围和必要背景应写入 `message`。额外字段按当前 Pydantic 默认行为忽略，不会改变执行配置。

每个请求独立执行，不自动继承上一轮对话。`run_id` 是本轮追踪标识，不能用于继续历史会话。

### 响应头

请求校验和初始化成功后返回 HTTP 200：

```http
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache, no-store
X-Accel-Buffering: no
```

HTTP 200 只表示流已建立。必须继续读取事件，依据 `done.status` 判断本轮是否正常完成。

### cURL 示例

```bash
curl --no-buffer http://127.0.0.1:8200/chat/stream \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -d '{"message":"查询糖化血红蛋白对应的本体概念与一条规则出处。"}'
```

## 3. SSE 帧格式

每条事件以空行结束。`data` 是单行 JSON，文本中的换行会作为 JSON 转义字符传输。

```text
id: 1
event: run_start
data: {"type":"run_start","run_id":"example-run","seq":1,"message":"开始查询","model":"zai-org/GLM-5.2"}

```

以下示例中的 `example-run`、`call-1` 和工具结果仅用于说明协议，不代表真实查询记录。

### 公共字段

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `type` | string | 事件类型，与 SSE 的 `event` 一致 |
| `run_id` | string | 服务端为本轮生成的 UUID 字符串；同一轮保持不变 |
| `seq` | integer | 本轮事件序号，从 1 开始严格递增；与 SSE 的 `id` 一致 |

序号不跨请求累计。目前不支持 `Last-Event-ID` 重放、断线续传或事件历史查询。不同工具的事件可以交错，使用 `call_id` 配对，不要依赖相邻位置。

## 4. 事件类型

| 事件 | 附加字段 | 含义与处理方式 |
| --- | --- | --- |
| `run_start` | `message: string`、`model: string` | 本轮开始，展示实际使用的模型名称 |
| `model_start` | `message: string` | 开始一次模型调用，一轮中可多次出现 |
| `text_delta` | `text: string` | 公开文本增量，追加到临时回答区域 |
| `tool_start` | `tool: string`、`call_id: string`、`arguments: object` | 开始调用工具，展示工具名与实际参数 |
| `tool_end` | `tool: string`、`call_id: string`、`ok: boolean`、`result: any` | 工具返回；依据 `ok` 区分正常结果与失败 |
| `todo_update` | `todos: array` | 已写入本轮图状态的完整待办清单，整体替换显示 |
| `answer` | `text: string` | 最终完整回答，替换临时回答区域 |
| `error` | `code: string`、`message: string` | 本轮执行失败；展示可读错误原因 |
| `done` | `status: "completed" \| "failed"` | 正常完成或执行失败的终止事件 |

当前实现没有独立的 `plan` 或 `tool_error` 事件。官方 Python `TodoListMiddleware` 提供 `write_todos` 工具，计划更新由 `todo_update` 呈现；被工具边界捕获的错误由 `tool_end(ok=false)` 呈现。

### 4.1 待办清单

对于多步骤需求、多个问题或用户明确要求清单的任务，模型使用 `write_todos` 创建并更新待办。简单问候或单步任务可以不创建清单。中间件注册工具，不新增 HTTP 路由。

工具调用参数示例：

```json
{
  "todos": [
    {"content": "解析糖化血红蛋白概念", "status": "in_progress"},
    {"content": "核对规则及原文出处", "status": "pending"}
  ]
}
```

`write_todos` 仍产生 `tool_start` 和 `tool_end` 事件。图状态成功应用更新后，额外发出：

```json
{
  "type": "todo_update",
  "run_id": "example-run",
  "seq": 5,
  "todos": [
    {"content": "解析糖化血红蛋白概念", "status": "completed"},
    {"content": "核对规则及原文出处", "status": "in_progress"}
  ]
}
```

| 待办字段 | 类型 | 含义 |
| --- | --- | --- |
| `content` | string | 具体任务描述 |
| `status` | string | `pending`（待处理）、`in_progress`（进行中）、`completed`（已完成） |

每次写入和每次事件都包含完整清单，客户端应整体替换，不能追加；空数组表示清空清单。当前待办没有独立 ID，不支持增量 patch。同一模型轮次不能并行写入多份待办清单。

待办只属于当前请求，不跨轮保存。失败、取消或证据不足不会由服务端自动标成完成；模型应如实保留未完成任务，并解释阻塞原因。`done.status=completed` 仅表示运行正常结束，不保证所有待办都为 completed。

旧版 `report_plan(steps)` 工具继续兼容，但仅返回简短行动说明，不更新 todos，也不产生 `todo_update`；使用待办清单后无需再调用它。最终回答仍通过 `answer` 返回，不能只发送清单作为回答。

### 4.2 工具结果

`result` 的结构因工具而异。通过 DMO API 返回的正常结果一般封装为：

```json
{
  "ok": true,
  "source": "/graph/concepts",
  "data": {
    "query": "示例查询",
    "concepts": [],
    "total": 0
  }
}
```

`source` 是内部 DMO 接口路径，不是 Agent 端口上可直接访问的路由。上例省略了其他业务字段，实际结果以对应 DMO 接口为准。

直接查询事实库的结果包含 `database`、`schema`、`table`、`columns`、`filters`、`rows`、`rowCount`、`hasMore`、`nextOffset`、`notice`。`hasMore=true` 时可继续分页，不能把当前页视为全部记录。

工具失败示例：

```json
{
  "type": "tool_end",
  "run_id": "example-run",
  "seq": 6,
  "tool": "query_patient_facts",
  "call_id": "call-2",
  "ok": false,
  "result": {
    "ok": false,
    "error": "ValueError",
    "hint": "需要显式列名和等值筛选条件（最多 40 列 / 8 个条件）。"
  }
}
```

`tool_end.ok=false` 不一定终止整轮；模型仍可修正参数、换用合适工具或说明无法判定。预算终止、取消或底层中断也可能导致某个 `tool_start` 没有配对的 `tool_end`，客户端应在终止时清理“执行中”状态。

### 4.3 增量与完整回答

```json
{"type":"text_delta","run_id":"example-run","seq":7,"text":"根据本轮查询，"}
```

```json
{"type":"answer","run_id":"example-run","seq":8,"text":"本轮未取得足够证据，无法作出判定。"}
```

```json
{"type":"done","run_id":"example-run","seq":9,"status":"completed"}
```

`text_delta` 可能包含中途的行动说明，不保证拼接后等于最终回答。收到 `answer` 后应替换已有增量文本，不能再次追加造成重复。

`completed` 表示执行正常结束，不表示所有工具均成功，也不表示获得了肯定的临床结论。回答可能是“证据不足”或“无法判定”。

### 4.4 典型事件顺序

```text
run_start
  → model_start
  → text_delta（可选、可重复）
  → tool_start / tool_end（可选、可交错）
  → model_start（可重复）
  → text_delta（可选、可重复）
  → answer
  → done(status=completed)
```

运行失败时通常以 `error → done(status=failed)` 结束。网络断开、客户端取消或进程退出时可能没有终止事件；此时应将本轮标记为中断，不能推断成功。

## 5. 错误处理

### 流建立前：HTTP 错误

| HTTP 状态 | 情况 | 响应说明 |
| --- | --- | --- |
| 422 | 缺少 message、类型或长度不符合要求、JSON 无效 | FastAPI/Pydantic 校验错误，`detail` 通常是数组 |
| 422 | message 仅含空白 | `{"detail":"message 不能为空白"}` |
| 503 | Agent 初始化失败 | `{"detail":"Agent 初始化失败，请检查模型与数据库配置。"}` |

### 流建立后：error 事件

```text
id: 3
event: error
data: {"type":"error","run_id":"example-run","seq":3,"code":"APIStatusError","message":"模型服务账号余额不足（HTTP 402），请充值后重试。"}

id: 4
event: done
data: {"type":"done","run_id":"example-run","seq":4,"status":"failed"}

```

上述 402 是模型服务的状态，不是 `/chat/stream` 已建立连接的 HTTP 状态。

| 底层情况 | 用户可见提示 |
| --- | --- |
| 模型服务 402 | 账号余额不足，充值后重试 |
| 模型服务 401 / 403 | 认证失败或无权限，检查模型密钥 |
| 模型服务 429 | 限流或额度不足，稍后重试或检查配额 |
| 单轮总超时 | 已达到执行时限，查询未完成 |
| 其他模型、数据服务异常或调用预算耗尽 | 本轮未完成，检查配置后重试 |

`error.code` 当前是异常类名，可能随依赖版本变化；客户端应以事件类型和 `done.status` 控制流程，不要把异常类名视为稳定业务枚举。错误提示不会返回底层完整异常文本。

## 6. Python 客户端示例

依赖 `httpx`。下面逐行读取 SSE，打印过程事件，并在失败或连接不完整时抛出异常。

```python
import json
import httpx


def query_agent(message: str) -> str:
    answer = None
    completed = False
    failure = None

    # 读取超时大于默认单轮执行时限；服务端不发送周期性心跳。
    with httpx.Client(timeout=httpx.Timeout(210.0, connect=10.0)) as client:
        with client.stream(
            "POST",
            "http://127.0.0.1:8200/chat/stream",
            headers={"Accept": "text/event-stream"},
            json={"message": message},
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                # 当前服务将完整事件 JSON 写在单个 data 行。
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                kind = event["type"]
                if kind == "text_delta":
                    print(event["text"], end="", flush=True)
                elif kind in ("tool_start", "tool_end", "todo_update"):
                    print("\n", json.dumps(event, ensure_ascii=False))
                elif kind == "answer":
                    answer = event["text"]
                elif kind == "error":
                    failure = event["message"]
                elif kind == "done":
                    completed = event["status"] == "completed"
                    break

    if not completed or answer is None:
        raise RuntimeError(failure or "连接中断或未收到完整回答")
    return answer


result = query_agent("查询糖化血红蛋白对应的本体概念与规则出处。")
print("\n最终回答：\n" + result)
```

## 7. 浏览器接入

使用 `fetch` 发起 POST，再通过 `response.body.getReader()` 读取流。浏览器原生 `EventSource` 不能直接发送此接口所需的 POST JSON 请求。

前端应遵循以下处理步骤：

1. 提交时清空本轮临时状态，保存用于取消请求的 `AbortController`。
2. 先检查 HTTP 状态；非 2xx 时按 JSON 错误响应处理。
3. 使用流式 `TextDecoder` 解码并保留跨网络分片的缓冲；以空行分隔完整 SSE 帧，不能假设一个网络分片等于一个事件。
4. 使用 `call_id` 更新工具状态，收到 `todo_update` 时整体替换清单，追加 `text_delta`，用 `answer` 替换完整回答。
5. 收到 `done` 或连接中断后恢复提交按钮；没有正常终止事件时展示“已中断”。
6. 点击停止时调用 `controller.abort()`。停止后不保证还能收到 `done`。

生产前端实现位于 [frontend/src](../frontend/src)，未构建时才回落到 [src/agent/index.html](../src/agent/index.html)。React 前端使用受限 Markdown 渲染（忽略原始 HTML、过滤不安全链接），并把技术细节折叠在通俗结论之后。

“知识图谱”视图是 SSE 事件的客户端投影，并非新增的服务端事件类型。它只接受 `tool_end(ok=true)` 的结构化结果，以 `seq` 为时间轴支持回放；失败调用和模型自然语言不会生成节点或边。前端应保留节点的工具名、`call_id`、`seq`、来源、演示数据和推演标记。布局坐标仅用于展示，不能解释为因果关系、相似度、证据强度或风险数值。“技术日志”仍应允许用户查看原始事件。

## 8. 内部工具与数据来源

以下工具由模型选择调用，出现在 `tool_start.tool` / `tool_end.tool` 中。

| 工具名 | 用途 | 数据来源 |
| --- | --- | --- |
| `write_todos` | 创建或替换待办清单与执行状态 | TodoListMiddleware / 本轮图状态 |
| `report_plan` | 兼容旧版的简短行动计划 | 当前模型调用 |
| `ontology_status` | 服务状态、能力清单、schema | DMO health / manifest / schema |
| `search_concepts` | 中文、编码或英文解析为 IRI | 本体概念与术语映射 |
| `explore_concept` | 节点、邻接、层次、出处链 | 本体图与关联事实 |
| `find_graph_path` | 最多三跳图路径 | 本体图 |
| `search_rules` | 阈值、目标、风险规则及详情 | 本体规则 |
| `search_passages` | 逐字原文及 sha256 | 证据片段 |
| `explain_term` | 映射与不可用原因 | 术语层 |
| `find_patients` | 按诊断、来源、档位分页 | 本体关系库；默认 ehr-legacy |
| `patient_evidence` | 判定、风险、安全、建议、监测、照护链 | DMO 融合查询 |
| `simulate_patient_course` | 使用用户明确给出的数值、单位与日期做只读条件推演 | DMO 内存推演；结果不是患者已发生事实 |
| `inspect_fact_schema` | 可查表、列、类型、注释 | 两个 PostgreSQL 库 |
| `query_patient_facts` | 受控等值筛选与分页查询 | 两个 PostgreSQL 库 |

事实库参数 `database` 使用 `original` 或 `ontology`，分别对应患者原始库和本体关系库。数据库连接凭据由服务端配置，调用方不应通过请求消息传入。

业务结果中的 `fact_origin`、`trust_level`、`caveat`、`disclaimer`、`quote`、`sha256`、规则版本和证据缺口应保留。原始事实未通过质量门槛；零行、工具失败或 `Insufficient-Evidence` 都不能解释为“正常”或“无风险”。

## 9. 执行限制与配置

| 项目 | 当前默认值 | 设置方式 |
| --- | --- | --- |
| 模型服务地址 | `https://api.siliconflow.cn/v1` | `OPENAI_BASE_URL` |
| 模型 | `glm-5.2` | `OPENAI_MODEL_TEXT`；SiliconFlow 下规范为 `zai-org/GLM-5.2` |
| 模型凭据 | 必填 | `OPENAI_API_KEY`，仅服务端使用 |
| 单次模型请求超时 | 60 秒 | `AGENT_MODEL_TIMEOUT` |
| 单轮执行总时限 | 180 秒 | `AGENT_RUN_TIMEOUT` |
| 单轮模型调用次数 | 12 | `AgentSettings.max_model_calls`，HTTP 请求不可覆盖 |
| 单轮工具调用次数 | 24 | `AgentSettings.max_tool_calls`，HTTP 请求不可覆盖 |
| 单个工具结果预算 | 24000 字符 | `AgentSettings.max_result_chars` |
| 事实查询单页行数 | 默认 20，最多 100 | 内部工具 `limit` |
| 事实查询 offset | 0–10000 | 内部工具 `offset` |
| 事实查询连接 / SQL 超时 | 5 / 10 秒 | `FactStore` 连接配置 |

环境变量优先于仓库根目录 `.env`。数据库与 GraphDB 的配置项见 [Agent 使用说明](../src/agent/README.md)。超大工具结果返回 `result_too_large`，不会静默截断证据后作为完整结果提供。

取消请求会取消模型流；已启动的同步数据库或 DMO 工作可能持续到完成或其底层超时。当前没有单独的 HTTP 取消接口。

## 10. 使用边界

- 当前服务默认监听本机，未实现 HTTP 身份认证、患者级授权、跨域配置或多租户访问隔离。
- 不提供会话历史、结果持久化、断点恢复和周期性 SSE 心跳；部署代理时需关闭流式缓冲并设置合适的读取超时。
- 执行过程包括公开文本、工具参数和结果，不提供模型内部思维链或 reasoning 字段。
- 事件会脱敏已识别的凭据形式，但工具结果仍可能包含患者事实；不要把凭据脱敏等同于患者数据匿名化。
- 查询事实会传给配置的模型服务用于组织回答。本轮关闭 LangSmith 托管追踪，不自动上传该追踪日志。

## 11. 实现位置

| 文件 | 内容 |
| --- | --- |
| [src/agent/api.py](../src/agent/api.py) | 请求模型、HTTP 路由、SSE 帧封装 |
| [src/agent/runtime.py](../src/agent/runtime.py) | LangChain harness、事件生成、预算与错误处理 |
| [src/agent/tools.py](../src/agent/tools.py) | 工具名称、参数与 API 映射 |
| [src/agent/database.py](../src/agent/database.py) | 事实查询白名单、参数化 SQL、只读与分页 |
| [src/agent/settings.py](../src/agent/settings.py) | 模型配置与默认执行限制 |
| [frontend/src/components/KnowledgePanel.jsx](../frontend/src/components/KnowledgePanel.jsx) | 3D 图谱、事件回放、节点出处与技术日志入口 |
| [frontend/src/lib/knowledgeGraph.js](../frontend/src/lib/knowledgeGraph.js) | 从成功工具结果生成有来源标记的图数据 |
| [tests/test_agent.py](../tests/test_agent.py) | 工具循环、SSE 与错误边界测试 |
