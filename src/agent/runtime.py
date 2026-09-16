"""Model + tools + execution policy + observable events = the harness."""

import asyncio
import contextlib
import json
import logging
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
from .logs import (
    bind_run,
    get_logger,
    log_event,
    log_exception,
    log_payload_enabled,
    timer,
    unbind_run,
)
from .prompt import SYSTEM_PROMPT
from .settings import AgentSettings
from .tools import build_tools

log = get_logger("runtime")


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


def _shape(value, _depth: int = 0):
    """返回值的「形状」：够判断是空结果、报错还是拿到了数据，但不含任何患者内容。

    默认日志用它代替真实返回。查问题时九成场景只需要知道
    「ok=true、rowCount=0」还是「ok=false、error=xxx」—— 不需要看到具体检验值。
    """
    if isinstance(value, dict):
        if _depth >= 2:
            return f"<dict:{len(value)}>"
        keep = ("ok", "error", "source", "rowCount", "hasMore", "count", "total", "database",
                "table", "status")
        shape = {k: value[k] for k in keep if k in value}
        for key, item in value.items():
            if key not in shape and isinstance(item, (dict, list)):
                shape[key] = _shape(item, _depth + 1)
        return shape or f"<dict:{len(value)}>"
    if isinstance(value, (list, tuple)):
        return f"<list:{len(value)}>"
    if isinstance(value, str):
        return f"<str:{len(value)}>"
    return value


def error_message(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None)
    error = body.get("error", body) if isinstance(body, dict) else {}
    code = error.get("code") if isinstance(error, dict) else None
    if status in (400, 404) and (
        str(code) in {"20012", "model_not_found"}
        or "model does not exist" in str(exc).lower()
        or "model_not_found" in str(exc).lower()
    ):
        return (
            "当前 API 服务商不支持所选模型，或此账号未获该模型访问权限。"
            "请核对该服务商的模型 ID、OPENAI_BASE_URL 和对应的 OPENAI_API_KEY；"
            "其他平台文档中的模型名称不能直接用于当前服务。"
        )
    if status == 400 and isinstance(error, dict) and "product is not activated" in str(error.get("message", "")).lower():
        return "当前百炼账号尚未开通所选模型。请在百炼控制台开通该模型服务后重试，或选择其他已开通的模型。"
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
        arguments = redact(call["args"])
        await adispatch_custom_event(
            "harness_tool_start",
            {
                "tool": call["name"],
                "call_id": call["id"],
                "arguments": arguments,
            },
        )
        # 参数里有 patientid、假设检验值等患者数据，默认只记「有哪些参数名」。
        log_event(
            log,
            logging.INFO,
            "tool.start",
            tool=call["name"],
            call_id=call["id"],
            arguments=arguments if log_payload_enabled() else sorted(call["args"]),
        )
        elapsed = timer()
        try:
            elapsed.__enter__()
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
            elapsed.__exit__(None, None, None)
            # 下面这个 ToolMessage 只留类型名和截断 hint，原始异常到此为止 ——
            # 所以在转换**之前**把完整 traceback 落到日志，这是工具排错的唯一入口。
            log_exception(
                log,
                "tool.exception",
                exc,
                tool=call["name"],
                call_id=call["id"],
                elapsed_ms=elapsed.ms,
                detail=str(exc)[:400],
            )
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
        else:
            elapsed.__exit__(None, None, None)
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
        log_event(
            log,
            logging.WARNING if failed else logging.INFO,
            "tool.end",
            tool=call["name"],
            call_id=call["id"],
            ok=not failed,
            elapsed_ms=elapsed.ms,
            # 失败时 content 是我们自己造的安全错误对象，不含患者数据，照常记。
            result=redact(content) if (failed or log_payload_enabled()) else None,
            result_shape=None if (failed or log_payload_enabled()) else _shape(content),
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
        # 日志与 SSE 事件共用同一个 run_id：用户报错时把事件里的 run_id 拿来
        # grep 日志，就能还原这一轮的服务端全过程。
        tokens = bind_run(run_id, conversation_id)
        run_timer = timer()
        run_timer.__enter__()
        model_calls, tool_calls = 0, 0

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
        log_event(
            log,
            logging.INFO,
            "run.start",
            model=self.settings.model,
            message_chars=len(message),
            # 用户问题本身可能含患者姓名/ID，默认不进日志。
            message=message if log_payload_enabled() else None,
            new_conversation=conversation_id not in self._conversations,
            live_conversations=len(self._conversations),
        )
        answer = ""
        completed_explanations = []
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
                            # Middleware nodes also consume steps; allow the model budget to finish.
                            "recursion_limit": 200,
                            # LangGraph 的键就叫 thread_id，对外的名字是 conversation_id。
                            "configurable": {"thread_id": conversation_id},
                        },
                        version="v2",
                    ):
                        kind, data = item["event"], item.get("data", {})
                        if kind == "on_chat_model_start":
                            model_calls += 1
                            log_event(
                                log,
                                logging.DEBUG,
                                "model.start",
                                call_no=model_calls,
                                budget=self.settings.max_model_calls,
                            )
                            yield event("model_start", message="正在选择查询或组织回答")
                        elif kind == "on_chat_model_stream":
                            text = public_text(data["chunk"].content)
                            if text:
                                yield event("text_delta", text=text)
                        elif kind == "on_chat_model_end":
                            output = data.get("output")
                            requested = getattr(output, "tool_calls", None) or []
                            tool_calls += len(requested)
                            log_event(
                                log,
                                logging.DEBUG,
                                "model.end",
                                call_no=model_calls,
                                # 模型选了哪些工具是纯控制流信息，不含患者数据。
                                tool_calls=[c.get("name") for c in requested] or None,
                                finish_reason=(getattr(output, "response_metadata", None) or {}).get(
                                    "finish_reason"
                                ),
                                usage=getattr(output, "usage_metadata", None),
                            )
                            if output is not None and not requested:
                                answer = public_text(output.content)
                            elif output is not None and requested and all(
                                c.get("name") == "write_todos"
                                and c.get("args", {}).get("todos")
                                and all(t.get("status") == "completed" for t in c["args"]["todos"])
                                for c in requested
                            ):
                                explanation = public_text(output.content)
                                if explanation and explanation not in completed_explanations:
                                    completed_explanations.append(explanation)
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
                            "harness_assessment_report",
                        ):
                            yield event(item["name"].removeprefix("harness_"), **data)
            if not answer:
                raise RuntimeError("Agent completed without a final answer")
            answer = "\n\n".join([text for text in completed_explanations if text != answer] + [answer])
            yield event("answer", text=answer)
            run_timer.__exit__(None, None, None)
            log_event(
                log,
                logging.INFO,
                "run.end",
                status="completed",
                elapsed_ms=run_timer.ms,
                model_calls=model_calls,
                tool_calls=tool_calls,
                events=seq,
                answer_chars=len(answer),
            )
            yield event("done", status="completed")
        except asyncio.CancelledError:
            run_timer.__exit__(None, None, None)
            log_event(
                log,
                logging.WARNING,
                "run.cancelled",
                elapsed_ms=run_timer.ms,
                model_calls=model_calls,
                tool_calls=tool_calls,
            )
            raise
        except Exception as exc:  # noqa: BLE001 -- sanitize errors at the public boundary
            run_timer.__exit__(None, None, None)
            # error_message() 会把任何异常压成几句固定文案，用户和事件流都看不到真因；
            # 唯一能查的地方就是这里的 traceback。
            log_exception(
                log,
                "run.exception",
                exc,
                elapsed_ms=run_timer.ms,
                model_calls=model_calls,
                tool_calls=tool_calls,
                status_code=getattr(exc, "status_code", None),
                detail=str(exc)[:500],
                user_message=error_message(exc),
            )
            yield event(
                "error",
                code=type(exc).__name__,
                message=error_message(exc),
            )
            yield event("done", status="failed")
        finally:
            unbind_run(tokens)
