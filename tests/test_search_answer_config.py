import json

import pytest

from smart_search import cli, service
from smart_search.config import config
from smart_search.providers.responses import SearchAnswer

from test_interactive_cli import FakePromptUI

NEW_KEYS = ("SEARCH_ANSWER_API_URL", "SEARCH_ANSWER_API_KEY", "SEARCH_ANSWER_MODEL")
OTHER_SECRETS = {"EXA_API_KEY": "exa-secret", "CONTEXT7_API_KEY": "context-secret", "ZHIPU_MCP_API_KEY": "zread-secret", "FIRECRAWL_API_KEY": "firecrawl-secret"}
OPENAI_LEGACY = {
    "OPENAI_COMPATIBLE_API_URL": "https://relay.example/v1",
    "OPENAI_COMPATIBLE_API_KEY": "sk-relay-1234567890",
    "OPENAI_COMPATIBLE_MODEL": "relay-model",
    "OPENAI_COMPATIBLE_STREAM": "true",
}
XAI_LEGACY = {"XAI_API_KEY": "xai-legacy-1234567890", "XAI_MODEL": "xai-model", "XAI_TOOLS": "x_search"}


def _write_config(data):
    config.config_file.write_text(json.dumps(data), encoding="utf-8")


def _read_config():
    return json.loads(config.config_file.read_text(encoding="utf-8"))


def _configure(monkeypatch):
    monkeypatch.setenv("SEARCH_ANSWER_API_URL", "https://relay.example/v1")
    monkeypatch.setenv("SEARCH_ANSWER_API_KEY", "secret")
    monkeypatch.setenv("SEARCH_ANSWER_MODEL", "model")


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, ["web_search"]),
        ("", ["web_search"]),
        ("  ", ["web_search"]),
        ("web_search,x_search", ["web_search", "x_search"]),
        (" X_Search , web_search,x_search,", ["x_search", "web_search"]),
    ],
)
def test_tool_list_parsing(monkeypatch, raw, expected):
    if raw is not None:
        monkeypatch.setenv("SEARCH_ANSWER_TOOLS", raw)
    assert config.parse_search_answer_tools() == expected


@pytest.mark.asyncio
async def test_invalid_tool_is_config_error_without_request(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setenv("SEARCH_ANSWER_TOOLS", "web_search,browse")
    monkeypatch.setattr(service, "ResponsesSearchProvider", lambda *a, **k: pytest.fail("request attempted"))

    result = await service.search_answer("q")

    assert result["error_type"] == "config_error"
    assert "browse" in result["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", NEW_KEYS)
async def test_every_required_key_is_enforced(monkeypatch, missing):
    _configure(monkeypatch)
    monkeypatch.delenv(missing)
    monkeypatch.setattr(service, "ResponsesSearchProvider", lambda *a, **k: pytest.fail("request attempted"))

    result = await service.search_answer("q")

    assert result["error_type"] == "config_error"
    assert missing in result["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [OPENAI_LEGACY, XAI_LEGACY])
async def test_legacy_only_config_gets_migration_hint(monkeypatch, legacy):
    _write_config(legacy)
    monkeypatch.setattr(service, "ResponsesSearchProvider", lambda *a, **k: pytest.fail("request attempted"))

    result = await service.search_answer("q")

    assert result["error_type"] == "config_error"
    assert "SEARCH_ANSWER_API_KEY" in result["error"]
    assert "smart-search setup" in result["error"]
    prefix = next(iter(legacy)).rsplit("_API", 1)[0]
    assert f"{prefix}_API_KEY" in result["error"]
    assert ("https://api.x.ai/v1" in result["error"]) == (prefix == "XAI")
    for value in legacy.values():
        if "123456" in value:
            assert value not in result["error"]


@pytest.mark.asyncio
async def test_service_passes_new_config_to_responses_provider(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setenv("SEARCH_ANSWER_TOOLS", "web_search,x_search")
    calls = []

    class FakeProvider:
        def __init__(self, api_url, api_key, model, tools, **kwargs):
            calls.append((api_url, api_key, model, tools))
            self.diagnostics = {}

        async def search(self, query):
            text = "<think>hidden</think>Answer body\n\n- [Tail](https://example.com/tail)"
            return SearchAnswer(text, [{"url": "https://example.com/cited"}])

    monkeypatch.setattr(service, "ResponsesSearchProvider", FakeProvider)

    result = await service.search_answer("q")

    assert result["ok"] is True
    assert calls == [("https://relay.example/v1", "secret", "model", ["web_search", "x_search"])]
    assert result["content"] == "Answer body\n\n- [Tail](https://example.com/tail)"
    assert result["sources"] == [{"url": "https://example.com/cited"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("status,error_type", [(404, "provider_error"), (405, "provider_error"), (422, "parameter_error")])
async def test_http_errors_are_mapped_and_redacted(monkeypatch, status, error_type):
    import httpx

    _configure(monkeypatch)

    class FailingProvider:
        def __init__(self, *args, **kwargs):
            self.diagnostics = {}

        async def search(self, query):
            request = httpx.Request("POST", "https://relay.example/v1/responses")
            response = httpx.Response(status, content=b"nope secret", request=request)
            raise httpx.HTTPStatusError("failed", request=request, response=response)

    monkeypatch.setattr(service, "ResponsesSearchProvider", FailingProvider)

    result = await service.search_answer("q")

    assert result["error_type"] == error_type
    assert "secret" not in result["error"]
    assert ("/responses" in result["error"]) == (status in {404, 405})


def test_removed_keys_can_be_unset_but_not_set():
    removed = [*OPENAI_LEGACY, *XAI_LEGACY, "OPENAI_COMPATIBLE_FALLBACK_MODELS", "SMART_SEARCH_GROK_TRANSPORT", "SMART_SEARCH_FALLBACK_MODE"]
    _write_config({key: "value" for key in removed})
    assert service.config_list()["values"] == {}
    for key in removed:
        assert service.config_set(key, "x")["ok"] is False
        assert service.config_unset(key)["ok"] is True
    assert _read_config() == {}


def test_config_info_reports_responses_fields(monkeypatch):
    _configure(monkeypatch)
    info = config.get_config_info()
    assert info["primary_api_mode"] == "responses"
    assert info["SEARCH_ANSWER_TOOLS"] == "web_search"
    assert info["SEARCH_ANSWER_API_KEY"] != "secret"
    assert info["config_status"].startswith("ok:")
    assert not [key for key in info if key.startswith(("XAI_", "OPENAI_COMPATIBLE_")) or key == "SMART_SEARCH_GROK_TRANSPORT"]
    assert service.current_model()["search_answer_model"] == "model"


def test_model_has_no_implicit_default():
    assert config.search_answer_model is None


def _isolated_setup(monkeypatch, prompt):
    async def fake_probe():
        return {"current_tools": "web_search", "results": {}, "suggested_tools": None, "skipped": "test"}

    monkeypatch.setattr(cli, "prompt_ui", prompt)
    monkeypatch.setattr(service, "probe_search_tools", fake_probe)


@pytest.mark.parametrize(
    "legacy,expected_url,expected_model",
    [
        (OPENAI_LEGACY | XAI_LEGACY, "https://relay.example/v1", "relay-model"),
        (OPENAI_LEGACY | XAI_LEGACY | {"SMART_SEARCH_GROK_TRANSPORT": "xai-responses"}, "https://api.x.ai/v1", "xai-model"),
    ],
)
def test_setup_migrates_the_previously_active_set(monkeypatch, capsys, legacy, expected_url, expected_model):
    _write_config(legacy | OTHER_SECRETS)
    # three reuse prompts, four existing secrets kept, skill declined, final apply
    prompt = FakePromptUI(confirms=[True, True, True, True, True, True, True, False, True])
    _isolated_setup(monkeypatch, prompt)

    assert cli.main(["setup"]) == 0
    captured = capsys.readouterr()
    saved = _read_config()

    assert saved["SEARCH_ANSWER_API_URL"] == expected_url
    assert saved["SEARCH_ANSWER_MODEL"] == expected_model
    assert "SEARCH_ANSWER_TOOLS" not in saved
    for key, value in legacy.items():
        assert saved[key] == value
    assert not any(call[0] in {"select", "secret", "text"} for call in prompt.calls)
    shown = captured.out + captured.err + json.dumps(prompt.calls)
    assert "sk-relay-1234567890" not in shown and "xai-legacy-1234567890" not in shown


def test_setup_does_not_borrow_values_from_the_other_set(monkeypatch, capsys):
    legacy = OPENAI_LEGACY | {"SMART_SEARCH_GROK_TRANSPORT": "xai-responses", "XAI_API_KEY": "xai-legacy-1234567890"}
    _write_config(legacy | OTHER_SECRETS)
    prompt = FakePromptUI(confirms=[True, True, True, True, True, True, False, True], texts=["typed-model"])
    _isolated_setup(monkeypatch, prompt)

    assert cli.main(["setup"]) == 0

    assert _read_config()["SEARCH_ANSWER_MODEL"] == "typed-model"


def test_setup_rejected_legacy_values_are_typed_again(monkeypatch, capsys):
    _write_config(OPENAI_LEGACY | OTHER_SECRETS)
    prompt = FakePromptUI(
        confirms=[False, False, False, True, True, True, True, False, True],
        texts=["https://new.example/v1", "new-model"],
        secrets=["new-key"],
    )
    _isolated_setup(monkeypatch, prompt)

    assert cli.main(["setup"]) == 0
    saved = _read_config()

    assert [saved[key] for key in NEW_KEYS] == ["https://new.example/v1", "new-key", "new-model"]
    assert saved["OPENAI_COMPATIBLE_API_KEY"] == OPENAI_LEGACY["OPENAI_COMPATIBLE_API_KEY"]


def test_setup_does_not_offer_legacy_values_when_new_ones_exist(monkeypatch, capsys):
    new = {"SEARCH_ANSWER_API_URL": "https://n.example/v1", "SEARCH_ANSWER_API_KEY": "new-secret-123456", "SEARCH_ANSWER_MODEL": "n"}
    _write_config(OPENAI_LEGACY | new | OTHER_SECRETS)
    prompt = FakePromptUI(confirms=[True] * 7 + [False, True])
    _isolated_setup(monkeypatch, prompt)

    assert cli.main(["setup"]) == 0

    assert all("OPENAI_COMPATIBLE" not in call[1] for call in prompt.calls if call[0] == "confirm")
    assert _read_config()["SEARCH_ANSWER_MODEL"] == "n"


def test_noninteractive_setup_ignores_legacy_values(monkeypatch, capsys):
    _write_config(OPENAI_LEGACY)
    _isolated_setup(monkeypatch, FakePromptUI(tty=False))

    assert cli.main(["setup", "--non-interactive"]) == 0

    assert not [key for key in _read_config() if key.startswith("SEARCH_ANSWER_")]
