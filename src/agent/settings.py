"""Environment-only credentials; no secret values in repr or error events."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dmo.config import ENV_FILE, _get, _parse_env_file

from .logs import get_logger, log_event

AVAILABLE_MODELS = ("qwen3.8-max", "kimi-k3", "zai-org/GLM-5.2")

def resolve_model(model: str, base_url: str) -> str:
    host = urlsplit(base_url).hostname or ""
    if host == "api.siliconflow.cn" and model.lower() == "glm-5.2":
        return "zai-org/GLM-5.2"
    if (host == "dashscope.aliyuncs.com" or host.endswith(".aliyuncs.com") and host.startswith("dashscope")) and model == "zai-org/GLM-5.2":
        return "glm-5.2"
    return model


log = get_logger("settings")


@dataclass(frozen=True)
class AgentSettings:
    api_key: str = field(repr=False)
    base_url: str = "https://api.siliconflow.cn/v1"
    model: str = "glm-5.2"
    model_timeout: float = 60
    run_timeout: float = 180
    max_model_calls: int = 30
    max_tool_calls: int = 30
    max_result_chars: int = 24000

    @classmethod
    def load(cls, env_file: Path = ENV_FILE):
        env = _parse_env_file(env_file)

        def get(name, default):
            return _get(env, name, default=str(default))

        key = get("OPENAI_API_KEY", "")
        if not key:
            raise ValueError("缺少 OPENAI_API_KEY，请在环境或 .env 中配置。")
        base_url = get("OPENAI_BASE_URL", cls.base_url).rstrip("/")
        model = get("OPENAI_MODEL_TEXT", cls.model)
        model = resolve_model(model, base_url)
        settings = cls(
            api_key=key,
            base_url=base_url,
            model=model,
            model_timeout=float(get("AGENT_MODEL_TIMEOUT", 60)),
            run_timeout=float(get("AGENT_RUN_TIMEOUT", 180)),
        )
        # 「连的是哪个端点、哪个模型、密钥是不是另一个」是排查第一问。
        # 只记密钥长度与后 4 位 —— 足以判断是否拿错 key，又不泄露密钥本身。
        log_event(
            log,
            logging.INFO,
            "settings.loaded",
            base_url=settings.base_url,
            model=settings.model,
            api_key_hint=f"len={len(key)} …{key[-4:]}" if len(key) > 8 else "len<=8",
            env_file=str(env_file),
            model_timeout=settings.model_timeout,
            run_timeout=settings.run_timeout,
        )
        return settings
