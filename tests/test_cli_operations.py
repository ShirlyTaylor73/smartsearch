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


def test_operation_candidates_require_features(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-key")
    candidates, missing = service.operation_candidates(
        "search.sources",
        required_features={"semantic", "highlights"},
    )
    assert candidates == ["exa"]
    assert missing == set()


@pytest.mark.asyncio
async def test_docs_tree_does_not_cross_fallback(monkeypatch):
    monkeypatch.delenv("ZHIPU_MCP_API_KEY", raising=False)
    result = await service.docs_tree("owner/repo")
    assert result["ok"] is False
    assert result["operation"] == "tree"
    assert result["error_type"] == "config_error"


def test_diagnose_and_dev_command_tree():
    parser = cli.build_parser()
    assert parser.parse_args(["diagnose", "provider", "openai-compatible"]).diagnose_command == "provider"
    assert parser.parse_args(["diagnose", "route", "query"]).diagnose_command == "route"
    assert parser.parse_args(["diagnose", "route-calibrate"]).diagnose_command == "route-calibrate"
    assert parser.parse_args(["diagnose", "smoke"]).diagnose_command == "smoke"
    assert parser.parse_args(["dev", "regression"]).dev_command == "regression"
