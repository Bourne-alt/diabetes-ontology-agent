"""Reuse the actual DMO API in-process, including its validation and graph guards."""

import asyncio
import json
import logging

import httpx

from .logs import get_logger, log_event, log_exception, timer

log = get_logger("backend")


class DmoBackend:
    def __init__(self, app=None, max_result_chars: int = 24000):
        if app is None:
            from dmo.api import app
        self.app = app
        self.max_result_chars = max_result_chars

    async def request(self, path: str, params=None, body=None, *, assessment_observer=None):
        # The tools supply fixed paths only. No arbitrary URL/HTTP tool is exposed.
        method = "GET" if body is None else "POST"
        # 查询参数里有患者 ID 与检索词，只记参数名。
        log_event(log, logging.DEBUG, "dmo.request", method=method, path=path,
                  params=sorted(params) if params else None)
        elapsed = timer()
        try:
            with elapsed:
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=self.app), base_url="http://dmo.internal"
                ) as client:
                    async with asyncio.timeout(40):
                        if body is None:
                            response = await client.get(
                                path,
                                params={
                                    k: v for k, v in (params or {}).items() if v is not None
                                },
                            )
                        else:
                            response = await client.post(path, json=body)
        except Exception as exc:  # 记下真因后原样上抛，不改变原有的失败行为
            # 40s 超时、ASGI 内部崩溃都走这里。上层只会看到一个异常类型名。
            log_exception(log, "dmo.transport_error", exc, method=method, path=path,
                          elapsed_ms=elapsed.ms)
            raise
        log_event(
            log,
            logging.WARNING if response.status_code >= 400 else logging.INFO,
            "dmo.response",
            method=method,
            path=path,
            status=response.status_code,
            elapsed_ms=elapsed.ms,
            bytes=len(response.content),
        )
        if response.status_code >= 500:
            # RuntimeError 之后正文就没了 —— DMO 内部 500 的真因只有这里能看到。
            log_event(log, logging.ERROR, "dmo.server_error", method=method, path=path,
                      status=response.status_code, body=response.text[:1000])
            raise RuntimeError("DMO 依赖暂不可用")
        try:
            payload = response.json()
        except ValueError as exc:
            log_exception(log, "dmo.decode_error", exc, method=method, path=path,
                          status=response.status_code, body=response.text[:500])
            raise
        if response.is_success and path.endswith('/treatment-assessments'):
            if assessment_observer is not None:
                await assessment_observer(payload)
            # The HTTP report includes the same facts in Markdown, mapped entities,
            # claims and evidence. Keep the complete claims and their supporting
            # evidence for the agent, without sending duplicate representations.
            payload = dict(payload)
            payload.pop('rendered_markdown', None)
            payload.pop('mapped_entities', None)
            payload.pop('execution_trace', None)
            payload['monitoring'] = [c['claim_id'] for c in payload.get('monitoring', [])]
            payload['unresolved_questions'] = [c['claim_id'] for c in payload.get('unresolved_questions', [])]
            payload['domains'] = [{k: v for k, v in d.items() if k != 'claim_ids'}
                                  for d in payload.get('domains', [])]
            referenced = {ref for claim in payload.get('claims', [])
                          for ref in claim.get('evidence_ids', [])}
            payload['evidence'] = [item for item in payload.get('evidence', [])
                                   if item.get('evidence_id') in referenced]
            # Null optional fields convey no additional facts; never truncate
            # statements, missing premises or verbatim supporting evidence.
            def omit_nulls(value):
                if isinstance(value, dict):
                    return {k: omit_nulls(v) for k, v in value.items() if v is not None}
                if isinstance(value, list):
                    return [omit_nulls(v) for v in value]
                return value
            payload = omit_nulls(payload)
            payload['evidence_defaults_by_kind'] = {}
            for kind in ('patient_fact', 'knowledge'):
                facts = [e for e in payload['evidence'] if e.get('kind') == kind]
                if len(facts) > 1:
                    shared = {k: v for k, v in facts[0].items()
                              if k not in ('evidence_id', 'kind') and all(e.get(k) == v for e in facts)}
                    payload['evidence_defaults_by_kind'][kind] = shared
                    for fact in facts:
                        for key in shared:
                            fact.pop(key)
            payload['evidence_format'] = 'Merge evidence_defaults_by_kind[kind] into each evidence; per-item values override defaults. Monitoring/unresolved_questions contain claim IDs.'
        result = {"ok": response.is_success, "source": path, "data": payload}
        size = len(json.dumps(result, ensure_ascii=False, default=str))
        if size > self.max_result_chars:
            log_event(log, logging.WARNING, "dmo.result_too_large", method=method, path=path,
                      chars=size, budget=self.max_result_chars)
            return {
                "ok": False,
                "error": "result_too_large",
                "source": path,
                "hint": "返回超出上下文预算，请缩小检索条件、limit 或使用单项端点。",
            }
        return result
