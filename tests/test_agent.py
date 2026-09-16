"""Offline tests: real LangChain loop, bounded SQL, SSE and failure semantics."""

import asyncio
import json
from contextlib import contextmanager

import httpx
import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, ValidationError

from agent.api import create_app
from agent.backend import DmoBackend
from agent.database import FactStore
from agent.runtime import AgentHarness, build_agent
from agent.settings import AgentSettings
from agent.tools import build_tools
from dmo.config import Config

SETTINGS = AgentSettings(api_key="test-placeholder")
CFG = Config(
    "postgresql://unused/original", "postgresql://unused/ontology", "http://unused", "dmo", 1
)


def run(coro):
    return asyncio.run(coro)


class ScriptedModel(BaseChatModel):
    responses: list[AIMessage] = Field(default_factory=list)
    position: int = 0

    @property
    def _llm_type(self):
        return "offline-scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        response = self.responses[min(self.position, len(self.responses) - 1)]
        self.position += 1
        return ChatResult(generations=[ChatGeneration(message=response)])


async def collect(harness):
    return [e async for e in harness.stream("查询本体概念")]


def test_real_langchain_tool_loop():
    model = ScriptedModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "report_plan",
                        "args": {"steps": ["查概念"]},
                        "id": "plan-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="本轮只记录计划，尚未查询数据库。"),
        ]
    )
    events = run(
        collect(
            AgentHarness(
                build_agent(SETTINGS, model=model, backend=DmoBackend(), facts=FactStore(CFG)),
                SETTINGS,
            )
        )
    )
    starts = [e for e in events if e["type"] == "tool_start"]
    ends = [e for e in events if e["type"] == "tool_end"]
    assert starts[0]["tool"] == "report_plan"
    assert ends[0]["result"] == {"steps": ["查概念"]}
    assert starts[0]["call_id"] == ends[0]["call_id"]
    assert events[-2]["type"] == "answer"
    assert events[-1]["status"] == "completed"
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))


def test_completed_todo_does_not_erase_explanation_before_final_closing_text():
    explanation = '如果新增检查成立，按当前规则从暂时无法确认变为已确认；风险仍然资料不足。'
    model = ScriptedModel(responses=[
        AIMessage(content=explanation, tool_calls=[{'name': 'write_todos', 'args': {
            'todos': [{'content': '对比推演结果', 'status': 'completed'}]}, 'id': 'done1', 'type': 'tool_call'}]),
        AIMessage(content='推演已完成，结论已在上方呈现。'),
    ])
    events = run(collect(AgentHarness(build_agent(SETTINGS, model=model, backend=DmoBackend(), facts=FactStore(CFG)), SETTINGS)))
    final = next(e['text'] for e in events if e['type'] == 'answer')
    assert explanation in final
    assert events[-1]['status'] == 'completed'


def test_model_budget_is_failure_not_success():
    settings = AgentSettings(api_key="unused", max_model_calls=1)
    model = ScriptedModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "report_plan",
                        "args": {"steps": ["继续"]},
                        "id": "p",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    )
    events = run(
        collect(
            AgentHarness(
                build_agent(settings, model=model, backend=DmoBackend(), facts=FactStore(CFG)),
                settings,
            )
        )
    )
    assert events[-1]["status"] == "failed"
    assert not any(e["type"] == "answer" for e in events)


@pytest.mark.parametrize("reserve_final_call", [True, False])
def test_graph_steps_allow_default_model_budget_to_finish_or_stop(reserve_final_call):
    tool_rounds = SETTINGS.max_model_calls - int(reserve_final_call)
    model = ScriptedModel(responses=[
        AIMessage(content="", tool_calls=[{
            "name": "report_plan",
            "args": {"steps": ["离线验证"]},
            "id": f"plan-{i}",
            "type": "tool_call",
        }])
        for i in range(tool_rounds)
    ] + [AIMessage(content="验证完成。")])
    events = run(collect(AgentHarness(
        build_agent(SETTINGS, model=model, backend=DmoBackend(), facts=FactStore(CFG)),
        SETTINGS,
    )))
    assert model.position == SETTINGS.max_model_calls
    if reserve_final_call:
        assert events[-1]["status"] == "completed"
        assert events[-2]["text"] == "验证完成。"
    else:
        assert events[-1]["status"] == "failed"
        assert events[-2]["code"] == "ModelCallLimitExceededError"
        assert not any(e["type"] == "answer" for e in events)


class FakeCursor:
    def fetchall(self):
        return [{"patientid": "demo", "fact_origin": "demo-cohort"}] * 3


class RecordingStore(FactStore):
    captured = None

    def catalog(self, database, table=None):
        return {
            "schema": "diabetes",
            "columns": [{"column_name": x} for x in ["patientid", "fact_origin", "sex"]],
        }

    @contextmanager
    def connection(self, database):
        yield self

    def execute(self, statement, params):
        self.captured = statement.as_string(), params
        return FakeCursor()


def test_parameterized_query_and_provenance():
    store = RecordingStore(CFG)
    payload = "x'; DROP TABLE core_patient; --"
    result = store.query("ontology", "core_patient", ["sex"], {"patientid": payload}, 2)
    query, params = store.captured
    assert payload not in query
    assert params == [payload, 3, 0]
    assert '"fact_origin"' in query
    assert '"patientid"' in query
    assert result["hasMore"] and result["rowCount"] == 2
    assert result["nextOffset"] == 2


@pytest.mark.parametrize(
    "columns,filters,limit",
    [
        (["*"], {"patientid": "p"}, 20),
        (["sex"], {}, 20),
        (["sex"], {"patientid": "p"}, 101),
        (["sex"], {"patientid": {"$ne": ""}}, 20),
        (["sex"], {"sex": "male"}, 20),
    ],
)
def test_query_rejects_unsafe_shapes(columns, filters, limit):
    with pytest.raises(ValueError):
        RecordingStore(CFG).query("ontology", "core_patient", columns, filters, limit)


def test_schema_rejects_unknown_table_before_connect():
    with pytest.raises(ValueError):
        FactStore(CFG).catalog("original", "pg_authid")


def test_read_only_is_enforced_for_both_connections(monkeypatch):
    seen = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, query):
            seen.append(query)

    def connect(dsn, **kwargs):
        seen.append(kwargs)
        return Connection()

    monkeypatch.setattr("agent.database.psycopg.connect", connect)
    for database in ("original", "ontology"):
        with FactStore(CFG).connection(database):
            pass
    assert all(
        "default_transaction_read_only=on" in x["options"] for x in seen if isinstance(x, dict)
    )
    assert seen.count("SET TRANSACTION READ ONLY") == 2


class EventGraph:
    async def astream_events(self, *args, **kwargs):
        yield {
            "event": "on_chat_model_stream",
            "data": {
                "chunk": AIMessageChunk(
                    content=[
                        {"type": "reasoning", "reasoning": "private"},
                        {"type": "text", "text": "公开内容"},
                    ]
                )
            },
        }
        yield {"event": "on_chat_model_end", "data": {"output": AIMessage(content="公开内容")}}


def test_sse_and_reasoning_filter():
    async def request():
        harness = AgentHarness(EventGraph(), SETTINGS)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(harness)), base_url="http://test"
        ) as client:
            response = await client.post("/chat/stream", json={"message": "test"})
            assert response.headers["content-type"].startswith("text/event-stream")
            assert "private" not in response.text
            assert "公开内容" in response.text
            frames = [
                json.loads(x[6:]) for x in response.text.splitlines() if x.startswith("data: ")
            ]
            assert frames[-1]["status"] == "completed"
            assert (await client.post("/chat/stream", json={"message": " "})).status_code == 422

    run(request())


def test_stream_error_redacts_secrets():
    class BrokenGraph:
        async def astream_events(self, *args, **kwargs):
            raise RuntimeError("sk-sensitive postgresql://u:password@host/db")
            yield  # pragma: no cover

    events = run(collect(AgentHarness(BrokenGraph(), SETTINGS)))
    assert events[-1]["status"] == "failed"
    assert "sensitive" not in json.dumps(events)
    assert "password" not in json.dumps(events)


def test_timeout():
    class SlowGraph:
        async def astream_events(self, *args, **kwargs):
            await asyncio.sleep(1)
            yield {}

    events = run(
        collect(AgentHarness(SlowGraph(), AgentSettings(api_key="unused", run_timeout=0.01)))
    )
    assert events[-2]["code"] == "TimeoutError"
    assert events[-1]["status"] == "failed"


def test_tools_use_actual_api_contract():
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/graph/concepts")
    def concepts(q: str, limit: int):
        return {"q": q, "limit": limit}

    tools = {t.name: t for t in build_tools(DmoBackend(app), FactStore(CFG))}
    result = run(tools["search_concepts"].ainvoke({"q": "糖化", "limit": 3}))
    assert result == {"ok": True, "source": "/graph/concepts", "data": {"q": "糖化", "limit": 3}}


def test_settings_environment_overrides_file(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=file-secret\nOPENAI_MODEL_TEXT=file-model\n")
    monkeypatch.setenv("OPENAI_API_KEY", "env-secret")
    monkeypatch.setenv("OPENAI_MODEL_TEXT", "glm-5.2")
    settings = AgentSettings.load(env)
    assert settings.api_key == "env-secret" and settings.model == "zai-org/GLM-5.2"
    assert "secret" not in repr(settings)


def test_tool_failure_is_visible_and_loop_can_recover():
    model = ScriptedModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "report_plan",
                        "args": {"steps": []},
                        "id": "bad-plan",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="计划参数无效，本轮没有查询患者。"),
        ]
    )
    graph = build_agent(SETTINGS, model=model, backend=DmoBackend(), facts=FactStore(CFG))
    events = run(collect(AgentHarness(graph, SETTINGS)))
    result = next(e for e in events if e["type"] == "tool_end")
    assert result["call_id"] == "bad-plan"
    assert result["ok"] is False
    assert result["result"]["error"] == "ValueError"
    assert events[-1]["status"] == "completed"


def test_billing_failure_is_actionable():
    from agent.runtime import error_message

    error = RuntimeError("private error body")
    error.status_code = 402
    assert "余额不足" in error_message(error)
    assert "private" not in error_message(error)


def test_cancel_propagates_and_does_not_claim_success():
    class CancelledGraph:
        async def astream_events(self, *args, **kwargs):
            raise asyncio.CancelledError()
            yield  # pragma: no cover

    with pytest.raises(asyncio.CancelledError):
        run(collect(AgentHarness(CancelledGraph(), SETTINGS)))


def test_oversized_backend_result_is_explicit():
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/graph/passages")
    def passages():
        return {"quote": "x" * 300}

    result = run(DmoBackend(app, max_result_chars=100).request("/graph/passages"))
    assert result["ok"] is False
    assert result["error"] == "result_too_large"
    assert "quote" not in result


def todo_message(todos, call_id="todos-1"):
    return AIMessage(
        content="",
        tool_calls=[
            {"name": "write_todos", "args": {"todos": todos}, "id": call_id, "type": "tool_call"}
        ],
    )


def test_todo_lifecycle_stream_and_graph_state():
    initial = [
        {"content": "检索概念", "status": "in_progress"},
        {"content": "核对出处", "status": "pending"},
    ]
    progress = [
        {"content": "检索概念", "status": "completed"},
        {"content": "核对出处", "status": "in_progress"},
    ]
    finished = [
        {"content": "检索概念", "status": "completed"},
        {"content": "核对出处", "status": "completed"},
    ]

    def graph():
        model = ScriptedModel(
            responses=[
                todo_message(initial),
                todo_message(progress, "todos-2"),
                todo_message(finished, "todos-3"),
                AIMessage(content="离线流程示例已结束。"),
            ]
        )
        return build_agent(SETTINGS, model=model, backend=DmoBackend(), facts=FactStore(CFG))

    events = run(collect(AgentHarness(graph(), SETTINGS)))
    assert [e["todos"] for e in events if e["type"] == "todo_update"] == [
        initial,
        progress,
        finished,
    ]
    assert events[-1]["status"] == "completed"
    assert len([e for e in events if e["type"] == "tool_end" and e["ok"]]) == 3
    # Assert the actual LangGraph state, not just an optimistic UI event.
    state = run(graph().ainvoke({"messages": [{"role": "user", "content": "建立计划"}]}))
    assert state["todos"] == finished


def test_invalid_todo_does_not_publish_state():
    model = ScriptedModel(
        responses=[
            todo_message([{"content": "查询", "status": "invalid"}]),
            AIMessage(content="计划状态无效。"),
        ]
    )
    graph = build_agent(SETTINGS, model=model, backend=DmoBackend(), facts=FactStore(CFG))
    events = run(collect(AgentHarness(graph, SETTINGS)))
    assert not any(e["type"] == "todo_update" for e in events)
    assert any(e["type"] == "tool_end" and not e["ok"] for e in events)


def test_failed_run_keeps_unfinished_todo():
    settings = AgentSettings(api_key="unused", max_model_calls=1)
    pending = [{"content": "查询证据", "status": "in_progress"}]
    model = ScriptedModel(responses=[todo_message(pending)])
    graph = build_agent(settings, model=model, backend=DmoBackend(), facts=FactStore(CFG))
    events = run(collect(AgentHarness(graph, settings)))
    assert [e["todos"] for e in events if e["type"] == "todo_update"] == [pending]
    assert events[-1]["status"] == "failed"


def test_todos_do_not_leak_between_runs():
    model = ScriptedModel(
        responses=[
            todo_message([{"content": "第一轮任务", "status": "pending"}]),
            AIMessage(content="第一轮待办已记录。"),
            AIMessage(content="第二轮问候。"),
        ]
    )
    graph = build_agent(SETTINGS, model=model, backend=DmoBackend(), facts=FactStore(CFG))
    harness = AgentHarness(graph, SETTINGS)
    first = run(collect(harness))
    second = run(collect(harness))
    assert any(e["type"] == "todo_update" for e in first)
    assert not any(e["type"] == "todo_update" for e in second)


class RecordingModel(ScriptedModel):
    """记录每次模型调用实际看到的消息，用来证明上下文真的跨轮传到了模型。"""

    seen: list = Field(default_factory=list)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def test_conversation_id_carries_context_and_isolates_conversations():
    from langgraph.checkpoint.memory import InMemorySaver

    model = RecordingModel(
        responses=[
            AIMessage(content="第一轮回答"),
            AIMessage(content="第二轮回答"),
            AIMessage(content="新会话回答"),
        ]
    )
    harness = AgentHarness(
        build_agent(
            SETTINGS,
            model=model,
            backend=DmoBackend(),
            facts=FactStore(CFG),
            checkpointer=InMemorySaver(),
        ),
        SETTINGS,
    )

    async def turns():
        return (
            [e async for e in harness.stream("第一轮：查 P90002", conversation_id="c-1")],
            [e async for e in harness.stream("第二轮：那他呢", conversation_id="c-1")],
            [e async for e in harness.stream("另一个会话", conversation_id="c-2")],
        )

    first, second, other = run(turns())

    # conversation_id 随 run_start 回传，客户端据此续会话。
    assert first[0]["conversation_id"] == "c-1"
    assert other[0]["conversation_id"] == "c-2"
    assert first[0]["run_id"] != second[0]["run_id"]  # 同会话不同轮，run_id 仍然各自独立

    def texts(call):
        return [str(getattr(m, "content", "")) for m in model.seen[call]]

    # 第二轮：模型看得到第一轮的提问与回答。
    assert any("第一轮：查 P90002" in t for t in texts(1))
    assert any("第一轮回答" in t for t in texts(1))

    # 另一个会话完全看不到第一个会话的任何内容。
    assert all("第一轮" not in t for t in texts(2))


def test_stream_without_conversation_id_generates_one():
    events = run(collect(AgentHarness(EventGraph(), SETTINGS)))
    assert events[0]["conversation_id"]
    again = run(collect(AgentHarness(EventGraph(), SETTINGS)))
    assert events[0]["conversation_id"] != again[0]["conversation_id"]


def sse_frames(response):
    return [json.loads(x[6:]) for x in response.text.splitlines() if x.startswith("data: ")]


def test_http_multi_turn_reuses_one_agent_and_keeps_context():
    """走真实 HTTP 路径的两次请求 —— harness 建在请求函数里时，这个测试会挂。

    上一版就是那样写的：每个请求现建一个 agent 和全新的 checkpointer，
    conversation_id 转一圈回来对面没有任何状态，多轮上下文静默丢失。
    """
    from unittest.mock import patch

    from langgraph.checkpoint.memory import InMemorySaver

    import agent.api as api_module

    model = RecordingModel(
        responses=[AIMessage(content="第一轮回答"), AIMessage(content="第二轮回答")]
    )
    builds = []

    def fake_build_serving_agent(settings):
        builds.append(settings)
        return build_agent(
            settings,
            model=model,
            backend=DmoBackend(),
            facts=FactStore(CFG),
            checkpointer=InMemorySaver(),
        )

    async def two_requests():
        with (
            patch.object(api_module, "build_serving_agent", fake_build_serving_agent),
            patch.object(AgentSettings, "load", classmethod(lambda cls: SETTINGS)),
        ):
            app = create_app()  # harness=None：走服务端真正的懒构建路径
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                first = await client.post("/chat/stream", json={"message": "第一轮：查 P90002"})
                conversation_id = sse_frames(first)[0]["conversation_id"]
                second = await client.post(
                    "/chat/stream",
                    json={"message": "第二轮：那他呢", "conversation_id": conversation_id},
                )
                return sse_frames(first), sse_frames(second), conversation_id

    first, second, conversation_id = run(two_requests())

    # agent 只构建一次，跨请求复用 —— 会话状态才有地方落脚。
    assert len(builds) == 1
    assert conversation_id and second[0]["conversation_id"] == conversation_id
    assert first[-1]["status"] == "completed" and second[-1]["status"] == "completed"

    # 第二次请求里，模型确实看到了第一轮的提问与回答。
    texts = [str(getattr(m, "content", "")) for m in model.seen[1]]
    assert any("第一轮：查 P90002" in t for t in texts)
    assert any("第一轮回答" in t for t in texts)


def test_http_new_session_does_not_leak_previous_conversation():
    from unittest.mock import patch

    from langgraph.checkpoint.memory import InMemorySaver

    import agent.api as api_module

    model = RecordingModel(
        responses=[AIMessage(content="甲会话回答"), AIMessage(content="乙会话回答")]
    )

    def fake_build_serving_agent(settings):
        return build_agent(
            settings,
            model=model,
            backend=DmoBackend(),
            facts=FactStore(CFG),
            checkpointer=InMemorySaver(),
        )

    async def two_sessions():
        with (
            patch.object(api_module, "build_serving_agent", fake_build_serving_agent),
            patch.object(AgentSettings, "load", classmethod(lambda cls: SETTINGS)),
        ):
            app = create_app()
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                a = await client.post("/chat/stream", json={"message": "甲会话的秘密编号"})
                b = await client.post("/chat/stream", json={"message": "乙会话第一问"})
                return sse_frames(a)[0]["conversation_id"], sse_frames(b)[0]["conversation_id"]

    conv_a, conv_b = run(two_sessions())

    assert conv_a != conv_b  # 不带 conversation_id 即开新会话
    assert all("甲会话的秘密编号" not in str(getattr(m, "content", "")) for m in model.seen[1])


def test_unknown_request_field_is_rejected_not_ignored():
    """拼错会话字段名必须报错。静默忽略会让客户端以为在续会话，实际每轮都是新会话。"""

    async def request():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(AgentHarness(EventGraph(), SETTINGS))),
            base_url="http://test",
        ) as client:
            stale = await client.post(
                "/chat/stream", json={"message": "x", "thread_id": "c-1"}
            )
            good = await client.post(
                "/chat/stream", json={"message": "x", "conversation_id": "c-1"}
            )
            return stale.status_code, good.status_code

    stale, good = run(request())
    assert stale == 422  # 旧字段名不再被接受
    assert good == 200


def test_prompt_does_not_forbid_using_earlier_turns():
    """提示词不能把多轮上下文掐死。

    「只依据本轮工具返回的事实回答」这句话曾经存在：即使会话历史完整进了上下文，
    它也禁止模型使用上一轮取回的事实，追问时模型会反过来要患者编号 ——
    传输层通了、策略层没通，表现就是「多轮对话没生效」，且极难定位。

    同时守住原有的证据纪律：不许拿模型知识顶替工具返回。
    """
    from agent.prompt import SYSTEM_PROMPT

    assert "只依据本轮" not in SYSTEM_PROMPT
    assert "先前轮次" in SYSTEM_PROMPT  # 明确允许沿用前几轮的工具事实
    assert "不得用模型知识、常识或推测补齐" in SYSTEM_PROMPT  # 证据纪律不放松
    assert "未调用工具不能声称已查库" in SYSTEM_PROMPT


def test_simulate_tool_posts_the_declared_body():
    """推演工具必须原样提交四个必填字段，并在 schema 层挡住残缺假设。

    服务端的 assume 是 dict[str, Any]，没有类型约束；约束只能由工具这一侧提供，
    否则模型只能靠试错吃 400。
    """
    from fastapi import FastAPI

    app = FastAPI()
    seen = {}

    @app.post("/patients/{pid}/simulate")
    def sim(pid: str, body: dict):
        seen["pid"] = pid
        seen["body"] = body
        return {"patientId": pid, "delta": []}

    tools = {t.name: t for t in build_tools(DmoBackend(app), FactStore(CFG))}
    tool = tools["simulate_patient_course"]

    one = {"term": "A1C", "value": 7.9, "unit": "percent", "date": "2026-02-20"}
    result = run(tool.ainvoke({"patient_id": "P90002", "assume": [one]}))

    assert seen["pid"] == "P90002"
    # 未开启的开关不进 body —— 服务端按缺省处理，不替它做决定。
    assert seen["body"] == {"assume": [one]}
    assert result["ok"] is True

    # 1..10 条写死在 schema 里：空假设等同重算基线，超量注入服务端会拒。
    assert tool.args["assume"]["minItems"] == 1
    assert tool.args["assume"]["maxItems"] == 10


def test_simulate_tool_rejects_incomplete_assumption():
    """缺单位或日期的假设不许发出去。服务端拒绝的理由是业务判断，不该靠它兜底。"""
    from fastapi import FastAPI

    app = FastAPI()
    called = []

    @app.post("/patients/{pid}/simulate")
    def sim(pid: str, body: dict):
        called.append(body)
        return {}

    tools = {t.name: t for t in build_tools(DmoBackend(app), FactStore(CFG))}
    with pytest.raises(ValidationError) as raised:
        run(
            tools["simulate_patient_course"].ainvoke(
                {"patient_id": "P90002", "assume": [{"term": "A1C", "value": 7.9}]}
            )
        )
    missing = {e["loc"][-1] for e in raised.value.errors()}
    assert {"unit", "date"} <= missing
    assert called == []  # 残缺请求根本没有发出


def test_treatment_assessment_tool_posts_pid_only():
    from fastapi import FastAPI

    app = FastAPI()
    seen = {}

    @app.post("/patients/{pid}/treatment-assessments")
    def assessment(pid: str):
        seen["pid"] = pid
        return {"report_id": "TA-test", "claims": []}

    tools = {t.name: t for t in build_tools(DmoBackend(app), FactStore(CFG))}
    result = run(tools["assess_patient_treatment"].ainvoke({"pid": "P90002"}))

    assert seen == {"pid": "P90002"}
    assert result["ok"] is True
    assert tools["assess_patient_treatment"].args == {"pid": {"title": "Pid", "type": "string"}}


def test_treatment_tool_preserves_claim_evidence_within_context_budget():
    from fastapi import FastAPI

    app = FastAPI()
    @app.post("/patients/{pid}/treatment-assessments")
    def assessment(pid: str):
        return {"report_id": "TA-test", "rendered_markdown": "x" * 25000,
                "mapped_entities": [{"duplicate": "x" * 25000}],
                "claims": [{"claim_id": "C1", "evidence_ids": ["E1"]}],
                "evidence": [{"evidence_id": "E1", "exact_quote": "preserve"},
                             {"evidence_id": "UNUSED"}]}

    result = run(DmoBackend(app).request("/patients/P1/treatment-assessments", body={}))
    assert result["ok"]
    assert result["data"]["claims"][0]["evidence_ids"] == ["E1"]
    assert result["data"]["evidence"] == [{"evidence_id": "E1", "exact_quote": "preserve"}]


def test_assessment_observer_keeps_full_trace_and_evidence_defaults_are_lossless():
    from fastapi import FastAPI
    app = FastAPI()
    evidence = [{"evidence_id": f"F{i}", "kind": "patient_fact", "value_trust": "verified",
                 "fact_origin": "demo-cohort", "value": i} for i in range(3)]
    report = {"execution_trace": {"steps": [{"key": "read"}]},
              "claims": [{"evidence_ids": ["F0", "F1", "F2"]}], "evidence": evidence}
    @app.post('/patients/{pid}/treatment-assessments')
    def assessment(pid: str):
        return report
    seen = []
    async def observe(value):
        seen.append(value)
    result = run(DmoBackend(app).request('/patients/P1/treatment-assessments', body={}, assessment_observer=observe))
    assert seen[0] == report
    data = result['data']
    assert 'execution_trace' not in data
    restored = [{**data['evidence_defaults_by_kind'].get(e['kind'], {}), **e} for e in data['evidence']]
    assert restored == evidence


def test_agent_stream_emits_assessment_report_before_compact_tool_result():
    from fastapi import FastAPI
    app = FastAPI()
    @app.post('/patients/{pid}/treatment-assessments')
    def assessment(pid: str):
        return {'report_id': 'TA1', 'claims': [], 'execution_trace': {'steps': [{'key': 'read'}]}}
    model = ScriptedModel(responses=[AIMessage(content='', tool_calls=[{
        'name': 'assess_patient_treatment', 'args': {'pid': 'P91001'}, 'id': 'a1', 'type': 'tool_call',
    }]), AIMessage(content='评估已完成。')])
    events = run(collect(AgentHarness(build_agent(SETTINGS, model=model, backend=DmoBackend(app), facts=FactStore(CFG)), SETTINGS)))
    report_event = next(e for e in events if e['type'] == 'assessment_report')
    end = next(e for e in events if e['type'] == 'tool_end')
    assert report_event['report']['execution_trace']['steps'][0]['key'] == 'read'
    assert report_event['seq'] < end['seq']
    assert 'execution_trace' not in end['result']['data']
    assert events[-1]['status'] == 'completed'


def test_prediction_demo_tool_calls_real_endpoint_and_streams_result():
    from fastapi import FastAPI

    app = FastAPI()
    received = []

    @app.post('/patients/{pid}/prediction-demo')
    def prediction(pid: str):
        received.append(pid)
        return {'predictions': [{'day': 7}, {'day': 14}, {'day': 28}]}

    model = ScriptedModel(responses=[
        AIMessage(content='', tool_calls=[{
            'name': 'run_prediction_demo', 'args': {'pid': 'P91001'},
            'id': 'prediction-1', 'type': 'tool_call',
        }]),
        AIMessage(content='预测演示已返回计算结果。'),
    ])
    harness = AgentHarness(build_agent(SETTINGS, model=model, backend=DmoBackend(app), facts=FactStore(CFG)), SETTINGS)

    async def request_demo():
        return [event async for event in harness.stream('运行 P91001 的预测演示')]

    events = run(request_demo())
    assert received == ['P91001']
    start = next(e for e in events if e['type'] == 'tool_start')
    end = next(e for e in events if e['type'] == 'tool_end')
    assert start['tool'] == 'run_prediction_demo'
    assert start['call_id'] == end['call_id']
    assert end['ok'] is True
    assert end['result']['data']['predictions'] == [{'day': 7}, {'day': 14}, {'day': 28}]


def test_model_selection_config_refresh_and_shared_credentials(monkeypatch):
    import agent.api as api_module
    from dataclasses import replace
    from agent.settings import AVAILABLE_MODELS

    configured = [replace(SETTINGS, model='qwen3.8-max')]
    builds = []
    monkeypatch.setattr(AgentSettings, 'load', classmethod(lambda cls: configured[0]))

    def build(settings):
        builds.append(settings)
        return build_agent(settings, model=ScriptedModel(responses=[AIMessage(content='ok')]),
                           backend=DmoBackend(), facts=FactStore(CFG))

    monkeypatch.setattr(api_module, 'build_serving_agent', build)

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url='http://test') as client:
            config = (await client.get('/chat/models')).json()
            assert config == {'models': list(AVAILABLE_MODELS), 'default_model': 'qwen3.8-max'}
            assert 'api_key' not in config and 'base_url' not in config
            for model in AVAILABLE_MODELS:
                response = await client.post('/chat/stream', json={'message': '你好', 'model': model})
                assert sse_frames(response)[0]['model'] == model
            await client.post('/chat/stream', json={'message': '你好', 'model': AVAILABLE_MODELS[0]})
            assert len(builds) == 3
            configured[0] = replace(configured[0], model='kimi-k3')
            assert (await client.get('/chat/models')).json()['default_model'] == 'kimi-k3'
            response = await client.post('/chat/stream', json={'message': '你好'})
            assert sse_frames(response)[0]['model'] == 'kimi-k3'
            invalid = await client.post('/chat/stream', json={'message': '你好', 'model': 'unknown'})
            assert invalid.status_code == 422
    run(exercise())
    assert all(s.api_key == SETTINGS.api_key and s.base_url == SETTINGS.base_url for s in builds)


@pytest.mark.parametrize("body", [
    {"code": 20012, "message": "Model does not exist. Please check it carefully."},
    {"error": {"code": "model_not_found", "message": "Unavailable model"}},
])
def test_missing_provider_model_has_actionable_safe_error(body):
    from agent.runtime import error_message

    class MissingModel(Exception):
        status_code = 400

    exc = MissingModel("private provider details")
    exc.body = body
    message = error_message(exc)
    assert "当前 API 服务商不支持所选模型" in message
    assert "OPENAI_BASE_URL" in message
    assert "private provider details" not in message



def test_bailian_glm_alias_and_product_activation_error():
    from agent.settings import resolve_model
    from agent.runtime import error_message
    assert resolve_model('zai-org/GLM-5.2', 'https://dashscope.aliyuncs.com/compatible-mode/v1') == 'glm-5.2'
    assert resolve_model('glm-5.2', 'https://api.siliconflow.cn/v1') == 'zai-org/GLM-5.2'
    assert resolve_model('kimi-k3', 'https://dashscope.aliyuncs.com/compatible-mode/v1') == 'kimi-k3'

    class NotActivated(Exception):
        status_code = 400
        body = {'code': 'invalid_parameter_error', 'message': 'The product is not activated, please confirm that you have activated products and try again after activation.'}

    assert '尚未开通' in error_message(NotActivated())
