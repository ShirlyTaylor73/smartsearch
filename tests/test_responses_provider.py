import asyncio
import json

import httpx
import pytest

from smart_search.providers.responses import ResponsesError, ResponsesSearchProvider


def _sse(*events) -> bytes:
    return "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events).encode()


def _message(text, annotations=()):
    return {"type": "message", "content": [{"type": "output_text", "text": text, "annotations": list(annotations)}]}


def _citation(url, title="1"):
    return {"type": "url_citation", "url": url, "title": title}


def _completed(output, **extra):
    response = {"id": "resp_1", "model": "model-build", "status": "completed", "output": output, **extra}
    return {"type": "response.completed", "response": response}


def _install(monkeypatch, handler):
    client_type = httpx.AsyncClient
    seen = {"requests": [], "client_kwargs": []}

    def record(request):
        seen["requests"].append(request)
        return handler(request, len(seen["requests"]))

    def factory(**kwargs):
        seen["client_kwargs"].append(kwargs)
        return client_type(transport=httpx.MockTransport(record), **kwargs)

    monkeypatch.setattr("smart_search.providers.responses.httpx.AsyncClient", factory)
    monkeypatch.setenv("SMART_SEARCH_RETRY_MULTIPLIER", "0")
    return seen


def _provider(**kwargs):
    kwargs.setdefault("tools", ["web_search", "x_search"])
    return ResponsesSearchProvider("https://relay.example/v1/", "secret-key", "test-model", **kwargs)


@pytest.mark.asyncio
async def test_request_always_streams_with_required_tools(monkeypatch):
    seen = _install(monkeypatch, lambda request, n: httpx.Response(200, content=_sse(_completed([_message("ok")]))))
    await _provider(timeout=300.0).search("What is new?")

    request = seen["requests"][0]
    assert str(request.url) == "https://relay.example/v1/responses"
    assert request.headers["authorization"] == "Bearer secret-key"
    assert request.headers["accept"] == "text/event-stream"
    payload = json.loads(request.content)
    assert payload["model"] == "test-model"
    assert payload["instructions"]
    assert payload["input"][0]["role"] == "user"
    assert "What is new?" in payload["input"][0]["content"]
    assert "[Current Time Context]" in payload["input"][0]["content"]
    assert payload["tools"] == [{"type": "web_search"}, {"type": "x_search"}]
    assert payload["tool_choice"] == "required"
    assert payload["stream"] is True
    assert seen["client_kwargs"][0]["timeout"].read == 300.0


@pytest.mark.asyncio
async def test_completed_output_is_the_only_content_source(monkeypatch):
    answer = "Answer [[1]](https://example.com/a)\n\n- [Example](https://example.com/tail)"
    events = [
        {"type": "response.created", "response": {"id": "resp_1"}},
        {"type": "response.output_text.delta", "delta": "partial text that must not be used"},
        {"type": "response.unknown_future_event"},
        _completed(
            [
                {"type": "reasoning"},
                {"type": "web_search_call", "status": "completed"},
                _message(answer, [_citation("https://example.com/a"), _citation("https://example.com/a", "dup")]),
                _message("Second part", [_citation("https://example.com/b", "")]),
            ]
        ),
    ]
    _install(monkeypatch, lambda request, n: httpx.Response(200, content=_sse(*events) + b"data: [DONE]\n\n"))

    result = await _provider().search("q")

    assert result.content == f"{answer}\n\nSecond part"
    assert result.sources == [{"url": "https://example.com/a", "title": "1"}, {"url": "https://example.com/b"}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "events,error_type,fragment",
    [
        ([_completed([])], "provider_error", "empty"),
        (
            [{"type": "response.incomplete", "response": {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}, "output": [_message("half")]}}],
            "provider_error",
            "max_output_tokens",
        ),
        ([{"type": "response.failed", "response": {"status": "failed", "error": {"message": "upstream exploded"}}}], "provider_error", "upstream exploded"),
        ([{"type": "error", "message": "bad things"}], "provider_error", "bad things"),
        ([{"type": "response.completed", "response": {"status": "incomplete", "output": [_message("half")]}}], "provider_error", "incomplete"),
        ([{"type": "response.output_text.delta", "delta": "half"}], "network_error", "terminal"),
    ],
)
async def test_non_completed_streams_are_errors(monkeypatch, events, error_type, fragment):
    seen = _install(monkeypatch, lambda request, n: httpx.Response(200, content=_sse(*events)))

    with pytest.raises(ResponsesError) as caught:
        await _provider().search("q")

    assert caught.value.error_type == error_type
    assert fragment in str(caught.value)
    assert len(seen["requests"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [b'{"output": []}', b"data: {not json}\n\n", b""])
async def test_non_sse_or_broken_body_is_parse_error(monkeypatch, body):
    _install(monkeypatch, lambda request, n: httpx.Response(200, content=body))

    with pytest.raises(ResponsesError) as caught:
        await _provider().search("q")

    assert caught.value.error_type == "parse_error"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 503])
async def test_retryable_status_before_any_event_is_retried(monkeypatch, status):
    def handler(request, n):
        if n == 1:
            return httpx.Response(status, content=b"busy")
        return httpx.Response(200, content=_sse(_completed([_message("ok")])))

    seen = _install(monkeypatch, handler)
    provider = _provider()

    assert (await provider.search("q")).content == "ok"
    assert len(seen["requests"]) == 2
    assert [item["status"] for item in provider.diagnostics["attempts"]] == ["error", "ok"]
    assert provider.diagnostics["attempts"][0]["http_status"] == status


@pytest.mark.asyncio
async def test_connect_error_is_retried(monkeypatch):
    def handler(request, n):
        if n == 1:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, content=_sse(_completed([_message("ok")])))

    seen = _install(monkeypatch, handler)

    assert (await _provider().search("q")).content == "ok"
    assert len(seen["requests"]) == 2


@pytest.mark.asyncio
async def test_broken_stream_after_first_event_is_not_retried(monkeypatch):
    class BrokenStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield _sse({"type": "response.created", "response": {}})
            raise httpx.ReadError("connection dropped")

    seen = _install(monkeypatch, lambda request, n: httpx.Response(200, stream=BrokenStream()))

    with pytest.raises(httpx.ReadError):
        await _provider().search("q")

    assert len(seen["requests"]) == 1


@pytest.mark.asyncio
async def test_retry_can_be_disabled(monkeypatch):
    seen = _install(monkeypatch, lambda request, n: httpx.Response(503, content=b"busy"))

    with pytest.raises(httpx.HTTPStatusError):
        await _provider(max_retries=0).search("q")

    assert len(seen["requests"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 422])
async def test_http_error_body_is_read_before_raise(monkeypatch, status):
    class ErrorStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{"error":"tool_choice not accepted"}'

    seen = _install(monkeypatch, lambda request, n: httpx.Response(status, stream=ErrorStream()))

    with pytest.raises(httpx.HTTPStatusError) as caught:
        await _provider().search("q")

    assert "tool_choice not accepted" in caught.value.response.text
    assert len(seen["requests"]) == 1


@pytest.mark.asyncio
async def test_diagnostics_prefer_reported_tool_usage(monkeypatch):
    usage = {
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "server_side_tool_usage_details": {"web_search_calls": 4, "x_search_calls": 2, "x_posts_fetched": 5},
    }
    events = [{"type": "response.created", "response": {}}, _completed([_message("ok")], usage=usage)]
    _install(monkeypatch, lambda request, n: httpx.Response(200, content=_sse(*events)))
    provider = _provider()

    await provider.search("a private question")

    data = provider.diagnostics
    assert data["tools"] == ["web_search", "x_search"]
    assert data["tool_choice"] == "required"
    assert data["response_id"] == "resp_1"
    assert data["response_model"] == "model-build"
    assert data["response_status"] == "completed"
    assert data["tool_usage"] == {"web_search_calls": 4, "x_search_calls": 2}
    assert data["usage"] == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    assert data["event_count"] == 2
    assert data["last_event_type"] == "response.completed"
    dumped = json.dumps(data)
    assert "secret-key" not in dumped and "a private question" not in dumped and "relay.example" not in dumped


@pytest.mark.asyncio
async def test_tool_usage_falls_back_to_output_items_and_omits_unknown(monkeypatch):
    output = [{"type": "web_search_call"}, {"type": "web_search_call"}, _message("ok")]
    _install(monkeypatch, lambda request, n: httpx.Response(200, content=_sse(_completed(output))))
    provider = _provider()

    await provider.search("q")

    assert provider.diagnostics["tool_usage"] == {"web_search_calls": 2}
    assert provider.tool_was_called("web_search")
    assert not provider.tool_was_called("x_search")


@pytest.mark.asyncio
async def test_cancelled_request_keeps_partial_diagnostics(monkeypatch):
    class HangingStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield _sse({"type": "response.created", "response": {"id": "resp_hang"}})
            await asyncio.sleep(30)

    _install(monkeypatch, lambda request, n: httpx.Response(200, stream=HangingStream()))
    provider = _provider()

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(provider.search("q"), timeout=0.2)

    assert provider.diagnostics["response_id"] == "resp_hang"
    assert provider.diagnostics["event_count"] == 1
    assert provider.diagnostics["attempts"][-1]["error_type"] == "cancelled"


def test_ssl_verify_follows_config_and_warns_once(monkeypatch, caplog):
    import logging

    from smart_search.providers import responses

    monkeypatch.setattr(responses, "_ssl_warning_emitted", False)
    monkeypatch.setenv("SSL_VERIFY", "false")
    provider = _provider()
    with caplog.at_level(logging.WARNING, logger="smart_search.providers.responses"):
        assert provider._get_ssl_verify() is False
        assert provider._get_ssl_verify() is False
    assert len([record for record in caplog.records if "SSL_VERIFY" in record.message]) == 1
