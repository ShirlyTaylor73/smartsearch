import json

import pytest

from smart_search import cli, service


def test_public_parser_exposes_capability_namespaces(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for command in ("search", "docs", "fetch", "map", "diagnose", "dev"):
        assert command in out
    for removed in ("anysearch-search", "deep", "research"):
        assert removed not in out


@pytest.mark.parametrize(
    ("argv", "command", "operation"),
    [
        (["search", "answer", "q"], "search", "answer"),
        (["search", "sources", "q"], "search", "sources"),
        (["search", "similar", "https://example.com"], "search", "similar"),
        (["docs", "resolve", "react"], "docs", "resolve"),
        (["docs", "search", "hooks"], "docs", "search"),
        (["docs", "tree", "owner/repo"], "docs", "tree"),
        (["docs", "read", "owner/repo", "README.md"], "docs", "read"),
        (["fetch", "content", "https://example.com"], "fetch", "content"),
        (["fetch", "extract", "https://example.com"], "fetch", "extract"),
        (["map", "site", "https://example.com"], "map", "site"),
    ],
)
def test_parser_sets_capability_operation(argv, command, operation):
    args = cli.build_parser().parse_args(argv)
    assert args.command == command
    assert args.operation == operation


def test_removed_commands_do_not_parse():
    parser = cli.build_parser()
    for command in ("anysearch-search", "anysearch-domains", "deep", "research"):
        with pytest.raises(SystemExit):
            parser.parse_args([command])


def test_operation_profiles_exclude_removed_capabilities():
    profiles = service.operation_profiles()
    assert "search.answer" in profiles
    assert "docs.resolve" in profiles
    assert "fetch.extract" in profiles
    assert "map.site" in profiles
    text = json.dumps(profiles).lower()
    assert "anysearch" not in text
    assert "vertical_search" not in text
    assert "deep_research" not in text


def test_operation_config_reorders_and_disables(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-key")
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-key")
    monkeypatch.setenv(
        "SMART_SEARCH_OPERATION_CONFIG",
        json.dumps({"search.sources": {"providers": ["zhipu", "exa"], "disabled": ["zhipu"]}}),
    )
    candidates, missing = service.operation_candidates("search.sources")
    assert candidates == ["exa"]
    assert missing == set()


def test_operation_config_can_disable_fallback_and_set_timeout(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-key")
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-key")
    monkeypatch.setenv(
        "SMART_SEARCH_OPERATION_CONFIG",
        json.dumps(
            {
                "search.sources": {
                    "providers": ["zhipu", "exa"],
                    "fallback": "off",
                    "timeout": 12,
                }
            }
        ),
    )

    candidates, missing = service.operation_candidates("search.sources")

    assert candidates == ["zhipu"]
    assert missing == set()
    assert service.operation_policy("search.sources") == {"fallback": False, "timeout": 12.0}


def test_operation_candidates_require_features(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-key")
    candidates, missing = service.operation_candidates(
        "search.sources",
        required_features={"semantic", "highlights"},
    )
    assert candidates == ["exa"]
    assert missing == set()


def test_provider_profiles_declare_exact_operations():
    profiles = service.provider_profiles()

    assert profiles["context7"]["operations"] == ["docs.resolve", "docs.search"]
    assert profiles["exa"]["operations"] == ["docs.search", "search.similar", "search.sources"]
    assert profiles["firecrawl"]["operations"] == ["fetch.content", "fetch.extract", "search.sources"]


@pytest.mark.asyncio
async def test_docs_tree_does_not_cross_fallback(monkeypatch):
    monkeypatch.delenv("ZHIPU_MCP_API_KEY", raising=False)
    result = await service.docs_tree("owner/repo")
    assert result["ok"] is False
    assert result["operation"] == "tree"
    assert result["error_type"] == "config_error"


@pytest.mark.asyncio
async def test_search_sources_feature_negotiation_and_normalization(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-key")

    async def fake_exa(*args, **kwargs):
        return {"ok": True, "results": [{"title": "Result", "url": "https://example.com", "description": "Snippet"}]}

    monkeypatch.setattr(service, "exa_search", fake_exa)
    result = await service.search_sources("q", mode="semantic", include_highlights=True)
    assert result["ok"] is True
    assert result["operation"] == "sources"
    assert result["results"][0]["url"] == "https://example.com"
    assert "provider_attempts" not in result


@pytest.mark.asyncio
async def test_fetch_extract_does_not_fall_back_to_content(monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    result = await service.fetch_extract("https://example.com")
    assert result["ok"] is False
    assert result["operation"] == "extract"
    assert result["error_type"] == "config_error"
    assert result["data"] is None


@pytest.mark.asyncio
async def test_fetch_extract_uses_structured_firecrawl(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-key")

    async def fake_extract(url, *, max_length=20000, schema=None):
        return {"ok": True, "data": {"title": "Page"}, "raw_evidence": '{"title":"Page"}'}

    monkeypatch.setattr(service, "firecrawl_extract", fake_extract)
    result = await service.fetch_extract("https://example.com", schema={"type": "object"})
    assert result["ok"] is True
    assert result["data"] == {"title": "Page"}


@pytest.mark.asyncio
async def test_map_site_is_separate_operation(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-key")

    async def fake_map(url, **kwargs):
        return {"ok": True, "results": [{"url": f"{url}/docs"}]}

    monkeypatch.setattr(service, "map_site", fake_map)
    result = await service.map_site_operation("https://example.com", limit=3)
    assert result["ok"] is True
    assert result["operation"] == "site"
    assert result["entries"][0]["url"].endswith("/docs")


def test_diagnose_and_dev_command_tree():
    parser = cli.build_parser()
    assert parser.parse_args(["diagnose", "provider", "openai-compatible"]).diagnose_command == "provider"
    assert parser.parse_args(["diagnose", "route", "query"]).diagnose_command == "route"
    assert parser.parse_args(["diagnose", "route-calibrate"]).diagnose_command == "route-calibrate"
    assert parser.parse_args(["diagnose", "smoke"]).diagnose_command == "smoke"
    assert parser.parse_args(["dev", "regression"]).dev_command == "regression"
