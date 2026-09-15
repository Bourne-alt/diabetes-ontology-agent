"""日志的作用是在异常被脱敏吞掉之后仍能查到真因 —— 这几条把它钉死。

harness 有三处刻意的异常吞噬（工具边界、run 边界、服务初始化）。它们不该取消，
但一旦哪天有人顺手删掉 log_exception，排查能力会**静默**归零：测试照样全绿，
只是出问题时再也查不出原因。所以这些用例断言的是「traceback 到底在不在日志里」。
"""

import asyncio
import logging

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from agent import logs as logs_mod
from agent.database import FactStore
from agent.logs import setup_logging
from agent.runtime import AgentHarness, _shape, build_agent
from agent.settings import AgentSettings
from dmo.config import Config

SETTINGS = AgentSettings(api_key="sk-secret-key-0123456789")
CFG = Config(
    "postgresql://user:pw@unused/original", "postgresql://user:pw@unused/ontology",
    "http://unused", "dmo", 1,
)


class ScriptedModel(BaseChatModel):
    responses: list = Field(default_factory=list)
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


class ExplodingBackend:
    async def request(self, path, params=None, body=None, **kwargs):
        raise ConnectionRefusedError("GraphDB 在 localhost:7200 上拒绝连接")


@pytest.fixture
def agent_logs(caplog, monkeypatch):
    """捕获 agent.* 日志。setup_logging 关了 propagate，测试里临时打开。"""
    monkeypatch.delenv("AGENT_LOG_PAYLOAD", raising=False)
    monkeypatch.setenv("AGENT_LOG_LEVEL", "DEBUG")
    logger = setup_logging(force=True)
    logger.propagate = True
    caplog.set_level(logging.DEBUG, logger="agent")
    yield caplog
    logs_mod._configured = False


def run_with_failing_tool():
    model = ScriptedModel(responses=[
        AIMessage(content="", tool_calls=[{"name": "search_concepts",
                                           "args": {"q": "糖尿病视网膜病变"},
                                           "id": "call_1", "type": "tool_call"}]),
        AIMessage(content="查询未能完成。"),
    ])
    graph = build_agent(SETTINGS, model=model, backend=ExplodingBackend(), facts=FactStore(CFG))
    harness = AgentHarness(graph, SETTINGS)

    async def go():
        return [e async for e in harness.stream("这个患者的诊断依据是什么")]

    return asyncio.run(go())


def test_tool_failure_keeps_the_traceback_the_model_never_sees(agent_logs):
    """模型只收到 "工具失败…"；根因必须完整留在日志里，含调用栈。"""
    events = run_with_failing_tool()
    tool_end = next(e for e in events if e["type"] == "tool_end")
    assert tool_end["ok"] is False
    # 事件流里只有类型名，没有任何可定位的信息 —— 这正是需要日志的理由。
    assert "localhost:7200" not in str(tool_end)

    failures = [r for r in agent_logs.records if r.getMessage() == "tool.exception"]
    assert len(failures) == 1
    record = failures[0]
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None, "没有 exc_info 就没有 traceback，等于没查到"
    assert record.exc_info[0] is ConnectionRefusedError
    assert "localhost:7200" in agent_logs.text
    assert record.fields["tool"] == "search_concepts"


def test_log_and_sse_share_one_run_id(agent_logs):
    """用户报错时给出事件里的 run_id，必须能 grep 到服务端全过程。"""
    events = run_with_failing_tool()
    run_id = events[0]["run_id"]
    tagged = [r for r in agent_logs.records if getattr(r, "run_id", None) == run_id]
    assert {r.getMessage() for r in tagged} >= {"run.start", "tool.start", "tool.end", "run.end"}


def test_patient_data_stays_out_of_logs_by_default(agent_logs):
    """默认只记参数名与形状。患者问题、检验项名称都不该落盘。"""
    run_with_failing_tool()
    assert "糖尿病视网膜病变" not in agent_logs.text
    assert "这个患者的诊断依据是什么" not in agent_logs.text
    start = next(r for r in agent_logs.records if r.getMessage() == "tool.start")
    assert start.fields["arguments"] == ["q"]


def test_payload_mode_records_content_and_warns(monkeypatch, caplog, capsys):
    """显式开 AGENT_LOG_PAYLOAD 才记内容，且必须提示其中含患者数据。"""
    monkeypatch.setenv("AGENT_LOG_PAYLOAD", "1")
    monkeypatch.setenv("AGENT_LOG_LEVEL", "DEBUG")
    caplog.set_level(logging.DEBUG, logger="agent")
    logger = setup_logging(force=True)
    # 开关警告在 setup_logging 内部就发出，那时 propagate 还是 False（这是对的：
    # 不向 root 冒泡），所以从 stderr 上验它，不从 caplog。
    assert "患者数据" in capsys.readouterr().err
    logger.propagate = True
    try:
        run_with_failing_tool()
        start = next(r for r in caplog.records if r.getMessage() == "tool.start")
        assert start.fields["arguments"] == {"q": "糖尿病视网膜病变"}
    finally:
        logs_mod._configured = False


def test_secrets_never_reach_logs(agent_logs):
    run_with_failing_tool()
    assert "sk-secret-key-0123456789" not in agent_logs.text
    assert "postgresql://user:pw@" not in agent_logs.text


def test_shape_summarises_without_leaking_values():
    """_shape 要说清「拿到了什么规模的东西」，且不带出任何具体数值。"""
    payload = {"ok": True, "source": "/patients/P1/care-chain",
               "data": {"rowCount": 3, "rows": [{"a1c": 9.1, "patientid": "P90018"}] * 3}}
    shape = _shape(payload)
    assert shape["ok"] is True and shape["source"] == "/patients/P1/care-chain"
    assert "9.1" not in str(shape) and "P90018" not in str(shape)
    assert shape["data"]["rowCount"] == 3


def test_logging_failure_never_breaks_the_query(agent_logs):
    """观测坏掉可以，业务查询不能因此中断。"""
    broken = logging.getLogger("agent.broken")
    broken.handle = lambda record: (_ for _ in ()).throw(OSError("磁盘满"))
    logs_mod.log_event(broken, logging.INFO, "smoke", a=1)
    logs_mod.log_exception(broken, "smoke", ValueError("x"))
