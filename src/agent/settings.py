"""Environment-only credentials; no secret values in repr or error events."""

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dmo.config import ENV_FILE, _get, _parse_env_file


@dataclass(frozen=True)
class AgentSettings:
    api_key: str = field(repr=False)
    base_url: str = "https://api.siliconflow.cn/v1"
    model: str = "glm-5.2"
    model_timeout: float = 60
    run_timeout: float = 180
    max_model_calls: int = 12
    max_tool_calls: int = 24
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
        # SiliconFlow's /models advertises the qualified ID, not the short alias.
        if urlsplit(base_url).hostname == "api.siliconflow.cn" and model.lower() == "glm-5.2":
            model = "zai-org/GLM-5.2"
        return cls(
            api_key=key,
            base_url=base_url,
            model=model,
            model_timeout=float(get("AGENT_MODEL_TIMEOUT", 60)),
            run_timeout=float(get("AGENT_RUN_TIMEOUT", 180)),
        )
