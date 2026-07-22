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
