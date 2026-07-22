import asyncio
import json
import time
from typing import Any

import httpx

from ..config import config


RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def _elapsed_ms(start: float) -> float:
    return round((time.time() - start) * 1000, 2)


def _error_payload(exc: BaseException, secret: str) -> dict[str, str]:
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
        message = f"HTTP {status}: {exc.response.text[:300]}"
    elif isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError, TimeoutError)):
        error_type, message = "timeout", "request timed out"
    elif isinstance(exc, httpx.RequestError):
        error_type, message = "network_error", str(exc)
    elif isinstance(exc, (json.JSONDecodeError, TypeError, KeyError)):
        error_type, message = "parse_error", str(exc)
    else:
        error_type, message = "provider_error", str(exc)
    return {"error_type": error_type, "error": message.replace(secret, "***") if secret else message}


class FirecrawlProvider:
    def __init__(self, api_url: str, api_key: str, timeout: float = 30.0):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def _post(self, path: str, payload: dict[str, Any], *, request_timeout: float | None = None) -> dict[str, Any]:
        timeout = httpx.Timeout(connect=6.0, read=request_timeout or self.timeout, write=10.0, pool=None)
        attempts = max(1, config.retry_max_attempts)
        last_error: BaseException | None = None
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            for attempt in range(attempts):
                try:
                    response = await client.post(f"{self.api_url}/{path.lstrip('/')}", headers=self.headers, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    if not isinstance(data, dict):
                        raise TypeError("Firecrawl response must be a JSON object")
                    return data
                except Exception as exc:
                    last_error = exc
                    retryable = isinstance(exc, (httpx.TimeoutException, httpx.RequestError))
                    if isinstance(exc, httpx.HTTPStatusError):
                        retryable = exc.response.status_code in RETRYABLE_STATUS_CODES
                    if not retryable or attempt + 1 >= attempts:
                        raise
        raise last_error or RuntimeError("Firecrawl request failed")

    async def scrape_markdown(self, url: str) -> dict[str, Any]:
        start = time.time()
        try:
            response = await self._post("scrape", {"url": url, "formats": ["markdown"]})
            data = response.get("data") or {}
            markdown = data.get("markdown") or ""
            if not isinstance(markdown, str) or not markdown.strip():
                raise ValueError("Firecrawl returned empty markdown")
            metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
            final_url = metadata.get("sourceURL") or metadata.get("url") or url
            return {"ok": True, "content": markdown, "final_url": final_url, "metadata": metadata, "elapsed_ms": _elapsed_ms(start)}
        except Exception as exc:
            return {"ok": False, **_error_payload(exc, self.api_key), "elapsed_ms": _elapsed_ms(start)}

    async def scrape_json(self, url: str, *, schema: dict[str, Any] | None = None, max_length: int = 20000) -> dict[str, Any]:
        start = time.time()
        json_format: dict[str, Any] = {"type": "json"}
        if schema is not None:
            json_format["schema"] = schema
        try:
            response = await self._post("scrape", {"url": url, "formats": [json_format]})
            payload = response.get("data") or {}
            data = payload.get("json")
            if data is None:
                raise KeyError("Firecrawl response missing data.json")
            raw_evidence = json.dumps(payload, ensure_ascii=False)
            return {"ok": True, "data": data, "raw_evidence": raw_evidence[:max_length], "elapsed_ms": _elapsed_ms(start)}
        except Exception as exc:
            return {"ok": False, **_error_payload(exc, self.api_key), "elapsed_ms": _elapsed_ms(start)}

    async def map_site(self, url: str, **options: Any) -> dict[str, Any]:
        start = time.time()
        timeout_ms = int(options.pop("timeout_ms"))
        payload = {"url": url, **options, "timeout": timeout_ms}
        try:
            response = await self._post("map", payload, request_timeout=max(self.timeout, timeout_ms / 1000 + 10))
            data = response.get("data") or {}
            links = data.get("links") or response.get("links") or []
            entries = []
            for item in links:
                if isinstance(item, str):
                    entries.append({"url": item})
                elif isinstance(item, dict) and item.get("url"):
                    entries.append(dict(item))
            return {"ok": True, "results": entries, "entries": entries, "elapsed_ms": _elapsed_ms(start)}
        except Exception as exc:
            return {"ok": False, **_error_payload(exc, self.api_key), "results": [], "entries": [], "elapsed_ms": _elapsed_ms(start)}
