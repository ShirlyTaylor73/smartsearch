"""Streaming Responses API adapter for `search answer`.

The same request shape is used for xAI, OpenAI and compatible relays; only the
base URL, key, model and tool list differ.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_random_exponential
from tenacity.wait import wait_base

from .base import BaseSearchProvider
from ..config import config
from ..logger import log_info
from ..utils import search_prompt


_logger = logging.getLogger(__name__)
_ssl_warning_emitted = False

TOOL_CHOICE = "required"
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_USAGE_TOKEN_KEYS = ("input_tokens", "output_tokens", "total_tokens")


def get_local_time_info() -> str:
    try:
        local_tz = datetime.now().astimezone().tzinfo
        local_now = datetime.now(local_tz)
    except Exception:
        local_now = datetime.now(timezone.utc)

    weekdays_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekdays_cn[local_now.weekday()]

    return (
        f"[Current Time Context]\n"
        f"- Date: {local_now.strftime('%Y-%m-%d')} ({weekday})\n"
        f"- Time: {local_now.strftime('%H:%M:%S')}\n"
        f"- Timezone: {local_now.tzname() or 'Local'}\n"
    )


def http_error_type(status: int) -> str:
    if status in {400, 422}:
        return "parameter_error"
    if status in {401, 403}:
        return "auth_error"
    if status == 429:
        return "rate_limited"
    if status >= 500:
        return "network_error"
    return "provider_error"


def _exception_error_type(exc: BaseException) -> str:
    if isinstance(exc, ResponsesError):
        return exc.error_type
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        return http_error_type(exc.response.status_code)
    if isinstance(exc, httpx.RequestError):
        return "network_error"
    if not isinstance(exc, Exception):
        return "cancelled"
    return "provider_error"


class ResponsesError(Exception):
    """A response that arrived but does not form a completed answer."""

    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type


@dataclass
class SearchAnswer:
    content: str
    sources: list[dict[str, str]] = field(default_factory=list)


class _WaitWithRetryAfter(wait_base):
    def __init__(self, multiplier: float, max_wait: int):
        self._base_wait = wait_random_exponential(multiplier=multiplier, max=max_wait)
        self._protocol_error_base = 3.0

    def __call__(self, retry_state):
        if retry_state.outcome and retry_state.outcome.failed:
            exc = retry_state.outcome.exception()
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                retry_after = self._parse_retry_after(exc.response)
                if retry_after is not None:
                    return retry_after
            if isinstance(exc, httpx.RemoteProtocolError):
                return self._base_wait(retry_state) + self._protocol_error_base
        return self._base_wait(retry_state)

    def _parse_retry_after(self, response: httpx.Response) -> Optional[float]:
        header = response.headers.get("Retry-After")
        if not header:
            return None
        header = header.strip()

        if header.isdigit():
            return float(header)

        try:
            retry_dt = parsedate_to_datetime(header)
            if retry_dt.tzinfo is None:
                retry_dt = retry_dt.replace(tzinfo=timezone.utc)
            delay = (retry_dt - datetime.now(timezone.utc)).total_seconds()
            return max(0.0, delay)
        except (TypeError, ValueError):
            return None


def _error_detail(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("message") or value.get("reason") or value.get("code") or json.dumps(value, ensure_ascii=False)
    return str(value or "no detail")[:300]


class ResponsesSearchProvider(BaseSearchProvider):
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        tools: list[str],
        *,
        timeout: float = 120.0,
        max_retries: int | None = None,
    ):
        super().__init__(api_url.rstrip("/"), api_key)
        self.model = model
        self.tools = list(tools)
        self.timeout = timeout
        self.max_retries = max_retries
        self._reset_observation()

    def get_provider_name(self) -> str:
        return "responses"

    def _reset_observation(self) -> None:
        # Filled in while the stream is read, so a cancelled call still reports what arrived.
        self.diagnostics: dict[str, Any] = {
            "tools": list(self.tools),
            "tool_choice": TOOL_CHOICE,
            "event_count": 0,
            "attempts": [],
        }
        self._output_tool_calls: dict[str, int] = {}
        self._reported_tool_calls: dict[str, int] = {}

    def tool_was_called(self, tool: str) -> bool:
        return self._reported_tool_calls.get(tool, 0) > 0 or self._output_tool_calls.get(tool, 0) > 0

    def _build_api_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": "smart-search/0.1.0",
        }

    def _get_ssl_verify(self) -> bool:
        global _ssl_warning_emitted
        verify = config.ssl_verify_enabled
        if not verify and not _ssl_warning_emitted:
            _ssl_warning_emitted = True
            _logger.warning("SSL_VERIFY=false: Responses API 请求已禁用 SSL 证书验证，存在安全风险")
        return verify

    def _build_search_payload(self, query: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "instructions": search_prompt,
            "input": [{"role": "user", "content": get_local_time_info() + "\n" + query}],
            "tools": [{"type": tool} for tool in self.tools],
            "tool_choice": TOOL_CHOICE,
            "stream": True,
        }

    async def search(self, query: str, ctx=None) -> SearchAnswer:
        self._reset_observation()
        await log_info(ctx, f"query: {query}", config.debug_enabled)
        response = await self._request(self._build_search_payload(query))
        answer = self._parse_output(response)
        await log_info(ctx, f"content: {answer.content}", config.debug_enabled)
        return answer

    async def _request(self, payload: dict) -> dict:
        timeout = httpx.Timeout(connect=6.0, read=self.timeout, write=10.0, pool=None)
        max_retries = config.retry_max_attempts if self.max_retries is None else self.max_retries

        def retryable(exc: BaseException) -> bool:
            # Once the upstream has started answering, a retry would bill the searches twice.
            if self.diagnostics["event_count"]:
                return False
            if isinstance(exc, httpx.HTTPStatusError):
                return exc.response.status_code in RETRYABLE_STATUS_CODES
            return isinstance(exc, (httpx.ConnectTimeout, httpx.NetworkError, httpx.RemoteProtocolError))

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=self._get_ssl_verify()) as client:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_retries + 1),
                wait=_WaitWithRetryAfter(config.retry_multiplier, config.retry_max_wait),
                retry=retry_if_exception(retryable),
                reraise=True,
            ):
                with attempt:
                    return await self._attempt(client, payload)
        raise ResponsesError("provider_error", "Responses request was not attempted")

    async def _attempt(self, client: httpx.AsyncClient, payload: dict) -> dict:
        start = time.time()
        record: dict[str, Any] = {"status": "error"}
        try:
            async with client.stream(
                "POST", f"{self.api_url}/responses", headers=self._build_api_headers(), json=payload
            ) as response:
                record["http_status"] = response.status_code
                if not response.is_success:
                    await response.aread()
                response.raise_for_status()
                result = await self._read_stream(response)
            record["status"] = "ok"
            return result
        except BaseException as exc:
            record["error_type"] = _exception_error_type(exc)
            raise
        finally:
            record["elapsed_ms"] = round((time.time() - start) * 1000, 2)
            self.diagnostics["attempts"].append(record)

    async def _read_stream(self, response: httpx.Response) -> dict:
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if not raw or raw == "[DONE]":
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ResponsesError("parse_error", f"Responses stream sent invalid JSON: {exc.msg}") from exc
            if not isinstance(event, dict):
                raise ResponsesError("parse_error", "Responses stream sent a non-object event")

            event_type = str(event.get("type") or "")
            self.diagnostics["event_count"] += 1
            self.diagnostics["last_event_type"] = event_type
            body = event.get("response") if isinstance(event.get("response"), dict) else {}
            self._observe_response(body)

            if event_type == "response.completed":
                status = body.get("status") or "completed"
                if status != "completed":
                    raise ResponsesError("provider_error", f"Responses finished with status {status}")
                return body
            if event_type == "response.incomplete":
                detail = _error_detail(body.get("incomplete_details"))
                raise ResponsesError("provider_error", f"Responses answer is incomplete: {detail}")
            if event_type in {"response.failed", "error"}:
                detail = _error_detail(body.get("error") or event.get("error") or event.get("message"))
                raise ResponsesError("provider_error", f"Responses request failed: {detail}")

        if not self.diagnostics["event_count"]:
            raise ResponsesError("parse_error", "Expected a Responses SSE stream but received no events")
        raise ResponsesError("network_error", "Responses stream ended without a terminal event")

    def _observe_response(self, body: dict) -> None:
        for source_key, target_key in (("id", "response_id"), ("model", "response_model"), ("status", "response_status")):
            if body.get(source_key):
                self.diagnostics[target_key] = str(body[source_key])

        output = body.get("output")
        if isinstance(output, list):
            counts: dict[str, int] = {}
            for item in output:
                kind = str(item.get("type") or "") if isinstance(item, dict) else ""
                if kind.endswith("_call"):
                    tool = kind[: -len("_call")]
                    counts[tool] = counts.get(tool, 0) + 1
            self._output_tool_calls = counts

        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        tokens = {key: usage[key] for key in _USAGE_TOKEN_KEYS if isinstance(usage.get(key), int)}
        if tokens:
            self.diagnostics["usage"] = tokens
        details = usage.get("server_side_tool_usage_details")
        reported: dict[str, int] = {}
        for tool in ("web_search", "x_search"):
            value = details.get(f"{tool}_calls") if isinstance(details, dict) else None
            if isinstance(value, int):
                reported[tool] = value
        if reported:
            self._reported_tool_calls = reported

        tool_usage = {
            f"{tool}_calls": self._reported_tool_calls.get(tool, self._output_tool_calls.get(tool))
            for tool in ("web_search", "x_search")
            if tool in self._reported_tool_calls or tool in self._output_tool_calls
        }
        if tool_usage:
            self.diagnostics["tool_usage"] = tool_usage

    def _parse_output(self, response: dict) -> SearchAnswer:
        text_parts: list[str] = []
        sources: list[dict[str, str]] = []
        seen: set[str] = set()

        for item in response.get("output") or []:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for part in item.get("content") or []:
                if not isinstance(part, dict) or part.get("type") != "output_text":
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.strip())
                for annotation in part.get("annotations") or []:
                    if not isinstance(annotation, dict) or annotation.get("type") != "url_citation":
                        continue
                    url = annotation.get("url")
                    if not isinstance(url, str) or not url.startswith(("http://", "https://")) or url in seen:
                        continue
                    seen.add(url)
                    source = {"url": url}
                    title = annotation.get("title")
                    if isinstance(title, str) and title.strip():
                        source["title"] = title.strip()
                    sources.append(source)

        content = "\n\n".join(text_parts)
        if not content:
            raise ResponsesError("provider_error", "Responses returned an empty answer")
        return SearchAnswer(content=content, sources=sources)
