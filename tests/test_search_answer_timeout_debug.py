import asyncio
import json

import httpx
import pytest

from smart_search import cli, service

KEY = "debug-secret-123456"


@pytest.fixture(autouse=True)
def answer_config(monkeypatch):
    monkeypatch.setenv("SEARCH_ANSWER_API_URL", "https://relay.example/v1?token=query-secret")
    monkeypatch.setenv("SEARCH_ANSWER_API_KEY", KEY)
    monkeypatch.setenv("SEARCH_ANSWER_MODEL", "model")
    monkeypatch.setenv("SMART_SEARCH_RETRY_MAX_ATTEMPTS", "0")


def _transport(monkeypatch, handler):
    client_type = httpx.AsyncClient
    seen = {}

    def factory(**kwargs):
        seen.update(kwargs)
        return client_type(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr("smart_search.providers.responses.httpx.AsyncClient", factory)
    return seen


def _ok(request):
    body = {"type": "response.completed", "response": {"id": "resp_1", "model": "m", "status": "completed",
            "output": [{"type": "web_search_call"}, {"type": "message", "content": [{"type": "output_text", "text": "the answer"}]}]}}
    return httpx.Response(200, content=f"data: {json.dumps(body)}\n\n".encode())


def test_cli_timeout_defaults_to_unset():
    assert cli.build_parser().parse_args(["search", "answer", "q"]).timeout is None


@pytest.mark.asyncio
@pytest.mark.parametrize("configured,explicit,expected", [(None, None, 120.0), (45, None, 45.0), (45, 300.0, 300.0), (45, 10.0, 10.0)])
async def test_explicit_timeout_wins_over_configured(monkeypatch, configured, explicit, expected):
    if configured:
        monkeypatch.setenv("SMART_SEARCH_OPERATION_TIMEOUTS", json.dumps({"search.answer": configured}))
    seen = _transport(monkeypatch, _ok)

    result = await service.search_answer("q", timeout_seconds=explicit, debug=True)

    assert result["ok"] is True
    assert result["debug"]["timeout_budget"] == expected
    assert seen["timeout"].read == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [0, -1])
async def test_non_positive_timeout_is_rejected(value):
    result = await service.search_answer("q", timeout_seconds=value)
    assert result["error_type"] == "parameter_error"


@pytest.mark.asyncio
async def test_normal_output_has_no_debug_fields(monkeypatch):
    _transport(monkeypatch, _ok)

    result = await service.search_answer("q")

    assert set(result) == {"ok", "capability", "operation", "content", "sources", "elapsed_ms"}


def _assert_safe(result):
    dumped = json.dumps(result["debug"])
    for secret in (KEY, "query-secret", "relay.example", "private question", "the answer", "Traceback"):
        assert secret not in dumped


@pytest.mark.asyncio
async def test_debug_on_success(monkeypatch):
    _transport(monkeypatch, _ok)

    result = await service.search_answer("private question", debug=True)

    assert result["provider"] == "responses"
    assert result["provider_operation"] == "web answer"
    debug = result["debug"]
    assert debug["tools"] == ["web_search"]
    assert debug["tool_choice"] == "required"
    assert debug["response_status"] == "completed"
    assert debug["tool_usage"] == {"web_search_calls": 1}
    assert debug["attempts"][0]["status"] == "ok"
    _assert_safe(result)


@pytest.mark.asyncio
async def test_debug_on_http_error(monkeypatch):
    _transport(monkeypatch, lambda request: httpx.Response(401, content=f"bad key {KEY}".encode()))

    result = await service.search_answer("private question", debug=True)

    assert result["error_type"] == "auth_error"
    assert KEY not in result["error"]
    assert result["debug"]["attempts"][0]["http_status"] == 401
    assert result["debug"]["attempts"][0]["error_type"] == "auth_error"
    _assert_safe(result)


@pytest.mark.asyncio
async def test_debug_on_timeout_keeps_partial_observation(monkeypatch):
    class Hanging(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"type":"response.created","response":{"id":"resp_slow"}}\n\n'
            await asyncio.sleep(30)

    _transport(monkeypatch, lambda request: httpx.Response(200, stream=Hanging()))

    result = await service.search_answer("private question", timeout_seconds=0.2, debug=True)

    assert result["error_type"] == "timeout"
    assert result["debug"]["response_id"] == "resp_slow"
    assert result["debug"]["last_event_type"] == "response.created"
    assert result["debug"]["attempts"][0]["error_type"] == "cancelled"
    _assert_safe(result)
