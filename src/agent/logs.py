"""可定位问题的日志：一条 run_id 串起事件流、模型调用、工具、HTTP 与 SQL。

三条原则，顺序不能颠倒：

1. **异常必须带 traceback**。harness 在工具边界和 run 边界把异常转成给用户看的
   安全文案（见 runtime.error_message），那层转换之后原始异常就没了 —— 所以
   转换**之前**必须 logger.exception 一次。这是这个模块存在的首要理由。
2. **默认不记患者数据**。工具参数与返回值里全是 patientid、检验值、诊断结论。
   默认只记「形状」：工具名、耗时、行数、状态码、错误类型。要看内容显式开
   AGENT_LOG_PAYLOAD=1，且请写到 logs/（已在 .gitignore）。
3. **日志自身不许抛异常**。埋点包在 try 里，观测坏了也不能把查询带崩。

对外的 run_id 与 SSE 事件里的 run_id 是同一个：用户报「这次查询出错了」，
把事件里的 run_id 拿来 grep 日志就能还原服务端全过程。
"""

from __future__ import annotations

import contextvars
import json
import logging
import logging.handlers
import os
import time
from pathlib import Path

from dmo.config import ENV_FILE, _parse_env_file

LOGGER_ROOT = "agent"

# 当前 run 的关联标识。stream() 进入时设置，所有下游（工具、HTTP、SQL）自动带上。
# async 任务创建时会复制当前 context，所以 LangGraph 内部 task 里读得到。
_run_id: contextvars.ContextVar[str] = contextvars.ContextVar("agent_run_id", default="-")
_conversation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "agent_conversation_id", default="-"
)

_configured = False


def get_logger(name: str) -> logging.Logger:
    """取一个 agent.* 子 logger。首次取用时按环境完成一次配置。"""
    setup_logging()
    return logging.getLogger(f"{LOGGER_ROOT}.{name}")


def bind_run(run_id: str, conversation_id: str):
    """绑定本 run 的关联标识，返回可传给 unbind_run 的 token 对。"""
    return _run_id.set(run_id), _conversation_id.set(conversation_id)


def unbind_run(tokens) -> None:
    run_token, conversation_token = tokens
    _run_id.reset(run_token)
    _conversation_id.reset(conversation_token)


def current_run_id() -> str:
    return _run_id.get()


def log_payload_enabled() -> bool:
    """是否记录工具参数/返回、SQL 筛选值等可能含患者数据的内容。"""
    setup_logging()
    return _settings()["payload"]


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = _run_id.get()
        record.conversation_id = _conversation_id.get()
        return True


class _JsonFormatter(logging.Formatter):
    """一行一个 JSON 对象，给 jq / 日志采集用。"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "run_id": getattr(record, "run_id", "-"),
            "conversation_id": getattr(record, "conversation_id", "-"),
            "message": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if extra:
            payload["fields"] = extra
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class _TextFormatter(logging.Formatter):
    """人读格式：时间 级别 logger [run=... conv=...] 消息 key=value..."""

    def __init__(self):
        super().__init__(
            "%(asctime)s %(levelname)-5s %(name)-16s [run=%(run_id)s conv=%(conversation_id)s] "
            "%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        extra = getattr(record, "fields", None)
        if extra:
            rendered = " ".join(
                f"{k}={json.dumps(v, ensure_ascii=False, default=str)}"
                if isinstance(v, (dict, list))
                else f"{k}={v}"
                for k, v in extra.items()
            )
            record = logging.makeLogRecord(record.__dict__)
            record.msg = f"{record.getMessage()} {rendered}"
            record.args = ()
        return super().format(record)


def _env(name: str, default: str) -> str:
    # 环境变量优先于 .env，与 dmo.config 的约定一致。
    value = os.environ.get(name)
    if value is None:
        try:
            value = _parse_env_file(ENV_FILE).get(name)
        except OSError:
            value = None
    return default if value is None or value == "" else value


def _settings() -> dict:
    return {
        "level": _env("AGENT_LOG_LEVEL", "INFO").upper(),
        "file": _env("AGENT_LOG_FILE", ""),
        "format": _env("AGENT_LOG_FORMAT", "text").lower(),
        "payload": _env("AGENT_LOG_PAYLOAD", "0").lower() in ("1", "true", "yes", "on"),
    }


def setup_logging(force: bool = False) -> logging.Logger:
    """配置 agent.* logger 树。重复调用无副作用；force=True 用于改环境后重配。

    只碰 `agent` 这一棵子树，不动 root —— 库使用者的日志配置归他们自己管。
    """
    global _configured
    logger = logging.getLogger(LOGGER_ROOT)
    if _configured and not force:
        return logger

    cfg = _settings()
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = _JsonFormatter() if cfg["format"] == "json" else _TextFormatter()
    context_filter = _ContextFilter()

    stream_handler = logging.StreamHandler()  # stderr：不污染 CLI 的 stdout 事件流
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(context_filter)
    logger.addHandler(stream_handler)

    if cfg["file"]:
        try:
            path = Path(cfg["file"]).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            # 轮转上限 10MB × 5：日志里可能有患者数据，不让它无界堆积。
            file_handler = logging.handlers.RotatingFileHandler(
                path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            file_handler.addFilter(context_filter)
            logger.addHandler(file_handler)
        except OSError as exc:
            logger.warning("日志文件打不开，仅输出到 stderr：%s", exc)

    logger.setLevel(getattr(logging, cfg["level"], logging.INFO))
    logger.propagate = False  # 不向 root 冒泡，避免宿主重复打印
    _configured = True
    if cfg["payload"]:
        logger.warning(
            "AGENT_LOG_PAYLOAD=1：工具参数与返回将被完整记录，其中含患者数据。"
            "仅用于本地排查，别在生产或共享环境开。"
        )
    return logger


def log_event(logger: logging.Logger, level: int, event: str, **fields) -> None:
    """记一条带结构化字段的事件。event 用点号分层（tool.start / sql.query），便于 grep。

    日志失败永远不向上抛 —— 观测坏了不能把业务带崩。
    """
    try:
        if logger.isEnabledFor(level):
            logger.log(level, event, extra={"fields": {k: v for k, v in fields.items()
                                                       if v is not None}})
    except Exception:  # noqa: BLE001,S110 -- 见下
        # 这里刻意 pass：日志失败时再 log 一次极可能二次失败（坏掉的往往就是 handler
        # 本身，比如磁盘满）。观测挂了可以，业务查询不能因此中断。
        pass


def log_exception(logger: logging.Logger, event: str, exc: BaseException, **fields) -> None:
    """记一条带完整 traceback 的异常。

    在把异常转成给用户看的安全文案**之前**调用 —— 转换之后原始异常就没了。
    """
    try:
        logger.error(
            event,
            exc_info=exc,
            extra={"fields": {"error": type(exc).__name__,
                              **{k: v for k, v in fields.items() if v is not None}}},
        )
    except Exception:  # noqa: BLE001,S110 -- 见下
        # 这里刻意 pass：日志失败时再 log 一次极可能二次失败（坏掉的往往就是 handler
        # 本身，比如磁盘满）。观测挂了可以，业务查询不能因此中断。
        pass


class timer:
    """`with timer() as t:` → t.ms 为经过的毫秒数（整数）。"""

    __slots__ = ("_start", "ms")

    def __enter__(self):
        self._start = time.perf_counter()
        self.ms = 0
        return self

    def __exit__(self, *exc):
        self.ms = int((time.perf_counter() - self._start) * 1000)
        return False
