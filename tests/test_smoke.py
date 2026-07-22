import pytest

from smart_search import service


@pytest.mark.asyncio
async def test_mock_smoke_covers_public_operation_matrix():
    result = await service.smoke("mock")
    assert result["ok"] is True
    case_names = {case["name"] for case in result["cases"]}
    assert {f"operation profile {operation}" for operation in service.OPERATION_PROFILES} <= case_names
    assert "no cross-provider fallback" in case_names


@pytest.mark.asyncio
async def test_live_smoke_reports_missing_fixed_executors(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    result = await service.smoke("live")
    assert result["mode"] == "live"
    sources = next(case for case in result["cases"] if case["name"] == "search.sources")
    assert sources["ok"] is False
    assert sources["responsible_provider"] == "exa"


@pytest.mark.asyncio
async def test_invalid_smoke_mode_is_parameter_error():
    result = await service.smoke("bogus")
    assert result["error_type"] == "parameter_error"
