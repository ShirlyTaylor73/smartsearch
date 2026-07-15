import json

import pytest

from smart_search import cli


def test_version_flag(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_get_version", lambda: "9.9.9-test")
    parser = cli.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])
    assert exc.value.code == 0
    assert "smart-search" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    [
        ["search", "answer", "--help"],
        ["search", "sources", "--help"],
        ["search", "similar", "--help"],
        ["docs", "resolve", "--help"],
        ["docs", "search", "--help"],
        ["docs", "tree", "--help"],
        ["docs", "read", "--help"],
        ["fetch", "content", "--help"],
        ["fetch", "extract", "--help"],
        ["map", "site", "--help"],
        ["diagnose", "provider", "--help"],
        ["diagnose", "route", "--help"],
        ["diagnose", "smoke", "--help"],
        ["dev", "regression", "--help"],
        ["doctor", "--help"],
        ["setup", "--help"],
        ["config", "list", "--help"],
        ["skills", "status", "--help"],
    ],
)
def test_public_help(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 0
    assert "usage:" in capsys.readouterr().out


def test_legacy_root_operations_are_normalized():
    assert cli._normalize_legacy_argv(["search", "query"]) == ["search", "answer", "query"]
    assert cli._normalize_legacy_argv(["fetch", "https://example.com"]) == ["fetch", "content", "https://example.com"]
    assert cli._normalize_legacy_argv(["map", "https://example.com"]) == ["map", "site", "https://example.com"]
    assert cli._normalize_legacy_argv(["diagnose", "openai-compatible"]) == ["diagnose", "provider", "openai-compatible"]


def test_legacy_commands_emit_migration_hint(monkeypatch, capsys):
    async def fake(*args, **kwargs):
        return {"ok": True, "capability": "search", "operation": "answer", "content": "ok", "sources": [], "elapsed_ms": 1}

    monkeypatch.setattr(cli.service, "search_answer", fake)

    assert cli.main(["search", "legacy query"]) == 0
    captured = capsys.readouterr()
    assert "smart-search search answer QUERY" in captured.err
    assert json.loads(captured.out)["ok"] is True


def test_removed_commands_fail(capsys):
    for command in ("anysearch-search", "anysearch-domains", "deep", "research"):
        with pytest.raises(SystemExit) as exc:
            cli.main([command])
        assert exc.value.code == 2
    capsys.readouterr()


def test_search_answer_calls_operation_service(monkeypatch, capsys):
    async def fake(query, **kwargs):
        return {"ok": True, "capability": "search", "operation": "answer", "content": query, "sources": [], "elapsed_ms": 1}

    monkeypatch.setattr(cli.service, "search_answer", fake)
    assert cli.main(["search", "answer", "hello"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["operation"] == "answer"


def test_search_sources_passes_filters(monkeypatch, capsys):
    captured = {}

    async def fake(query, **kwargs):
        captured.update(kwargs)
        return {"ok": True, "capability": "search", "operation": "sources", "content": "", "sources": [], "results": [], "elapsed_ms": 1}

    monkeypatch.setattr(cli.service, "search_sources", fake)
    assert cli.main(["search", "sources", "q", "--mode", "semantic", "--include-highlights", "--include-domains", "example.com"]) == 0
    assert captured["mode"] == "semantic"
    assert captured["include_highlights"] is True
    assert captured["include_domains"] == ["example.com"]
    capsys.readouterr()


@pytest.mark.parametrize(
    ("argv", "service_name", "operation"),
    [
        (["search", "similar", "https://example.com"], "search_similar", "similar"),
        (["docs", "resolve", "react"], "docs_resolve", "resolve"),
        (["docs", "search", "hooks"], "docs_search", "search"),
        (["docs", "tree", "owner/repo"], "docs_tree", "tree"),
        (["docs", "read", "owner/repo", "README.md"], "docs_read", "read"),
        (["fetch", "content", "https://example.com"], "fetch_content", "content"),
        (["fetch", "extract", "https://example.com"], "fetch_extract", "extract"),
        (["map", "site", "https://example.com"], "map_site_operation", "site"),
    ],
)
def test_operation_dispatch(monkeypatch, capsys, argv, service_name, operation):
    async def fake(*args, **kwargs):
        return {"ok": True, "capability": argv[0], "operation": operation, "content": "ok", "sources": [], "elapsed_ms": 1}

    monkeypatch.setattr(cli.service, service_name, fake)
    assert cli.main(argv) == 0
    assert json.loads(capsys.readouterr().out)["operation"] == operation


def test_output_file(monkeypatch, tmp_path, capsys):
    async def fake(*args, **kwargs):
        return {"ok": True, "capability": "search", "operation": "answer", "content": "answer", "sources": [], "elapsed_ms": 1}

    monkeypatch.setattr(cli.service, "search_answer", fake)
    output = tmp_path / "answer.json"
    assert cli.main(["search", "answer", "q", "--output", str(output)]) == 0
    assert json.loads(output.read_text())["content"] == "answer"
    assert json.loads(capsys.readouterr().out)["content"] == "answer"


def test_diagnose_operation_dispatch(monkeypatch, capsys):
    async def fake(capability, operation=""):
        return {"ok": True, "capability": capability, "operation": operation, "checks": []}

    monkeypatch.setattr(cli.service, "diagnose_operation", fake)
    assert cli.main(["diagnose", "docs", "tree"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["capability"] == "docs"
    assert data["operation"] == "tree"


def test_config_commands(monkeypatch, capsys):
    monkeypatch.setattr(cli.service, "config_list", lambda show_secrets=False: {"ok": True, "config": {}})
    assert cli.main(["config", "list"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
