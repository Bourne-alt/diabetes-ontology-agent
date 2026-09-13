import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from ..config import _parse_env_file

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class ModelSettings:
    api_key: str = field(repr=False, default="")
    base_url: str = "https://api.siliconflow.cn/v1"
    model: str = "glm-5.2"
    timeout: float = 45.0

    @classmethod
    def load(cls):
        # Dedicated file and overrides: do not repurpose the extraction service's .env.
        env = _parse_env_file(ROOT / ".env.assessment")
        return cls(
            api_key=os.environ.get("DMO_ASSESSMENT_API_KEY", env.get("OPENAI_API_KEY", "")),
            base_url=os.environ.get(
                "DMO_ASSESSMENT_BASE_URL",
                env.get("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1"),
            ).rstrip("/"),
            model=os.environ.get("DMO_ASSESSMENT_MODEL", env.get("OPENAI_MODEL_TEXT", "glm-5.2")),
        )

    def valid(self):
        parts = urlsplit(self.base_url)
        return bool(
            self.api_key
            and self.model
            and parts.scheme == "https"
            and parts.hostname
            and not parts.username
            and not parts.password
            and not parts.query
            and not parts.fragment
        )
