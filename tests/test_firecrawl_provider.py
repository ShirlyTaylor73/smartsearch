import httpx
import pytest

from smart_search import service
from smart_search.providers.firecrawl import FirecrawlProvider


class FakeFirecrawlClient:
    calls = []
    responses = []

    def __init__(self, timeout, follow_redirects=True):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, endpoint, headers, json):
        self.__class__.calls.append({"endpoint": endpoint, "headers": headers, "json": json})
        payload = self.__class__.responses.pop(0)
        return httpx.Response(200, json=payload, request=httpx.Request("POST", endpoint))


@pytest.fixture(autouse=True)
def reset_client(monkeypatch):
    FakeFirecrawlClient.calls = []
    FakeFirecrawlClient.responses = []
    monkeypatch.setattr("smart_search.providers.firecrawl.httpx.AsyncClient", FakeFirecrawlClient)


@pytest.mark.asyncio
async def test_scrape_markdown_and_json_payloads():
    FakeFirecrawlClient.responses = [
        {"data": {"markdown": "# Page", "metadata": {"sourceURL": "https://final.example"}}},
        {"data": {"json": {"title": "Page"}, "markdown": "evidence"}},
    ]
    provider = FirecrawlProvider("https://api.firecrawl.dev/v2", "secret")

    content = await provider.scrape_markdown("https://example.com")
    extracted = await provider.scrape_json(
        "https://example.com",
        schema={"type": "object", "properties": {"title": {"type": "string"}}},
        max_length=20,
    )

    assert content["content"] == "# Page"
    assert content["final_url"] == "https://final.example"
    assert extracted["data"] == {"title": "Page"}
    assert len(extracted["raw_evidence"]) <= 20
    assert FakeFirecrawlClient.calls[0]["json"] == {"url": "https://example.com", "formats": ["markdown"]}
    assert FakeFirecrawlClient.calls[1]["json"]["formats"][0]["type"] == "json"
    assert FakeFirecrawlClient.calls[1]["json"]["formats"][0]["schema"]["type"] == "object"


@pytest.mark.asyncio
async def test_map_payload_and_normalization():
    FakeFirecrawlClient.responses = [{"data": {"links": ["https://example.com/a", {"url": "https://example.com/b", "title": "B"}]}}]
    provider = FirecrawlProvider("https://api.firecrawl.dev/v2", "secret")

    result = await provider.map_site(
        "https://example.com",
        search="docs",
        sitemap="only",
        includeSubdomains=False,
        ignoreQueryParameters=False,
        ignoreCache=True,
        limit=10,
        timeout_ms=60000,
        location={"country": "US", "languages": ["en-US"]},
    )

    assert result["entries"] == [
        {"url": "https://example.com/a"},
        {"url": "https://example.com/b", "title": "B"},
    ]
    assert FakeFirecrawlClient.calls[0]["json"]["timeout"] == 60000
    assert FakeFirecrawlClient.calls[0]["json"]["includeSubdomains"] is False


@pytest.mark.asyncio
async def test_fetch_extract_rejects_non_object_schema_before_network(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "secret")
    result = await service.fetch_extract("https://example.com", schema=[])
    assert result["ok"] is False
    assert result["error_type"] == "parameter_error"
    assert FakeFirecrawlClient.calls == []
