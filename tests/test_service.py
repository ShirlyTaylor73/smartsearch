import json

import pytest

from smart_search import service


@pytest.mark.asyncio
async def test_search_answer_uses_openai_compatible_when_selected(monkeypatch):
    calls = []

    class FakeProvider:
        def __init__(self, api_url, api_key, model, stream):
            calls.append((api_url, api_key, model, stream))

        async def search(self, query):
            return "Answer\n\nsources([{\"url\":\"https://example.com\"}])"

    monkeypatch.setenv("SMART_SEARCH_GROK_TRANSPORT", "openai-compatible")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "grok")
    monkeypatch.setattr(service, "OpenAICompatibleSearchProvider", FakeProvider)
    result = await service.search_answer("q")
    assert result["ok"] is True
    assert result["sources"][0]["url"] == "https://example.com"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_selected_grok_transport_does_not_fallback(monkeypatch):
    monkeypatch.setenv("SMART_SEARCH_GROK_TRANSPORT", "xai-responses")
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "secret")
    result = await service.search_answer("q")
    assert result["error_type"] == "config_error"
    assert "XAI_API_KEY" in result["error"]


@pytest.mark.asyncio
async def test_exa_error_is_preserved(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "secret")

    async def fail(*args, **kwargs):
        return {"ok": False, "error_type": "rate_limited", "error": "limited"}

    monkeypatch.setattr(service, "exa_search", fail)
    result = await service.search_sources("q")
    assert result["error_type"] == "rate_limited"
    assert result["error"] == "limited"


@pytest.mark.asyncio
async def test_context7_docs_search_normalizes_results(monkeypatch):
    monkeypatch.setenv("CONTEXT7_API_KEY", "secret")

    async def fake_docs(library_id, query):
        return {"ok": True, "results": [{"title": "Hooks", "content": "Use hooks"}], "content": "raw"}

    monkeypatch.setattr(service, "context7_docs", fake_docs)
    result = await service.docs_search("hooks", source="/facebook/react")
    assert result["ok"] is True
    assert result["results"][0]["url"].startswith("context7:")


@pytest.mark.asyncio
async def test_invalid_docs_source_stops_before_network(monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("network called")

    monkeypatch.setattr(service, "context7_docs", forbidden)
    result = await service.docs_search("q", source="not a source")
    assert result["error_type"] == "parameter_error"


def test_config_set_masks_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("SMART_SEARCH_CONFIG_DIR", str(tmp_path))
    service.config._config_file = None
    service.config._config_dir_source = None
    result = service.config_set("EXA_API_KEY", "1234567890abcdef")
    assert result["ok"] is True
    assert result["value"] != "1234567890abcdef"


@pytest.mark.asyncio
async def test_doctor_contains_fixed_operation_matrix():
    result = await service.doctor()
    assert set(result["operation_status"]) == set(service.OPERATION_PROFILES)
    assert result["operation_status"]["map.site"]["responsible_provider"] == "firecrawl"


def test_config_info_is_json_serializable():
    json.dumps(service.config.get_config_info())
