"""Local SSE transport. Browser/CLI consume the same ordered event contract."""

import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .logs import get_logger, log_event, log_exception, setup_logging
from .runtime import AgentHarness, build_serving_agent
from .settings import AgentSettings

log = get_logger("api")

# 前端是 frontend/ 下的 Vite + React 工程，这里只托管它的构建产物 frontend/dist。
# 未构建（或装成包、目录缺失）时回落到包内单文件页面，服务本身照常可用。
# 开发期走 `npm run dev`，由 Vite 把 /chat/stream 代理到本服务，不经过这里。
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
PACKAGED_INDEX = Path(__file__).with_name("index.html")


def index_file() -> Path:
    built = FRONTEND_DIST / "index.html"
    return built if built.is_file() else PACKAGED_INDEX


class ChatRequest(BaseModel):
    # 拒绝未知字段：客户端拼错会话字段名时给 422，而不是静默开一个新会话、
    # 让多轮上下文无声丢失 —— 那种失败非常难查。
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=12000)
    # 会话标识。省略即开新会话，服务端生成并在 run_start 事件里回传。
    conversation_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")


def create_app(harness: AgentHarness | None = None):
    app = FastAPI(title="糖尿病本体 Agent", version="0.1.0")

    # 会话状态存在 harness 持有的 checkpointer 里，所以 harness 必须是进程级单例。
    # 早先这段建在请求处理函数内：conversation_id 每次都落到一个全新的 checkpointer 上，
    # 客户端带回来的会话永远是空的 —— 多轮上下文就是这么丢的。
    runtime_slot: dict[str, AgentHarness | None] = {"runtime": harness}
    build_lock = asyncio.Lock()

    async def get_runtime() -> AgentHarness:
        if runtime_slot["runtime"] is not None:
            return runtime_slot["runtime"]
        async with build_lock:
            if runtime_slot["runtime"] is None:
                try:
                    settings = AgentSettings.load()
                    built = AgentHarness(build_serving_agent(settings), settings)
                except Exception as exc:  # noqa: BLE001 -- do not expose configuration secrets
                    # `from None` 是刻意的：异常链里可能带着 DSN 与密钥，不能进 HTTP 响应。
                    # 代价是客户端只剩一句 503 —— 所以真因必须在这里落盘，否则无从查起。
                    log_exception(log, "runtime.build_failed", exc)
                    # 不缓存失败：配置修好后下一次请求应该能重新构建。
                    raise HTTPException(503, "Agent 初始化失败，请检查模型与数据库配置。") from None
                log_event(log, logging.INFO, "runtime.built", model=settings.model,
                          base_url=settings.base_url, run_timeout=settings.run_timeout)
                runtime_slot["runtime"] = built
        return runtime_slot["runtime"]

    @app.get("/", response_class=HTMLResponse)
    def index():
        return index_file().read_text(encoding="utf-8")

    @app.post("/chat/stream")
    async def chat(body: ChatRequest):
        if not body.message.strip():
            raise HTTPException(422, "message 不能为空白")
        runtime = await get_runtime()
        # 消息正文可能含患者姓名/ID，入口只记规模与是否续接已有会话。
        log_event(log, logging.INFO, "http.chat", message_chars=len(body.message),
                  resumed=body.conversation_id is not None)

        async def events():
            try:
                async for event in runtime.stream(body.message, body.conversation_id):
                    yield (
                        f"id: {event['seq']}\nevent: {event['type']}\ndata: "
                        + json.dumps(event, ensure_ascii=False, default=str)
                        + "\n\n"
                    )
            except asyncio.CancelledError:
                # 浏览器关页面/断网时 SSE 生成器被取消。不记的话，
                # 服务端只表现为「这次查询没有 done 事件」，看着像卡死。
                log_event(log, logging.WARNING, "http.chat_disconnected")
                raise

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store",
                "X-Accel-Buffering": "no",
            },
        )

    # The demo UI uses the exact DMO implementations, with no model call or seed writes.
    from dmo.api import prediction_demo, treatment_assessment, treatment_scenarios

    app.add_api_route("/demo/treatment-scenarios", treatment_scenarios, methods=["GET"])
    app.add_api_route("/patients/{pid}/treatment-assessments", treatment_assessment, methods=["POST"])
    app.add_api_route("/patients/{pid}/prediction-demo", prediction_demo, methods=["POST"])

    setup_logging()
    log_event(log, logging.INFO, "app.created", frontend="dist"
              if (FRONTEND_DIST / "index.html").is_file() else "packaged")

    # 挂在最后：上面的路由先匹配，剩下的路径（/assets/*）才落到构建产物。
    if (FRONTEND_DIST / "index.html").is_file():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST), name="frontend")

    return app


app = create_app()
