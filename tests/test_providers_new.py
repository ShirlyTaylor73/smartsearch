import json

import httpx
import pytest

from smart_search.providers.context7 import Context7Provider
from smart_search.providers.exa import ExaSearchProvider


@pytest.mark.asyncio
async def test_context7_provider_normalizes_library_results(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, timeout, follow_redirects=True):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, endpoint, headers):
            url = httpx.URL(endpoint)
            assert url.path == "/api/v2/libs/search"
            assert url.params["libraryName"] == "react"
            assert url.params["query"] == "hooks"
            return httpx.Response(200, json=[{"id": "/facebook/react", "title": "React", "description": "UI"}], headers={"content-type": "application/json"}, request=httpx.Request("GET", endpoint))

    monkeypatch.setattr("smart_search.providers.context7.httpx.AsyncClient", FakeAsyncClient)
    data = json.loads(await Context7Provider("https://context7.com", "key").library("react", "hooks"))
    assert data["ok"] is True
    assert data["results"][0]["id"] == "/facebook/react"


@pytest.mark.asyncio
async def test_context7_documentation_search_uses_v3_json(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout, follow_redirects=True):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, endpoint, headers):
            calls.append(endpoint)
            return httpx.Response(200, json={
                "codeSnippets": [{"codeId": "https://fastapi.tiangolo.com/reference/dependencies", "codeTitle": "Depends", "pageTitle": "Dependencies", "codeDescription": "dependency"}],
                "infoSnippets": [{"pageId": "https://fastapi.tiangolo.com/tutorial/dependencies", "breadcrumb": "Dependencies", "content": "guide"}],
                "version": {"status": "verified"},
            }, headers={"content-type": "application/json"}, request=httpx.Request("GET", endpoint))

    monkeypatch.setattr("smart_search.providers.context7.httpx.AsyncClient", FakeAsyncClient)
    data = json.loads(await Context7Provider("https://context7.com", "key").documentation_search("FastAPI dependencies", library=["fastapi", "/fastapi/fastapi"], version="1.0", language="Python"))
    assert data["ok"] is True
    assert data["results"][0]["codeId"] == "https://fastapi.tiangolo.com/reference/dependencies"
    assert "/api/v3/search?" in calls[0]
    assert "type=json" in calls[0]
    params = httpx.URL(calls[0]).params
    assert params.get_list("library") == ["fastapi", "/fastapi/fastapi"]
    assert params["version"] == "1.0"
    assert params["language"] == "Python"
    assert data["version"] == {"status": "verified"}
    assert "Source: https://fastapi.tiangolo.com" in data["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["library", "docs", "documentation_search"])
@pytest.mark.parametrize("status,body,error_type", [
    (401, {"error": "invalid_api_key", "message": "Invalid API key"}, "auth_error"),
    (429, {"error": "rate_limit_exceeded", "message": "Rate limit exceeded"}, "rate_limited"),
    (202, {"error": "library_not_finalized", "message": "Indexing pending"}, "provider_error"),
    (503, "upstream temporarily unavailable", "provider_error"),
])
async def test_context7_errors_preserve_status_and_body(monkeypatch, method, status, body, error_type):
    client_type = httpx.AsyncClient
    def respond(request):
        return httpx.Response(status, **({"json": body} if isinstance(body, dict) else {"text": body}))
    monkeypatch.setattr("smart_search.providers.context7.httpx.AsyncClient", lambda **kwargs: client_type(transport=httpx.MockTransport(respond), **kwargs))
    monkeypatch.setenv("SMART_SEARCH_RETRY_MAX_ATTEMPTS", "0")
    provider = Context7Provider("https://context7.com", "secret")
    args = ("/fastapi/fastapi", "Depends") if method == "docs" else ("fastapi",)
    result = json.loads(await getattr(provider, method)(*args))
    assert result["ok"] is False
    assert result["error_type"] == error_type
    assert result["http_status"] == status
    assert f"HTTP {status}" in result["error"]
    if isinstance(body, dict):
        assert result["provider_error_code"] == body["error"]
        assert body["message"] in result["error"]
    else:
        assert body in result["error"]


@pytest.mark.asyncio
async def test_context7_docs_follows_library_redirect(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout, follow_redirects=True):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, endpoint, headers):
            calls.append(endpoint)
            request = httpx.Request("GET", endpoint)
            if "%2Ffastapi%2Ffastapi" in endpoint:
                return httpx.Response(
                    301,
                    json={
                        "error": "library_redirected",
                        "message": "Library redirected",
                        "redirectUrl": "/websites/fastapi_tiangolo",
                    },
                    headers={"content-type": "application/json"},
                    request=request,
                )
            return httpx.Response(
                200,
                json={"codeSnippets": [{"title": "Depends"}], "infoSnippets": []},
                headers={"content-type": "application/json"},
                request=request,
            )

    monkeypatch.setattr("smart_search.providers.context7.httpx.AsyncClient", FakeAsyncClient)
    data = json.loads(await Context7Provider("https://context7.com", "key").docs("/fastapi/fastapi", "Depends"))

    assert data["ok"] is True
    assert data["library_id"] == "/websites/fastapi_tiangolo"
    assert data["redirected_from"] == "/fastapi/fastapi"
    assert data["results"] == [{"title": "Depends"}]
    assert len(calls) == 2
    assert all("type=json" in endpoint for endpoint in calls)


@pytest.mark.asyncio
async def test_context7_docs_rejects_non_redirect_301(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, timeout, follow_redirects=True):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, endpoint, headers):
            return httpx.Response(
                301,
                json={"error": "invalid_library", "message": "Invalid library id"},
                headers={"content-type": "application/json"},
                request=httpx.Request("GET", endpoint),
            )

    monkeypatch.setattr("smart_search.providers.context7.httpx.AsyncClient", FakeAsyncClient)
    data = json.loads(await Context7Provider("https://context7.com", "key").docs("/invalid/library", "query"))

    assert data["ok"] is False
    assert "Invalid library id" in data["error"]


@pytest.mark.asyncio
async def test_exa_provider_reports_bad_request_as_parameter_error(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, endpoint, headers, json):
            return httpx.Response(400, json={"error": "invalid includeDomains"}, request=httpx.Request("POST", endpoint))

    monkeypatch.setattr("smart_search.providers.exa.httpx.AsyncClient", FakeAsyncClient)
    data = json.loads(await ExaSearchProvider("https://api.exa.ai", "key").search("test", include_domains=["github.com freertos.org"]))
    assert data["ok"] is False
    assert data["error_type"] == "parameter_error"
