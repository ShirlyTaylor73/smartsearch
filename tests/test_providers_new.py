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
            return httpx.Response(200, json=[{"id": "/facebook/react", "title": "React", "description": "UI"}], headers={"content-type": "application/json"}, request=httpx.Request("GET", endpoint))

    monkeypatch.setattr("smart_search.providers.context7.httpx.AsyncClient", FakeAsyncClient)
    data = json.loads(await Context7Provider("https://context7.com", "key").library("react", "hooks"))
    assert data["ok"] is True
    assert data["results"][0]["id"] == "/facebook/react"


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
