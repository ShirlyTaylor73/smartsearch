import json

import httpx
import pytest

from smart_search import cli, service
from smart_search.config import config
from smart_search.providers.responses import ResponsesError, SearchAnswer

from test_interactive_cli import FakePromptUI

OTHER_SECRETS = {"EXA_API_KEY": "exa-secret", "CONTEXT7_API_KEY": "context-secret", "ZHIPU_MCP_API_KEY": "zread-secret", "FIRECRAWL_API_KEY": "firecrawl-secret"}
ANSWER_CONFIG = {"SEARCH_ANSWER_API_URL": "https://relay.example/v1", "SEARCH_ANSWER_API_KEY": "probe-secret-123456", "SEARCH_ANSWER_MODEL": "model"}
ALL_KEPT = [True] * 7 + [False, True]  # keep seven values, no skill, apply


def _write_config(data):
    config.config_file.write_text(json.dumps(data), encoding="utf-8")


def _read_config():
    return json.loads(config.config_file.read_text(encoding="utf-8"))


def _http_error(status, body):
    request = httpx.Request("POST", "https://relay.example/v1/responses")
    return httpx.HTTPStatusError("failed", request=request, response=httpx.Response(status, content=body.encode(), request=request))


def _fake_provider(monkeypatch, outcomes):
    """outcomes: {tool: "called" | "silent" | "empty_called" | exception}"""
    calls = []

    class FakeProvider:
        def __init__(self, api_url, api_key, model, tools, **kwargs):
            assert len(tools) == 1
            self.tool = tools[0]
            self.diagnostics = {}
            self.called = False
            calls.append((self.tool, kwargs))

        async def search(self, query):
            outcome = outcomes[self.tool]
            if isinstance(outcome, BaseException):
                raise outcome
            self.diagnostics.update(last_event_type="response.completed", response_status="completed")
            self.called = outcome in {"called", "empty_called"}
            if outcome == "empty_called":
                raise ResponsesError("provider_error", "Responses returned an empty answer")
            return SearchAnswer("answer")

        def tool_was_called(self, tool):
            return self.called and tool == self.tool

    monkeypatch.setattr(service, "ResponsesSearchProvider", FakeProvider)
    return calls


def _env_config(monkeypatch):
    for key, value in ANSWER_CONFIG.items():
        monkeypatch.setenv(key, value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "web,x,web_status,x_status,suggested",
    [
        ("called", "called", "supported", "supported", "web_search,x_search"),
        ("called", "empty_called", "supported", "supported", "web_search,x_search"),
        ("called", _http_error(422, "unknown variant `x_search`"), "supported", "unsupported", "web_search"),
        ("called", _http_error(400, "tool x_search is not supported"), "supported", "unsupported", "web_search"),
        ("called", _http_error(400, "bad temperature"), "supported", "unknown", None),
        ("called", _http_error(429, "slow down x_search"), "supported", "unknown", None),
        ("called", _http_error(503, "x_search down"), "supported", "unknown", None),
        ("called", TimeoutError(), "supported", "unknown", None),
        ("called", "silent", "supported", "unknown", None),
        ("silent", "called", "unknown", "supported", None),
    ],
)
async def test_probe_classification_and_suggestion(monkeypatch, web, x, web_status, x_status, suggested):
    _env_config(monkeypatch)
    calls = _fake_provider(monkeypatch, {"web_search": web, "x_search": x})

    result = await service.probe_search_tools()

    assert [result["results"][tool]["status"] for tool in ("web_search", "x_search")] == [web_status, x_status]
    assert result["suggested_tools"] == suggested
    assert [tool for tool, _ in calls] == ["web_search", "x_search"]
    assert all(kwargs == {"timeout": 60.0, "max_retries": 0} for _, kwargs in calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [_http_error(401, "bad key probe-secret-123456"), _http_error(422, "web_search unknown"), httpx.ConnectError("refused")])
async def test_probe_skips_x_search_when_web_request_fails(monkeypatch, failure):
    _env_config(monkeypatch)
    calls = _fake_provider(monkeypatch, {"web_search": failure, "x_search": "called"})

    result = await service.probe_search_tools()

    assert [tool for tool, _ in calls] == ["web_search"]
    assert result["results"]["web_search"]["request_failed"] is True
    assert result["results"]["x_search"]["status"] == "unknown"
    assert result["suggested_tools"] is None
    assert "probe-secret-123456" not in json.dumps(result)


@pytest.mark.asyncio
async def test_probe_without_answer_config_sends_nothing(monkeypatch):
    calls = _fake_provider(monkeypatch, {})

    result = await service.probe_search_tools()

    assert calls == []
    assert "SEARCH_ANSWER_API_URL" in result["skipped"]


@pytest.mark.asyncio
async def test_default_doctor_stays_offline(monkeypatch):
    _env_config(monkeypatch)
    monkeypatch.setattr(service, "ResponsesSearchProvider", lambda *a, **k: pytest.fail("request attempted"))

    assert "tool_probe" not in await service.doctor()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tools,web,x,ok",
    [
        ("web_search", "called", _http_error(422, "no x_search"), True),
        ("web_search,x_search", "called", _http_error(422, "no x_search"), False),
        ("web_search,x_search", "called", "silent", True),
        ("web_search", "silent", "silent", True),
        ("web_search", _http_error(401, "bad key"), "called", False),
    ],
)
async def test_doctor_probe_verdict_is_read_only(monkeypatch, tools, web, x, ok):
    _write_config(ANSWER_CONFIG | OTHER_SECRETS | {"SEARCH_ANSWER_TOOLS": tools})
    _fake_provider(monkeypatch, {"web_search": web, "x_search": x})
    before = config.config_file.read_text(encoding="utf-8")

    result = await service.doctor(probe_tools=True)

    assert result["ok"] is ok
    assert result["tool_probe"]["current_tools"] == tools
    assert ("error_type" in result) is (not ok)
    assert config.config_file.read_text(encoding="utf-8") == before


def test_cli_doctor_accepts_probe_flag():
    assert cli.build_parser().parse_args(["doctor", "--probe-tools"]).probe_tools is True
    assert cli.build_parser().parse_args(["doctor"]).probe_tools is False


@pytest.mark.parametrize("accept", [True, False])
def test_interactive_setup_asks_before_updating_tools(monkeypatch, capsys, accept):
    _write_config(ANSWER_CONFIG | OTHER_SECRETS)
    _fake_provider(monkeypatch, {"web_search": "called", "x_search": "called"})
    prompt = FakePromptUI(confirms=ALL_KEPT + [accept])
    monkeypatch.setattr(cli, "prompt_ui", prompt)

    assert cli.main(["setup"]) == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert prompt.calls[-1] == ("confirm", "Update SEARCH_ANSWER_TOOLS: web_search -> web_search,x_search?", True)
    assert _read_config().get("SEARCH_ANSWER_TOOLS") == ("web_search,x_search" if accept else None)
    assert result["tool_probe"]["updated"] is accept
    assert "billed" in captured.err
    assert "probe-secret-123456" not in captured.out + captured.err


@pytest.mark.parametrize(
    "current,x_outcome",
    [("x_search,web_search", "called"), ("web_search", "silent"), ("web_search", _http_error(422, "x_search"))],
)
def test_interactive_setup_does_not_ask_when_nothing_would_change(monkeypatch, capsys, current, x_outcome):
    _write_config(ANSWER_CONFIG | OTHER_SECRETS | {"SEARCH_ANSWER_TOOLS": current})
    _fake_provider(monkeypatch, {"web_search": "called", "x_search": x_outcome})
    prompt = FakePromptUI(confirms=list(ALL_KEPT))
    monkeypatch.setattr(cli, "prompt_ui", prompt)

    assert cli.main(["setup"]) == 0

    assert prompt.calls[-1][1] == "Apply this setup?"
    assert _read_config()["SEARCH_ANSWER_TOOLS"] == current


def test_interactive_setup_asks_after_explicit_tools_flag(monkeypatch, capsys):
    _write_config(ANSWER_CONFIG | OTHER_SECRETS)
    _fake_provider(monkeypatch, {"web_search": "called", "x_search": _http_error(422, "x_search")})
    prompt = FakePromptUI(confirms=ALL_KEPT + [True])
    monkeypatch.setattr(cli, "prompt_ui", prompt)

    assert cli.main(["setup", "--search-answer-tools", "web_search,x_search"]) == 0

    assert prompt.calls[-1][1] == "Update SEARCH_ANSWER_TOOLS: web_search,x_search -> web_search?"
    assert _read_config()["SEARCH_ANSWER_TOOLS"] == "web_search"


def test_interactive_setup_only_reports_environment_managed_tools(monkeypatch, capsys):
    _write_config(ANSWER_CONFIG | OTHER_SECRETS)
    monkeypatch.setenv("SEARCH_ANSWER_TOOLS", "web_search")
    _fake_provider(monkeypatch, {"web_search": "called", "x_search": "called"})
    prompt = FakePromptUI(confirms=list(ALL_KEPT))
    monkeypatch.setattr(cli, "prompt_ui", prompt)

    assert cli.main(["setup"]) == 0

    assert prompt.calls[-1][1] == "Apply this setup?"
    assert "environment" in capsys.readouterr().err
    assert "SEARCH_ANSWER_TOOLS" not in _read_config()


def test_failed_probe_keeps_saved_config_and_setup_succeeds(monkeypatch, capsys):
    _write_config(ANSWER_CONFIG | OTHER_SECRETS)
    _fake_provider(monkeypatch, {"web_search": _http_error(401, "bad key")})
    monkeypatch.setattr(cli, "prompt_ui", FakePromptUI(confirms=list(ALL_KEPT)))

    assert cli.main(["setup"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["ok"] is True
    assert result["tool_probe"]["results"]["web_search"]["status"] == "unknown"
    assert _read_config()["SEARCH_ANSWER_MODEL"] == "model"


def test_noninteractive_setup_does_not_probe_by_default(monkeypatch, capsys):
    calls = _fake_provider(monkeypatch, {})
    monkeypatch.setattr(cli, "prompt_ui", FakePromptUI(tty=False))

    argv = ["setup", "--non-interactive", "--search-answer-api-url", "https://relay.example/v1",
            "--search-answer-api-key", "k", "--search-answer-model", "m"]
    assert cli.main(argv) == 0

    assert calls == []
    assert json.loads(capsys.readouterr().out)["tool_probe"] is None


def test_noninteractive_probe_reports_without_writing_tools(monkeypatch, capsys):
    _write_config(ANSWER_CONFIG)
    calls = _fake_provider(monkeypatch, {"web_search": "called", "x_search": "called"})
    prompt = FakePromptUI(tty=False)
    monkeypatch.setattr(cli, "prompt_ui", prompt)

    assert cli.main(["setup", "--non-interactive", "--probe-tools"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert len(calls) == 2
    assert prompt.calls == []
    assert result["tool_probe"]["suggested_tools"] == "web_search,x_search"
    assert result["tool_probe"]["updated"] is False
    assert "SEARCH_ANSWER_TOOLS" not in _read_config()
