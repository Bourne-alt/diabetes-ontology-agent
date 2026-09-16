"""Offline failure injection for GraphDB transport and the in-process agent API."""

import asyncio
from unittest.mock import Mock

import httpx
import pytest

from agent.backend import DmoBackend
from dmo.api import app
from dmo.graph import explore
from dmo.graph.client import GraphDBError, _http


@pytest.mark.parametrize("failure", [502, 503, 504, _http.GraphDBTransportError("reset")])
def test_read_query_recovers_from_transient_failure(monkeypatch, failure):
    responses = [failure if isinstance(failure, BaseException) else (failure, ""), (200, "ok")]
    request = Mock(side_effect=responses)
    monkeypatch.setattr(_http, "request", request)
    monkeypatch.setattr(_http.time, "sleep", Mock())
    assert _http.sparql("http://graph", "dmo", "ASK {}", timeout=30) == "ok"
    assert request.call_count == 2


def test_persistent_failure_stops_after_three_attempts(monkeypatch):
    request = Mock(return_value=(502, ""))
    monkeypatch.setattr(_http, "request", request)
    monkeypatch.setattr(_http.time, "sleep", Mock())
    with pytest.raises(SystemExit, match="HTTP 502"):
        _http.sparql("http://graph", "dmo", "ASK {}")
    assert request.call_count == 3


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_permanent_errors_are_not_retried(monkeypatch, status):
    request = Mock(return_value=(status, "bad request"))
    monkeypatch.setattr(_http, "request", request)
    with pytest.raises(SystemExit, match=f"HTTP {status}"):
        _http.sparql("http://graph", "dmo", "ASK {}")
    assert request.call_count == 1


def test_retry_does_not_restart_timeout_budget(monkeypatch):
    clock = [0.0]
    timeouts = []
    def request(*args, timeout, **kwargs):
        timeouts.append(timeout)
        clock[0] += 15
        return 502, ""
    monkeypatch.setattr(_http, "request", request)
    monkeypatch.setattr(_http.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(_http.time, "sleep", lambda delay: clock.__setitem__(0, clock[0] + delay))
    with pytest.raises(SystemExit, match="HTTP 502"):
        _http.sparql("http://graph", "dmo", "ASK {}", timeout=30)
    assert timeouts == [30, 14.75]


def test_graph_requests_ignore_system_proxy(monkeypatch):
    monkeypatch.setenv("http_proxy", "http://bad-proxy:7897")
    response = Mock(status=200)
    response.read.return_value = b"ok"
    opener = Mock()
    opener.open.return_value.__enter__ = Mock(return_value=response)
    opener.open.return_value.__exit__ = Mock(return_value=False)
    build = Mock(return_value=opener)
    monkeypatch.setattr(_http.urllib.request, "build_opener", build)
    assert _http.request("GET", "http://graph:7200") == (200, "ok")
    assert build.call_args.args[0].proxies == {}
    assert opener.open.call_args.args[0].full_url == "http://graph:7200"


def test_graph_writes_are_not_retried(monkeypatch):
    request = Mock(return_value=(502, ""))
    monkeypatch.setattr(_http, "request", request)
    with pytest.raises(SystemExit, match="HTTP 502"):
        _http.put_graph("http://graph", "dmo", "urn:test", "")
    assert request.call_count == 1


def test_graphdb_failure_reaches_agent_as_structured_error(monkeypatch):
    monkeypatch.setattr(explore, "node", Mock(side_effect=GraphDBError("SPARQL 失败 HTTP 502")))
    async def check():
        # Keep raise_app_exceptions=True: a generic Exception handler used to rethrow here.
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/graph/node", params={"iri": "https://example.org/dmo#test"})
        assert response.status_code == 503
        assert response.json()["code"] == "graphdb_unavailable"
        result = await DmoBackend(app=app).request("/graph/node", {"iri": "https://example.org/dmo#test"})
        assert result["ok"] is False
        assert result["error"] == "graphdb_unavailable"
        assert "不表示没有" in result["hint"]
    asyncio.run(check())
