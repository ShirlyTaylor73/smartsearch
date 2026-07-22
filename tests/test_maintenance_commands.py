import pytest

from smart_search import cli, service


def test_setup_only_accepts_minimal_provider_options():
    parser = cli.build_parser()
    args = parser.parse_args(["setup", "--non-interactive", "--grok-transport", "xai-responses", "--exa-search-type", "auto"])
    assert args.grok_transport == "xai-responses"
    for removed in ("--tavily-key", "--jina-key", "--zhipu-key", "--fallback-mode", "--operation-config"):
        with pytest.raises(SystemExit):
            parser.parse_args(["setup", removed, "value"])


def test_config_rejects_removed_provider_keys(monkeypatch, tmp_path):
    monkeypatch.setenv("SMART_SEARCH_CONFIG_DIR", str(tmp_path))
    service.config._config_file = None
    service.config._config_dir_source = None
    result = service.config_set("TAVILY_API_KEY", "secret")
    assert result["ok"] is False
    assert result["error_type"] == "parameter_error"


@pytest.mark.asyncio
async def test_diagnose_reports_responsible_provider(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "secret")
    result = await service.diagnose_operation("search", "sources")
    assert result["checks"] == [
        {
            "operation": "search.sources",
            "responsible_provider": "exa",
            "configured": True,
            "missing_config": [],
            "executor": "search_sources",
            "timeout": 30.0,
            "detail": "exa",
        }
    ]


@pytest.mark.asyncio
async def test_doctor_lists_every_public_operation():
    result = await service.doctor()
    assert set(result["operation_status"]) == set(service.OPERATION_PROFILES)
    assert all("responsible_provider" in item for item in result["operation_status"].values())


def test_diagnose_provider_choices_are_minimal_set():
    parser = cli.build_parser()
    for provider in ("xai-responses", "openai-compatible", "exa", "context7", "zhipu-mcp-zread", "firecrawl"):
        assert parser.parse_args(["diagnose", "provider", provider]).provider == provider
    with pytest.raises(SystemExit):
        parser.parse_args(["diagnose", "provider", "tavily"])
