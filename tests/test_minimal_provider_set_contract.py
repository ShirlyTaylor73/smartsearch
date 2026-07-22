import json

import httpx
import pytest

from smart_search import cli, service
from smart_search.config import Config


def _fresh_config(monkeypatch):
    config = Config()
    monkeypatch.setattr(config, "_config_file", None)
    monkeypatch.setattr(config, "_config_dir_source", None)
    return config


def test_search_parser_only_exposes_answer_and_sources():
    parser = cli.build_parser()
    assert parser.parse_args(["search", "answer", "q"]).operation == "answer"
    assert parser.parse_args(["search", "sources", "q"]).operation == "sources"
    with pytest.raises(SystemExit):
        parser.parse_args(["search", "similar", "https://example.com"])


def test_search_sources_rejects_removed_mode():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["search", "sources", "q", "--mode", "semantic"])


def test_search_answer_rejects_transport_stream_flags():
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["search", "answer", "q", "--stream"])
    with pytest.raises(SystemExit):
        parser.parse_args(["search", "answer", "q", "--no-stream"])


def test_docs_zread_commands_reject_ref():
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["docs", "tree", "owner/repo", "--ref", "main"])
    with pytest.raises(SystemExit):
        parser.parse_args(["docs", "read", "owner/repo", "README.md", "--ref", "main"])


def test_map_parser_uses_firecrawl_contract():
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "map",
            "site",
            "https://example.com",
            "--search",
            "docs",
            "--sitemap",
            "only",
            "--no-include-subdomains",
            "--no-ignore-query-parameters",
            "--ignore-cache",
            "--limit",
            "10",
            "--timeout",
            "60",
            "--location",
            '{"country":"US","languages":["en-US"]}',
        ]
    )
    assert args.search == "docs"
    assert args.sitemap == "only"
    assert args.include_subdomains is False
    assert args.ignore_query_parameters is False
    assert args.ignore_cache is True
    assert args.limit == 10
    assert args.timeout == 60

    for removed in ("--instructions", "--max-depth", "--max-breadth"):
        with pytest.raises(SystemExit):
            parser.parse_args(["map", "site", "https://example.com", removed, "1"])


def test_legacy_provider_commands_are_removed():
    parser = cli.build_parser()
    for command in (
        "exa-search",
        "exa-similar",
        "context7-library",
        "zhipu-search",
        "zhipu-mcp-search",
        "zhipu-mcp-reader",
        "zhipu-mcp-search-doc",
        "zhipu-mcp-repo-structure",
        "zhipu-mcp-read-file",
    ):
        with pytest.raises(SystemExit):
            parser.parse_args([command])


def test_config_uses_fixed_provider_keys(monkeypatch):
    monkeypatch.delenv("SMART_SEARCH_GROK_TRANSPORT", raising=False)
    monkeypatch.delenv("EXA_SEARCH_TYPE", raising=False)
    config = _fresh_config(monkeypatch)
    assert config.grok_transport == "openai-compatible"
    assert config.exa_search_type == "auto"
    info = config.get_config_info()
    assert info["SMART_SEARCH_GROK_TRANSPORT"] == "openai-compatible"
    assert info["EXA_SEARCH_TYPE"] == "auto"
    for removed in (
        "SMART_SEARCH_FALLBACK_MODE",
        "SMART_SEARCH_OPERATION_CONFIG",
        "OPENAI_COMPATIBLE_FALLBACK_MODELS",
        "TAVILY_API_KEY",
        "JINA_API_KEY",
        "ZHIPU_API_KEY",
        "ZHIPU_MCP_SEARCH_API_URL",
        "ZHIPU_MCP_READER_API_URL",
    ):
        assert removed not in info


@pytest.mark.parametrize("value", ["neural", "keyword", "bogus"])
def test_invalid_exa_search_type_is_rejected(monkeypatch, value):
    monkeypatch.setenv("EXA_SEARCH_TYPE", value)
    config = _fresh_config(monkeypatch)
    with pytest.raises(ValueError, match="EXA_SEARCH_TYPE"):
        _ = config.exa_search_type


@pytest.mark.parametrize("value", ["xai-responses", "openai-compatible"])
def test_grok_transport_tracks_config_source(monkeypatch, value):
    monkeypatch.setenv("SMART_SEARCH_GROK_TRANSPORT", value)
    config = _fresh_config(monkeypatch)
    assert config.grok_transport == value
    assert config.get_config_source("SMART_SEARCH_GROK_TRANSPORT") == "environment"


def test_invalid_grok_transport_is_rejected(monkeypatch):
    monkeypatch.setenv("SMART_SEARCH_GROK_TRANSPORT", "auto")
    config = _fresh_config(monkeypatch)
    with pytest.raises(ValueError, match="SMART_SEARCH_GROK_TRANSPORT"):
        _ = config.grok_transport


def test_operation_timeouts_only_accept_known_operations(monkeypatch):
    monkeypatch.setenv(
        "SMART_SEARCH_OPERATION_TIMEOUTS",
        '{"search.sources":12,"docs.tree":30}',
    )
    config = _fresh_config(monkeypatch)
    assert config.operation_timeouts == {"search.sources": 12.0, "docs.tree": 30.0}

    monkeypatch.setenv("SMART_SEARCH_OPERATION_TIMEOUTS", '{"search.similar":12}')
    with pytest.raises(ValueError, match="search.similar"):
        _ = config.operation_timeouts

    monkeypatch.setenv("SMART_SEARCH_OPERATION_TIMEOUTS", '{"search.sources":{"providers":["exa"]}}')
    with pytest.raises(ValueError, match="positive number"):
        _ = config.operation_timeouts


def test_operation_descriptors_have_one_responsible_provider():
    profiles = service.operation_profiles()
    expected = {
        "search.answer": "grok",
        "search.sources": "exa",
        "docs.resolve": "context7",
        "docs.search": "context7-or-zread",
        "docs.tree": "zhipu-mcp-zread",
        "docs.read": "zhipu-mcp-zread",
        "fetch.content": "firecrawl",
        "fetch.extract": "firecrawl",
        "map.site": "firecrawl",
    }
    assert set(profiles) == set(expected)
    assert {name: profile["responsible_provider"] for name, profile in profiles.items()} == expected
    assert not hasattr(service, "operation_candidates")


def test_operation_error_redacts_configured_secrets(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-secret-value")
    assert service._redact_sensitive("upstream echoed exa-secret-value") == "upstream echoed ***"


@pytest.mark.asyncio
async def test_search_sources_does_not_fallback_after_exa_failure(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-key")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-key")
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-key")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-key")

    async def fail_exa(*args, **kwargs):
        return {"ok": False, "error_type": "network_error", "error": "exa failed"}

    async def forbidden(*args, **kwargs):
        raise AssertionError("cross-provider fallback attempted")

    monkeypatch.setattr(service, "exa_search", fail_exa)
    monkeypatch.setattr(service, "zhipu_search", forbidden)
    monkeypatch.setattr(service, "zhipu_mcp_search", forbidden)
    monkeypatch.setattr(service, "call_tavily_search", forbidden)
    monkeypatch.setattr(service, "call_firecrawl_search", forbidden)

    result = await service.search_sources("q")
    assert result["ok"] is False
    assert result["error"] == "exa failed"
    assert "provider_attempts" not in result


@pytest.mark.asyncio
async def test_exa_search_uses_native_type_and_public_filters(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, endpoint, headers, json):
            calls.append(json)
            return httpx.Response(200, json={"results": []}, request=httpx.Request("POST", endpoint))

    monkeypatch.setattr("smart_search.providers.exa.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setenv("EXA_API_KEY", "exa-key")
    monkeypatch.setenv("EXA_SEARCH_TYPE", "deep-lite")
    await service.search_sources(
        "q",
        limit=7,
        start_published_date="2026-01-01T00:00:00.000Z",
        include_domains=["example.com"],
        exclude_domains=["spam.example"],
        category="research paper",
        include_text=True,
        include_highlights=True,
    )
    assert calls == [
        {
            "query": "q",
            "numResults": 7,
            "type": "deep-lite",
            "contents": {"text": True, "highlights": True},
            "startPublishedDate": "2026-01-01T00:00:00.000Z",
            "includeDomains": ["example.com"],
            "excludeDomains": ["spam.example"],
            "category": "research paper",
        }
    ]


@pytest.mark.asyncio
async def test_search_answer_only_uses_selected_grok_transport(monkeypatch):
    calls = []

    class FakeXAI:
        def __init__(self, *args, **kwargs):
            calls.append("xai-init")

        async def search(self, query):
            calls.append("xai-search")
            return "answer"

    class ForbiddenOpenAI:
        def __init__(self, *args, **kwargs):
            raise AssertionError("OpenAI-compatible fallback attempted")

    monkeypatch.setenv("SMART_SEARCH_GROK_TRANSPORT", "xai-responses")
    monkeypatch.setenv("XAI_API_KEY", "xai-key")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-key")
    monkeypatch.setattr(service, "XAIResponsesSearchProvider", FakeXAI)
    monkeypatch.setattr(service, "OpenAICompatibleSearchProvider", ForbiddenOpenAI)
    result = await service.search_answer("q")
    assert result["ok"] is True
    assert calls == ["xai-init", "xai-search"]


@pytest.mark.asyncio
async def test_docs_search_routes_repo_to_zread_with_language(monkeypatch):
    monkeypatch.setenv("ZHIPU_MCP_API_KEY", "zread-key")
    captured = {}

    async def fake_zread(repo, query, *, language):
        captured.update(repo=repo, query=query, language=language)
        return {
            "ok": True,
            "results": [{"title": "PR", "url": "https://example.com/pr", "description": "result"}],
        }

    async def forbidden(*args, **kwargs):
        raise AssertionError("unexpected docs provider")

    monkeypatch.setattr(service, "zhipu_mcp_search_doc", fake_zread)
    monkeypatch.setattr(service, "context7_library", forbidden)
    monkeypatch.setattr(service, "context7_docs", forbidden)
    monkeypatch.setattr(service, "exa_search", forbidden)

    result = await service.docs_search("最近的重要 PR", source="owner/repo")
    assert result["ok"] is True
    assert captured == {"repo": "owner/repo", "query": "最近的重要 PR", "language": "zh"}


@pytest.mark.asyncio
async def test_zread_tree_and_read_never_send_ref(monkeypatch):
    monkeypatch.setenv("ZHIPU_MCP_API_KEY", "zread-key")
    tree_call = {}
    read_call = {}

    async def fake_tree(repo, *, path=""):
        tree_call.update(repo=repo, path=path)
        return {"ok": True, "results": []}

    async def fake_read(repo, path):
        read_call.update(repo=repo, path=path)
        return {"ok": True, "content": "hello"}

    monkeypatch.setattr(service, "zhipu_mcp_repo_structure", fake_tree)
    monkeypatch.setattr(service, "zhipu_mcp_read_file", fake_read)

    assert (await service.docs_tree("owner/repo", path="src"))["ok"] is True
    assert (await service.docs_read("owner/repo", "README.md"))["ok"] is True
    assert tree_call == {"repo": "owner/repo", "path": "src"}
    assert read_call == {"repo": "owner/repo", "path": "README.md"}


def test_map_location_json_contract():
    assert service.parse_firecrawl_location('{"country":"US","languages":["en-US"]}') == {
        "country": "US",
        "languages": ["en-US"],
    }
    for invalid in (
        '{"country":"usa"}',
        '{"country":"US","languages":"en-US"}',
        '{"country":"US","timezone":"UTC"}',
        "[]",
    ):
        with pytest.raises(ValueError):
            service.parse_firecrawl_location(invalid)


def test_map_limit_contract():
    for limit in (0, 100001):
        with pytest.raises(ValueError):
            service.validate_firecrawl_map_limit(limit)
    assert service.validate_firecrawl_map_limit(1) == 1
    assert service.validate_firecrawl_map_limit(100000) == 100000


def test_config_info_remains_json_serializable(monkeypatch):
    info = _fresh_config(monkeypatch).get_config_info()
    json.dumps(info)
