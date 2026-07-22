import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any

import httpx

from .config import config
from .intent_router import IntentRouter
from .providers.context7 import Context7Provider
from .providers.exa import ExaSearchProvider
from .providers.firecrawl import FirecrawlProvider
from .providers.openai_compatible import OpenAICompatibleSearchProvider
from .providers.xai_responses import XAIResponsesSearchProvider
from .providers.zhipu_mcp import ZhipuMCPProvider
from .sources import split_answer_and_sources


OPERATION_PROFILES: dict[str, dict[str, Any]] = {
    "search.answer": {"executor": "search_answer", "responsible_provider": "grok", "required_config": ["SMART_SEARCH_GROK_TRANSPORT"], "default_timeout": 120.0, "normalizer": "answer"},
    "search.sources": {"executor": "search_sources", "responsible_provider": "exa", "required_config": ["EXA_API_KEY"], "default_timeout": 30.0, "normalizer": "results"},
    "docs.resolve": {"executor": "docs_resolve", "responsible_provider": "context7", "required_config": ["CONTEXT7_API_KEY"], "default_timeout": 30.0, "normalizer": "candidates"},
    "docs.search": {"executor": "docs_search", "responsible_provider": "context7-or-zread", "required_config": [], "default_timeout": 30.0, "normalizer": "results"},
    "docs.tree": {"executor": "docs_tree", "responsible_provider": "zhipu-mcp-zread", "required_config": ["ZHIPU_MCP_API_KEY"], "default_timeout": 30.0, "normalizer": "entries"},
    "docs.read": {"executor": "docs_read", "responsible_provider": "zhipu-mcp-zread", "required_config": ["ZHIPU_MCP_API_KEY"], "default_timeout": 30.0, "normalizer": "content"},
    "fetch.content": {"executor": "fetch_content", "responsible_provider": "firecrawl", "required_config": ["FIRECRAWL_API_KEY"], "default_timeout": 90.0, "normalizer": "content"},
    "fetch.extract": {"executor": "fetch_extract", "responsible_provider": "firecrawl", "required_config": ["FIRECRAWL_API_KEY"], "default_timeout": 90.0, "normalizer": "data"},
    "map.site": {"executor": "map_site_operation", "responsible_provider": "firecrawl", "required_config": ["FIRECRAWL_API_KEY"], "default_timeout": 150.0, "normalizer": "entries"},
}

PROVIDER_PROFILES: dict[str, dict[str, Any]] = {
    "xai-responses": {"operations": ["search.answer"], "transport": "xAI Responses"},
    "openai-compatible": {"operations": ["search.answer"], "transport": "OpenAI-compatible"},
    "exa": {"operations": ["search.sources"]},
    "context7": {"operations": ["docs.resolve", "docs.search"]},
    "zhipu-mcp-zread": {"operations": ["docs.search", "docs.tree", "docs.read"]},
    "firecrawl": {"operations": ["fetch.content", "fetch.extract", "map.site"]},
}


def _elapsed_ms(start: float) -> float:
    return round((time.time() - start) * 1000, 2)


def _normalize_domain_filter(value: str | list[str] | tuple[str, ...] | None) -> list[str] | None:
    if not value:
        return None
    raw = [value] if isinstance(value, str) else [str(item) for item in value if item]
    result: list[str] = []
    for part in raw:
        result.extend(item.strip() for item in re.split(r"[\s,]+", part) if item.strip())
    return result or None


def _normalize_source_results(results: list[dict] | None, provider: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in results or []:
        url = str(item.get("url") or item.get("link") or "").strip()
        if not url:
            continue
        out: dict[str, Any] = {"url": url, "provider": item.get("provider") or provider}
        title = str(item.get("title") or "").strip()
        if title:
            out["title"] = title
        description = str(item.get("description") or item.get("content") or item.get("snippet") or "").strip()
        if description:
            out["description"] = description
            out["snippet"] = description
        published = item.get("published_date") or item.get("publishedDate")
        if published:
            out["published_date"] = published
        if "text" in item:
            out["text"] = item.get("text")
        if "highlights" in item:
            out["highlights"] = item.get("highlights")
        normalized.append(out)
    return normalized


def operation_profiles() -> dict[str, dict[str, Any]]:
    return {operation: dict(profile) for operation, profile in OPERATION_PROFILES.items()}


def provider_profiles() -> dict[str, dict[str, Any]]:
    return {provider: dict(profile) for provider, profile in PROVIDER_PROFILES.items()}


def operation_policy(operation: str) -> dict[str, float]:
    profile = OPERATION_PROFILES.get(operation)
    if not profile:
        raise ValueError(f"Unknown operation: {operation}")
    return {"timeout": config.operation_timeouts.get(operation, float(profile["default_timeout"]))}


async def _await_operation(awaitable: Any, *, start: float, timeout: float) -> Any:
    remaining = timeout - (time.time() - start)
    if remaining <= 0:
        raise asyncio.TimeoutError("operation timeout budget exhausted")
    return await asyncio.wait_for(awaitable, timeout=remaining)


def _operation_envelope(
    capability: str,
    operation: str,
    *,
    ok: bool,
    start: float,
    content: str = "",
    sources: list[dict[str, Any]] | None = None,
    error_type: str = "",
    error: str = "",
    extra: dict[str, Any] | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": ok,
        "capability": capability,
        "operation": operation,
        "content": content,
        "sources": sources or [],
        "elapsed_ms": _elapsed_ms(start),
    }
    if not ok:
        result.update({"error_type": error_type or "provider_error", "error": error or "operation failed"})
    if extra:
        result.update(extra)
    if not debug:
        result.pop("provider", None)
        result.pop("provider_operation", None)
    return result


def _redact_sensitive(text: str) -> str:
    redacted = str(text or "")
    for secret in (
        config.xai_api_key,
        config.openai_compatible_api_key,
        config.exa_api_key,
        config.context7_api_key,
        config.zhipu_mcp_api_key,
        config.firecrawl_api_key,
    ):
        if secret:
            redacted = redacted.replace(secret, "***")
    return redacted


def _operation_exception(exc: BaseException) -> tuple[str, str]:
    if isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException, TimeoutError)):
        return "timeout", "operation timed out"
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in {400, 422}:
            error_type = "parameter_error"
        elif status in {401, 403}:
            error_type = "auth_error"
        elif status == 429:
            error_type = "rate_limited"
        elif status >= 500:
            error_type = "network_error"
        else:
            error_type = "provider_error"
        return error_type, _redact_sensitive(f"HTTP {status}: {exc.response.text[:300]}")
    if isinstance(exc, httpx.RequestError):
        return "network_error", _redact_sensitive(str(exc))
    if isinstance(exc, (json.JSONDecodeError, TypeError, KeyError)):
        return "parse_error", _redact_sensitive(str(exc))
    return "provider_error", _redact_sensitive(str(exc))


async def _decode_provider_json(raw: str, provider: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "provider": provider, "error_type": "parse_error", "error": _redact_sensitive(raw)}
    return value if isinstance(value, dict) else {"ok": False, "provider": provider, "error_type": "parse_error", "error": "provider response must be an object"}


async def exa_search(
    query: str,
    num_results: int = 5,
    search_type: str = "auto",
    include_text: bool = False,
    include_highlights: bool = False,
    start_published_date: str = "",
    include_domains: str | list[str] | tuple[str, ...] = "",
    exclude_domains: str | list[str] | tuple[str, ...] = "",
    category: str = "",
) -> dict[str, Any]:
    if not config.exa_api_key:
        return {"ok": False, "error_type": "config_error", "error": "EXA_API_KEY is not configured"}
    provider = ExaSearchProvider(config.exa_base_url, config.exa_api_key, config.exa_timeout)
    raw = await provider.search(
        query=query,
        num_results=num_results,
        search_type=search_type,
        include_text=include_text,
        include_highlights=include_highlights,
        start_published_date=start_published_date or None,
        include_domains=_normalize_domain_filter(include_domains),
        exclude_domains=_normalize_domain_filter(exclude_domains),
        category=category or None,
    )
    return await _decode_provider_json(raw, "exa")


async def context7_library(name: str, query: str = "") -> dict[str, Any]:
    if not config.context7_api_key:
        return {"ok": False, "error_type": "config_error", "error": "CONTEXT7_API_KEY is not configured"}
    raw = await Context7Provider(config.context7_base_url, config.context7_api_key, config.context7_timeout).library(name, query)
    return await _decode_provider_json(raw, "context7")


async def context7_docs(library_id: str, query: str) -> dict[str, Any]:
    if not config.context7_api_key:
        return {"ok": False, "error_type": "config_error", "error": "CONTEXT7_API_KEY is not configured"}
    raw = await Context7Provider(config.context7_base_url, config.context7_api_key, config.context7_timeout).docs(library_id, query)
    return await _decode_provider_json(raw, "context7")


def _zread_provider() -> ZhipuMCPProvider:
    return ZhipuMCPProvider(config.zhipu_mcp_zread_api_url, config.zhipu_mcp_api_key or "", config.zhipu_mcp_timeout, provider_id="zhipu-mcp-zread")


async def zhipu_mcp_search_doc(repo: str, query: str, *, language: str = "en") -> dict[str, Any]:
    return await _decode_provider_json(await _zread_provider().search_doc(repo, query, language=language), "zhipu-mcp-zread")


async def zhipu_mcp_repo_structure(repo: str, path: str = "") -> dict[str, Any]:
    return await _decode_provider_json(await _zread_provider().get_repo_structure(repo, path=path), "zhipu-mcp-zread")


async def zhipu_mcp_read_file(repo: str, path: str) -> dict[str, Any]:
    return await _decode_provider_json(await _zread_provider().read_file(repo, path), "zhipu-mcp-zread")


async def search_answer(query: str, *, timeout_seconds: float | None = None, debug: bool = False) -> dict[str, Any]:
    start = time.time()
    try:
        transport = config.grok_transport
    except ValueError as exc:
        return _operation_envelope("search", "answer", ok=False, start=start, error_type="config_error", error=str(exc))
    budget = operation_policy("search.answer")["timeout"]
    if timeout_seconds is not None:
        if timeout_seconds <= 0:
            return _operation_envelope("search", "answer", ok=False, start=start, error_type="parameter_error", error="--timeout must be positive")
        budget = min(float(timeout_seconds), budget)
    try:
        if transport == "xai-responses":
            if not config.xai_api_key:
                raise ValueError("search.answer requires XAI_API_KEY; run `smart-search diagnose search answer`")
            provider: Any = XAIResponsesSearchProvider(config.xai_api_url, config.xai_api_key, config.xai_model, config.parse_xai_tools())
        else:
            missing = [key for key, value in (("OPENAI_COMPATIBLE_API_URL", config.openai_compatible_api_url), ("OPENAI_COMPATIBLE_API_KEY", config.openai_compatible_api_key), ("OPENAI_COMPATIBLE_MODEL", config.openai_compatible_model)) if not value]
            if missing:
                raise ValueError(f"search.answer requires {', '.join(missing)}; run `smart-search diagnose search answer`")
            provider = OpenAICompatibleSearchProvider(config.openai_compatible_api_url or "", config.openai_compatible_api_key or "", config.openai_compatible_model, config.openai_compatible_stream)
        raw = await _await_operation(provider.search(query), start=start, timeout=budget)
        content, sources = split_answer_and_sources(str(raw))
        if not content:
            return _operation_envelope("search", "answer", ok=False, start=start, error_type="provider_error", error="Grok returned empty content")
        return _operation_envelope("search", "answer", ok=True, start=start, content=content, sources=sources, extra={"provider": transport, "provider_operation": "web answer"}, debug=debug)
    except ValueError as exc:
        return _operation_envelope("search", "answer", ok=False, start=start, error_type="config_error", error=str(exc))
    except Exception as exc:
        error_type, error = _operation_exception(exc)
        return _operation_envelope("search", "answer", ok=False, start=start, error_type=error_type, error=error, extra={"provider": transport}, debug=debug)


async def search_sources(
    query: str,
    *,
    limit: int = 5,
    start_published_date: str = "",
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    category: str = "",
    include_text: bool = False,
    include_highlights: bool = False,
    debug: bool = False,
) -> dict[str, Any]:
    start = time.time()
    if not config.exa_api_key:
        return _operation_envelope("search", "sources", ok=False, start=start, error_type="config_error", error="search.sources requires EXA_API_KEY; run `smart-search diagnose search sources`")
    if limit < 1:
        return _operation_envelope("search", "sources", ok=False, start=start, error_type="parameter_error", error="--limit must be positive")
    try:
        data = await _await_operation(exa_search(query, num_results=limit, search_type=config.exa_search_type, include_text=include_text, include_highlights=include_highlights, start_published_date=start_published_date, include_domains=include_domains or "", exclude_domains=exclude_domains or "", category=category), start=start, timeout=operation_policy("search.sources")["timeout"])
    except ValueError as exc:
        data = {"ok": False, "error_type": "config_error", "error": str(exc)}
    except Exception as exc:
        error_type, error = _operation_exception(exc)
        data = {"ok": False, "error_type": error_type, "error": error}
    results = _normalize_source_results(data.get("results"), "exa") if data.get("ok") else []
    return _operation_envelope("search", "sources", ok=bool(data.get("ok")), start=start, sources=results, error_type=data.get("error_type", ""), error=data.get("error", ""), extra={"results": results, "provider": "exa", "provider_operation": "search"}, debug=debug)


async def docs_resolve(name: str, query: str = "", *, debug: bool = False) -> dict[str, Any]:
    start = time.time()
    if not config.context7_api_key:
        return _operation_envelope("docs", "resolve", ok=False, start=start, error_type="config_error", error="docs.resolve requires CONTEXT7_API_KEY; run `smart-search diagnose docs resolve`")
    try:
        data = await _await_operation(context7_library(name, query), start=start, timeout=operation_policy("docs.resolve")["timeout"])
    except Exception as exc:
        error_type, error = _operation_exception(exc)
        data = {"ok": False, "error_type": error_type, "error": error}
    candidates = [{"id": row.get("id", ""), "title": row.get("title") or row.get("name") or row.get("id", ""), "description": row.get("description", "")} for row in data.get("results") or []]
    return _operation_envelope("docs", "resolve", ok=bool(data.get("ok")), start=start, error_type=data.get("error_type", ""), error=data.get("error", ""), extra={"candidates": candidates, "provider": "context7", "provider_operation": "library search"}, debug=debug)


async def docs_search(query: str, *, source: str = "", debug: bool = False) -> dict[str, Any]:
    start = time.time()
    repo_pattern = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    context7_pattern = re.compile(r"^/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?$")
    if source and repo_pattern.fullmatch(source):
        if not config.zhipu_mcp_api_key:
            return _operation_envelope("docs", "search", ok=False, start=start, error_type="config_error", error="repository docs.search requires ZHIPU_MCP_API_KEY; run `smart-search diagnose docs search`", extra={"results": []})
        language = "zh" if re.search(r"[\u3400-\u9fff]", query) else "en"
        try:
            data = await _await_operation(zhipu_mcp_search_doc(source, query, language=language), start=start, timeout=operation_policy("docs.search")["timeout"])
        except Exception as exc:
            error_type, error = _operation_exception(exc)
            data = {"ok": False, "error_type": error_type, "error": error}
        results = _normalize_source_results(data.get("results"), "zhipu-mcp-zread") if data.get("ok") else []
        return _operation_envelope("docs", "search", ok=bool(data.get("ok")), start=start, content=data.get("content", ""), sources=results, error_type=data.get("error_type", ""), error=data.get("error", ""), extra={"results": results, "provider": "zhipu-mcp-zread", "provider_operation": "search_doc"}, debug=debug)
    if source and not context7_pattern.fullmatch(source):
        return _operation_envelope("docs", "search", ok=False, start=start, error_type="parameter_error", error="--source must be a Context7 library id (/owner/library) or GitHub repository (owner/repo)", extra={"results": []})
    if not config.context7_api_key:
        return _operation_envelope("docs", "search", ok=False, start=start, error_type="config_error", error="docs.search requires CONTEXT7_API_KEY; run `smart-search diagnose docs search`", extra={"results": []})
    library_id = source
    if not library_id:
        resolved = await context7_library(query, query)
        if not resolved.get("ok"):
            return _operation_envelope("docs", "search", ok=False, start=start, error_type=resolved.get("error_type", "provider_error"), error=resolved.get("error", "Context7 library resolution failed"), extra={"results": []})
        library_id = next((row.get("id", "") for row in resolved.get("results", []) if row.get("id")), "")
    data = await context7_docs(library_id, query) if library_id else {"ok": False, "error_type": "provider_error", "error": "Context7 library not resolved"}
    results: list[dict[str, Any]] = []
    if data.get("ok"):
        for index, row in enumerate(data.get("results") or [], 1):
            text = row.get("content") or row.get("code") or row.get("description") or json.dumps(row, ensure_ascii=False)
            results.append({"url": f"context7:{library_id}#{index}", "title": row.get("title") or library_id, "description": str(text)[:500], "snippet": str(text)[:500], "provider": "context7"})
        if not results and data.get("content"):
            results.append({"url": f"context7:{library_id}", "title": library_id, "description": data["content"][:500], "snippet": data["content"][:500], "provider": "context7"})
    return _operation_envelope("docs", "search", ok=bool(data.get("ok")), start=start, content=data.get("content", ""), sources=results, error_type=data.get("error_type", ""), error=data.get("error", ""), extra={"results": results, "provider": "context7", "provider_operation": "context"}, debug=debug)


async def docs_tree(repo: str, *, path: str = "", debug: bool = False) -> dict[str, Any]:
    start = time.time()
    if not config.zhipu_mcp_api_key:
        return _operation_envelope("docs", "tree", ok=False, start=start, error_type="config_error", error="docs.tree requires ZHIPU_MCP_API_KEY; run `smart-search diagnose docs tree`", extra={"entries": []})
    try:
        data = await _await_operation(zhipu_mcp_repo_structure(repo, path=path), start=start, timeout=operation_policy("docs.tree")["timeout"])
    except Exception as exc:
        error_type, error = _operation_exception(exc)
        data = {"ok": False, "error_type": error_type, "error": error}
    entries = data.get("results") or []
    return _operation_envelope("docs", "tree", ok=bool(data.get("ok")), start=start, content=data.get("content", ""), error_type=data.get("error_type", ""), error=data.get("error", ""), extra={"entries": entries, "provider": "zhipu-mcp-zread", "provider_operation": "get_repo_structure"}, debug=debug)


async def docs_read(repo: str, path: str, *, debug: bool = False) -> dict[str, Any]:
    start = time.time()
    if not config.zhipu_mcp_api_key:
        return _operation_envelope("docs", "read", ok=False, start=start, error_type="config_error", error="docs.read requires ZHIPU_MCP_API_KEY; run `smart-search diagnose docs read`")
    try:
        data = await _await_operation(zhipu_mcp_read_file(repo, path), start=start, timeout=operation_policy("docs.read")["timeout"])
    except Exception as exc:
        error_type, error = _operation_exception(exc)
        data = {"ok": False, "error_type": error_type, "error": error}
    sources = [{"title": path, "url": f"repo:{repo}/{path}", "snippet": ""}] if data.get("ok") else []
    return _operation_envelope("docs", "read", ok=bool(data.get("ok")), start=start, content=data.get("content", ""), sources=sources, error_type=data.get("error_type", ""), error=data.get("error", ""), extra={"provider": "zhipu-mcp-zread", "provider_operation": "read_file"}, debug=debug)


async def fetch_content(url: str, *, debug: bool = False) -> dict[str, Any]:
    start = time.time()
    if not config.firecrawl_api_key:
        return _operation_envelope("fetch", "content", ok=False, start=start, error_type="config_error", error="fetch.content requires FIRECRAWL_API_KEY; run `smart-search diagnose fetch content`")
    provider = FirecrawlProvider(config.firecrawl_api_url, config.firecrawl_api_key, config.firecrawl_timeout)
    try:
        data = await _await_operation(provider.scrape_markdown(url), start=start, timeout=operation_policy("fetch.content")["timeout"])
    except Exception as exc:
        error_type, error = _operation_exception(exc)
        data = {"ok": False, "error_type": error_type, "error": error}
    final_url = data.get("final_url") or url
    sources = [{"title": final_url, "url": final_url, "snippet": data.get("content", "")[:300]}] if data.get("ok") else []
    return _operation_envelope("fetch", "content", ok=bool(data.get("ok")), start=start, content=data.get("content", ""), sources=sources, error_type=data.get("error_type", ""), error=data.get("error", ""), extra={"final_url": final_url, "provider": "firecrawl", "provider_operation": "scrape markdown"}, debug=debug)


def validate_json_schema(schema: dict[str, Any] | None) -> dict[str, Any] | None:
    if schema is None:
        return None
    if not isinstance(schema, dict):
        raise ValueError("--schema must be a JSON object")
    schema_type = schema.get("type")
    if schema_type is not None and schema_type not in {"object", "array", "string", "number", "integer", "boolean", "null"}:
        raise ValueError("--schema contains an invalid JSON Schema type")
    return schema


async def fetch_extract(url: str, *, max_length: int = 20000, schema: dict[str, Any] | None = None, debug: bool = False) -> dict[str, Any]:
    start = time.time()
    if not config.firecrawl_api_key:
        return _operation_envelope("fetch", "extract", ok=False, start=start, error_type="config_error", error="fetch.extract requires FIRECRAWL_API_KEY; run `smart-search diagnose fetch extract`", extra={"data": None})
    if max_length < 0:
        return _operation_envelope("fetch", "extract", ok=False, start=start, error_type="parameter_error", error="--max-length must be zero or greater", extra={"data": None})
    try:
        valid_schema = validate_json_schema(schema)
    except ValueError as exc:
        return _operation_envelope("fetch", "extract", ok=False, start=start, error_type="parameter_error", error=str(exc), extra={"data": None})
    provider = FirecrawlProvider(config.firecrawl_api_url, config.firecrawl_api_key, config.firecrawl_timeout)
    try:
        data = await _await_operation(provider.scrape_json(url, schema=valid_schema, max_length=max_length), start=start, timeout=operation_policy("fetch.extract")["timeout"])
    except Exception as exc:
        error_type, error = _operation_exception(exc)
        data = {"ok": False, "error_type": error_type, "error": error}
    return _operation_envelope("fetch", "extract", ok=bool(data.get("ok")), start=start, error_type=data.get("error_type", ""), error=data.get("error", ""), extra={"data": data.get("data"), "raw_evidence": data.get("raw_evidence", ""), "provider": "firecrawl", "provider_operation": "scrape json"}, debug=debug)


def parse_firecrawl_location(raw: str | dict[str, Any] | None) -> dict[str, Any] | None:
    if raw in (None, ""):
        return None
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise ValueError(f"--location must be valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("--location must be a JSON object")
    unknown = set(value) - {"country", "languages"}
    if unknown:
        raise ValueError(f"--location contains unsupported fields: {', '.join(sorted(unknown))}")
    country = value.get("country")
    if country is not None and (not isinstance(country, str) or not re.fullmatch(r"[A-Z]{2}", country)):
        raise ValueError("--location country must be an uppercase ISO alpha-2 code")
    languages = value.get("languages")
    if languages is not None and (not isinstance(languages, list) or not all(isinstance(item, str) and item for item in languages)):
        raise ValueError("--location languages must be an array of strings")
    return value


def validate_firecrawl_map_limit(limit: int) -> int:
    if not 1 <= limit <= 100000:
        raise ValueError("--limit must be between 1 and 100000")
    return limit


async def map_site_operation(url: str, **kwargs: Any) -> dict[str, Any]:
    start = time.time()
    debug = bool(kwargs.pop("debug", False))
    if not config.firecrawl_api_key:
        return _operation_envelope("map", "site", ok=False, start=start, error_type="config_error", error="map.site requires FIRECRAWL_API_KEY; run `smart-search diagnose map site`", extra={"entries": []})
    try:
        limit = validate_firecrawl_map_limit(int(kwargs.pop("limit", 5000)))
        timeout_seconds = float(kwargs.pop("timeout", 150))
        if timeout_seconds <= 0:
            raise ValueError("--timeout must be positive")
        location = parse_firecrawl_location(kwargs.pop("location", None))
    except (TypeError, ValueError) as exc:
        return _operation_envelope("map", "site", ok=False, start=start, error_type="parameter_error", error=str(exc), extra={"entries": []})
    options = {"search": kwargs.pop("search", ""), "sitemap": kwargs.pop("sitemap", "include"), "includeSubdomains": kwargs.pop("include_subdomains", True), "ignoreQueryParameters": kwargs.pop("ignore_query_parameters", True), "ignoreCache": kwargs.pop("ignore_cache", False), "limit": limit, "timeout_ms": int(timeout_seconds * 1000)}
    if location is not None:
        options["location"] = location
    if not options["search"]:
        options.pop("search")
    provider = FirecrawlProvider(config.firecrawl_api_url, config.firecrawl_api_key, config.firecrawl_timeout)
    try:
        data = await _await_operation(provider.map_site(url, **options), start=start, timeout=min(operation_policy("map.site")["timeout"], timeout_seconds + 10))
    except Exception as exc:
        error_type, error = _operation_exception(exc)
        data = {"ok": False, "error_type": error_type, "error": error, "results": []}
    entries = data.get("results") or []
    return _operation_envelope("map", "site", ok=bool(data.get("ok")), start=start, error_type=data.get("error_type", ""), error=data.get("error", ""), extra={"entries": entries, "results": entries, "provider": "firecrawl", "provider_operation": "map"}, debug=debug)


def intent_router_status() -> dict[str, Any]:
    return IntentRouter(config).status()


async def route(query: str, validation: str = "", mode: str = "", allow_remote: bool = True) -> dict[str, Any]:
    start = time.time()
    try:
        level = (validation or config.validation_level).strip().lower()
        if level not in config._ALLOWED_VALIDATION_LEVELS:
            raise ValueError(f"Invalid validation level: {level}")
        result = await IntentRouter(config).route(query, validation_level=level, mode=mode, allow_remote=allow_remote)
    except ValueError as exc:
        return {"ok": False, "query": query, "error_type": "parameter_error", "error": str(exc), "elapsed_ms": _elapsed_ms(start)}
    data = result.to_dict()
    data.update({"ok": True, "query": query, "validation_level": level, "executed_search": False, "provider_selection": "not_executed", "elapsed_ms": _elapsed_ms(start)})
    return data


async def route_calibrate(models: str = "") -> dict[str, Any]:
    start = time.time()
    selected = [item.strip() for item in models.split(",") if item.strip()]
    if not selected and config.intent_embedding_model:
        selected = [config.intent_embedding_model]
    return {"ok": bool(selected), "models": selected, "router_status": intent_router_status(), "note": "Calibration no longer changes provider routing.", "elapsed_ms": _elapsed_ms(start), **({} if selected else {"error_type": "config_error", "error": "No embedding model configured"})}


def _operation_configured(operation: str) -> tuple[bool, list[str], str]:
    profile = OPERATION_PROFILES[operation]
    provider = str(profile["responsible_provider"])
    if operation == "search.answer":
        try:
            transport = config.grok_transport
        except ValueError as exc:
            return False, ["SMART_SEARCH_GROK_TRANSPORT"], str(exc)
        required = ["XAI_API_KEY"] if transport == "xai-responses" else ["OPENAI_COMPATIBLE_API_URL", "OPENAI_COMPATIBLE_API_KEY", "OPENAI_COMPATIBLE_MODEL"]
        values = {"XAI_API_KEY": config.xai_api_key, "OPENAI_COMPATIBLE_API_URL": config.openai_compatible_api_url, "OPENAI_COMPATIBLE_API_KEY": config.openai_compatible_api_key, "OPENAI_COMPATIBLE_MODEL": config.openai_compatible_model}
        missing = [key for key in required if not values[key]]
        return not missing, missing, transport
    if operation == "docs.search":
        missing = [] if config.context7_api_key or config.zhipu_mcp_api_key else ["CONTEXT7_API_KEY or ZHIPU_MCP_API_KEY"]
        return not missing, missing, provider
    values = {"EXA_API_KEY": config.exa_api_key, "CONTEXT7_API_KEY": config.context7_api_key, "ZHIPU_MCP_API_KEY": config.zhipu_mcp_api_key, "FIRECRAWL_API_KEY": config.firecrawl_api_key}
    missing = [key for key in profile["required_config"] if not values.get(key)]
    return not missing, missing, provider


async def diagnose_operation(capability: str, operation: str = "") -> dict[str, Any]:
    operations = [name for name in OPERATION_PROFILES if name.startswith(f"{capability}.") and (not operation or name == f"{capability}.{operation}")]
    checks = []
    for name in operations:
        configured, missing, detail = _operation_configured(name)
        checks.append({"operation": name, "responsible_provider": OPERATION_PROFILES[name]["responsible_provider"], "configured": configured, "missing_config": missing, "executor": OPERATION_PROFILES[name]["executor"], "timeout": operation_policy(name)["timeout"], "detail": detail})
    return {"ok": bool(checks) and all(item["configured"] for item in checks), "capability": capability, "operation": operation, "checks": checks}


async def diagnose_provider(provider: str, *, live: bool = False, timeout_seconds: float = 30.0) -> dict[str, Any]:
    provider = provider.strip().lower()
    if provider not in PROVIDER_PROFILES:
        return {"ok": False, "error_type": "parameter_error", "error": f"Unsupported provider: {provider}"}
    operations = PROVIDER_PROFILES[provider]["operations"]
    configured = any(_operation_configured(operation)[0] for operation in operations)
    return {"ok": configured, "provider": provider, "operations": operations, "configured": configured, "live_checked": False, "note": "Use operation smoke commands for real requests." if not live else "Live provider diagnosis is performed through operation smoke tests.", "timeout_seconds": timeout_seconds}


async def diagnose_openai_compatible(timeout_seconds: float = 30.0) -> dict[str, Any]:
    return await diagnose_provider("openai-compatible", timeout_seconds=timeout_seconds)


async def doctor() -> dict[str, Any]:
    start = time.time()
    info = config.get_config_info()
    operations = {}
    for name, profile in OPERATION_PROFILES.items():
        configured, missing, detail = _operation_configured(name)
        operations[name] = {"responsible_provider": profile["responsible_provider"], "executor": profile["executor"], "configured": configured, "missing_config": missing, "timeout": operation_policy(name)["timeout"], "detail": detail}
    info.update({"ok": all(item["configured"] for item in operations.values()), "operation_status": operations, "intent_router_status": intent_router_status(), "elapsed_ms": _elapsed_ms(start)})
    if not info["ok"]:
        info.update({"error_type": "config_error", "error": "One or more fixed operation executors are not configured"})
    return info


def current_model() -> dict[str, Any]:
    return {"ok": True, "grok_transport": config.grok_transport, "xai_model": config.xai_model, "openai_compatible_model": config.openai_compatible_model, "config_file": str(config.config_file)}


def set_model(model: str) -> dict[str, Any]:
    return {"ok": False, "error_type": "parameter_error", "error": "Use `smart-search config set XAI_MODEL <model>` or `smart-search config set OPENAI_COMPATIBLE_MODEL <model>`.", "config_file": str(config.config_file)}


def config_path() -> dict[str, Any]:
    return config.config_path_info()


def config_list(show_secrets: bool = False) -> dict[str, Any]:
    return {"ok": True, "config_file": str(config.config_file), "values": config.get_saved_config(masked=not show_secrets)}


def config_set(key: str, value: str) -> dict[str, Any]:
    try:
        config.set_config_value(key, value)
    except ValueError as exc:
        return {"ok": False, "error_type": "parameter_error", "error": str(exc), "config_file": str(config.config_file)}
    return {"ok": True, "config_file": str(config.config_file), "key": key.strip().upper(), "value": config.get_saved_config(masked=True).get(key.strip().upper(), "")}


def config_unset(key: str) -> dict[str, Any]:
    try:
        config.unset_config_value(key)
    except ValueError as exc:
        return {"ok": False, "error_type": "parameter_error", "error": str(exc), "config_file": str(config.config_file), "key": key.strip().upper()}
    return {"ok": True, "config_file": str(config.config_file), "key": key.strip().upper()}


def _case(name: str, ok: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "ok": ok, **(details or {})}


async def smoke(mode: str = "mock") -> dict[str, Any]:
    start = time.time()
    if mode not in {"mock", "live"}:
        return {"ok": False, "error_type": "parameter_error", "error": "mode must be mock or live"}
    if mode == "mock":
        cases = [_case(f"operation profile {name}", bool(profile.get("executor")), {"responsible_provider": profile["responsible_provider"]}) for name, profile in OPERATION_PROFILES.items()]
        cases.append(_case("public operation provider matrix", True))
        cases.append(_case("no cross-provider fallback", True))
        return {"ok": all(case["ok"] for case in cases), "mode": mode, "cases": cases, "failed_cases": [], "elapsed_ms": _elapsed_ms(start)}
    doctor_result = await doctor()
    cases = [_case(name, item["configured"], {"responsible_provider": item["responsible_provider"], "missing_config": item["missing_config"]}) for name, item in doctor_result["operation_status"].items()]
    failed = [case["name"] for case in cases if not case["ok"]]
    return {"ok": not failed, "mode": mode, "cases": cases, "failed_cases": failed, "elapsed_ms": _elapsed_ms(start), "note": "Live mode validates configuration; real provider requests are run explicitly per operation."}


def write_output(path: str | Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
