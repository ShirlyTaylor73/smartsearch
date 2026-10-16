import json
import time
from typing import Any
from urllib.parse import quote

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_random_exponential

from .base import BaseSearchProvider
from ..config import config
from ..logger import log_info


RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
MAX_LIBRARY_REDIRECTS = 3


def _is_retryable_exception(exc) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS_CODES
    return False


def _normalize_library(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id") or "",
        "title": item.get("title") or "",
        "description": item.get("description") or "",
        "trust_score": item.get("trustScore"),
        "benchmark_score": item.get("benchmarkScore"),
        "total_snippets": item.get("totalSnippets"),
        "stars": item.get("stars"),
        "provider": "context7",
    }


class Context7ResponseError(ValueError):
    def __init__(self, data: dict[str, Any], status: int | None = None):
        self.data = data
        self.status = status
        super().__init__(str(data.get("message") or data.get("error")))


def _context7_error(exc: Exception, secret: str) -> dict[str, Any]:
    status = None
    data: dict[str, Any] = {}
    message = str(exc)
    error_type = "provider_error"
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        message = exc.response.text[:1000] or exc.response.reason_phrase
        try:
            body = exc.response.json()
            if isinstance(body, dict):
                data = body
        except ValueError:
            pass
    elif isinstance(exc, Context7ResponseError):
        data, status = exc.data, exc.status
    elif isinstance(exc, httpx.TimeoutException):
        error_type = "timeout"
    elif isinstance(exc, httpx.RequestError):
        error_type = "network_error"
    elif isinstance(exc, ValueError):
        error_type = "parse_error"
    code = str(data.get("error") or "")
    if status in {401, 403} or code == "invalid_api_key":
        error_type = "auth_error"
    elif status == 429 or code == "rate_limit_exceeded":
        error_type = "rate_limited"
    elif status == 400:
        error_type = "parameter_error"
    message = str(data.get("message") or code or message)
    if status is not None:
        message = f"HTTP {status}: {message}"
    result: dict[str, Any] = {"error_type": error_type, "error": message.replace(secret, "***") if secret else message}
    if status is not None:
        result["http_status"] = status
    if code:
        result["provider_error_code"] = code
    return result


def _documentation_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or not any(key in data for key in ("codeSnippets", "infoSnippets")):
        raise ValueError("Context7 response missing documentation snippets")
    code = data.get("codeSnippets", [])
    info = data.get("infoSnippets", [])
    if not isinstance(code, list) or not isinstance(info, list) or not all(isinstance(row, dict) for row in code + info):
        raise ValueError("Context7 returned invalid documentation snippets")
    sections = []
    for row in code:
        parts = [f"### {row.get('codeTitle') or row.get('title') or 'Code example'}"]
        if row.get("codeId"):
            parts.append(f"Source: {row['codeId']}")
        if row.get("codeDescription"):
            parts.append(str(row["codeDescription"]))
        for example in row.get("codeList") or []:
            parts.append(f"```{example.get('language') or ''}\n{example.get('code') or ''}\n```")
        sections.append("\n\n".join(parts))
    for row in info:
        parts = [f"### {row.get('breadcrumb') or 'Documentation'}"]
        if row.get("pageId"):
            parts.append(f"Source: {row['pageId']}")
        parts.append(str(row.get("content") or ""))
        sections.append("\n\n".join(parts))
    return {
        "code_snippets": code, "info_snippets": info, "results": code + info,
        "total": len(code) + len(info), "content": "\n\n".join(sections),
        **{key: data[key] for key in ("version", "rules") if key in data},
    }


class Context7Provider(BaseSearchProvider):
    def __init__(self, api_url: str, api_key: str, timeout: float = 30.0):
        super().__init__(api_url.rstrip("/"), api_key)
        self.timeout = timeout

    def get_provider_name(self) -> str:
        return "Context7"

    async def search(self, query: str, max_results: int = 5) -> str:
        return await self.library(query)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/plain",
            "X-Context7-Source": "smart-search",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def library(self, name: str, query: str = "", ctx=None) -> str:
        request_query = query.strip()
        endpoint = f"{self.api_url}/api/v2/libs/search?libraryName={quote(name)}&query={quote(request_query or name)}"
        await log_info(ctx, f"Context7 library: {name} {request_query}".strip(), config.debug_enabled)
        start_time = time.time()
        try:
            data = await self._get_with_retry(endpoint)
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            raw_results = data if isinstance(data, list) else data.get("results", [])
            results = [_normalize_library(item) for item in raw_results or []]
            output = {
                "ok": True,
                "name": name,
                "query": request_query,
                "provider": "context7",
                "results": results,
                "total": len(results),
                "elapsed_ms": elapsed_ms,
            }
        except Exception as e:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            output = {
                "ok": False,
                **_context7_error(e, self.api_key),
                "query": request_query,
                "provider": "context7",
                "elapsed_ms": elapsed_ms,
            }
        return json.dumps(output, ensure_ascii=False, indent=2)

    async def documentation_search(
        self,
        query: str,
        *,
        library: list[str] | None = None,
        version: str | None = None,
        language: str | None = None,
        ctx=None,
    ) -> str:
        params = [f"query={quote(query)}", "type=json"]
        for hint in library or []:
            params.append(f"library={quote(hint)}")
        if version:
            params.append(f"version={quote(version)}")
        if language:
            params.append(f"language={quote(language)}")
        endpoint = f"{self.api_url}/api/v3/search?{'&'.join(params)}"
        await log_info(ctx, f"Context7 documentation search: {query}", config.debug_enabled)
        start_time = time.time()
        try:
            data = await self._get_with_retry(endpoint)
            return json.dumps({
                "ok": True,
                "query": query,
                "provider": "context7",
                **_documentation_payload(data),
                "elapsed_ms": round((time.time() - start_time) * 1000, 2),
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"ok": False, **_context7_error(e, self.api_key), "query": query, "provider": "context7", "elapsed_ms": round((time.time() - start_time) * 1000, 2)}, ensure_ascii=False, indent=2)

    async def docs(self, library_id: str, query: str, ctx=None) -> str:
        await log_info(ctx, f"Context7 docs: {library_id} {query}", config.debug_enabled)
        start_time = time.time()
        current_library_id = library_id
        redirected_from = ""
        try:
            for _ in range(MAX_LIBRARY_REDIRECTS + 1):
                endpoint = f"{self.api_url}/api/v2/context?libraryId={quote(current_library_id, safe='')}&query={quote(query)}&type=json"
                data = await self._get_with_retry(endpoint, accepted_status_codes={301})
                if not isinstance(data, dict) or not data.get("error"):
                    break
                if data.get("error") != "library_redirected":
                    raise Context7ResponseError(data, 301)
                redirect_url = data.get("redirectUrl")
                if not isinstance(redirect_url, str) or not redirect_url.startswith("/") or redirect_url == current_library_id:
                    raise ValueError("Context7 returned an invalid library redirect")
                redirected_from = redirected_from or current_library_id
                current_library_id = redirect_url
            else:
                raise ValueError("Context7 library redirect limit exceeded")

            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            output = {
                "ok": True,
                "library_id": current_library_id,
                "query": query,
                "provider": "context7",
                **_documentation_payload(data),
                "elapsed_ms": elapsed_ms,
            }
            if redirected_from:
                output["redirected_from"] = redirected_from
        except Exception as e:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            output = {
                "ok": False,
                "library_id": library_id,
                "query": query,
                "provider": "context7",
                **_context7_error(e, self.api_key),
                "elapsed_ms": elapsed_ms,
            }
        return json.dumps(output, ensure_ascii=False, indent=2)

    async def _get_with_retry(self, endpoint: str, accepted_status_codes: set[int] | None = None) -> Any:
        timeout = httpx.Timeout(connect=6.0, read=self.timeout, write=10.0, pool=None)
        accepted_status_codes = accepted_status_codes or set()
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(config.retry_max_attempts + 1),
                wait=wait_random_exponential(multiplier=config.retry_multiplier, max=config.retry_max_wait),
                retry=retry_if_exception(_is_retryable_exception),
                reraise=True,
            ):
                with attempt:
                    response = await client.get(endpoint, headers=self._headers())
                    if response.status_code not in accepted_status_codes:
                        response.raise_for_status()
                    data = response.json()
                    if isinstance(data, dict) and data.get("error") and response.status_code not in accepted_status_codes:
                        raise Context7ResponseError(data, response.status_code)
                    return data
        return {}
