import json

import pytest

from smart_search import service


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
        return {"ok": True, "results": [{"pageId": "https://react.dev/reference/react/hooks", "breadcrumb": "Hooks", "content": "Use hooks"}], "content": "raw"}

    monkeypatch.setattr(service, "context7_docs", fake_docs)
    result = await service.docs_search("hooks", source="/facebook/react")
    assert result["ok"] is True
    assert result["results"][0]["url"] == "https://react.dev/reference/react/hooks"


@pytest.mark.asyncio
async def test_context7_docs_search_without_source_uses_v3_results(monkeypatch):
    monkeypatch.setenv("CONTEXT7_API_KEY", "secret")

    async def fake_search(query):
        return {
            "ok": True,
            "content": "raw",
            "version": {"status": "unverified"},
            "results": [
                {"codeId": "https://fastapi.tiangolo.com/reference/dependencies", "codeTitle": "Depends", "pageTitle": "Dependencies", "codeDescription": "dependency", "libraryId": "/websites/fastapi_tiangolo"},
                {"pageId": "https://fastapi.tiangolo.com/tutorial/dependencies", "breadcrumb": "Dependencies", "content": "guide"},
            ],
        }

    async def forbidden(*args, **kwargs):
        raise AssertionError("legacy library resolution called")

    monkeypatch.setattr(service, "context7_documentation_search", fake_search)
    monkeypatch.setattr(service, "context7_library", forbidden)
    result = await service.docs_search("FastAPI dependency injection")
    assert result["ok"] is True
    assert result["version"] == {"status": "unverified"}
    assert result["results"][0]["library_id"] == "/websites/fastapi_tiangolo"
    assert [row["url"] for row in result["results"]] == [
        "https://fastapi.tiangolo.com/reference/dependencies",
        "https://fastapi.tiangolo.com/tutorial/dependencies",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["/vercel/next.js@15", "/vercel/next.js/v15.1.11"])
async def test_context7_versioned_source_is_forwarded(monkeypatch, source):
    monkeypatch.setenv("CONTEXT7_API_KEY", "secret")
    async def fake_docs(library_id, query):
        assert library_id == source
        return {"ok": True, "results": [], "content": ""}
    monkeypatch.setattr(service, "context7_docs", fake_docs)
    assert (await service.docs_search("routing", source=source))["ok"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["", "/owner/repo"])
async def test_context7_error_metadata_reaches_cli_envelope(monkeypatch, source):
    monkeypatch.setenv("CONTEXT7_API_KEY", "secret")
    async def fail(*args):
        return {"ok": False, "error_type": "rate_limited", "error": "HTTP 429: limited", "http_status": 429, "provider_error_code": "rate_limit_exceeded"}
    monkeypatch.setattr(service, "context7_documentation_search", fail)
    monkeypatch.setattr(service, "context7_docs", fail)
    result = await service.docs_search("q", source=source)
    assert result["http_status"] == 429
    assert result["provider_error_code"] == "rate_limit_exceeded"
    assert result["error_type"] == "rate_limited"


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
