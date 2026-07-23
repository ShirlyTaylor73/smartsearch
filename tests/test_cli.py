import json

import pytest

from smart_search import cli


@pytest.mark.parametrize("argv", [
    ["search", "answer", "--help"], ["search", "sources", "--help"],
    ["docs", "resolve", "--help"], ["docs", "search", "--help"],
    ["docs", "tree", "--help"], ["docs", "read", "--help"],
    ["fetch", "content", "--help"], ["fetch", "extract", "--help"],
    ["map", "site", "--help"], ["diagnose", "provider", "--help"],
    ["diagnose", "route", "--help"], ["diagnose", "smoke", "--help"],
    ["dev", "regression", "--help"], ["doctor", "--help"],
    ["setup", "--help"], ["config", "list", "--help"],
    ["skills", "install", "--help"], ["skills", "uninstall", "--help"],
    ["skills", "status", "--help"], ["skills", "update", "--help"],
])
def test_public_help(argv):
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 0


def test_removed_commands_are_parse_errors():
    parser = cli.build_parser()
    for argv in (["search", "similar", "https://example.com"], ["exa-search", "q"], ["zhipu-search", "q"]):
        with pytest.raises(SystemExit):
            parser.parse_args(argv)


def test_search_answer_dispatch(monkeypatch, capsys):
    async def fake(query, **kwargs):
        return {"ok": True, "capability": "search", "operation": "answer", "content": query, "sources": [], "elapsed_ms": 1}

    monkeypatch.setattr(cli.service, "search_answer", fake)
    assert cli.main(["search", "answer", "hello"]) == 0
    assert json.loads(capsys.readouterr().out)["content"] == "hello"


def test_search_sources_passes_filters(monkeypatch):
    captured = {}

    async def fake(query, **kwargs):
        captured.update(kwargs)
        return {"ok": True, "capability": "search", "operation": "sources", "content": "", "sources": [], "results": [], "elapsed_ms": 1}

    monkeypatch.setattr(cli.service, "search_sources", fake)
    assert cli.main(["search", "sources", "q", "--include-highlights", "--include-domains", "example.com"]) == 0
    assert captured["include_highlights"] is True
    assert captured["include_domains"] == ["example.com"]


@pytest.mark.parametrize(("argv", "service_name"), [
    (["docs", "resolve", "react"], "docs_resolve"),
    (["docs", "search", "hooks"], "docs_search"),
    (["docs", "tree", "owner/repo"], "docs_tree"),
    (["docs", "read", "owner/repo", "README.md"], "docs_read"),
    (["fetch", "content", "https://example.com"], "fetch_content"),
    (["fetch", "extract", "https://example.com"], "fetch_extract"),
    (["map", "site", "https://example.com"], "map_site_operation"),
])
def test_operation_dispatch(monkeypatch, argv, service_name):
    async def fake(*args, **kwargs):
        return {"ok": True, "capability": argv[0], "operation": argv[1], "content": "ok", "sources": [], "elapsed_ms": 1}

    monkeypatch.setattr(cli.service, service_name, fake)
    assert cli.main(argv) == 0


def test_output_file(monkeypatch, tmp_path, capsys):
    async def fake(*args, **kwargs):
        return {"ok": True, "capability": "search", "operation": "answer", "content": "answer", "sources": [], "elapsed_ms": 1}

    monkeypatch.setattr(cli.service, "search_answer", fake)
    output = tmp_path / "answer.json"
    assert cli.main(["search", "answer", "q", "--output", str(output)]) == 0
    assert json.loads(output.read_text())["content"] == "answer"
    assert capsys.readouterr().out == ""
