"""Reuse the actual DMO API in-process, including its validation and graph guards."""

import asyncio
import json

import httpx


class DmoBackend:
    def __init__(self, app=None, max_result_chars: int = 24000):
        if app is None:
            from dmo.api import app
        self.app = app
        self.max_result_chars = max_result_chars

    async def request(self, path: str, params=None, body=None):
        # The tools supply fixed paths only. No arbitrary URL/HTTP tool is exposed.
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://dmo.internal"
        ) as client:
            async with asyncio.timeout(40):
                if body is None:
                    response = await client.get(
                        path, params={k: v for k, v in (params or {}).items() if v is not None}
                    )
                else:
                    response = await client.post(path, json=body)
        if response.status_code >= 500:
            raise RuntimeError("DMO 依赖暂不可用")
        payload = response.json()
        if len(json.dumps(payload, ensure_ascii=False, default=str)) > self.max_result_chars:
            return {
                "ok": False,
                "error": "result_too_large",
                "source": path,
                "hint": "返回超出上下文预算，请缩小检索条件、limit 或使用单项端点。",
            }
        return {"ok": response.is_success, "source": path, "data": payload}
