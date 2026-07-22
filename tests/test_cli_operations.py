import pytest

from smart_search import cli, service


def test_parser_sets_current_operations():
    parser = cli.build_parser()
    commands = [
        ["search", "answer", "q"], ["search", "sources", "q"],
        ["docs", "resolve", "react"], ["docs", "search", "hooks"],
        ["docs", "tree", "owner/repo"], ["docs", "read", "owner/repo", "README.md"],
        ["fetch", "content", "https://example.com"], ["fetch", "extract", "https://example.com"],
        ["map", "site", "https://example.com"],
    ]
    for argv in commands:
        args = parser.parse_args(argv)
        assert args.command == argv[0]
        assert args.operation == argv[1]


def test_profiles_are_fixed_descriptors():
    profiles = service.operation_profiles()
    assert len(profiles) == 9
    assert profiles["search.sources"]["responsible_provider"] == "exa"
    assert profiles["fetch.content"]["responsible_provider"] == "firecrawl"
    assert all("executor" in profile and "providers" not in profile for profile in profiles.values())


def test_operation_timeout_override(monkeypatch):
    monkeypatch.setenv("SMART_SEARCH_OPERATION_TIMEOUTS", '{"search.sources":12}')
    assert service.operation_policy("search.sources") == {"timeout": 12.0}


@pytest.mark.asyncio
async def test_missing_provider_stops_operation(monkeypatch):
    monkeypatch.delenv("ZHIPU_MCP_API_KEY", raising=False)
    result = await service.docs_tree("owner/repo")
    assert result["error_type"] == "config_error"


def test_diagnose_and_dev_command_tree():
    parser = cli.build_parser()
    assert parser.parse_args(["diagnose", "provider", "exa"]).diagnose_command == "provider"
    assert parser.parse_args(["diagnose", "route", "query"]).diagnose_command == "route"
    assert parser.parse_args(["diagnose", "route-calibrate"]).diagnose_command == "route-calibrate"
    assert parser.parse_args(["diagnose", "smoke"]).diagnose_command == "smoke"
    assert parser.parse_args(["dev", "regression"]).dev_command == "regression"
