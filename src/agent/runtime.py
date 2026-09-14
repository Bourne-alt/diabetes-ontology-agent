"""Model + tools + execution policy + observable events = the harness."""

import asyncio
import contextlib
import json
import re
from collections import OrderedDict
from collections.abc import AsyncIterator
from uuid import uuid4

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    TodoListMiddleware,
    ToolCallLimitMiddleware,
    wrap_tool_call,
)
from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.messages import ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from langsmith import tracing_context

from dmo.config import load

from .backend import DmoBackend
from .database import FactStore
from .prompt import SYSTEM_PROMPT
from .settings import AgentSettings
from .tools import build_tools


def public_text(content) -> str:
    """Only public text blocks. Provider reasoning/tool-call fragments stay private."""
    if isinstance(content, str):
        return content
    return "".join(
        block.get("text", "")
        for block in content or []
        if isinstance(block, dict) and block.get("type") == "text"
    )


def redact(value):
    if isinstance(value, dict):
        return {
            k: "[redacted]"
            if any(s in k.lower() for s in ("password", "api_key", "authorization", "dsn"))
            else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r"sk-[A-Za-z0-9_-]+", "[redacted]", value)
        return re.sub(r"(postgres(?:ql)?://)[^\s]+", r"\1[redacted]", value)
    return value


def error_message(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    if status == 402:
        return "模型服务账号余额不足（HTTP 402），请充值后重试。"
    if status in (401, 403):
        return "模型服务认证失败或无访问权限，请检查 OPENAI_API_KEY。"
    if status == 429:
        return "模型服务限流或额度不足，请稍后重试或检查配额。"
    if isinstance(exc, TimeoutError):
        return "本轮已达到执行时限，查询未完成。"
    return "本轮未完成：模型、数据服务不可用或已达到执行预算；请检查配置后重试。"


# 进程内会话上限。超出按最近最少使用逐出，避免长时间运行后无界增长。
# 会话只活在本进程内存里：重启即清空，多副本部署时同一会话不保证落到同一进程。
MAX_CONVERSATIONS = 32


def build_agent(
    settings: AgentSettings, *, model=None, backend=None, facts=None, checkpointer=None
):
    backend = backend or DmoBackend(max_result_chars=settings.max_result_chars)
    facts = facts or FactStore(load())

    @wrap_tool_call
    async def tool_boundary(request, handler):
        call = request.tool_call
        await adispatch_custom_event(
            "harness_tool_start",
            {
                "tool": call["name"],
                "call_id": call["id"],
                "arguments": redact(call["args"]),
            },
        )
        try:
            if (
                call["name"] == "write_todos"
                and len(json.dumps(call["args"], ensure_ascii=False)) > settings.max_result_chars
            ):
                raise ValueError("待办清单过长，请缩短任务描述。")
            result = await handler(request)
            if (
                isinstance(result, ToolMessage)
                and len(public_text(result.content)) > settings.max_result_chars
            ):
                result = ToolMessage(
                    content=json.dumps(
                        {
                            "ok": False,
                            "error": "result_too_large",
                            "hint": "请缩小查询范围或分页。",
                        },
                        ensure_ascii=False,
                    ),
                    tool_call_id=call["id"],
                    status="error",
                )
        except Exception as exc:  # noqa: BLE001 -- sanitize errors at the public boundary
            result = ToolMessage(
                content=json.dumps(
                    {
                        "ok": False,
                        "error": type(exc).__name__,
                        "hint": str(exc)[:400]
                        if type(exc) is ValueError
                        else "工具失败；检查 schema/参数或服务连通性，不是查无数据。",
                    },
                    ensure_ascii=False,
                ),
                tool_call_id=call["id"],
                status="error",
            )
        if isinstance(result, Command):
            # TodoListMiddleware returns a state update, not a ToolMessage.
            # Preserve the Command so LangGraph actually stores the todos.
            update = result.update or {}
            content = {"todos": update.get("todos", [])}
        else:
            content = result.content if isinstance(result, ToolMessage) else result
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except ValueError:
                pass
        failed = (
            getattr(result, "status", None) == "error"
            or isinstance(content, dict)
            and content.get("ok") is False
        )
        await adispatch_custom_event(
            "harness_tool_end",
            {
                "tool": call["name"],
                "call_id": call["id"],
                "ok": not failed,
                "result": redact(content),
            },
        )
        return result

    if model is None:
        model = ChatOpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            model=settings.model,
            streaming=True,
            timeout=settings.model_timeout,
            max_retries=1,
            max_tokens=4096,
        )
    return create_agent(
        model=model,
        tools=build_tools(backend, facts),
        system_prompt=SYSTEM_PROMPT,
        # 多轮上下文由 checkpointer 按 thread_id 持有：消息、工具结果与待办清单一起存，
        # 不在应用层另抄一份消息数组。默认不挂 —— 只有服务路径需要会话，见 build_serving_agent。
        checkpointer=checkpointer,
        middleware=[
            TodoListMiddleware(),
            ModelCallLimitMiddleware(run_limit=settings.max_model_calls, exit_behavior="error"),
            ToolCallLimitMiddleware(run_limit=settings.max_tool_calls, exit_behavior="error"),
            tool_boundary,
        ],
    )


def build_serving_agent(settings: AgentSettings):
    """HTTP 服务路径：挂进程内 checkpointer 以支持多轮会话。

    CLI 与测试走 build_agent（不挂 checkpointer），保持单轮、无隐式记忆。
    """
    return build_agent(settings, checkpointer=InMemorySaver())


class AgentHarness:
    """多轮会话按 conversation_id 隔离，状态存在 graph 的 checkpointer 里。

    同一会话内模型能看到之前几轮的消息与工具结果；不同会话之间不共享任何东西。
    未传 conversation_id 时每次生成新的，行为与单轮一致。调用预算按「轮」计，不按会话累计。

    对外一律叫 conversation_id；LangGraph 内部的键仍是 configurable.thread_id，
    那是框架契约，只在提交 config 时做一次映射。
    """

    def __init__(self, graph, settings: AgentSettings):
        self.graph = graph
        self.settings = settings
        self._conversations: OrderedDict[str, asyncio.Lock] = OrderedDict()

    def _touch(self, conversation_id: str) -> asyncio.Lock:
        lock = self._conversations.pop(conversation_id, None) or asyncio.Lock()
        self._conversations[conversation_id] = lock
        return lock

    async def _evict(self) -> None:
        checkpointer = getattr(self.graph, "checkpointer", None)
        while len(self._conversations) > MAX_CONVERSATIONS:
            old_id, old_lock = next(iter(self._conversations.items()))
            if old_lock.locked():
                break  # 正在跑的会话不动，下次再回收
            self._conversations.pop(old_id)
            if checkpointer is None:
                continue
            with contextlib.suppress(Exception):  # 回收失败不该影响本轮查询
                await checkpointer.adelete_thread(old_id)

    async def stream(
        self, message: str, conversation_id: str | None = None
    ) -> AsyncIterator[dict]:
        conversation_id = conversation_id or str(uuid4())
        run_id, seq = str(uuid4()), 0

        def event(kind, **data):
            nonlocal seq
            seq += 1
            return {"type": kind, "run_id": run_id, "seq": seq, **redact(data)}

        yield event(
            "run_start",
            message="开始查询",
            model=self.settings.model,
            conversation_id=conversation_id,
        )
        answer = ""
        lock = self._touch(conversation_id)
        await self._evict()
        try:
            # Keep patient traces local even when the host enables LangSmith globally.
            with tracing_context(enabled=False):
                # 同一会话串行执行：并发请求排队，等待时间一并计入本轮总时限。
                async with lock, asyncio.timeout(self.settings.run_timeout):
                    # 只提交新消息：checkpointer 会把它接到该 thread 已有的状态后面。
                    async for item in self.graph.astream_events(
                        {"messages": [{"role": "user", "content": message}]},
                        config={
                            "recursion_limit": 60,
                            # LangGraph 的键就叫 thread_id，对外的名字是 conversation_id。
                            "configurable": {"thread_id": conversation_id},
                        },
                        version="v2",
                    ):
                        kind, data = item["event"], item.get("data", {})
                        if kind == "on_chat_model_start":
                            yield event("model_start", message="正在选择查询或组织回答")
                        elif kind == "on_chat_model_stream":
                            text = public_text(data["chunk"].content)
                            if text:
                                yield event("text_delta", text=text)
                        elif kind == "on_chat_model_end":
                            output = data.get("output")
                            if output is not None and not getattr(output, "tool_calls", None):
                                answer = public_text(output.content)
                        elif kind == "on_chain_stream" and not item.get("parent_ids"):
                            # Root graph updates arrive after the tool Command is applied.
                            chunk = data.get("chunk", {})
                            if isinstance(chunk, dict):
                                for update in chunk.values():
                                    if isinstance(update, dict) and "todos" in update:
                                        yield event("todo_update", todos=update["todos"])
                        elif kind == "on_custom_event" and item["name"] in (
                            "harness_tool_start",
                            "harness_tool_end",
                        ):
                            yield event(item["name"].removeprefix("harness_"), **data)
            if not answer:
                raise RuntimeError("Agent completed without a final answer")
            yield event("answer", text=answer)
            yield event("done", status="completed")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 -- sanitize errors at the public boundary
            yield event(
                "error",
                code=type(exc).__name__,
                message=error_message(exc),
            )
            yield event("done", status="failed")
